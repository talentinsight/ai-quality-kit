"""Structure evaluation reporting sheets for RAG Reliability & Robustness."""

from typing import List, Dict, Any, Optional
from apps.evaluation.contracts import mask_pii


def write_structure_sheet(wb: Any, rows: List[Dict[str, Any]], *, previews_max_chars: int = 1200) -> None:
    """
    Write Structure sheet with prompt robustness evaluation results.
    
    Args:
        wb: Workbook object (openpyxl or similar)
        rows: List of result dictionaries
        previews_max_chars: Maximum characters for preview fields
    """
    # Create Structure sheet
    ws = wb.create_sheet("Structure")
    
    # Define columns in exact order
    columns = [
        "run_id", "item_id", "task_type", "mode", "paraphrase_idx",
        "prompt_source", "prompt_hash",
        "input_preview_masked", "gold_preview_masked",
        "raw_output_preview_masked", "parsed_result",
        "exact_match", "similarity_score",
        "contract_ok",
        "latency_ms", "prompt_tokens", "completion_tokens",
        "skip_reason"
    ]
    
    # Write header row
    for col_idx, column in enumerate(columns, 1):
        ws.cell(row=1, column=col_idx, value=column)
    
    # Write data rows
    for row_idx, row_data in enumerate(rows, 2):
        for col_idx, column in enumerate(columns, 1):
            value = row_data.get(column, "")
            
            # Apply PII masking and truncation to preview fields
            if column in ["input_preview_masked", "gold_preview_masked", "raw_output_preview_masked"]:
                if value:
                    value = mask_pii(str(value))
                    if len(value) > previews_max_chars:
                        value = value[:previews_max_chars] + "…"
            
            # Handle special formatting
            elif column == "parsed_result" and value is not None:
                value = str(value)
            elif column in ["exact_match", "contract_ok"] and value is not None:
                value = bool(value) if value != "" else ""
            elif column in ["similarity_score", "latency_ms", "prompt_tokens", "completion_tokens"]:
                if value == "" or value is None:
                    value = ""
                else:
                    try:
                        value = float(value)
                    except (ValueError, TypeError):
                        value = ""
            
            ws.cell(row=row_idx, column=col_idx, value=value)


def write_structure_prompts_sheet(wb: Any, prompt_rows: List[Dict[str, Any]], *, previews_max_chars: int = 4000) -> None:
    """
    Write Structure_Prompts sheet with deduplicated prompt information.
    
    Args:
        wb: Workbook object
        prompt_rows: List of prompt dictionaries
        previews_max_chars: Maximum characters for prompt preview
    """
    # Create Structure_Prompts sheet
    ws = wb.create_sheet("Structure_Prompts")
    
    # Define columns
    columns = [
        "item_id", "mode", "prompt_source", "prompt_hash",
        "prompt_masked_full", "style_contract_version", "provider_profile", "gates_passed"
    ]
    
    # Write header row
    for col_idx, column in enumerate(columns, 1):
        ws.cell(row=1, column=col_idx, value=column)
    
    # Deduplicate by (item_id, mode, prompt_hash)
    seen_prompts = set()
    unique_rows = []
    
    for row in prompt_rows:
        key = (row.get("item_id", ""), row.get("mode", ""), row.get("prompt_hash", ""))
        if key not in seen_prompts:
            seen_prompts.add(key)
            unique_rows.append(row)
    
    # Write data rows
    for row_idx, row_data in enumerate(unique_rows, 2):
        for col_idx, column in enumerate(columns, 1):
            value = row_data.get(column, "")
            
            # Apply PII masking and truncation to prompt_masked_full
            if column == "prompt_masked_full" and value:
                value = mask_pii(str(value))
                if len(value) > previews_max_chars:
                    value = value[:previews_max_chars] + "…"
            
            # Handle boolean fields
            elif column == "gates_passed" and value is not None and value != "":
                value = bool(value)
            
            ws.cell(row=row_idx, column=col_idx, value=value)


def write_structure_diffs_sheet(wb: Any, diff_rows: List[Dict[str, Any]]) -> None:
    """
    Write Structure_Diffs sheet with task-specific comparison results.
    
    Args:
        wb: Workbook object
        diff_rows: List of diff result dictionaries
    """
    # Create Structure_Diffs sheet
    ws = wb.create_sheet("Structure_Diffs")
    
    # Base columns (always present)
    base_columns = ["item_id", "mode", "paraphrase_idx", "diff_preview"]
    
    # Determine task-specific columns from the data
    task_specific_columns = set()
    for row in diff_rows:
        task_type = row.get("task_type", "")
        if task_type == "long_multiplication":
            task_specific_columns.update(["abs_diff", "relative_error"])
        elif task_type == "extraction":
            task_specific_columns.update(["fieldwise_accuracy", "missing_fields", "mismatched_fields"])
        elif task_type == "json_to_sql":
            task_specific_columns.update(["canonical_equal", "where_and_set_equal", "normalized_sql_diff_preview"])
        elif task_type == "rag_qa":
            task_specific_columns.update(["lexical_f1", "faithfulness_flag"])
    
    # Combine columns
    columns = base_columns + sorted(list(task_specific_columns))
    
    # Write header row
    for col_idx, column in enumerate(columns, 1):
        ws.cell(row=1, column=col_idx, value=column)
    
    # Write data rows
    for row_idx, row_data in enumerate(diff_rows, 2):
        for col_idx, column in enumerate(columns, 1):
            value = row_data.get(column, "")
            
            # Apply PII masking to diff_preview and normalized_sql_diff_preview
            if column in ["diff_preview", "normalized_sql_diff_preview"] and value:
                value = mask_pii(str(value))
            
            # Handle boolean fields
            elif column in ["canonical_equal", "where_and_set_equal", "faithfulness_flag"] and value is not None and value != "":
                value = bool(value)
            
            # Handle numeric fields
            elif column in ["abs_diff", "relative_error", "fieldwise_accuracy", "lexical_f1"]:
                if value == "" or value is None:
                    value = ""
                else:
                    try:
                        value = float(value)
                    except (ValueError, TypeError):
                        value = ""
            
            ws.cell(row=row_idx, column=col_idx, value=value)


def compute_summary_rollups(structure_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Compute summary rollups for RAG Reliability & Robustness.
    
    Args:
        structure_rows: List of structure evaluation results
        
    Returns:
        Dictionary with computed rollups
    """
    if not structure_rows:
        return {
            "capacity_lift_avg": 0.0,
            "stability_avg_by_mode": {},
            "contract_adherence_pct": 0.0,
            "faithfulness_avg": None
        }
    
    # Group by item_id and mode
    mode_results = {}
    contract_results = []
    
    for row in structure_rows:
        item_id = row.get("item_id", "")
        mode = row.get("mode", "")
        exact_match = row.get("exact_match", False)
        contract_ok = row.get("contract_ok")
        
        if mode not in mode_results:
            mode_results[mode] = []
        
        mode_results[mode].append({
            "item_id": item_id,
            "exact_match": bool(exact_match) if exact_match is not None else False
        })
        
        if contract_ok is not None:
            contract_results.append(bool(contract_ok))
    
    # Compute mode accuracies
    mode_accuracies = {}
    for mode, results in mode_results.items():
        if results:
            accuracy = sum(1 for r in results if r["exact_match"]) / len(results)
            mode_accuracies[mode] = accuracy
    
    # Compute capacity lift (scaffold - simple)
    capacity_lift_avg = 0.0
    if "scaffold" in mode_accuracies and "simple" in mode_accuracies:
        capacity_lift_avg = mode_accuracies["scaffold"] - mode_accuracies["simple"]
    
    # Compute stability by mode (simplified - would need paraphrase data for full implementation)
    stability_avg_by_mode = {}
    for mode in mode_accuracies:
        # For now, use accuracy as a proxy for stability
        stability_avg_by_mode[mode] = mode_accuracies.get(mode, 0.0)
    
    # Compute contract adherence
    contract_adherence_pct = 0.0
    if contract_results:
        contract_adherence_pct = (sum(contract_results) / len(contract_results)) * 100
    
    return {
        "capacity_lift_avg": round(capacity_lift_avg, 4),
        "stability_avg_by_mode": {k: round(v, 4) for k, v in stability_avg_by_mode.items()},
        "contract_adherence_pct": round(contract_adherence_pct, 1),
        "faithfulness_avg": None  # Would be populated if RAG faithfulness is available
    }
