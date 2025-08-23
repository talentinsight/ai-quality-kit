"""
Structured audit logging with PII redaction.
"""
import os
import json
import time
from typing import Any, Dict, List, Set, Optional
import logging

# Configuration
AUDIT_ENABLED = os.getenv("AUDIT_ENABLED", "true").lower() == "true"
AUDIT_REDACT_FIELDS = set(os.getenv("AUDIT_REDACT_FIELDS", "answer,text,inputs,content,response").split(","))

# Logger specifically for audit events (outputs to stdout)
audit_logger = logging.getLogger("audit")
audit_logger.setLevel(logging.INFO)

# Create handler that outputs to stdout if not already configured
if not audit_logger.handlers:
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    
    # Use simple format - we'll output JSON directly
    formatter = logging.Formatter('%(message)s')
    handler.setFormatter(formatter)
    
    audit_logger.addHandler(handler)
    audit_logger.propagate = False  # Don't propagate to root logger


def _redact_value(value: Any) -> Any:
    """Redact a value if it appears to be sensitive."""
    if isinstance(value, str):
        if len(value) > 50:  # Long strings likely contain sensitive data
            return f"[REDACTED:{len(value)}chars]"
        return value
    elif isinstance(value, dict):
        return {k: _redact_value(v) if k.lower() in AUDIT_REDACT_FIELDS else v 
                for k, v in value.items()}
    elif isinstance(value, list):
        return [_redact_value(item) for item in value]
    else:
        return value


def _redact_fields(data: Dict[str, Any], redact_fields: Set[str]) -> Dict[str, Any]:
    """Redact specified fields from audit data."""
    redacted = {}
    
    for key, value in data.items():
        if key.lower() in redact_fields:
            if isinstance(value, str):
                redacted[key] = f"[REDACTED:{len(value)}chars]"
            elif isinstance(value, (list, dict)):
                redacted[key] = f"[REDACTED:{type(value).__name__}]"
            else:
                redacted[key] = "[REDACTED]"
        else:
            # Apply recursive redaction for nested structures
            redacted[key] = _redact_value(value)
    
    return redacted


def audit(event: str, **fields) -> None:
    """
    Emit structured audit log entry.
    
    Args:
        event: Event type/name
        **fields: Additional fields to include in audit log
    """
    if not AUDIT_ENABLED:
        return
    
    # Build base audit record
    audit_record = {
        "timestamp": time.time(),
        "event": event,
        "iso_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    
    # Add additional fields with PII redaction
    if fields:
        redacted_fields = _redact_fields(fields, AUDIT_REDACT_FIELDS)
        audit_record.update(redacted_fields)
    
    # Emit as single JSON line to stdout
    try:
        audit_line = json.dumps(audit_record, separators=(',', ':'), default=str)
        audit_logger.info(audit_line)
    except Exception as e:
        # If audit logging fails, log to standard logger but don't fail the operation
        logging.getLogger(__name__).error(f"Failed to emit audit log: {e}")


def audit_request_accepted(route: str, actor: str, ip: str, run_id: Optional[str] = None, **kwargs) -> None:
    """Audit successful request acceptance."""
    audit(
        "request_accepted",
        route=route,
        actor=actor,
        client_ip=ip,
        run_id=run_id,
        **kwargs
    )


def audit_orchestrator_run_started(run_id: str, suites: List[str], provider: str, model: str, 
                                 actor: str, testdata_id: Optional[str] = None, **kwargs) -> None:
    """Audit orchestrator run start."""
    audit(
        "orchestrator_run_started",
        run_id=run_id,
        suites=suites,
        provider=provider,
        model=model,
        actor=actor,
        testdata_id=testdata_id,
        **kwargs
    )


def audit_orchestrator_run_finished(run_id: str, suites: List[str], provider: str, model: str,
                                  actor: str, duration_ms: float, success: bool, 
                                  testdata_id: Optional[str] = None, **kwargs) -> None:
    """Audit orchestrator run completion."""
    audit(
        "orchestrator_run_finished",
        run_id=run_id,
        suites=suites,
        provider=provider,
        model=model,
        actor=actor,
        duration_ms=duration_ms,
        success=success,
        testdata_id=testdata_id,
        **kwargs
    )


def audit_red_team_finding(run_id: str, attack_type: str, blocked: bool, flagged: bool, 
                         actor: str, **kwargs) -> None:
    """Audit red team security finding."""
    audit(
        "red_team_finding",
        run_id=run_id,
        attack_type=attack_type,
        blocked=blocked,
        flagged=flagged,
        actor=actor,
        **kwargs
    )


def audit_auth_failure(reason: str, ip: str, route: Optional[str] = None, token_prefix: Optional[str] = None, **kwargs) -> None:
    """Audit authentication failure (without exposing token contents)."""
    audit(
        "auth_failure",
        reason=reason,
        client_ip=ip,
        route=route,
        token_prefix=token_prefix,  # Only log hash prefix, never full token
        **kwargs
    )


def audit_testdata_operation(operation: str, testdata_id: str, actor: str, artifact_types: Optional[List[str]] = None,
                           **kwargs) -> None:
    """Audit test data operations."""
    audit(
        "testdata_operation",
        operation=operation,
        testdata_id=testdata_id,
        actor=actor,
        artifact_types=artifact_types or [],
        **kwargs
    )


def audit_provider_call(operation: str, provider: str, model: str, success: bool, duration_ms: float,
                       actor: str, **kwargs) -> None:
    """Audit LLM provider calls."""
    audit(
        "provider_call",
        operation=operation,
        provider=provider,
        model=model,
        success=success,
        duration_ms=duration_ms,
        actor=actor,
        **kwargs
    )


def set_audit_enabled(enabled: bool) -> None:
    """Enable or disable audit logging (useful for testing)."""
    global AUDIT_ENABLED
    AUDIT_ENABLED = enabled


def get_redact_fields() -> Set[str]:
    """Get current set of fields that will be redacted."""
    return AUDIT_REDACT_FIELDS.copy()


def add_redact_field(field_name: str) -> None:
    """Add a field to the redaction list."""
    AUDIT_REDACT_FIELDS.add(field_name.lower())


def remove_redact_field(field_name: str) -> None:
    """Remove a field from the redaction list."""
    AUDIT_REDACT_FIELDS.discard(field_name.lower())
