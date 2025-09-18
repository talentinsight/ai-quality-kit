#!/usr/bin/env python3
"""
Script to check Snowflake logs and tables for AI Quality Kit.
This helps verify that logging, evaluation, and caching are working.

Usage:
    python scripts/check_snowflake_logs.py
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

try:
    from apps.db.snowflake_client import snowflake_cursor
except ImportError:
    print("❌ Error: Cannot import snowflake_client. Make sure you're in the project root.")
    sys.exit(1)

# Load environment variables
load_dotenv()


def check_database_connection():
    """Check database connection and current context."""
    print("🔍 Checking Snowflake Connection...")
    print("=" * 50)
    
    try:
        with snowflake_cursor() as cursor:
            cursor.execute("SELECT CURRENT_DATABASE(), CURRENT_SCHEMA(), CURRENT_USER(), CURRENT_ROLE()")
            result = cursor.fetchone()
            
            if result:
                database, schema, user, role = result
                print(f"✅ Database: {database}")
                print(f"✅ Schema: {schema}")
                print(f"✅ User: {user}")
                print(f"✅ Role: {role}")
                return True
            else:
                print("❌ No connection details returned")
                return False
                
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False


def check_tables_exist():
    """Check if required tables exist."""
    print("\n📋 Checking Required Tables...")
    print("=" * 50)
    
    required_tables = [
        "LLM_API_LOGS_PROD",
        "LLM_API_EVAL_RESULTS_PROD", 
        "LLM_RESPONSE_CACHE_PROD"
    ]
    
    existing_tables = []
    
    try:
        with snowflake_cursor() as cursor:
            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()
            
            for table in tables:
                table_name = table[1]  # Table name is in second column
                existing_tables.append(table_name)
            
            print("📊 Found tables:")
            for table in existing_tables:
                print(f"  - {table}")
            
            print("\n🎯 Required tables:")
            for required in required_tables:
                if required in existing_tables:
                    print(f"  ✅ {required}")
                else:
                    print(f"  ❌ {required}")
                    
            return all(required in existing_tables for required in required_tables)
                    
    except Exception as e:
        print(f"❌ Failed to check tables: {e}")
        return False


def check_api_logs():
    """Check API logs table for recent activity."""
    print("\n📝 Checking API Logs...")
    print("=" * 50)
    
    try:
        with snowflake_cursor() as cursor:
            # Check total count
            cursor.execute("SELECT COUNT(*) FROM LLM_API_LOGS_PROD")
            result = cursor.fetchone()
            total_count = result[0] if result else 0
            print(f"📊 Total API logs: {total_count}")
            
            if total_count > 0:
                # Check recent logs
                cursor.execute("""
                    SELECT 
                        REQUEST_AT,
                        QUERY_TEXT,
                        SOURCE,
                        STATUS,
                        LATENCY_MS
                    FROM LLM_API_LOGS_PROD 
                    ORDER BY REQUEST_AT DESC 
                    LIMIT 5
                """)
                
                recent_logs = cursor.fetchall()
                print(f"\n🕒 Recent API calls (last 5):")
                for log in recent_logs:
                    request_at, query_text, source, status, latency = log
                    print(f"  📅 {request_at} | {source} | {status} | {latency}ms")
                    print(f"     Query: {query_text[:50]}...")
                    print()
            else:
                print("⚠️  No API logs found. Make sure you've made some API calls.")
                
    except Exception as e:
        print(f"❌ Failed to check API logs: {e}")


def check_evaluation_results():
    """Check evaluation results table."""
    print("\n📊 Checking Evaluation Results...")
    print("=" * 50)
    
    try:
        with snowflake_cursor() as cursor:
            # Check total count
            cursor.execute("SELECT COUNT(*) FROM LLM_API_EVAL_RESULTS_PROD")
            result = cursor.fetchone()
            total_count = result[0] if result else 0
            print(f"📊 Total evaluation results: {total_count}")
            
            if total_count > 0:
                # Check recent evaluations
                cursor.execute("""
                    SELECT 
                        METRIC_GROUP,
                        METRIC_NAME,
                        METRIC_VALUE,
                        RECORDED_AT
                    FROM LLM_API_EVAL_RESULTS_PROD 
                    ORDER BY RECORDED_AT DESC 
                    LIMIT 10
                """)
                
                recent_evals = cursor.fetchall()
                print(f"\n🎯 Recent evaluations (last 10):")
                for eval_result in recent_evals:
                    metric_group, metric_name, metric_value, recorded_at = eval_result
                    print(f"  📊 {metric_group}.{metric_name}: {metric_value:.3f} | {recorded_at}")
            else:
                print("⚠️  No evaluation results found.")
                
    except Exception as e:
        print(f"❌ Failed to check evaluation results: {e}")


def check_cache():
    """Check response cache table."""
    print("\n💾 Checking Response Cache...")
    print("=" * 50)
    
    try:
        with snowflake_cursor() as cursor:
            # Check total count
            cursor.execute("SELECT COUNT(*) FROM LLM_RESPONSE_CACHE_PROD")
            result = cursor.fetchone()
            total_count = result[0] if result else 0
            print(f"📊 Total cached responses: {total_count}")
            
            if total_count > 0:
                # Check cache details
                cursor.execute("""
                    SELECT 
                        QUERY_HASH,
                        CONTEXT_VERSION,
                        CREATED_AT,
                        EXPIRES_AT
                    FROM LLM_RESPONSE_CACHE_PROD 
                    ORDER BY CREATED_AT DESC 
                    LIMIT 5
                """)
                
                cache_entries = cursor.fetchall()
                print(f"\n🔄 Recent cache entries (last 5):")
                for entry in cache_entries:
                    query_hash, context_version, created_at, expires_at = entry
                    print(f"  🔑 Hash: {query_hash[:16]}... | Version: {context_version}")
                    print(f"     Created: {created_at} | Expires: {expires_at}")
                    print()
            else:
                print("⚠️  No cached responses found.")
                
    except Exception as e:
        print(f"❌ Failed to check cache: {e}")


def main():
    """Main function to check all Snowflake components."""
    print("🚀 AI Quality Kit - Snowflake Health Check")
    print("=" * 60)
    
    # Check connection
    if not check_database_connection():
        print("❌ Cannot proceed without database connection")
        sys.exit(1)
    
    # Check tables
    tables_exist = check_tables_exist()
    
    if tables_exist:
        # Check data in tables
        check_api_logs()
        check_evaluation_results()
        check_cache()
        
        print("\n" + "=" * 60)
        print("🎉 HEALTH CHECK COMPLETED!")
        print("=" * 60)
        print("✅ All required tables exist")
        print("✅ Database connection working")
        print("\n📚 Next steps:")
        print("1. Make API calls to generate logs")
        print("2. Check logs in Snowflake web interface")
        print("3. Monitor quality metrics")
        
    else:
        print("\n" + "=" * 60)
        print("⚠️  HEALTH CHECK FAILED!")
        print("=" * 60)
        print("❌ Some required tables are missing")
        print("\n🔧 To fix:")
        print("1. Run: python scripts/create_snowflake_tables.py --env prod")
        print("2. Check database permissions")
        print("3. Verify .env configuration")


if __name__ == "__main__":
    main()
