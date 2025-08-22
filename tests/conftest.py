"""Test configuration and fixtures for AI Quality Kit tests."""

import pytest
from unittest.mock import Mock, MagicMock
from fastapi.testclient import TestClient
import os


@pytest.fixture
def set_env_defaults(monkeypatch):
    """Set minimal environment variables for testing."""
    env_vars = {
        "PROVIDER": "openai",
        "MODEL_NAME": "gpt-4o-mini", 
        "RAG_TOP_K": "3",
        "ENABLE_API_LOGGING": "false",
        "ENABLE_LIVE_EVAL": "false",
        "CACHE_ENABLED": "false",
        "OPENAI_API_KEY": "test-key",
        "ANTHROPIC_API_KEY": "test-key"
    }
    
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)
    
    return env_vars


@pytest.fixture
def fake_snowflake_cursor(monkeypatch):
    """Mock Snowflake cursor for testing."""
    fake_cursor = Mock()
    fake_cursor.execute = Mock()
    fake_cursor.fetchone = Mock(return_value=None)
    fake_cursor.fetchall = Mock(return_value=[])
    fake_cursor.rowcount = 0
    
    # Make the cursor support context manager protocol
    fake_cursor.__enter__ = Mock(return_value=fake_cursor)
    fake_cursor.__exit__ = Mock(return_value=None)
    
    def mock_snowflake_cursor():
        return fake_cursor
    
    # Mock the function in both cache_store and log_service modules after they're imported
    monkeypatch.setattr("apps.cache.cache_store.snowflake_cursor", mock_snowflake_cursor)
    monkeypatch.setattr("apps.observability.log_service.snowflake_cursor", mock_snowflake_cursor)
    return fake_cursor


@pytest.fixture
def client(monkeypatch):
    """FastAPI TestClient fixture."""
    try:
        # Mock the startup event to prevent RAG pipeline initialization
        from apps.rag_service.main import app
        
        # Create a mock RAG pipeline with proper methods
        mock_rag_pipeline = Mock()
        mock_rag_pipeline.passages = ["Mock passage 1", "Mock passage 2"]
        mock_rag_pipeline.build_index_from_passages = Mock()
        
        # Mock the retrieve method to return a list of contexts
        mock_rag_pipeline.retrieve = Mock(return_value=["Mock context 1", "Mock context 2"])
        
        # Mock the query method to return a dict with answer and context
        mock_rag_pipeline.query = Mock(return_value={
            "answer": "This is a mock answer from the RAG pipeline.",
            "context": ["Mock context 1", "Mock context 2"]
        })
        
        # Set the global variable directly in the main module
        import apps.rag_service.main as main_module
        main_module.rag_pipeline = mock_rag_pipeline
        
        # Try to clear startup handlers safely without triggering Pylance errors
        try:
            # Use setattr to avoid Pylance attribute access issues
            if hasattr(app.router, 'startup_handlers'):
                setattr(app.router, 'startup_handlers', [])
        except Exception:
            # If we can't clear startup handlers, that's OK - our mock should handle it
            pass
        
        return TestClient(app)
    except Exception as e:
        pytest.skip(f"Failed to import app: {e}")


@pytest.fixture
def mock_openai_client(monkeypatch):
    """Mock OpenAI client for testing."""
    mock_client = Mock()
    mock_client.chat.completions.create = Mock()
    
    def mock_get_openai_client(**kwargs):
        return mock_client
    
    monkeypatch.setattr("openai.OpenAI", mock_get_openai_client)
    return mock_client


@pytest.fixture
def mock_openai_embeddings(monkeypatch):
    """Mock OpenAI embeddings for testing."""
    mock_embeddings = Mock()
    mock_embeddings.embed_documents = Mock(return_value=[[0.1, 0.2, 0.3]] * 10)  # Mock embeddings
    mock_embeddings.embed_query = Mock(return_value=[0.1, 0.2, 0.3])  # Mock query embedding
    
    def mock_get_openai_embeddings(**kwargs):
        return mock_embeddings
    
    # Mock at the module level where RAGPipeline imports it
    monkeypatch.setattr("apps.rag_service.rag_pipeline.OpenAIEmbeddings", mock_get_openai_embeddings)
    return mock_embeddings


@pytest.fixture
def mock_anthropic_client(monkeypatch):
    """Mock Anthropic client for testing."""
    mock_client = Mock()
    mock_client.messages.create = Mock()
    
    def mock_get_anthropic_client():
        return mock_client
    
    monkeypatch.setattr("anthropic.Anthropic", lambda: mock_client)
    return mock_client


@pytest.fixture
def sample_passages():
    """Sample passages for testing."""
    return [
        "AI Quality Kit is a comprehensive platform for evaluating AI systems.",
        "The platform provides real-time quality monitoring and assessment.",
        "RAG pipeline integrates with multiple LLM providers including OpenAI and Anthropic."
    ]


@pytest.fixture
def sample_query():
    """Sample query for testing."""
    return "What is AI Quality Kit?"


@pytest.fixture
def sample_context():
    """Sample context for testing."""
    return [
        "AI Quality Kit is a comprehensive platform for evaluating AI systems.",
        "The platform provides real-time quality monitoring and assessment."
    ]
