"""Tests for Promptfoo reader module.

These tests ensure the Promptfoo YAML reader works correctly with deterministic behavior,
proper variable expansion, and assertion handling.
"""

import unittest
import tempfile
import yaml
from pathlib import Path
from typing import Dict, List, Any

from apps.orchestrator.importers.promptfoo_reader import (
    load_promptfoo_file, to_internal_tests, evaluate_promptfoo_assertions,
    _resolve_variables, _expand_test_matrix, _extract_assertions
)


class TestPromptfooReader(unittest.TestCase):
    """Test cases for Promptfoo reader functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        
    def _create_yaml_file(self, content: Dict[str, Any], filename: str = "test.yaml") -> Path:
        """Create a temporary YAML file with given content."""
        file_path = Path(self.temp_dir) / filename
        with open(file_path, 'w') as f:
            yaml.dump(content, f)
        return file_path
    
    def test_load_promptfoo_file_success(self):
        """Test successful loading of a valid Promptfoo YAML file."""
        content = {
            'prompts': ['Hello {{name}}'],
            'variables': {'name': 'World'},
            'tests': [{'assert': [{'type': 'contains', 'value': 'World'}]}]
        }
        
        file_path = self._create_yaml_file(content)
        result = load_promptfoo_file(file_path)
        
        self.assertEqual(result, content)
    
    def test_load_promptfoo_file_not_found(self):
        """Test loading a non-existent file raises FileNotFoundError."""
        non_existent_path = Path(self.temp_dir) / "nonexistent.yaml"
        
        with self.assertRaises(FileNotFoundError):
            load_promptfoo_file(non_existent_path)
    
    def test_load_promptfoo_file_invalid_yaml(self):
        """Test loading invalid YAML raises YAMLError."""
        file_path = Path(self.temp_dir) / "invalid.yaml"
        with open(file_path, 'w') as f:
            f.write("invalid: yaml: content: [")
        
        with self.assertRaises(yaml.YAMLError):
            load_promptfoo_file(file_path)
    
    def test_resolve_variables_basic(self):
        """Test basic variable resolution."""
        text = "Hello {{name}}, welcome to {{place}}!"
        variables = {'name': 'Alice', 'place': 'Wonderland'}
        
        result = _resolve_variables(text, variables)
        expected = "Hello Alice, welcome to Wonderland!"
        
        self.assertEqual(result, expected)
    
    def test_resolve_variables_missing_variable(self):
        """Test variable resolution with missing variables (should remain unchanged)."""
        text = "Hello {{name}}, welcome to {{missing}}!"
        variables = {'name': 'Alice'}
        
        result = _resolve_variables(text, variables)
        expected = "Hello Alice, welcome to {{missing}}!"
        
        self.assertEqual(result, expected)
    
    def test_resolve_variables_non_string_input(self):
        """Test variable resolution with non-string input."""
        from typing import cast, Any
        result = _resolve_variables(cast(Any, 123), {'name': 'Alice'})
        self.assertEqual(result, "123")
    
    def test_expand_test_matrix_no_matrix(self):
        """Test test matrix expansion when no testMatrix is provided."""
        spec = {
            'variables': {'name': 'World', 'greeting': 'Hello'}
        }
        
        result = _expand_test_matrix(spec)
        expected = [{'variables': {'name': 'World', 'greeting': 'Hello'}}]
        
        self.assertEqual(result, expected)
    
    def test_expand_test_matrix_with_overrides(self):
        """Test test matrix expansion with variable overrides."""
        spec = {
            'variables': {'name': 'World', 'greeting': 'Hello'},
            'testMatrix': [
                {'name': 'Alice'},
                {'name': 'Bob', 'greeting': 'Hi'}
            ]
        }
        
        result = _expand_test_matrix(spec)
        expected = [
            {'variables': {'name': 'Alice', 'greeting': 'Hello'}},
            {'variables': {'name': 'Bob', 'greeting': 'Hi'}}
        ]
        
        self.assertEqual(result, expected)
    
    def test_extract_assertions_list_format(self):
        """Test assertion extraction from list format."""
        test_case = {
            'assert': [
                {'type': 'contains', 'value': 'hello'},
                {'type': 'equals', 'value': 'exact match'},
                {'type': 'unsupported', 'value': 'test'}
            ]
        }
        
        result = _extract_assertions(test_case)
        
        self.assertEqual(len(result), 3)
        self.assertTrue(result[0]['supported'])
        self.assertEqual(result[0]['type'], 'contains')
        self.assertTrue(result[1]['supported'])
        self.assertEqual(result[1]['type'], 'equals')
        self.assertFalse(result[2]['supported'])
        self.assertEqual(result[2]['type'], 'unsupported')
    
    def test_extract_assertions_string_format(self):
        """Test assertion extraction from simple string format."""
        test_case = {
            'assert': 'hello world'
        }
        
        result = _extract_assertions(test_case)
        
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0]['supported'])
        self.assertEqual(result[0]['type'], 'contains')
        self.assertEqual(result[0]['value'], 'hello world')
    
    def test_to_internal_tests_basic(self):
        """Test conversion to internal tests with basic configuration."""
        spec = {
            'prompts': ['Hello {{name}}!'],
            'variables': {'name': 'World'},
            'tests': [{'assert': [{'type': 'contains', 'value': 'World'}]}]
        }
        
        result = to_internal_tests(spec, "test.yaml")
        
        self.assertEqual(len(result), 1)
        test = result[0]
        self.assertEqual(test.suite, "promptfoo")
        self.assertEqual(test.input, "Hello World!")
        self.assertEqual(test.origin, "promptfoo")
        self.assertEqual(test.source, "test.yaml")
        self.assertEqual(len(test.expectations), 1)
        self.assertTrue(test.expectations[0]['supported'])
    
    def test_to_internal_tests_with_test_matrix(self):
        """Test conversion with testMatrix expansion."""
        spec = {
            'prompts': ['Hello {{name}}!', 'Goodbye {{name}}!'],
            'variables': {'name': 'World'},
            'testMatrix': [
                {'name': 'Alice'},
                {'name': 'Bob'}
            ]
        }
        
        result = to_internal_tests(spec, "test.yaml")
        
        # Should have 2 prompts × 2 matrix entries = 4 tests
        self.assertEqual(len(result), 4)
        
        # Check that variables are properly resolved
        inputs = [test.input for test in result]
        self.assertIn("Hello Alice!", inputs)
        self.assertIn("Hello Bob!", inputs)
        self.assertIn("Goodbye Alice!", inputs)
        self.assertIn("Goodbye Bob!", inputs)
    
    def test_to_internal_tests_with_provider_hint(self):
        """Test conversion with provider hint extraction."""
        spec = {
            'prompts': ['Test prompt'],
            'providers': ['openai:gpt-4']
        }
        
        result = to_internal_tests(spec, "test.yaml", force_provider_from_yaml=True)
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].provider_hint, "openai:gpt-4")
    
    def test_to_internal_tests_no_prompts(self):
        """Test conversion with no prompts returns empty list."""
        spec = {
            'variables': {'name': 'World'}
        }
        
        result = to_internal_tests(spec, "test.yaml")
        
        self.assertEqual(len(result), 0)
    
    def test_evaluate_promptfoo_assertions_contains_pass(self):
        """Test Promptfoo assertion evaluation - contains assertion passes."""
        actual_output = "Hello world, this is a test response."
        expectations = [
            {'type': 'contains', 'value': 'world', 'supported': True}
        ]
        
        result = evaluate_promptfoo_assertions(actual_output, expectations)
        
        self.assertTrue(result['passed'])
        self.assertEqual(len(result['assertion_results']), 1)
        self.assertTrue(result['assertion_results'][0]['passed'])
    
    def test_evaluate_promptfoo_assertions_contains_fail(self):
        """Test Promptfoo assertion evaluation - contains assertion fails."""
        actual_output = "Hello there, this is a test response."
        expectations = [
            {'type': 'contains', 'value': 'world', 'supported': True}
        ]
        
        result = evaluate_promptfoo_assertions(actual_output, expectations)
        
        self.assertFalse(result['passed'])
        self.assertEqual(len(result['assertion_results']), 1)
        self.assertFalse(result['assertion_results'][0]['passed'])
    
    def test_evaluate_promptfoo_assertions_equals_pass(self):
        """Test Promptfoo assertion evaluation - equals assertion passes."""
        actual_output = "exact match"
        expectations = [
            {'type': 'equals', 'value': 'exact match', 'supported': True}
        ]
        
        result = evaluate_promptfoo_assertions(actual_output, expectations)
        
        self.assertTrue(result['passed'])
        self.assertTrue(result['assertion_results'][0]['passed'])
    
    def test_evaluate_promptfoo_assertions_equals_fail(self):
        """Test Promptfoo assertion evaluation - equals assertion fails."""
        actual_output = "not exact match"
        expectations = [
            {'type': 'equals', 'value': 'exact match', 'supported': True}
        ]
        
        result = evaluate_promptfoo_assertions(actual_output, expectations)
        
        self.assertFalse(result['passed'])
        self.assertFalse(result['assertion_results'][0]['passed'])
    
    def test_evaluate_promptfoo_assertions_unsupported(self):
        """Test Promptfoo assertion evaluation with unsupported assertion."""
        actual_output = "test response"
        expectations = [
            {'type': 'unsupported', 'value': 'test', 'supported': False, 'note': 'Not supported in v1'}
        ]
        
        result = evaluate_promptfoo_assertions(actual_output, expectations)
        
        # Should pass overall (unsupported assertions don't fail the test)
        self.assertTrue(result['passed'])
        self.assertTrue(result['assertion_results'][0]['passed'])
        self.assertIn('Not supported in v1', result['assertion_results'][0]['note'])
    
    def test_evaluate_promptfoo_assertions_mixed(self):
        """Test Promptfoo assertion evaluation with mixed pass/fail."""
        actual_output = "Hello world test"
        expectations = [
            {'type': 'contains', 'value': 'world', 'supported': True},  # Pass
            {'type': 'contains', 'value': 'missing', 'supported': True},  # Fail
            {'type': 'unsupported', 'value': 'test', 'supported': False}  # Pass (unsupported)
        ]
        
        result = evaluate_promptfoo_assertions(actual_output, expectations)
        
        # Should fail overall (one supported assertion failed)
        self.assertFalse(result['passed'])
        self.assertEqual(len(result['assertion_results']), 3)
        self.assertTrue(result['assertion_results'][0]['passed'])   # contains world
        self.assertFalse(result['assertion_results'][1]['passed'])  # contains missing
        self.assertTrue(result['assertion_results'][2]['passed'])   # unsupported
    
    def test_evaluate_promptfoo_assertions_no_expectations(self):
        """Test Promptfoo assertion evaluation with no expectations."""
        actual_output = "test response"
        expectations = []
        
        result = evaluate_promptfoo_assertions(actual_output, expectations)
        
        self.assertTrue(result['passed'])
        self.assertEqual(result['details'], "No assertions to evaluate")


class TestPromptfooIntegration(unittest.TestCase):
    """Integration tests for Promptfoo reader with realistic scenarios."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
    
    def _create_yaml_file(self, content: Dict[str, Any], filename: str = "test.yaml") -> Path:
        """Create a temporary YAML file with given content."""
        file_path = Path(self.temp_dir) / filename
        with open(file_path, 'w') as f:
            yaml.dump(content, f)
        return file_path
    
    def test_realistic_promptfoo_config(self):
        """Test with a realistic Promptfoo configuration."""
        content = {
            'prompts': [
                'Summarize this text: {{text}}',
                'Translate to {{language}}: {{text}}'
            ],
            'variables': {
                'text': 'Hello world',
                'language': 'Spanish'
            },
            'testMatrix': [
                {'text': 'The quick brown fox jumps over the lazy dog'},
                {'text': 'AI is transforming the world', 'language': 'French'}
            ],
            'tests': [
                {
                    'assert': [
                        {'type': 'contains', 'value': 'fox'},
                        {'type': 'equals', 'value': 'exact summary'}
                    ]
                }
            ]
        }
        
        file_path = self._create_yaml_file(content)
        spec = load_promptfoo_file(file_path)
        internal_tests = to_internal_tests(spec, file_path.name)
        
        # Should have 2 prompts × 2 matrix entries = 4 tests
        self.assertEqual(len(internal_tests), 4)
        
        # Check variable resolution
        inputs = [test.input for test in internal_tests]
        self.assertIn('Summarize this text: The quick brown fox jumps over the lazy dog', inputs)
        self.assertIn('Translate to French: AI is transforming the world', inputs)
        
        # Check assertions are properly extracted
        for test in internal_tests:
            self.assertEqual(len(test.expectations), 2)
            self.assertEqual(test.suite, "promptfoo")
            self.assertEqual(test.origin, "promptfoo")


if __name__ == '__main__':
    unittest.main()
