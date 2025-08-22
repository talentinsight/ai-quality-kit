"""JSON utilities using orjson for safe serialization."""

import orjson
from typing import Any, Dict, List, Union


def to_json(obj: Any) -> str:
    """
    Safely serialize object to JSON string using orjson.
    
    Args:
        obj: Object to serialize
        
    Returns:
        JSON string representation
        
    Raises:
        TypeError: If object cannot be serialized
    """
    try:
        return orjson.dumps(obj).decode('utf-8')
    except (TypeError, ValueError) as e:
        raise TypeError(f"Object cannot be serialized to JSON: {e}")


def from_json(s: str) -> Any:
    """
    Safely deserialize JSON string using orjson.
    
    Args:
        s: JSON string to deserialize
        
    Returns:
        Deserialized object
        
    Raises:
        ValueError: If string is not valid JSON
    """
    try:
        return orjson.loads(s)
    except (ValueError, TypeError) as e:
        raise ValueError(f"Invalid JSON string: {e}")


def safe_json_serialize(obj: Any, default: str = "{}") -> str:
    """
    Safely serialize object with fallback to default string.
    
    Args:
        obj: Object to serialize
        default: Default string to return on serialization failure
        
    Returns:
        JSON string or default string on failure
    """
    try:
        return to_json(obj)
    except (TypeError, ValueError):
        return default


def safe_json_deserialize(s: str, default: Dict = None) -> Union[Dict, List, Any]:
    """
    Safely deserialize JSON string with fallback to default value.
    
    Args:
        s: JSON string to deserialize
        default: Default value to return on deserialization failure
        
    Returns:
        Deserialized object or default value on failure
    """
    if default is None:
        default = {}
    
    try:
        return from_json(s)
    except (ValueError, TypeError):
        return default
