"""Excel report generation for orchestrator results."""

import json
from pathlib import Path
from typing import Dict, List, Any
from openpyxl import Workbook
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
    if data.get("adversarial") and len(data["adversarial"]) > 0:
        _create_adversarial_sheet(wb, data)
    
    if data.get("coverage") and data["coverage"]:
        _create_coverage_sheet(wb, data)
    
    # Save workbook
    wb.save(path)


def _create_summary_sheet(wb: Workbook, data: Dict[str, Any]) -> None:
    """Create Summary sheet with run overview."""
    ws = wb.create_sheet("Summary", 0)
    
    headers = [
        "run_id", "started_at", "finished_at", "suites", "total_tests", 
        "pass_rate", "faithfulness_avg", "context_recall_avg", 
        "attack_success_rate", "warm_p95_ms", "provider", "model"
    ]
    
    # Write headers
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)  # type: ignore
        cell.font = Font(bold=True)  # type: ignore
        ws.column_dimensions[get_column_letter(col)].width = 16  # type: ignore
    
    # Write data row
    run_meta = data.get("run", {})
    summary = data.get("summary", {})
    
    row_data = [
        run_meta.get("run_id", ""),
        run_meta.get("started_at", ""),
        run_meta.get("finished_at", ""),
        ",".join(run_meta.get("suites", [])),
        summary.get("total_tests", 0),
        summary.get("pass_rate", 0.0),
        summary.get("faithfulness_avg", 0.0),
        summary.get("context_recall_avg", 0.0),
        summary.get("attack_success_rate", 0.0),
        summary.get("warm_p95_ms", 0),
        run_meta.get("provider", ""),
        run_meta.get("model", "")
    ]
    
    for col, value in enumerate(row_data, 1):
        ws.cell(row=2, column=col, value=value)  # type: ignore
    
    # Freeze panes and format
    ws.freeze_panes = "A2"  # type: ignore


def _create_detailed_sheet(wb: Workbook, data: Dict[str, Any]) -> None:
    """Create Detailed sheet with per-test results."""
    ws = wb.create_sheet("Detailed")
    
    headers = [
        "suite", "test_id", "provider", "model", "query_masked", 
        "answer_masked", "context_ids", "metrics_json", "pass", 
        "latency_ms", "timestamp"
    ]
    
    # Write headers with styling
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)  # type: ignore
        cell.font = Font(bold=True)  # type: ignore
        cell.alignment = Alignment(wrap_text=True)  # type: ignore
        
        # Set column widths
        if header in ["query_masked", "answer_masked"]:
            ws.column_dimensions[get_column_letter(col)].width = 40  # type: ignore
        elif header in ["metrics_json", "context_ids"]:
            ws.column_dimensions[get_column_letter(col)].width = 30  # type: ignore
        else:
            ws.column_dimensions[get_column_letter(col)].width = 16  # type: ignore
    
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
            cell = ws.cell(row=row_idx, column=col, value=value)  # type: ignore
            if col in [5, 6]:  # query_masked, answer_masked
                cell.alignment = Alignment(wrap_text=True)  # type: ignore
    
    ws.freeze_panes = "A2"  # type: ignore


def _create_api_details_sheet(wb: Workbook, data: Dict[str, Any]) -> None:
    """Create API_Details sheet with API call information."""
    ws = wb.create_sheet("API_Details")
    
    headers = [
        "suite", "test_id", "endpoint", "status_code", "x_source", 
        "x_perf_phase", "x_latency_ms", "request_id", "timestamp"
    ]
    
    # Write headers
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)  # type: ignore
        cell.font = Font(bold=True)  # type: ignore
        ws.column_dimensions[get_column_letter(col)].width = 16  # type: ignore
    
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
    
    ws.freeze_panes = "A2"  # type: ignore


def _create_inputs_expected_sheet(wb: Workbook, data: Dict[str, Any]) -> None:
    """Create Inputs_And_Expected sheet with test configuration."""
    ws = wb.create_sheet("Inputs_And_Expected")
    
    headers = [
        "suite", "test_id", "target_mode", "top_k", "options_json", 
        "thresholds_json", "expected_json", "notes"
    ]
    
    # Write headers
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)  # type: ignore
        cell.font = Font(bold=True)  # type: ignore
        cell.alignment = Alignment(wrap_text=True)  # type: ignore
        
        # Set column widths for JSON columns
        if "_json" in header:
            ws.column_dimensions[get_column_letter(col)].width = 30  # type: ignore
        else:
            ws.column_dimensions[get_column_letter(col)].width = 16  # type: ignore
    
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
            cell = ws.cell(row=row_idx, column=col, value=value)  # type: ignore
            if "_json" in headers[col-1]:
                cell.alignment = Alignment(wrap_text=True)  # type: ignore
    
    ws.freeze_panes = "A2"  # type: ignore


def _create_adversarial_sheet(wb: Workbook, data: Dict[str, Any]) -> None:
    """Create Adversarial_Details sheet for red team results."""
    ws = wb.create_sheet("Adversarial_Details")
    
    headers = [
        "attack_id", "variant_id", "category", "prompt_variant_masked", 
        "decision", "banned_hits_json", "notes", "timestamp"
    ]
    
    # Write headers
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)  # type: ignore
        cell.font = Font(bold=True)  # type: ignore
        cell.alignment = Alignment(wrap_text=True)  # type: ignore
        
        # Set column widths
        if header == "prompt_variant_masked":
            ws.column_dimensions[get_column_letter(col)].width = 50  # type: ignore
        elif "_json" in header:
            ws.column_dimensions[get_column_letter(col)].width = 25  # type: ignore
        else:
            ws.column_dimensions[get_column_letter(col)].width = 16  # type: ignore
    
    # Write data rows
    adv_rows = data.get("adversarial", [])
    for row_idx, row_data in enumerate(adv_rows, 2):
        values = [
            row_data.get("attack_id", ""),
            row_data.get("variant_id", ""),
            row_data.get("category", ""),
            row_data.get("prompt_variant_masked", ""),
            row_data.get("decision", ""),
            json.dumps(row_data.get("banned_hits_json", [])) if row_data.get("banned_hits_json") else "",
            row_data.get("notes", ""),
            row_data.get("timestamp", "")
        ]
        
        for col, value in enumerate(values, 1):
            cell = ws.cell(row=row_idx, column=col, value=value)  # type: ignore
            if col == 4:  # prompt_variant_masked
                cell.alignment = Alignment(wrap_text=True)  # type: ignore
    
    ws.freeze_panes = "A2"  # type: ignore


def _create_coverage_sheet(wb: Workbook, data: Dict[str, Any]) -> None:
    """Create Coverage sheet for test coverage analysis."""
    ws = wb.create_sheet("Coverage")
    
    headers = [
        "category", "attempts", "successes", "success_rate", "avg_latency_ms"
    ]
    
    # Write headers
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)  # type: ignore
        cell.font = Font(bold=True)  # type: ignore
        ws.column_dimensions[get_column_letter(col)].width = 16  # type: ignore
    
    # Write data rows from coverage dict
    coverage = data.get("coverage", {})
    row_idx = 2
    for category, stats in coverage.items():
        if isinstance(stats, dict):
            values = [
                category,
                stats.get("attempts", 0),
                stats.get("successes", 0),
                stats.get("success_rate", 0.0),
                stats.get("avg_latency_ms", 0)
            ]
            
            for col, value in enumerate(values, 1):
                ws.cell(row=row_idx, column=col, value=value)  # type: ignore
            
            row_idx += 1
    
    ws.freeze_panes = "A2"  # type: ignore