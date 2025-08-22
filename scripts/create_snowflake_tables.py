#!/usr/bin/env python3
"""
Migration script to create required Snowflake tables for AI Quality Kit.
This script follows production best practices for database schema management.

Usage:
    python scripts/create_snowflake_tables.py [--env dev|staging|prod]
"""

import os
import sys
import argparse
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


def get_environment():
    """Get current environment from command line or .env file."""
    parser = argparse.ArgumentParser(description="Create Snowflake tables for AI Quality Kit")
    parser.add_argument("--env", choices=["dev", "staging", "prod"], 
                       default=os.getenv("ENVIRONMENT", "dev"),
                       help="Environment to create tables for")
    args = parser.parse_args()
    return args.env


def create_llm_api_logs_table(cursor, env):
    """Create LLM_API_LOGS table."""
    print(f"📝 Creating LLM_API_LOGS table for {env} environment...")
    
    ddl = f"""
    CREATE TABLE IF NOT EXISTS LLM_API_LOGS_{env.upper()} (
        ID STRING DEFAULT UUID_STRING() PRIMARY KEY,
        RUN_ID STRING,
        REQUEST_AT TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
        RESPONSE_AT TIMESTAMP_NTZ,
        PROVIDER STRING,
        MODEL_NAME STRING,
        QUERY_HASH STRING,
        QUERY_TEXT STRING,
        CONTEXT ARRAY,
        ANSWER STRING,
        SOURCE STRING,              -- 'live' | 'cache'
        LATENCY_MS NUMBER,
        STATUS STRING,              -- 'ok' | 'error'
        ERROR_MSG STRING,
        CREATED_AT TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
    );
    """
    
    try:
        cursor.execute(ddl)
        print("✅ LLM_API_LOGS table created successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to create LLM_API_LOGS table: {e}")
        return False


def create_llm_api_eval_results_table(cursor, env):
    """Create LLM_API_EVAL_RESULTS table."""
    print(f"📊 Creating LLM_API_EVAL_RESULTS table for {env} environment...")
    
    ddl = f"""
    CREATE TABLE IF NOT EXISTS LLM_API_EVAL_RESULTS_{env.upper()} (
        LOG_ID STRING,              -- foreign key to LLM_API_LOGS.ID
        METRIC_GROUP STRING,        -- 'ragas' | 'guardrails' | 'safety'
        METRIC_NAME STRING,         -- e.g., 'faithfulness'
        METRIC_VALUE FLOAT,
        EXTRA VARIANT,
        RECORDED_AT TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
    );
    """
    
    try:
        cursor.execute(ddl)
        print("✅ LLM_API_EVAL_RESULTS table created successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to create LLM_API_EVAL_RESULTS table: {e}")
        return False


def create_llm_response_cache_table(cursor, env):
    """Create LLM_RESPONSE_CACHE table."""
    print(f"💾 Creating LLM_RESPONSE_CACHE table for {env} environment...")
    
    ddl = f"""
    CREATE TABLE IF NOT EXISTS LLM_RESPONSE_CACHE_{env.upper()} (
        QUERY_HASH STRING,
        CONTEXT_VERSION STRING,
        ANSWER STRING,
        CONTEXT ARRAY,
        CREATED_AT TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
        EXPIRES_AT TIMESTAMP_NTZ,
        PRIMARY KEY (QUERY_HASH, CONTEXT_VERSION)
    );
    """
    
    try:
        cursor.execute(ddl)
        print("✅ LLM_RESPONSE_CACHE table created successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to create LLM_RESPONSE_CACHE table: {e}")
        return False


def create_indexes(cursor, env):
    """Create performance indexes."""
    print(f"🚀 Creating performance indexes for {env} environment...")
    
    indexes = [
        f"CREATE INDEX IF NOT EXISTS IDX_API_LOGS_REQUEST_AT_{env.upper()} ON LLM_API_LOGS_{env.upper()}(REQUEST_AT);",
        f"CREATE INDEX IF NOT EXISTS IDX_API_LOGS_QUERY_HASH_{env.upper()} ON LLM_API_LOGS_{env.upper()}(QUERY_HASH);",
        f"CREATE INDEX IF NOT EXISTS IDX_API_LOGS_STATUS_{env.upper()} ON LLM_API_LOGS_{env.upper()}(STATUS);",
        f"CREATE INDEX IF NOT EXISTS IDX_CACHE_EXPIRES_{env.upper()} ON LLM_RESPONSE_CACHE_{env.upper()}(EXPIRES_AT);",
        f"CREATE INDEX IF NOT EXISTS IDX_EVAL_LOG_ID_{env.upper()} ON LLM_API_EVAL_RESULTS_{env.upper()}(LOG_ID);"
    ]
    
    success_count = 0
    for index_ddl in indexes:
        try:
            cursor.execute(index_ddl)
            success_count += 1
        except Exception as e:
            print(f"⚠️  Warning: Failed to create index: {e}")
    
    print(f"✅ Created {success_count}/{len(indexes)} indexes successfully")
    return success_count == len(indexes)


def validate_connection():
    """Validate Snowflake connection and permissions."""
    print("🔍 Validating Snowflake connection...")
    
    try:
        with snowflake_cursor() as cursor:
            cursor.execute("SELECT CURRENT_USER(), CURRENT_ROLE(), CURRENT_DATABASE(), CURRENT_SCHEMA()")
            result = cursor.fetchone()
            
            if result:
                user, role, database, schema = result
                print(f"✅ Connected as: {user}")
                print(f"✅ Role: {role}")
                print(f"✅ Database: {database}")
                print(f"✅ Schema: {schema}")
                
                # Check if user has CREATE TABLE permission (simplified check)
                try:
                    cursor.execute("SELECT CURRENT_USER()")
                    print("✅ User has basic permissions")
                    return True
                except Exception:
                    print("❌ User lacks basic permissions")
                    return False
            else:
                print("❌ Failed to get connection details")
                return False
                
    except Exception as e:
        print(f"❌ Connection validation failed: {e}")
        return False


def main():
    """Main migration function."""
    print("🚀 AI Quality Kit - Snowflake Table Migration")
    print("=" * 50)
    
    # Get environment
    env = get_environment()
    print(f"🎯 Target Environment: {env.upper()}")
    
    # Validate connection
    if not validate_connection():
        print("❌ Migration aborted due to connection/permission issues")
        sys.exit(1)
    
    # Create tables
    success_count = 0
    total_tables = 3
    
    try:
        with snowflake_cursor() as cursor:
            # Create tables
            if create_llm_api_logs_table(cursor, env):
                success_count += 1
            
            if create_llm_api_eval_results_table(cursor, env):
                success_count += 1
            
            if create_llm_response_cache_table(cursor, env):
                success_count += 1
            
            # Create indexes
            create_indexes(cursor, env)
            
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        sys.exit(1)
    
    # Summary
    print("\n" + "=" * 50)
    print("📋 MIGRATION SUMMARY")
    print("=" * 50)
    print(f"✅ Tables created: {success_count}/{total_tables}")
    print(f"🎯 Environment: {env.upper()}")
    
    if success_count == total_tables:
        print("🎉 Migration completed successfully!")
        print("\n📚 Next steps:")
        print("1. Update your .env file with table names:")
        print(f"   LLM_API_LOGS_TABLE=LLM_API_LOGS_{env.upper()}")
        print(f"   LLM_API_EVAL_RESULTS_TABLE=LLM_API_EVAL_RESULTS_{env.upper()}")
        print(f"   LLM_RESPONSE_CACHE_TABLE=LLM_RESPONSE_CACHE_{env.upper()}")
        print("2. Restart your RAG service")
        print("3. Test API calls to verify logging works")
    else:
        print("⚠️  Migration partially completed. Check errors above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
