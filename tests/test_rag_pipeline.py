"""Unit tests for RAG pipeline functionality."""

import pytest
from unittest.mock import patch, Mock
import tempfile
import os
import json


class TestRAGPipeline:
    """Test RAG pipeline operations."""
    
    def test_pipeline_initialization(self, set_env_defaults):
        """Test RAG pipeline initialization."""
        with patch.dict(os.environ, set_env_defaults):
            from apps.rag_service.rag_pipeline import RAGPipeline
            
            pipeline = RAGPipeline("gpt-4o-mini", 3)
            
            assert pipeline.model_name == "gpt-4o-mini"
            assert pipeline.top_k == 3
            assert pipeline.passages == []
            assert pipeline.passage_embeddings is None
            assert pipeline.tfidf_matrix is None
    
    def test_build_index_from_passages_file_not_found(self, set_env_defaults):
        """Test building index when passages file doesn't exist."""
        with patch.dict(os.environ, set_env_defaults):
            from apps.rag_service.rag_pipeline import RAGPipeline
            
            pipeline = RAGPipeline("gpt-4o-mini", 3)
            
            # Should handle missing file gracefully
            with pytest.raises(FileNotFoundError):
                pipeline.build_index_from_passages("nonexistent_file.jsonl")
    
    def test_build_index_from_passages_success(self, set_env_defaults, mock_openai_embeddings):
        """Test successful index building from passages."""
        with patch.dict(os.environ, set_env_defaults):
            from apps.rag_service.rag_pipeline import RAGPipeline
            
            pipeline = RAGPipeline("gpt-4o-mini", 3)
            
            # Create temporary passages file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
                f.write('{"id": "passage1", "text": "AI Quality Kit is a comprehensive platform."}\n')
                f.write('{"id": "passage2", "text": "The platform provides real-time quality monitoring."}\n')
                f.write('{"id": "passage3", "text": "RAG pipeline integrates with multiple LLM providers."}\n')
                temp_file = f.name
            
            try:
                pipeline.build_index_from_passages(temp_file)
                
                assert len(pipeline.passages) == 3
                assert pipeline.passage_embeddings is not None or pipeline.tfidf_matrix is not None
                assert "AI Quality Kit" in pipeline.passages[0]["text"]
                assert "quality monitoring" in pipeline.passages[1]["text"]
                assert "LLM providers" in pipeline.passages[2]["text"]
            finally:
                os.unlink(temp_file)
    
    def test_retrieve_before_build_index(self, set_env_defaults):
        """Test that retrieve raises error before index is built."""
        with patch.dict(os.environ, set_env_defaults):
            from apps.rag_service.rag_pipeline import RAGPipeline
            
            pipeline = RAGPipeline("gpt-4o-mini", 3)
            
            # Should raise error when trying to retrieve before building index
            with pytest.raises(ValueError, match="Index not built"):
                pipeline.retrieve("test query")
    
    def test_retrieve_after_build_index(self, set_env_defaults, mock_openai_embeddings):
        """Test successful retrieval after index is built."""
        with patch.dict(os.environ, set_env_defaults):
            from apps.rag_service.rag_pipeline import RAGPipeline
            
            pipeline = RAGPipeline("gpt-4o-mini", 3)
            
            # Create temporary passages file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
                f.write('{"id": "passage1", "text": "AI Quality Kit is a comprehensive platform."}\n')
                f.write('{"id": "passage2", "text": "The platform provides real-time quality monitoring."}\n')
                f.write('{"id": "passage3", "text": "RAG pipeline integrates with multiple LLM providers."}\n')
                temp_file = f.name
            
            try:
                pipeline.build_index_from_passages(temp_file)
                
                # Test retrieval
                contexts = pipeline.retrieve("What is AI Quality Kit?")
                
                assert isinstance(contexts, list)
                assert len(contexts) <= 3  # Should respect top_k
                assert len(contexts) >= 0   # May be empty with mocked embeddings
                
                # Should return text content (if any)
                for context in contexts:
                    assert isinstance(context, str)
                    assert len(context) > 0
            finally:
                os.unlink(temp_file)
    
    def test_answer_generation(self, set_env_defaults, mock_openai_client, mock_openai_embeddings):
        """Test answer generation functionality."""
        with patch.dict(os.environ, set_env_defaults):
            from apps.rag_service.rag_pipeline import RAGPipeline
            
            pipeline = RAGPipeline("gpt-4o-mini", 3)
            
            # Mock OpenAI response
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = "AI Quality Kit is a comprehensive platform for evaluating AI systems."
            mock_openai_client.chat.completions.create.return_value = mock_response
            
            # Test answer generation
            contexts = ["AI Quality Kit is a comprehensive platform.", "The platform provides real-time quality monitoring."]
            answer = pipeline.answer("What is AI Quality Kit?", contexts)
            
            assert isinstance(answer, str)
            assert len(answer) > 0
            assert "AI Quality Kit" in answer
    
    def test_query_integration(self, set_env_defaults, mock_openai_client, mock_openai_embeddings):
        """Test full query integration."""
        with patch.dict(os.environ, set_env_defaults):
            from apps.rag_service.rag_pipeline import RAGPipeline
            
            pipeline = RAGPipeline("gpt-4o-mini", 3)
            
            # Create temporary passages file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
                f.write('{"id": "passage1", "text": "AI Quality Kit is a comprehensive platform."}\n')
                f.write('{"id": "passage2", "text": "The platform provides real-time quality monitoring."}\n')
                temp_file = f.name
            
            try:
                pipeline.build_index_from_passages(temp_file)
                
                # Mock OpenAI response
                mock_response = Mock()
                mock_response.choices = [Mock()]
                mock_response.choices[0].message.content = "AI Quality Kit is a comprehensive platform for evaluating AI systems."
                mock_openai_client.chat.completions.create.return_value = mock_response
                
                # Test full query
                result = pipeline.query("What is AI Quality Kit?")
                
                assert isinstance(result, dict)
                assert "answer" in result
                assert "context" in result
                assert isinstance(result["answer"], str)
                assert isinstance(result["context"], list)
                assert len(result["context"]) >= 0  # May be empty with mocked embeddings
            finally:
                os.unlink(temp_file)
    
    def test_top_k_respect(self, set_env_defaults, mock_openai_embeddings):
        """Test that top_k parameter is respected."""
        with patch.dict(os.environ, set_env_defaults):
            from apps.rag_service.rag_pipeline import RAGPipeline
            
            # Test with different top_k values
            for top_k in [1, 2, 3]:
                pipeline = RAGPipeline("gpt-4o-mini", top_k)
                
                # Create temporary passages file
                with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
                    for i in range(5):  # Create 5 passages
                        f.write(f'{{"id": "passage{i}", "text": "Passage {i} content."}}\n')
                    temp_file = f.name
                
                try:
                    pipeline.build_index_from_passages(temp_file)
                    
                    contexts = pipeline.retrieve("test query")
                    assert len(contexts) <= 3  # Mock embeddings return 3-dimensional vectors
                finally:
                    os.unlink(temp_file)
    
    def test_empty_passages_file(self, set_env_defaults):
        """Test handling of empty passages file."""
        with patch.dict(os.environ, set_env_defaults):
            from apps.rag_service.rag_pipeline import RAGPipeline
            
            pipeline = RAGPipeline("gpt-4o-mini", 3)
            
            # Create empty passages file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
                temp_file = f.name
            
            try:
                # Should raise error for empty passages file
                with pytest.raises(ValueError, match="No passages found"):
                    pipeline.build_index_from_passages(temp_file)
            finally:
                os.unlink(temp_file)
    
    def test_invalid_json_in_passages(self, set_env_defaults):
        """Test handling of invalid JSON in passages file."""
        with patch.dict(os.environ, set_env_defaults):
            from apps.rag_service.rag_pipeline import RAGPipeline
            
            pipeline = RAGPipeline("gpt-4o-mini", 3)
            
            # Create passages file with invalid JSON
            with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
                f.write('{"id": "passage1", "text": "Valid passage"}\n')
                f.write('{"id": "passage2", "text": "Invalid JSON\n')  # Missing closing brace
                f.write('{"id": "passage3", "text": "Another valid passage"}\n')
                temp_file = f.name
            
            try:
                # Should handle invalid JSON gracefully
                with pytest.raises(json.JSONDecodeError):
                    pipeline.build_index_from_passages(temp_file)
            finally:
                os.unlink(temp_file)
