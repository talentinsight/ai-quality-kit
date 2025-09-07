"""Test JSONL upload with various content types."""

import pytest
from fastapi.testclient import TestClient
from io import BytesIO
from apps.rag_service.main import app, setup_routers
from apps.testdata.store import get_store

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

def test_jsonl_upload_with_octet_stream(client, auth_headers):
    """Test that JSONL files with application/octet-stream content type are accepted."""
    
    # Sample JSONL content for passages
    jsonl_content = '''{"id": "p1", "text": "This is a test passage."}
{"id": "p2", "text": "This is another test passage."}'''
    
    # Create file-like object
    file_data = BytesIO(jsonl_content.encode('utf-8'))
    
    # Test passages upload with octet-stream content type
    response = client.post(
        "/testdata/upload",
        files={
            "passages": ("test_passages.jsonl", file_data, "application/octet-stream")
        },
        headers=auth_headers
    )
    
    assert response.status_code == 200, f"Upload failed: {response.text}"
    data = response.json()
    assert "testdata_id" in data
    assert "passages" in data["artifacts"]

def test_jsonl_upload_with_json_content_type(client, auth_headers):
    """Test that JSONL files with application/json content type are accepted."""
    
    # Sample JSONL content for qaset
    jsonl_content = '''{"qid": "q1", "question": "What is AI?", "expected_answer": "Artificial Intelligence"}
{"qid": "q2", "question": "What is ML?", "expected_answer": "Machine Learning"}'''
    
    # Create file-like object
    file_data = BytesIO(jsonl_content.encode('utf-8'))
    
    # Test qaset upload with json content type
    response = client.post(
        "/testdata/upload",
        files={
            "qaset": ("test_qaset.jsonl", file_data, "application/json")
        },
        headers=auth_headers
    )
    
    assert response.status_code == 200, f"Upload failed: {response.text}"
    data = response.json()
    assert "testdata_id" in data
    assert "qaset" in data["artifacts"]

def test_jsonl_upload_with_csv_content_type(client, auth_headers):
    """Test that JSONL files with text/csv content type are accepted (browser misidentification)."""
    
    # Sample JSONL content for passages
    jsonl_content = '''{"id": "p1", "text": "CSV misidentified as JSONL."}'''
    
    # Create file-like object
    file_data = BytesIO(jsonl_content.encode('utf-8'))
    
    # Test passages upload with csv content type (should be allowed)
    response = client.post(
        "/testdata/upload",
        files={
            "passages": ("test_passages.jsonl", file_data, "text/csv")
        },
        headers=auth_headers
    )
    
    assert response.status_code == 200, f"Upload failed: {response.text}"
    data = response.json()
    assert "testdata_id" in data
    assert "passages" in data["artifacts"]

def test_invalid_content_type_still_rejected(client, auth_headers):
    """Test that truly invalid content types are still rejected."""
    
    # Sample content
    content = '''{"id": "p1", "text": "Test"}'''
    
    # Create file-like object
    file_data = BytesIO(content.encode('utf-8'))
    
    # Test with invalid content type
    response = client.post(
        "/testdata/upload",
        files={
            "passages": ("test.jsonl", file_data, "image/png")
        },
        headers=auth_headers
    )
    
    assert response.status_code == 415
    assert "Unsupported content type" in response.text
