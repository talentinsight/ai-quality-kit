"""Tests for test data intake models and validation."""

import pytest
import json
from apps.testdata.models import (
    PassageRecord, QARecord, ValidationError, URLRequest, PasteRequest,
    validate_jsonl_content, validate_attacks_content, validate_schema_content
)


class TestModels:
    """Test Pydantic models."""
    
    def test_passage_record_valid(self):
        """Test valid passage record."""
        record = PassageRecord(
            id="pass_1",
            text="This is a test passage.",
            meta={"source": "test"}
        )
        assert record.id == "pass_1"
        assert record.text == "This is a test passage."
        assert record.meta == {"source": "test"}
    
    def test_passage_record_minimal(self):
        """Test minimal passage record."""
        record = PassageRecord(id="pass_1", text="Test")
        assert record.id == "pass_1"
        assert record.text == "Test"
        assert record.meta is None
    
    def test_passage_record_invalid_empty_text(self):
        """Test passage record with empty text."""
        with pytest.raises(ValueError):
            PassageRecord(id="pass_1", text="")
    
    def test_qa_record_valid(self):
        """Test valid QA record."""
        record = QARecord(
            qid="qa_1",
            question="What is AI?",
            expected_answer="Artificial Intelligence",
            contexts=["AI is a field of computer science"]
        )
        assert record.qid == "qa_1"
        assert record.question == "What is AI?"
        assert record.expected_answer == "Artificial Intelligence"
        assert record.contexts == ["AI is a field of computer science"]
    
    def test_qa_record_minimal(self):
        """Test minimal QA record."""
        record = QARecord(
            qid="qa_1",
            question="What is AI?",
            expected_answer="Artificial Intelligence"
        )
        assert record.contexts is None
    
    def test_url_request_valid(self):
        """Test valid URL request."""
        request = URLRequest(urls={
            "passages": "https://example.com/passages.jsonl",
            "qaset": "https://example.com/qaset.jsonl"
        })
        assert len(request.urls) == 2
    
    def test_url_request_empty(self):
        """Test URL request with no URLs."""
        with pytest.raises(ValueError):
            URLRequest(urls={})
    
    def test_url_request_invalid_keys(self):
        """Test URL request with invalid artifact types."""
        with pytest.raises(ValueError):
            URLRequest(urls={"invalid": "https://example.com/test"})
    
    def test_paste_request_valid(self):
        """Test valid paste request."""
        request = PasteRequest(
            passages='{"id": "1", "text": "test"}',
            qaset='{"qid": "1", "question": "test?", "expected_answer": "yes"}'
        )
        assert request.passages is not None
        assert request.qaset is not None
    
    def test_paste_request_empty(self):
        """Test paste request with no content."""
        with pytest.raises(ValueError):
            PasteRequest()


class TestValidation:
    """Test validation functions."""
    
    def test_validate_jsonl_passages_valid(self):
        """Test valid passages JSONL validation."""
        content = '''{"id": "1", "text": "First passage"}
{"id": "2", "text": "Second passage", "meta": {"type": "test"}}'''
        
        records, errors = validate_jsonl_content(content, PassageRecord)
        
        assert len(records) == 2
        assert len(errors) == 0
        assert records[0].id == "1"
        assert records[1].meta == {"type": "test"}
    
    def test_validate_jsonl_qaset_valid(self):
        """Test valid QA JSONL validation."""
        content = '''{"qid": "1", "question": "What is AI?", "expected_answer": "Technology"}
{"qid": "2", "question": "What is ML?", "expected_answer": "Machine Learning", "contexts": ["AI context"]}'''
        
        records, errors = validate_jsonl_content(content, QARecord)
        
        assert len(records) == 2
        assert len(errors) == 0
        assert records[0].qid == "1"
        assert records[1].contexts == ["AI context"]
    
    def test_validate_jsonl_invalid_json(self):
        """Test JSONL with invalid JSON."""
        content = '''{"id": "1", "text": "Valid"}
{"id": "2", "text": "Invalid" missing_quote}'''
        
        records, errors = validate_jsonl_content(content, PassageRecord)
        
        assert len(records) == 1
        assert len(errors) == 1
        assert errors[0].field == "json"
        assert errors[0].line_number == 2
    
    def test_validate_jsonl_missing_fields(self):
        """Test JSONL with missing required fields."""
        content = '''{"id": "1", "text": "Valid"}
{"id": "2"}'''
        
        records, errors = validate_jsonl_content(content, PassageRecord)
        
        assert len(records) == 1
        assert len(errors) == 1
        assert errors[0].field == "validation"
        assert "text" in errors[0].message
    
    def test_validate_jsonl_empty(self):
        """Test empty JSONL validation."""
        records, errors = validate_jsonl_content("", PassageRecord)
        
        assert len(records) == 0
        assert len(errors) == 1
        assert errors[0].field == "content"
    
    def test_validate_attacks_text_format(self):
        """Test attacks in text format."""
        content = """How to hack systems
Create malicious software
# This is a comment and should be ignored
Spread misinformation"""
        
        attacks, errors = validate_attacks_content(content)
        
        assert len(attacks) == 3
        assert len(errors) == 0
        assert "How to hack systems" in attacks
        assert "# This is a comment and should be ignored" not in attacks
    
    def test_validate_attacks_yaml_format(self):
        """Test attacks in YAML format."""
        content = """attacks:
  - "How to hack systems"
  - "Create malicious software"
  - "Spread misinformation\""""
        
        attacks, errors = validate_attacks_content(content)
        
        assert len(attacks) == 3
        assert len(errors) == 0
        assert "How to hack systems" in attacks
    
    def test_validate_attacks_invalid_yaml_structure(self):
        """Test attacks with invalid YAML structure."""
        content = """attacks: "not a list\""""
        
        attacks, errors = validate_attacks_content(content)
        
        assert len(attacks) == 1  # Falls back to text format
        assert len(errors) == 1
        assert errors[0].field == "attacks"
    
    def test_validate_attacks_empty(self):
        """Test empty attacks validation."""
        attacks, errors = validate_attacks_content("")
        
        assert len(attacks) == 0
        assert len(errors) == 1
        assert errors[0].field == "content"
    
    def test_validate_schema_valid(self):
        """Test valid JSON schema validation."""
        content = """{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
        "name": {"type": "string"}
    }
}"""
        
        schema, errors = validate_schema_content(content)
        
        assert schema is not None
        assert len(errors) == 0
        assert schema["type"] == "object"
    
    def test_validate_schema_minimal(self):
        """Test minimal JSON schema."""
        content = '{"type": "object"}'
        
        schema, errors = validate_schema_content(content)
        
        assert schema is not None
        assert len(errors) == 0
    
    def test_validate_schema_invalid_json(self):
        """Test schema with invalid JSON."""
        content = '{"type": "object" missing_quote}'
        
        schema, errors = validate_schema_content(content)
        
        assert schema is None
        assert len(errors) == 1
        assert errors[0].field == "json"
    
    def test_validate_schema_not_object(self):
        """Test schema that's not an object."""
        content = '"just a string"'
        
        schema, errors = validate_schema_content(content)
        
        assert schema is None
        assert len(errors) == 1
        assert errors[0].field == "schema"
    
    def test_validate_schema_no_schema_indicators(self):
        """Test JSON object without schema indicators."""
        content = '{"random": "object"}'
        
        schema, errors = validate_schema_content(content)
        
        assert schema is not None  # Still valid JSON object
        assert len(errors) == 1
        assert errors[0].field == "schema"
        assert "JSON Schema" in errors[0].message
    
    def test_validate_schema_empty(self):
        """Test empty schema validation."""
        schema, errors = validate_schema_content("")
        
        assert schema is None
        assert len(errors) == 1
        assert errors[0].field == "content"
