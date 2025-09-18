"""Performance metrics collection and analysis for Production Readiness."""

import time
import psutil
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Performance metrics data structure."""
    cold_start_ms: float = 0.0
    warm_p95_ms: float = 0.0
    throughput_rps: float = 0.0
    memory_usage_mb: float = 0.0
    estimator_vs_actuals: Dict[str, Any] = None
    dedupe_savings: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.estimator_vs_actuals is None:
            self.estimator_vs_actuals = {}
        if self.dedupe_savings is None:
            self.dedupe_savings = {}


class PerformanceCollector:
    """Collects performance metrics during test execution."""
    
    def __init__(self):
        self.start_time: Optional[float] = None
        self.cold_start_recorded = False
        self.cold_start_ms = 0.0
        self.response_times: List[float] = []
        self.memory_samples: List[float] = []
        self.request_count = 0
        self.dedupe_stats = {
            "total_tests": 0,
            "cached_tests": 0,
            "time_saved_ms": 0.0
        }
        self.estimator_data = {
            "estimated_duration_ms": 0,
            "estimated_cost_usd": 0.0,
            "actual_duration_ms": 0,
            "actual_cost_usd": 0.0
        }
    
    def start_collection(self):
        """Start performance metrics collection."""
        self.start_time = time.time()
        logger.info("Performance metrics collection started")
    
    def record_cold_start(self, duration_ms: float):
        """Record cold start latency."""
        if not self.cold_start_recorded:
            self.cold_start_ms = duration_ms
            self.cold_start_recorded = True
            logger.info(f"Cold start recorded: {duration_ms:.2f}ms")
    
    def record_response_time(self, duration_ms: float):
        """Record individual response time."""
        self.response_times.append(duration_ms)
        self.request_count += 1
    
    def record_memory_sample(self):
        """Record current memory usage sample."""
        try:
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            self.memory_samples.append(memory_mb)
        except Exception as e:
            logger.warning(f"Failed to collect memory sample: {e}")
    
    def record_dedupe_hit(self, time_saved_ms: float = 0.0):
        """Record a cache hit for deduplication."""
        self.dedupe_stats["cached_tests"] += 1
        self.dedupe_stats["time_saved_ms"] += time_saved_ms
    
    def record_test_execution(self, cached: bool = False):
        """Record test execution (cached or fresh)."""
        self.dedupe_stats["total_tests"] += 1
        if cached:
            self.record_dedupe_hit()
    
    def set_estimator_data(self, estimated_duration_ms: float, estimated_cost_usd: float):
        """Set estimator predictions."""
        self.estimator_data["estimated_duration_ms"] = estimated_duration_ms
        self.estimator_data["estimated_cost_usd"] = estimated_cost_usd
    
    def finalize_actuals(self, actual_duration_ms: float, actual_cost_usd: float):
        """Set actual measurements."""
        self.estimator_data["actual_duration_ms"] = actual_duration_ms
        self.estimator_data["actual_cost_usd"] = actual_cost_usd
    
    def calculate_p95_latency(self) -> float:
        """Calculate 95th percentile latency."""
        if not self.response_times:
            return 0.0
        
        sorted_times = sorted(self.response_times)
        p95_index = int(len(sorted_times) * 0.95)
        return sorted_times[p95_index] if p95_index < len(sorted_times) else sorted_times[-1]
    
    def calculate_throughput(self) -> float:
        """Calculate requests per second."""
        if not self.start_time or self.request_count == 0:
            return 0.0
        
        elapsed_seconds = time.time() - self.start_time
        return self.request_count / elapsed_seconds if elapsed_seconds > 0 else 0.0
    
    def get_peak_memory(self) -> float:
        """Get peak memory usage in MB."""
        return max(self.memory_samples) if self.memory_samples else 0.0
    
    def calculate_dedupe_savings(self) -> Dict[str, Any]:
        """Calculate deduplication savings."""
        total_tests = self.dedupe_stats["total_tests"]
        cached_tests = self.dedupe_stats["cached_tests"]
        
        if total_tests == 0:
            return {"percentage": 0.0, "tests_saved": 0, "time_saved_ms": 0.0}
        
        percentage = (cached_tests / total_tests) * 100
        
        return {
            "percentage": percentage,
            "tests_saved": cached_tests,
            "time_saved_ms": self.dedupe_stats["time_saved_ms"],
            "total_tests": total_tests
        }
    
    def get_estimator_accuracy(self) -> Dict[str, Any]:
        """Calculate estimator vs actual accuracy."""
        estimated_duration = self.estimator_data["estimated_duration_ms"]
        actual_duration = self.estimator_data["actual_duration_ms"]
        estimated_cost = self.estimator_data["estimated_cost_usd"]
        actual_cost = self.estimator_data["actual_cost_usd"]
        
        duration_accuracy = 0.0
        cost_accuracy = 0.0
        
        if estimated_duration > 0 and actual_duration > 0:
            duration_error = abs(estimated_duration - actual_duration) / estimated_duration
            duration_accuracy = max(0.0, 1.0 - duration_error)
        
        if estimated_cost > 0 and actual_cost > 0:
            cost_error = abs(estimated_cost - actual_cost) / estimated_cost
            cost_accuracy = max(0.0, 1.0 - cost_error)
        
        return {
            "duration_accuracy": duration_accuracy,
            "cost_accuracy": cost_accuracy,
            "estimated_duration_ms": estimated_duration,
            "actual_duration_ms": actual_duration,
            "estimated_cost_usd": estimated_cost,
            "actual_cost_usd": actual_cost
        }
    
    def generate_metrics(self) -> PerformanceMetrics:
        """Generate final performance metrics."""
        # Record final memory sample
        self.record_memory_sample()
        
        # Use recorded cold start or first response time as fallback
        cold_start_ms = self.cold_start_ms
        if cold_start_ms == 0.0 and self.response_times:
            cold_start_ms = self.response_times[0]
        
        return PerformanceMetrics(
            cold_start_ms=cold_start_ms,
            warm_p95_ms=self.calculate_p95_latency(),
            throughput_rps=self.calculate_throughput(),
            memory_usage_mb=self.get_peak_memory(),
            estimator_vs_actuals=self.get_estimator_accuracy(),
            dedupe_savings=self.calculate_dedupe_savings()
        )


class EstimatorEngine:
    """Enhanced estimator with dedupe savings and performance predictions."""
    
    # Static per-test constants (in ms and USD)
    BASE_ESTIMATES = {
        "rag_reliability_robustness": {"duration_ms": 2000, "cost_usd": 0.05},
        "red_team": {"duration_ms": 1500, "cost_usd": 0.03},
        "safety": {"duration_ms": 1200, "cost_usd": 0.02},
        "bias": {"duration_ms": 1800, "cost_usd": 0.04},
        "performance": {"duration_ms": 3000, "cost_usd": 0.01},
        "guardrails": {"duration_ms": 500, "cost_usd": 0.005}
    }
    
    @classmethod
    def estimate_test_run(
        cls, 
        selected_tests: Dict[str, List[str]], 
        dedupe_fingerprints: Optional[List[str]] = None,
        provider_performance: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """Estimate test run duration and cost with dedupe savings."""
        
        total_duration_ms = 0
        total_cost_usd = 0.0
        test_count = 0
        dedupe_savings = {"tests_saved": 0, "time_saved_ms": 0, "cost_saved_usd": 0.0}
        
        # Count dedupe fingerprints if provided
        cached_fingerprints = set(dedupe_fingerprints or [])
        
        for suite_id, test_ids in selected_tests.items():
            suite_estimates = cls.BASE_ESTIMATES.get(suite_id, {"duration_ms": 1000, "cost_usd": 0.02})
            
            for test_id in test_ids:
                test_count += 1
                
                # Create test fingerprint (simplified)
                test_fingerprint = f"{suite_id}:{test_id}"
                
                if test_fingerprint in cached_fingerprints:
                    # Dedupe hit - much faster
                    dedupe_duration = suite_estimates["duration_ms"] * 0.1  # 10% of original time
                    dedupe_cost = 0.0  # No API cost for cached results
                    
                    total_duration_ms += dedupe_duration
                    total_cost_usd += dedupe_cost
                    
                    # Track savings
                    dedupe_savings["tests_saved"] += 1
                    dedupe_savings["time_saved_ms"] += suite_estimates["duration_ms"] - dedupe_duration
                    dedupe_savings["cost_saved_usd"] += suite_estimates["cost_usd"]
                else:
                    # Fresh execution
                    duration = suite_estimates["duration_ms"]
                    cost = suite_estimates["cost_usd"]
                    
                    # Apply provider performance multiplier if available
                    if provider_performance and suite_id in provider_performance:
                        duration *= provider_performance[suite_id]
                    
                    total_duration_ms += duration
                    total_cost_usd += cost
        
        # Calculate dedupe percentage
        dedupe_percentage = (dedupe_savings["tests_saved"] / test_count * 100) if test_count > 0 else 0.0
        
        return {
            "total_tests": test_count,
            "estimated_duration_ms": total_duration_ms,
            "estimated_cost_usd": total_cost_usd,
            "dedupe_savings": {
                **dedupe_savings,
                "percentage": dedupe_percentage
            }
        }


# Global performance collector instance
_performance_collector: Optional[PerformanceCollector] = None


def get_performance_collector() -> PerformanceCollector:
    """Get or create global performance collector."""
    global _performance_collector
    if _performance_collector is None:
        _performance_collector = PerformanceCollector()
    return _performance_collector


def reset_performance_collector():
    """Reset global performance collector."""
    global _performance_collector
    _performance_collector = PerformanceCollector()
