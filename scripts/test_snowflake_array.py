#!/usr/bin/env python3
"""
Test script to understand Snowflake array handling and fix the issues.
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

def test_snowflake_array():
    """Test how Snowflake handles arrays."""
    print("🧪 Testing Snowflake array handling...")
    
    try:
        from apps.db.snowflake_client import snowflake_cursor
        
        with snowflake_cursor() as cursor:
            # Test 1: Simple array insert
            print("📝 Test 1: Simple array insert")
            try:
                test_sql = "INSERT INTO LLM_API_LOGS_PROD (RUN_ID, PROVIDER, MODEL_NAME, QUERY_HASH, QUERY_TEXT, CONTEXT, SOURCE, STATUS) VALUES ('test_run', 'test_provider', 'test_model', 'test_hash', 'test_query', ARRAY['test_context'], 'test', 'ok')"
                cursor.execute(test_sql)
                print("✅ Simple array insert successful")
                
                # Clean up
                cursor.execute("DELETE FROM LLM_API_LOGS_PROD WHERE RUN_ID = 'test_run'")
                print("✅ Test data cleaned up")
                
            except Exception as e:
                print(f"❌ Simple array insert failed: {e}")
            
            # Test 2: Empty array insert
            print("\n📝 Test 2: Empty array insert")
            try:
                test_sql = "INSERT INTO LLM_API_LOGS_PROD (RUN_ID, PROVIDER, MODEL_NAME, QUERY_HASH, QUERY_TEXT, CONTEXT, SOURCE, STATUS) VALUES ('test_run2', 'test_provider', 'test_model', 'test_hash2', 'test_query', ARRAY[], 'test', 'ok')"
                cursor.execute(test_sql)
                print("✅ Empty array insert successful")
                
                # Clean up
                cursor.execute("DELETE FROM LLM_API_LOGS_PROD WHERE RUN_ID = 'test_run2'")
                print("✅ Test data cleaned up")
                
            except Exception as e:
                print(f"❌ Empty array insert failed: {e}")
            
            # Test 3: Parameter binding with array
            print("\n📝 Test 3: Parameter binding with array")
            try:
                test_sql = "INSERT INTO LLM_API_LOGS_PROD (RUN_ID, PROVIDER, MODEL_NAME, QUERY_HASH, QUERY_TEXT, CONTEXT, SOURCE, STATUS) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
                cursor.execute(test_sql, ('test_run3', 'test_provider', 'test_model', 'test_hash3', 'test_query', ['test_context'], 'test', 'ok'))
                print("✅ Parameter binding with array successful")
                
                # Clean up
                cursor.execute("DELETE FROM LLM_API_LOGS_PROD WHERE RUN_ID = 'test_run3'")
                print("✅ Test data cleaned up")
                
            except Exception as e:
                print(f"❌ Parameter binding with array failed: {e}")
                
    except Exception as e:
        print(f"❌ Snowflake connection failed: {e}")

def main():
    """Main test function."""
    print("🚀 Testing Snowflake Array Handling")
    print("=" * 40)
    
    test_snowflake_array()
    
    print("\n" + "=" * 40)
    print("📊 TEST COMPLETED")
    print("=" * 40)

if __name__ == "__main__":
    main()
