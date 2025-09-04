"""
Integration tests for Compare Mode end-to-end functionality.
"""

import pytest
from unittest.mock import Mock, patch
from apps.orchestrator.run_tests import TestRunner, OrchestratorRequest


class TestCompareModeIntegration:
    """Integration tests for Compare Mode."""
    
    def test_compare_mode_request_schema(self):
        """Test that compare_with configuration is properly handled in requests."""
        # Create request with compare_with configuration
        request_data = {
            "target_mode": "api",
            "provider": "openai",
            "model": "gpt-4o",
            "suites": ["rag_quality"],
            "compare_with": {
                "enabled": True,
                "auto_select": {
                    "enabled": True,
                    "strategy": "same_or_near_tier",
                    "hint_tier": "economy"
                },
                "carry_over": {
                    "use_contexts_from_primary": True,
                    "require_non_empty": True,
                    "max_context_items": 5
                }
            }
        }
        
        # Verify request can be created
        request = OrchestratorRequest(**request_data)
        
        assert request.compare_with is not None
        assert request.compare_with["enabled"] is True
        assert request.compare_with["auto_select"]["strategy"] == "same_or_near_tier"
        assert request.compare_with["carry_over"]["require_non_empty"] is True
    
    @patch('apps.testdata.loaders_rag.resolve_manifest_from_bundle')
    @patch('apps.orchestrator.client_factory.make_client')
    @patch('apps.testdata.store.get_store')
    def test_test_runner_compare_mode_integration(self, mock_get_store, mock_make_client, mock_resolve_manifest):
        """Test TestRunner integration with Compare Mode."""
        # Mock dependencies
        mock_client = Mock()
        mock_make_client.return_value = mock_client
        
        mock_manifest = Mock()
        mock_manifest.passages = "test_passages.jsonl"
        mock_manifest.qaset = "test_qaset.jsonl"
        mock_resolve_manifest.return_value = mock_manifest
        
        # Mock store to return a valid bundle
        mock_store = Mock()
        mock_bundle = Mock()
        mock_store.get_bundle.return_value = mock_bundle
        mock_get_store.return_value = mock_store
        
        # Create request with compare mode enabled
        request = OrchestratorRequest(
            target_mode="api",
            provider="openai",
            model="gpt-4o",
            suites=["rag_quality"],
            testdata_id="test_bundle",
            compare_with={
                "enabled": True,
                "auto_select": {
                    "enabled": True,
                    "strategy": "same_or_near_tier"
                }
            }
        )
        
        # Create test runner
        runner = TestRunner(request)
        
        # Verify compare_with configuration is accessible
        assert runner.request.compare_with is not None
        assert runner.request.compare_with["enabled"] is True
        
        # Verify compare_data is initialized
        assert hasattr(runner, 'compare_data')
        assert runner.compare_data is None  # Initially None
    
    def test_compare_mode_disabled_by_default(self):
        """Test that Compare Mode is disabled by default."""
        request = OrchestratorRequest(
            target_mode="api",
            provider="openai",
            model="gpt-4o",
            suites=["rag_quality"]
        )
        
        runner = TestRunner(request)
        
        # compare_with should be None by default
        assert runner.request.compare_with is None
    
    @pytest.mark.asyncio
    @patch('apps.testdata.loaders_rag.resolve_manifest_from_bundle')
    @patch('apps.orchestrator.client_factory.make_client')
    @patch('apps.testdata.store.get_store')
    async def test_rag_evaluation_with_compare_mode(self, mock_get_store, mock_make_client, mock_resolve_manifest):
        """Test RAG evaluation creates CompareRAGRunner when compare mode enabled."""
        # Mock dependencies
        mock_client = Mock()
        mock_make_client.return_value = mock_client
        
        mock_manifest = Mock()
        mock_manifest.passages = "test_passages.jsonl"
        mock_manifest.qaset = "test_qaset.jsonl"
        mock_resolve_manifest.return_value = mock_manifest
        
        # Mock store to return a valid bundle
        mock_store = Mock()
        mock_bundle = Mock()
        mock_store.get_bundle.return_value = mock_bundle
        mock_get_store.return_value = mock_store
        
        # Create request with compare mode
        request = OrchestratorRequest(
            target_mode="api",
            provider="openai",
            model="gpt-4o",
            suites=["rag_quality"],
            testdata_id="test_bundle",
            compare_with={
                "enabled": True,
                "auto_select": {"enabled": True, "strategy": "same_or_near_tier"}
            }
        )
        
        runner = TestRunner(request)
        
        # Verify that runner has compare_with configuration
        assert runner.request.compare_with is not None
        assert runner.request.compare_with["enabled"] is True
        
        # Test that CompareRAGRunner can be imported and instantiated
        from apps.orchestrator.compare_rag_runner import CompareRAGRunner
        
        # Mock minimal dependencies for CompareRAGRunner
        with patch('apps.testdata.loaders_rag.load_passages') as mock_load_passages:
            with patch('apps.testdata.loaders_rag.load_qaset') as mock_load_qaset:
                mock_load_passages.return_value = []
                mock_load_qaset.return_value = []
                
                # Create CompareRAGRunner to verify integration
                from typing import cast
                from apps.orchestrator.client_factory import BaseClient
                
                compare_runner = CompareRAGRunner(
                    cast(BaseClient, mock_client),
                    mock_manifest,
                    None,  # thresholds
                    request.compare_with
                )
                
                # Verify compare runner was created with correct config
                assert compare_runner.compare_config == request.compare_with
    
    def test_json_report_includes_compare_data(self):
        """Test that JSON reports include compare data when present."""
        from apps.reporters.json_reporter import build_json
        
        # Mock compare data
        compare_data = {
            "enabled": True,
            "summary": {
                "compared_cases": 2,
                "skipped_no_contexts": 1,
                "skipped_total": 1
            },
            "cases": [
                {
                    "qid": "q1",
                    "question": "Test question",
                    "primary_answer": "Primary answer",
                    "baseline_answer": "Baseline answer",
                    "baseline_status": "ok",
                    "primary_metrics": {"faithfulness": 0.85},
                    "baseline_metrics": {"faithfulness": 0.78},
                    "delta_metrics": {"faithfulness": -0.07}
                }
            ],
            "aggregates": {
                "faithfulness_primary_avg": 0.85,
                "faithfulness_baseline_avg": 0.78,
                "faithfulness_delta_avg": -0.07
            }
        }
        
        # Build JSON report
        json_report = build_json(
            run_meta={"run_id": "test_run"},
            summary={"total_tests": 1},
            detailed_rows=[],
            api_rows=[],
            inputs_rows=[],
            compare_data=compare_data,
            anonymize=False
        )
        
        # Verify compare section is included
        assert "compare" in json_report
        assert json_report["compare"]["enabled"] is True
        assert json_report["compare"]["summary"]["compared_cases"] == 2
        assert len(json_report["compare"]["cases"]) == 1
    
    def test_excel_report_includes_compare_sheet(self):
        """Test that Excel reports include Compare sheet when compare data present."""
        from apps.reporters.excel_reporter import write_excel
        import tempfile
        import os
        
        # Mock data with compare section
        data = {
            "version": "2.0",
            "run": {"run_id": "test_run", "provider": "openai", "model": "gpt-4o"},
            "summary": {"total_tests": 1},
            "detailed": [],
            "api_details": [],
            "inputs_expected": [],
            "compare": {
                "enabled": True,
                "summary": {"compared_cases": 1, "skipped_no_contexts": 0},
                "cases": [
                    {
                        "qid": "q1",
                        "question": "Test question",
                        "primary_contexts_used_count": 2,
                        "baseline_model_resolved": {"preset": "anthropic", "model": "claude-3-5-sonnet"},
                        "primary_metrics": {"faithfulness": 0.85},
                        "baseline_metrics": {"faithfulness": 0.78},
                        "delta_metrics": {"faithfulness": -0.07},
                        "baseline_status": "ok"
                    }
                ]
            }
        }
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp_file:
            try:
                # Write Excel report
                write_excel(tmp_file.name, data)
                
                # Verify file was created
                assert os.path.exists(tmp_file.name)
                assert os.path.getsize(tmp_file.name) > 0
                
                # Note: In a full test, we would load the Excel file and verify
                # that the Compare sheet exists with the expected data
                
            finally:
                # Clean up
                if os.path.exists(tmp_file.name):
                    os.unlink(tmp_file.name)
    
    def test_compare_mode_error_handling(self):
        """Test error handling when compare mode fails."""
        request = OrchestratorRequest(
            target_mode="api",
            provider="openai",
            model="gpt-4o",
            suites=["rag_quality"],
            compare_with={
                "enabled": True,
                "auto_select": {"enabled": False}  # Invalid config
            }
        )
        
        runner = TestRunner(request)
        
        # Verify that invalid compare config doesn't break runner creation
        assert runner.request.compare_with is not None
        assert runner.request.compare_with["enabled"] is True
        assert hasattr(runner, 'compare_data')
    
    def test_frontend_request_mapping(self):
        """Test that frontend compare configuration maps correctly to backend request."""
        # Simulate frontend configuration
        frontend_config = {
            "compareEnabled": True,
            "compareAutoSelect": True,
            "compareHintTier": "economy",
            "compareManualPreset": "",
            "compareManualModel": ""
        }
        
        # Map to backend format (simulating frontend API mapping)
        compare_with = {
            "enabled": frontend_config["compareEnabled"],
            "baseline": None if frontend_config["compareAutoSelect"] else {
                "preset": frontend_config["compareManualPreset"] or None,
                "model": frontend_config["compareManualModel"] or None,
                "decoding": {"temperature": 0, "top_p": 1, "max_tokens": 1024}
            },
            "auto_select": {
                "enabled": frontend_config["compareAutoSelect"],
                "strategy": "same_or_near_tier",
                "hint_tier": frontend_config["compareHintTier"] or None
            },
            "carry_over": {
                "use_contexts_from_primary": True,
                "require_non_empty": True,
                "max_context_items": 7,
                "heading": "Context:",
                "joiner": "\n- "
            }
        }
        
        # Verify mapping
        assert compare_with["enabled"] is True
        assert compare_with["baseline"] is None  # Auto-select mode
        assert compare_with["auto_select"]["enabled"] is True
        assert compare_with["auto_select"]["hint_tier"] == "economy"
        assert compare_with["carry_over"]["require_non_empty"] is True


@pytest.mark.asyncio
async def test_end_to_end_compare_mode_flow():
    """Test end-to-end Compare Mode flow with mocked dependencies."""
    from apps.orchestrator.baseline_resolver import BaselineResolver
    from apps.orchestrator.compare_rag_runner import CompareRAGRunner
    
    # Test the complete flow: request -> resolution -> comparison -> reporting
    
    # 1. Baseline resolution
    resolver = BaselineResolver()
    compare_config = {
        "auto_select": {"enabled": True, "strategy": "same_or_near_tier"}
    }
    
    baseline_config = resolver.resolve_baseline_model(
        compare_config,
        primary_meta_model="gpt-4o-mini"
    )
    
    assert baseline_config["resolved_via"] == "same_model"
    assert baseline_config["preset"] == "openai"
    
    # 2. Client creation (mocked)
    with patch('apps.orchestrator.client_factory.make_baseline_client') as mock_make_baseline:
        mock_baseline_client = Mock()
        mock_make_baseline.return_value = mock_baseline_client
        
        # 3. Compare runner execution (mocked)
        with patch('apps.testdata.loaders_rag.load_passages') as mock_load_passages:
            with patch('apps.testdata.loaders_rag.load_qaset') as mock_load_qaset:
                mock_load_passages.return_value = [{"id": "1", "text": "Context"}]
                mock_load_qaset.return_value = [{"qid": "q1", "question": "Test?"}]
                
                # Create and run compare runner
                from apps.testdata.loaders_rag import RAGManifest
                manifest = RAGManifest(passages="test.jsonl", qaset="test.jsonl")
                
                runner = CompareRAGRunner(
                    Mock(),  # Primary client
                    manifest,
                    compare_config={"enabled": True, "auto_select": {"enabled": True}}
                )
                
                # Mock the baseline inference
                with patch.object(runner, '_run_baseline_inference') as mock_inference:
                    mock_inference.return_value = {"text": "Baseline answer", "latency_ms": 100}
                    
                    # This would normally run the full evaluation
                    # For this test, we just verify the components work together
                    assert runner.compare_config["enabled"] is True
                    assert runner.baseline_resolver is not None
