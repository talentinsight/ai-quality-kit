"""Hash utilities for query normalization and identification."""

import hashlib
import re


def normalize_query(q: str) -> str:
    """
    Normalize query text for consistent hashing.
    
    Args:
        q: Raw query text
        
    Returns:
        Normalized query string (stripped, whitespace collapsed, lowercase)
    """
    if not q:
        return ""
    
    # Strip whitespace and convert to lowercase
    normalized = q.strip().lower()
    
    # Collapse multiple whitespace characters into single space
    normalized = re.sub(r'\s+', ' ', normalized)
    
    return normalized


def query_hash(q: str) -> str:
    """
    Generate SHA256 hash of normalized query.
    
    Args:
        q: Raw query text
        
    Returns:
        SHA256 hash as hexadecimal string
        
    Note:
        Uses normalized query for consistent hashing of semantically similar queries
    """
    normalized = normalize_query(q)
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()
