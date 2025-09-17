"""
Test Data Intake API endpoints for Phase 3.1
Handles upload/URL/paste with in-memory processing and ephemeral IDs
"""

import json
import uuid
import time
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from io import StringIO
import yaml
import requests
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Form
from pydantic import BaseModel, validator
import pandas as pd

from apps.security.auth import require_user_or_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/testdata", tags=["testdata"])

# In-memory storage for ephemeral test data (TTL: 1 hour)
EPHEMERAL_STORAGE: Dict[str, Dict[str, Any]] = {}
STORAGE_TTL = 3600  # 1 hour in seconds

class UrlRequest(BaseModel):
    url: str
    type: str
    suite_id: str
    
    @validator('url')
    def validate_url(cls, v):
        if not v.startswith(('http://', 'https://')):
            raise ValueError('URL must start with http:// or https://')
        # Block private IPs for security
        import ipaddress
        import urllib.parse
        try:
            parsed = urllib.parse.urlparse(v)
            if parsed.hostname:
                try:
                    ip = ipaddress.ip_address(parsed.hostname)
                    if ip.is_private or ip.is_loopback or ip.is_link_local:
                        raise ValueError('Private IP addresses are not allowed')
                except ipaddress.AddressValueError:
                    # It's a domain name, allow it
                    pass
        except Exception:
            pass  # Allow domain names
        return v

class PasteRequest(BaseModel):
    content: str
    type: str
    suite_id: str
    
    @validator('content')
    def validate_content(cls, v):
        if len(v.strip()) == 0:
            raise ValueError('Content cannot be empty')
        if len(v) > 50 * 1024 * 1024:  # 50MB limit
            raise ValueError('Content too large (max 50MB)')
        return v

class ValidationResponse(BaseModel):
    success: bool
    testdata_id: Optional[str] = None
    type: str
    counts: Optional[Dict[str, int]] = None
    meta: Optional[Dict[str, Any]] = None
    errors: Optional[List[str]] = None
    sample: Optional[List[Dict[str, Any]]] = None

def cleanup_expired_data():
    """Remove expired ephemeral data"""
    current_time = time.time()
    expired_keys = [
        key for key, data in EPHEMERAL_STORAGE.items()
        if current_time - data.get('timestamp', 0) > STORAGE_TTL
    ]
    for key in expired_keys:
        del EPHEMERAL_STORAGE[key]
    
    if expired_keys:
        logger.info(f"Cleaned up {len(expired_keys)} expired test data entries")

def generate_ephemeral_id() -> str:
    """Generate ephemeral test data ID"""
    return f"ephemeral_{uuid.uuid4().hex[:12]}_{int(time.time())}"

def mask_pii_in_sample(data: List[Dict[str, Any]], max_items: int = 3) -> List[Dict[str, Any]]:
    """Mask PII in sample data for UI display"""
    import re
    
    def mask_text(text: str) -> str:
        if not isinstance(text, str):
            return text
        
        # Mask email addresses
        text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]', text)
        # Mask phone numbers
        text = re.sub(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[PHONE]', text)
        # Mask credit card numbers
        text = re.sub(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b', '[CARD]', text)
        # Truncate long text
        if len(text) > 100:
            text = text[:97] + '...'
        return text
    
    masked_sample = []
    for item in data[:max_items]:
        masked_item = {}
        for key, value in item.items():
            if isinstance(value, str):
                masked_item[key] = mask_text(value)
            elif isinstance(value, (int, float, bool)):
                masked_item[key] = value
            else:
                masked_item[key] = str(value)[:50] + ('...' if len(str(value)) > 50 else '')
        masked_sample.append(masked_item)
    
    return masked_sample

def validate_passages(content: str) -> ValidationResponse:
    """Validate passages data (JSONL format)"""
    try:
        lines = content.strip().split('\n')
        passages = []
        
        for i, line in enumerate(lines):
            if not line.strip():
                continue
            try:
                passage = json.loads(line)
                if not isinstance(passage, dict):
                    return ValidationResponse(
                        success=False,
                        type="passages",
                        errors=[f"Line {i+1}: Expected JSON object, got {type(passage).__name__}"]
                    )
                
                # Check required fields
                if 'id' not in passage:
                    return ValidationResponse(
                        success=False,
                        type="passages",
                        errors=[f"Line {i+1}: Missing required field 'id'"]
                    )
                
                if 'text' not in passage:
                    return ValidationResponse(
                        success=False,
                        type="passages",
                        errors=[f"Line {i+1}: Missing required field 'text'"]
                    )
                
                passages.append(passage)
                
            except json.JSONDecodeError as e:
                return ValidationResponse(
                    success=False,
                    type="passages",
                    errors=[f"Line {i+1}: Invalid JSON - {str(e)}"]
                )
        
        if not passages:
            return ValidationResponse(
                success=False,
                type="passages",
                errors=["No valid passages found"]
            )
        
        # Generate ephemeral ID and store
        testdata_id = generate_ephemeral_id()
        EPHEMERAL_STORAGE[testdata_id] = {
            'type': 'passages',
            'data': passages,
            'timestamp': time.time(),
            'counts': {'passages': len(passages)}
        }
        
        return ValidationResponse(
            success=True,
            testdata_id=testdata_id,
            type="passages",
            counts={'passages': len(passages)},
            meta={'avg_length': sum(len(p.get('text', '')) for p in passages) // len(passages)},
            sample=mask_pii_in_sample(passages)
        )
        
    except Exception as e:
        logger.error(f"Passages validation error: {e}", exc_info=True)
        return ValidationResponse(
            success=False,
            type="passages",
            errors=[f"Validation error: {str(e)}"]
        )

def validate_qaset(content: str) -> ValidationResponse:
    """Validate QA set data (JSONL format)"""
    try:
        lines = content.strip().split('\n')
        qa_pairs = []
        
        for i, line in enumerate(lines):
            if not line.strip():
                continue
            try:
                qa = json.loads(line)
                if not isinstance(qa, dict):
                    return ValidationResponse(
                        success=False,
                        type="qaset",
                        errors=[f"Line {i+1}: Expected JSON object, got {type(qa).__name__}"]
                    )
                
                # Check required fields
                required_fields = ['question', 'answer']
                for field in required_fields:
                    if field not in qa:
                        return ValidationResponse(
                            success=False,
                            type="qaset",
                            errors=[f"Line {i+1}: Missing required field '{field}'"]
                        )
                
                qa_pairs.append(qa)
                
            except json.JSONDecodeError as e:
                return ValidationResponse(
                    success=False,
                    type="qaset",
                    errors=[f"Line {i+1}: Invalid JSON - {str(e)}"]
                )
        
        if not qa_pairs:
            return ValidationResponse(
                success=False,
                type="qaset",
                errors=["No valid QA pairs found"]
            )
        
        # Generate ephemeral ID and store
        testdata_id = generate_ephemeral_id()
        EPHEMERAL_STORAGE[testdata_id] = {
            'type': 'qaset',
            'data': qa_pairs,
            'timestamp': time.time(),
            'counts': {'qa_pairs': len(qa_pairs)}
        }
        
        return ValidationResponse(
            success=True,
            testdata_id=testdata_id,
            type="qaset",
            counts={'qa_pairs': len(qa_pairs)},
            meta={'has_ground_truth': all('answer' in qa for qa in qa_pairs)},
            sample=mask_pii_in_sample(qa_pairs)
        )
        
    except Exception as e:
        logger.error(f"QA set validation error: {e}", exc_info=True)
        return ValidationResponse(
            success=False,
            type="qaset",
            errors=[f"Validation error: {str(e)}"]
        )

def validate_attacks(content: str) -> ValidationResponse:
    """Validate attacks data (TXT or YAML format)"""
    try:
        # Try YAML first, then fall back to text
        attacks = []
        
        try:
            # Try parsing as YAML
            yaml_data = yaml.safe_load(content)
            if isinstance(yaml_data, list):
                attacks = yaml_data
            elif isinstance(yaml_data, dict) and 'attacks' in yaml_data:
                attacks = yaml_data['attacks']
            else:
                # Fall back to text format
                attacks = [line.strip() for line in content.strip().split('\n') if line.strip()]
        except yaml.YAMLError:
            # Fall back to text format
            attacks = [line.strip() for line in content.strip().split('\n') if line.strip()]
        
        if not attacks:
            return ValidationResponse(
                success=False,
                type="attacks",
                errors=["No attacks found"]
            )
        
        # Generate ephemeral ID and store
        testdata_id = generate_ephemeral_id()
        EPHEMERAL_STORAGE[testdata_id] = {
            'type': 'attacks',
            'data': attacks,
            'timestamp': time.time(),
            'counts': {'attacks': len(attacks)}
        }
        
        return ValidationResponse(
            success=True,
            testdata_id=testdata_id,
            type="attacks",
            counts={'attacks': len(attacks)},
            meta={'format': 'yaml' if isinstance(yaml_data, (list, dict)) else 'text'},
            sample=mask_pii_in_sample([{'attack': attack} for attack in attacks[:3]])
        )
        
    except Exception as e:
        logger.error(f"Attacks validation error: {e}", exc_info=True)
        return ValidationResponse(
            success=False,
            type="attacks",
            errors=[f"Validation error: {str(e)}"]
        )

def validate_safety(content: str) -> ValidationResponse:
    """Validate safety data (JSON/YAML format)"""
    try:
        # Try JSON first, then YAML
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            data = yaml.safe_load(content)
        
        if not isinstance(data, (list, dict)):
            return ValidationResponse(
                success=False,
                type="safety",
                errors=["Safety data must be JSON array or object"]
            )
        
        # Convert to list if needed
        if isinstance(data, dict):
            if 'safety_tests' in data:
                safety_items = data['safety_tests']
            elif 'tests' in data:
                safety_items = data['tests']
            else:
                safety_items = [data]
        else:
            safety_items = data
        
        if not safety_items:
            return ValidationResponse(
                success=False,
                type="safety",
                errors=["No safety test items found"]
            )
        
        # Generate ephemeral ID and store
        testdata_id = generate_ephemeral_id()
        EPHEMERAL_STORAGE[testdata_id] = {
            'type': 'safety',
            'data': safety_items,
            'timestamp': time.time(),
            'counts': {'safety_tests': len(safety_items)}
        }
        
        return ValidationResponse(
            success=True,
            testdata_id=testdata_id,
            type="safety",
            counts={'safety_tests': len(safety_items)},
            meta={'categories': list(set(item.get('category', 'unknown') for item in safety_items if isinstance(item, dict)))},
            sample=mask_pii_in_sample(safety_items[:3] if isinstance(safety_items[0], dict) else [{'content': item} for item in safety_items[:3]])
        )
        
    except Exception as e:
        logger.error(f"Safety validation error: {e}", exc_info=True)
        return ValidationResponse(
            success=False,
            type="safety",
            errors=[f"Validation error: {str(e)}"]
        )

def validate_generic(content: str, data_type: str) -> ValidationResponse:
    """Generic validator for bias, scenarios, schema, etc."""
    try:
        # Try JSON first, then YAML
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            data = yaml.safe_load(content)
        
        if not isinstance(data, (list, dict)):
            return ValidationResponse(
                success=False,
                type=data_type,
                errors=[f"{data_type} data must be JSON array or object"]
            )
        
        # Convert to list if needed
        if isinstance(data, dict):
            if f'{data_type}_tests' in data:
                items = data[f'{data_type}_tests']
            elif 'tests' in data:
                items = data['tests']
            elif 'items' in data:
                items = data['items']
            else:
                items = [data]
        else:
            items = data
        
        if not items:
            return ValidationResponse(
                success=False,
                type=data_type,
                errors=[f"No {data_type} items found"]
            )
        
        # Generate ephemeral ID and store
        testdata_id = generate_ephemeral_id()
        EPHEMERAL_STORAGE[testdata_id] = {
            'type': data_type,
            'data': items,
            'timestamp': time.time(),
            'counts': {f'{data_type}_items': len(items)}
        }
        
        return ValidationResponse(
            success=True,
            testdata_id=testdata_id,
            type=data_type,
            counts={f'{data_type}_items': len(items)},
            meta={'format': 'json' if isinstance(data, (list, dict)) else 'yaml'},
            sample=mask_pii_in_sample(items[:3] if isinstance(items[0], dict) else [{'content': item} for item in items[:3]])
        )
        
    except Exception as e:
        logger.error(f"{data_type} validation error: {e}", exc_info=True)
        return ValidationResponse(
            success=False,
            type=data_type,
            errors=[f"Validation error: {str(e)}"]
        )

@router.post("/upload", response_model=ValidationResponse)
async def upload_testdata(
    file: UploadFile = File(...),
    type: str = Form(...),
    suite_id: str = Form(None),
    user=Depends(require_user_or_admin)
):
    """Upload test data file with validation"""
    cleanup_expired_data()
    
    # Size check
    MAX_SIZE = 50 * 1024 * 1024  # 50MB
    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=413, detail=f"File too large (max {MAX_SIZE // 1024 // 1024}MB)")
    
    try:
        # Decode content
        text_content = content.decode('utf-8')
        
        # Log metrics only (no raw content)
        logger.info(f"Processing upload: type={type}, size={len(content)}, filename={file.filename}")
        
        # Route to appropriate validator
        if type == 'passages':
            result = validate_passages(text_content)
        elif type == 'qaset':
            result = validate_qaset(text_content)
        elif type == 'attacks':
            result = validate_attacks(text_content)
        elif type == 'safety':
            result = validate_safety(text_content)
        elif type in ['bias', 'scenarios', 'schema']:
            result = validate_generic(text_content, type)
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported data type: {type}")
        
        # Log result metrics only
        if result.success:
            logger.info(f"Upload successful: testdata_id={result.testdata_id}, counts={result.counts}")
        else:
            logger.warning(f"Upload validation failed: type={type}, errors={len(result.errors or [])}")
        
        return result
        
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be UTF-8 encoded text")
    except Exception as e:
        logger.error(f"Upload processing error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/url", response_model=ValidationResponse)
async def fetch_url_testdata(
    request: UrlRequest,
    user=Depends(require_user_or_admin)
):
    """Fetch test data from URL with validation"""
    cleanup_expired_data()
    
    try:
        # Fetch with timeout and size limits
        response = requests.get(
            request.url,
            timeout=30,
            stream=True,
            headers={'User-Agent': 'AI-Quality-Kit/1.0'}
        )
        response.raise_for_status()
        
        # Check content length
        MAX_SIZE = 50 * 1024 * 1024  # 50MB
        content_length = response.headers.get('content-length')
        if content_length and int(content_length) > MAX_SIZE:
            raise HTTPException(status_code=413, detail=f"Content too large (max {MAX_SIZE // 1024 // 1024}MB)")
        
        # Read content with size limit
        content = ""
        total_size = 0
        for chunk in response.iter_content(chunk_size=8192, decode_unicode=True):
            total_size += len(chunk.encode('utf-8'))
            if total_size > MAX_SIZE:
                raise HTTPException(status_code=413, detail=f"Content too large (max {MAX_SIZE // 1024 // 1024}MB)")
            content += chunk
        
        # Log metrics only
        logger.info(f"Processing URL fetch: type={request.type}, size={total_size}, url_domain={requests.utils.urlparse(request.url).netloc}")
        
        # Route to appropriate validator
        if request.type == 'passages':
            result = validate_passages(content)
        elif request.type == 'qaset':
            result = validate_qaset(content)
        elif request.type == 'attacks':
            result = validate_attacks(content)
        elif request.type == 'safety':
            result = validate_safety(content)
        elif request.type in ['bias', 'scenarios', 'schema']:
            result = validate_generic(content, request.type)
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported data type: {request.type}")
        
        # Log result metrics only
        if result.success:
            logger.info(f"URL fetch successful: testdata_id={result.testdata_id}, counts={result.counts}")
        else:
            logger.warning(f"URL fetch validation failed: type={request.type}, errors={len(result.errors or [])}")
        
        return result
        
    except HTTPException:
        # Re-raise HTTP exceptions (like 413 for content too large)
        raise
    except requests.RequestException as e:
        logger.error(f"URL fetch error: {e}")
        raise HTTPException(status_code=422, detail=f"Failed to fetch URL: {str(e)}")
    except Exception as e:
        logger.error(f"URL processing error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/paste", response_model=ValidationResponse)
async def paste_testdata(
    request: PasteRequest,
    user=Depends(require_user_or_admin)
):
    """Validate pasted test data content"""
    cleanup_expired_data()
    
    try:
        # Log metrics only
        logger.info(f"Processing paste: type={request.type}, size={len(request.content)}")
        
        # Route to appropriate validator
        if request.type == 'passages':
            result = validate_passages(request.content)
        elif request.type == 'qaset':
            result = validate_qaset(request.content)
        elif request.type == 'attacks':
            result = validate_attacks(request.content)
        elif request.type == 'safety':
            result = validate_safety(request.content)
        elif request.type in ['bias', 'scenarios', 'schema']:
            result = validate_generic(request.content, request.type)
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported data type: {request.type}")
        
        # Log result metrics only
        if result.success:
            logger.info(f"Paste successful: testdata_id={result.testdata_id}, counts={result.counts}")
        else:
            logger.warning(f"Paste validation failed: type={request.type}, errors={len(result.errors or [])}")
        
        return result
        
    except Exception as e:
        logger.error(f"Paste processing error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/template")
async def get_template(type: str, format: str = "jsonl"):
    """Download template file for specific data type and format"""
    import os
    from pathlib import Path
    from fastapi.responses import FileResponse
    
    # Map data types to available template files
    template_files = {
        'passages': {
            'jsonl': 'passages.template.jsonl',
            'xlsx': 'passages.template.xlsx'
        },
        'qaset': {
            'jsonl': 'qaset.template.jsonl', 
            'xlsx': 'qaset.template.xlsx'
        },
        'attacks': {
            'yaml': 'attacks.yaml',
            'json': 'attacks.json'
        },
        'safety': {
            'yaml': 'safety.yaml',
            'json': 'safety.json'
        },
        'bias': {
            'yaml': 'bias.yaml',
            'json': 'bias.json'
        },
        'scenarios': {
            'yaml': 'perf.yaml',
            'json': 'perf.json'
        },
        'schema': {
            'json': 'schema_template.json'
        }
    }
    
    if type not in template_files:
        raise HTTPException(status_code=404, detail=f"Template not found for type: {type}")
    
    available_formats = template_files[type]
    if format not in available_formats:
        raise HTTPException(status_code=404, detail=f"Format {format} not available for type {type}. Available formats: {list(available_formats.keys())}")
    
    # Get template file path
    template_filename = available_formats[format]
    # Find the project root (where data/ folder is located)
    current_file = Path(__file__)
    project_root = current_file
    while project_root.parent != project_root:
        if (project_root / "data" / "templates").exists():
            break
        project_root = project_root.parent
    
    template_path = project_root / "data" / "templates" / template_filename
    
    if not template_path.exists():
        # Fallback to hardcoded templates for missing files
        fallback_templates = {
            'schema_template.json': '{\n  "type": "object",\n  "properties": {\n    "name": {"type": "string"},\n    "age": {"type": "integer", "minimum": 0},\n    "email": {"type": "string", "format": "email"}\n  },\n  "required": ["name", "age"]\n}'
        }
        
        if template_filename in fallback_templates:
            from fastapi.responses import Response
            content_type = 'application/json' if format == 'json' else 'text/plain'
            return Response(
                content=fallback_templates[template_filename],
                media_type=content_type,
                headers={
                    'Content-Disposition': f'attachment; filename="{template_filename}"'
                }
            )
        else:
            raise HTTPException(status_code=404, detail=f"Template file not found: {template_filename}")
    
    # Return the actual template file
    return FileResponse(
        path=str(template_path),
        filename=template_filename,
        media_type='application/octet-stream'
    )

@router.get("/{testdata_id}")
async def get_testdata(
    testdata_id: str,
    user=Depends(require_user_or_admin)
):
    """Get ephemeral test data by ID (for orchestrator use)"""
    cleanup_expired_data()
    
    if testdata_id not in EPHEMERAL_STORAGE:
        raise HTTPException(status_code=404, detail="Test data not found or expired")
    
    data = EPHEMERAL_STORAGE[testdata_id]
    
    # Log access (metrics only)
    logger.info(f"Test data accessed: id={testdata_id}, type={data['type']}, age={time.time() - data['timestamp']:.1f}s")
    
    return {
        'testdata_id': testdata_id,
        'type': data['type'],
        'data': data['data'],
        'counts': data['counts'],
        'timestamp': data['timestamp']
    }

@router.delete("/{testdata_id}")
async def delete_testdata(
    testdata_id: str,
    user=Depends(require_user_or_admin)
):
    """Delete ephemeral test data"""
    if testdata_id in EPHEMERAL_STORAGE:
        data_type = EPHEMERAL_STORAGE[testdata_id]['type']
        del EPHEMERAL_STORAGE[testdata_id]
        logger.info(f"Test data deleted: id={testdata_id}, type={data_type}")
        return {"message": "Test data deleted"}
    else:
        raise HTTPException(status_code=404, detail="Test data not found")
