"""Anti-flake harness for detecting and quarantining unstable test cases."""

import random
from typing import Dict, List, Optional, Any, Callable
import logging

from .schema_v2 import TestCaseV2, QualityGuardOptions, is_critical_case
from .oracles import TestEvaluator, EvaluationResult

logger = logging.getLogger(__name__)


class StabilityResult:
    """Result of stability testing for a test case."""
    
    def __init__(self, case_id: str, is_stable: bool, results: List[EvaluationResult]):
        self.case_id = case_id
        self.is_stable = is_stable
        self.results = results
        self.consensus_result = None
        
        if results:
            # Use first result as consensus if stable, or majority vote
            if is_stable:
                self.consensus_result = results[0]
            else:
                # For unstable cases, try to find consensus among results
                passes = sum(1 for r in results if r.passed)
                self.consensus_result = results[0]  # Fallback to first
                self.consensus_result.passed = passes > len(results) // 2


class AntiFlakeHarness:
    """Harness for detecting flaky/unstable test cases through repetition."""
    
    def __init__(self, options: QualityGuardOptions):
        self.options = options
        self.evaluator = TestEvaluator()
        self.quarantined_cases = set()
        self.stability_results: Dict[str, StabilityResult] = {}
    
    def should_test_stability(self, case: TestCaseV2) -> bool:
        """Determine if a case should be tested for stability."""
        if not self.options.enabled:
            return False
        
        # Always test critical cases (up to sample limit)
        if is_critical_case(case):
            critical_count = sum(
                1 for result in self.stability_results.values() 
                if result.case_id.startswith("critical_")  # Simplified check based on naming
            )
            return critical_count < self.options.sample_criticals
        
        # Could add other sampling strategies here
        # For now, only test critical cases
        return False
    
    def run_stability_test(
        self, 
        case: TestCaseV2, 
        test_runner: Callable[[TestCaseV2], str]
    ) -> StabilityResult:
        """Run stability test by repeating the same case multiple times."""
        if case.test_id in self.stability_results:
            return self.stability_results[case.test_id]
        
        logger.debug(f"Running stability test for case {case.test_id}")
        
        # Set deterministic seed for reproducibility
        if case.deterministic_seed is not None:
            random.seed(case.deterministic_seed)
        
        results = []
        
        try:
            for attempt in range(self.options.repeat_n):
                logger.debug(f"Stability test attempt {attempt + 1}/{self.options.repeat_n} for {case.test_id}")
                
                # Run the actual test
                actual_output = test_runner(case)
                
                # Evaluate the result
                eval_result = self.evaluator.evaluate_case(case, actual_output)
                eval_result.details["stability_attempt"] = attempt + 1
                results.append(eval_result)
        
        except Exception as e:
            logger.error(f"Error during stability test for {case.test_id}: {e}")
            # Create a failure result
            error_result = EvaluationResult(
                passed=False,
                score=0.0,
                details={"stability_error": str(e)}
            )
            results = [error_result]
        
        # Analyze stability
        is_stable = self._analyze_stability(results)
        
        stability_result = StabilityResult(case.test_id, is_stable, results)
        self.stability_results[case.test_id] = stability_result
        
        if not is_stable:
            self.quarantined_cases.add(case.test_id)
            logger.warning(f"Case {case.test_id} marked as unstable and quarantined")
        
        return stability_result
    
    def _analyze_stability(self, results: List[EvaluationResult]) -> bool:
        """Analyze if results show stable behavior."""
        if len(results) < 2:
            return True  # Not enough data to determine instability
        
        # Check if all results have the same pass/fail outcome
        outcomes = [result.passed for result in results]
        all_same_outcome = all(outcome == outcomes[0] for outcome in outcomes)
        
        if not all_same_outcome:
            return False
        
        # For semantic/scoring oracles, also check score variance
        scores = [result.score for result in results if result.score is not None]
        if len(scores) >= 2:
            score_variance = self._calculate_variance(scores)
            # Consider unstable if score variance is too high
            if score_variance > 0.1:  # 10% variance threshold
                return False
        
        return True
    
    def _calculate_variance(self, scores: List[float]) -> float:
        """Calculate variance of scores."""
        if len(scores) < 2:
            return 0.0
        
        mean = sum(scores) / len(scores)
        variance = sum((score - mean) ** 2 for score in scores) / len(scores)
        return variance
    
    def is_quarantined(self, case_id: str) -> bool:
        """Check if a case is quarantined due to instability."""
        return case_id in self.quarantined_cases
    
    def get_stability_summary(self) -> Dict[str, Any]:
        """Get summary of stability testing results."""
        stable_count = sum(1 for result in self.stability_results.values() if result.is_stable)
        unstable_count = len(self.stability_results) - stable_count
        
        return {
            "total_tested": len(self.stability_results),
            "stable_cases": stable_count,
            "unstable_cases": unstable_count,
            "quarantined_cases": len(self.quarantined_cases),
            "stability_rate": stable_count / len(self.stability_results) if self.stability_results else 1.0
        }
    
    def get_consensus_result(self, case_id: str) -> Optional[EvaluationResult]:
        """Get the consensus result for a case, if stability tested."""
        if case_id in self.stability_results:
            return self.stability_results[case_id].consensus_result
        return None


class QualityGuardRegistry:
    """Registry for managing quality guard state across test runs."""
    
    def __init__(self):
        self.harnesses: Dict[str, AntiFlakeHarness] = {}
    
    def get_harness(self, run_id: str, options: QualityGuardOptions) -> AntiFlakeHarness:
        """Get or create an anti-flake harness for a test run."""
        if run_id not in self.harnesses:
            self.harnesses[run_id] = AntiFlakeHarness(options)
        return self.harnesses[run_id]
    
    def cleanup_run(self, run_id: str):
        """Clean up harness data for a completed run."""
        self.harnesses.pop(run_id, None)
    
    def get_global_summary(self) -> Dict[str, Any]:
        """Get global summary across all active runs."""
        total_tested = sum(len(harness.stability_results) for harness in self.harnesses.values())
        total_quarantined = sum(len(harness.quarantined_cases) for harness in self.harnesses.values())
        
        return {
            "active_runs": len(self.harnesses),
            "total_tested": total_tested,
            "total_quarantined": total_quarantined
        }


# Global registry instance
_quality_guard_registry = QualityGuardRegistry()


def get_quality_guard_registry() -> QualityGuardRegistry:
    """Get the global quality guard registry."""
    return _quality_guard_registry
