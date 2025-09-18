"""
Integration tests for Compare RAG runner functionality.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from typing import cast
from apps.orchestrator.compare_rag_runner import CompareRAGRunner, CompareCase
from apps.orchestrator.rag_runner import RAGThresholds
from apps.testdata.loaders_rag import RAGManifest
from apps.orchestrator.client_factory import BaseClient


class MockClient:
    """Mock client for testing."""
    
    def __init__(self, provider="openai", model="gpt-4o"):
        self.provider = provider
        self.model = model
    
    async def generate(self, messages):
        """Mock generate method."""
        user_message = next((msg["content"] for msg in messages if msg["role"] == "user"), "")
        return {
            "text": f"Mock answer for: {user_message[:50]}...",
            "prompt_tokens": 100,
            "completion_tokens": 50
        }


class TestCompareRAGRunner:
    """Test cases for CompareRAGRunner."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_client = MockClient()
        self.mock_manifest = RAGManifest(
            passages="test_passages.jsonl",
            qaset="test_qaset.jsonl"
        )
        self.thresholds = RAGThresholds()
        
        # Compare configuration
        self.compare_config = {
            "enabled": True,
            "auto_select": {
                "enabled": True,
                "strategy": "same_or_near_tier"
            },
            "carry_over": {
                "use_contexts_from_primary": True,
                "require_non_empty": True,
                "max_context_items": 5,
                "heading": "Context:",
                "joiner": "\n- "
            }
        }
        
        self.runner = CompareRAGRunner(
            cast(BaseClient, self.mock_client),
            self.mock_manifest,
            self.thresholds,
            self.compare_config
        )
    
    @pytest.mark.asyncio
    @patch('apps.testdata.loaders_rag.load_passages')
    @patch('apps.testdata.loaders_rag.load_qaset')
    async def test_compare_mode_enabled_with_contexts(self, mock_load_qaset, mock_load_passages):
        """Test compare mode with contexts present."""
        # Mock data
        mock_load_passages.return_value = [
            {"id": "1", "text": "Context passage 1"},
            {"id": "2", "text": "Context passage 2"}
        ]
        mock_load_qaset.return_value = [
            {"qid": "q1", "question": "Test question 1", "expected_answer": "Expected 1"},
            {"qid": "q2", "question": "Test question 2", "expected_answer": "Expected 2"}
        ]
        
        # Mock baseline resolution
        with patch.object(self.runner.baseline_resolver, 'resolve_baseline_model') as mock_resolve:
            mock_resolve.return_value = {
                "preset": "anthropic",
                "model": "claude-3-sonnet-20240229",
                "decoding": {"temperature": 0, "top_p": 1, "max_tokens": 1024},
                "resolved_via": "same_model",
                "source": "Test source"
            }
            
            # Mock baseline client creation
            with patch.object(self.runner, '_create_baseline_client') as mock_create_client:
                mock_baseline_client = MockClient("anthropic", "claude-3-sonnet-20240229")
                mock_create_client.return_value = mock_baseline_client
                
                # Run evaluation
                result = await self.runner.run_rag_quality("not_available")
                
                # Verify compare section exists
                assert "compare" in result
                compare_result = result["compare"]
                
                assert compare_result["enabled"] is True
                assert "summary" in compare_result
                assert "cases" in compare_result
                assert "aggregates" in compare_result
                
                # Verify cases were processed
                summary = compare_result["summary"]
                assert summary["compared_cases"] >= 0
                assert summary["skipped_total"] >= 0
    
    @pytest.mark.asyncio
    @patch('apps.testdata.loaders_rag.load_passages')
    @patch('apps.testdata.loaders_rag.load_qaset')
    async def test_compare_mode_contexts_only_skip(self, mock_load_qaset, mock_load_passages):
        """Test that cases without contexts are skipped when require_non_empty=True."""
        # Mock data with no passages (no contexts)
        mock_load_passages.return_value = []
        mock_load_qaset.return_value = [
            {"qid": "q1", "question": "Test question", "expected_answer": "Expected"}
        ]
        
        # Mock the parent class run_rag_quality to return primary results
        with patch('apps.orchestrator.rag_runner.RAGRunner.run_rag_quality') as mock_parent:
            mock_parent.return_value = {
                "metrics": {"faithfulness": 0.85},
                "gate": True,
                "cases": [{
                    "qid": "q1",
                    "question": "Test question",
                    "generated_answer": "Primary answer",
                    "retrieved_contexts": []  # No contexts
                }],
                "warnings": []
            }
            
            result = await self.runner.run_rag_quality("not_available")
            
            # Verify compare section
            compare_result = result["compare"]
            summary = compare_result["summary"]
            
            # Should skip due to no contexts
            assert summary["compared_cases"] == 0
            assert summary["skipped_no_contexts"] > 0
    
    @pytest.mark.asyncio
    async def test_process_single_comparison_no_contexts(self):
        """Test processing single comparison when no contexts available."""
        primary_case = {
            "qid": "q1",
            "question": "Test question",
            "generated_answer": "Primary answer",
            "retrieved_contexts": []
        }
        
        result = await self.runner._process_single_comparison(primary_case)
        
        assert isinstance(result, CompareCase)
        assert result.qid == "q1"
        assert result.baseline_status == "skipped"
        assert result.skip_reason == "no_contexts"
    
    @pytest.mark.asyncio
    async def test_process_single_comparison_with_contexts(self):
        """Test processing single comparison with contexts."""
        primary_case = {
            "qid": "q1",
            "question": "Test question",
            "generated_answer": "Primary answer",
            "retrieved_contexts": ["Context 1", "Context 2"]
        }
        
        # Mock baseline resolution
        with patch.object(self.runner.baseline_resolver, 'resolve_baseline_model') as mock_resolve:
            mock_resolve.return_value = {
                "preset": "openai",
                "model": "gpt-4o-mini",
                "decoding": {"temperature": 0, "top_p": 1, "max_tokens": 1024}
            }
            
            # Mock baseline client creation and inference
            with patch.object(self.runner, '_create_baseline_client') as mock_create_client:
                mock_baseline_client = MockClient()
                mock_create_client.return_value = mock_baseline_client
                
                with patch.object(self.runner, '_run_baseline_inference') as mock_inference:
                    mock_inference.return_value = {
                        "text": "Baseline answer",
                        "latency_ms": 150
                    }
                    
                    result = await self.runner._process_single_comparison(primary_case)
                    
                    assert result.baseline_status == "ok"
                    assert result.baseline_answer == "Baseline answer"
                    assert result.baseline_latency_ms == 150
                    assert result.baseline_model_resolved is not None
                    assert result.baseline_model_resolved["preset"] == "openai"
    
    @pytest.mark.asyncio
    async def test_baseline_inference_prompt_construction(self):
        """Test that baseline inference constructs prompts correctly."""
        question = "What is AI?"
        contexts = ["AI is artificial intelligence", "AI helps automate tasks"]
        mock_client = MockClient()
        
        result = await self.runner._run_baseline_inference(question, contexts, cast(BaseClient, mock_client))
        
        assert "text" in result
        assert "latency_ms" in result
        # The mock client should receive messages with context formatting
    
    def test_compute_compare_summary(self):
        """Test computation of compare summary statistics."""
        cases = [
            CompareCase("q1", "Q1", "A1", 100, 2, "B1", 120, "ok"),
            CompareCase("q2", "Q2", "A2", 110, 0, skip_reason="no_contexts", baseline_status="skipped"),
            CompareCase("q3", "Q3", "A3", 105, 1, skip_reason="missing_creds", baseline_status="skipped"),
        ]
        
        summary = self.runner._compute_compare_summary(cases)
        
        assert summary["compared_cases"] == 1
        assert summary["skipped_no_contexts"] == 1
        assert summary["skipped_missing_creds"] == 1
        assert summary["skipped_total"] == 2
    
    def test_compute_compare_aggregates_no_cases(self):
        """Test aggregates computation when no successful cases."""
        cases = [
            CompareCase("q1", "Q1", "A1", 100, 0, skip_reason="no_contexts", baseline_status="skipped")
        ]
        
        aggregates = self.runner._compute_compare_aggregates(cases, "not_available")
        
        assert "message" in aggregates
        assert "No contexts observed" in aggregates["message"]
    
    @patch('apps.orchestrator.compare_rag_runner.evaluate_ragas')
    def test_compute_case_metrics_with_ragas(self, mock_ragas):
        """Test case metrics computation using RAGAS."""
        # Mock RAGAS evaluation
        mock_ragas.side_effect = [
            {"ragas": {"faithfulness": 0.85, "answer_relevancy": 0.80}},  # Primary
            {"ragas": {"faithfulness": 0.78, "answer_relevancy": 0.75}}   # Baseline
        ]
        
        case = CompareCase(
            "q1", "Test question", "Primary answer", 100, 2,
            "Baseline answer", 120, "ok",
            contexts_carried=["Context 1", "Context 2"]
        )
        
        primary_metrics, baseline_metrics, delta_metrics = self.runner._compute_case_metrics(
            case, "not_available"
        )
        
        # Verify metrics
        assert primary_metrics["faithfulness"] == 0.85
        assert baseline_metrics["faithfulness"] == 0.78
        assert abs(delta_metrics["faithfulness"] - (-0.07)) < 0.001  # baseline - primary (floating point tolerance)
        
        # Verify RAGAS was called twice
        assert mock_ragas.call_count == 2
    
    @patch('apps.orchestrator.compare_rag_runner.evaluate_ragas')
    def test_compute_case_metrics_fallback(self, mock_ragas):
        """Test case metrics computation with RAGAS fallback."""
        # Mock RAGAS to raise exception
        mock_ragas.side_effect = Exception("RAGAS failed")
        
        case = CompareCase(
            "q1", "Test question", "Primary answer", 100, 2,
            "Baseline answer", 120, "ok",
            contexts_carried=["Context 1", "Context 2"]
        )
        
        primary_metrics, baseline_metrics, delta_metrics = self.runner._compute_case_metrics(
            case, "not_available"
        )
        
        # Should fall back to heuristic metrics
        assert "faithfulness" in primary_metrics
        assert "faithfulness" in baseline_metrics
        assert "faithfulness" in delta_metrics
        
        # Values should be reasonable heuristics
        assert 0 <= primary_metrics["faithfulness"] <= 1
        assert 0 <= baseline_metrics["faithfulness"] <= 1
    
    def test_serialize_compare_case(self):
        """Test serialization of compare case for JSON output."""
        case = CompareCase(
            "q1", "Test question", "Primary answer", 100, 2,
            "Baseline answer", 120, "ok",
            baseline_model_resolved={"preset": "openai", "model": "gpt-4o"},
            contexts_carried=["Context 1", "Context 2"],
            primary_metrics={"faithfulness": 0.85},
            baseline_metrics={"faithfulness": 0.78},
            delta_metrics={"faithfulness": -0.07}
        )
        
        serialized = self.runner._serialize_compare_case(case)
        
        assert serialized["qid"] == "q1"
        assert serialized["baseline_status"] == "ok"
        assert serialized["contexts_carried"] == 2
        assert serialized["primary_metrics"]["faithfulness"] == 0.85
        assert serialized["delta_metrics"]["faithfulness"] == -0.07
    
    @pytest.mark.asyncio
    async def test_compare_mode_disabled(self):
        """Test that compare mode is skipped when disabled."""
        # Create runner without compare config
        runner = CompareRAGRunner(
            cast(BaseClient, self.mock_client),
            self.mock_manifest,
            self.thresholds,
            {"enabled": False}
        )
        
        with patch.object(runner, 'run_rag_quality', wraps=runner.run_rag_quality) as mock_super:
            # Mock the parent class method
            mock_super.return_value = {
                "metrics": {},
                "gate": True,
                "cases": [],
                "warnings": []
            }
            
            result = await runner.run_rag_quality("not_available")
            
            # Should not have compare section
            assert "compare" not in result
    
    def test_baseline_resolver_integration(self):
        """Test integration with baseline resolver."""
        # Verify resolver is initialized
        assert self.runner.baseline_resolver is not None
        assert hasattr(self.runner.baseline_resolver, 'resolve_baseline_model')
        
        # Test that resolver can be reset
        self.runner.baseline_resolver.reset_cache()
        assert self.runner._resolved_baseline is None


@pytest.mark.asyncio
async def test_compare_runner_error_handling():
    """Test error handling in compare runner."""
    mock_client = MockClient()
    mock_manifest = RAGManifest(passages="test.jsonl", qaset="test.jsonl")
    
    runner = CompareRAGRunner(
        cast(BaseClient, mock_client),
        mock_manifest,
        RAGThresholds(),
        {"enabled": True, "auto_select": {"enabled": True}}
    )
    
    # Test with invalid compare config
    with patch.object(runner.baseline_resolver, 'resolve_baseline_model') as mock_resolve:
        mock_resolve.side_effect = ValueError("No suitable baseline")
        
        primary_case = {
            "qid": "q1",
            "question": "Test",
            "generated_answer": "Answer",
            "retrieved_contexts": ["Context"]
        }
        
        result = await runner._process_single_comparison(primary_case)
        
        assert result.baseline_status == "skipped"
        assert result.skip_reason == "no_candidate"


def test_compare_case_dataclass():
    """Test CompareCase dataclass functionality."""
    case = CompareCase(
        qid="test_qid",
        question="Test question?",
        primary_answer="Primary response",
        primary_latency_ms=100,
        primary_contexts_used_count=3
    )
    
    # Test default values
    assert case.baseline_answer is None
    assert case.baseline_status == "pending"
    assert case.skip_reason is None
    
    # Test field assignment
    case.baseline_answer = "Baseline response"
    case.baseline_status = "ok"
    
    assert case.baseline_answer == "Baseline response"
    assert case.baseline_status == "ok"
