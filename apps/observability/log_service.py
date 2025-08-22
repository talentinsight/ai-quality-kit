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
        run_id = get_run_id() if get_run_id() else f"run_{int(time.time())}"
        
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


def finish_log(log_id: str, answer: str, latency_ms: int, status: str = "ok", error_msg: str = None) -> None:
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


def log_eval_metrics(log_id: str, metric_group: str, metrics: Dict[str, float], extra: Dict = None) -> None:
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
        extra_json = safe_json_serialize(extra) if extra else None
        
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
