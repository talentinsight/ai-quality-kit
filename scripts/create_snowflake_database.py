#!/usr/bin/env python3
"""
Script to create a new Snowflake database and schema for AI Quality Kit.
This creates a dedicated environment for our tables.

Usage:
    python scripts/create_snowflake_database.py
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


def create_database_and_schema():
    """Create new database and schema for AI Quality Kit."""
    print("🚀 Creating Snowflake Database and Schema for AI Quality Kit")
    print("=" * 60)
    
    # Database and schema names
    database_name = "AI_QUALITY_KIT"
    schema_name = "PROD"
    
    try:
        with snowflake_cursor() as cursor:
            # Create database
            print(f"📚 Creating database: {database_name}")
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {database_name}")
            print("✅ Database created successfully")
            
            # Use the new database
            print(f"🔄 Switching to database: {database_name}")
            cursor.execute(f"USE DATABASE {database_name}")
            print("✅ Database switched successfully")
            
            # Create schema
            print(f"📁 Creating schema: {schema_name}")
            cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_name}")
            print("✅ Schema created successfully")
            
            # Use the new schema
            print(f"🔄 Switching to schema: {schema_name}")
            cursor.execute(f"USE SCHEMA {schema_name}")
            print("✅ Schema switched successfully")
            
            # Test table creation
            print("🧪 Testing table creation permissions...")
            test_ddl = """
            CREATE TABLE IF NOT EXISTS TEST_PERMISSIONS (
                ID STRING DEFAULT UUID_STRING(),
                TEST_COL STRING,
                CREATED_AT TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
            );
            """
            cursor.execute(test_ddl)
            print("✅ Table creation test successful")
            
            # Clean up test table
            cursor.execute("DROP TABLE IF EXISTS TEST_PERMISSIONS")
            print("✅ Test table cleaned up")
            
    except Exception as e:
        print(f"❌ Failed to create database/schema: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("🎉 DATABASE AND SCHEMA CREATED SUCCESSFULLY!")
    print("=" * 60)
    print(f"📚 Database: {database_name}")
    print(f"📁 Schema: {schema_name}")
    print("\n📝 Update your .env file with:")
    print(f"SNOWFLAKE_DATABASE={database_name}")
    print(f"SNOWFLAKE_SCHEMA={schema_name}")
    print("\n🚀 Then run: python scripts/create_snowflake_tables.py")
    
    return True


if __name__ == "__main__":
    create_database_and_schema()
