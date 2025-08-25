"""Oracle and evaluation system for enhanced test quality."""

import re
import unicodedata
from typing import Dict, List, Optional, Any, Tuple
import logging

from .schema_v2 import TestCaseV2, OracleType, get_effective_oracle_type

logger = logging.getLogger(__name__)


class EvaluationResult:
    """Result of test case evaluation with detailed metadata."""
    
    def __init__(self, passed: bool, score: float = 0.0, details: Optional[Dict[str, Any]] = None):
        self.passed = passed
        self.score = score
        self.details = details or {}
        self.oracle_used: Optional[str] = None
        self.secondary_guards_triggered: List[str] = []


class TextNormalizer:
    """Utility for normalizing text before comparison."""
    
    @staticmethod
    def normalize(text: str) -> str:
        """Apply minimal normalization to reduce false negatives."""
        if not text:
            return ""
        
        # Remove common markdown/quote artifacts
        text = re.sub(r'^["\']|["\']$', '', text.strip())
        text = re.sub(r'^```.*?```$', lambda m: m.group(0)[3:-3], text, flags=re.DOTALL)
        
        # Normalize unicode and whitespace
        text = unicodedata.normalize('NFKD', text)
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Collapse repeated punctuation
        text = re.sub(r'([.!?]){2,}', r'\1', text)
        
        return text.lower()


class PrimaryOracles:
    """Primary oracle implementations for different evaluation types."""
    
    @staticmethod
    def exact(actual: str, expected: str) -> EvaluationResult:
        """Exact string equality oracle."""
        normalized_actual = TextNormalizer.normalize(actual)
        normalized_expected = TextNormalizer.normalize(expected)
        
        passed = normalized_actual == normalized_expected
        score = 1.0 if passed else 0.0
        
        return EvaluationResult(
            passed=passed,
            score=score,
            details={
                "oracle_type": "exact",
                "normalized_actual": normalized_actual,
                "normalized_expected": normalized_expected
            }
        )
    
    @staticmethod
    def contains(actual: str, expected: str) -> EvaluationResult:
        """Substring containment oracle with normalization."""
        normalized_actual = TextNormalizer.normalize(actual)
        normalized_expected = TextNormalizer.normalize(expected)
        
        passed = normalized_expected in normalized_actual
        score = 1.0 if passed else 0.0
        
        return EvaluationResult(
            passed=passed,
            score=score,
            details={
                "oracle_type": "contains",
                "normalized_actual": normalized_actual,
                "normalized_expected": normalized_expected
            }
        )
    
    @staticmethod
    def regex(actual: str, pattern: str) -> EvaluationResult:
        """Regex oracle with safe compilation and word boundaries."""
        try:
            # Make pattern word-boundary aware if not already
            if not pattern.startswith(r'\b') and not pattern.startswith('^'):
                pattern = r'\b' + pattern
            if not pattern.endswith(r'\b') and not pattern.endswith('$'):
                pattern = pattern + r'\b'
            
            compiled_pattern = re.compile(pattern, re.IGNORECASE | re.MULTILINE)
            normalized_actual = TextNormalizer.normalize(actual)
            
            match = compiled_pattern.search(normalized_actual)
            passed = match is not None
            score = 1.0 if passed else 0.0
            
            return EvaluationResult(
                passed=passed,
                score=score,
                details={
                    "oracle_type": "regex",
                    "pattern": pattern,
                    "match_found": bool(match),
                    "match_span": match.span() if match else None
                }
            )
            
        except re.error as e:
            logger.warning(f"Invalid regex pattern '{pattern}': {e}")
            return EvaluationResult(
                passed=False,
                score=0.0,
                details={
                    "oracle_type": "regex",
                    "error": f"Invalid pattern: {e}",
                    "pattern": pattern
                }
            )
    
    @staticmethod
    def semantic(actual: str, expected: str, min_threshold: float = 0.8) -> EvaluationResult:
        """Semantic similarity oracle with fallback to contains."""
        try:
            # Try to use existing semantic scoring if available
            score = SemanticScorer.compute_similarity(actual, expected)
            passed = score >= min_threshold
            
            return EvaluationResult(
                passed=passed,
                score=score,
                details={
                    "oracle_type": "semantic",
                    "similarity_score": score,
                    "threshold": min_threshold,
                    "method": "semantic_model"
                }
            )
            
        except Exception as e:
            logger.debug(f"Semantic scoring unavailable, falling back to contains: {e}")
            # Fallback to contains oracle
            result = PrimaryOracles.contains(actual, expected)
            result.details["oracle_type"] = "semantic_fallback"
            result.details["fallback_reason"] = str(e)
            return result


class SemanticScorer:
    """Semantic similarity computation (placeholder for existing scoring)."""
    
    @staticmethod
    def compute_similarity(actual: str, expected: str) -> float:
        """Compute semantic similarity between two texts."""
        # Placeholder: In real implementation, this would use:
        # - Existing RAGAS scoring if available
        # - Sentence transformers
        # - Other semantic models in the repo
        
        # For now, use a simple heuristic as fallback
        normalized_actual = TextNormalizer.normalize(actual)
        normalized_expected = TextNormalizer.normalize(expected)
        
        if not normalized_expected:
            return 1.0 if not normalized_actual else 0.0
        
        # Simple token overlap as basic semantic proxy
        actual_tokens = set(normalized_actual.split())
        expected_tokens = set(normalized_expected.split())
        
        if not expected_tokens:
            return 1.0
        
        intersection = actual_tokens & expected_tokens
        return len(intersection) / len(expected_tokens)


class SecondaryGuards:
    """Secondary guards to reduce false positives."""
    
    # Simple forbidden patterns that often indicate failure
    FORBIDDEN_PATTERNS = [
        r'\b(error|exception|failed|cannot|unable)\b',
        r'\b(sorry|apologize|can\'t help)\b',
        r'\b(not available|not found|no information)\b'
    ]
    
    @staticmethod
    def check_forbidden_patterns(text: str) -> List[str]:
        """Check for patterns that indicate failure even if oracle passes."""
        triggered = []
        normalized_text = TextNormalizer.normalize(text)
        
        for pattern in SecondaryGuards.FORBIDDEN_PATTERNS:
            if re.search(pattern, normalized_text, re.IGNORECASE):
                triggered.append(pattern)
        
        return triggered
    
    @staticmethod
    def apply_guards(result: EvaluationResult, actual_text: str) -> EvaluationResult:
        """Apply secondary guards to an oracle result."""
        if not result.passed:
            return result  # Already failed, no need for additional checks
        
        forbidden = SecondaryGuards.check_forbidden_patterns(actual_text)
        
        if forbidden:
            result.passed = False
            result.secondary_guards_triggered = forbidden
            result.details["secondary_guard_failure"] = forbidden
            logger.debug(f"Secondary guard triggered: {forbidden}")
        
        return result


class TestEvaluator:
    """Main evaluator that orchestrates two-stage evaluation."""
    
    def evaluate_case(self, case: TestCaseV2, actual_output: str) -> EvaluationResult:
        """Evaluate a test case using two-stage oracle + guards."""
        oracle_type = get_effective_oracle_type(case)
        
        # Stage 1: Primary oracle
        if oracle_type == "exact":
            result = PrimaryOracles.exact(actual_output, case.expected_answer or "")
        elif oracle_type == "contains":
            result = PrimaryOracles.contains(actual_output, case.expected_answer or "")
        elif oracle_type == "regex":
            result = PrimaryOracles.regex(actual_output, case.expected_answer or "")
        elif oracle_type == "semantic":
            min_threshold = 0.8
            if case.acceptance and case.acceptance.min_semantic:
                min_threshold = case.acceptance.min_semantic
            result = PrimaryOracles.semantic(actual_output, case.expected_answer or "", min_threshold)
        else:
            result = EvaluationResult(
                passed=False,
                score=0.0,
                details={"error": f"Unknown oracle type: {oracle_type}"}
            )
        
        result.oracle_used = oracle_type
        
        # Stage 2: Secondary guards (only for semantic and contains)
        if oracle_type in ["semantic", "contains"]:
            result = SecondaryGuards.apply_guards(result, actual_output)
        
        return result
