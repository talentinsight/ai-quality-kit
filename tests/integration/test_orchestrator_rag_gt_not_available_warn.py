"""Integration test for RAG orchestrator with ground truth not available."""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path
import tempfile
import json

from apps.orchestrator.run_tests import TestRunner, OrchestratorRequest
from apps.orchestrator.client_factory import ApiClient
from apps.orchestrator.rag_runner import RAGRunner, RAGThresholds


@pytest.fixture
def mock_client():
    """Mock API client for testing."""
    client = Mock(spec=ApiClient)
    client.generate = AsyncMock(return_value={
        'text': 'This is a mock RAG response without ground truth.',
        'prompt_tokens': 45,
        'completion_tokens': 12
    })
    return client


@pytest.fixture
def temp_passages_only():
    """Create temporary test data with passages and QA set (for no-GT mode testing)."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create passages.jsonl
        passages_file = temp_path / "passages.jsonl"
        passages_data = [
            {"id": "p1", "text": "The capital of France is Paris."},
            {"id": "p2", "text": "Python is a programming language."},
            {"id": "p3", "text": "Machine learning uses algorithms to learn patterns."}
        ]
        with open(passages_file, 'w') as f:
            for passage in passages_data:
                f.write(json.dumps(passage) + '\n')
        
        # Create qaset.jsonl (needed for generating cases, even in no-GT mode)
        qaset_file = temp_path / "qaset.jsonl"
        qaset_data = [
            {"qid": "q1", "question": "What is the capital of France?", "expected_answer": "Paris", "contexts": ["p1"]},
            {"qid": "q2", "question": "What is Python?", "expected_answer": "A programming language", "contexts": ["p2"]}
        ]
        with open(qaset_file, 'w') as f:
            for qa in qaset_data:
                f.write(json.dumps(qa) + '\n')
        
        yield {
            "passages": str(passages_file),
            "qaset": str(qaset_file),
            "temp_dir": temp_path
        }


@pytest.mark.asyncio
async def test_rag_gt_not_available_warning(mock_client, temp_passages_only):
    """Test RAG evaluation without ground truth shows appropriate warnings."""
    from apps.testdata.loaders_rag import RAGManifest
    
    # Create manifest with passages and qaset
    manifest = RAGManifest(
        passages=temp_passages_only["passages"],
        qaset=temp_passages_only["qaset"]
    )
    
    # Create RAG runner
    runner = RAGRunner(mock_client, manifest, RAGThresholds())
    
    # Mock RAGAS evaluation to return GT-agnostic metrics only
    with patch('apps.orchestrator.rag_runner.evaluate_ragas') as mock_ragas:
        mock_ragas.return_value = {
            "ragas": {
                "faithfulness": 0.83,
                "answer_relevancy": 0.81,
                "context_precision": 0.78
                # Note: No GT-dependent metrics like context_recall, answer_correctness
            }
        }
        
        # Run evaluation in no-GT mode
        result = await runner.run_rag_quality("not_available")
        
        # Verify results
        assert result["gate"] is True  # No-GT mode doesn't fail gate
        assert result["gt_mode"] == "not_available"
        assert len(result["warnings"]) > 0
        
        # Check warning message
        warning_text = " ".join(result["warnings"])
        assert "Ground truth not available" in warning_text
        assert "GT-agnostic" in warning_text
        
        # Check only GT-agnostic metrics are present
        metrics = result["metrics"]
        assert "faithfulness" in metrics
        assert "answer_relevancy" in metrics
        assert "context_precision" in metrics
        
        # GT-dependent metrics should not be present
        assert "context_recall" not in metrics
        assert "answer_correctness" not in metrics
        assert "answer_similarity" not in metrics


@pytest.mark.asyncio
async def test_rag_no_passages_error(mock_client):
    """Test error handling when no passages are available."""
    from apps.testdata.loaders_rag import RAGManifest
    
    # Create empty manifest
    manifest = RAGManifest()
    
    # Create RAG runner
    runner = RAGRunner(mock_client, manifest, RAGThresholds())
    
    # Run evaluation - should return error
    result = await runner.run_rag_quality("not_available")
    
    # Verify error handling
    assert result["gate"] is False
    assert "error" in result
    assert "Missing passages" in result["error"]
    assert len(result["warnings"]) > 0


@pytest.mark.asyncio
async def test_rag_internal_scorers_fallback(mock_client, temp_passages_only):
    """Test fallback to internal scorers when RAGAS fails."""
    from apps.testdata.loaders_rag import RAGManifest
    
    # Create manifest with passages and qaset
    manifest = RAGManifest(
        passages=temp_passages_only["passages"],
        qaset=temp_passages_only["qaset"]
    )
    
    # Create RAG runner
    runner = RAGRunner(mock_client, manifest, RAGThresholds())
    
    # Mock RAGAS to raise an exception (simulating RAGAS unavailable)
    with patch('apps.orchestrator.rag_runner.evaluate_ragas') as mock_ragas:
        mock_ragas.side_effect = Exception("RAGAS not available")
        
        # Run evaluation - should fall back to internal scorers
        result = await runner.run_rag_quality("not_available")
        
        # Verify fallback worked
        assert result["gate"] is True
        assert result["gt_mode"] == "not_available"
        
        # Check that internal scorer metrics are present
        metrics = result["metrics"]
        assert "faithfulness" in metrics
        assert "answer_relevancy" in metrics
        assert "context_precision" in metrics
        
        # Values should be placeholder scores from internal implementation
        assert 0.7 <= metrics["faithfulness"] <= 0.9
        assert 0.7 <= metrics["answer_relevancy"] <= 0.9
        assert 0.7 <= metrics["context_precision"] <= 0.9


@pytest.mark.asyncio
async def test_orchestrator_no_gt_integration(temp_passages_only):
    """Test full orchestrator integration without ground truth."""
    # Create orchestrator request
    request = OrchestratorRequest(
        target_mode="api",
        provider="mock",
        model="mock-model",
        suites=["rag_quality"],
        llm_option="rag",
        ground_truth="not_available",
        testdata_id="test-bundle-id",  # Add testdata_id so manifest can be resolved
        thresholds={
            "faithfulness": 0.7,
            "answer_relevancy": 0.7,
            "context_precision": 0.7
        },
        determinism={
            "temperature": 0.0,
            "top_p": 1.0,
            "seed": 42
        }
    )
    
    # Mock client creation, RAGAS evaluation, and testdata store
    with patch('apps.orchestrator.client_factory.make_client') as mock_make_client, \
         patch('apps.orchestrator.rag_runner.evaluate_ragas') as mock_ragas, \
         patch('apps.testdata.store.get_store') as mock_store:
        
        # Mock testdata store to return bundle exists
        mock_store_instance = Mock()
        mock_store_instance.get_meta.return_value = {"testdata_id": "test-bundle-id", "created_at": "2024-01-01"}
        mock_store.return_value = mock_store_instance
        
        # Create test runner
        runner = TestRunner(request)
        
        # Mock the intake bundle directory
        runner.intake_bundle_dir = temp_passages_only["temp_dir"]
        
        # Setup mocks
        mock_client = Mock(spec=ApiClient)
        mock_client.generate = AsyncMock(return_value={
            'text': 'Mock response without GT',
            'prompt_tokens': 25,
            'completion_tokens': 8
        })
        mock_make_client.return_value = mock_client
        
        mock_ragas.return_value = {
            "ragas": {
                "faithfulness": 0.83,
                "answer_relevancy": 0.81,
                "context_precision": 0.78
            }
        }
        
        # Run RAG evaluation
        await runner._run_rag_quality_evaluation()
        
        # Verify results were stored
        assert hasattr(runner, 'rag_quality_result')
        assert runner.rag_quality_result["gate"] is True  # No-GT mode passes gate
        assert runner.rag_quality_result["gt_mode"] == "not_available"
        
        # Verify warnings are present
        assert len(runner.rag_quality_result["warnings"]) > 0
        
        # Verify summary data
        assert hasattr(runner, 'rag_summary_data')
        assert runner.rag_summary_data["gate"] is True
        assert runner.rag_summary_data["ground_truth"] == "not_available"


@pytest.mark.asyncio
async def test_prompt_robustness_included(mock_client, temp_passages_only):
    """Test that prompt robustness is included in no-GT mode."""
    from apps.testdata.loaders_rag import RAGManifest
    
    # Create manifest with only passages
    manifest = RAGManifest(passages=temp_passages_only["passages"])
    
    # Create RAG runner
    runner = RAGRunner(mock_client, manifest, RAGThresholds())
    
    # Mock RAGAS evaluation
    with patch('apps.orchestrator.rag_runner.evaluate_ragas') as mock_ragas:
        mock_ragas.return_value = {
            "ragas": {
                "faithfulness": 0.83,
                "answer_relevancy": 0.81,
                "context_precision": 0.78
            }
        }
        
        # Run evaluation
        result = await runner.run_rag_quality("not_available")
        
        # Verify prompt robustness is included
        metrics = result["metrics"]
        assert "prompt_robustness" in metrics
        assert isinstance(metrics["prompt_robustness"], float)
        assert 0.0 <= metrics["prompt_robustness"] <= 1.0
