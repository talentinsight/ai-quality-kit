"""
Safety Details Report Generator.

Generates detailed Safety test results for JSON and XLSX reports.
"""

from typing import List, Dict, Any, Optional
from apps.orchestrator.suites.safety.schemas import SafetyResult


def generate_safety_details_data(
    safety_results: List[SafetyResult],
    selected_subtests: Optional[Dict[str, List[str]]] = None
) -> List[Dict[str, Any]]:
    """
    Generate Safety details data for reporting.
    
    Args:
        safety_results: List of safety test results
        selected_subtests: Optional dict of selected subtests by category
        
    Returns:
        List of dictionaries containing safety details data
    """
    if not safety_results:
        return []
    
    details_data = []
    
    for result in safety_results:
        # Basic result data
        row_data = {
            "id": result.id,
            "category": result.category,
            "subtype": result.subtype,
            "required": result.required,
            "passed": result.passed,
            "reason": result.reason,
            
            # Stage findings
            "input_blocked": result.stage_findings.input.blocked if result.stage_findings.input else False,
            "retrieved_dropped_count": len([r for r in result.stage_findings.retrieved if r.blocked]) if result.stage_findings.retrieved else 0,
            "output_blocked": result.stage_findings.output.blocked if result.stage_findings.output else False,
            
            # Labels and detection info
            "labels_joined": _get_all_labels(result),
            "unsupported_claims_count": result.unsupported_claims_count or 0,
            
            # Timing information
            "latency_input_ms": result.latency_input_ms or 0,
            "latency_retrieved_ms": result.latency_retrieved_ms or 0,
            "latency_output_ms": result.latency_output_ms or 0,
            
            # Evidence (masked for safety)
            "evidence_snippet": _mask_evidence(result.evidence_snippet) if result.evidence_snippet else "",
            
            # Selected subtests snapshot
            "selected_subtests_snapshot": _format_selected_subtests(selected_subtests) if selected_subtests else ""
        }
        
        details_data.append(row_data)
    
    return details_data


def _get_all_labels(result: SafetyResult) -> str:
    """Extract all labels from stage findings."""
    all_labels = []
    
    if result.stage_findings.input and result.stage_findings.input.labels:
        all_labels.extend(result.stage_findings.input.labels)
    
    if result.stage_findings.retrieved:
        for retrieved_result in result.stage_findings.retrieved:
            if retrieved_result.labels:
                all_labels.extend(retrieved_result.labels)
    
    if result.stage_findings.output and result.stage_findings.output.labels:
        all_labels.extend(result.stage_findings.output.labels)
    
    # Remove duplicates and join
    unique_labels = list(set(all_labels))
    return ", ".join(unique_labels)


def _mask_evidence(evidence: str) -> str:
    """Mask potentially harmful content in evidence snippets."""
    if not evidence:
        return ""
    
    # For safety, limit evidence length and mask potentially harmful content
    masked = evidence[:100]  # Limit to first 100 characters
    
    # Add masking indicators
    if len(evidence) > 100:
        masked += "... [TRUNCATED]"
    
    return masked


def _format_selected_subtests(selected_subtests: Dict[str, List[str]]) -> str:
    """Format selected subtests for display."""
    if not selected_subtests:
        return ""
    
    formatted_parts = []
    for category, subtypes in selected_subtests.items():
        if subtypes:
            formatted_parts.append(f"{category}: {', '.join(subtypes)}")
    
    return "; ".join(formatted_parts)


def generate_safety_summary(safety_results: List[SafetyResult]) -> Dict[str, Any]:
    """
    Generate Safety suite summary statistics.
    
    Args:
        safety_results: List of safety test results
        
    Returns:
        Dictionary with summary statistics
    """
    if not safety_results:
        return {
            "total_cases": 0,
            "passed_cases": 0,
            "failed_cases": 0,
            "pass_rate": 0.0,
            "required_cases": 0,
            "required_passed": 0,
            "categories": {},
            "three_point_stats": {},
            "avg_latency_ms": {}
        }
    
    total_cases = len(safety_results)
    passed_cases = sum(1 for r in safety_results if r.passed)
    failed_cases = total_cases - passed_cases
    required_cases = sum(1 for r in safety_results if r.required)
    required_passed = sum(1 for r in safety_results if r.required and r.passed)
    
    # Category breakdown
    categories = {}
    for result in safety_results:
        cat = result.category
        if cat not in categories:
            categories[cat] = {"total": 0, "passed": 0}
        categories[cat]["total"] += 1
        if result.passed:
            categories[cat]["passed"] += 1
    
    # Three-point moderation stats
    input_blocked = sum(1 for r in safety_results if r.stage_findings.input and r.stage_findings.input.blocked)
    retrieved_dropped = sum(len([rr for rr in r.stage_findings.retrieved if rr.blocked]) for r in safety_results if r.stage_findings.retrieved)
    output_blocked = sum(1 for r in safety_results if r.stage_findings.output and r.stage_findings.output.blocked)
    
    three_point_stats = {
        "input_blocked": input_blocked,
        "retrieved_dropped": retrieved_dropped,
        "output_blocked": output_blocked,
        "total_moderation_actions": input_blocked + retrieved_dropped + output_blocked
    }
    
    # Average latencies
    latencies = {"input": [], "retrieved": [], "output": []}
    for result in safety_results:
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
    
    # Unsupported claims aggregate
    total_unsupported_claims = sum(r.unsupported_claims_count or 0 for r in safety_results)
    
    return {
        "total_cases": total_cases,
        "passed_cases": passed_cases,
        "failed_cases": failed_cases,
        "pass_rate": passed_cases / total_cases,
        "required_cases": required_cases,
        "required_passed": required_passed,
        "categories": categories,
        "three_point_stats": three_point_stats,
        "avg_latency_ms": avg_latency_ms,
        "total_unsupported_claims": total_unsupported_claims
    }
