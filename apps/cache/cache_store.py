"""Cache store for response caching with Snowflake and in-memory fallback."""

import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import snowflake client functions
try:
    from apps.db.snowflake_client import snowflake_cursor
except ImportError:
    # Fallback if snowflake client not available
    snowflake_cursor = None

# In-memory cache as fallback
_memory_cache: Dict[str, Dict] = {}


def is_cache_enabled() -> bool:
    """Check if caching is enabled."""
    return os.getenv("CACHE_ENABLED", "true").lower() == "true"


def get_cache_ttl() -> int:
    """Get cache TTL in seconds."""
    return int(os.getenv("CACHE_TTL_SECONDS", "86400"))


def get_context_version() -> str:
    """Get current context version."""
    return os.getenv("CONTEXT_VERSION", "v1")


def get_cached(query_hash: str, context_version: str) -> Optional[Dict]:
    """
    Get cached response for query hash and context version.
    
    Args:
        query_hash: Hash of the query
        context_version: Version of context used
        
    Returns:
        Cached response dict or None if not found/expired
    """
    if not is_cache_enabled():
        return None
    
    cache_key = f"{query_hash}:{context_version}"
    
    # Try in-memory cache first (always available)
    if cache_key in _memory_cache:
        cached_item = _memory_cache[cache_key]
        # Check if expired
        if cached_item["expires_at"] > time.time():
            print(f"🔍 DEBUG: Cache HIT (memory): {cache_key[:16]}...")
            return {
                "answer": cached_item["answer"],
                "context": cached_item["context"],
                "created_at": cached_item["created_at"],
                "expires_at": cached_item["expires_at"],
                "source": "memory_cache"
            }
        else:
            # Remove expired entry
            del _memory_cache[cache_key]
            print(f"🔍 DEBUG: Cache EXPIRED (memory): {cache_key[:16]}...")
    
    # Fallback to Snowflake cache if available
    if snowflake_cursor is None:
        print(f"🔍 DEBUG: Cache MISS (memory only): {cache_key[:16]}...")
        return None
    
    try:
        with snowflake_cursor() as cursor:
            # Check for valid cache entry
            select_sql = "SELECT ANSWER, CONTEXT, CREATED_AT, EXPIRES_AT FROM LLM_RESPONSE_CACHE_PROD WHERE QUERY_HASH = %s AND CONTEXT_VERSION = %s AND EXPIRES_AT > CURRENT_TIMESTAMP()"
            
            cursor.execute(select_sql, (query_hash, context_version))
            result = cursor.fetchone()
            
            if result:
                answer, context, created_at, expires_at = result
                
                # Parse context if it's a string (Snowflake array format)
                if isinstance(context, str):
                    try:
                        # Remove ARRAY_CONSTRUCT wrapper and parse
                        if context.startswith('[') and context.endswith(']'):
                            # Simple list format
                            import ast
                            parsed_context = ast.literal_eval(context)
                        else:
                            # ARRAY_CONSTRUCT format, extract items
                            import re
                            # Extract text between quotes
                            parsed_context = re.findall(r'"([^"]*)"', context)
                        context = parsed_context
                    except Exception as e:
                        print(f"Warning: Failed to parse context: {e}")
                        context = []
                
                return {
                    "answer": answer,
                    "context": context,
                    "created_at": created_at,
                    "expires_at": expires_at,
                    "source": "cache"
                }
            
            return None
            
    except Exception as e:
        # Log error without exposing secrets
        print(f"Warning: Cache lookup failed: {str(e)}")
        return None


def set_cache(query_hash: str, context_version: str, answer: str, context: List[str], ttl_seconds: int) -> None:
    """
    Cache response for query hash and context version.
    
    Args:
        query_hash: Hash of the query
        context_version: Version of context used
        answer: Generated answer
        context: Retrieved context passages
        ttl_seconds: Time to live in seconds
    """
    if not is_cache_enabled():
        return
    
    cache_key = f"{query_hash}:{context_version}"
    expires_at_timestamp = time.time() + ttl_seconds
    
    # Always store in memory cache (fast and always available)
    _memory_cache[cache_key] = {
        "answer": answer[:2000] if len(answer) > 2000 else answer,  # Truncate long answers
        "context": context,
        "created_at": time.time(),
        "expires_at": expires_at_timestamp
    }
    print(f"🔍 DEBUG: Cache SET (memory): {cache_key[:16]}... TTL={ttl_seconds}s")
    
    # Also store in Snowflake if available (persistent across restarts)
    if snowflake_cursor is None:
        print(f"🔍 DEBUG: Snowflake unavailable, using memory cache only")
        return
    
    try:
        expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)
        
        with snowflake_cursor() as cursor:
            # Truncate long text to avoid SQL issues
            answer_truncated = answer[:2000] if len(answer) > 2000 else answer
            
            # DEBUG: Print what we're actually building
            print(f"🔍 DEBUG: Context type: {type(context)}")
            print(f"🔍 DEBUG: Context value: {context}")
            
            # Use ARRAY_CONSTRUCT() in subquery approach for Snowflake
            if context:
                # Build array with ARRAY_CONSTRUCT() function
                context_items = ",".join(["'" + item.replace("'", "''") + "'" for item in context])
                context_array = "ARRAY_CONSTRUCT(" + context_items + ")"
                print(f"🔍 DEBUG: Built context_array: {context_array}")
            else:
                context_array = "ARRAY_CONSTRUCT()"
                print(f"🔍 DEBUG: Empty context_array: {context_array}")
            
            # Use subquery approach to avoid VALUES clause issues
            try:
                # Try UPDATE first
                update_sql = "UPDATE LLM_RESPONSE_CACHE_PROD SET ANSWER = %s, CONTEXT = (" + context_array + "), CREATED_AT = CURRENT_TIMESTAMP(), EXPIRES_AT = %s WHERE QUERY_HASH = %s AND CONTEXT_VERSION = %s"
                print(f"🔍 DEBUG: UPDATE SQL: {update_sql}")
                
                cursor.execute(update_sql, (answer_truncated, expires_at, query_hash, context_version))
                
                if cursor.rowcount == 0:
                    # No rows updated, do INSERT - use subquery for array
                    insert_sql = "INSERT INTO LLM_RESPONSE_CACHE_PROD (QUERY_HASH, CONTEXT_VERSION, ANSWER, CONTEXT, CREATED_AT, EXPIRES_AT) SELECT %s, %s, %s, (" + context_array + "), CURRENT_TIMESTAMP(), %s"
                    print(f"🔍 DEBUG: INSERT SQL: {insert_sql}")
                    
                    cursor.execute(insert_sql, (query_hash, context_version, answer_truncated, expires_at))
                    
            except Exception as e:
                print(f"Warning: Cache upsert failed, trying simple insert: {str(e)}")
                # Fallback to simple insert with subquery
                insert_sql = "INSERT INTO LLM_RESPONSE_CACHE_PROD (QUERY_HASH, CONTEXT_VERSION, ANSWER, CONTEXT, CREATED_AT, EXPIRES_AT) SELECT %s, %s, %s, (" + context_array + "), CURRENT_TIMESTAMP(), %s"
                print(f"🔍 DEBUG: FALLBACK INSERT SQL: {insert_sql}")
                
                cursor.execute(insert_sql, (query_hash, context_version, answer_truncated, expires_at))
            
    except Exception as e:
        # Log error without exposing secrets
        print(f"Warning: Cache storage failed: {str(e)}")


def clear_expired_cache() -> None:
    """Clear expired cache entries from both memory and Snowflake."""
    if not is_cache_enabled():
        return
    
    current_time = time.time()
    
    # Clean memory cache
    expired_keys = [
        key for key, item in _memory_cache.items() 
        if item["expires_at"] <= current_time
    ]
    
    for key in expired_keys:
        del _memory_cache[key]
    
    if expired_keys:
        print(f"🔍 DEBUG: Cleaned {len(expired_keys)} expired entries from memory cache")
    
    # Clean Snowflake cache if available
    if snowflake_cursor is None:
        return
    
    try:
        with snowflake_cursor() as cursor:
            delete_sql = "DELETE FROM LLM_RESPONSE_CACHE_PROD WHERE EXPIRES_AT <= CURRENT_TIMESTAMP()"
            cursor.execute(delete_sql)
            
    except Exception as e:
        # Log error without exposing secrets
        print(f"Warning: Snowflake cache cleanup failed: {str(e)}")


def get_cache_stats() -> Dict[str, int]:
    """Get cache statistics."""
    current_time = time.time()
    total_entries = len(_memory_cache)
    expired_entries = sum(
        1 for item in _memory_cache.values() 
        if item["expires_at"] <= current_time
    )
    
    return {
        "total_entries": total_entries,
        "active_entries": total_entries - expired_entries,
        "expired_entries": expired_entries
    }
