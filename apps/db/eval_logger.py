"""Evaluation results logging to Snowflake."""

import os
import json
from datetime import datetime
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Import snowflake client functions
try:
    from .snowflake_client import snowflake_cursor
except ImportError:
    # Fallback if snowflake client not available
    snowflake_cursor = None

# Load environment variables
load_dotenv()


def is_logging_enabled() -> bool:
    """Check if logging to Snowflake is enabled and environment is complete."""
    if os.getenv("LOG_TO_SNOWFLAKE") != "true":
        return False
    
    # Check if all required Snowflake env vars are present
    required_vars = [
        "SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "SNOWFLAKE_PASSWORD",
        "SNOWFLAKE_ROLE", "SNOWFLAKE_WAREHOUSE", "SNOWFLAKE_DATABASE", "SNOWFLAKE_SCHEMA"
    ]
    
    return all(os.getenv(var) for var in required_vars)


def ensure_tables_note() -> None:
    """Print a reminder about creating required tables (no-op function)."""
    print("Note: Ensure LLM_EVAL_RESULTS table exists in Snowflake with columns:")
    print("  RUN_ID, METRIC_GROUP, METRIC_NAME, METRIC_VALUE, EXTRA, RECORDED_AT")
    print("  Run DDL: CREATE TABLE LLM_EVAL_RESULTS (...)")


def log_evaluation_results(
    run_id: str, 
    metric_group: str, 
    metrics: Dict[str, float], 
    extra: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log evaluation results to Snowflake.
    
    Args:
        run_id: Unique identifier for this evaluation run
        metric_group: Group name for the metrics (e.g., "ragas", "guardrails")
        metrics: Dictionary of metric names to values
        extra: Optional additional data to log
        
    Returns:
        None (logs to Snowflake or prints info message)
    """
    if not is_logging_enabled():
        print(f"Info: Skipping Snowflake logging for {metric_group} metrics (LOG_TO_SNOWFLAKE != true)")
        return
    
    if snowflake_cursor is None:
        print(f"Info: Skipping Snowflake logging - snowflake client not available")
        return
    
    try:
        # Prepare extra data as JSON string
        extra_json = json.dumps(extra) if extra else None
        recorded_at = datetime.utcnow()
        
        # Log each metric as a separate row
        with snowflake_cursor() as cursor:
            for metric_name, metric_value in metrics.items():
                insert_sql = """
                INSERT INTO LLM_EVAL_RESULTS 
                (RUN_ID, METRIC_GROUP, METRIC_NAME, METRIC_VALUE, EXTRA, RECORDED_AT)
                VALUES (%s, %s, %s, %s, %s, %s)
                """
                
                cursor.execute(insert_sql, (
                    run_id,
                    metric_group,
                    metric_name,
                    metric_value,
                    extra_json,
                    recorded_at
                ))
        
        print(f"Info: Logged {len(metrics)} metrics to Snowflake for {metric_group}")
        
    except Exception as e:
        # Log error without exposing secrets
        print(f"Warning: Failed to log {metric_group} metrics to Snowflake: {str(e)}")
        # Don't crash tests - just print warning and continue
