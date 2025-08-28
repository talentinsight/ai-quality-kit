"""Structured evaluation runner for prompt robustness testing."""

import json
import re
import time
import statistics
from typing import Dict, List, Any, Optional, Callable
from jinja2 import Template, Environment


def render_template(tmpl: str, ctx: dict) -> str:
    """
    Render a Jinja2 template with the given context.
    
    Args:
        tmpl: Template string with Jinja2 syntax
        ctx: Context dictionary for template variables
        
    Returns:
        Rendered template string
    """
    env = Environment()
    template = env.from_string(tmpl)
    return template.render(**ctx)


def run_case(client: Any, case: Dict[str, Any], mode: str, prompt_text: str, 
             parse_fn: Callable[[str], Any], contract_cfg: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Run a single test case with the given prompt and parse the result.
    
    Args:
        client: Provider client for making API calls
        case: Test case data
        mode: Prompt mode (simple, cot, scaffold)
        prompt_text: Rendered prompt text
        parse_fn: Function to parse the raw response
        contract_cfg: Optional contract configuration for validation
        
    Returns:
        Dictionary with mode, ok, parsed, raw, latency_ms, contract_ok, tokens_in, tokens_out
    """
    start_time = time.time()
    
    try:
        # Make API call with deterministic settings
        response = client.complete(
            prompt=prompt_text,
            temperature=0,
            top_p=1,
            max_tokens=1000
        )
        
        latency_ms = int((time.time() - start_time) * 1000)
        
        # Extract response text and token counts
        if hasattr(response, 'text'):
            raw_output = response.text
        elif isinstance(response, dict):
            raw_output = response.get('text', str(response))
        else:
            raw_output = str(response)
        
        tokens_in = getattr(response, 'prompt_tokens', 0) if hasattr(response, 'prompt_tokens') else 0
        tokens_out = getattr(response, 'completion_tokens', 0) if hasattr(response, 'completion_tokens') else 0
        
        # Parse the result
        parsed_result = parse_fn(raw_output)
        
        # Check exact match against gold
        gold = case.get("gold")
        exact_match = _check_exact_match(parsed_result, gold, case.get("task_type", ""))
        
        # Validate contract if provided
        contract_ok = None
        if contract_cfg:
            from apps.evaluation.contracts import validate_contract
            contract_ok = validate_contract(contract_cfg, raw_output)
        
        return {
            "mode": mode,
            "ok": exact_match,
            "parsed": parsed_result,
            "raw": raw_output,
            "latency_ms": latency_ms,
            "contract_ok": contract_ok,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out
        }
        
    except Exception as e:
        print(f"Error running case for mode {mode}: {e}")
        return {
            "mode": mode,
            "ok": False,
            "parsed": None,
            "raw": f"ERROR: {str(e)}",
            "latency_ms": int((time.time() - start_time) * 1000),
            "contract_ok": None,
            "tokens_in": 0,
            "tokens_out": 0
        }


def extract_result(text: str, task_type: str) -> Any:
    """
    Extract the result from raw text based on task type.
    
    Args:
        text: Raw response text
        task_type: Type of task (long_multiplication, extraction, etc.)
        
    Returns:
        Parsed result appropriate for the task type
    """
    if task_type == "long_multiplication":
        return _extract_long_multiplication_result(text)
    elif task_type == "extraction":
        return _extract_extraction_result(text)
    elif task_type == "json_to_sql":
        return _extract_json_to_sql_result(text)
    elif task_type == "rag_qa":
        return _extract_rag_qa_result(text)
    else:
        # Default: try to extract JSON, fall back to text
        try:
            return json.loads(text.strip())
        except:
            return text.strip()


def compute_stability(binary_outcomes: List[int]) -> float:
    """
    Compute stability as 1 - population_standard_deviation(outcomes).
    
    Args:
        binary_outcomes: List of 0/1 outcomes
        
    Returns:
        Stability score between 0 and 1
    """
    if len(binary_outcomes) <= 1:
        return 1.0
    
    try:
        pstdev = statistics.pstdev(binary_outcomes)
        return max(0.0, 1.0 - pstdev)
    except:
        return 0.0


def _extract_long_multiplication_result(text: str) -> Any:
    """Extract the final integer result from multiplication text."""
    # First try to parse as JSON
    try:
        data = json.loads(text.strip())
        if isinstance(data, dict) and "result" in data:
            return int(data["result"])
        elif isinstance(data, (int, float)):
            return int(data)
    except:
        pass
    
    # Extract last integer from text
    numbers = re.findall(r'-?\d+', text)
    if numbers:
        try:
            return int(numbers[-1])
        except ValueError:
            pass
    
    return None


def _extract_extraction_result(text: str) -> Any:
    """Extract structured data from extraction text."""
    # Try to parse as JSON first
    try:
        data = json.loads(text.strip())
        if isinstance(data, dict):
            # Normalize fields
            normalized = {}
            for key, value in data.items():
                key_lower = key.lower().strip()
                if "merchant" in key_lower or "store" in key_lower or "business" in key_lower:
                    normalized["merchant"] = str(value).strip()
                elif "total" in key_lower or "amount" in key_lower:
                    # Try to extract numeric value
                    if isinstance(value, (int, float)):
                        normalized["total"] = float(value)
                    else:
                        # Extract number from string
                        amount_match = re.search(r'[\d,]+\.?\d*', str(value))
                        if amount_match:
                            normalized["total"] = float(amount_match.group().replace(',', ''))
                elif "date" in key_lower:
                    normalized["date"] = str(value).strip()
                else:
                    # Keep original key if no mapping found
                    normalized[key] = value
            return normalized
    except:
        pass
    
    # Fallback: try to extract from unstructured text
    result = {}
    
    # Extract merchant (usually first line or after keywords)
    merchant_match = re.search(r'(?:merchant|store|business):\s*(.+?)(?:\n|$)', text, re.IGNORECASE)
    if merchant_match:
        result["merchant"] = merchant_match.group(1).strip()
    
    # Extract total
    total_match = re.search(r'(?:total|amount):\s*\$?([\d,]+\.?\d*)', text, re.IGNORECASE)
    if total_match:
        result["total"] = float(total_match.group(1).replace(',', ''))
    
    # Extract date
    date_match = re.search(r'(?:date):\s*(\d{1,2}/\d{1,2}/\d{4})', text, re.IGNORECASE)
    if date_match:
        result["date"] = date_match.group(1)
    
    return result if result else None


def _extract_json_to_sql_result(text: str) -> Any:
    """Extract SQL query from text."""
    # Try to parse as JSON first
    try:
        data = json.loads(text.strip())
        if isinstance(data, dict) and "sql" in data:
            return {"sql": data["sql"].strip()}
    except:
        pass
    
    # Extract SQL from text (look for SELECT, INSERT, UPDATE, DELETE)
    sql_match = re.search(r'((?:SELECT|INSERT|UPDATE|DELETE).*?)(?:\n\n|$)', text, re.IGNORECASE | re.DOTALL)
    if sql_match:
        sql = sql_match.group(1).strip()
        # Normalize whitespace
        sql = re.sub(r'\s+', ' ', sql)
        return {"sql": sql}
    
    return {"sql": text.strip()}


def _extract_rag_qa_result(text: str) -> Any:
    """Extract answer and citations from RAG QA text."""
    # Try to parse as JSON first
    try:
        data = json.loads(text.strip())
        if isinstance(data, dict):
            return data
    except:
        pass
    
    # Extract answer and citations from structured text
    result: Dict[str, Any] = {"answer": text.strip()}
    
    # Look for citations
    citations = re.findall(r'(?:citation|source|reference):\s*(.+?)(?:\n|$)', text, re.IGNORECASE)
    if citations:
        result["citations"] = [c.strip() for c in citations]
    
    return result


def _check_exact_match(parsed_result: Any, gold: Any, task_type: str) -> bool:
    """Check if parsed result exactly matches gold standard."""
    if parsed_result is None or gold is None:
        return False
    
    if task_type == "long_multiplication":
        try:
            parsed_num = int(parsed_result) if isinstance(parsed_result, (int, str)) else parsed_result.get("result", 0)
            gold_num = int(gold) if isinstance(gold, (int, str)) else gold
            return parsed_num == gold_num
        except (ValueError, TypeError):
            return False
    
    elif task_type == "extraction":
        if isinstance(parsed_result, dict) and isinstance(gold, dict):
            # Check all required fields match
            for key in gold:
                if key not in parsed_result:
                    return False
                if str(parsed_result[key]).lower().strip() != str(gold[key]).lower().strip():
                    return False
            return True
        return False
    
    else:
        # Default string comparison
        return str(parsed_result).strip().lower() == str(gold).strip().lower()
