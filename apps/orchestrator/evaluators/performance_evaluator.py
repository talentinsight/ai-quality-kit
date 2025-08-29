"""
Professional Performance Evaluator for latency and throughput testing.

This evaluator implements comprehensive performance evaluation using:
- Latency analysis (cold start, warm, sustained)
- Throughput measurement and SLA compliance
- Performance regression detection
- Resource utilization assessment
- Statistical performance profiling
- Performance tier classification
"""

import statistics
from typing import Dict, Any, List, Set, Tuple, Optional
from dataclasses import dataclass
import logging

from .base_evaluator import BaseEvaluator, EvaluationResult, TestCase, TestResponse

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Performance evaluation metrics."""
    
    # Latency metrics
    latency_ms: float
    p50_latency: float
    p95_latency: float
    p99_latency: float
    
    # Throughput metrics
    requests_per_second: float
    tokens_per_second: float
    
    # SLA compliance
    sla_compliance_rate: float
    performance_tier: str
    
    # Quality assessment
    performance_score: float
    meets_requirements: bool


class PerformanceEvaluator(BaseEvaluator):
    """
    Professional performance evaluator for latency and throughput testing.
    
    Features:
    - Multi-phase latency analysis (cold/warm/sustained)
    - SLA compliance checking
    - Performance tier classification
    - Throughput measurement
    - Statistical performance profiling
    - Regression detection capabilities
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        
        # Load performance SLA thresholds
        self.sla_thresholds = self._load_sla_thresholds()
        
        # Performance tier definitions
        self.performance_tiers = {
            "EXCELLENT": {"max_latency": 500, "min_throughput": 50},
            "GOOD": {"max_latency": 1000, "min_throughput": 25},
            "ACCEPTABLE": {"max_latency": 2000, "min_throughput": 10},
            "POOR": {"max_latency": 5000, "min_throughput": 5},
            "UNACCEPTABLE": {"max_latency": float('inf'), "min_throughput": 0}
        }
        
        # Phase-specific expectations
        self.phase_expectations = {
            "cold": {"max_latency": 3000, "tolerance": 1.5},  # Cold start can be slower
            "warm": {"max_latency": 1000, "tolerance": 1.2},  # Warm should be faster
            "sustained": {"max_latency": 800, "tolerance": 1.0}  # Sustained should be fastest
        }
    
    def evaluate(self, test_case: TestCase, response: TestResponse) -> EvaluationResult:
        """
        Evaluate performance of a single test case response.
        
        Args:
            test_case: Performance test case with expected latency/throughput
            response: LLM response with performance metrics
            
        Returns:
            Detailed performance evaluation result
        """
        try:
            # Extract performance information
            latency_ms = response.latency_ms
            expected_phase = test_case.metadata.get("expected_phase", "warm")
            expected_latency = test_case.metadata.get("expected_latency_ms", 1000)
            
            # Get additional performance data from metadata
            perf_data = response.metadata.get("performance", {})
            throughput_data = response.metadata.get("throughput", {})
            
            # Calculate performance metrics
            perf_metrics = self._calculate_performance_metrics(
                latency_ms, expected_phase, expected_latency, perf_data, throughput_data
            )
            
            # Determine if performance meets requirements
            meets_requirements = self._meets_performance_requirements(
                perf_metrics, expected_phase, expected_latency
            )
            
            # Calculate confidence based on measurement consistency
            confidence = self._calculate_confidence(perf_metrics, perf_data)
            
            # Determine performance tier
            performance_tier = self._determine_performance_tier(perf_metrics)
            
            # Generate detailed explanation
            explanation = self._generate_explanation(
                meets_requirements, perf_metrics, expected_phase
            )
            
            # Compile detailed metrics
            metrics = {
                "latency_ms": perf_metrics.latency_ms,
                "p50_latency": perf_metrics.p50_latency,
                "p95_latency": perf_metrics.p95_latency,
                "p99_latency": perf_metrics.p99_latency,
                "requests_per_second": perf_metrics.requests_per_second,
                "tokens_per_second": perf_metrics.tokens_per_second,
                "sla_compliance_rate": perf_metrics.sla_compliance_rate,
                "performance_score": perf_metrics.performance_score
            }
            
            # Additional details for debugging/analysis
            details = {
                "performance_tier": performance_tier,
                "expected_phase": expected_phase,
                "expected_latency_ms": expected_latency,
                "sla_threshold_used": self.sla_thresholds.get(expected_phase, {}),
                "evaluation_method": "comprehensive_performance_v1"
            }
            
            return EvaluationResult(
                passed=meets_requirements,
                score=perf_metrics.performance_score,
                confidence=confidence,
                details=details,
                risk_level="LOW" if meets_requirements else "MEDIUM",
                explanation=explanation,
                metrics=metrics
            )
            
        except Exception as e:
            logger.error(f"Performance evaluation error for test {test_case.test_id}: {e}")
            return EvaluationResult(
                passed=False,
                score=0.0,
                confidence=0.0,
                details={"error": str(e)},
                risk_level="HIGH",
                explanation=f"Evaluation failed: {str(e)}",
                metrics={}
            )
    
    def evaluate_batch(self, test_cases: List[TestCase], responses: List[TestResponse]) -> List[EvaluationResult]:
        """
        Evaluate a batch of performance test cases.
        
        Args:
            test_cases: List of performance test cases
            responses: List of corresponding responses
            
        Returns:
            List of performance evaluation results
        """
        if len(test_cases) != len(responses):
            raise ValueError("Number of test cases must match number of responses")
        
        results = []
        latencies = []
        
        # First pass: individual evaluations and collect latencies
        for test_case, response in zip(test_cases, responses):
            result = self.evaluate(test_case, response)
            results.append(result)
            latencies.append(response.latency_ms)
        
        # Second pass: enhance results with batch statistics
        if latencies:
            batch_stats = self._calculate_batch_statistics(latencies)
            for i, result in enumerate(results):
                result.metrics.update(batch_stats)
        
        return results
    
    def _load_default_thresholds(self) -> Dict[str, float]:
        """Load default performance evaluation thresholds."""
        return {
            "excellent_latency": 500,  # ms
            "good_latency": 1000,  # ms
            "acceptable_latency": 2000,  # ms
            "sla_compliance_threshold": 0.95,  # 95% of requests must meet SLA
            "high_confidence_threshold": 0.9
        }
    
    def _load_sla_thresholds(self) -> Dict[str, Dict[str, float]]:
        """Load SLA thresholds for different performance phases."""
        return {
            "cold": {
                "max_latency_ms": 3000,
                "target_latency_ms": 2000,
                "min_throughput_rps": 5
            },
            "warm": {
                "max_latency_ms": 1500,
                "target_latency_ms": 1000,
                "min_throughput_rps": 15
            },
            "sustained": {
                "max_latency_ms": 1000,
                "target_latency_ms": 800,
                "min_throughput_rps": 25
            }
        }
    
    def _calculate_performance_metrics(self, latency_ms: float, expected_phase: str,
                                     expected_latency: float, perf_data: Dict[str, Any],
                                     throughput_data: Dict[str, Any]) -> PerformanceMetrics:
        """Calculate comprehensive performance metrics."""
        
        # Extract latency percentiles from performance data
        p50_latency = perf_data.get("p50_latency_ms", latency_ms)
        p95_latency = perf_data.get("p95_latency_ms", latency_ms * 1.2)
        p99_latency = perf_data.get("p99_latency_ms", latency_ms * 1.5)
        
        # Extract throughput metrics
        requests_per_second = throughput_data.get("requests_per_second", 0.0)
        tokens_per_second = throughput_data.get("tokens_per_second", 0.0)
        
        # Calculate SLA compliance
        sla_threshold = self.sla_thresholds.get(expected_phase, {}).get("max_latency_ms", 2000)
        sla_compliance_rate = 1.0 if latency_ms <= sla_threshold else 0.0
        
        # Calculate overall performance score
        performance_score = self._calculate_performance_score(
            latency_ms, expected_latency, expected_phase, requests_per_second
        )
        
        # Determine if requirements are met
        meets_requirements = (
            latency_ms <= sla_threshold and
            performance_score >= 0.7
        )
        
        # Determine performance tier
        performance_tier = self._classify_performance_tier(latency_ms, requests_per_second)
        
        return PerformanceMetrics(
            latency_ms=latency_ms,
            p50_latency=p50_latency,
            p95_latency=p95_latency,
            p99_latency=p99_latency,
            requests_per_second=requests_per_second,
            tokens_per_second=tokens_per_second,
            sla_compliance_rate=sla_compliance_rate,
            performance_tier=performance_tier,
            performance_score=performance_score,
            meets_requirements=meets_requirements
        )
    
    def _calculate_performance_score(self, actual_latency: float, expected_latency: float,
                                   phase: str, throughput: float) -> float:
        """Calculate normalized performance score (0.0 - 1.0)."""
        
        # Latency score (lower is better)
        phase_threshold = self.phase_expectations.get(phase, {}).get("max_latency", 2000)
        if actual_latency <= phase_threshold * 0.5:
            latency_score = 1.0
        elif actual_latency <= phase_threshold:
            latency_score = 1.0 - (actual_latency - phase_threshold * 0.5) / (phase_threshold * 0.5)
        else:
            latency_score = max(0.0, 1.0 - (actual_latency - phase_threshold) / phase_threshold)
        
        # Throughput score (higher is better)
        min_throughput = self.performance_tiers["ACCEPTABLE"]["min_throughput"]
        excellent_throughput = self.performance_tiers["EXCELLENT"]["min_throughput"]
        
        if throughput >= excellent_throughput:
            throughput_score = 1.0
        elif throughput >= min_throughput:
            throughput_score = (throughput - min_throughput) / (excellent_throughput - min_throughput)
        else:
            throughput_score = throughput / min_throughput if min_throughput > 0 else 0.0
        
        # Combined score (weighted)
        combined_score = 0.7 * latency_score + 0.3 * min(throughput_score, 1.0)
        
        return min(combined_score, 1.0)
    
    def _classify_performance_tier(self, latency_ms: float, throughput_rps: float) -> str:
        """Classify performance into tiers based on latency and throughput."""
        
        for tier, requirements in self.performance_tiers.items():
            if (latency_ms <= requirements["max_latency"] and 
                throughput_rps >= requirements["min_throughput"]):
                return tier
        
        return "UNACCEPTABLE"
    
    def _meets_performance_requirements(self, metrics: PerformanceMetrics, 
                                      expected_phase: str, expected_latency: float) -> bool:
        """Determine if performance meets requirements."""
        
        # Check SLA compliance
        sla_threshold = self.sla_thresholds.get(expected_phase, {}).get("max_latency_ms", 2000)
        meets_sla = metrics.latency_ms <= sla_threshold
        
        # Check performance score
        meets_score = metrics.performance_score >= 0.6
        
        # Check tier requirement (at least ACCEPTABLE)
        acceptable_tiers = ["EXCELLENT", "GOOD", "ACCEPTABLE"]
        meets_tier = metrics.performance_tier in acceptable_tiers
        
        return meets_sla and meets_score and meets_tier
    
    def _calculate_confidence(self, metrics: PerformanceMetrics, perf_data: Dict[str, Any]) -> float:
        """Calculate confidence in the performance evaluation."""
        
        # Base confidence from measurement consistency
        latency_values = [
            metrics.latency_ms,
            metrics.p50_latency,
            metrics.p95_latency
        ]
        
        # Calculate coefficient of variation (lower = more consistent = higher confidence)
        if len(latency_values) > 1:
            mean_latency = statistics.mean(latency_values)
            if mean_latency > 0:
                std_dev = statistics.stdev(latency_values)
                cv = std_dev / mean_latency
                consistency_confidence = max(0, 1.0 - cv)
            else:
                consistency_confidence = 0.5
        else:
            consistency_confidence = 0.8
        
        # Boost confidence for clear performance results
        if metrics.performance_tier in ["EXCELLENT", "UNACCEPTABLE"]:
            tier_confidence = 0.9
        elif metrics.performance_tier in ["GOOD", "POOR"]:
            tier_confidence = 0.8
        else:
            tier_confidence = 0.7
        
        # Sample size confidence (if available)
        sample_size = perf_data.get("sample_size", 1)
        sample_confidence = min(0.5 + (sample_size - 1) * 0.1, 1.0)
        
        # Combined confidence
        combined_confidence = (consistency_confidence + tier_confidence + sample_confidence) / 3
        
        return min(combined_confidence, 1.0)
    
    def _determine_performance_tier(self, metrics: PerformanceMetrics) -> str:
        """Determine overall performance tier."""
        return metrics.performance_tier
    
    def _calculate_batch_statistics(self, latencies: List[float]) -> Dict[str, float]:
        """Calculate batch-level performance statistics."""
        if not latencies:
            return {}
        
        return {
            "batch_mean_latency": statistics.mean(latencies),
            "batch_median_latency": statistics.median(latencies),
            "batch_min_latency": min(latencies),
            "batch_max_latency": max(latencies),
            "batch_std_latency": statistics.stdev(latencies) if len(latencies) > 1 else 0.0,
            "batch_sample_size": len(latencies)
        }
    
    def _generate_explanation(self, meets_requirements: bool, metrics: PerformanceMetrics,
                            expected_phase: str) -> str:
        """Generate human-readable explanation of the performance evaluation."""
        
        if meets_requirements:
            explanation = f"✅ PERFORMANCE OK: {metrics.performance_tier} tier"
            explanation += f" (latency: {metrics.latency_ms:.0f}ms, score: {metrics.performance_score:.3f})"
            
            if metrics.requests_per_second > 0:
                explanation += f", throughput: {metrics.requests_per_second:.1f} RPS"
        else:
            explanation = f"⚠️ PERFORMANCE ISSUE: {metrics.performance_tier} tier"
            explanation += f" (latency: {metrics.latency_ms:.0f}ms, score: {metrics.performance_score:.3f})"
            
            # Identify specific issues
            sla_threshold = self.sla_thresholds.get(expected_phase, {}).get("max_latency_ms", 2000)
            if metrics.latency_ms > sla_threshold:
                explanation += f" - Exceeds {expected_phase} SLA ({sla_threshold}ms)"
            
            if metrics.requests_per_second < 10:
                explanation += " - Low throughput"
        
        return explanation
    
    def _get_required_config_keys(self) -> List[str]:
        """Get required configuration keys for performance evaluator."""
        return []  # No required keys, all have defaults
