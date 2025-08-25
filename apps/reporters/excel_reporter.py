"""Excel report generation for orchestrator results."""

import json
from pathlib import Path
from typing import Dict, List, Any, cast
from openpyxl import Workbook
from openpyxl.worksheet.worksheet import Worksheet
from openpyxl.styles import Font, Alignment
from openpyxl.utils import get_column_letter


def write_excel(path: str, data: Dict[str, Any]) -> None:
    """Write comprehensive Excel report from JSON data.
    
    Args:
        path: Output Excel file path
        data: JSON report data from build_json()
    """
    wb = Workbook()
    
    # Remove default sheet
    if "Sheet" in wb.sheetnames:
        wb.remove(wb["Sheet"])
    
    # Create sheets in order
    _create_summary_sheet(wb, data)
    _create_detailed_sheet(wb, data)
    _create_api_details_sheet(wb, data)
    _create_inputs_expected_sheet(wb, data)
    
    # Optional sheets for red team results
    if data.get("adversarial_details") and len(data["adversarial_details"]) > 0:
        _create_adversarial_sheet(wb, data)
    
    if data.get("coverage") and data["coverage"]:
        _create_coverage_sheet(wb, data)
    
    # Optional sheet for resilience results
    if data.get("resilience") and data["resilience"].get("details"):
        _create_resilience_details_sheet(wb, data)
    
    # Optional sheets for new smoke suites
    if data.get("compliance_smoke") and data["compliance_smoke"].get("details"):
        _create_compliance_details_sheet(wb, data)
    
    if data.get("bias_smoke") and data["bias_smoke"].get("details"):
        _create_bias_details_sheet(wb, data)
    
    # Save workbook
    wb.save(path)


def _create_summary_sheet(wb: Workbook, data: Dict[str, Any]) -> None:
    """Create Summary sheet with run overview."""
    ws = cast(Worksheet, wb.create_sheet("Summary", 0))
    
    headers = [
        "run_id", "started_at", "finished_at", "suites", "total_tests", 
        "pass_rate", "faithfulness_avg", "context_recall_avg", 
        "attack_success_rate", "warm_p95_ms", "provider", "model"
    ]
    
    # Add resilience headers if resilience data exists
    if data.get("resilience") and data["resilience"].get("summary"):
        headers.extend([
            "resilience_samples", "resilience_success_rate", "resilience_timeouts",
            "resilience_5xx", "resilience_429", "resilience_circuit_open", "resilience_p50_ms", "resilience_p95_ms"
        ])
    
    # Add compliance_smoke headers if data exists
    if data.get("compliance_smoke") and data["compliance_smoke"].get("summary"):
        headers.extend([
            "compliance_cases_scanned", "compliance_pii_hits", "compliance_rbac_checks", 
            "compliance_rbac_violations", "compliance_pass"
        ])
    
    # Add bias_smoke headers if data exists
    if data.get("bias_smoke") and data["bias_smoke"].get("summary"):
        headers.extend([
            "bias_pairs", "bias_metric", "bias_fails", "bias_fail_ratio", "bias_pass"
        ])
    
    # Add dataset metadata headers (additive)
    summary = data.get("summary", {})
    if summary.get("dataset_source"):
        headers.extend([
            "dataset_source", "dataset_version", "estimated_tests"
        ])
    
    # Write headers
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = Font(bold=True)  # type: ignore
        ws.column_dimensions[get_column_letter(col)].width = 16
    
    # Write data row
    run_meta = data.get("run", {})
    summary = data.get("summary", {})
    
    row_data = [
        run_meta.get("run_id", ""),
        run_meta.get("started_at", ""),
        run_meta.get("finished_at", ""),
        ",".join(run_meta.get("suites", [])),
        summary.get("overall", {}).get("total_tests", 0),
        summary.get("overall", {}).get("pass_rate", 0.0),
        summary.get("rag_quality", {}).get("avg_faithfulness", 0.0),
        summary.get("rag_quality", {}).get("avg_context_recall", 0.0),
        summary.get("safety", {}).get("attack_success_rate", 0.0),
        summary.get("performance", {}).get("p95_latency_ms", 0),
        run_meta.get("provider", ""),
        run_meta.get("model", "")
    ]
    
    # Add resilience data if available
    if data.get("resilience") and data["resilience"].get("summary"):
        resilience_summary = data["resilience"]["summary"]
        row_data.extend([
            resilience_summary.get("samples", 0),
            resilience_summary.get("success_rate", 0.0),
            resilience_summary.get("timeouts", 0),
            resilience_summary.get("upstream_5xx", 0),
            resilience_summary.get("upstream_429", 0),
            resilience_summary.get("circuit_open_events", 0),
            resilience_summary.get("p50_ms", 0),
            resilience_summary.get("p95_ms", 0)
        ])
    
    # Add compliance_smoke data if available
    if data.get("compliance_smoke") and data["compliance_smoke"].get("summary"):
        compliance_summary = data["compliance_smoke"]["summary"]
        row_data.extend([
            compliance_summary.get("cases_scanned", 0),
            compliance_summary.get("pii_hits", 0),
            compliance_summary.get("rbac_checks", 0),
            compliance_summary.get("rbac_violations", 0),
            compliance_summary.get("pass", False)
        ])
    
    # Add bias_smoke data if available
    if data.get("bias_smoke") and data["bias_smoke"].get("summary"):
        bias_summary = data["bias_smoke"]["summary"]
        row_data.extend([
            bias_summary.get("pairs", 0),
            bias_summary.get("metric", "unknown"),
            bias_summary.get("fails", 0),
            bias_summary.get("fail_ratio", 0.0),
            bias_summary.get("pass", False)
        ])
    
    # Add dataset metadata if available (additive)
    summary = data.get("summary", {})
    if summary.get("dataset_source"):
        row_data.extend([
            summary.get("dataset_source", "unknown"),
            summary.get("dataset_version", "n/a"),
            summary.get("estimated_tests", 0)
        ])
    
    for col, value in enumerate(row_data, 1):
        ws.cell(row=2, column=col, value=value)
    
    # Add deprecation note if applicable
    if summary.get("_deprecated_note"):
        ws.cell(row=4, column=1, value="Note:")
        ws.cell(row=4, column=2, value=summary["_deprecated_note"])
        ws.cell(row=4, column=1).font = Font(bold=True)
    
    # Freeze panes and format
    ws.freeze_panes = "A2"


def _create_detailed_sheet(wb: Workbook, data: Dict[str, Any]) -> None:
    """Create Detailed sheet with per-test results."""
    ws = cast(Worksheet, wb.create_sheet("Detailed"))
    
    headers = [
        "suite", "test_id", "provider", "model", "query_masked", 
        "answer_masked", "context_ids", "metrics_json", "pass", 
        "latency_ms", "timestamp"
    ]
    
    # Write headers with styling
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = Font(bold=True)
        cell.alignment = Alignment(wrap_text=True)
        
        # Set column widths
        if header in ["query_masked", "answer_masked"]:
            ws.column_dimensions[get_column_letter(col)].width = 40  # type: ignore
        elif header in ["metrics_json", "context_ids"]:
            ws.column_dimensions[get_column_letter(col)].width = 30  # type: ignore
        else:
            ws.column_dimensions[get_column_letter(col)].width = 16
    
    # Write data rows
    detailed_rows = data.get("detailed", [])
    for row_idx, row_data in enumerate(detailed_rows, 2):
        values = [
            row_data.get("suite", ""),
            row_data.get("test_id", ""),
            row_data.get("provider", ""),
            row_data.get("model", ""),
            row_data.get("query_masked", ""),
            row_data.get("answer_masked", ""),
            ",".join(row_data.get("context_ids", [])),
            json.dumps(row_data.get("metrics_json", {})) if row_data.get("metrics_json") else "",
            row_data.get("pass", False),
            row_data.get("latency_ms", 0),
            row_data.get("timestamp", "")
        ]
        
        for col, value in enumerate(values, 1):
            cell = ws.cell(row=row_idx, column=col, value=value)
            if col in [5, 6]:  # query_masked, answer_masked
                cell.alignment = Alignment(wrap_text=True)  # type: ignore
    
    ws.freeze_panes = "A2"


def _create_api_details_sheet(wb: Workbook, data: Dict[str, Any]) -> None:
    """Create API_Details sheet with API call information."""
    ws = cast(Worksheet, wb.create_sheet("API_Details"))
    
    headers = [
        "suite", "test_id", "endpoint", "status_code", "x_source", 
        "x_perf_phase", "x_latency_ms", "request_id", "timestamp"
    ]
    
    # Write headers
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = Font(bold=True)  # type: ignore
        ws.column_dimensions[get_column_letter(col)].width = 16
    
    # Write data rows
    api_rows = data.get("api_details", [])
    for row_idx, row_data in enumerate(api_rows, 2):
        values = [
            row_data.get("suite", ""),
            row_data.get("test_id", ""),
            row_data.get("endpoint", ""),
            row_data.get("status_code", ""),
            row_data.get("x_source", ""),
            row_data.get("x_perf_phase", ""),
            row_data.get("x_latency_ms", ""),
            row_data.get("request_id", ""),
            row_data.get("timestamp", "")
        ]
        
        for col, value in enumerate(values, 1):
            ws.cell(row=row_idx, column=col, value=value)  # type: ignore
    
    ws.freeze_panes = "A2"


def _create_inputs_expected_sheet(wb: Workbook, data: Dict[str, Any]) -> None:
    """Create Inputs_And_Expected sheet with test configuration."""
    ws = cast(Worksheet, wb.create_sheet("Inputs_And_Expected"))
    
    headers = [
        "suite", "test_id", "target_mode", "top_k", "options_json", 
        "thresholds_json", "expected_json", "notes"
    ]
    
    # Write headers
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = Font(bold=True)
        cell.alignment = Alignment(wrap_text=True)
        
        # Set column widths for JSON columns
        if "_json" in header:
            ws.column_dimensions[get_column_letter(col)].width = 30  # type: ignore
        else:
            ws.column_dimensions[get_column_letter(col)].width = 16
    
    # Write data rows
    inputs_rows = data.get("inputs_expected", [])
    for row_idx, row_data in enumerate(inputs_rows, 2):
        values = [
            row_data.get("suite", ""),
            row_data.get("test_id", ""),
            row_data.get("target_mode", ""),
            row_data.get("top_k", ""),
            json.dumps(row_data.get("options_json", {})) if row_data.get("options_json") else "",
            json.dumps(row_data.get("thresholds_json", {})) if row_data.get("thresholds_json") else "",
            json.dumps(row_data.get("expected_json", {})) if row_data.get("expected_json") else "",
            row_data.get("notes", "")
        ]
        
        for col, value in enumerate(values, 1):
            cell = ws.cell(row=row_idx, column=col, value=value)
            if "_json" in headers[col-1]:
                cell.alignment = Alignment(wrap_text=True)  # type: ignore
    
    ws.freeze_panes = "A2"


def _create_adversarial_sheet(wb: Workbook, data: Dict[str, Any]) -> None:
    """Create Adversarial_Details sheet for red team results."""
    ws = cast(Worksheet, wb.create_sheet("Adversarial_Details"))
    
    # Required column order as specified
    headers = [
        "run_id", "timestamp", "suite", "provider", "model", "request_id", 
        "attack_id", "attack_text", "response_snippet", "safety_flags", "blocked", "notes"
    ]
    
    # Write headers with styling
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = Font(bold=True)
        cell.alignment = Alignment(wrap_text=True)
    
    # Auto-size columns based on content type
    for col, header in enumerate(headers, 1):
        if header in ["attack_text", "response_snippet"]:
            ws.column_dimensions[get_column_letter(col)].width = 40  # type: ignore
        elif header in ["safety_flags", "notes"]:
            ws.column_dimensions[get_column_letter(col)].width = 25  # type: ignore
        else:
            ws.column_dimensions[get_column_letter(col)].width = 16
    
    # Write data rows
    adv_rows = data.get("adversarial_details", [])
    for row_idx, row_data in enumerate(adv_rows, 2):
        values = [
            row_data.get("run_id", ""),
            row_data.get("timestamp", ""),
            row_data.get("suite", ""),
            row_data.get("provider", ""),
            row_data.get("model", ""),
            row_data.get("request_id", ""),
            row_data.get("attack_id", ""),
            row_data.get("attack_text", ""),
            row_data.get("response_snippet", ""),
            json.dumps(row_data.get("safety_flags", [])) if row_data.get("safety_flags") else "",
            row_data.get("blocked", False),
            row_data.get("notes", "")
        ]
        
        for col, value in enumerate(values, 1):
            cell = ws.cell(row=row_idx, column=col, value=value)
            # Apply text wrapping for long content fields
            if headers[col-1] in ["attack_text", "response_snippet", "notes"]:
                cell.alignment = Alignment(wrap_text=True)  # type: ignore
    
    ws.freeze_panes = "A2"


def _create_coverage_sheet(wb: Workbook, data: Dict[str, Any]) -> None:
    """Create Coverage sheet for test coverage analysis."""
    ws = cast(Worksheet, wb.create_sheet("Coverage"))
    
    # Required column order as specified
    headers = [
        "module", "stmts", "miss", "branch", "brpart", "cover_percent", "total_lines"
    ]
    
    # Write headers with styling
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = Font(bold=True)
        cell.alignment = Alignment(wrap_text=True)
    
    # Auto-size columns
    for col, header in enumerate(headers, 1):
        if header == "module":
            ws.column_dimensions[get_column_letter(col)].width = 30  # type: ignore
        else:
            ws.column_dimensions[get_column_letter(col)].width = 12  # type: ignore
    
    # Write data rows from coverage modules
    coverage = data.get("coverage", {})
    modules = coverage.get("modules", [])
    
    for row_idx, module_data in enumerate(modules, 2):
        values = [
            module_data.get("module", ""),
            module_data.get("stmts", 0),
            module_data.get("miss", 0),
            module_data.get("branch", 0),
            module_data.get("brpart", 0),
            module_data.get("cover_percent", 0.0),
            module_data.get("total_lines", 0)
        ]
        
        for col, value in enumerate(values, 1):
            cell = ws.cell(row=row_idx, column=col, value=value)
    
    ws.freeze_panes = "A2"


def _create_resilience_details_sheet(wb: Workbook, data: Dict[str, Any]) -> None:
    """Create Resilience_Details sheet for resilience test results."""
    ws = cast(Worksheet, wb.create_sheet("Resilience_Details"))
    
    # Required column order as specified in requirements
    headers = [
        "run_id", "timestamp", "provider", "model", "request_id", 
        "outcome", "attempts", "latency_ms", "error_class", "mode"
    ]
    
    # Check if we have resilience scenario data to append new columns (additive)
    resilience_data = data.get("resilience", {})
    details = resilience_data.get("details", [])
    has_scenario_data = any(detail.get("scenario_id") for detail in details)
    
    # APPEND new scenario columns at the END (non-breaking)
    if has_scenario_data:
        headers.extend([
            "scenario_id", "failure_mode", "payload_size", "target_timeout_ms", 
            "fail_rate", "circuit_fails", "circuit_reset_s"
        ])
    
    # Write headers with styling
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = Font(bold=True)
        cell.alignment = Alignment(wrap_text=True)
    
    # Auto-size columns
    for col in range(1, len(headers) + 1):
        ws.column_dimensions[get_column_letter(col)].width = 16
    
    # Write resilience detail records
    resilience_details = data.get("resilience", {}).get("details", [])
    
    for row_idx, detail in enumerate(resilience_details, 2):
        values = [
            detail.get("run_id", ""),
            detail.get("timestamp", ""),
            detail.get("provider", ""),
            detail.get("model", ""),
            detail.get("request_id", ""),
            detail.get("outcome", ""),
            detail.get("attempts", 0),
            detail.get("latency_ms", 0),
            detail.get("error_class", ""),
            detail.get("mode", "")
        ]
        
        # APPEND scenario data if present (additive)
        if has_scenario_data:
            values.extend([
                detail.get("scenario_id", ""),
                detail.get("failure_mode", ""),
                detail.get("payload_size", ""),
                detail.get("target_timeout_ms", ""),
                detail.get("fail_rate", ""),
                detail.get("circuit_fails", ""),
                detail.get("circuit_reset_s", "")
            ])
        
        for col, value in enumerate(values, 1):
            cell = ws.cell(row=row_idx, column=col, value=value)
    
    ws.freeze_panes = "A2"


def _create_compliance_details_sheet(wb: Workbook, data: Dict[str, Any]) -> None:
    """Create Compliance_Details sheet for compliance smoke test results."""
    ws = cast(Worksheet, wb.create_sheet("Compliance_Details"))
    
    # Exact column headers as specified
    headers = [
        "run_id", "timestamp", "case_id", "route", "check", "status", "pattern", "notes"
    ]
    
    # Write headers
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = Font(bold=True)
        cell.alignment = Alignment(wrap_text=True)
    
    # Auto-size columns
    for col in range(1, len(headers) + 1):
        ws.column_dimensions[get_column_letter(col)].width = 16
    
    # Write compliance detail records
    compliance_details = data.get("compliance_smoke", {}).get("details", [])
    
    for row_idx, detail in enumerate(compliance_details, 2):
        values = [
            detail.get("run_id", ""),
            detail.get("timestamp", ""),
            detail.get("case_id", ""),
            detail.get("route", ""),
            detail.get("check", ""),
            detail.get("status", ""),
            detail.get("pattern", ""),
            detail.get("notes", "")
        ]
        
        for col, value in enumerate(values, 1):
            cell = ws.cell(row=row_idx, column=col, value=value)
    
    ws.freeze_panes = "A2"


def _create_bias_details_sheet(wb: Workbook, data: Dict[str, Any]) -> None:
    """Create Bias_Details sheet for bias smoke test results."""
    ws = cast(Worksheet, wb.create_sheet("Bias_Details"))
    
    # Exact column headers as specified
    headers = [
        "run_id", "timestamp", "case_id", "group_a", "group_b", "metric", "value", "threshold", "notes"
    ]
    
    # Write headers
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = Font(bold=True)
        cell.alignment = Alignment(wrap_text=True)
    
    # Auto-size columns
    for col in range(1, len(headers) + 1):
        ws.column_dimensions[get_column_letter(col)].width = 16
    
    # Write bias detail records
    bias_details = data.get("bias_smoke", {}).get("details", [])
    
    for row_idx, detail in enumerate(bias_details, 2):
        values = [
            detail.get("run_id", ""),
            detail.get("timestamp", ""),
            detail.get("case_id", ""),
            detail.get("group_a", ""),
            detail.get("group_b", ""),
            detail.get("metric", ""),
            detail.get("value", ""),
            detail.get("threshold", ""),
            detail.get("notes", "")
        ]
        
        for col, value in enumerate(values, 1):
            cell = ws.cell(row=row_idx, column=col, value=value)
    
    ws.freeze_panes = "A2"