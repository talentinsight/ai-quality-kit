"""Test data intake API endpoints for AI Quality Kit orchestrator."""

import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from pydantic import BaseModel

from apps.security.auth import require_user_or_admin, Principal
from .intake.storage import (
    create_bundle_dir, list_bundle, validate_file, delete_bundle,
    sanitize_filename, check_total_size, ALLOWED_FILES
)

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/orchestrator/testdata", tags=["testdata"])


class UploadResponse(BaseModel):
    """Response model for test data upload."""
    testdata_id: str
    files: List[Dict[str, Any]]


class PasteRequest(BaseModel):
    """Request model for pasting test data content."""
    passages_text: Optional[str] = None
    qaset_text: Optional[str] = None
    attacks_text: Optional[str] = None


class BundleManifest(BaseModel):
    """Response model for bundle manifest."""
    testdata_id: str
    created_at: float
    files: List[Dict[str, Any]]


def get_reports_dir() -> Path:
    """Get reports directory path from environment."""
    reports_dir = Path(os.getenv("REPORTS_DIR", "./reports"))
    reports_dir.mkdir(exist_ok=True)
    return reports_dir


@router.post("/upload", response_model=UploadResponse)
async def upload_testdata(
    passages: Optional[UploadFile] = File(None),
    qaset: Optional[UploadFile] = File(None),
    attacks: Optional[UploadFile] = File(None),
    passages_text: Optional[str] = Form(None),
    qaset_text: Optional[str] = Form(None),
    attacks_text: Optional[str] = Form(None),
    principal: Optional[Principal] = Depends(require_user_or_admin())
) -> UploadResponse:
    """
    Upload test data files or text content.
    
    Accepts either multipart file uploads or JSON text content.
    Files are validated and stored in temporary bundle directory.
    
    Args:
        passages: Passages JSONL file
        qaset: QA set JSONL file  
        attacks: Attacks text/YAML file
        passages_text: Passages content as text
        qaset_text: QA set content as text
        attacks_text: Attacks content as text
        principal: Authenticated principal
        
    Returns:
        Upload response with testdata_id and file list
    """
    try:
        reports_dir = get_reports_dir()
        testdata_id, bundle_dir = create_bundle_dir(reports_dir)
        
        saved_files = []
        temp_files = []
        
        # Process file uploads
        file_uploads = [
            (passages, "passages.jsonl", "passages"),
            (qaset, "qaset.jsonl", "qaset"), 
            (attacks, "attacks.txt", "attacks")
        ]
        
        for upload_file, default_name, kind in file_uploads:
            if upload_file and upload_file.filename:
                try:
                    # Sanitize filename
                    filename = sanitize_filename(upload_file.filename)
                    file_path = bundle_dir / filename
                    
                    # Save uploaded content
                    content = await upload_file.read()
                    file_path.write_bytes(content)
                    temp_files.append(file_path)
                    
                    # Validate content
                    validate_file(file_path, kind)
                    saved_files.append(file_path)
                    
                except Exception as e:
                    # Clean up on validation error
                    if file_path.exists():
                        file_path.unlink()
                    raise ValueError(f"Invalid {kind} file: {e}")
        
        # Process text content
        text_content = [
            (passages_text, "passages.jsonl", "passages"),
            (qaset_text, "qaset.jsonl", "qaset"),
            (attacks_text, "attacks.txt", "attacks")
        ]
        
        for text, filename, kind in text_content:
            if text and text.strip():
                try:
                    file_path = bundle_dir / filename
                    file_path.write_text(text, encoding='utf-8')
                    temp_files.append(file_path)
                    
                    # Validate content
                    validate_file(file_path, kind)
                    saved_files.append(file_path)
                    
                except Exception as e:
                    # Clean up on validation error
                    if file_path.exists():
                        file_path.unlink()
                    raise ValueError(f"Invalid {kind} text: {e}")
        
        # Check if any files were provided
        if not saved_files:
            delete_bundle(bundle_dir)
            raise HTTPException(
                status_code=400,
                detail="No valid test data provided. Please upload at least one file or provide text content."
            )
        
        # Check total size
        check_total_size(saved_files)
        
        # Get file manifest
        file_list = list_bundle(bundle_dir)
        
        logger.info(f"Created test data bundle {testdata_id} with {len(file_list)} files")
        
        return UploadResponse(
            testdata_id=testdata_id,
            files=file_list
        )
        
    except ValueError as e:
        # Clean up bundle on validation error
        if 'bundle_dir' in locals():
            delete_bundle(bundle_dir)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Clean up bundle on unexpected error
        if 'bundle_dir' in locals():
            delete_bundle(bundle_dir)
        logger.error(f"Failed to upload test data: {e}")
        raise HTTPException(status_code=500, detail="Failed to process upload")


@router.post("/paste", response_model=UploadResponse)
async def paste_testdata(
    request: PasteRequest,
    principal: Optional[Principal] = Depends(require_user_or_admin())
) -> UploadResponse:
    """
    Upload test data via pasted text content.
    
    Args:
        request: Paste request with text content
        principal: Authenticated principal
        
    Returns:
        Upload response with testdata_id and file list
    """
    try:
        reports_dir = get_reports_dir()
        testdata_id, bundle_dir = create_bundle_dir(reports_dir)
        
        saved_files = []
        
        # Process text content
        text_content = [
            (request.passages_text, "passages.jsonl", "passages"),
            (request.qaset_text, "qaset.jsonl", "qaset"),
            (request.attacks_text, "attacks.txt", "attacks")
        ]
        
        for text, filename, kind in text_content:
            if text and text.strip():
                try:
                    file_path = bundle_dir / filename
                    file_path.write_text(text, encoding='utf-8')
                    
                    # Validate content
                    validate_file(file_path, kind)
                    saved_files.append(file_path)
                    
                except Exception as e:
                    # Clean up on validation error
                    if file_path.exists():
                        file_path.unlink()
                    raise ValueError(f"Invalid {kind} content: {e}")
        
        # Check if any content was provided
        if not saved_files:
            delete_bundle(bundle_dir)
            raise HTTPException(
                status_code=400,
                detail="No valid test data provided. Please provide at least one type of content."
            )
        
        # Check total size
        check_total_size(saved_files)
        
        # Get file manifest
        file_list = list_bundle(bundle_dir)
        
        logger.info(f"Created test data bundle {testdata_id} with {len(file_list)} files from paste")
        
        return UploadResponse(
            testdata_id=testdata_id,
            files=file_list
        )
        
    except ValueError as e:
        # Clean up bundle on validation error
        if 'bundle_dir' in locals():
            delete_bundle(bundle_dir)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Clean up bundle on unexpected error
        if 'bundle_dir' in locals():
            delete_bundle(bundle_dir)
        logger.error(f"Failed to process paste: {e}")
        raise HTTPException(status_code=500, detail="Failed to process content")


@router.get("/{testdata_id}", response_model=BundleManifest)
async def get_testdata_manifest(
    testdata_id: str,
    principal: Optional[Principal] = Depends(require_user_or_admin())
) -> BundleManifest:
    """
    Get manifest for a test data bundle.
    
    Args:
        testdata_id: Test data bundle identifier
        principal: Authenticated principal
        
    Returns:
        Bundle manifest with file list
    """
    reports_dir = get_reports_dir()
    bundle_dir = reports_dir / "intake" / testdata_id
    
    if not bundle_dir.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Test data bundle not found: {testdata_id}"
        )
    
    # Read metadata
    metadata_file = bundle_dir / ".metadata.json"
    if metadata_file.exists():
        import json
        try:
            with open(metadata_file) as f:
                metadata = json.load(f)
            created_at = metadata.get("created_at", 0)
        except (json.JSONDecodeError, OSError):
            created_at = bundle_dir.stat().st_mtime
    else:
        created_at = bundle_dir.stat().st_mtime
    
    # Get file list
    file_list = list_bundle(bundle_dir)
    
    return BundleManifest(
        testdata_id=testdata_id,
        created_at=created_at,
        files=file_list
    )


@router.delete("/{testdata_id}")
async def delete_testdata_bundle(
    testdata_id: str,
    principal: Optional[Principal] = Depends(require_user_or_admin())
):
    """
    Delete a test data bundle.
    
    Args:
        testdata_id: Test data bundle identifier
        principal: Authenticated principal
        
    Returns:
        204 No Content on success
    """
    reports_dir = get_reports_dir()
    bundle_dir = reports_dir / "intake" / testdata_id
    
    # Delete bundle (no error if already gone)
    delete_bundle(bundle_dir)
    
    logger.info(f"Deleted test data bundle {testdata_id}")
    
    return {"status": "deleted"}
