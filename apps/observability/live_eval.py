"""Live evaluation module for real-time quality assessment."""

import os
from typing import Dict, List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import dependencies
try:
    from evals.metrics import eval_batch, create_eval_sample
    from guardrails.test_guardrails import TestGuardrails
    from safety.test_safety_basic import TestSafetyBasic
except ImportError:
    # Fallback if dependencies not available
    eval_batch = None
    create_eval_sample = None
    TestGuardrails = None
    TestSafetyBasic = None


def is_live_eval_enabled() -> bool:
    """Check if live evaluation is enabled."""
    return os.getenv("ENABLE_LIVE_EVAL", "false").lower() == "true"


def _has_provider_keys() -> bool:
    """Check if required provider keys are available."""
    openai_key = os.getenv("OPENAI_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    return bool(openai_key or anthropic_key)


def evaluate_one(question: str, contexts: List[str], answer: str) -> Dict[str, float]:
    """
    Evaluate a single response using Ragas metrics.
    
    Args:
        question: The original question
        contexts: Retrieved context passages
        answer: Generated answer
        
    Returns:
        Dictionary with metric scores (empty if evaluation fails)
    """
    if not is_live_eval_enabled() or not _has_provider_keys():
        return {}
    
    if not eval_batch or not create_eval_sample:
        return {}
    
    try:
        # Create evaluation sample
        sample = create_eval_sample(
            question=question,
            answer=answer,
            contexts=contexts
        )
        
        # Evaluate with Ragas
        scores = eval_batch([sample])
        
        return scores
        
    except Exception as e:
        # Log error without exposing secrets
        print(f"Warning: Live evaluation failed: {str(e)}")
        return {}


def validate_guardrails(answer: str) -> Dict[str, float]:
    """
    Validate answer against guardrails.
    
    Args:
        answer: Generated answer to validate
        
    Returns:
        Dictionary with guardrail metrics
    """
    if not is_live_eval_enabled() or not _has_provider_keys():
        return {}
    
    if not TestGuardrails:
        return {}
    
    try:
        # Create a temporary test instance for validation
        test_instance = TestGuardrails()
        
        # Load JSON schema
        import json
        schema_path = "guardrails/schema.json"
        with open(schema_path, 'r') as f:
            json_schema = json.load(f)
        
        # Validate JSON structure (best-effort)
        try:
            import jsonschema
            jsonschema.validate(answer, json_schema)
            return {"json_schema_pass": 1.0}
        except (jsonschema.ValidationError, ValueError):
            return {"json_schema_pass": 0.0}
            
    except Exception as e:
        # Log error without exposing secrets
        print(f"Warning: Guardrail validation failed: {str(e)}")
        return {}


def scan_safety_violations(answer: str) -> Dict[str, float]:
    """
    Scan answer for safety violations.
    
    Args:
        answer: Generated answer to scan
        
    Returns:
        Dictionary with safety metrics
    """
    if not is_live_eval_enabled() or not _has_provider_keys():
        return {}
    
    if not TestSafetyBasic:
        return {}
    
    try:
        # Define violation patterns
        violation_patterns = [
            'ssn', 'bypass', 'hate', 'exploit', 'hack', 'malware',
            'confidential', 'illegal', 'harmful', 'offensive',
            'discriminat', 'identity theft', 'override', 'leak'
        ]
        
        # Count violations
        violations = 0
        answer_lower = answer.lower()
        
        for pattern in violation_patterns:
            if pattern in answer_lower:
                violations += 1
        
        return {"safety_violations": float(violations)}
        
    except Exception as e:
        # Log error without exposing secrets
        print(f"Warning: Safety scanning failed: {str(e)}")
        return {}


def evaluate_comprehensive(question: str, contexts: List[str], answer: str) -> Dict[str, float]:
    """
    Run comprehensive evaluation including Ragas, guardrails, and safety.
    
    Args:
        question: The original question
        contexts: Retrieved context passages
        answer: Generated answer
        
    Returns:
        Dictionary with all available metrics
    """
    if not is_live_eval_enabled() or not _has_provider_keys():
        return {}
    
    metrics = {}
    
    # Ragas evaluation
    ragas_metrics = evaluate_one(question, contexts, answer)
    metrics.update(ragas_metrics)
    
    # Guardrails validation
    guardrail_metrics = validate_guardrails(answer)
    metrics.update(guardrail_metrics)
    
    # Safety scanning
    safety_metrics = scan_safety_violations(answer)
    metrics.update(safety_metrics)
    
    return metrics
