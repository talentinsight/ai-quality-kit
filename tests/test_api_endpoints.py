"""Unit tests for FastAPI endpoints."""

import pytest
import os
from unittest.mock import patch, Mock
from fastapi.testclient import TestClient


class TestAPIEndpoints:
    """Test FastAPI endpoint functionality."""
    
    def test_health_endpoint(self, client):
        """Test /health endpoint returns status ok."""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"
    
    def test_root_endpoint(self, client):
        """Test / endpoint returns welcome message."""
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "AI Quality Kit" in data["message"]
    
    def test_ask_endpoint_no_llm_keys(self, client, set_env_defaults):
        """Test /ask endpoint when LLM keys are missing."""
        with patch.dict(os.environ, set_env_defaults):
            # Remove API keys
            with patch.dict(os.environ, {"OPENAI_API_KEY": "", "ANTHROPIC_API_KEY": ""}):
                response = client.post(
                    "/ask",
                    json={"query": "What is AI Quality Kit?"}
                )
                
                # Should either skip gracefully or return error
                assert response.status_code in [200, 400, 422, 500]
                
                if response.status_code == 200:
                    data = response.json()
                    # Should return some response even without keys
                    assert "answer" in data
                else:
                    # Should return graceful error without stack traces
                    data = response.json()
                    assert "error" in data or "detail" in data
    
    def test_ask_endpoint_with_keys(self, client, set_env_defaults, mock_openai_client):
        """Test /ask endpoint when LLM keys are available."""
        with patch.dict(os.environ, set_env_defaults):
            # Mock OpenAI response
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = "AI Quality Kit is a comprehensive platform."
            mock_openai_client.chat.completions.create.return_value = mock_response
    
            response = client.post(
                "/ask",
                json={"query": "What is AI Quality Kit?"}
            )
    
            # Should return 200 with proper structure
            assert response.status_code == 200
            data = response.json()
            
            assert "answer" in data
            assert "context" in data
            assert isinstance(data["answer"], str)
            assert isinstance(data["context"], list)
            assert len(data["answer"]) > 0
    
    def test_ask_endpoint_invalid_query(self, client):
        """Test /ask endpoint with invalid query."""
        # Test empty query
        response = client.post(
            "/ask",
            json={"query": ""}
        )
        
        # Should handle gracefully
        assert response.status_code in [200, 400, 422]
        
        if response.status_code == 200:
            data = response.json()
            # Should return some response for empty query
            assert "answer" in data
        else:
            # Should return validation error
            data = response.json()
            assert "detail" in data
    
    def test_ask_endpoint_missing_query(self, client):
        """Test /ask endpoint with missing query field."""
        response = client.post(
            "/ask",
            json={}
        )
        
        # Should return validation error
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
    
    def test_ask_endpoint_large_query(self, client):
        """Test /ask endpoint with very large query."""
        large_query = "What is AI Quality Kit? " * 1000  # Very long query
        
        response = client.post(
            "/ask",
            json={"query": large_query}
        )
        
        # Should handle large queries gracefully
        assert response.status_code in [200, 400, 413]  # 413 = Payload Too Large
        
        if response.status_code == 200:
            data = response.json()
            assert "answer" in data
        elif response.status_code == 413:
            # Payload too large
            pass
        else:
            # Other validation error
            data = response.json()
            assert "detail" in data
    
    def test_ask_endpoint_special_characters(self, client):
        """Test /ask endpoint with special characters in query."""
        special_query = "What is AI Quality Kit? 🚀 #AI #Quality #Testing"
        
        response = client.post(
            "/ask",
            json={"query": special_query}
        )
        
        # Should handle special characters gracefully
        assert response.status_code in [200, 400, 422]
        
        if response.status_code == 200:
            data = response.json()
            assert "answer" in data
        else:
            data = response.json()
            assert "detail" in data
    
    def test_ask_endpoint_response_structure(self, client, set_env_defaults, mock_openai_client):
        """Test that /ask response has correct structure."""
        with patch.dict(os.environ, set_env_defaults):
            # Mock OpenAI response
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = "AI Quality Kit is a comprehensive platform."
            mock_openai_client.chat.completions.create.return_value = mock_response
            
            response = client.post(
                "/ask",
                json={"query": "What is AI Quality Kit?"}
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Check required fields
                required_fields = ["answer", "context"]
                for field in required_fields:
                    assert field in data, f"Missing required field: {field}"
                
                # Check field types
                assert isinstance(data["answer"], str), "Answer should be string"
                assert isinstance(data["context"], list), "Context should be list"
                
                # Check field values
                assert len(data["answer"]) > 0, "Answer should not be empty"
                assert len(data["context"]) >= 0, "Context should be list (can be empty)"
    
    def test_ask_endpoint_error_handling(self, client, set_env_defaults):
        """Test /ask endpoint error handling."""
        with patch.dict(os.environ, set_env_defaults):
            # Test with malformed JSON
            response = client.post(
                "/ask",
                data="invalid json",
                headers={"Content-Type": "application/json"}
            )
            
            # Should return 422 for malformed JSON
            assert response.status_code == 422
    
    def test_ask_endpoint_method_not_allowed(self, client):
        """Test /ask endpoint with wrong HTTP method."""
        # Test GET instead of POST
        response = client.get("/ask")
        
        # Should return 405 Method Not Allowed
        assert response.status_code == 405
    
    def test_health_endpoint_methods(self, client):
        """Test /health endpoint with different HTTP methods."""
        # GET should work
        response = client.get("/health")
        assert response.status_code == 200
        
        # POST should not work
        response = client.post("/health")
        assert response.status_code == 405
    

