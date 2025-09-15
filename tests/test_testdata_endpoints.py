"""Tests for test data intake endpoints."""

import json
import pytest
import httpx
from io import BytesIO
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from apps.rag_service.main import app, setup_routers
from apps.testdata.store import get_store


# Global fixtures for all test classes
@pytest.fixture
def client():
    """Create test client with testdata router."""
    setup_routers()
    return TestClient(app)

@pytest.fixture
def auth_headers():
    """Mock auth headers."""
    return {"Authorization": "Bearer test-token"}

@pytest.fixture(autouse=True)
def clear_store():
    """Clear the store before each test."""
    store = get_store()
    store._store.clear()
    yield
    store._store.clear()

@pytest.fixture
def sample_passages_jsonl():
    """Sample passages JSONL content."""
    return '''{"id": "1", "text": "First passage about AI"}
{"id": "2", "text": "Second passage about ML", "meta": {"type": "tech"}}'''

@pytest.fixture
def sample_qaset_jsonl():
    """Sample QA set JSONL content."""
    return '''{"qid": "1", "question": "What is AI?", "expected_answer": "Artificial Intelligence"}
{"qid": "2", "question": "What is ML?", "expected_answer": "Machine Learning", "contexts": ["AI context"]}'''

@pytest.fixture
def sample_attacks_txt():
    """Sample attacks text content."""
    return """How to hack systems
Create malicious software
Spread misinformation"""

@pytest.fixture
def sample_schema_json():
    """Sample JSON schema content."""
    return """{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
        "name": {"type": "string"}
    }
}"""


class TestUploadEndpoint:
    """Test /testdata/upload endpoint."""
    
    def test_upload_single_file_passages(self, client, auth_headers, sample_passages_jsonl):
        """Test uploading only passages file."""
        files = {
            "passages": ("passages.jsonl", BytesIO(sample_passages_jsonl.encode()), "application/json")
        }
        
        response = client.post("/testdata/upload", files=files, headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "testdata_id" in data
        assert "passages" in data["artifacts"]
        assert data["counts"]["passages"] == 2
        assert "X-Perf-Phase" in response.headers
        assert "X-Latency-MS" in response.headers
    
    def test_upload_multiple_files(self, client, auth_headers, sample_passages_jsonl, sample_qaset_jsonl):
        """Test uploading multiple files."""
        files = {
            "passages": ("passages.jsonl", BytesIO(sample_passages_jsonl.encode()), "application/json"),
            "qaset": ("qaset.jsonl", BytesIO(sample_qaset_jsonl.encode()), "application/json")
        }
        
        response = client.post("/testdata/upload", files=files, headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["artifacts"]) == 2
        assert "passages" in data["artifacts"]
        assert "qaset" in data["artifacts"]
        assert data["counts"]["passages"] == 2
        assert data["counts"]["qaset"] == 2
    
    def test_upload_no_files(self, client, auth_headers):
        """Test uploading without any files."""
        response = client.post("/testdata/upload", headers=auth_headers)
        
        assert response.status_code == 400
        assert "At least one file must be provided" in response.json()["message"]
    
    def test_upload_invalid_file_extension(self, client, auth_headers):
        """Test uploading file with invalid extension."""
        files = {
            "passages": ("passages.txt", BytesIO(b"test"), "text/plain")
        }
        
        response = client.post("/testdata/upload", files=files, headers=auth_headers)
        
        assert response.status_code == 415
        assert "Unsupported file extension" in response.json()["message"]
    
    def test_upload_invalid_content_type(self, client, auth_headers, sample_passages_jsonl):
        """Test uploading file with invalid content type."""
        files = {
            "passages": ("passages.jsonl", BytesIO(sample_passages_jsonl.encode()), "image/png")
        }
        
        response = client.post("/testdata/upload", files=files, headers=auth_headers)
        
        assert response.status_code == 415
        assert "Unsupported content type" in response.json()["message"]
    
    def test_upload_file_too_large(self, client, auth_headers):
        """Test uploading file that's too large."""
        # Create large content (larger than MAX_FILE_SIZE)
        large_content = "x" * (11 * 1024 * 1024)  # 11MB
        files = {
            "passages": ("passages.jsonl", BytesIO(large_content.encode()), "application/json")
        }
        
        response = client.post("/testdata/upload", files=files, headers=auth_headers)
        
        assert response.status_code == 413
        assert "File too large" in response.json()["message"]
    
    def test_upload_invalid_jsonl(self, client, auth_headers):
        """Test uploading invalid JSONL content."""
        invalid_content = '''{"id": "1", "text": "valid"}
{"id": "2", "text": "invalid" missing_quote}'''
        
        files = {
            "passages": ("passages.jsonl", BytesIO(invalid_content.encode()), "application/json")
        }
        
        response = client.post("/testdata/upload", files=files, headers=auth_headers)
        
        assert response.status_code == 400
        data = response.json()
        assert "validation_errors" in data
        assert len(data["validation_errors"]) == 1
        assert data["validation_errors"][0]["artifact"] == "passages"
    
    def test_upload_attacks_yaml_format(self, client, auth_headers):
        """Test uploading attacks in YAML format."""
        yaml_content = """attacks:
  - "How to hack systems"
  - "Create malicious software\""""
        
        files = {
            "attacks": ("attacks.yaml", BytesIO(yaml_content.encode()), "text/yaml")
        }
        
        response = client.post("/testdata/upload", files=files, headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["counts"]["attacks"] == 2
    
    def test_upload_without_auth(self, client, sample_passages_jsonl):
        """Test uploading without authentication."""
        files = {
            "passages": ("passages.jsonl", BytesIO(sample_passages_jsonl.encode()), "application/json")
        }
        
        with patch.dict('os.environ', {'AUTH_ENABLED': 'true'}):
            response = client.post("/testdata/upload", files=files)
            assert response.status_code in [401, 403]


class TestByUrlEndpoint:
    """Test /testdata/by_url endpoint."""
    
    @pytest.mark.asyncio
    async def test_ingest_by_url_success(self, client, auth_headers, sample_passages_jsonl):
        """Test successful URL ingestion."""
        mock_response = AsyncMock()
        mock_response.text = sample_passages_jsonl
        mock_response.headers = {"content-type": "application/json"}
        mock_response.raise_for_status = AsyncMock()
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            
            request_data = {
                "urls": {
                    "passages": "https://example.com/passages.jsonl"
                }
            }
            
            response = client.post("/testdata/by_url", json=request_data, headers=auth_headers)
            
            assert response.status_code == 200
            data = response.json()
            assert "testdata_id" in data
            assert "passages" in data["artifacts"]
            assert data["counts"]["passages"] == 2
    
    def test_ingest_by_url_no_urls(self, client, auth_headers):
        """Test URL ingestion with no URLs."""
        request_data = {"urls": {}}
        
        response = client.post("/testdata/by_url", json=request_data, headers=auth_headers)
        
        assert response.status_code == 422  # Validation error
    
    def test_ingest_by_url_invalid_artifact_type(self, client, auth_headers):
        """Test URL ingestion with invalid artifact type."""
        request_data = {
            "urls": {
                "invalid_type": "https://example.com/test.jsonl"
            }
        }
        
        response = client.post("/testdata/by_url", json=request_data, headers=auth_headers)
        
        assert response.status_code == 422  # Validation error
    
    @pytest.mark.asyncio
    async def test_ingest_by_url_timeout(self, client, auth_headers):
        """Test URL ingestion with timeout."""
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.TimeoutException("Timeout")
            )
            
            request_data = {
                "urls": {
                    "passages": "https://example.com/passages.jsonl"
                }
            }
            
            response = client.post("/testdata/by_url", json=request_data, headers=auth_headers)
            
            assert response.status_code == 408
            assert "Timeout" in response.json()["message"]
    
    @pytest.mark.asyncio
    async def test_ingest_by_url_http_error(self, client, auth_headers):
        """Test URL ingestion with HTTP error."""
        mock_response = AsyncMock()
        mock_response.status_code = 404
        
        with patch('httpx.AsyncClient') as mock_client:
            from httpx import Request
            mock_request = Request("GET", "https://example.com/test")
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.HTTPStatusError("Not found", request=mock_request, response=mock_response)
            )
            
            request_data = {
                "urls": {
                    "passages": "https://example.com/passages.jsonl"
                }
            }
            
            response = client.post("/testdata/by_url", json=request_data, headers=auth_headers)
            
            assert response.status_code == 400
            assert "HTTP error" in response.json()["message"]


class TestPasteEndpoint:
    """Test /testdata/paste endpoint."""
    
    def test_paste_single_content(self, client, auth_headers, sample_passages_jsonl):
        """Test pasting single content type."""
        request_data = {
            "passages": sample_passages_jsonl
        }
        
        response = client.post("/testdata/paste", json=request_data, headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "testdata_id" in data
        assert "passages" in data["artifacts"]
        assert data["counts"]["passages"] == 2
    
    def test_paste_multiple_content(self, client, auth_headers, sample_passages_jsonl, sample_qaset_jsonl):
        """Test pasting multiple content types."""
        request_data = {
            "passages": sample_passages_jsonl,
            "qaset": sample_qaset_jsonl
        }
        
        response = client.post("/testdata/paste", json=request_data, headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["artifacts"]) == 2
        assert data["counts"]["passages"] == 2
        assert data["counts"]["qaset"] == 2
    
    def test_paste_no_content(self, client, auth_headers):
        """Test pasting without any content."""
        request_data = {}
        
        response = client.post("/testdata/paste", json=request_data, headers=auth_headers)
        
        assert response.status_code == 422  # Validation error from Pydantic
    
    def test_paste_content_too_large(self, client, auth_headers):
        """Test pasting content that's too large."""
        large_content = "x" * (11 * 1024 * 1024)  # 11MB
        request_data = {
            "passages": large_content
        }
        
        response = client.post("/testdata/paste", json=request_data, headers=auth_headers)
        
        assert response.status_code == 413
        assert "Content too large" in response.json()["message"]
    
    def test_paste_invalid_jsonl(self, client, auth_headers):
        """Test pasting invalid JSONL content."""
        invalid_content = '''{"id": "1", "text": "valid"}
{"id": "2", "text": "invalid" missing_quote}'''
        
        request_data = {
            "passages": invalid_content
        }
        
        response = client.post("/testdata/paste", json=request_data, headers=auth_headers)
        
        assert response.status_code == 400
        data = response.json()
        assert "validation_errors" in data
    
    def test_paste_attacks_text_format(self, client, auth_headers, sample_attacks_txt):
        """Test pasting attacks in text format."""
        request_data = {
            "attacks": sample_attacks_txt
        }
        
        response = client.post("/testdata/paste", json=request_data, headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["counts"]["attacks"] == 3


class TestMetaEndpoint:
    """Test /testdata/{testdata_id}/meta endpoint."""
    
    def test_get_meta_existing(self, client, auth_headers, sample_passages_jsonl):
        """Test getting metadata for existing bundle."""
        # First upload some data
        files = {
            "passages": ("passages.jsonl", BytesIO(sample_passages_jsonl.encode()), "application/json")
        }
        upload_response = client.post("/testdata/upload", files=files, headers=auth_headers)
        testdata_id = upload_response.json()["testdata_id"]
        
        # Get metadata
        response = client.get(f"/testdata/{testdata_id}/meta", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["testdata_id"] == testdata_id
        assert data["artifacts"]["passages"]["present"] is True
        assert data["artifacts"]["passages"]["count"] == 2
        assert data["artifacts"]["qaset"]["present"] is False
        assert "sha256" in data["artifacts"]["passages"]
        assert "X-Perf-Phase" in response.headers
    
    def test_get_meta_nonexistent(self, client, auth_headers):
        """Test getting metadata for non-existent bundle."""
        response = client.get("/testdata/nonexistent-id/meta", headers=auth_headers)
        
        assert response.status_code == 404
        assert "not found" in response.json()["message"]
    
    def test_get_meta_expired(self, client, auth_headers, sample_passages_jsonl):
        """Test getting metadata for expired bundle."""
        from datetime import datetime, timedelta
        from apps.testdata.store import get_store, create_bundle
        from apps.testdata.models import PassageRecord
        
        # Create and store an expired bundle directly
        expired_bundle = create_bundle(
            passages=[PassageRecord(id="1", text="test", meta={})]
        )
        expired_bundle.expires_at = datetime.utcnow() - timedelta(hours=1)
        
        store = get_store()
        testdata_id = store.put_bundle(expired_bundle)
        
        response = client.get(f"/testdata/{testdata_id}/meta", headers=auth_headers)
        
        assert response.status_code == 404  # Expired bundles are cleaned up, so they return 404
        assert "expired" in response.json()["message"]


class TestMetricsEndpoint:
    """Test /testdata/metrics endpoint."""
    
    def test_get_metrics(self, client, auth_headers):
        """Test getting ingestion metrics."""
        response = client.get("/testdata/metrics", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "ingest.bytes_total" in data
        assert "ingest.records_total" in data
        assert isinstance(data["ingest.bytes_total"], int)
        assert isinstance(data["ingest.records_total"], int)


class TestIntegrationFlow:
    """Test complete integration flow."""
    
    def test_upload_and_retrieve_flow(self, client, auth_headers, sample_passages_jsonl, sample_qaset_jsonl):
        """Test complete upload and retrieve flow."""
        # Upload data
        files = {
            "passages": ("passages.jsonl", BytesIO(sample_passages_jsonl.encode()), "application/json"),
            "qaset": ("qaset.jsonl", BytesIO(sample_qaset_jsonl.encode()), "application/json")
        }
        
        upload_response = client.post("/testdata/upload", files=files, headers=auth_headers)
        assert upload_response.status_code == 200
        
        testdata_id = upload_response.json()["testdata_id"]
        
        # Get metadata
        meta_response = client.get(f"/testdata/{testdata_id}/meta", headers=auth_headers)
        assert meta_response.status_code == 200
        
        meta_data = meta_response.json()
        assert meta_data["artifacts"]["passages"]["present"] is True
        assert meta_data["artifacts"]["qaset"]["present"] is True
        assert meta_data["artifacts"]["attacks"]["present"] is False
        assert meta_data["artifacts"]["schema"]["present"] is False
        
        # Verify data is accessible from store
        from apps.testdata.store import get_store
        store = get_store()
        bundle = store.get_bundle(testdata_id)
        assert bundle is not None
        assert bundle.passages is not None and len(bundle.passages) == 2
        assert bundle.qaset is not None and len(bundle.qaset) == 2
