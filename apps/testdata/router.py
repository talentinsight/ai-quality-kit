"""FastAPI router for test data intake endpoints."""

import asyncio
import os
import time
from typing import Dict, List, Optional, Any
import logging
import httpx
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Response, Request
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

logger = logging.getLogger(__name__)

# Configuration
HTTP_TIMEOUT = int(os.getenv("INTAKE_HTTP_TIMEOUT", "15"))
ALLOWED_EXTENSIONS = {
    "passages": [".jsonl"],
    "qaset": [".jsonl"],
    "attacks": [".txt", ".yaml", ".yml"],
    "schema": [".json"]
}
ALLOWED_CONTENT_TYPES = {
    "passages": ["application/json", "text/plain"],
    "qaset": ["application/json", "text/plain"],
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
            counts=counts
        )
        
    except HTTPException:
        _add_performance_headers(response, start_time, "/testdata")
        raise
    except Exception as e:
        _add_performance_headers(response, start_time, "/testdata")
        logger.error(f"Unexpected error in upload endpoint: {str(e)}")
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
            counts=counts
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
            counts=counts
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
