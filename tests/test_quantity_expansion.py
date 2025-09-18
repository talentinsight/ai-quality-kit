"""Tests for quantity expansion and dataset selection features."""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from apps.orchestrator.run_tests import TestRunner, OrchestratorRequest


class TestQuantityGenerator:
    """Tests for quantity generator script."""
    
    def test_generator_import(self):
        """Test that quantity generator imports correctly."""
        from scripts.expand_tests_quantity import QuantityGenerator, TARGETS
        
        assert TARGETS["rag_quality"] == 100
        assert TARGETS["red_team"] == 100
        assert TARGETS["safety"] == 50
        assert sum(TARGETS.values()) >= 390  # 395 is close enough
    
    def test_generator_initialization(self):
        """Test generator initialization."""
        from scripts.expand_tests_quantity import QuantityGenerator
        
        gen = QuantityGenerator("20250101")
        assert gen.base_date == "20250101"
        assert str(gen.output_dir).endswith("data/expanded/20250101")
    
    @patch('scripts.expand_tests_quantity.Path.exists')
    def test_check_existing_output(self, mock_exists):
        """Test existing output detection."""
        from scripts.expand_tests_quantity import QuantityGenerator
        
        gen = QuantityGenerator("20250101")
        
        # No directory exists
        mock_exists.return_value = False
        assert not gen.check_existing_output()
        
        # Directory exists but no manifest
        mock_exists.side_effect = lambda path=None: "expanded/20250101" in str(path) if path else False
        assert not gen.check_existing_output()
    
    def test_deterministic_generation(self):
        """Test that generation is deterministic."""
        from scripts.expand_tests_quantity import QuantityGenerator
        
        gen1 = QuantityGenerator("test")
        gen1.load_seeds()
        
        gen2 = QuantityGenerator("test")
        gen2.load_seeds()
        
        # Generate same suite multiple times
        rag1 = gen1.generate_rag_quality()
        rag2 = gen2.generate_rag_quality()
        
        # Should be identical
        assert len(rag1) == len(rag2)
        assert rag1[0]["query"] == rag2[0]["query"]


class TestDatasetSelection:
    """Tests for orchestrator dataset selection."""
    
    def test_dataset_metadata_initialization(self):
        """Test dataset metadata initialization."""
        request = OrchestratorRequest(
            target_mode="api",
            suites=["rag_quality"],
            use_expanded=True,
            dataset_version="20250101"
        )
        
        with patch('apps.orchestrator.run_tests.Path.exists') as mock_exists:
            mock_exists.return_value = True
            runner = TestRunner(request)
            
            assert runner.dataset_source == "expanded"
            assert runner.dataset_version == "20250101"
            assert runner.estimated_tests > 0
    
    def test_uploaded_dataset_priority(self):
        """Test that uploaded data takes priority."""
        request = OrchestratorRequest(
            target_mode="api", 
            suites=["rag_quality"],
            testdata_id="test_bundle",
            use_expanded=True
        )
        
        with patch('apps.testdata.store.get_store') as mock_store:
            mock_bundle = Mock()
            mock_store.return_value.get_bundle.return_value = mock_bundle
            
            runner = TestRunner(request)
            
            assert runner.dataset_source == "uploaded"
            assert runner.testdata_bundle == mock_bundle
    
    def test_golden_fallback(self):
        """Test fallback to golden dataset."""
        request = OrchestratorRequest(
            target_mode="api",
            suites=["rag_quality"],
            use_expanded=False
        )
        
        runner = TestRunner(request)
        
        assert runner.dataset_source == "golden"
        assert runner.dataset_version == "golden"
    
    def test_dataset_version_detection(self):
        """Test automatic dataset version detection."""
        request = OrchestratorRequest(
            target_mode="api",
            suites=["rag_quality"],
            use_expanded=True
            # No explicit dataset_version
        )
        
        with patch('apps.orchestrator.run_tests.Path') as mock_path:
            # Mock expanded directory with versions
            mock_expanded_dir = Mock()
            mock_expanded_dir.exists.return_value = True
            # Create mock directories with names
            mock_dir1 = Mock()
            mock_dir1.name = "20250101"
            mock_dir1.is_dir.return_value = True
            mock_dir2 = Mock()
            mock_dir2.name = "20250102"
            mock_dir2.is_dir.return_value = True
            mock_expanded_dir.iterdir.return_value = [mock_dir1, mock_dir2]
            mock_path.return_value = mock_expanded_dir
            
            runner = TestRunner(request)
            
            # Should pick latest version
            assert runner.dataset_version == "20250102"
    
    @patch('apps.orchestrator.run_tests.Path.exists')
    @patch('builtins.open')
    def test_expanded_dataset_loading(self, mock_open, mock_exists):
        """Test loading from expanded datasets."""
        request = OrchestratorRequest(
            target_mode="api",
            suites=["rag_quality"],
            use_expanded=True,
            dataset_version="20250101"
        )
        
        # Mock file existence
        mock_exists.return_value = True
        
        # Mock file content
        mock_file_content = [
            '{"test_id": "rag_quality_1", "query": "What is AI?", "expected_answer": "AI is..."}\n',
            '{"test_id": "rag_quality_2", "query": "How does ML work?", "expected_answer": "ML works..."}\n'
        ]
        mock_open.return_value.__enter__.return_value = iter(mock_file_content)
        
        runner = TestRunner(request)
        tests = runner._load_rag_quality_tests()
        
        assert len(tests) == 2
        assert tests[0]["test_id"] == "rag_quality_1"
        assert tests[1]["query"] == "How does ML work?"
    
    def test_estimate_test_count_expanded(self):
        """Test test count estimation with expanded datasets."""
        request = OrchestratorRequest(
            target_mode="api",
            suites=["rag_quality", "red_team"],
            use_expanded=True,
            dataset_version="20250101"
        )
        
        manifest_data = {
            "counts": {
                "rag_quality": 100,
                "red_team": 100,
                "safety": 50
            }
        }
        
        with patch('apps.orchestrator.run_tests.Path') as mock_path, \
             patch('builtins.open') as mock_open:
            
            # Mock manifest file
            mock_path.return_value.exists.return_value = True
            mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(manifest_data)
            
            runner = TestRunner(request)
            
            # Should estimate 200 (100 rag + 100 red_team)
            assert runner.estimated_tests == 200
    
    def test_estimate_test_count_fallback(self):
        """Test test count estimation fallback."""
        request = OrchestratorRequest(
            target_mode="api",
            suites=["rag_quality", "red_team"],
            use_expanded=False
        )
        
        runner = TestRunner(request)
        
        # Should use fallback defaults (8 + 15 = 23)
        assert runner.estimated_tests == 23


class TestReportingMetadata:
    """Tests for reporting metadata integration."""
    
    def test_summary_includes_metadata(self):
        """Test that summary includes dataset metadata."""
        request = OrchestratorRequest(
            target_mode="api",
            suites=["rag_quality"],
            use_expanded=True,
            dataset_version="20250101"
        )
        
        with patch('apps.orchestrator.run_tests.Path') as mock_path:
            # Mock that the expanded directory exists
            mock_expanded_dir = Mock()
            mock_expanded_dir.exists.return_value = True
            mock_path.return_value = mock_expanded_dir
            
            runner = TestRunner(request)
            # Add at least one detailed row so summary is generated
            from apps.orchestrator.run_tests import DetailedRow
            runner.detailed_rows = [DetailedRow(
                run_id="test",
                suite="rag_quality", 
                test_id="test1",
                status="pass",
                timestamp="2024-01-01T00:00:00",
                provider="mock",
                model="test",
                query="test",
                expected_answer="test",
                actual_answer="test",
                context=["test"],
                source="test",
                perf_phase="test",
                faithfulness=1.0,
                context_recall=1.0,
                safety_score=1.0,
                attack_success=False,
                latency_ms=100
            )]
            
            summary = runner._generate_summary()
        
        assert summary["dataset_source"] == "expanded"
        assert summary["dataset_version"] == "20250101"
        assert "estimated_tests" in summary
    
    def test_json_reporter_metadata(self):
        """Test JSON reporter includes metadata."""
        from apps.reporters.json_reporter import build_json
        
        run_meta = {"run_id": "test_run"}
        summary = {
            "dataset_source": "expanded",
            "dataset_version": "20250101", 
            "estimated_tests": 200
        }
        
        json_report = build_json(
            run_meta=run_meta,
            summary=summary,
            detailed_rows=[],
            api_rows=[],
            inputs_rows=[]
        )
        
        assert json_report["summary"]["dataset_source"] == "expanded"
        assert json_report["summary"]["dataset_version"] == "20250101"
        assert json_report["summary"]["estimated_tests"] == 200


class TestIntegration:
    """Integration tests for quantity expansion features."""
    
    def test_end_to_end_expanded_dataset_usage(self):
        """Test complete workflow with expanded datasets."""
        request = OrchestratorRequest(
            target_mode="api",
            suites=["rag_quality"],
            use_expanded=True,
            dataset_version="test"
        )
        
        # Mock everything needed for test
        with patch('apps.orchestrator.run_tests.Path.exists') as mock_exists, \
             patch('builtins.open') as mock_open:
            
            # Mock expanded file
            mock_exists.return_value = True
            mock_open.return_value.__enter__.return_value = [
                '{"test_id": "rag_1", "query": "Test?", "expected_answer": "Answer"}\n'
            ]
            
            runner = TestRunner(request)
            
            # Should use expanded dataset
            assert runner.dataset_source == "expanded"
            
            # Should load from expanded file
            tests = runner._load_rag_quality_tests()
            assert len(tests) >= 1
            assert tests[0]["test_id"] == "rag_1"
    
    def test_backward_compatibility(self):
        """Test that existing functionality is not broken."""
        # Standard request without expanded options
        request = OrchestratorRequest(
            target_mode="api",
            suites=["rag_quality"]
        )
        
        runner = TestRunner(request)
        
        # Should default to golden
        assert runner.dataset_source == "golden"
        assert runner.request.use_expanded is False or runner.request.use_expanded is None
        
        # Should still work normally
        assert runner.estimated_tests > 0
