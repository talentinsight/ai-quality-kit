"""
Evaluator Factory for creating and managing test suite evaluators.

This factory provides a clean interface for:
- Creating appropriate evaluators for each test suite
- Managing evaluator configurations
- Handling fallback to legacy evaluation methods
- Providing consistent evaluation interfaces
"""

from typing import Dict, Any, Optional, Union, List
import logging

from .base_evaluator import BaseEvaluator, EvaluationResult, TestCase, TestResponse

logger = logging.getLogger(__name__)


class EvaluatorFactory:
    """
    Factory class for creating and managing test suite evaluators.
    
    Features:
    - Automatic evaluator selection based on suite type
    - Configuration management for evaluators
    - Graceful fallback to legacy evaluation
    - Consistent evaluation interface
    - Debug logging and error handling
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._evaluator_cache: Dict[str, BaseEvaluator] = {}
        
        # Suite to evaluator mapping
        self.suite_evaluator_map = {
            "safety": "SafetyEvaluator",
            "red_team": "RedTeamEvaluator",  # Red team uses specialized evaluator
            "bias_smoke": "BiasEvaluator",
            "rag_reliability_robustness": "RAGEvaluator",
            "rag_quality": "RAGEvaluator",
            "performance": "PerformanceEvaluator"
        }
        
        # Import paths for evaluators (absolute imports for subprocess compatibility)
        self.evaluator_imports = {
            "SafetyEvaluator": "evaluators.safety_evaluator",
            "RedTeamEvaluator": "evaluators.red_team_evaluator",
            "BiasEvaluator": "evaluators.bias_evaluator", 
            "RAGEvaluator": "evaluators.rag_evaluator",
            "PerformanceEvaluator": "evaluators.performance_evaluator"
        }
    
    def get_evaluator(self, suite: str) -> Optional[BaseEvaluator]:
        """
        Get or create an evaluator for the specified test suite.
        
        Args:
            suite: Test suite name (e.g., 'safety', 'bias_smoke', etc.)
            
        Returns:
            Evaluator instance or None if not available
        """
        try:
            # Check if evaluator is already cached
            if suite in self._evaluator_cache:
                return self._evaluator_cache[suite]
            
            # Get evaluator class name
            evaluator_class_name = self.suite_evaluator_map.get(suite)
            if not evaluator_class_name:
                logger.debug(f"No professional evaluator available for suite: {suite}")
                return None
            
            # Import and create evaluator
            evaluator = self._create_evaluator(evaluator_class_name, suite)
            if evaluator:
                self._evaluator_cache[suite] = evaluator
                logger.info(f"Created professional evaluator for suite: {suite}")
            
            return evaluator
            
        except Exception as e:
            logger.error(f"Failed to create evaluator for suite {suite}: {e}")
            return None
    
    def evaluate_test_result(self, suite: str, test_item: Dict[str, Any], 
                           test_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate a test result using the appropriate evaluator.
        
        Args:
            suite: Test suite name
            test_item: Test case data
            test_result: Test execution result
            
        Returns:
            Evaluation result dictionary
        """
        try:
            # Enable Ragas for RAG suites with proper fallback
            if suite in ["rag_reliability_robustness", "rag_quality"]:
                logger.info(f"🎯 RAGAS: Attempting Ragas evaluation for {suite} with fallback to legacy")
                # Use existing evaluator creation flow but enable Ragas
                pass  # Fall through to normal evaluator creation
            
            # Get evaluator for this suite
            evaluator = self.get_evaluator(suite)
            if not evaluator:
                logger.debug(f"No professional evaluator for {suite}, using legacy evaluation")
                return self._legacy_evaluation_placeholder(suite, test_item, test_result)
            
            # Convert to standard format
            test_case = self._convert_to_test_case(test_item, suite)
            test_response = self._convert_to_test_response(test_result)
            
            # Perform evaluation
            logger.debug(f"🔍 EVALUATOR DEBUG: Starting {suite} evaluation with professional evaluator")
            eval_result = evaluator.evaluate(test_case, test_response)
            
            # Log evaluation details
            logger.debug(f"🔍 EVALUATOR DEBUG: {suite} evaluation completed")
            logger.debug(f"🔍 EVALUATOR DEBUG: Score: {eval_result.score:.3f}, Passed: {eval_result.passed}")
            logger.debug(f"🔍 EVALUATOR DEBUG: Confidence: {eval_result.confidence:.3f}, Risk: {eval_result.risk_level}")
            logger.debug(f"🔍 EVALUATOR DEBUG: Explanation: {eval_result.explanation}")
            
            # Convert back to legacy format for backward compatibility
            return self._convert_to_legacy_format(eval_result, suite)
            
        except ImportError as e:
            logger.warning(f"Professional evaluator unavailable for {suite}: {e}")
            return self._legacy_evaluation_placeholder(suite, test_item, test_result)
        
        except Exception as e:
            logger.error(f"Professional evaluator error for {suite}: {e}")
            return self._legacy_evaluation_placeholder(suite, test_item, test_result)
    
    def _create_evaluator(self, evaluator_class_name: str, suite: str) -> Optional[BaseEvaluator]:
        """Create an evaluator instance."""
        try:
            # Get import path
            import_path = self.evaluator_imports.get(evaluator_class_name)
            if not import_path:
                logger.error(f"No import path for evaluator: {evaluator_class_name}")
                return None
            
            # Dynamic import
            module = __import__(import_path, fromlist=[evaluator_class_name])
            evaluator_class = getattr(module, evaluator_class_name)
            
            # Create instance with suite-specific config
            suite_config = self.config.get(suite, {})
            evaluator = evaluator_class(suite_config)
            
            logger.debug(f"Successfully created {evaluator_class_name} for {suite}")
            return evaluator
            
        except Exception as e:
            logger.error(f"Failed to create {evaluator_class_name}: {e}")
            return None
    
    def _convert_to_test_case(self, test_item: Dict[str, Any], suite: str) -> TestCase:
        """Convert test item to standardized TestCase format."""
        return TestCase(
            test_id=test_item.get("test_id", "unknown"),
            query=test_item.get("query", ""),
            expected_behavior=test_item.get("expected_behavior", self._get_default_behavior(suite)),
            category=test_item.get("category", suite),
            severity=test_item.get("severity", "medium"),
            tags=test_item.get("tags", []),
            metadata=test_item
        )
    
    def _convert_to_test_response(self, test_result: Dict[str, Any]) -> TestResponse:
        """Convert test result to standardized TestResponse format."""
        return TestResponse(
            answer=test_result.get("answer", ""),
            context=test_result.get("context", []),
            latency_ms=test_result.get("latency_ms", 0.0),
            provider=test_result.get("provider", "unknown"),
            model=test_result.get("model", "unknown"),
            metadata=test_result
        )
    
    def _convert_to_legacy_format(self, eval_result: EvaluationResult, suite: str) -> Dict[str, Any]:
        """Convert EvaluationResult back to legacy format for backward compatibility."""
        
        # Base evaluation result
        evaluation = {
            "passed": eval_result.passed,
            "score": eval_result.score,
            "confidence": eval_result.confidence,
            "explanation": eval_result.explanation,
            "risk_level": eval_result.risk_level,
            "details": eval_result.details,
            "metrics": eval_result.metrics
        }
        
        # Suite-specific mappings for backward compatibility
        if suite in ["safety", "red_team"]:
            evaluation.update({
                "attack_success": not eval_result.passed,
                "safety_score": eval_result.score,
                "safety_details": eval_result.details
            })
        
        elif suite == "bias_smoke":
            evaluation.update({
                "bias_detected": not eval_result.passed,
                "fairness_score": eval_result.score,
                "bias_details": eval_result.details
            })
        
        elif suite in ["rag_reliability_robustness", "rag_quality"]:
            evaluation.update({
                "rag_quality_score": eval_result.score,
                "rag_details": eval_result.details,
                "faithfulness_score": eval_result.metrics.get("faithfulness_score", 0.0),
                "relevance_score": eval_result.metrics.get("answer_relevance_score", 0.0),
                # Legacy compatibility fields
                "faithfulness": eval_result.metrics.get("faithfulness", 0.8 if eval_result.passed else 0.3),
                "context_recall": eval_result.metrics.get("context_recall", 0.7 if eval_result.passed else 0.4)
            })
        
        elif suite == "performance":
            evaluation.update({
                "performance_score": eval_result.score,
                "performance_details": eval_result.details,
                "latency_ms": eval_result.metrics.get("latency_ms", 0.0),
                "performance_tier": eval_result.details.get("performance_tier", "UNKNOWN")
            })
        
        return evaluation
    
    def _get_default_behavior(self, suite: str) -> str:
        """Get default expected behavior for a suite."""
        defaults = {
            "safety": "refuse_harmful_request",
            "red_team": "block_adversarial_attack", 
            "bias_smoke": "fair_treatment",
            "rag_reliability_robustness": "accurate_retrieval",
            "rag_quality": "accurate_retrieval",
            "performance": "meet_sla_requirements"
        }
        return defaults.get(suite, "appropriate_response")
    
    def _legacy_evaluation_placeholder(self, suite: str, test_item: Dict[str, Any], 
                                     test_result: Dict[str, Any]) -> Dict[str, Any]:
        """Placeholder for legacy evaluation - indicates fallback needed."""
        return {
            "passed": False,
            "score": 0.0,
            "confidence": 0.0,
            "explanation": f"Legacy evaluation needed for {suite}",
            "risk_level": "UNKNOWN",
            "details": {"fallback_required": True, "suite": suite},
            "metrics": {},
            "requires_legacy_fallback": True
        }
    
    def get_available_suites(self) -> List[str]:
        """Get list of suites with professional evaluators available."""
        return list(self.suite_evaluator_map.keys())
    
    def clear_cache(self):
        """Clear the evaluator cache."""
        self._evaluator_cache.clear()
        logger.debug("Evaluator cache cleared")
    
    def get_evaluator_info(self, suite: str) -> Dict[str, Any]:
        """Get information about the evaluator for a suite."""
        evaluator_class = self.suite_evaluator_map.get(suite)
        if not evaluator_class:
            return {"available": False, "reason": "No evaluator defined"}
        
        try:
            evaluator = self.get_evaluator(suite)
            if evaluator:
                return {
                    "available": True,
                    "class": evaluator_class,
                    "thresholds": evaluator.thresholds,
                    "config": evaluator.config
                }
            else:
                return {"available": False, "reason": "Failed to create evaluator"}
        except Exception as e:
            return {"available": False, "reason": str(e)}
