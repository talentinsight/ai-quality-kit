"""Tests for RAG prompt robustness runner."""

import unittest
from unittest.mock import MagicMock, patch
from apps.evaluation.structured_runner import (
    render_template,
    extract_result,
    compute_stability,
    _extract_long_multiplication_result,
    _extract_extraction_result
)
from apps.evaluation.contracts import validate_contract, mask_pii


class TestStructuredRunner(unittest.TestCase):
    """Test structured evaluation runner functions."""
    
    def test_render_template_basic(self):
        """Test basic template rendering."""
        template = "Calculate {{input.a}} × {{input.b}}"
        context = {"input": {"a": 123, "b": 456}}
        result = render_template(template, context)
        self.assertEqual(result, "Calculate 123 × 456")
    
    def test_render_template_complex(self):
        """Test complex template rendering."""
        template = "Extract from: {{input.text}}\nExpected: {{gold}}"
        context = {
            "input": {"text": "Sample receipt"},
            "gold": {"merchant": "Test Store"}
        }
        result = render_template(template, context)
        self.assertIn("Sample receipt", result)
        self.assertIn("Test Store", result)
    
    def test_extract_long_multiplication_json(self):
        """Test extracting multiplication result from JSON."""
        text = '{"result": 12345}'
        result = _extract_long_multiplication_result(text)
        self.assertEqual(result, 12345)
    
    def test_extract_long_multiplication_text(self):
        """Test extracting multiplication result from text."""
        text = "The calculation shows 123 × 456 = 56088"
        result = _extract_long_multiplication_result(text)
        self.assertEqual(result, 56088)
    
    def test_extract_extraction_result_json(self):
        """Test extracting structured data from JSON."""
        text = '{"merchant": "Test Store", "total": 45.67, "date": "2024-03-15"}'
        result = _extract_extraction_result(text)
        self.assertEqual(result["merchant"], "Test Store")
        self.assertEqual(result["total"], 45.67)
        self.assertEqual(result["date"], "2024-03-15")
    
    def test_extract_extraction_result_text(self):
        """Test extracting structured data from unstructured text."""
        text = "Merchant: Test Store\nTotal: $45.67\nDate: 03/15/2024"
        result = _extract_extraction_result(text)
        self.assertEqual(result["merchant"], "Test Store")
        self.assertEqual(result["total"], 45.67)
        self.assertEqual(result["date"], "03/15/2024")
    
    def test_compute_stability_perfect(self):
        """Test stability computation with perfect results."""
        outcomes = [1, 1, 1, 1]
        stability = compute_stability(outcomes)
        self.assertEqual(stability, 1.0)
    
    def test_compute_stability_mixed(self):
        """Test stability computation with mixed results."""
        outcomes = [1, 0, 1, 0]
        stability = compute_stability(outcomes)
        self.assertLess(stability, 1.0)
        self.assertGreater(stability, 0.0)
    
    def test_compute_stability_single(self):
        """Test stability computation with single outcome."""
        outcomes = [1]
        stability = compute_stability(outcomes)
        self.assertEqual(stability, 1.0)
    
    def test_extract_result_task_types(self):
        """Test extract_result for different task types."""
        # Long multiplication
        result = extract_result("The answer is 12345", "long_multiplication")
        self.assertEqual(result, 12345)
        
        # Extraction
        result = extract_result('{"merchant": "Test", "total": 10.0}', "extraction")
        self.assertIsInstance(result, dict)
        self.assertEqual(result["merchant"], "Test")
        
        # Unknown task type
        result = extract_result("Some text", "unknown")
        self.assertEqual(result, "Some text")


class TestContracts(unittest.TestCase):
    """Test contract validation and PII masking."""
    
    def test_validate_jsonschema_valid(self):
        """Test JSON schema validation with valid data."""
        schema = {
            "type": "object",
            "properties": {
                "result": {"type": "integer"}
            },
            "required": ["result"]
        }
        contract_cfg = {"type": "jsonschema", "schema": schema}
        
        # Mock jsonschema import
        with patch('apps.evaluation.contracts.jsonschema') as mock_jsonschema:
            mock_jsonschema.validate.return_value = None  # No exception = valid
            result = validate_contract(contract_cfg, '{"result": 123}')
            self.assertTrue(result)
    
    def test_validate_jsonschema_invalid(self):
        """Test JSON schema validation with invalid data."""
        schema = {
            "type": "object",
            "properties": {
                "result": {"type": "integer"}
            },
            "required": ["result"]
        }
        contract_cfg = {"type": "jsonschema", "schema": schema}
        
        # Mock jsonschema import and ValidationError
        with patch('apps.evaluation.contracts.jsonschema') as mock_jsonschema:
            from jsonschema import ValidationError
            mock_jsonschema.ValidationError = ValidationError
            mock_jsonschema.validate.side_effect = ValidationError("Invalid")
            result = validate_contract(contract_cfg, '{"wrong": "field"}')
            self.assertFalse(result)
    
    def test_validate_ebnf_stub(self):
        """Test EBNF validation returns None (stub)."""
        contract_cfg = {"type": "ebnf", "grammar": "number := [0-9]+"}
        result = validate_contract(contract_cfg, "123")
        self.assertIsNone(result)
    
    def test_mask_pii_email(self):
        """Test PII masking for email addresses."""
        text = "Contact us at user@example.com for support"
        masked = mask_pii(text)
        self.assertIn("[EMAIL]", masked)
        self.assertNotIn("user@example.com", masked)
    
    def test_mask_pii_phone(self):
        """Test PII masking for phone numbers."""
        text = "Call us at (555) 123-4567"
        masked = mask_pii(text)
        self.assertIn("[PHONE]", masked)
        self.assertNotIn("555", masked)
    
    def test_mask_pii_credit_card(self):
        """Test PII masking for credit card numbers."""
        text = "Card number: 4532 1234 5678 9012"
        masked = mask_pii(text)
        self.assertIn("[CREDIT_CARD]", masked)
        self.assertNotIn("4532", masked)
    
    def test_mask_pii_multiple(self):
        """Test PII masking for multiple types."""
        text = "Email: user@test.com, Phone: 555-123-4567, Card: 4532123456789012"
        masked = mask_pii(text)
        self.assertIn("[EMAIL]", masked)
        self.assertIn("[PHONE]", masked)
        self.assertIn("[CREDIT_CARD]", masked)
        self.assertNotIn("user@test.com", masked)
        self.assertNotIn("555-123-4567", masked)


if __name__ == '__main__':
    unittest.main()
