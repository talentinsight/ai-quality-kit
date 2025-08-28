"""Tests for suite aliasing and backward compatibility."""

import unittest
import warnings
from unittest.mock import patch, MagicMock
from apps.orchestrator.run_tests import TestRunner, OrchestratorRequest


class TestSuiteAliasing(unittest.TestCase):
    """Test suite aliasing functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.base_request = OrchestratorRequest(
            target_mode="api",
            api_base_url="http://test",
            suites=[],
            provider="mock",
            model="test-model"
        )
    
    def test_rag_quality_alias_to_rag_reliability_robustness(self):
        """Test that rag_quality is mapped to rag_reliability_robustness with deprecation warning."""
        request = self.base_request.copy()
        request.suites = ["rag_quality"]
        
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            runner = TestRunner(request)
            
            # Check that deprecation warning was issued
            self.assertEqual(len(w), 1)
            self.assertTrue(issubclass(w[0].category, DeprecationWarning))
            self.assertIn("rag_quality is deprecated", str(w[0].message))
            self.assertIn("rag_reliability_robustness", str(w[0].message))
    
    def test_rag_structure_eval_alias_to_rag_prompt_robustness(self):
        """Test that rag_structure_eval is mapped to rag_prompt_robustness."""
        request = self.base_request.copy()
        request.suites = ["rag_structure_eval"]
        
        runner = TestRunner(request)
        suite_data = runner.load_suites()
        
        # Should have rag_prompt_robustness in the results
        self.assertIn("rag_prompt_robustness", suite_data)
        self.assertNotIn("rag_structure_eval", suite_data)
    
    def test_rag_reliability_robustness_direct_usage(self):
        """Test that rag_reliability_robustness can be used directly without warnings."""
        request = self.base_request.copy()
        request.suites = ["rag_reliability_robustness"]
        
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            runner = TestRunner(request)
            
            # Should not issue any deprecation warnings
            deprecation_warnings = [warning for warning in w if issubclass(warning.category, DeprecationWarning)]
            self.assertEqual(len(deprecation_warnings), 0)
    
    def test_mixed_suites_with_aliases(self):
        """Test that mixed suite names work correctly."""
        request = self.base_request.copy()
        request.suites = ["rag_quality", "rag_reliability_robustness", "red_team"]
        
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            runner = TestRunner(request)
            suite_data = runner.load_suites()
            
            # Should have rag_reliability_robustness and red_team
            self.assertIn("rag_reliability_robustness", suite_data)
            self.assertIn("red_team", suite_data)
            
            # Should issue exactly one deprecation warning
            deprecation_warnings = [warning for warning in w if issubclass(warning.category, DeprecationWarning)]
            self.assertEqual(len(deprecation_warnings), 1)
    
    def test_deprecated_suites_tracking(self):
        """Test that deprecated suites are tracked correctly."""
        request = self.base_request.copy()
        request.suites = ["rag_quality", "gibberish"]
        
        runner = TestRunner(request)
        
        # Should track both deprecated suites
        self.assertIn("rag_quality", runner.deprecated_suites)
        self.assertIn("gibberish", runner.deprecated_suites)


if __name__ == '__main__':
    unittest.main()
