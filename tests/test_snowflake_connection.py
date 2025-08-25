"""Snowflake connection tests."""

import pytest
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from dotenv import load_dotenv
from apps.db.snowflake_client import snowflake_cursor, env_summary

# Load environment variables
load_dotenv()


@pytest.mark.snowflake
class TestSnowflakeConnection:
    """Test class for Snowflake connectivity."""
    
    def test_snowflake_connection(self):
        """Test basic Snowflake connectivity and query execution."""
        # Check if required environment variables are present
        env_status = env_summary()
        missing_vars = [var for var, status in env_status.items() if not status['present']]
        
        if missing_vars:
            pytest.skip(
                f"Snowflake environment variables not configured. Missing: {', '.join(missing_vars)}. "
                f"Set these variables in your .env file to enable Snowflake tests."
            )
        
        # Test connection and simple query
        try:
            with snowflake_cursor() as cursor:
                # Execute simple test query
                cursor.execute("SELECT 1 AS test_value")
                result = cursor.fetchone()
                
                # Verify result
                assert result is not None, "Query returned no results"
                assert result[0] == 1, f"Expected 1, got {result[0]}"
                
        except Exception as e:
            pytest.fail(f"Snowflake connection test failed: {str(e)}")
    
    def test_snowflake_environment_summary(self):
        """Test environment summary function."""
        summary = env_summary()
        
        # Verify summary structure
        expected_vars = [
            'SNOWFLAKE_ACCOUNT',
            'SNOWFLAKE_USER',
            'SNOWFLAKE_PASSWORD',
            'SNOWFLAKE_ROLE',
            'SNOWFLAKE_WAREHOUSE',
            'SNOWFLAKE_DATABASE',
            'SNOWFLAKE_SCHEMA'
        ]
        
        for var in expected_vars:
            assert var in summary, f"Missing variable {var} in environment summary"
            assert 'present' in summary[var], f"Missing 'present' flag for {var}"
            assert 'value' in summary[var], f"Missing 'value' field for {var}"
        
        # Verify password is masked
        if summary['SNOWFLAKE_PASSWORD']['present']:
            assert summary['SNOWFLAKE_PASSWORD']['value'] == '***MASKED***', \
                "Password should be masked in environment summary"
