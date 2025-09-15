"""Integration tests for run profiles and reporting fields."""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

from apps.orchestrator.run_tests import TestRunner, OrchestratorRequest
from apps.orchestrator.run_profiles import (
    resolve_run_profile,
    apply_profile_to_qa_cases,
    get_profile_metadata,
    RateLimitSafetyManager
)


class TestRunProfileResolution:
    """Test run profile resolution from requests."""
    
    def test_resolve_profile_default_smoke(self):
        """Test default profile resolution to smoke."""
        request = OrchestratorRequest(
            target_mode="api",
            provider="mock",
            model="mock-model",
            suites=["rag_quality"]
        )
        
        profile = resolve_run_profile(request)
        
        assert profile.name == "smoke"
        assert profile.qa_sample_size == 20
        assert profile.concurrency_limit == 2
    
    def test_resolve_profile_from_options(self):
        """Test profile resolution from options."""
        request = OrchestratorRequest(
            target_mode="api",
            provider="mock",
            model="mock-model",
            suites=["rag_quality"],
            options={"profile": "full"}
        )
        
        profile = resolve_run_profile(request)
        
        assert profile.name == "full"
        assert profile.qa_sample_size is None
        assert profile.concurrency_limit == 4
    
    def test_resolve_profile_from_volume(self):
        """Test profile resolution from volume field."""
        request = OrchestratorRequest(
            target_mode="api",
            provider="mock",
            model="mock-model",
            suites=["rag_quality"],
            volume={"profile": "full"}
        )
        
        profile = resolve_run_profile(request)
        
        assert profile.name == "full"
        assert profile.qa_sample_size is None
    
    def test_resolve_profile_custom_qa_sample_size(self):
        """Test profile with custom QA sample size override."""
        request = OrchestratorRequest(
            target_mode="api",
            provider="mock",
            model="mock-model",
            suites=["rag_quality"],
            options={"profile": "smoke", "qa_sample_size": 50}
        )
        
        profile = resolve_run_profile(request)
        
        assert profile.name == "smoke"
        assert profile.qa_sample_size == 50  # Overridden
        assert "custom sample size" in profile.description
    
    def test_resolve_profile_with_perf_repeats(self):
        """Test profile adjustment for performance testing."""
        request = OrchestratorRequest(
            target_mode="api",
            provider="mock",
            model="mock-model",
            suites=["rag_quality"],
            options={"profile": "full", "perf_repeats": 5}
        )
        
        profile = resolve_run_profile(request)
        
        assert profile.name == "full"
        assert profile.concurrency_limit == 2  # Capped for perf testing
        assert "perf testing" in profile.description
    
    def test_resolve_profile_unknown_defaults_to_smoke(self):
        """Test unknown profile defaults to smoke."""
        request = OrchestratorRequest(
            target_mode="api",
            provider="mock",
            model="mock-model",
            suites=["rag_quality"],
            options={"profile": "unknown_profile"}
        )
        
        profile = resolve_run_profile(request)
        
        assert profile.name == "smoke"  # Falls back to smoke


class TestProfileApplication:
    """Test profile application to QA cases."""
    
    def test_apply_smoke_profile_sampling(self):
        """Test smoke profile sampling."""
        qa_cases = [
            {"qid": f"q{i}", "question": f"Question {i}?", "expected_answer": f"Answer {i}"}
            for i in range(50)
        ]
        
        from apps.orchestrator.run_profiles import RUN_PROFILES
        smoke_profile = RUN_PROFILES["smoke"]
        
        filtered_cases = apply_profile_to_qa_cases(qa_cases, smoke_profile)
        
        assert len(filtered_cases) == 20  # Smoke profile limit
    
    def test_apply_full_profile_no_sampling(self):
        """Test full profile doesn't sample."""
        qa_cases = [
            {"qid": f"q{i}", "question": f"Question {i}?", "expected_answer": f"Answer {i}"}
            for i in range(50)
        ]
        
        from apps.orchestrator.run_profiles import RUN_PROFILES
        full_profile = RUN_PROFILES["full"]
        
        filtered_cases = apply_profile_to_qa_cases(qa_cases, full_profile)
        
        assert len(filtered_cases) == 50  # No sampling
    
    def test_apply_profile_deterministic_sampling(self):
        """Test profile sampling is deterministic."""
        qa_cases = [
            {"qid": f"q{i}", "question": f"Question {i}?", "expected_answer": f"Answer {i}"}
            for i in range(100)
        ]
        
        from apps.orchestrator.run_profiles import RUN_PROFILES
        smoke_profile = RUN_PROFILES["smoke"]
        
        filtered1 = apply_profile_to_qa_cases(qa_cases, smoke_profile)
        filtered2 = apply_profile_to_qa_cases(qa_cases, smoke_profile)
        
        # Should be identical
        assert len(filtered1) == len(filtered2) == 20
        for c1, c2 in zip(filtered1, filtered2):
            assert c1["qid"] == c2["qid"]
    
    def test_apply_profile_fewer_cases_than_limit(self):
        """Test profile when fewer cases than limit."""
        qa_cases = [
            {"qid": "q1", "question": "Question 1?", "expected_answer": "Answer 1"},
            {"qid": "q2", "question": "Question 2?", "expected_answer": "Answer 2"}
        ]
        
        from apps.orchestrator.run_profiles import RUN_PROFILES
        smoke_profile = RUN_PROFILES["smoke"]  # Limit 20
        
        filtered_cases = apply_profile_to_qa_cases(qa_cases, smoke_profile)
        
        assert len(filtered_cases) == 2  # All cases returned


class TestRateLimitSafety:
    """Test rate limiting and safety mechanisms."""
    
    @pytest.mark.asyncio
    async def test_rate_limit_manager_concurrency(self):
        """Test rate limit manager respects concurrency."""
        manager = RateLimitSafetyManager(concurrency_limit=2)
        
        # Track concurrent executions
        concurrent_count = 0
        max_concurrent = 0
        
        async def mock_operation():
            nonlocal concurrent_count, max_concurrent
            concurrent_count += 1
            max_concurrent = max(max_concurrent, concurrent_count)
            await asyncio.sleep(0.1)  # Simulate work
            concurrent_count -= 1
            return "success"
        
        # Start 5 operations simultaneously
        import asyncio
        tasks = [
            manager.execute_with_backoff(mock_operation(), f"case_{i}")
            for i in range(5)
        ]
        
        results = await asyncio.gather(*tasks)
        
        assert len(results) == 5
        assert all(r == "success" for r in results)
        assert max_concurrent <= 2  # Should not exceed concurrency limit
    
    @pytest.mark.asyncio
    async def test_rate_limit_manager_retry_on_429(self):
        """Test rate limit manager retries on 429 errors."""
        manager = RateLimitSafetyManager(concurrency_limit=1, base_delay=0.01)
        
        call_count = 0
        
        async def mock_operation_with_429():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                # Simulate 429 error first two times
                raise Exception("429 Too Many Requests")
            return "success_after_retries"
        
        result = await manager.execute_with_backoff(mock_operation_with_429, "test_case")
        
        assert result == "success_after_retries"
        assert call_count == 3  # Should have retried twice
    
    @pytest.mark.asyncio
    async def test_rate_limit_manager_non_rate_limit_error(self):
        """Test rate limit manager doesn't retry non-rate-limit errors."""
        manager = RateLimitSafetyManager(concurrency_limit=1)
        
        async def mock_operation_with_other_error():
            raise ValueError("Some other error")
        
        with pytest.raises(ValueError, match="Some other error"):
            await manager.execute_with_backoff(mock_operation_with_other_error(), "test_case")
    
    def test_rate_limit_manager_stats(self):
        """Test rate limit manager statistics."""
        manager = RateLimitSafetyManager(concurrency_limit=3)
        
        stats = manager.get_stats()
        
        assert "concurrency_limit" in stats
        assert "active_requests" in stats
        assert "total_retries" in stats
        assert "cases_with_retries" in stats
        
        assert stats["concurrency_limit"] == 3
        assert stats["active_requests"] == 0  # No active requests
        assert stats["total_retries"] == 0
        assert stats["cases_with_retries"] == 0


class TestProfileMetadata:
    """Test profile metadata generation."""
    
    def test_get_profile_metadata_basic(self):
        """Test basic profile metadata."""
        from apps.orchestrator.run_profiles import RUN_PROFILES
        smoke_profile = RUN_PROFILES["smoke"]
        
        metadata = get_profile_metadata(smoke_profile)
        
        assert metadata["profile"] == "smoke"
        assert metadata["qa_sample_size"] == 20
        assert metadata["concurrency_limit"] == 2
        assert metadata["description"] == "Quick smoke test with limited samples"
    
    def test_get_profile_metadata_with_rate_limit_stats(self):
        """Test profile metadata with rate limiting stats."""
        from apps.orchestrator.run_profiles import RUN_PROFILES
        full_profile = RUN_PROFILES["full"]
        
        rate_limit_stats = {
            "total_retries": 5,
            "cases_with_retries": 2
        }
        
        metadata = get_profile_metadata(full_profile, rate_limit_stats)
        
        assert metadata["profile"] == "full"
        assert metadata["rate_limit_retries"] == 5
        assert metadata["cases_with_retries"] == 2


class TestIntegrationWithOrchestrator:
    """Test integration with orchestrator."""
    
    @pytest.fixture
    def temp_testdata(self):
        """Create temporary test data files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create passages.jsonl
            passages_file = temp_path / "passages.jsonl"
            passages_data = [
                {"id": "p1", "text": "The capital of France is Paris."},
                {"id": "p2", "text": "Python is a programming language."}
            ]
            with open(passages_file, 'w') as f:
                for passage in passages_data:
                    f.write(json.dumps(passage) + '\n')
            
            # Create qaset.jsonl with many cases
            qaset_file = temp_path / "qaset.jsonl"
            qaset_data = [
                {
                    "qid": f"q{i}",
                    "question": f"Question {i}?",
                    "expected_answer": f"Answer {i}",
                    "contexts": ["p1", "p2"]
                }
                for i in range(50)  # 50 test cases
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
    async def test_orchestrator_respects_smoke_profile(self, temp_testdata):
        """Test orchestrator respects smoke profile."""
        request = OrchestratorRequest(
            target_mode="api",
            provider="mock",
            model="mock-model",
            suites=["rag_quality"],
            llm_option="rag",
            ground_truth="available",
            testdata_id="test-bundle-id",  # Add testdata_id so manifest can be resolved
            options={"profile": "smoke"}  # Smoke profile
        )
        
        # Mock the RAG evaluation to track how many cases were processed
        processed_cases = []
        
        with patch('apps.orchestrator.client_factory.make_client') as mock_make_client, \
             patch('apps.orchestrator.rag_runner.evaluate_ragas') as mock_ragas, \
             patch('apps.testdata.store.get_store') as mock_store:
            
            # Mock testdata store to return bundle exists
            mock_store_instance = Mock()
            mock_store_instance.get_meta.return_value = {"testdata_id": "test-bundle-id", "created_at": "2024-01-01"}
            mock_store.return_value = mock_store_instance
            
            runner = TestRunner(request)
            runner.intake_bundle_dir = temp_testdata["temp_dir"]
            
            mock_client = Mock()
            mock_client.generate = AsyncMock(return_value={
                'text': 'Mock response',
                'prompt_tokens': 20,
                'completion_tokens': 10
            })
            mock_make_client.return_value = mock_client
            
            def mock_ragas_eval(dataset, **kwargs):
                nonlocal processed_cases
                processed_cases = dataset
                return {
                    "ragas": {
                        "faithfulness": 0.85,
                        "context_recall": 0.80,
                        "answer_relevancy": 0.82
                    }
                }
            
            mock_ragas.side_effect = mock_ragas_eval
            
            # Run RAG evaluation
            await runner._run_rag_quality_evaluation()
            
            # Should have processed only smoke profile limit (20 cases)
            assert len(processed_cases) <= 20
            
            # Check that profile metadata is stored
            assert hasattr(runner, 'rag_summary_data')
            # Profile info should be in metadata (implementation dependent)
    
    @pytest.mark.asyncio
    async def test_orchestrator_respects_full_profile(self, temp_testdata):
        """Test orchestrator respects full profile."""
        request = OrchestratorRequest(
            target_mode="api",
            provider="mock",
            model="mock-model",
            suites=["rag_quality"],
            llm_option="rag",
            ground_truth="available",
            testdata_id="test-bundle-id",  # Add testdata_id so manifest can be resolved
            options={"profile": "full"}  # Full profile
        )
        
        # Mock the RAG evaluation to track how many cases were processed
        processed_cases = []
        
        with patch('apps.orchestrator.client_factory.make_client') as mock_make_client, \
             patch('apps.orchestrator.rag_runner.evaluate_ragas') as mock_ragas, \
             patch('apps.testdata.store.get_store') as mock_store:
            
            # Mock testdata store to return bundle exists
            mock_store_instance = Mock()
            mock_store_instance.get_meta.return_value = {"testdata_id": "test-bundle-id", "created_at": "2024-01-01"}
            mock_store.return_value = mock_store_instance
            
            runner = TestRunner(request)
            runner.intake_bundle_dir = temp_testdata["temp_dir"]
            
            mock_client = Mock()
            mock_client.generate = AsyncMock(return_value={
                'text': 'Mock response',
                'prompt_tokens': 20,
                'completion_tokens': 10
            })
            mock_make_client.return_value = mock_client
            
            def mock_ragas_eval(dataset, **kwargs):
                nonlocal processed_cases
                processed_cases = dataset
                return {
                    "ragas": {
                        "faithfulness": 0.85,
                        "context_recall": 0.80,
                        "answer_relevancy": 0.82
                    }
                }
            
            mock_ragas.side_effect = mock_ragas_eval
            
            # Run RAG evaluation
            await runner._run_rag_quality_evaluation()
            
        # Should have processed all cases (full profile has no limit)
        assert len(processed_cases) == 50  # All test cases from fixture
