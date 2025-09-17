"""JSON report generation for orchestrator results."""

import json
from typing import Dict, List, Optional, Any
from apps.utils.pii_redaction import mask_text


def build_json(
    run_meta: Dict[str, Any],
    summary: Dict[str, Any],
    detailed_rows: List[Dict[str, Any]],
    api_rows: List[Dict[str, Any]],
    inputs_rows: List[Dict[str, Any]],
    adv_rows: Optional[List[Dict[str, Any]]] = None,
    coverage: Optional[Dict[str, Any]] = None,
    resilience_details: Optional[List[Dict[str, Any]]] = None,
    compliance_smoke_details: Optional[List[Dict[str, Any]]] = None,
    bias_smoke_details: Optional[List[Dict[str, Any]]] = None,
    logs: Optional[List[Dict[str, Any]]] = None,
    rag_reliability_robustness: Optional[Dict[str, Any]] = None,
    compare_data: Optional[Dict[str, Any]] = None,
    guardrails_data: Optional[Dict[str, Any]] = None,
    performance_metrics: Optional[Dict[str, Any]] = None,
    anonymize: bool = True
) -> Dict[str, Any]:
    """Build comprehensive JSON report from orchestrator data.
    
    Args:
        run_meta: Run metadata (run_id, timestamps, provider, etc.)
        summary: Summary statistics and aggregates
        detailed_rows: Per-test detailed results
        api_rows: API call details and headers
        inputs_rows: Test inputs and expected values
        adv_rows: Adversarial test details (optional)
        coverage: Coverage analysis (optional)
        resilience_details: Resilience test detail records (optional)
        compliance_smoke_details: Compliance smoke test detail records (optional)
        bias_smoke_details: Bias smoke test detail records (optional)
        anonymize: Whether to mask PII in text fields
        
    Returns:
        Complete JSON report dictionary
    """
    
    # Apply PII masking if requested
    if anonymize:
        detailed_rows = _mask_detailed_rows(detailed_rows)
        if adv_rows:
            adv_rows = _mask_adversarial_rows(adv_rows)
    
    # Build resilience section if data exists
    resilience_section = None
    if resilience_details:
        # Extract resilience summary from overall summary if present
        resilience_summary = summary.get("resilience", {})
        resilience_section = {
            "summary": resilience_summary,
            "details": resilience_details
        }
    
    # Build compliance_smoke section if data exists
    compliance_smoke_section = None
    if compliance_smoke_details:
        compliance_smoke_summary = summary.get("compliance_smoke", {})
        compliance_smoke_section = {
            "summary": compliance_smoke_summary,
            "details": compliance_smoke_details
        }
    
    # Build bias_smoke section if data exists
    bias_smoke_section = None
    if bias_smoke_details:
        bias_smoke_summary = summary.get("bias_smoke", {})
        bias_smoke_section = {
            "summary": bias_smoke_summary,
            "details": bias_smoke_details
        }
    
    # Build logs section if data exists
    logs_section = None
    if logs:
        logs_section = {
            "count": len(logs),
            "entries": logs
        }
    
    report = {
        "version": "2.0",
        "run": run_meta,
        "summary": summary,
        "detailed": detailed_rows,
        "api_details": api_rows,
        "inputs_expected": inputs_rows,
        "adversarial": adv_rows or [],  # Keep for backwards compatibility
        "adversarial_details": adv_rows or [],  # New structured format
        "coverage": coverage or {}
    }
    
    # Add new sections if present
    if resilience_section:
        report["resilience"] = resilience_section
    if compliance_smoke_section:
        report["compliance_smoke"] = compliance_smoke_section
    if bias_smoke_section:
        report["bias_smoke"] = bias_smoke_section
    if logs_section:
        report["logs"] = logs_section
    
    # Add RAG Reliability & Robustness section if present
    if rag_reliability_robustness:
        report["rag_reliability_robustness"] = rag_reliability_robustness
    
    # Add Compare Mode section if present
    if compare_data:
        report["compare"] = compare_data
    
    # Add Guardrails section if present (Reports v2)
    if guardrails_data:
        report["guardrails"] = {
            "mode": guardrails_data.get("mode", "advisory"),
            "decision": guardrails_data.get("decision", "pass"),
            "failing_categories": guardrails_data.get("failing_categories", []),
            "reused_fingerprints": guardrails_data.get("reused_fingerprints", []),
            "provider_availability": guardrails_data.get("provider_availability", {}),
            "signals": guardrails_data.get("signals", []),
            "run_manifest": guardrails_data.get("run_manifest", {})
        }
    
    # Add Performance Metrics section if present (Reports v2)
    if performance_metrics:
        report["performance"] = {
            "cold_start_ms": performance_metrics.get("cold_start_ms", 0),
            "warm_p95_ms": performance_metrics.get("warm_p95_ms", 0),
            "throughput_rps": performance_metrics.get("throughput_rps", 0),
            "memory_usage_mb": performance_metrics.get("memory_usage_mb", 0),
            "estimator_vs_actuals": performance_metrics.get("estimator_vs_actuals", {}),
            "dedupe_savings": performance_metrics.get("dedupe_savings", {})
        }
    
    return report


def _mask_detailed_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Apply PII masking to detailed rows."""
    masked_rows = []
    for row in rows:
        masked_row = row.copy()
        # Mask text fields that might contain PII
        for field in ["query", "answer", "context", "prompt", "response", "notes"]:
            if field in masked_row and masked_row[field]:
                masked_row[field] = mask_text(str(masked_row[field]))
        masked_rows.append(masked_row)
    return masked_rows


def _mask_adversarial_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Apply PII masking to adversarial rows."""
    masked_rows = []
    for row in rows:
        masked_row = row.copy()
        # Mask attack prompts and responses
        for field in ["attack_prompt", "response", "original_prompt", "modified_prompt"]:
            if field in masked_row and masked_row[field]:
                masked_row[field] = mask_text(str(masked_row[field]))
        masked_rows.append(masked_row)
    return masked_rows


def _mask_compare_data(compare_data: Dict[str, Any]) -> Dict[str, Any]:
    """Apply PII masking to compare data."""
    masked_data = compare_data.copy()
    # Mask any text fields in compare data
    for key, value in masked_data.items():
        if isinstance(value, str):
            masked_data[key] = mask_text(value)
        elif isinstance(value, list):
            masked_data[key] = [mask_text(str(item)) if isinstance(item, str) else item for item in value]
    return masked_data


def _mask_detailed_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Apply PII masking to detailed test rows."""
    masked_rows = []
    for row in rows:
        masked_row = row.copy()
        
        # Mask text fields that may contain PII
        if "query_masked" in masked_row:
            masked_row["query_masked"] = mask_text(masked_row["query_masked"]) or ""
        if "answer_masked" in masked_row:
            masked_row["answer_masked"] = mask_text(masked_row["answer_masked"]) or ""
        if "context_snippet" in masked_row:
            masked_row["context_snippet"] = mask_text(masked_row["context_snippet"]) or ""
            
        masked_rows.append(masked_row)
    
    return masked_rows


def _mask_adversarial_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Apply PII masking to adversarial test rows."""
    masked_rows = []
    for row in rows:
        masked_row = row.copy()
        
        # Mask prompt variants that may contain sensitive content
        if "prompt_variant_masked" in masked_row:
            masked_row["prompt_variant_masked"] = mask_text(masked_row["prompt_variant_masked"]) or ""
            
        masked_rows.append(masked_row)
    
    return masked_rows


def _mask_compare_data(compare_data: Dict[str, Any]) -> Dict[str, Any]:
    """Apply PII masking to compare mode data."""
    masked_data = compare_data.copy()
    
    # Mask cases if present
    if "cases" in masked_data:
        masked_cases = []
        for case in masked_data["cases"]:
            masked_case = case.copy()
            
            # Mask question and answer text fields
            if "question" in masked_case:
                masked_case["question"] = mask_text(masked_case["question"]) or ""
            if "primary_answer" in masked_case:
                masked_case["primary_answer"] = mask_text(masked_case["primary_answer"]) or ""
            if "baseline_answer" in masked_case:
                masked_case["baseline_answer"] = mask_text(masked_case["baseline_answer"]) or ""
            
            masked_cases.append(masked_case)
        
        masked_data["cases"] = masked_cases
    
    return masked_data
