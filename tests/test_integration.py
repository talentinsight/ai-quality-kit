"""Integration tests for the complete system."""

import pytest
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


@pytest.fixture
def test_client():
    """Create test client with mocked dependencies."""
    from apps.rag_service.main import app
    
    # Mock the RAG pipeline to avoid needing real data files
    with patch('apps.rag_service.main.rag_pipeline') as mock_pipeline:
        mock_pipeline.retrieve.return_value = ["Mock context passage"]
        mock_pipeline.answer.return_value = "Mock answer"
        mock_pipeline.passages = ["passage1", "passage2"]
        
        client = TestClient(app)
        yield client


def test_health_endpoints(test_client):
    """Test health check endpoints."""
    # Root endpoint
    response = test_client.get("/")
    assert response.status_code == 200
    assert "AI Quality Kit RAG Service is running" in response.json()["message"]
    
    # Health endpoint
    response = test_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "allowed_providers" in data
    
    # Kubernetes-style endpoints
    response = test_client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    
    response = test_client.get("/readyz")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_ask_endpoint_without_auth(test_client):
    """Test /ask endpoint when auth is disabled."""
    with patch.dict(os.environ, {"AUTH_ENABLED": "false"}):
        response = test_client.post("/ask", json={
            "query": "What is AI?",
            "provider": "mock",
            "model": "mock-model"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        assert "answer" in data
        assert "context" in data
        assert "provider" in data
        assert "model" in data
        
        # Check performance headers
        assert "X-Source" in response.headers
        assert "X-Perf-Phase" in response.headers
        assert "X-Latency-MS" in response.headers


def test_ask_endpoint_with_auth_no_token(test_client):
    """Test /ask endpoint when auth is enabled but no token provided."""
    with patch.dict(os.environ, {"AUTH_ENABLED": "true"}):
        response = test_client.post("/ask", json={
            "query": "What is AI?"
        })
        
        assert response.status_code == 401


def test_ask_endpoint_with_valid_token(test_client):
    """Test /ask endpoint with valid authentication token."""
    with patch.dict(os.environ, {
        "AUTH_ENABLED": "true",
        "AUTH_TOKENS": "user:SECRET_USER"
    }):
        headers = {"Authorization": "Bearer SECRET_USER"}
        response = test_client.post("/ask", json={
            "query": "What is AI?",
            "provider": "mock"
        }, headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data


def test_ask_endpoint_invalid_provider(test_client):
    """Test /ask endpoint with invalid provider."""
    with patch.dict(os.environ, {
        "AUTH_ENABLED": "false",
        "ALLOWED_PROVIDERS": "openai,mock"
    }):
        response = test_client.post("/ask", json={
            "query": "What is AI?",
            "provider": "invalid_provider"
        })
        
        assert response.status_code == 400
        assert "not in allowed providers" in response.json()["detail"]


@pytest.mark.asyncio
async def test_orchestrator_integration():
    """Test orchestrator integration."""
    from apps.orchestrator.run_tests import OrchestratorRequest, TestRunner
    
    with tempfile.TemporaryDirectory() as temp_dir:
        with patch.dict(os.environ, {
            "REPORTS_DIR": temp_dir,
            "RAGAS_SAMPLE_SIZE": "1"
        }):
            # Create minimal test data
            qaset_path = Path("data/golden/qaset.jsonl")
            qaset_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(qaset_path, 'w') as f:
                f.write('{"question": "What is AI?", "answer": "Artificial Intelligence"}\n')
            
            try:
                request = OrchestratorRequest(
                    target_mode="mcp",
                    suites=["rag_quality"],
                    options={"provider": "mock", "model": "mock-model"}
                )
                
                runner = TestRunner(request)
                result = await runner.run_all_tests()
                
                # Verify integration worked
                assert result.run_id
                assert result.counts["total_tests"] > 0
                assert Path(result.artifacts["json_path"]).exists()
                assert Path(result.artifacts["xlsx_path"]).exists()
                
            finally:
                if qaset_path.exists():
                    qaset_path.unlink()
                if qaset_path.parent.exists():
                    qaset_path.parent.rmdir()


def test_orchestrator_endpoint_integration(test_client):
    """Test orchestrator endpoint integration."""
    with tempfile.TemporaryDirectory() as temp_dir:
        with patch.dict(os.environ, {
            "AUTH_ENABLED": "false",
            "REPORTS_DIR": temp_dir,
            "RAGAS_SAMPLE_SIZE": "1"
        }):
            # Mock test data loading
            with patch('apps.orchestrator.run_tests.TestRunner._load_rag_quality_tests') as mock_load:
                mock_load.return_value = [{
                    "test_id": "test1",
                    "query": "What is AI?",
                    "expected_answer": "Artificial Intelligence"
                }]
                
                response = test_client.post("/orchestrator/run_tests", json={
                    "target_mode": "mcp",
                    "suites": ["rag_quality"],
                    "options": {"provider": "mock", "model": "mock-model"}
                })
                
                assert response.status_code == 200
                data = response.json()
                
                assert "run_id" in data
                assert "summary" in data
                assert "counts" in data
                assert "artifacts" in data


def test_a2a_integration(test_client):
    """Test A2A integration."""
    with patch.dict(os.environ, {"AUTH_ENABLED": "false", "A2A_ENABLED": "true"}):
        # Test manifest
        response = test_client.get("/a2a/manifest")
        assert response.status_code == 200
        
        manifest = response.json()
        assert manifest["agent"] == "quality-agent"
        assert len(manifest["skills"]) > 0
        
        # Test act endpoint
        response = test_client.post("/a2a/act", json={
            "skill": "ask_rag",
            "args": {"query": "What is AI?", "provider": "mock"}
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data


def test_provider_switching_integration():
    """Test provider switching in integrated environment."""
    with patch.dict(os.environ, {
        "AUTH_ENABLED": "false",
        "ALLOWED_PROVIDERS": "mock,openai"
    }):
        from apps.rag_service.config import resolve_provider_and_model
        
        # Test mock provider
        provider, model = resolve_provider_and_model("mock", "mock-model")
        assert provider == "mock"
        assert model == "mock-model"
        
        # Test OpenAI provider (would need API key in real scenario)
        provider, model = resolve_provider_and_model("openai", "gpt-4")
        assert provider == "openai"
        assert model == "gpt-4"


def test_privacy_integration():
    """Test privacy features integration."""
    from apps.utils.pii_redaction import mask_text, should_anonymize
    
    with patch.dict(os.environ, {"ANONYMIZE_REPORTS": "true"}):
        assert should_anonymize() is True
        
        # Test PII masking
        sensitive_text = "Contact john@example.com or call 555-123-4567"
        masked = mask_text(sensitive_text)
        
        assert masked is not None
        assert "[EMAIL_REDACTED]" in masked
        assert "[PHONE_REDACTED]" in masked


def test_performance_headers_integration(test_client):
    """Test performance headers in integrated environment."""
    with patch.dict(os.environ, {"AUTH_ENABLED": "false"}):
        # First request (should be cold)
        response1 = test_client.post("/ask", json={
            "query": "What is AI?",
            "provider": "mock"
        })
        
        assert response1.status_code == 200
        assert "X-Perf-Phase" in response1.headers
        assert "X-Latency-MS" in response1.headers
        assert "X-Source" in response1.headers
        
        # Verify header values
        assert response1.headers["X-Perf-Phase"] in ["cold", "warm"]
        assert response1.headers["X-Latency-MS"].isdigit()
        assert response1.headers["X-Source"] in ["live", "cache"]


def test_error_handling_integration(test_client):
    """Test error handling in integrated environment."""
    with patch.dict(os.environ, {"AUTH_ENABLED": "false"}):
        # Test with missing query
        response = test_client.post("/ask", json={})
        assert response.status_code == 422  # Validation error
        
        # Test with invalid JSON
        response = test_client.post("/ask", data="invalid json", 
                                  headers={"Content-Type": "application/json"})
        assert response.status_code == 422


def test_caching_integration(test_client):
    """Test caching behavior in integrated environment."""
    with patch.dict(os.environ, {"AUTH_ENABLED": "false", "CACHE_ENABLED": "true"}):
        with patch('apps.cache.cache_store.get_cached') as mock_get_cached:
            with patch('apps.cache.cache_store.set_cache') as mock_set_cache:
                # First request (cache miss)
                mock_get_cached.return_value = None
                
                response1 = test_client.post("/ask", json={
                    "query": "What is AI?",
                    "provider": "mock"
                })
                
                assert response1.status_code == 200
                assert response1.headers.get("X-Source") == "live"
                
                # Verify cache was attempted to be set
                mock_set_cache.assert_called()


def test_audit_logging_integration():
    """Test audit logging integration."""
    from apps.observability.log_service import audit_start, audit_finish
    
    with patch.dict(os.environ, {
        "AUDIT_LOG_ENABLED": "true",
        "PERSIST_DB": "true"
    }):
        with patch('apps.observability.log_service.snowflake_cursor') as mock_cursor:
            mock_cursor.return_value.__enter__.return_value = MagicMock()
            
            # Test audit logging
            audit_id = audit_start("/test", "POST", "user", "12345678")
            assert audit_id is not None
            
            audit_finish(audit_id, 200, 100, False)
            
            # Verify database calls were made
            assert mock_cursor.called


def test_full_workflow_integration():
    """Test complete workflow from request to report generation."""
    with tempfile.TemporaryDirectory() as temp_dir:
        with patch.dict(os.environ, {
            "AUTH_ENABLED": "false",
            "REPORTS_DIR": temp_dir,
            "ANONYMIZE_REPORTS": "false",
            "RAGAS_SAMPLE_SIZE": "1"
        }):
            # Create test client
            from apps.rag_service.main import app
            client = TestClient(app)
            
            # Mock dependencies
            with patch('apps.rag_service.main.rag_pipeline') as mock_pipeline:
                mock_pipeline.retrieve.return_value = ["Context"]
                mock_pipeline.answer.return_value = "Answer"
                mock_pipeline.passages = ["passage1"]
                
                # 1. Test basic RAG query
                response = client.post("/ask", json={
                    "query": "What is AI?",
                    "provider": "mock"
                })
                assert response.status_code == 200
                
                # 2. Test orchestrator run
                with patch('apps.orchestrator.run_tests.TestRunner._load_rag_quality_tests') as mock_load:
                    mock_load.return_value = [{
                        "test_id": "test1",
                        "query": "What is AI?",
                        "expected_answer": "AI"
                    }]
                    
                    response = client.post("/orchestrator/run_tests", json={
                        "target_mode": "mcp",
                        "suites": ["rag_quality"],
                        "options": {"provider": "mock"}
                    })
                    assert response.status_code == 200
                    
                    run_data = response.json()
                    run_id = run_data["run_id"]
                    
                    # 3. Test report download
                    response = client.get(f"/orchestrator/report/{run_id}.json")
                    assert response.status_code == 200
                    
                    response = client.get(f"/orchestrator/report/{run_id}.xlsx")
                    assert response.status_code == 200
