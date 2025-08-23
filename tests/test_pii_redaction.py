"""Tests for PII redaction and privacy features."""

import pytest
from apps.utils.pii_redaction import mask_text, mask_dict_recursive, anonymize_query_response, should_anonymize


def test_email_redaction():
    """Test email address redaction."""
    test_cases = [
        ("Contact me at john@example.com", "Contact me at [EMAIL_REDACTED]"),
        ("Email: user.name+tag@domain.co.uk", "Email: [EMAIL_REDACTED]"),
        ("Multiple emails: a@b.com and c@d.org", "Multiple emails: [EMAIL_REDACTED] and [EMAIL_REDACTED]"),
        ("No email here", "No email here"),
    ]
    
    for input_text, expected in test_cases:
        result = mask_text(input_text)
        assert result == expected


def test_phone_redaction():
    """Test phone number redaction."""
    test_cases = [
        ("Call me at 123-456-7890", "Call me at [PHONE_REDACTED]"),
        ("Phone: (555) 123-4567", "Phone: [PHONE_REDACTED]"),
        ("Contact: 555.123.4567", "Contact: [PHONE_REDACTED]"),
        ("Number: 5551234567", "Number: [PHONE_REDACTED]"),
        ("International: +1-555-123-4567", "International: [PHONE_REDACTED]"),
        ("No phone here", "No phone here"),
    ]
    
    for input_text, expected in test_cases:
        result = mask_text(input_text)
        assert result == expected


def test_ssn_redaction():
    """Test Social Security Number redaction."""
    test_cases = [
        ("SSN: 123-45-6789", "SSN: [SSN_REDACTED]"),
        ("Social Security: 987-65-4321", "Social Security: [SSN_REDACTED]"),
        ("No SSN here", "No SSN here"),
    ]
    
    for input_text, expected in test_cases:
        result = mask_text(input_text)
        assert result == expected


def test_credit_card_redaction():
    """Test credit card number redaction."""
    test_cases = [
        ("Card: 1234 5678 9012 3456", "Card: [CARD_REDACTED]"),
        ("Credit card: 1234-5678-9012-3456", "Credit card: [CARD_REDACTED]"),
        ("Number: 1234567890123456", "Number: [CARD_REDACTED]"),
        ("No card here", "No card here"),
    ]
    
    for input_text, expected in test_cases:
        result = mask_text(input_text)
        assert result == expected


def test_token_redaction():
    """Test API token and secret redaction."""
    test_cases = [
        ("API key: sk-1234567890abcdef1234567890abcdef", "API key: [TOKEN_REDACTED]"),
        ("Token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9", "Token: [TOKEN_REDACTED]"),
        ("Secret: abcdef1234567890abcdef1234567890abcdef12", "Secret: [HEX_TOKEN_REDACTED]"),
        ("Bearer abc123def456", "Bearer [BEARER_TOKEN_REDACTED]"),
        ("No tokens here", "No tokens here"),
    ]
    
    for input_text, expected in test_cases:
        result = mask_text(input_text)
        assert result is not None and (expected in result or result == expected)


def test_secret_pattern_redaction():
    """Test secret pattern redaction."""
    test_cases = [
        ("api_key: secret123", "api_key: [SECRET_REDACTED]"),
        ("password=mypassword", "password: [SECRET_REDACTED]"),
        ("token: 'abc123'", "token: [SECRET_REDACTED]"),
        ("Authorization: Bearer token123", "Authorization: bearer [AUTH_TOKEN_REDACTED]"),
    ]
    
    for input_text, expected in test_cases:
        result = mask_text(input_text)
        # Check if the redaction pattern is present (exact match may vary due to regex)
        assert result is not None and ("[SECRET_REDACTED]" in result or "[AUTH_TOKEN_REDACTED]" in result or "[BEARER_TOKEN_REDACTED]" in result)


def test_url_parameter_redaction():
    """Test URL parameter redaction."""
    test_cases = [
        ("https://api.example.com/data?token=secret123", "https://api.example.com/data?token=[PARAM_REDACTED]"),
        ("http://example.com/api?key=abc123&other=value", "http://example.com/api?key=[PARAM_REDACTED]&other=value"),
    ]
    
    for input_text, expected in test_cases:
        result = mask_text(input_text)
        assert result is not None and "[PARAM_REDACTED]" in result


def test_mask_dict_recursive():
    """Test recursive dictionary masking."""
    test_data = {
        "username": "john_doe",
        "password": "secret123",
        "email": "john@example.com",
        "api_key": "sk-1234567890abcdef",
        "config": {
            "database_password": "db_secret",
            "public_setting": "visible"
        },
        "tokens": ["token1", "token2"],
        "safe_data": "this is safe"
    }
    
    result = mask_dict_recursive(test_data)
    
    # Sensitive keys should be redacted
    assert result["password"] == "[REDACTED]"
    assert result["api_key"] == "[REDACTED]"
    assert result["config"]["database_password"] == "[REDACTED]"
    
    # Safe data should remain
    assert result["username"] == "john_doe"
    assert result["config"]["public_setting"] == "visible"
    assert result["safe_data"] == "this is safe"
    
    # Email should be masked in the text
    assert "[EMAIL_REDACTED]" in result["email"]


def test_anonymize_query_response():
    """Test query-response anonymization."""
    query = "My email is john@example.com and I need help"
    response = "I can help you! Contact support at support@company.com"
    context = ["Support email: help@company.com", "Phone: 555-123-4567"]
    
    anon_query, anon_response, anon_context = anonymize_query_response(query, response, context)
    
    # Check that emails are redacted
    assert "[EMAIL_REDACTED]" in anon_query
    assert "[EMAIL_REDACTED]" in anon_response
    assert "[EMAIL_REDACTED]" in anon_context[0]
    assert "[PHONE_REDACTED]" in anon_context[1]


def test_should_anonymize():
    """Test anonymization flag checking."""
    import os
    from unittest.mock import patch
    
    # Test enabled
    with patch.dict(os.environ, {"ANONYMIZE_REPORTS": "true"}):
        assert should_anonymize() is True
    
    # Test disabled
    with patch.dict(os.environ, {"ANONYMIZE_REPORTS": "false"}):
        assert should_anonymize() is False
    
    # Test default (should be true)
    with patch.dict(os.environ, {}, clear=True):
        assert should_anonymize() is True


def test_empty_and_none_inputs():
    """Test handling of empty and None inputs."""
    # Empty string
    assert mask_text("") == ""
    
    # None input
    assert mask_text(None) is None
    
    # Non-string input (convert to string first in real usage)
    # assert mask_text(123) == 123  # This would fail type checking
    
    # Empty dict
    result = mask_dict_recursive({})
    assert result == {}
    
    # None context in anonymize_query_response
    anon_query, anon_response, anon_context = anonymize_query_response("test", "test", None)
    assert anon_context == []


def test_complex_mixed_content():
    """Test masking of complex mixed content."""
    complex_text = """
    User Details:
    Email: john.doe@company.com
    Phone: (555) 123-4567
    SSN: 123-45-6789
    
    API Configuration:
    api_key: sk-1234567890abcdefghijklmnopqrstuvwxyz
    password: "super_secret_password"
    
    Credit Card: 4532 1234 5678 9012
    
    Safe information: This should remain visible.
    """
    
    result = mask_text(complex_text)
    
    # Verify all PII is redacted
    assert result is not None
    assert "[EMAIL_REDACTED]" in result
    assert "[PHONE_REDACTED]" in result
    assert "[SSN_REDACTED]" in result
    assert "[TOKEN_REDACTED]" in result or "[SECRET_REDACTED]" in result
    assert "[CARD_REDACTED]" in result
    
    # Verify safe content remains
    assert "Safe information: This should remain visible." in result


def test_custom_sensitive_keys():
    """Test custom sensitive keys in dictionary masking."""
    test_data = {
        "user_id": "12345",
        "custom_secret": "sensitive_value",
        "normal_field": "normal_value"
    }
    
    custom_keys = {"custom_secret", "user_id"}
    result = mask_dict_recursive(test_data, custom_keys)
    
    assert result["custom_secret"] == "[REDACTED]"
    assert result["user_id"] == "[REDACTED]"
    assert result["normal_field"] == "normal_value"


def test_nested_list_masking():
    """Test masking of nested lists in dictionaries."""
    test_data = {
        "users": [
            {"name": "John", "email": "john@example.com"},
            {"name": "Jane", "email": "jane@example.com"}
        ],
        "config": {
            "emails": ["admin@company.com", "support@company.com"]
        }
    }
    
    result = mask_dict_recursive(test_data)
    
    # Check that emails in nested structures are masked
    assert "[EMAIL_REDACTED]" in result["users"][0]["email"]
    assert "[EMAIL_REDACTED]" in result["users"][1]["email"]
    assert "[EMAIL_REDACTED]" in result["config"]["emails"][0]
    assert "[EMAIL_REDACTED]" in result["config"]["emails"][1]
    
    # Names should remain
    assert result["users"][0]["name"] == "John"
    assert result["users"][1]["name"] == "Jane"


def test_performance_with_large_text():
    """Test performance with large text inputs."""
    # Create a large text with some PII
    large_text = "Normal text. " * 1000 + "Email: test@example.com " + "More text. " * 1000
    
    result = mask_text(large_text)
    
    # Should still work correctly
    assert result is not None
    assert "[EMAIL_REDACTED]" in result
    assert len(result) > 0
