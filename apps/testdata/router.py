"""FastAPI router for test data intake endpoints."""

import asyncio
import os
import time
import uuid
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging
import httpx
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Response, Request, Form
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError

from apps.security.auth import require_user_or_admin, Principal
from apps.observability.perf import decide_phase_and_latency, record_latency
from apps.utils.pii_redaction import mask_text
from .models import (
    UploadResponse, URLRequest, PasteRequest, TestDataMeta,
    PassageRecord, QARecord, ValidationError,
    validate_jsonl_content, validate_attacks_content, validate_schema_content,
    MAX_FILE_SIZE
)
from .store import get_store, create_bundle
from .excel_convert import convert_excel_file
from .templates.qa_template import (
    create_qa_template, create_passages_template, 
    create_qa_jsonl_template, create_passages_jsonl_template
)

logger = logging.getLogger(__name__)

# Configuration
HTTP_TIMEOUT = int(os.getenv("INTAKE_HTTP_TIMEOUT", "15"))
ALLOWED_EXTENSIONS = {
    "passages": [".jsonl", ".xlsx", ".xls"],
    "qaset": [".jsonl", ".xlsx", ".xls"],
    "attacks": [".txt", ".yaml", ".yml"],
    "schema": [".json"]
}
ALLOWED_CONTENT_TYPES = {
    "passages": ["application/json", "text/plain", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/vnd.ms-excel"],
    "qaset": ["application/json", "text/plain", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/vnd.ms-excel"],
    "attacks": ["text/plain", "application/x-yaml", "text/yaml"],
    "schema": ["application/json"]
}

# Create router
router = APIRouter(prefix="/testdata", tags=["testdata"])

# Metrics counters (simple in-memory counters)
_metrics = {
    "ingest.bytes_total": 0,
    "ingest.records_total": 0
}


def _add_performance_headers(response: Response, start_time: float, route: str):
    """Add performance headers to response."""
    latency_ms = int((time.time() - start_time) * 1000)
    phase, _ = decide_phase_and_latency(start_time)
    response.headers["X-Perf-Phase"] = phase
    response.headers["X-Latency-MS"] = str(latency_ms)
    
    # Add percentile headers if enabled
    p50, p95 = record_latency(route, latency_ms)
    if p50 is not None:
        response.headers["X-P50-MS"] = str(p50)
    if p95 is not None:
        response.headers["X-P95-MS"] = str(p95)


def _increment_metrics(bytes_count: int, records_count: int):
    """Increment internal metrics counters."""
    _metrics["ingest.bytes_total"] += bytes_count
    _metrics["ingest.records_total"] += records_count


def _validate_file_size_and_type(file: UploadFile, artifact_type: str):
    """Validate file size and content type."""
    # Check file size (FastAPI doesn't provide file.size reliably for all cases)
    # We'll check size during content reading
    
    # Check extension
    if file.filename:
        file_ext = os.path.splitext(file.filename.lower())[1]
        if file_ext not in ALLOWED_EXTENSIONS.get(artifact_type, []):
            raise HTTPException(
                status_code=415,
                detail=f"Unsupported file extension for {artifact_type}: {file_ext}. "
                       f"Allowed: {ALLOWED_EXTENSIONS.get(artifact_type, [])}"
            )
    
    # Check content type
    if file.content_type and file.content_type not in ALLOWED_CONTENT_TYPES.get(artifact_type, []):
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported content type for {artifact_type}: {file.content_type}. "
                   f"Allowed: {ALLOWED_CONTENT_TYPES.get(artifact_type, [])}"
        )


async def _read_and_validate_file(file: UploadFile, artifact_type: str) -> tuple[str, Any, List[ValidationError]]:
    """Read file content and validate based on artifact type."""
    # Read content with size check
    content_bytes = await file.read()
    if len(content_bytes) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large: {len(content_bytes)} bytes (max: {MAX_FILE_SIZE})"
        )
    
    content = content_bytes.decode('utf-8')
    _increment_metrics(len(content_bytes), 0)  # Records counted later
    
    # Validate content based on type
    if artifact_type == "passages":
        records, errors = validate_jsonl_content(content, PassageRecord)
        _increment_metrics(0, len(records))
        return content, records, errors
    elif artifact_type == "qaset":
        records, errors = validate_jsonl_content(content, QARecord)
        _increment_metrics(0, len(records))
        return content, records, errors
    elif artifact_type == "attacks":
        attacks, errors = validate_attacks_content(content)
        _increment_metrics(0, len(attacks))
        return content, attacks, errors
    elif artifact_type == "schema":
        schema, errors = validate_schema_content(content)
        _increment_metrics(0, 1 if schema else 0)
        return content, schema, errors
    else:
        raise HTTPException(status_code=400, detail=f"Unknown artifact type: {artifact_type}")


async def _fetch_url_content(url: str, artifact_type: str) -> tuple[str, Any, List[ValidationError]]:
    """Fetch content from URL and validate."""
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            response = await client.get(url)
            response.raise_for_status()
            
            # Check content size
            content = response.text
            if len(content.encode('utf-8')) > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=413,
                    detail=f"Content too large from URL: {len(content.encode('utf-8'))} bytes (max: {MAX_FILE_SIZE})"
                )
            
            # Check content type if provided
            content_type = response.headers.get('content-type', '').split(';')[0]
            if content_type and content_type not in ALLOWED_CONTENT_TYPES.get(artifact_type, []):
                logger.warning(f"Unexpected content type from URL {mask_text(url)}: {content_type}")
            
            _increment_metrics(len(content.encode('utf-8')), 0)
            
            # Validate content
            if artifact_type == "passages":
                records, errors = validate_jsonl_content(content, PassageRecord)
                _increment_metrics(0, len(records))
                return content, records, errors
            elif artifact_type == "qaset":
                records, errors = validate_jsonl_content(content, QARecord)
                _increment_metrics(0, len(records))
                return content, records, errors
            elif artifact_type == "attacks":
                attacks, errors = validate_attacks_content(content)
                _increment_metrics(0, len(attacks))
                return content, attacks, errors
            elif artifact_type == "schema":
                schema, errors = validate_schema_content(content)
                _increment_metrics(0, 1 if schema else 0)
                return content, schema, errors
            else:
                raise HTTPException(status_code=400, detail=f"Unknown artifact type: {artifact_type}")
                
    except httpx.TimeoutException:
        raise HTTPException(status_code=408, detail=f"Timeout fetching URL: {mask_text(url)}")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=400, detail=f"HTTP error fetching URL: {e.response.status_code}")
    except Exception as e:
        logger.error(f"Error fetching URL {mask_text(url)}: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Error fetching URL: {str(e)}")


def _validate_paste_content(content: str, artifact_type: str) -> tuple[Any, List[ValidationError]]:
    """Validate pasted content."""
    if len(content.encode('utf-8')) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"Content too large: {len(content.encode('utf-8'))} bytes (max: {MAX_FILE_SIZE})"
        )
    
    _increment_metrics(len(content.encode('utf-8')), 0)
    
    if artifact_type == "passages":
        records, errors = validate_jsonl_content(content, PassageRecord)
        _increment_metrics(0, len(records))
        return records, errors
    elif artifact_type == "qaset":
        records, errors = validate_jsonl_content(content, QARecord)
        _increment_metrics(0, len(records))
        return records, errors
    elif artifact_type == "attacks":
        attacks, errors = validate_attacks_content(content)
        _increment_metrics(0, len(attacks))
        return attacks, errors
    elif artifact_type == "schema":
        schema, errors = validate_schema_content(content)
        _increment_metrics(0, 1 if schema else 0)
        return schema, errors
    else:
        raise HTTPException(status_code=400, detail=f"Unknown artifact type: {artifact_type}")


@router.post("/upload", response_model=UploadResponse)
async def upload_testdata(
    response: Response,
    passages: Optional[UploadFile] = File(None),
    qaset: Optional[UploadFile] = File(None),
    attacks: Optional[UploadFile] = File(None),
    json_schema: Optional[UploadFile] = File(None),
    principal: Optional[Principal] = Depends(require_user_or_admin())
):
    """Upload test data files via multipart form."""
    start_time = time.time()
    
    try:
        # Check that at least one file is provided
        files = {"passages": passages, "qaset": qaset, "attacks": attacks, "schema": json_schema}
        provided_files = {k: v for k, v in files.items() if v is not None}
        
        if not provided_files:
            raise HTTPException(
                status_code=400,
                detail="At least one file must be provided"
            )
        
        # Process each file
        bundle_data = {}
        raw_payloads = {}
        artifacts = []
        counts = {}
        all_errors = []
        
        for artifact_type, file in provided_files.items():
            try:
                _validate_file_size_and_type(file, artifact_type)
                content, data, errors = await _read_and_validate_file(file, artifact_type)
                
                if errors:
                    all_errors.extend([
                        {"artifact": artifact_type, "error": error.dict()} for error in errors
                    ])
                else:
                    bundle_data[artifact_type] = data
                    raw_payloads[artifact_type] = content
                    artifacts.append(artifact_type)
                    counts[artifact_type] = len(data) if isinstance(data, list) else 1
                    
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error processing {artifact_type} file: {str(e)}")
                all_errors.append({
                    "artifact": artifact_type,
                    "error": {"field": "processing", "message": str(e)}
                })
        
        # If we have validation errors, return them
        if all_errors:
            _add_performance_headers(response, start_time, "/testdata")
            return JSONResponse(
                status_code=400,
                content={
                    "detail": "Validation errors occurred",
                    "validation_errors": all_errors
                }
            )
        
        # Create and store bundle
        bundle = create_bundle(
            passages=bundle_data.get("passages"),
            qaset=bundle_data.get("qaset"),
            attacks=bundle_data.get("attacks"),
            json_schema=bundle_data.get("schema"),
            raw_payloads=raw_payloads
        )
        
        store = get_store()
        testdata_id = store.put_bundle(bundle)
        
        logger.info(f"Successfully uploaded test data bundle {testdata_id} with artifacts: {artifacts}")
        
        _add_performance_headers(response, start_time, "/testdata")
        return UploadResponse(
            testdata_id=testdata_id,
            artifacts=artifacts,
            counts=counts,
            manifest={},
            stats={},
            warnings=[]
        )
        
    except HTTPException:
        _add_performance_headers(response, start_time, "/testdata")
        raise
    except Exception as e:
        _add_performance_headers(response, start_time, "/testdata")
        logger.error(f"Unexpected error in upload endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/", response_model=UploadResponse)
async def upload_testdata_enhanced(
    response: Response,
    # Named fields (preferred approach)
    passages: Optional[UploadFile] = File(None),
    qaset: Optional[UploadFile] = File(None),
    attacks: Optional[UploadFile] = File(None),
    schema: Optional[UploadFile] = File(None),
    # Legacy approach: files[] + kinds[]
    files: Optional[List[UploadFile]] = File(None),
    kinds: Optional[List[str]] = Form(None),
    principal: Optional[Principal] = Depends(require_user_or_admin())
):
    """
    Enhanced upload endpoint supporting both named fields and legacy files[]+kinds[].
    
    Supports Excel conversion and returns manifest, stats, and warnings.
    """
    start_time = time.time()
    
    try:
        # Determine which approach is being used
        named_files = {"passages": passages, "qaset": qaset, "attacks": attacks, "schema": schema}
        provided_named = {k: v for k, v in named_files.items() if v is not None}
        
        # Process files based on approach
        if provided_named:
            # Named fields approach
            file_map = provided_named
        elif files and kinds:
            # Legacy files[] + kinds[] approach
            if len(files) != len(kinds):
                raise HTTPException(
                    status_code=400,
                    detail="files[] and kinds[] arrays must have the same length"
                )
            
            file_map = {}
            for file, kind in zip(files, kinds):
                if kind not in ["passages", "qaset", "attacks", "schema"]:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid kind '{kind}'. Must be one of: passages, qaset, attacks, schema"
                    )
                file_map[kind] = file
        else:
            raise HTTPException(
                status_code=400,
                detail="Either provide named fields (passages, qaset, etc.) or files[] + kinds[] arrays"
            )
        
        # Create temporary directory for this upload
        temp_dir = Path(tempfile.mkdtemp(prefix="testdata_"))
        testdata_id = str(uuid.uuid4())
        bundle_dir = temp_dir / testdata_id
        bundle_dir.mkdir(exist_ok=True)
        
        # Process each file
        manifest = {}
        bundle_data = {}
        raw_payloads = {}
        artifacts = []
        counts = {}
        all_errors = []
        all_warnings = []
        
        for artifact_type, file in file_map.items():
            try:
                _validate_file_size_and_type(file, artifact_type)
                
                # Check if it's an Excel file
                file_ext = Path(file.filename or "").suffix.lower()
                if file_ext in [".xlsx", ".xls"]:
                    # Save Excel file temporarily
                    excel_path = bundle_dir / f"temp_{artifact_type}{file_ext}"
                    with open(excel_path, "wb") as f:
                        content = await file.read()
                        f.write(content)
                    
                    # Convert Excel to JSONL
                    try:
                        detected_type, jsonl_content, records = convert_excel_file(
                            str(excel_path), 
                            target_type=artifact_type if artifact_type in ["passages", "qaset"] else None
                        )
                        
                        # Save converted JSONL
                        jsonl_path = bundle_dir / f"{artifact_type}.jsonl"
                        with open(jsonl_path, "w") as f:
                            f.write(jsonl_content)
                        
                        manifest[artifact_type] = str(jsonl_path)
                        bundle_data[artifact_type] = records
                        raw_payloads[artifact_type] = jsonl_content
                        artifacts.append(artifact_type)
                        counts[artifact_type] = len(records)
                        
                        all_warnings.append(f"Converted Excel {artifact_type} to JSONL ({len(records)} records)")
                        
                        # Clean up temp Excel file
                        excel_path.unlink()
                        
                    except Exception as e:
                        logger.error(f"Excel conversion failed for {artifact_type}: {e}")
                        all_errors.append({
                            "artifact": artifact_type,
                            "error": {"field": "excel_conversion", "message": str(e)}
                        })
                        continue
                else:
                    # Handle regular JSONL/text files
                    content, data, errors = await _read_and_validate_file(file, artifact_type)
                    
                    if errors:
                        all_errors.extend([
                            {"artifact": artifact_type, "error": error.dict()} for error in errors
                        ])
                    else:
                        # Save file to bundle directory
                        file_path = bundle_dir / f"{artifact_type}{file_ext or '.jsonl'}"
                        with open(file_path, "w") as f:
                            f.write(content)
                        
                        manifest[artifact_type] = str(file_path)
                        bundle_data[artifact_type] = data
                        raw_payloads[artifact_type] = content
                        artifacts.append(artifact_type)
                        counts[artifact_type] = len(data) if isinstance(data, list) else 1
                        
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error processing {artifact_type} file: {str(e)}")
                all_errors.append({
                    "artifact": artifact_type,
                    "error": {"field": "processing", "message": str(e)}
                })
        
        # If we have validation errors, return them
        if all_errors:
            _add_performance_headers(response, start_time, "/testdata")
            return JSONResponse(
                status_code=400,
                content={
                    "detail": "Validation errors occurred",
                    "validation_errors": all_errors
                }
            )
        
        # Save manifest.json
        manifest_path = bundle_dir / "manifest.json"
        with open(manifest_path, "w") as f:
            import json
            json.dump(manifest, f, indent=2)
        
        # Run RAG validators if available
        stats = {}
        try:
            from apps.testdata.validators_rag import validate_rag_data
            
            # Get passages and qaset data for validation
            passages_data = bundle_data.get("passages", [])
            qaset_data = bundle_data.get("qaset", [])
            
            if passages_data and qaset_data:
                # Run validation
                validation_result = validate_rag_data(passages_data, qaset_data)
                stats = {
                    "total_passages": len(passages_data),
                    "total_qa_items": len(qaset_data),
                    "duplicate_count": getattr(validation_result, 'duplicate_count', 0),
                    "easy_count": getattr(validation_result, 'easy_count', 0)
                }
                validation_warnings = getattr(validation_result, 'warnings', [])
                all_warnings.extend(validation_warnings)
            
        except ImportError:
            logger.info("RAG validators not available, skipping validation")
        except Exception as e:
            logger.warning(f"RAG validation failed: {e}")
            all_warnings.append(f"Validation warning: {str(e)}")
        
        # Create and store bundle (for compatibility with existing system)
        try:
            # Create bundle with the existing testdata_id
            from datetime import datetime, timedelta
            from .models import TestDataBundle
            
            now = datetime.utcnow()
            expires_at = now + timedelta(hours=24)  # TTL_HOURS
            
            bundle = TestDataBundle(
                testdata_id=testdata_id,  # Use existing ID, not a new one!
                created_at=now,
                expires_at=expires_at,
                passages=bundle_data.get("passages"),
                qaset=bundle_data.get("qaset"),
                attacks=bundle_data.get("attacks"),
                json_schema=bundle_data.get("schema"),
                raw_payloads=raw_payloads or {}
            )
            
            store = get_store()
            store.put_bundle(bundle)
            logger.info(f"Stored test data bundle {testdata_id} in store")
            
        except Exception as e:
            logger.warning(f"Bundle creation failed: {e}")
            # Continue without bundle storage
        
        logger.info(f"Successfully uploaded test data bundle {testdata_id} with artifacts: {artifacts}")
        
        _add_performance_headers(response, start_time, "/testdata")
        return UploadResponse(
            testdata_id=testdata_id,
            artifacts=artifacts,
            counts=counts,
            manifest=manifest,
            stats=stats,
            warnings=all_warnings
        )
        
    except HTTPException:
        _add_performance_headers(response, start_time, "/testdata")
        raise
    except Exception as e:
        _add_performance_headers(response, start_time, "/testdata")
        logger.error(f"Unexpected error in enhanced upload endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{testdata_id}/manifest")
async def get_manifest(
    testdata_id: str,
    principal: Optional[Principal] = Depends(require_user_or_admin())
):
    """Get manifest for uploaded test data."""
    try:
        # Look for manifest in temp directory
        temp_dirs = Path(tempfile.gettempdir()).glob("testdata_*")
        
        for temp_dir in temp_dirs:
            bundle_dir = temp_dir / testdata_id
            manifest_path = bundle_dir / "manifest.json"
            
            if manifest_path.exists():
                import json
                with open(manifest_path) as f:
                    manifest = json.load(f)
                
                # Add TTL info
                import time
                created_time = manifest_path.stat().st_mtime
                ttl_hours = 24  # 24 hour TTL
                expires_at = created_time + (ttl_hours * 3600)
                
                return {
                    "testdata_id": testdata_id,
                    "manifest": manifest,
                    "created_at": created_time,
                    "expires_at": expires_at,
                    "ttl_hours": ttl_hours
                }
        
        raise HTTPException(status_code=404, detail="Test data not found or expired")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving manifest: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/by_url", response_model=UploadResponse)
async def ingest_by_url(
    request: URLRequest,
    response: Response,
    principal: Optional[Principal] = Depends(require_user_or_admin())
):
    """Ingest test data from URLs."""
    start_time = time.time()
    
    try:
        # Process each URL
        bundle_data = {}
        raw_payloads = {}
        artifacts = []
        counts = {}
        all_errors = []
        
        for artifact_type, url in request.urls.items():
            try:
                content, data, errors = await _fetch_url_content(url, artifact_type)
                
                if errors:
                    all_errors.extend([
                        {"artifact": artifact_type, "error": error.dict()} for error in errors
                    ])
                else:
                    bundle_data[artifact_type] = data
                    raw_payloads[artifact_type] = content
                    artifacts.append(artifact_type)
                    counts[artifact_type] = len(data) if isinstance(data, list) else 1
                    
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error processing {artifact_type} URL {mask_text(url)}: {str(e)}")
                all_errors.append({
                    "artifact": artifact_type,
                    "error": {"field": "processing", "message": str(e)}
                })
        
        # If we have validation errors, return them
        if all_errors:
            _add_performance_headers(response, start_time, "/testdata")
            return JSONResponse(
                status_code=400,
                content={
                    "detail": "Validation errors occurred",
                    "validation_errors": all_errors
                }
            )
        
        # Create and store bundle
        bundle = create_bundle(
            passages=bundle_data.get("passages"),
            qaset=bundle_data.get("qaset"),
            attacks=bundle_data.get("attacks"),
            json_schema=bundle_data.get("schema"),
            raw_payloads=raw_payloads
        )
        
        store = get_store()
        testdata_id = store.put_bundle(bundle)
        
        logger.info(f"Successfully ingested test data bundle {testdata_id} from URLs with artifacts: {artifacts}")
        
        _add_performance_headers(response, start_time, "/testdata")
        return UploadResponse(
            testdata_id=testdata_id,
            artifacts=artifacts,
            counts=counts,
            manifest={},
            stats={},
            warnings=[]
        )
        
    except HTTPException:
        _add_performance_headers(response, start_time, "/testdata")
        raise
    except Exception as e:
        _add_performance_headers(response, start_time, "/testdata")
        logger.error(f"Unexpected error in by_url endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/paste", response_model=UploadResponse)
async def ingest_by_paste(
    request: PasteRequest,
    response: Response,
    principal: Optional[Principal] = Depends(require_user_or_admin())
):
    """Ingest test data from pasted content."""
    start_time = time.time()
    
    try:
        # Process each content field
        bundle_data = {}
        raw_payloads = {}
        artifacts = []
        counts = {}
        all_errors = []
        
        content_fields = {
            "passages": request.passages,
            "qaset": request.qaset,
            "attacks": request.attacks,
            "schema": request.json_schema
        }
        
        for artifact_type, content in content_fields.items():
            if content is not None:
                try:
                    data, errors = _validate_paste_content(content, artifact_type)
                    
                    if errors:
                        all_errors.extend([
                            {"artifact": artifact_type, "error": error.dict()} for error in errors
                        ])
                    else:
                        bundle_data[artifact_type] = data
                        raw_payloads[artifact_type] = content
                        artifacts.append(artifact_type)
                        counts[artifact_type] = len(data) if isinstance(data, list) else 1
                        
                except HTTPException:
                    raise
                except Exception as e:
                    logger.error(f"Error processing {artifact_type} paste content: {str(e)}")
                    all_errors.append({
                        "artifact": artifact_type,
                        "error": {"field": "processing", "message": str(e)}
                    })
        
        # If we have validation errors, return them
        if all_errors:
            _add_performance_headers(response, start_time, "/testdata")
            return JSONResponse(
                status_code=400,
                content={
                    "detail": "Validation errors occurred",
                    "validation_errors": all_errors
                }
            )
        
        # Create and store bundle
        bundle = create_bundle(
            passages=bundle_data.get("passages"),
            qaset=bundle_data.get("qaset"),
            attacks=bundle_data.get("attacks"),
            json_schema=bundle_data.get("schema"),
            raw_payloads=raw_payloads
        )
        
        store = get_store()
        testdata_id = store.put_bundle(bundle)
        
        logger.info(f"Successfully ingested test data bundle {testdata_id} from paste with artifacts: {artifacts}")
        
        _add_performance_headers(response, start_time, "/testdata")
        return UploadResponse(
            testdata_id=testdata_id,
            artifacts=artifacts,
            counts=counts,
            manifest={},
            stats={},
            warnings=[]
        )
        
    except HTTPException:
        _add_performance_headers(response, start_time, "/testdata")
        raise
    except Exception as e:
        _add_performance_headers(response, start_time, "/testdata")
        logger.error(f"Unexpected error in paste endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{testdata_id}/meta", response_model=TestDataMeta)
async def get_testdata_meta(
    testdata_id: str,
    response: Response,
    principal: Optional[Principal] = Depends(require_user_or_admin())
):
    """Get metadata for a test data bundle."""
    start_time = time.time()
    
    try:
        store = get_store()
        meta = store.get_meta(testdata_id)
        
        if meta is None:
            _add_performance_headers(response, start_time, "/testdata")
            raise HTTPException(status_code=404, detail="Test data bundle not found or expired")
        
        _add_performance_headers(response, start_time, "/testdata")
        return meta
        
    except HTTPException:
        _add_performance_headers(response, start_time, "/testdata")
        raise
    except Exception as e:
        _add_performance_headers(response, start_time, "/testdata")
        logger.error(f"Unexpected error in meta endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/metrics")
async def get_metrics(
    response: Response,
    principal: Optional[Principal] = Depends(require_user_or_admin())
):
    """Get ingestion metrics (for debugging)."""
    start_time = time.time()
    _add_performance_headers(response, start_time, "/testdata/metrics")
    return _metrics


@router.get("/templates/qa-excel")
async def download_qa_excel_template(
    response: Response,
    principal: Optional[Principal] = Depends(require_user_or_admin())
):
    """Download Excel template for QA set."""
    try:
        template_bytes = create_qa_template()
        
        response.headers["Content-Type"] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        response.headers["Content-Disposition"] = "attachment; filename=qa_template.xlsx"
        
        return Response(
            content=template_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": "attachment; filename=qa_template.xlsx"
            }
        )
    except Exception as e:
        logger.error(f"Error creating QA Excel template: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate template")


@router.get("/templates/passages-excel")
async def download_passages_excel_template(
    response: Response,
    principal: Optional[Principal] = Depends(require_user_or_admin())
):
    """Download Excel template for passages."""
    try:
        template_bytes = create_passages_template()
        
        return Response(
            content=template_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": "attachment; filename=passages_template.xlsx"
            }
        )
    except Exception as e:
        logger.error(f"Error creating passages Excel template: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate template")


@router.get("/templates/qa-jsonl")
async def download_qa_jsonl_template(
    response: Response,
    principal: Optional[Principal] = Depends(require_user_or_admin())
):
    """Download JSONL template for QA set."""
    try:
        template_content = create_qa_jsonl_template()
        
        return Response(
            content=template_content,
            media_type="application/json",
            headers={
                "Content-Disposition": "attachment; filename=qa_template.jsonl"
            }
        )
    except Exception as e:
        logger.error(f"Error creating QA JSONL template: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate template")


@router.get("/templates/passages-jsonl")
async def download_passages_jsonl_template(
    response: Response,
    principal: Optional[Principal] = Depends(require_user_or_admin())
):
    """Download JSONL template for passages."""
    try:
        template_content = create_passages_jsonl_template()
        
        return Response(
            content=template_content,
            media_type="application/json",
            headers={
                "Content-Disposition": "attachment; filename=passages_template.jsonl"
            }
        )
    except Exception as e:
        logger.error(f"Error creating passages JSONL template: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate template")
