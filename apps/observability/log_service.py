"""Logging and live evaluation service for API observability."""

import os
import time
from datetime import datetime
from typing import Dict, List, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import dependencies
try:
    from apps.db.snowflake_client import snowflake_cursor
    from apps.db.run_context import get_run_id
    from apps.utils.json_utils import safe_json_serialize
except ImportError:
    # Fallback if dependencies not available
    snowflake_cursor = None
    get_run_id = None
    safe_json_serialize = None


def is_logging_enabled() -> bool:
    """Check if API logging is enabled."""
    return os.getenv("ENABLE_API_LOGGING", "false").lower() == "true"


def is_live_eval_enabled() -> bool:
    """Check if live evaluation is enabled."""
    return os.getenv("ENABLE_LIVE_EVAL", "false").lower() == "true"


def _get_provider_info() -> Dict[str, str]:
    """Get provider and model information from environment."""
    provider = os.getenv("PROVIDER", "unknown")
    model_name = os.getenv("MODEL_NAME", "unknown")
    
    return {
        "provider": provider,
        "model_name": model_name
    }


def start_log(query_text: str, query_hash: str, context: List[str], source: str) -> str:
    """
    Start logging an API request.
    
    Args:
        query_text: Original query text
        query_hash: Hash of the query
        context: Retrieved context passages
        source: Source of response ('live' or 'cache')
        
    Returns:
        Log ID for tracking this request
    """
    if not is_logging_enabled() or snowflake_cursor is None:
        # Return pseudo-id for no-op logging
        return f"pseudo_{int(time.time())}"
    
    try:
        provider_info = _get_provider_info()
        run_id = get_run_id() if get_run_id is not None and get_run_id() else f"run_{int(time.time())}"
        
        with snowflake_cursor() as cursor:
            # Truncate long text to avoid SQL issues
            query_text_truncated = query_text[:1000] if len(query_text) > 1000 else query_text
            
            # Use ARRAY_CONSTRUCT() in subquery approach for Snowflake
            if context:
                # Build array with ARRAY_CONSTRUCT() function
                context_items = ",".join(["'" + item.replace("'", "''") + "'" for item in context])
                context_array = "ARRAY_CONSTRUCT(" + context_items + ")"
                insert_sql = "INSERT INTO LLM_API_LOGS_PROD (RUN_ID, PROVIDER, MODEL_NAME, QUERY_HASH, QUERY_TEXT, CONTEXT, SOURCE, STATUS) SELECT %s, %s, %s, %s, %s, (" + context_array + "), %s, %s"
                
                print("DEBUG: SQL: " + insert_sql)
                print("DEBUG: Context items: " + str(len(context)) + " items")
                
                cursor.execute(insert_sql, (
                    run_id, provider_info["provider"], provider_info["model_name"], 
                    query_hash, query_text_truncated, source, "ok"
                ))
            else:
                # Use ARRAY_CONSTRUCT() for empty array
                insert_sql = "INSERT INTO LLM_API_LOGS_PROD (RUN_ID, PROVIDER, MODEL_NAME, QUERY_HASH, QUERY_TEXT, CONTEXT, SOURCE, STATUS) SELECT %s, %s, %s, %s, %s, ARRAY_CONSTRUCT(), %s, %s"
                
                print("DEBUG: SQL: " + insert_sql)
                print("DEBUG: Context items: 0 items")
                
                cursor.execute(insert_sql, (
                    run_id, provider_info["provider"], provider_info["model_name"], 
                    query_hash, query_text_truncated, source, "ok"
                ))
            
            # Return generated run_id as log_id
            return str(run_id)
            
    except Exception as e:
        # Log error without exposing secrets
        print(f"Warning: Failed to start logging: {str(e)}")
        return f"error_{int(time.time())}"


def finish_log(log_id: str, answer: str, latency_ms: int, status: str = "ok", error_msg: Optional[str] = None) -> None:
    """
    Complete logging an API request.
    
    Args:
        log_id: Log ID from start_log
        answer: Generated answer
        latency_ms: Response time in milliseconds
        status: Response status ('ok' or 'error')
        error_msg: Error message if status is 'error'
    """
    if not is_logging_enabled() or snowflake_cursor is None or log_id.startswith("pseudo_"):
        return
    
    try:
        with snowflake_cursor() as cursor:
            # Truncate long answer to avoid SQL issues
            answer_truncated = answer[:2000] if len(answer) > 2000 else answer
            
            update_sql = "UPDATE LLM_API_LOGS_PROD SET RESPONSE_AT = CURRENT_TIMESTAMP(), ANSWER = %s, LATENCY_MS = %s, STATUS = %s, ERROR_MSG = %s WHERE RUN_ID = %s"
            
            cursor.execute(update_sql, (
                answer_truncated,
                latency_ms,
                status,
                error_msg,
                log_id
            ))
            
    except Exception as e:
        # Log error without exposing secrets
        print(f"Warning: Failed to complete logging: {str(e)}")


def log_eval_metrics(log_id: str, metric_group: str, metrics: Dict[str, float], extra: Optional[Dict] = None) -> None:
    """
    Log evaluation metrics for an API request.
    
    Args:
        log_id: Log ID from start_log
        metric_group: Group name for metrics (e.g., 'ragas', 'guardrails')
        metrics: Dictionary of metric names to values
        extra: Optional additional data
    """
    if not is_logging_enabled() or snowflake_cursor is None or log_id.startswith("pseudo_"):
        return
    
    try:
        extra_json = safe_json_serialize(extra) if extra and safe_json_serialize is not None else None
        
        with snowflake_cursor() as cursor:
            for metric_name, metric_value in metrics.items():
                insert_sql = "INSERT INTO LLM_API_EVAL_RESULTS_PROD (LOG_ID, METRIC_GROUP, METRIC_NAME, METRIC_VALUE, EXTRA) VALUES (%s, %s, %s, %s, %s)"
                
                cursor.execute(insert_sql, (
                    log_id,
                    metric_group,
                    metric_name,
                    metric_value,
                    extra_json
                ))
                
    except Exception as e:
        # Log error without exposing secrets
        print(f"Warning: Failed to log evaluation metrics: {str(e)}")


# Audit logging functions
def is_audit_enabled() -> bool:
    """Check if audit logging is enabled."""
    return os.getenv("AUDIT_LOG_ENABLED", "false").lower() == "true"


def is_persist_enabled() -> bool:
    """Check if database persistence is enabled."""
    return os.getenv("PERSIST_DB", "false").lower() == "true"


def audit_start(path: str, method: str, role: Optional[str], token_hash_prefix: Optional[str]) -> Optional[str]:
    """
    Start audit logging for a request.
    
    Args:
        path: Request path
        method: HTTP method
        role: User role (if authenticated)
        token_hash_prefix: Short hash prefix of token (never full token)
        
    Returns:
        Audit ID for tracking, None if audit disabled or no Snowflake
    """
    if not is_audit_enabled() or not is_persist_enabled() or snowflake_cursor is None:
        return None
    
    try:
        audit_id = f"audit_{int(time.time() * 1000)}"
        
        with snowflake_cursor() as cursor:
            insert_sql = """
                INSERT INTO API_AUDIT_LOGS (
                    AUDIT_ID, REQUEST_PATH, HTTP_METHOD, USER_ROLE, 
                    TOKEN_HASH_PREFIX, STARTED_AT
                ) VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP())
            """
            
            cursor.execute(insert_sql, (
                audit_id,
                path,
                method,
                role,
                token_hash_prefix
            ))
            
        return audit_id
        
    except Exception as e:
        print(f"Warning: Failed to start audit logging: {str(e)}")
        return None


def audit_finish(audit_id: Optional[str], status_code: int, latency_ms: int, is_cold: bool) -> None:
    """
    Complete audit logging for a request.
    
    Args:
        audit_id: Audit ID from audit_start
        status_code: HTTP status code
        latency_ms: Request latency in milliseconds
        is_cold: Whether this was a cold start
    """
    if not audit_id or not is_audit_enabled() or not is_persist_enabled() or snowflake_cursor is None:
        return
    
    try:
        with snowflake_cursor() as cursor:
            update_sql = """
                UPDATE API_AUDIT_LOGS 
                SET FINISHED_AT = CURRENT_TIMESTAMP(),
                    STATUS_CODE = %s,
                    LATENCY_MS = %s,
                    IS_COLD_START = %s
                WHERE AUDIT_ID = %s
            """
            
            cursor.execute(update_sql, (
                status_code,
                latency_ms,
                is_cold,
                audit_id
            ))
            
    except Exception as e:
        print(f"Warning: Failed to complete audit logging: {str(e)}")
