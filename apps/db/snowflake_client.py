"""Snowflake database client for AI Quality Kit."""

import os
from typing import Dict, Any, Generator
from contextlib import contextmanager
import snowflake.connector
from snowflake.connector.connection import SnowflakeConnection
from snowflake.connector.cursor import SnowflakeCursor
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def get_snowflake_connection() -> SnowflakeConnection:
    """
    Create and return a Snowflake database connection.
    
    Returns:
        Active Snowflake connection object
        
    Raises:
        RuntimeError: If required environment variables are missing or connection fails
    """
    # Required environment variables
    required_vars = [
        'SNOWFLAKE_ACCOUNT',
        'SNOWFLAKE_USER',
        'SNOWFLAKE_PASSWORD',
        'SNOWFLAKE_ROLE',
        'SNOWFLAKE_WAREHOUSE',
        'SNOWFLAKE_DATABASE',
        'SNOWFLAKE_SCHEMA'
    ]
    
    # Check for missing variables
    missing_vars = []
    config = {}
    
    for var in required_vars:
        value = os.getenv(var)
        if not value:
            missing_vars.append(var)
        else:
            # Map environment variable names to Snowflake connector parameters
            param_name = var.replace('SNOWFLAKE_', '').lower()
            config[param_name] = value
    
    if missing_vars:
        raise RuntimeError(
            f"Missing required Snowflake environment variables: {', '.join(missing_vars)}. "
            f"Please set these variables in your .env file or environment."
        )
    
    try:
        # Create connection with validated configuration
        connection = snowflake.connector.connect(**config)
        return connection
    except Exception as e:
        raise RuntimeError(f"Failed to connect to Snowflake: {str(e)}")


@contextmanager
def snowflake_cursor() -> Generator[SnowflakeCursor, None, None]:
    """
    Context manager for Snowflake cursor with automatic cleanup.
    
    Yields:
        Snowflake cursor object
        
    Raises:
        RuntimeError: If connection or cursor creation fails
    """
    connection = None
    cursor = None
    
    try:
        connection = get_snowflake_connection()
        cursor = connection.cursor()
        yield cursor
    finally:
        # Ensure proper cleanup
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass  # Ignore close errors
        if connection:
            try:
                connection.close()
            except Exception:
                pass  # Ignore close errors


def env_summary() -> Dict[str, Any]:
    """
    Provide a summary of Snowflake environment variable configuration.
    
    Returns:
        Dictionary with boolean flags indicating presence of required variables
        and masked values for debugging (passwords are never exposed)
    """
    required_vars = [
        'SNOWFLAKE_ACCOUNT',
        'SNOWFLAKE_USER',
        'SNOWFLAKE_PASSWORD',
        'SNOWFLAKE_ROLE',
        'SNOWFLAKE_WAREHOUSE',
        'SNOWFLAKE_DATABASE',
        'SNOWFLAKE_SCHEMA'
    ]
    
    summary = {}
    
    for var in required_vars:
        value = os.getenv(var)
        is_present = bool(value and value.strip())
        
        # Mask sensitive information
        if var == 'SNOWFLAKE_PASSWORD':
            display_value = '***MASKED***' if is_present else None
        else:
            display_value = value if is_present else None
        
        summary[var] = {
            'present': is_present,
            'value': display_value
        }
    
    return summary


def validate_connection() -> bool:
    """
    Validate Snowflake connection without exposing sensitive information.
    
    Returns:
        True if connection can be established successfully
    """
    try:
        with snowflake_cursor():
            return True
    except Exception:
        return False
