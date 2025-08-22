"""Snowflake connectivity smoke test script."""

import sys
import os
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from dotenv import load_dotenv
from apps.db.snowflake_client import snowflake_cursor, env_summary

def main() -> int:
    """
    Run Snowflake connectivity smoke test.
    
    Returns:
        Exit code: 0 for success, 1 for connection error, 2 for missing configuration
    """
    # Load environment variables
    load_dotenv()
    
    print("Snowflake Connectivity Smoke Test")
    print("=" * 40)
    
    # Check environment configuration
    env_status = env_summary()
    missing_vars = [var for var, status in env_status.items() if not status['present']]
    
    if missing_vars:
        print("ERROR: Missing required Snowflake environment variables:")
        for var in missing_vars:
            print(f"  - {var}")
        print("\nPlease configure these variables in your .env file.")
        print("See docs/SNOWFLAKE_SETUP.md for setup instructions.")
        return 2
    
    print("Environment configuration: OK")
    
    # Test connection and run diagnostic query
    try:
        with snowflake_cursor() as cursor:
            print("Database connection: OK")
            
            # Run comprehensive diagnostic query
            query = """
            SELECT 
                CURRENT_ACCOUNT() AS account,
                CURRENT_REGION() AS region,
                CURRENT_ROLE() AS role,
                CURRENT_WAREHOUSE() AS warehouse,
                CURRENT_DATABASE() AS database,
                CURRENT_SCHEMA() AS schema,
                CURRENT_TIMESTAMP() AS timestamp
            """
            
            cursor.execute(query)
            result = cursor.fetchone()
            
            if result:
                print("\nSnowflake Environment Details:")
                print(f"  Account:   {result[0]}")
                print(f"  Region:    {result[1]}")
                print(f"  Role:      {result[2]}")
                print(f"  Warehouse: {result[3]}")
                print(f"  Database:  {result[4]}")
                print(f"  Schema:    {result[5]}")
                print(f"  Timestamp: {result[6]}")
                
                print("\nSnowflake connectivity test: PASSED")
                return 0
            else:
                print("ERROR: Query returned no results")
                return 1
                
    except Exception as e:
        print(f"ERROR: Snowflake connection failed: {str(e)}")
        print("\nTroubleshooting tips:")
        print("1. Verify account name and region are correct")
        print("2. Check username and password")
        print("3. Ensure role has access to specified warehouse/database/schema")
        print("4. Verify network connectivity to Snowflake")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
