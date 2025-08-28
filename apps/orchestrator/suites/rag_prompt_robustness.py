"""RAG Prompt Robustness (Structured Prompting) evaluation suite.

This module implements the prompt robustness evaluation that tests the same input
across different prompt modes (simple, cot, scaffold) to measure capacity lift,
stability, and contract adherence.
"""

import json
import hashlib
import time
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path

from apps.evaluation.structured_runner import (
    render_template,
    run_case,
    extract_result,
    compute_stability
)
from apps.evaluation.contracts import validate_contract, mask_pii
from apps.utils.sql_normalize import compare_sql


# Built-in PromptSets
BUILTIN_PROMPTSETS = {
    "long_multiplication": {
        "task_type": "long_multiplication",
        "requires": ["input.a", "input.b"],
        "constraints": {"digits_min": 7, "digits_max": 10},
        "modes": {
            "simple": "Calculate {{input.a}} × {{input.b}}. Show only the final result.",
            "cot": "Calculate {{input.a}} × {{input.b}}. Think step by step:\n1. Break down the multiplication\n2. Show your work\n3. Provide the final result",
            "scaffold": "Calculate {{input.a}} × {{input.b}} using the standard multiplication algorithm:\n1. Write the numbers vertically\n2. Multiply each digit of the bottom number by each digit of the top number\n3. Add the partial products\n4. Show each step clearly\n5. Provide the final result"
        },
        "contracts": {
            "type": "jsonschema",
            "schema": {
                "type": "object",
                "properties": {
                    "result": {"type": "integer"}
                },
                "required": ["result"]
            }
        },
        "paraphrases": [
            "Compute the product of {{input.a}} and {{input.b}}",
            "What is {{input.a}} multiplied by {{input.b}}?"
        ]
    },
    "extraction": {
        "task_type": "extraction",
        "requires": ["input.text"],
        "constraints": {},
        "modes": {
            "simple": "Extract merchant, total, and date from this receipt:\n{{input.text}}",
            "cot": "Extract merchant, total, and date from this receipt. Think step by step:\n1. Identify the merchant name\n2. Find the total amount\n3. Locate the date\n\nReceipt:\n{{input.text}}",
            "scaffold": "Extract structured information from this receipt following these steps:\n1. Scan for merchant/business name (usually at top)\n2. Look for total amount (keywords: total, amount due, etc.)\n3. Find transaction date (format: MM/DD/YYYY or similar)\n4. Format as JSON with fields: merchant, total, date\n\nReceipt:\n{{input.text}}"
        },
        "contracts": {
            "type": "jsonschema",
            "schema": {
                "type": "object",
                "properties": {
                    "merchant": {"type": "string"},
                    "total": {"type": "number"},
                    "date": {"type": "string"}
                },
                "required": ["merchant", "total", "date"]
            }
        },
        "paraphrases": [
            "Parse the merchant, total amount, and date from:\n{{input.text}}",
            "From this receipt, extract merchant name, total cost, and transaction date:\n{{input.text}}"
        ]
    },
    "json_to_sql": {
        "task_type": "json_to_sql",
        "requires": ["input.schema", "input.request"],
        "constraints": {},
        "modes": {
            "simple": "Convert this request to SQL:\nSchema: {{input.schema}}\nRequest: {{input.request}}",
            "cot": "Convert this request to SQL. Think step by step:\n1. Understand the schema\n2. Parse the request\n3. Write the SQL query\n\nSchema: {{input.schema}}\nRequest: {{input.request}}",
            "scaffold": "Convert this natural language request to SQL following these steps:\n1. Analyze the database schema: {{input.schema}}\n2. Identify required tables and columns\n3. Determine JOIN conditions if multiple tables\n4. Apply WHERE clauses for filters\n5. Add ORDER BY, GROUP BY, LIMIT as needed\n6. Write clean, valid SQL\n\nRequest: {{input.request}}"
        },
        "contracts": {
            "type": "jsonschema",
            "schema": {
                "type": "object",
                "properties": {
                    "sql": {"type": "string"}
                },
                "required": ["sql"]
            }
        },
        "paraphrases": [
            "Generate SQL for: {{input.request}} (Schema: {{input.schema}})",
            "Write a SQL query for '{{input.request}}' using schema {{input.schema}}"
        ]
    },
    "rag_qa": {
        "task_type": "rag_qa",
        "requires": ["input.context", "input.question"],
        "constraints": {},
        "modes": {
            "simple": "Answer the question based on the context:\nContext: {{input.context}}\nQuestion: {{input.question}}",
            "cot": "Answer the question based on the context. Think step by step:\n1. Read the context carefully\n2. Identify relevant information\n3. Formulate your answer\n\nContext: {{input.context}}\nQuestion: {{input.question}}",
            "scaffold": "Answer the question using this structured approach:\n1. RETRIEVE: Find relevant information from the context\n2. QUOTE: Identify key passages that support your answer\n3. ANSWER: Formulate a clear, direct response\n4. CITE: Reference the specific context used\n\nContext: {{input.context}}\nQuestion: {{input.question}}"
        },
        "contracts": {
            "type": "jsonschema",
            "schema": {
                "type": "object",
                "properties": {
                    "answer": {"type": "string"},
                    "citations": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["answer"]
            }
        },
        "paraphrases": [
            "Based on the provided context, answer: {{input.question}}\nContext: {{input.context}}",
            "Using the context below, respond to: {{input.question}}\n{{input.context}}"
        ]
    }
}


def run_prompt_robustness(run_cfg: Dict[str, Any], provider_client: Any, dataset_items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Run prompt robustness evaluation across different prompt modes.
    
    Args:
        run_cfg: Configuration for the run including prompt_robustness settings
        provider_client: Provider client for making API calls
        dataset_items: List of test items to evaluate
        
    Returns:
        Dictionary containing structure_rows, prompts_rows, diffs_rows, and rollups
    """
    structure_rows = []
    prompts_rows = []
    diffs_rows = []
    
    # Get prompt robustness config
    prompt_config = run_cfg.get("rag_reliability_robustness", {}).get("prompt_robustness", {})
    if not prompt_config.get("enabled", False):
        return {
            "structure_rows": [],
            "prompts_rows": [],
            "diffs_rows": [],
            "rollups": {}
        }
    
    prompt_source = prompt_config.get("prompt_source", "built_in")
    include_prompts = prompt_config.get("include_prompts", True)
    paraphrase_runs = prompt_config.get("paraphrase_runs", 2)
    
    modes = ["simple", "cot", "scaffold"]
    
    for item in dataset_items:
        task_type = item.get("task_type", "unknown")
        item_id = item.get("test_id", item.get("id", "unknown"))
        
        # Get PromptSet for this task_type
        promptset = BUILTIN_PROMPTSETS.get(task_type)
        if not promptset:
            # Skip items without supported PromptSet
            structure_rows.append({
                "run_id": run_cfg.get("run_id", "unknown"),
                "item_id": item_id,
                "task_type": task_type,
                "mode": "N/A",
                "paraphrase_idx": 0,
                "prompt_source": prompt_source,
                "prompt_hash": "",
                "input_preview_masked": mask_pii(str(item.get("input", {}))),
                "gold_preview_masked": mask_pii(str(item.get("gold", ""))),
                "raw_output_preview_masked": "",
                "parsed_result": None,
                "exact_match": False,
                "similarity_score": 0.0,
                "contract_ok": None,
                "latency_ms": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "skip_reason": f"No PromptSet for task_type: {task_type}"
            })
            continue
        
        # Preflight check
        skip_reason = _check_preflight(item, promptset)
        if skip_reason:
            structure_rows.append({
                "run_id": run_cfg.get("run_id", "unknown"),
                "item_id": item_id,
                "task_type": task_type,
                "mode": "N/A",
                "paraphrase_idx": 0,
                "prompt_source": prompt_source,
                "prompt_hash": "",
                "input_preview_masked": mask_pii(str(item.get("input", {}))),
                "gold_preview_masked": mask_pii(str(item.get("gold", ""))),
                "raw_output_preview_masked": "",
                "parsed_result": None,
                "exact_match": False,
                "similarity_score": 0.0,
                "contract_ok": None,
                "latency_ms": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "skip_reason": skip_reason
            })
            continue
        
        # Run each mode
        mode_results = {}
        for mode in modes:
            mode_template = promptset["modes"].get(mode)
            if not mode_template:
                continue
                
            # Render base prompt
            try:
                prompt_text = render_template(mode_template, {"input": item.get("input", {})})
                prompt_hash = hashlib.sha256(prompt_text.encode()).hexdigest()[:16]
            except Exception as e:
                print(f"Error rendering template for {item_id} mode {mode}: {e}")
                continue
            
            # Run base case
            case_result = run_case(
                provider_client,
                item,
                mode,
                prompt_text,
                lambda text: extract_result(text, task_type),
                promptset.get("contracts")
            )
            
            # Compute similarity score and handle SQL comparison
            similarity_score = _compute_similarity_score(case_result.get("parsed"), item.get("gold"), task_type)
            
            # Add to structure results
            result_record = {
                "run_id": run_cfg.get("run_id", "unknown"),
                "item_id": item_id,
                "task_type": task_type,
                "mode": mode,
                "paraphrase_idx": 0,
                "prompt_source": prompt_source,
                "prompt_hash": prompt_hash,
                "input_preview_masked": str(item.get("input", {}))[:200],
                "gold_preview_masked": str(item.get("gold", ""))[:200],
                "raw_output_preview_masked": case_result.get("raw", "")[:500],
                "parsed_result": case_result.get("parsed"),
                "exact_match": case_result.get("ok", False),
                "similarity_score": similarity_score,
                "contract_ok": case_result.get("contract_ok"),
                "latency_ms": case_result.get("latency_ms", 0),
                "prompt_tokens": case_result.get("tokens_in", 0),
                "completion_tokens": case_result.get("tokens_out", 0),
                "skip_reason": ""
            }
            structure_rows.append(result_record)
            
            # Add to prompts results if include_prompts is enabled
            if include_prompts:
                prompts_rows.append({
                    "item_id": item_id,
                    "mode": mode,
                    "prompt_source": prompt_source,
                    "prompt_hash": prompt_hash,
                    "prompt_masked_full": _normalize_prompt_for_hash(prompt_text),
                    "style_contract_version": "",
                    "provider_profile": "",
                    "gates_passed": ""
                })
            
            # Add to diffs results with task-specific data
            diff_record = _create_diff_record(item_id, mode, 0, task_type, case_result.get("parsed"), item.get("gold"))
            if diff_record:
                diffs_rows.append(diff_record)
            
            # Store for stability computation
            mode_results[mode] = [case_result.get("ok", False)]
            
            # Run paraphrases if available
            paraphrases = promptset.get("paraphrases", [])
            if paraphrases and paraphrase_runs > 0:
                for para_idx, paraphrase_template in enumerate(paraphrases[:paraphrase_runs]):
                    try:
                        para_prompt = render_template(paraphrase_template, {"input": item.get("input", {})})
                        para_hash = hashlib.sha256(para_prompt.encode()).hexdigest()[:16]
                        
                        para_result = run_case(
                            provider_client,
                            item,
                            mode,
                            para_prompt,
                            lambda text: extract_result(text, task_type),
                            promptset.get("contracts")
                        )
                        
                        # Add paraphrase result to structure_rows
                        para_record = result_record.copy()
                        para_record.update({
                            "paraphrase_idx": para_idx + 1,
                            "prompt_hash": para_hash,
                            "raw_output_preview_masked": para_result.get("raw", "")[:500],
                            "parsed_result": para_result.get("parsed"),
                            "exact_match": para_result.get("ok", False),
                            "similarity_score": _compute_similarity_score(para_result.get("parsed"), item.get("gold"), task_type),
                            "contract_ok": para_result.get("contract_ok"),
                            "latency_ms": para_result.get("latency_ms", 0),
                            "prompt_tokens": para_result.get("tokens_in", 0),
                            "completion_tokens": para_result.get("tokens_out", 0)
                        })
                        structure_rows.append(para_record)
                        
                        # Add paraphrase prompt if include_prompts is enabled
                        if include_prompts:
                            prompts_rows.append({
                                "item_id": item_id,
                                "mode": mode,
                                "prompt_source": prompt_source,
                                "prompt_hash": para_hash,
                                "prompt_masked_full": _normalize_prompt_for_hash(para_prompt),
                                "style_contract_version": "",
                                "provider_profile": "",
                                "gates_passed": ""
                            })
                        
                        # Add paraphrase diff record
                        para_diff_record = _create_diff_record(item_id, mode, para_idx + 1, task_type, para_result.get("parsed"), item.get("gold"))
                        if para_diff_record:
                            diffs_rows.append(para_diff_record)
                        
                        # Add to stability computation
                        mode_results[mode].append(para_result.get("ok", False))
                        
                    except Exception as e:
                        print(f"Error running paraphrase {para_idx} for {item_id} mode {mode}: {e}")
    
    # Compute rollups
    from apps.reporting.structure_sheet import compute_summary_rollups
    rollups = compute_summary_rollups(structure_rows)
    
    return {
        "structure_rows": structure_rows,
        "prompts_rows": prompts_rows,
        "diffs_rows": diffs_rows,
        "rollups": rollups
    }


def _check_preflight(item: Dict[str, Any], promptset: Dict[str, Any]) -> Optional[str]:
    """
    Check if item satisfies PromptSet requirements and constraints.
    
    Returns:
        None if checks pass, error message string if they fail
    """
    requires = promptset.get("requires", [])
    constraints = promptset.get("constraints", {})
    item_input = item.get("input", {})
    
    # Check required fields
    for req_field in requires:
        if "." in req_field:
            # Handle nested field like "input.a"
            parts = req_field.split(".")
            if parts[0] == "input":
                if len(parts) > 1 and parts[1] not in item_input:
                    return f"missing_field: {req_field}"
                if len(parts) > 1 and not item_input.get(parts[1]):
                    return f"empty_field: {req_field}"
        else:
            if req_field not in item:
                return f"missing_field: {req_field}"
    
    # Check constraints
    if constraints:
        # Check digit constraints for multiplication
        if "digits_min" in constraints or "digits_max" in constraints:
            a_val = item_input.get("a")
            b_val = item_input.get("b")
            if a_val is not None and b_val is not None:
                a_digits = len(str(abs(int(a_val))))
                b_digits = len(str(abs(int(b_val))))
                min_digits = constraints.get("digits_min", 0)
                max_digits = constraints.get("digits_max", 999)
                
                if a_digits < min_digits or a_digits > max_digits:
                    return f"constraint_violation: a digits {a_digits} not in range [{min_digits}, {max_digits}]"
                if b_digits < min_digits or b_digits > max_digits:
                    return f"constraint_violation: b digits {b_digits} not in range [{min_digits}, {max_digits}]"
    
    return None


def _compute_similarity_score(parsed_result: Any, gold: Any, task_type: str) -> float:
    """Compute task-specific similarity score."""
    if parsed_result is None or gold is None:
        return 0.0
    
    if task_type == "long_multiplication":
        try:
            parsed_num = int(parsed_result) if isinstance(parsed_result, (int, str)) else parsed_result.get("result", 0)
            gold_num = int(gold) if isinstance(gold, (int, str)) else gold
            if parsed_num == gold_num:
                return 1.0
            else:
                # Relative error
                return max(0.0, 1.0 - abs(parsed_num - gold_num) / max(abs(gold_num), 1))
        except (ValueError, TypeError):
            return 0.0
    
    elif task_type == "extraction":
        if isinstance(parsed_result, dict) and isinstance(gold, dict):
            matches = 0
            total = len(gold)
            for key in gold:
                if key in parsed_result:
                    if str(parsed_result[key]).lower().strip() == str(gold[key]).lower().strip():
                        matches += 1
            return matches / max(total, 1)
        return 0.0
    
    elif task_type in ["json_to_sql", "rag_qa"]:
        # Simple string similarity for now
        parsed_str = str(parsed_result).lower().strip()
        gold_str = str(gold).lower().strip()
        if parsed_str == gold_str:
            return 1.0
        # Jaccard similarity
        parsed_words = set(parsed_str.split())
        gold_words = set(gold_str.split())
        intersection = len(parsed_words & gold_words)
        union = len(parsed_words | gold_words)
        return intersection / max(union, 1)
    
    return 0.0


def _normalize_prompt_for_hash(prompt_text: str) -> str:
    """Normalize prompt text for consistent hashing."""
    if not prompt_text:
        return ""
    
    # Strip whitespace and normalize line breaks
    normalized = prompt_text.strip()
    normalized = normalized.replace('\r\n', '\n').replace('\r', '\n')
    
    # Collapse multiple spaces to single space
    import re
    normalized = re.sub(r' +', ' ', normalized)
    
    return normalized


def _create_diff_record(item_id: str, mode: str, paraphrase_idx: int, task_type: str, parsed_result: Any, gold: Any) -> Optional[Dict[str, Any]]:
    """Create a diff record with task-specific comparison data."""
    base_record = {
        "item_id": item_id,
        "mode": mode,
        "paraphrase_idx": paraphrase_idx,
        "task_type": task_type,
        "diff_preview": ""
    }
    
    if task_type == "long_multiplication":
        try:
            parsed_num = int(parsed_result) if isinstance(parsed_result, (int, str)) else parsed_result.get("result", 0) if parsed_result else 0
            gold_num = int(gold) if isinstance(gold, (int, str)) else gold
            abs_diff = abs(parsed_num - gold_num)
            relative_error = abs_diff / max(abs(gold_num), 1) if gold_num != 0 else 1.0
            
            base_record.update({
                "abs_diff": abs_diff,
                "relative_error": relative_error,
                "diff_preview": f"Parsed: {parsed_num}, Gold: {gold_num}, Diff: {abs_diff}"
            })
        except (ValueError, TypeError):
            base_record.update({
                "abs_diff": 0,
                "relative_error": 1.0,
                "diff_preview": f"Parse error - Parsed: {parsed_result}, Gold: {gold}"
            })
    
    elif task_type == "extraction":
        if isinstance(parsed_result, dict) and isinstance(gold, dict):
            matches = 0
            total = len(gold)
            missing_fields = []
            mismatched_fields = []
            
            for key in gold:
                if key not in parsed_result:
                    missing_fields.append(key)
                elif str(parsed_result[key]).lower().strip() != str(gold[key]).lower().strip():
                    mismatched_fields.append(key)
                else:
                    matches += 1
            
            fieldwise_accuracy = matches / max(total, 1)
            
            base_record.update({
                "fieldwise_accuracy": fieldwise_accuracy,
                "missing_fields": ", ".join(missing_fields),
                "mismatched_fields": ", ".join(mismatched_fields),
                "diff_preview": f"Accuracy: {fieldwise_accuracy:.2f}, Missing: {len(missing_fields)}, Mismatched: {len(mismatched_fields)}"
            })
        else:
            base_record.update({
                "fieldwise_accuracy": 0.0,
                "missing_fields": "parse_error",
                "mismatched_fields": "",
                "diff_preview": "Failed to parse as structured data"
            })
    
    elif task_type == "json_to_sql":
        try:
            parsed_sql = parsed_result.get("sql", "") if isinstance(parsed_result, dict) else str(parsed_result)
            gold_sql = str(gold)
            
            sql_comparison = compare_sql(gold_sql, parsed_sql)
            
            base_record.update({
                "canonical_equal": sql_comparison["canonical_equal"],
                "where_and_set_equal": sql_comparison["where_and_set_equal"],
                "normalized_sql_diff_preview": sql_comparison["normalized_sql_diff_preview"],
                "diff_preview": f"Canonical: {sql_comparison['canonical_equal']}, WHERE-AND: {sql_comparison['where_and_set_equal']}"
            })
        except Exception:
            base_record.update({
                "canonical_equal": False,
                "where_and_set_equal": False,
                "normalized_sql_diff_preview": "Comparison failed",
                "diff_preview": "SQL comparison error"
            })
    
    elif task_type == "rag_qa":
        try:
            parsed_answer = parsed_result.get("answer", "") if isinstance(parsed_result, dict) else str(parsed_result)
            gold_answer = str(gold)
            
            # Simple lexical F1 computation
            parsed_words = set(parsed_answer.lower().split())
            gold_words = set(gold_answer.lower().split())
            
            if not gold_words:
                lexical_f1 = 1.0 if not parsed_words else 0.0
            else:
                intersection = len(parsed_words & gold_words)
                precision = intersection / len(parsed_words) if parsed_words else 0.0
                recall = intersection / len(gold_words) if gold_words else 0.0
                lexical_f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
            
            base_record.update({
                "lexical_f1": lexical_f1,
                "faithfulness_flag": None,  # Would be populated if faithfulness evaluator is available
                "diff_preview": f"Lexical F1: {lexical_f1:.3f}"
            })
        except Exception:
            base_record.update({
                "lexical_f1": 0.0,
                "faithfulness_flag": None,
                "diff_preview": "QA comparison error"
            })
    
    return base_record
