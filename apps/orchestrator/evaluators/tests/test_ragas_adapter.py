"""Tests for Ragas adapter module.

These tests ensure the Ragas evaluator works correctly with deterministic behavior,
graceful degradation, and proper threshold checking.
"""

import unittest
from unittest.mock import patch, MagicMock
import os
import sys
from typing import Dict, List, Any

# Add the project root to the path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../../..'))

from apps.orchestrator.evaluators.ragas_adapter import evaluate_ragas, check_ragas_thresholds


class TestRagasAdapter(unittest.TestCase):
    """Test cases for Ragas adapter functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.sample_data = [
            {
                'question': 'What is the capital of France?',
                'answer': 'The capital of France is Paris.',
                'contexts': ['Paris is the capital and most populous city of France.'],
                'ground_truth': 'Paris'
            },
            {
                'question': 'What is machine learning?',
                'answer': 'Machine learning is a subset of AI that enables computers to learn without explicit programming.',
                'contexts': ['Machine learning is a method of data analysis that automates analytical model building.'],
                'ground_truth': 'Machine learning is a subset of artificial intelligence.'
            }
        ]
    
    def test_evaluate_ragas_import_failure(self):
        """Test that evaluate_ragas returns empty dict when Ragas import fails."""
        with patch('apps.orchestrator.evaluators.ragas_adapter.evaluate', side_effect=ImportError("No module named 'ragas'")):
            result = evaluate_ragas(self.sample_data)
            self.assertEqual(result, {})
    
    def test_evaluate_ragas_empty_samples(self):
        """Test that evaluate_ragas handles empty sample list gracefully."""
        result = evaluate_ragas([])
        self.assertEqual(result, {})
    
    def test_evaluate_ragas_invalid_samples(self):
        """Test that evaluate_ragas handles invalid samples gracefully."""
        invalid_samples = [
            {'question': '', 'answer': 'test', 'contexts': []},  # Empty question
            {'question': 'test', 'answer': '', 'contexts': ['context']},  # Empty answer
            {'question': 'test', 'answer': 'test', 'contexts': 'not_a_list'},  # Invalid contexts
            {'answer': 'test', 'contexts': ['context']},  # Missing question
        ]
        
        result = evaluate_ragas(invalid_samples)
        self.assertEqual(result, {})
    
    def test_evaluate_ragas_mixed_valid_invalid_samples(self):
        """Test that evaluate_ragas processes only valid samples from mixed input."""
        mixed_samples = [
            {'question': '', 'answer': 'test', 'contexts': []},  # Invalid
            {
                'question': 'What is Python?',
                'answer': 'Python is a programming language.',
                'contexts': ['Python is a high-level programming language.']
            },  # Valid
        ]
        
        # Mock the Ragas evaluation to return deterministic results
        mock_dataset = MagicMock()
        mock_result = {
            'faithfulness': 0.85,
            'answer_relevancy': 0.90
        }
        
        with patch('apps.orchestrator.evaluators.ragas_adapter.Dataset') as mock_dataset_class, \
             patch('apps.orchestrator.evaluators.ragas_adapter.evaluate') as mock_evaluate:
            
            mock_dataset_class.from_dict.return_value = mock_dataset
            mock_evaluate.return_value = mock_result
            
            result = evaluate_ragas(mixed_samples)
            
            # Should return results for the valid sample
            expected = {'ragas': {'faithfulness': 0.85, 'answer_relevancy': 0.90}}
            self.assertEqual(result, expected)
    
    @patch('apps.orchestrator.evaluators.ragas_adapter.Dataset')
    @patch('apps.orchestrator.evaluators.ragas_adapter.evaluate')
    def test_evaluate_ragas_successful_evaluation(self, mock_evaluate, mock_dataset_class):
        """Test successful Ragas evaluation with mocked results."""
        # Mock the dataset creation
        mock_dataset = MagicMock()
        mock_dataset_class.from_dict.return_value = mock_dataset
        
        # Mock the evaluation result
        mock_result = {
            'faithfulness': 0.85,
            'answer_relevancy': 0.90,
            'context_precision': 0.88,
            'context_recall': 0.82
        }
        mock_evaluate.return_value = mock_result
        
        result = evaluate_ragas(self.sample_data)
        
        # Verify the result structure
        expected = {
            'ragas': {
                'faithfulness': 0.85,
                'answer_relevancy': 0.90,
                'context_precision': 0.88,
                'context_recall': 0.82
            }
        }
        self.assertEqual(result, expected)
        
        # Verify that evaluate was called with correct parameters
        mock_evaluate.assert_called_once()
        call_args = mock_evaluate.call_args
        self.assertIsNotNone(call_args)
    
    @patch('apps.orchestrator.evaluators.ragas_adapter.Dataset')
    @patch('apps.orchestrator.evaluators.ragas_adapter.evaluate')
    def test_evaluate_ragas_handles_nan_values(self, mock_evaluate, mock_dataset_class):
        """Test that evaluate_ragas handles NaN values in results."""
        mock_dataset = MagicMock()
        mock_dataset_class.from_dict.return_value = mock_dataset
        
        # Mock result with NaN value
        mock_result = {
            'faithfulness': float('nan'),
            'answer_relevancy': 0.90
        }
        mock_evaluate.return_value = mock_result
        
        result = evaluate_ragas(self.sample_data)
        
        # Should only include valid metrics
        expected = {'ragas': {'answer_relevancy': 0.90}}
        self.assertEqual(result, expected)
    
    @patch('apps.orchestrator.evaluators.ragas_adapter.Dataset')
    @patch('apps.orchestrator.evaluators.ragas_adapter.evaluate')
    def test_evaluate_ragas_handles_evaluation_errors(self, mock_evaluate, mock_dataset_class):
        """Test that evaluate_ragas handles evaluation errors gracefully."""
        mock_dataset = MagicMock()
        mock_dataset_class.from_dict.return_value = mock_dataset
        
        # Mock evaluation failure
        mock_evaluate.side_effect = Exception("Evaluation failed")
        
        result = evaluate_ragas(self.sample_data)
        
        # Should return empty dict on error
        self.assertEqual(result, {})
    
    @patch('apps.orchestrator.evaluators.ragas_adapter.Dataset')
    @patch('apps.orchestrator.evaluators.ragas_adapter.evaluate')
    def test_evaluate_ragas_handles_uvloop_error(self, mock_evaluate, mock_dataset_class):
        """Test that evaluate_ragas handles uvloop compatibility errors."""
        mock_dataset = MagicMock()
        mock_dataset_class.from_dict.return_value = mock_dataset
        
        # Mock uvloop error
        mock_evaluate.side_effect = Exception("Can't patch loop of type <class 'uvloop.Loop'>")
        
        result = evaluate_ragas(self.sample_data)
        
        # Should return empty dict on uvloop error
        self.assertEqual(result, {})
    
    def test_check_ragas_thresholds_all_pass(self):
        """Test threshold checking when all metrics pass."""
        ragas_metrics = {
            'faithfulness': 0.85,
            'answer_relevancy': 0.90,
            'context_precision': 0.88,
            'context_recall': 0.82
        }
        
        thresholds = {
            'min_faithfulness': 0.8,
            'min_answer_relevancy': 0.85,
            'min_context_precision': 0.8,
            'min_context_recall': 0.8
        }
        
        result = check_ragas_thresholds(ragas_metrics, thresholds)
        
        expected = {
            'min_faithfulness': True,
            'min_answer_relevancy': True,
            'min_context_precision': True,
            'min_context_recall': True
        }
        self.assertEqual(result, expected)
    
    def test_check_ragas_thresholds_some_fail(self):
        """Test threshold checking when some metrics fail."""
        ragas_metrics = {
            'faithfulness': 0.75,  # Below threshold
            'answer_relevancy': 0.90,
            'context_precision': 0.70,  # Below threshold
            'context_recall': 0.82
        }
        
        thresholds = {
            'min_faithfulness': 0.8,
            'min_answer_relevancy': 0.85,
            'min_context_precision': 0.8,
            'min_context_recall': 0.8
        }
        
        result = check_ragas_thresholds(ragas_metrics, thresholds)
        
        expected = {
            'min_faithfulness': False,
            'min_answer_relevancy': True,
            'min_context_precision': False,
            'min_context_recall': True
        }
        self.assertEqual(result, expected)
    
    def test_check_ragas_thresholds_missing_metrics(self):
        """Test threshold checking when some metrics are missing."""
        ragas_metrics = {
            'faithfulness': 0.85,
            'answer_relevancy': 0.90
            # Missing context_precision and context_recall
        }
        
        thresholds = {
            'min_faithfulness': 0.8,
            'min_answer_relevancy': 0.85,
            'min_context_precision': 0.8,
            'min_context_recall': 0.8
        }
        
        result = check_ragas_thresholds(ragas_metrics, thresholds)
        
        expected = {
            'min_faithfulness': True,
            'min_answer_relevancy': True,
            'min_context_precision': False,  # Missing metric = False
            'min_context_recall': False      # Missing metric = False
        }
        self.assertEqual(result, expected)
    
    def test_check_ragas_thresholds_empty_inputs(self):
        """Test threshold checking with empty inputs."""
        result = check_ragas_thresholds({}, {})
        self.assertEqual(result, {})
        
        result = check_ragas_thresholds({'faithfulness': 0.8}, {})
        self.assertEqual(result, {})
        
        result = check_ragas_thresholds({}, {'min_faithfulness': 0.8})
        self.assertEqual(result, {'min_faithfulness': False})


class TestRagasAdapterIntegration(unittest.TestCase):
    """Integration tests for Ragas adapter with environment settings."""
    
    def test_ragas_disabled_by_default(self):
        """Test that Ragas is disabled by default via environment."""
        # This test verifies the default behavior without actually running Ragas
        with patch.dict(os.environ, {}, clear=True):
            # Import settings to check default value
            from apps.settings import Settings
            settings = Settings()
            self.assertFalse(settings.RAGAS_ENABLED)
    
    def test_ragas_enabled_via_environment(self):
        """Test that Ragas can be enabled via environment variable."""
        with patch.dict(os.environ, {'RAGAS_ENABLED': 'true'}):
            from apps.settings import Settings
            settings = Settings()
            self.assertTrue(settings.RAGAS_ENABLED)


if __name__ == '__main__':
    unittest.main()
