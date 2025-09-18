"""Performance metrics provider for latency and cost gates."""

import logging
import time
from typing import Optional, Dict, Any
from ..interfaces import GuardrailProvider, SignalResult, SignalLabel, GuardrailCategory
from ..registry import register_provider

logger = logging.getLogger(__name__)


@register_provider("performance.metrics", GuardrailCategory.LATENCY)
class PerformanceMetricsProvider(GuardrailProvider):
    """Performance metrics provider for latency and cost monitoring."""
    
    def __init__(self):
        super().__init__("performance.metrics", GuardrailCategory.LATENCY)
        self.requires_llm = True  # Needs orchestrator timing data
        self._available = True
    
    def is_available(self) -> bool:
        """Always available (uses orchestrator metrics)."""
        return self._available
    
    def check_dependencies(self) -> list[str]:
        """No external dependencies."""
        return []
    
    @property
    def version(self) -> Optional[str]:
        """Get provider version."""
        return "1.0.0"
    
    async def check(self, input_text: str, output_text: Optional[str] = None, 
                   metrics: Optional[Dict[str, Any]] = None) -> SignalResult:
        """Check performance metrics against thresholds."""
        if not self.is_available():
            return SignalResult(
                id=self.provider_id,
                category=self.category,
                score=0.0,
                label=SignalLabel.UNAVAILABLE,
                confidence=0.0,
                details={"missing_dep": True}
            )
        
        # Extract metrics from orchestrator
        if not metrics:
            return SignalResult(
                id=self.provider_id,
                category=self.category,
                score=0.0,
                label=SignalLabel.CLEAN,
                confidence=0.5,
                details={"no_metrics": True}
            )
        
        # Extract performance data
        latency_ms = metrics.get("latency_ms", 0)
        p95_latency_ms = metrics.get("p95_latency_ms", latency_ms)  # Use p95 if available
        token_count = metrics.get("token_count", 0)
        cost_per_test = metrics.get("cost_per_test", 0.0)
        
        # Default thresholds from requirements
        latency_p95_threshold_ms = metrics.get("latency_p95_ms", 3000)  # 3000ms default
        cost_per_test_threshold = metrics.get("cost_per_test_threshold", 0.01)  # $0.01 default
        
        # Calculate violation scores (1.0 if exceeds threshold, 0.0 if within)
        latency_violation = 1.0 if p95_latency_ms > latency_p95_threshold_ms else 0.0
        cost_violation = 1.0 if cost_per_test > cost_per_test_threshold else 0.0
        
        # Overall score (max of violations - any violation is a problem)
        score = max(latency_violation, cost_violation)
        confidence = 0.9  # High confidence in metrics
        
        # Determine violations
        violations = []
        if latency_violation > 0:
            violations.append("latency_p95_exceeded")
        if cost_violation > 0:
            violations.append("cost_per_test_exceeded")
        
        # Determine label based on violations
        if score >= 1.0:
            label = SignalLabel.VIOLATION
        elif score > 0.0:
            label = SignalLabel.HIT
        else:
            label = SignalLabel.CLEAN
        
        return SignalResult(
            id=self.provider_id,
            category=self.category,
            score=score,
            label=label,
            confidence=confidence,
            details={
                "latency_ms": latency_ms,
                "p95_latency_ms": p95_latency_ms,
                "token_count": token_count,
                "cost_per_test": cost_per_test,
                "thresholds": {
                    "latency_p95_ms": latency_p95_threshold_ms,
                    "cost_per_test": cost_per_test_threshold
                },
                "violations": {
                    "latency": latency_violation > 0,
                    "cost": cost_violation > 0
                },
                "violation_details": violations
            }
        )


@register_provider("rate_cost.limits", GuardrailCategory.RATE_COST)
class RateCostLimitsProvider(GuardrailProvider):
    """Rate and cost limits provider."""
    
    def __init__(self):
        super().__init__("rate_cost.limits", GuardrailCategory.RATE_COST)
        self.requires_llm = True
        self._available = True
    
    def is_available(self) -> bool:
        """Always available."""
        return self._available
    
    def check_dependencies(self) -> list[str]:
        """No external dependencies."""
        return []
    
    @property
    def version(self) -> Optional[str]:
        """Get provider version."""
        return "1.0.0"
    
    async def check(self, input_text: str, output_text: Optional[str] = None,
                   metrics: Optional[Dict[str, Any]] = None) -> SignalResult:
        """Check rate and cost limits."""
        if not self.is_available():
            return SignalResult(
                id=self.provider_id,
                category=self.category,
                score=0.0,
                label=SignalLabel.UNAVAILABLE,
                confidence=0.0,
                details={"missing_dep": True}
            )
        
        if not metrics:
            return SignalResult(
                id=self.provider_id,
                category=self.category,
                score=0.0,
                label=SignalLabel.CLEAN,
                confidence=0.5,
                details={"no_metrics": True}
            )
        
        # Extract rate/cost data
        requests_per_minute = metrics.get("requests_per_minute", 0)
        cost_per_minute = metrics.get("cost_per_minute", 0.0)
        tokens_per_minute = metrics.get("tokens_per_minute", 0)
        
        # Default limits
        rps_limit = metrics.get("rps_limit", 60)  # 60 RPM
        cost_limit = metrics.get("cost_limit_per_minute", 10.0)  # $10/min
        token_limit = metrics.get("token_limit_per_minute", 100000)  # 100k tokens/min
        
        # Calculate utilization scores
        rps_score = min(1.0, requests_per_minute / rps_limit) if rps_limit > 0 else 0.0
        cost_score = min(1.0, cost_per_minute / cost_limit) if cost_limit > 0 else 0.0
        token_score = min(1.0, tokens_per_minute / token_limit) if token_limit > 0 else 0.0
        
        # Overall score
        score = max(rps_score, cost_score, token_score)
        confidence = 0.8
        
        # Determine label
        if score > 0.9:
            label = SignalLabel.VIOLATION
        elif score > 0.7:
            label = SignalLabel.HIT
        else:
            label = SignalLabel.CLEAN
        
        return SignalResult(
            id=self.provider_id,
            category=self.category,
            score=score,
            label=label,
            confidence=confidence,
            details={
                "current": {
                    "requests_per_minute": requests_per_minute,
                    "cost_per_minute": cost_per_minute,
                    "tokens_per_minute": tokens_per_minute
                },
                "limits": {
                    "rps": rps_limit,
                    "cost": cost_limit,
                    "tokens": token_limit
                },
                "utilization": {
                    "rps": rps_score,
                    "cost": cost_score,
                    "tokens": token_score
                }
            }
        )
