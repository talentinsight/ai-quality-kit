"""Unit tests for utility functions."""

import pytest
import json
from unittest.mock import patch


class TestHashUtils:
    """Test hash utility functions."""
    
    def test_normalize_query_whitespace_collapse(self):
        """Test that normalize_query collapses whitespace."""
        from apps.utils.hash_utils import normalize_query
        
        # Multiple spaces
        assert normalize_query("hello    world") == "hello world"
        
        # Tabs and newlines
        assert normalize_query("hello\tworld\n") == "hello world"
        
        # Mixed whitespace
        assert normalize_query("  hello  \t  world  \n  ") == "hello world"
    
    def test_normalize_query_lowercase(self):
        """Test that normalize_query converts to lowercase."""
        from apps.utils.hash_utils import normalize_query
        
        assert normalize_query("Hello World") == "hello world"
        assert normalize_query("HELLO WORLD") == "hello world"
        assert normalize_query("HeLLo WoRLd") == "hello world"
    
    def test_normalize_query_edge_cases(self):
        """Test normalize_query with edge cases."""
        from apps.utils.hash_utils import normalize_query
        
        # Empty string
        assert normalize_query("") == ""
        
        # Only whitespace
        assert normalize_query("   \t\n  ") == ""
        
        # Single character
        assert normalize_query("a") == "a"
        assert normalize_query("A") == "a"
    
    def test_query_hash_deterministic(self):
        """Test that query_hash is deterministic for same input."""
        from apps.utils.hash_utils import query_hash
        
        query1 = "What is AI Quality Kit?"
        query2 = "What is AI Quality Kit?"
        
        hash1 = query_hash(query1)
        hash2 = query_hash(query2)
        
        assert hash1 == hash2
        assert isinstance(hash1, str)
        assert len(hash1) > 0
    
    def test_query_hash_different_inputs(self):
        """Test that query_hash produces different hashes for different inputs."""
        from apps.utils.hash_utils import query_hash
        
        query1 = "What is AI Quality Kit?"
        query2 = "What is machine learning?"
        
        hash1 = query_hash(query1)
        hash2 = query_hash(query2)
        
        assert hash1 != hash2
    
    def test_query_hash_normalized(self):
        """Test that query_hash uses normalized input."""
        from apps.utils.hash_utils import query_hash
        
        query1 = "What is AI Quality Kit?"
        query2 = "  What   is   AI   Quality   Kit?  "
        
        hash1 = query_hash(query1)
        hash2 = query_hash(query2)
        
        assert hash1 == hash2


class TestJsonUtils:
    """Test JSON utility functions."""
    
    def test_to_json_serialization(self):
        """Test to_json serialization."""
        from apps.utils.json_utils import to_json
        
        data = {"key": "value", "number": 42, "list": [1, 2, 3]}
        json_str = to_json(data)
        
        assert isinstance(json_str, str)
        assert json.loads(json_str) == data
    
    def test_from_json_deserialization(self):
        """Test from_json deserialization."""
        from apps.utils.json_utils import from_json
        
        json_str = '{"key": "value", "number": 42}'
        data = from_json(json_str)
        
        assert data == {"key": "value", "number": 42}
    
    def test_json_roundtrip(self):
        """Test JSON roundtrip serialization/deserialization."""
        from apps.utils.json_utils import to_json, from_json
        
        original_data = {
            "string": "hello",
            "number": 123,
            "float": 3.14,
            "boolean": True,
            "null": None,
            "list": [1, 2, 3],
            "dict": {"nested": "value"}
        }
        
        json_str = to_json(original_data)
        deserialized_data = from_json(json_str)
        
        assert deserialized_data == original_data
    
    def test_safe_json_serialize(self):
        """Test safe_json_serialize with various data types."""
        from apps.utils.json_utils import safe_json_serialize
        
        # Test with regular data
        data = {"key": "value"}
        result = safe_json_serialize(data)
        # JSON serialization might not preserve exact spacing
        assert result.replace(" ", "") == '{"key":"value"}'
        
        # Test with non-serializable data (should handle gracefully)
        data_with_function = {"key": lambda x: x}
        result = safe_json_serialize(data_with_function)
        # Should return default value on failure
        assert result == "{}"
    
    def test_safe_json_deserialize(self):
        """Test safe_json_deserialize with various inputs."""
        from apps.utils.json_utils import safe_json_deserialize
        
        # Test with valid JSON
        valid_json = '{"key": "value"}'
        result = safe_json_deserialize(valid_json)
        assert result == {"key": "value"}
        
        # Test with invalid JSON
        invalid_json = '{"key": "value"'
        result = safe_json_deserialize(invalid_json)
        # Should handle invalid JSON gracefully
        assert result is None or isinstance(result, dict) or "error" in str(result).lower()


# PII utility tests removed - module not implemented
# class TestPiiUtils:
#     """Test PII utility functions."""
#     
#     def test_pii_redaction_emails(self):
#         """Test PII redaction for email addresses."""
#         try:
#             from apps.utils.pii_redaction import redact
#         except ImportError:
#             pytest.skip("PII redaction module not available")
#         
#         text = "Contact us at user@example.com or admin@test.org"
#         redacted = redact(text)
#         
#         assert "user@example.com" not in redacted
#         assert "admin@test.org" not in redacted
#         assert "***" in redacted or "REDACTED" in redacted
#     
#     def test_pii_redaction_phones(self):
#         """Test PII redaction for phone numbers."""
#         try:
#             from apps.utils.pii_redaction import redact
#         except ImportError:
#             pytest.skip("PII redaction module not available")
#         
#         text = "Call us at +1-555-123-4567 or 555-987-6543"
#         redacted = redact(text)
#         
#         assert "+1-555-123-4567" not in redacted
#         assert "555-987-6543" not in redacted
#         assert "***" in redacted or "REDACTED" in redacted
#     
#     def test_pii_redaction_ids(self):
#         """Test PII redaction for ID numbers."""
#         try:
#             from apps.utils.pii_redaction import redact
#         except ImportError:
#             pytest.skip("PII redaction module not available")
#         
#         text = "User ID: 12345-67890, SSN: 123-45-6789"
#         redacted = redact(text)
#         
#         assert "12345-67890" not in redacted
#         assert "123-45-6789" not in redacted
#         assert "***" in redacted or "REDACTED" in redacted
#     
#     def test_redact_list(self):
#         """Test redact_list function."""
#         try:
#             from apps.utils.pii_redaction import redact_list
#         except ImportError:
#             pytest.skip("PII redaction module not available")
#         
#         texts = [
#             "Email: user@example.com",
#             "Phone: 555-123-4567",
#             "No PII here"
#         ]
#         
#         redacted_list = redact_list(texts)
#         
#         assert len(redacted_list) == len(texts)
#         assert "user@example.com" not in redacted_list[0]
#         assert "555-123-4567" not in redacted_list[1]
#         assert redacted_list[2] == "No PII here"
