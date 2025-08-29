"""Tests for synthetic provider."""

import pytest
from apps.orchestrator.synthetic_provider import SyntheticProvider, create_synthetic_provider


class TestSyntheticProvider:
    """Test synthetic provider functionality."""
    
    def test_create_synthetic_provider(self):
        """Test synthetic provider creation."""
        provider = create_synthetic_provider(success_rate=0.8)
        
        assert provider.provider == "synthetic"
        assert provider.model == "synthetic-v1"
        assert provider.success_rate == 0.8
    
    def test_receipt_extraction_success(self):
        """Test successful receipt extraction."""
        provider = create_synthetic_provider(success_rate=1.0)  # Always succeed
        
        prompt = """
        COSTCO WHOLESALE
        Member #12345678
        
        Merchandise: $89.47
        Tax: $7.16
        Amount Due: $96.63
        
        Date: 03/18/2024
        """
        
        response = provider.complete(prompt)
        
        assert "text" in response
        import json
        result = json.loads(response["text"])
        
        assert result["merchant"] == "COSTCO WHOLESALE"
        assert result["total"] == 96.63
        assert result["date"] == "03/18/2024"
    
    def test_math_operation_success(self):
        """Test successful math operation."""
        provider = create_synthetic_provider(success_rate=1.0)  # Always succeed
        
        prompt = "Calculate 1234567 × 9876543"
        
        response = provider.complete(prompt)
        
        assert "text" in response
        import json
        result = json.loads(response["text"])
        
        expected = 1234567 * 9876543
        assert result["result"] == expected
    
    def test_math_operation_failure(self):
        """Test math operation with controlled failure."""
        provider = create_synthetic_provider(success_rate=0.0)  # Always fail
        
        prompt = "Calculate 1234567 × 9876543"
        
        response = provider.complete(prompt)
        
        assert "text" in response
        import json
        result = json.loads(response["text"])
        
        expected = 1234567 * 9876543
        # Should be different due to synthetic error
        assert result["result"] != expected
    
    def test_sql_generation(self):
        """Test SQL generation."""
        provider = create_synthetic_provider(success_rate=1.0)
        
        prompt = "Generate a SQL query to select all users"
        
        response = provider.complete(prompt)
        
        assert "text" in response
        assert "SELECT" in response["text"].upper()
        assert "users" in response["text"].lower()
    
    def test_qa_task(self):
        """Test QA task handling."""
        provider = create_synthetic_provider(success_rate=1.0)
        
        prompt = "What is Python programming language?"
        
        response = provider.complete(prompt)
        
        assert "text" in response
        assert "python" in response["text"].lower()
        assert len(response["text"]) > 10  # Should be a meaningful answer
    
    def test_deterministic_behavior(self):
        """Test that provider gives consistent results."""
        provider1 = create_synthetic_provider(success_rate=0.5)
        provider2 = create_synthetic_provider(success_rate=0.5)
        
        prompt = "Calculate 123 × 456"
        
        # Should give same results due to fixed seed
        response1 = provider1.complete(prompt)
        response2 = provider2.complete(prompt)
        
        assert response1["text"] == response2["text"]


if __name__ == "__main__":
    pytest.main([__file__])
