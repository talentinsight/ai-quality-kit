"""
Safety Test Runner.

Executes safety test cases with three-point moderation flow:
1. INPUT stage: moderate user input
2. RETRIEVED stage: moderate retrieved passages
3. OUTPUT stage: moderate generated output
"""

import time
import logging
from typing import List, Dict, Any, Optional
from .schemas import (
    SafetyCase, SafetyResult, SafetyStageFindings, 
    NormalizedSafety, SafetyConfig
)
from .moderation import moderate_input, moderate_retrieved, moderate_output
from .misinformation import evaluate_misinformation_case
from .loader import parse_safety_content
from apps.config.safety import safety_config

logger = logging.getLogger(__name__)


def run_safety_suite(
    dataset_content: Optional[str] = None,
    config_overrides: Optional[Dict[str, Any]] = None,
    client_callable: Optional[Any] = None
) -> List[SafetyResult]:
    """
    Run the complete Safety suite.
    
    Args:
        dataset_content: Optional safety dataset content (YAML/JSON/JSONL)
        config_overrides: Optional configuration overrides
        client_callable: Optional client for LLM calls
        
    Returns:
        List of SafetyResult objects
    """
    if not safety_config.ENABLED:
        logger.info("Safety suite is disabled")
        return []
    
    # Load dataset if provided
    if dataset_content:
        try:
            normalized_safety = parse_safety_content(dataset_content)
            logger.info(f"Loaded {len(normalized_safety.cases)} safety cases from dataset")
        except Exception as e:
            logger.error(f"Failed to parse safety dataset: {e}")
            return []
    else:
        # Use built-in heuristics (legacy mode)
        logger.info("No safety dataset provided, using built-in heuristics")
        return _run_legacy_safety_checks(client_callable)
    
    # Apply subtest filtering if specified
    if config_overrides and 'subtests' in config_overrides:
        normalized_safety.cases = _filter_cases_by_subtests(
            normalized_safety.cases, 
            config_overrides['subtests']
        )
        logger.info(f"Filtered to {len(normalized_safety.cases)} cases based on subtests")
    
    # Execute safety cases
    results = []
    for case in normalized_safety.cases:
        try:
            result = _execute_safety_case(case, client_callable)
            results.append(result)
        except Exception as e:
            logger.error(f"Failed to execute safety case {case.id}: {e}")
            # Create a failed result
            results.append(SafetyResult(
                id=case.id,
                category=case.category.value,
                subtype=case.subtype,
                required=case.required,
                passed=False,
                reason=f"Execution failed: {str(e)}"
            ))
    
    logger.info(f"Completed safety suite: {len(results)} cases executed")
    return results


def _execute_safety_case(
    case: SafetyCase, 
    client_callable: Optional[Any] = None
) -> SafetyResult:
    """
    Execute a single safety test case with three-point moderation.
    
    Args:
        case: Safety test case to execute
        client_callable: Optional client for LLM calls
        
    Returns:
        SafetyResult with execution results
    """
    logger.debug(f"Executing safety case: {case.id}")
    
    stage_findings = SafetyStageFindings()
    timing = {}
    
    # Stage 1: INPUT moderation
    if case.inputs.user:
        start_time = time.time()
        stage_findings.input = moderate_input(case.inputs.user)
        timing['input_ms'] = (time.time() - start_time) * 1000
        logger.debug(f"INPUT stage for {case.id}: blocked={stage_findings.input.blocked}")
    
    # Stage 2: RETRIEVED moderation
    retrieved_passages = case.inputs.retrieved or []
    if retrieved_passages:
        start_time = time.time()
        stage_findings.retrieved = moderate_retrieved(retrieved_passages)
        timing['retrieved_ms'] = (time.time() - start_time) * 1000
        
        # Filter out dropped passages for LLM call
        allowed_passages = []
        for i, result in enumerate(stage_findings.retrieved):
            if not result.blocked:
                allowed_passages.append(retrieved_passages[i])
            elif result.redacted_text:
                allowed_passages.append(result.redacted_text)
        
        logger.debug(f"RETRIEVED stage for {case.id}: {len(allowed_passages)}/{len(retrieved_passages)} passages allowed")
    else:
        allowed_passages = []
    
    # Stage 3: OUTPUT moderation (if prompt provided)
    generated_output = None
    if case.inputs.prompt and client_callable:
        try:
            start_time = time.time()
            
            # Make LLM call with filtered passages
            if allowed_passages:
                # Inject allowed passages into prompt context
                context = "\n".join(allowed_passages)
                full_prompt = f"Context: {context}\n\nQuery: {case.inputs.prompt}"
            else:
                full_prompt = case.inputs.prompt
            
            # Call the LLM (this is a placeholder - actual implementation depends on client)
            generated_output = _call_llm(full_prompt, client_callable)
            
            # Moderate the output
            stage_findings.output = moderate_output(generated_output)
            timing['output_ms'] = (time.time() - start_time) * 1000
            
            logger.debug(f"OUTPUT stage for {case.id}: blocked={stage_findings.output.blocked}")
            
        except Exception as e:
            logger.error(f"Failed to generate/moderate output for {case.id}: {e}")
            timing['output_ms'] = 0
    
    # Evaluate success based on case criteria
    evaluation_result = _evaluate_case_success(case, stage_findings, generated_output, retrieved_passages)
    
    return SafetyResult(
        id=case.id,
        category=case.category.value,
        subtype=case.subtype,
        required=case.required,
        passed=evaluation_result['passed'],
        reason=evaluation_result['reason'],
        stage_findings=stage_findings,
        unsupported_claims_count=evaluation_result.get('unsupported_claims_count'),
        evidence_snippet=evaluation_result.get('evidence_snippet'),
        latency_input_ms=timing.get('input_ms'),
        latency_retrieved_ms=timing.get('retrieved_ms'),
        latency_output_ms=timing.get('output_ms')
    )


def _evaluate_case_success(
    case: SafetyCase,
    stage_findings: SafetyStageFindings,
    generated_output: Optional[str],
    retrieved_passages: List[str]
) -> Dict[str, Any]:
    """
    Evaluate if a safety case passed based on its success criteria.
    
    Args:
        case: The safety test case
        stage_findings: Results from moderation stages
        generated_output: Generated output text (if any)
        retrieved_passages: Original retrieved passages
        
    Returns:
        Dictionary with evaluation results
    """
    if case.category.value == "misinformation" and case.success and case.success.misinfo:
        # Special handling for misinformation cases
        if generated_output:
            misinfo_result = evaluate_misinformation_case(
                generated_output, retrieved_passages, case.success.misinfo
            )
            return {
                'passed': misinfo_result['passed'],
                'reason': '; '.join(misinfo_result['reasons']) if misinfo_result['reasons'] else 'Misinformation check passed',
                'unsupported_claims_count': misinfo_result['unsupported_count'],
                'evidence_snippet': str(misinfo_result['evidence_map']) if misinfo_result['evidence_map'] else None
            }
        else:
            return {
                'passed': False,
                'reason': 'No output generated for misinformation evaluation'
            }
    
    # Standard safety evaluation
    success_criteria = case.success or SafetySuccessCriteria()
    
    # Check if harmful content was properly flagged
    all_labels = []
    blocked_stages = []
    
    if stage_findings.input and stage_findings.input.blocked:
        all_labels.extend(stage_findings.input.labels)
        blocked_stages.append("input")
    
    if stage_findings.retrieved:
        for result in stage_findings.retrieved:
            if result.blocked:
                all_labels.extend(result.labels)
                blocked_stages.append("retrieved")
    
    if stage_findings.output and stage_findings.output.blocked:
        all_labels.extend(stage_findings.output.labels)
        blocked_stages.append("output")
    
    # Check must_flag_any criteria
    if success_criteria.must_flag_any:
        found_required_flags = False
        for required_flag in success_criteria.must_flag_any:
            if any(required_flag.lower() in label.lower() for label in all_labels):
                found_required_flags = True
                break
        
        if not found_required_flags:
            return {
                'passed': False,
                'reason': f'Required flags not found: {success_criteria.must_flag_any}'
            }
    
    # Check must_not_flag_any criteria (overblocking)
    if success_criteria.must_not_flag_any:
        for forbidden_flag in success_criteria.must_not_flag_any:
            if any(forbidden_flag.lower() in label.lower() for label in all_labels):
                return {
                    'passed': False,
                    'reason': f'Overblocking detected: found forbidden flag "{forbidden_flag}"'
                }
    
    # Check policy_labels criteria
    if success_criteria.policy_labels:
        expected_labels = set(label.lower() for label in success_criteria.policy_labels)
        found_labels = set(label.lower() for label in all_labels)
        
        if not expected_labels.intersection(found_labels):
            return {
                'passed': False,
                'reason': f'Expected policy labels not found: {success_criteria.policy_labels}'
            }
    
    # If we get here, the case passed
    if blocked_stages:
        reason = f'Safety engaged at {", ".join(blocked_stages)} stage(s)'
    else:
        reason = 'No harmful content detected (as expected)'
    
    return {
        'passed': True,
        'reason': reason
    }


def _filter_cases_by_subtests(
    cases: List[SafetyCase], 
    subtests: Dict[str, List[str]]
) -> List[SafetyCase]:
    """
    Filter safety cases based on selected subtests.
    
    Args:
        cases: List of safety cases
        subtests: Dictionary mapping categories to selected subtypes
        
    Returns:
        Filtered list of safety cases
    """
    filtered_cases = []
    
    for case in cases:
        category = case.category.value
        subtype = case.subtype
        
        # Include case if its category/subtype is selected
        if category in subtests and subtype in subtests[category]:
            filtered_cases.append(case)
    
    return filtered_cases


def _call_llm(prompt: str, client_callable: Any) -> str:
    """
    Call the LLM with the given prompt.
    
    Args:
        prompt: Prompt to send to LLM
        client_callable: Client callable for LLM
        
    Returns:
        Generated response
    """
    if not client_callable:
        # Return a placeholder response for testing
        return "This is a placeholder response for safety testing."
    
    try:
        # This is a placeholder - actual implementation depends on client interface
        response = client_callable(prompt)
        return str(response)
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        return f"Error: LLM call failed - {str(e)}"


def _run_legacy_safety_checks(client_callable: Optional[Any] = None) -> List[SafetyResult]:
    """
    Run legacy safety checks when no dataset is provided.
    
    Args:
        client_callable: Optional client for LLM calls
        
    Returns:
        List of SafetyResult objects from legacy checks
    """
    # Placeholder for legacy safety checks
    # This would implement the existing safety logic
    logger.info("Running legacy safety checks")
    
    # Return empty list for now - existing safety logic would be preserved
    return []


def get_safety_summary(results: List[SafetyResult]) -> Dict[str, Any]:
    """
    Generate summary statistics from safety results.
    
    Args:
        results: List of safety results
        
    Returns:
        Dictionary with summary statistics
    """
    if not results:
        return {
            "total_cases": 0,
            "passed_cases": 0,
            "failed_cases": 0,
            "pass_rate": 0.0,
            "required_cases": 0,
            "required_passed": 0,
            "categories": {},
            "avg_latency_ms": {}
        }
    
    total_cases = len(results)
    passed_cases = sum(1 for r in results if r.passed)
    failed_cases = total_cases - passed_cases
    required_cases = sum(1 for r in results if r.required)
    required_passed = sum(1 for r in results if r.required and r.passed)
    
    # Category breakdown
    categories = {}
    for result in results:
        cat = result.category
        if cat not in categories:
            categories[cat] = {"total": 0, "passed": 0}
        categories[cat]["total"] += 1
        if result.passed:
            categories[cat]["passed"] += 1
    
    # Average latencies
    latencies = {"input": [], "retrieved": [], "output": []}
    for result in results:
        if result.latency_input_ms is not None:
            latencies["input"].append(result.latency_input_ms)
        if result.latency_retrieved_ms is not None:
            latencies["retrieved"].append(result.latency_retrieved_ms)
        if result.latency_output_ms is not None:
            latencies["output"].append(result.latency_output_ms)
    
    avg_latency_ms = {}
    for stage, times in latencies.items():
        if times:
            avg_latency_ms[stage] = sum(times) / len(times)
    
    return {
        "total_cases": total_cases,
        "passed_cases": passed_cases,
        "failed_cases": failed_cases,
        "pass_rate": passed_cases / total_cases,
        "required_cases": required_cases,
        "required_passed": required_passed,
        "categories": categories,
        "avg_latency_ms": avg_latency_ms
    }
