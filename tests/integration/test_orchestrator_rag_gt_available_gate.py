"""Integration test for RAG orchestrator with ground truth available and gating."""

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
        'text': 'This is a mock RAG response based on the provided context.',
        'prompt_tokens': 50,
        'completion_tokens': 15
    })
    return client


@pytest.fixture
def temp_testdata():
    """Create temporary test data files."""
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
        
        # Create qaset.jsonl
        qaset_file = temp_path / "qaset.jsonl"
        qaset_data = [
            {
                "qid": "q1",
                "question": "What is the capital of France?",
                "expected_answer": "Paris",
                "contexts": ["p1"]
            },
            {
                "qid": "q2", 
                "question": "What is Python?",
                "expected_answer": "A programming language",
                "contexts": ["p2"]
            }
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
async def test_rag_gt_available_gate_pass(mock_client, temp_testdata):
    """Test RAG evaluation with ground truth available and passing gate."""
    from apps.testdata.loaders_rag import RAGManifest
    
    # Create manifest
    manifest = RAGManifest(
        passages=temp_testdata["passages"],
        qaset=temp_testdata["qaset"]
    )
    
    # Set high thresholds that should pass
    thresholds = RAGThresholds(
        faithfulness=0.5,
        context_recall=0.5,
        answer_similarity=0.5
    )
    
    # Create RAG runner
    runner = RAGRunner(mock_client, manifest, thresholds)
    
    # Mock RAGAS evaluation to return good scores
    with patch('apps.orchestrator.rag_runner.evaluate_ragas') as mock_ragas:
        mock_ragas.return_value = {
            "ragas": {
                "faithfulness": 0.85,
                "context_recall": 0.80,
                "answer_relevancy": 0.82,
                "context_precision": 0.78,
                "answer_correctness": 0.75,
                "answer_similarity": 0.73
            }
        }
        
        # Run evaluation
        result = await runner.run_rag_quality("available")
        
        # Verify results
        assert result["gate"] is True
        assert result["gt_mode"] == "available"
        assert len(result["cases"]) > 0
        assert len(result["warnings"]) == 0
        
        # Check metrics
        metrics = result["metrics"]
        assert metrics["faithfulness"] == 0.85
        assert metrics["context_recall"] == 0.80
        assert metrics["answer_similarity"] == 0.73


@pytest.mark.asyncio
async def test_rag_gt_available_gate_fail(mock_client, temp_testdata):
    """Test RAG evaluation with ground truth available and failing gate."""
    from apps.testdata.loaders_rag import RAGManifest
    
    # Create manifest
    manifest = RAGManifest(
        passages=temp_testdata["passages"],
        qaset=temp_testdata["qaset"]
    )
    
    # Set high thresholds that should fail
    thresholds = RAGThresholds(
        faithfulness=0.9,  # High threshold
        context_recall=0.9,
        answer_similarity=0.9
    )
    
    # Create RAG runner
    runner = RAGRunner(mock_client, manifest, thresholds)
    
    # Mock RAGAS evaluation to return low scores
    with patch('apps.orchestrator.rag_runner.evaluate_ragas') as mock_ragas:
        mock_ragas.return_value = {
            "ragas": {
                "faithfulness": 0.65,  # Below threshold
                "context_recall": 0.60,  # Below threshold
                "answer_relevancy": 0.62,
                "context_precision": 0.58,
                "answer_correctness": 0.55,
                "answer_similarity": 0.53  # Below threshold
            }
        }
        
        # Run evaluation
        result = await runner.run_rag_quality("available")
        
        # Verify results
        assert result["gate"] is False
        assert result["gt_mode"] == "available"
        assert len(result["warnings"]) > 0
        
        # Check that warnings mention failed metrics
        warning_text = " ".join(result["warnings"])
        assert "faithfulness" in warning_text
        assert "context_recall" in warning_text
        assert "answer_similarity" in warning_text


@pytest.mark.asyncio
async def test_orchestrator_rag_integration(temp_testdata):
    """Test full orchestrator integration with RAG evaluation."""
    # Create orchestrator request
    request = OrchestratorRequest(
        target_mode="api",
        provider="mock",
        model="mock-model",
        suites=["rag_quality"],
        llm_option="rag",
        ground_truth="available",
        testdata_id="test-bundle-id",  # Add testdata_id so manifest can be resolved
        thresholds={
            "faithfulness": 0.7,
            "context_recall": 0.7,
            "answer_similarity": 0.7
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
        runner.intake_bundle_dir = temp_testdata["temp_dir"]
        
        # Setup mocks
        mock_client = Mock(spec=ApiClient)
        mock_client.generate = AsyncMock(return_value={
            'text': 'Mock response',
            'prompt_tokens': 20,
            'completion_tokens': 10
        })
        mock_make_client.return_value = mock_client
        
        mock_ragas.return_value = {
            "ragas": {
                "faithfulness": 0.85,
                "context_recall": 0.80,
                "answer_relevancy": 0.82,
                "answer_similarity": 0.75
            }
        }
        
        # Run RAG evaluation
        await runner._run_rag_quality_evaluation()
        
        # Verify results were stored
        assert hasattr(runner, 'rag_quality_result')
        assert runner.rag_quality_result["gate"] is True
        assert runner.rag_quality_result["gt_mode"] == "available"
        
        # Verify summary data
        assert hasattr(runner, 'rag_summary_data')
        assert runner.rag_summary_data["gate"] is True
        assert runner.rag_summary_data["ground_truth"] == "available"


@pytest.mark.asyncio
async def test_missing_qaset_error(mock_client):
    """Test error handling when QA set is missing for GT mode."""
    from apps.testdata.loaders_rag import RAGManifest
    
    # Create manifest with no qaset (None)
    manifest = RAGManifest()  # No passages or qaset
    
    # Create RAG runner
    runner = RAGRunner(mock_client, manifest, RAGThresholds())
    
    # Run evaluation - should return error for missing QA set in GT mode
    result = await runner.run_rag_quality("available")
    
    # Verify error handling
    assert result["gate"] is False
    assert "error" in result
    assert "Missing QA set" in result["error"]
    assert len(result["warnings"]) > 0
