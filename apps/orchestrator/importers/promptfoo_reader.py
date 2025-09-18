"""Promptfoo YAML reader for importing external test assets.

This module provides phase-1 support for reading Promptfoo test configurations
and converting them to internal test format. It supports basic variable expansion,
testMatrix resolution, and simple assertions (contains/equals).
"""

import logging
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass
import itertools

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class InternalTest:
    """Internal test representation for Promptfoo-imported tests."""
    suite: str
    name: str
    input: str  # Resolved prompt string
    expectations: List[Dict[str, Any]]  # List of assertions
    provider_hint: Optional[str] = None
    origin: str = "promptfoo"
    source: str = ""


def load_promptfoo_file(file_path: Path) -> Dict[str, Any]:
    """
    Load and parse a Promptfoo YAML file.
    
    Args:
        file_path: Path to the Promptfoo YAML file
        
    Returns:
        Parsed YAML content as dictionary
        
    Raises:
        FileNotFoundError: If file doesn't exist
        yaml.YAMLError: If YAML is malformed
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = yaml.safe_load(f)
            
        if not isinstance(content, dict):
            raise ValueError(f"Promptfoo file must contain a YAML dictionary, got {type(content)}")
            
        logger.info(f"Loaded Promptfoo file: {file_path}")
        return content
        
    except FileNotFoundError:
        logger.error(f"Promptfoo file not found: {file_path}")
        raise
    except yaml.YAMLError as e:
        logger.error(f"Invalid YAML in Promptfoo file {file_path}: {e}")
        raise
    except Exception as e:
        logger.error(f"Error loading Promptfoo file {file_path}: {e}")
        raise


def _resolve_variables(text: str, variables: Dict[str, Any]) -> str:
    """
    Resolve variable placeholders in text using simple string replacement.
    
    Args:
        text: Text containing {{variable}} placeholders
        variables: Dictionary of variable values
        
    Returns:
        Text with variables resolved
    """
    if not isinstance(text, str):
        return str(text)
        
    resolved = text
    for key, value in variables.items():
        placeholder = f"{{{{{key}}}}}"
        resolved = resolved.replace(placeholder, str(value))
        
    return resolved


def _expand_test_matrix(spec: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Expand testMatrix into individual test cases with variable combinations.
    
    Args:
        spec: Promptfoo specification dictionary
        
    Returns:
        List of expanded test cases with resolved variables
    """
    base_variables = spec.get('variables', {})
    test_matrix = spec.get('testMatrix', [])
    
    if not test_matrix:
        # No test matrix, return single case with base variables
        return [{'variables': base_variables}]
    
    expanded_cases = []
    
    for matrix_entry in test_matrix:
        if isinstance(matrix_entry, dict):
            # Matrix entry contains variable overrides
            case_variables = {**base_variables, **matrix_entry}
            expanded_cases.append({'variables': case_variables})
        else:
            logger.warning(f"Unsupported testMatrix entry type: {type(matrix_entry)}")
            
    return expanded_cases if expanded_cases else [{'variables': base_variables}]


def _extract_assertions(test_case: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract and normalize assertions from a test case.
    
    Args:
        test_case: Individual test case dictionary
        
    Returns:
        List of normalized assertion dictionaries
    """
    assertions = []
    
    # Handle 'assert' field (list or single assertion)
    assert_field = test_case.get('assert', [])
    if not isinstance(assert_field, list):
        assert_field = [assert_field]
        
    for assertion in assert_field:
        if isinstance(assertion, dict):
            # Extract assertion type and value
            assertion_type = assertion.get('type')
            assertion_value = assertion.get('value')
            
            if assertion_type in ['contains', 'equals']:
                assertions.append({
                    'type': assertion_type,
                    'value': assertion_value,
                    'supported': True
                })
            else:
                # Unsupported assertion - note but don't fail
                assertions.append({
                    'type': assertion_type or 'unknown',
                    'value': assertion_value,
                    'supported': False,
                    'note': f"Unsupported assertion type '{assertion_type}' in Promptfoo v1 reader"
                })
        elif isinstance(assertion, str):
            # Simple string assertion - treat as contains
            assertions.append({
                'type': 'contains',
                'value': assertion,
                'supported': True
            })
        else:
            logger.warning(f"Unsupported assertion format: {assertion}")
            
    return assertions


def to_internal_tests(
    spec: Dict[str, Any], 
    source_file: str = "",
    force_provider_from_yaml: bool = False
) -> List[InternalTest]:
    """
    Convert Promptfoo specification to internal test format.
    
    Args:
        spec: Parsed Promptfoo YAML specification
        source_file: Source filename for tracking
        force_provider_from_yaml: Whether to use provider from YAML vs orchestrator request
        
    Returns:
        List of InternalTest objects
    """
    internal_tests = []
    
    # Get prompts (required)
    prompts = spec.get('prompts', [])
    if not prompts:
        logger.warning(f"No prompts found in Promptfoo spec from {source_file}")
        return []
    
    # Expand test matrix to get all variable combinations
    expanded_cases = _expand_test_matrix(spec)
    
    # Get tests (optional - if not provided, create basic tests for each prompt)
    tests = spec.get('tests', [])
    if not tests:
        # Create basic test for each prompt/variable combination
        tests = [{}] * len(prompts)
    
    # Extract provider hint if requested
    provider_hint = None
    if force_provider_from_yaml:
        providers = spec.get('providers', [])
        if providers and isinstance(providers[0], (str, dict)):
            if isinstance(providers[0], str):
                provider_hint = providers[0]
            elif isinstance(providers[0], dict):
                provider_hint = providers[0].get('id') or providers[0].get('name')
    
    # Generate tests for each combination
    test_counter = 0
    for prompt_idx, prompt in enumerate(prompts):
        for case_idx, case in enumerate(expanded_cases):
            variables = case.get('variables', {})
            
            # Resolve prompt with variables
            if isinstance(prompt, str):
                resolved_prompt = _resolve_variables(prompt, variables)
            elif isinstance(prompt, dict):
                # Handle prompt object with content
                prompt_content = prompt.get('content', '') or prompt.get('text', '')
                resolved_prompt = _resolve_variables(str(prompt_content), variables)
            else:
                resolved_prompt = str(prompt)
            
            # Get corresponding test case (if available)
            test_case = tests[min(prompt_idx, len(tests) - 1)] if tests else {}
            
            # Extract assertions
            expectations = _extract_assertions(test_case)
            
            # Create test name
            test_name = (
                test_case.get('name') or 
                f"prompt_{prompt_idx + 1}_case_{case_idx + 1}"
            )
            
            # Add variable info to name if present
            if variables:
                var_summary = "_".join(f"{k}={v}" for k, v in list(variables.items())[:2])
                test_name = f"{test_name}_{var_summary}"
            
            internal_test = InternalTest(
                suite="promptfoo",
                name=test_name,
                input=resolved_prompt,
                expectations=expectations,
                provider_hint=provider_hint,
                origin="promptfoo",
                source=source_file
            )
            
            internal_tests.append(internal_test)
            test_counter += 1
    
    logger.info(f"Converted {len(internal_tests)} tests from Promptfoo spec in {source_file}")
    return internal_tests


def evaluate_promptfoo_assertions(
    actual_output: str, 
    expectations: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Evaluate Promptfoo assertions against actual output.
    
    Args:
        actual_output: The actual response from the LLM
        expectations: List of assertion dictionaries
        
    Returns:
        Evaluation result with pass/fail status and details
    """
    if not expectations:
        return {
            "passed": True,
            "details": "No assertions to evaluate"
        }
    
    results = []
    overall_passed = True
    
    for expectation in expectations:
        assertion_type = expectation.get('type')
        expected_value = expectation.get('value')
        supported = expectation.get('supported', True)
        
        if not supported:
            # Unsupported assertion - note but don't fail the test
            results.append({
                "assertion": assertion_type,
                "expected": expected_value,
                "actual": actual_output,
                "passed": True,  # Don't fail on unsupported
                "note": expectation.get('note', f"Unsupported assertion: {assertion_type}")
            })
            continue
        
        # Evaluate supported assertions
        passed = False
        note = None
        
        if assertion_type == 'contains':
            passed = str(expected_value) in actual_output
        elif assertion_type == 'equals':
            passed = str(expected_value) == actual_output.strip()
        else:
            # This shouldn't happen if supported=True, but handle gracefully
            passed = True
            note = f"Unknown supported assertion: {assertion_type}"
        
        results.append({
            "assertion": assertion_type,
            "expected": expected_value,
            "actual": actual_output,
            "passed": passed,
            "note": note
        })
        
        if not passed:
            overall_passed = False
    
    return {
        "passed": overall_passed,
        "assertion_results": results,
        "details": f"Evaluated {len(expectations)} assertions, {sum(1 for r in results if r['passed'])} passed"
    }
