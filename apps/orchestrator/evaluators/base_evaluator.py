"""
Base evaluator class for all test suite evaluators.

This module provides the abstract base class that all specific evaluators
must inherit from, ensuring consistent interface and behavior.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class EvaluationResult:
    """Standard evaluation result structure."""
    passed: bool
    score: float  # 0.0 - 1.0 scale
    confidence: float  # 0.0 - 1.0 confidence in the result
    details: Dict[str, Any]
    risk_level: str  # LOW, MEDIUM, HIGH, CRITICAL
    explanation: str
    metrics: Dict[str, float]  # Additional metrics
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "passed": self.passed,
            "score": self.score,
            "confidence": self.confidence,
            "details": self.details,
            "risk_level": self.risk_level,
            "explanation": self.explanation,
            "metrics": self.metrics
        }


@dataclass
class TestCase:
    """Standard test case structure."""
    test_id: str
    query: str
    expected_behavior: str
    category: str
    severity: str
    tags: List[str]
    metadata: Dict[str, Any]


@dataclass
class TestResponse:
    """Standard test response structure."""
    answer: str
    context: List[str]
    latency_ms: float
    provider: str
    model: str
    metadata: Dict[str, Any]


class BaseEvaluator(ABC):
    """
    Abstract base class for all test suite evaluators.
    
    Each evaluator is responsible for:
    1. Understanding its specific test suite requirements
    2. Implementing domain-specific evaluation logic
    3. Providing consistent result format
    4. Supporting configurable thresholds
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize evaluator with configuration.
        
        Args:
            config: Evaluator-specific configuration dictionary
        """
        self.config = config or {}
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Load default thresholds (can be overridden by config)
        self.thresholds = self._load_default_thresholds()
        if "thresholds" in self.config:
            self.thresholds.update(self.config["thresholds"])
    
    @abstractmethod
    def evaluate(self, test_case: TestCase, response: TestResponse) -> EvaluationResult:
        """
        Evaluate a single test case response.
        
        Args:
            test_case: The test case that was executed
            response: The response from the LLM
            
        Returns:
            EvaluationResult with detailed evaluation metrics
        """
        pass
    
    @abstractmethod
    def evaluate_batch(self, test_cases: List[TestCase], responses: List[TestResponse]) -> List[EvaluationResult]:
        """
        Evaluate a batch of test cases (for efficiency).
        
        Args:
            test_cases: List of test cases
            responses: List of corresponding responses
            
        Returns:
            List of evaluation results
        """
        pass
    
    @abstractmethod
    def _load_default_thresholds(self) -> Dict[str, float]:
        """
        Load default thresholds for this evaluator.
        
        Returns:
            Dictionary of threshold values
        """
        pass
    
    def get_suite_name(self) -> str:
        """Get the name of the test suite this evaluator handles."""
        return self.__class__.__name__.replace("Evaluator", "").lower()
    
    def validate_config(self) -> bool:
        """
        Validate evaluator configuration.
        
        Returns:
            True if configuration is valid
        """
        try:
            required_keys = self._get_required_config_keys()
            for key in required_keys:
                if key not in self.config:
                    self.logger.error(f"Missing required config key: {key}")
                    return False
            return True
        except Exception as e:
            self.logger.error(f"Config validation error: {e}")
            return False
    
    def _get_required_config_keys(self) -> List[str]:
        """
        Get list of required configuration keys.
        
        Returns:
            List of required config keys (override in subclasses)
        """
        return []
    
    def get_evaluation_summary(self, results: List[EvaluationResult]) -> Dict[str, Any]:
        """
        Generate summary statistics for a batch of evaluation results.
        
        Args:
            results: List of evaluation results
            
        Returns:
            Summary statistics dictionary
        """
        if not results:
            return {"total": 0, "passed": 0, "failed": 0, "pass_rate": 0.0}
        
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        failed = total - passed
        
        scores = [r.score for r in results]
        avg_score = sum(scores) / len(scores) if scores else 0.0
        
        confidences = [r.confidence for r in results]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        
        risk_levels = {}
        for result in results:
            risk_level = result.risk_level
            risk_levels[risk_level] = risk_levels.get(risk_level, 0) + 1
        
        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": passed / total,
            "average_score": avg_score,
            "average_confidence": avg_confidence,
            "risk_distribution": risk_levels,
            "suite": self.get_suite_name()
        }
