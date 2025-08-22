#!/usr/bin/env python3
"""Snowflake connectivity ping script."""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def main():
    """Main function to test Snowflake connectivity."""
    print("Snowflake Connectivity Ping Test")
    print("=" * 40)
    
    try:
        # Import snowflake client
        import sys
        sys.path.append('.')
        from apps.db.snowflake_client import snowflake_cursor
        
        # Test connection using context manager
        with snowflake_cursor() as cursor:
            cursor.execute("""
                SELECT 
                    CURRENT_ACCOUNT(), 
                    CURRENT_REGION(), 
                    CURRENT_ROLE(), 
                    CURRENT_WAREHOUSE(), 
                    CURRENT_DATABASE(), 
                    CURRENT_SCHEMA(), 
                    CURRENT_TIMESTAMP()
            """)
            
            result = cursor.fetchone()
            
            if result:
                print("✅ Connection successful!")
                print()
                print("Environment Details:")
                print(f"  Account:   {result[0]}")
                print(f"  Region:    {result[1]}")
                print(f"  Role:      {result[2]}")
                print(f"  Warehouse: {result[3]}")
                print(f"  Database:  {result[4]}")
                print(f"  Schema:    {result[5]}")
                print(f"  Timestamp: {result[6]}")
                print()
                print("Snowflake connectivity test: PASSED")
                sys.exit(0)
            else:
                print("❌ No results returned from query")
                sys.exit(1)
                
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Make sure you're running from the project root with virtual environment activated")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
