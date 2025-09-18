"""PII redaction utilities for privacy-by-default reporting."""

import re
from typing import Dict, List, Any, Optional


def mask_text(text: Optional[str]) -> Optional[str]:
    """
    Mask PII and sensitive information in text.
    
    Args:
        text: Input text that may contain PII
        
    Returns:
        Text with PII masked
    """
    if not text or not isinstance(text, str):
        return text
    
    masked = text
    
    # Email addresses
    masked = re.sub(
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        '[EMAIL_REDACTED]',
        masked
    )
    
    # Phone numbers (various formats)
    phone_patterns = [
        r'\b\d{3}-\d{3}-\d{4}\b',  # 123-456-7890
        r'\(\d{3}\)\s*\d{3}-\d{4}',  # (123) 456-7890
        r'\b\d{3}\.\d{3}\.\d{4}\b',  # 123.456.7890
        r'\b\d{10}\b',  # 1234567890
        r'\+1[-.\s]?\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b'  # +1-123-456-7890
    ]
    
    for pattern in phone_patterns:
        masked = re.sub(pattern, '[PHONE_REDACTED]', masked)
    
    # Social Security Numbers
    masked = re.sub(
        r'\b\d{3}-\d{2}-\d{4}\b',
        '[SSN_REDACTED]',
        masked
    )
    
    # Credit card numbers (basic pattern)
    masked = re.sub(
        r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',
        '[CARD_REDACTED]',
        masked
    )
    
    # Long base64/hex tokens (likely API keys or secrets)
    masked = re.sub(
        r'\b[A-Za-z0-9+/]{32,}={0,2}\b',  # Base64 tokens
        '[TOKEN_REDACTED]',
        masked
    )
    
    masked = re.sub(
        r'\b[a-fA-F0-9]{32,}\b',  # Hex tokens
        '[HEX_TOKEN_REDACTED]',
        masked
    )
    
    # OpenAI API keys (sk-...)
    masked = re.sub(
        r'\bsk-[a-zA-Z0-9]{16,}\b',
        '[TOKEN_REDACTED]',
        masked
    )
    
    # Common secret patterns
    secret_patterns = [
        (r'(?i)(api[_-]?key|secret|token|password|pwd)\s*[:=]\s*["\']?([^"\'\s]+)["\']?', r'\1: [SECRET_REDACTED]'),
        (r'(?i)bearer\s+([a-zA-Z0-9._-]+)', r'bearer [BEARER_TOKEN_REDACTED]'),
        (r'(?i)authorization:\s*bearer\s+([a-zA-Z0-9._-]+)', r'authorization: bearer [AUTH_TOKEN_REDACTED]')
    ]
    
    for pattern, replacement in secret_patterns:
        masked = re.sub(pattern, replacement, masked)
    
    # IP addresses (optional - might be needed for debugging)
    # masked = re.sub(
    #     r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
    #     '[IP_REDACTED]',
    #     masked
    # )
    
    # URLs with potential sensitive parameters
    masked = re.sub(
        r'(https?://[^\s]+[?&](?:token|key|secret|password)=)[^&\s]+',
        r'\1[PARAM_REDACTED]',
        masked
    )
    
    return masked


def mask_dict_recursive(data: dict, sensitive_keys: Optional[set] = None) -> dict:
    """
    Recursively mask sensitive keys in a dictionary.
    
    Args:
        data: Dictionary to mask
        sensitive_keys: Set of keys to mask (case-insensitive)
        
    Returns:
        Dictionary with sensitive values masked
    """
    if sensitive_keys is None:
        sensitive_keys = {
            'password', 'secret', 'token', 'key', 'auth', 'authorization',
            'api_key', 'access_token', 'refresh_token', 'bearer_token',
            'email', 'phone', 'ssn', 'credit_card', 'card_number'
        }
    
    if not isinstance(data, dict):
        return data
    
    masked_data = {}
    
    for key, value in data.items():
        key_lower = key.lower()
        
        if any(sensitive_key in key_lower for sensitive_key in sensitive_keys):
            # Mask the entire value for sensitive keys
            if isinstance(value, str):
                masked_data[key] = '[REDACTED]'
            else:
                masked_data[key] = '[REDACTED]'
        elif isinstance(value, dict):
            # Recursively mask nested dictionaries
            masked_data[key] = mask_dict_recursive(value, sensitive_keys)
        elif isinstance(value, list):
            # Mask items in lists
            masked_data[key] = [
                mask_dict_recursive(item, sensitive_keys) if isinstance(item, dict)
                else mask_text(item) if isinstance(item, str)
                else item
                for item in value
            ]
        elif isinstance(value, str):
            # Mask text values
            masked_data[key] = mask_text(value)
        else:
            # Keep other types as-is
            masked_data[key] = value
    
    return masked_data


def anonymize_query_response(query: str, response: str, context: Optional[list] = None) -> tuple:
    """
    Anonymize a query-response pair for reporting.
    
    Args:
        query: Original query
        response: Original response
        context: Optional context passages
        
    Returns:
        Tuple of (anonymized_query, anonymized_response, anonymized_context)
    """
    anonymized_query = mask_text(query)
    anonymized_response = mask_text(response)
    
    anonymized_context = []
    if context:
        for passage in context:
            if isinstance(passage, str):
                anonymized_context.append(mask_text(passage))
            else:
                anonymized_context.append(passage)
    
    return anonymized_query, anonymized_response, anonymized_context


def should_anonymize() -> bool:
    """Check if anonymization is enabled."""
    import os
    return os.getenv("ANONYMIZE_REPORTS", "true").lower() == "true"


def mask_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convenience function to mask a dictionary using default sensitive keys.
    
    Args:
        data: Dictionary to mask
        
    Returns:
        Dictionary with sensitive values masked
    """
    return mask_dict_recursive(data)
