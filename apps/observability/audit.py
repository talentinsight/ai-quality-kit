"""
Structured audit logging with PII redaction and rotating files.
Disabled by default, enabled via AUDIT_LOG_ENABLED=true.
"""

import os
import json
import time
import hashlib
import re
from pathlib import Path
from typing import Dict, Any, Optional, List
from logging.handlers import RotatingFileHandler
import logging

logger = logging.getLogger(__name__)

# PII redaction patterns
EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
PHONE_PATTERN = re.compile(r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b|\(\d{3}\)\s*\d{3}[-.\s]?\d{4}\b')
SSN_PATTERN = re.compile(r'\b\d{3}-\d{2}-\d{4}\b')
CARD_PATTERN = re.compile(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b')
TOKEN_PATTERN = re.compile(r'\b[A-Za-z0-9+/]{32,}={0,2}\b|sk-[a-zA-Z0-9]{16,}\b')

# Sensitive field names that should be redacted
SENSITIVE_FIELDS = {
    'prompt', 'input_text', 'user_message', 'query', 'question', 
    'answer', 'response', 'content', 'text', 'message'
}

class AuditConfig:
    """Audit logging configuration."""
    
    def __init__(self):
        self.enabled = os.getenv("AUDIT_LOG_ENABLED", "false").lower() == "true"
        self.log_path = os.getenv("AUDIT_LOG_PATH", "logs/audit.log")
        self.max_bytes = 10 * 1024 * 1024  # 10MB
        self.backup_count = 5
        
        # Ensure log directory exists
        if self.enabled:
            log_dir = Path(self.log_path).parent
            log_dir.mkdir(parents=True, exist_ok=True)

# Global config and handler
_audit_config: Optional[AuditConfig] = None
_audit_handler: Optional[RotatingFileHandler] = None

def get_audit_config() -> AuditConfig:
    """Get audit configuration (lazy initialization)."""
    global _audit_config
    if _audit_config is None:
        _audit_config = AuditConfig()
    return _audit_config

def get_audit_handler() -> Optional[RotatingFileHandler]:
    """Get audit log handler (lazy initialization)."""
    global _audit_handler
    config = get_audit_config()
    
    if not config.enabled:
        return None
        
    if _audit_handler is None:
        try:
            _audit_handler = RotatingFileHandler(
                config.log_path,
                maxBytes=config.max_bytes,
                backupCount=config.backup_count,
                encoding='utf-8'
            )
            # Set minimal formatter - we'll format JSON ourselves
            _audit_handler.setFormatter(logging.Formatter('%(message)s'))
        except Exception as e:
            logger.error(f"Failed to create audit log handler: {e}")
            return None
    
    return _audit_handler

def safe_str(value: Any, max_length: int = 1000) -> str:
    """Convert value to safe string representation."""
    if value is None:
        return ""
    
    try:
        if isinstance(value, (dict, list)):
            text = json.dumps(value, ensure_ascii=False)[:max_length]
        else:
            text = str(value)[:max_length]
        return text
    except Exception:
        return f"<error_converting_{type(value).__name__}>"

def redact_pii(text: str) -> Dict[str, Any]:
    """
    Redact PII from text and return metadata.
    
    Returns:
        Dict with 'redacted_text', 'original_length', 'hash_prefix'
    """
    if not text or not isinstance(text, str):
        return {
            'redacted_text': text,
            'original_length': 0,
            'hash_prefix': ''
        }
    
    original_length = len(text)
    redacted = text
    
    # Apply PII redaction patterns
    redacted = EMAIL_PATTERN.sub('[EMAIL_REDACTED]', redacted)
    redacted = PHONE_PATTERN.sub('[PHONE_REDACTED]', redacted)
    redacted = SSN_PATTERN.sub('[SSN_REDACTED]', redacted)
    redacted = CARD_PATTERN.sub('[CARD_REDACTED]', redacted)
    redacted = TOKEN_PATTERN.sub('[TOKEN_REDACTED]', redacted)
    
    # Generate hash prefix for original content
    hash_prefix = hashlib.sha256(text.encode('utf-8')).hexdigest()[:8]
    
    return {
        'redacted_text': redacted,
        'original_length': original_length,
        'hash_prefix': hash_prefix
    }

def redact_sensitive_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    """Redact sensitive fields in event data."""
    if not isinstance(data, dict):
        return data
    
    redacted = {}
    for key, value in data.items():
        key_lower = key.lower()
        
        # Check if field name indicates sensitive content
        if any(sensitive in key_lower for sensitive in SENSITIVE_FIELDS):
            if isinstance(value, str) and value:
                pii_data = redact_pii(value)
                redacted[key] = {
                    'redacted': True,
                    'length': pii_data['original_length'],
                    'hash_prefix': pii_data['hash_prefix'],
                    'preview': pii_data['redacted_text'][:100] + ('...' if len(pii_data['redacted_text']) > 100 else '')
                }
            else:
                redacted[key] = {'redacted': True, 'type': type(value).__name__}
        elif isinstance(value, dict):
            redacted[key] = redact_sensitive_fields(value)
        elif isinstance(value, list):
            redacted[key] = [redact_sensitive_fields(item) if isinstance(item, dict) else item for item in value]
        else:
            redacted[key] = value
    
    return redacted

def log_event(event: Dict[str, Any]) -> None:
    """
    Log audit event to structured log file.
    
    Args:
        event: Event dictionary with audit information
    """
    config = get_audit_config()
    if not config.enabled:
        return
    
    handler = get_audit_handler()
    if not handler:
        return
    
    try:
        # Add standard fields
        audit_event = {
            'ts': time.time(),
            'iso_ts': time.strftime('%Y-%m-%dT%H:%M:%S.%fZ', time.gmtime()),
            **event
        }
        
        # Redact sensitive fields
        audit_event = redact_sensitive_fields(audit_event)
        
        # Convert to compact JSON
        log_line = json.dumps(audit_event, ensure_ascii=False, separators=(',', ':'))
        
        # Write to log file
        audit_logger = logging.getLogger('audit')
        audit_logger.setLevel(logging.INFO)
        if handler not in audit_logger.handlers:
            audit_logger.addHandler(handler)
        
        audit_logger.info(log_line)
        
    except Exception as e:
        logger.error(f"Failed to log audit event: {e}")

def log_request_start(request_id: str, route: str, method: str, 
                     user_role: Optional[str] = None) -> None:
    """Log request start event."""
    log_event({
        'event_type': 'request_start',
        'request_id': request_id,
        'route': route,
        'method': method,
        'user_role': user_role
    })

def log_request_end(request_id: str, status: int, latency_ms: int,
                   tokens_in: Optional[int] = None, tokens_out: Optional[int] = None,
                   errors: Optional[List[str]] = None) -> None:
    """Log request completion event."""
    log_event({
        'event_type': 'request_end',
        'request_id': request_id,
        'status': status,
        'latency_ms': latency_ms,
        'tokens_in': tokens_in,
        'tokens_out': tokens_out,
        'errors': errors or []
    })

def log_test_suite_start(request_id: str, suite: str, case_count: int) -> None:
    """Log test suite start event."""
    log_event({
        'event_type': 'suite_start',
        'request_id': request_id,
        'suite': suite,
        'case_count': case_count
    })

def log_test_case_result(request_id: str, suite: str, case_id: str,
                        status: str, score: Optional[float] = None,
                        latency_ms: Optional[int] = None) -> None:
    """Log individual test case result."""
    log_event({
        'event_type': 'case_result',
        'request_id': request_id,
        'suite': suite,
        'case_id': case_id,
        'status': status,
        'score': score,
        'latency_ms': latency_ms
    })

def log_rate_limit_hit(client_id: str, route: str, retry_after_ms: int) -> None:
    """Log rate limit violation."""
    log_event({
        'event_type': 'rate_limit_hit',
        'client_id': client_id,
        'route': route,
        'retry_after_ms': retry_after_ms
    })

def log_auth_failure(client_ip: str, reason: str, route: str) -> None:
    """Log authentication failure."""
    log_event({
        'event_type': 'auth_failure',
        'client_ip': client_ip,
        'reason': reason,
        'route': route
    })

# Cleanup function for testing
def reset_audit_state():
    """Reset audit logging state (for testing)."""
    global _audit_config, _audit_handler
    
    if _audit_handler:
        _audit_handler.close()
    
    _audit_config = None
    _audit_handler = None
