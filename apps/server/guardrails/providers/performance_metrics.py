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
        token_count = metrics.get("token_count", 0)
        cost_usd = metrics.get("cost_usd", 0.0)
        
        # Default thresholds (can be overridden by config)
        latency_threshold_ms = metrics.get("latency_threshold_ms", 30000)  # 30s
        cost_threshold_usd = metrics.get("cost_threshold_usd", 1.0)  # $1
        token_threshold = metrics.get("token_threshold", 10000)  # 10k tokens
        
        # Calculate scores for each metric
        latency_score = min(1.0, latency_ms / latency_threshold_ms) if latency_threshold_ms > 0 else 0.0
        cost_score = min(1.0, cost_usd / cost_threshold_usd) if cost_threshold_usd > 0 else 0.0
        token_score = min(1.0, token_count / token_threshold) if token_threshold > 0 else 0.0
        
        # Overall score (max of individual scores)
        score = max(latency_score, cost_score, token_score)
        confidence = 0.9  # High confidence in metrics
        
        # Determine violations
        violations = []
        if latency_score > 0.8:
            violations.append("high_latency")
        if cost_score > 0.8:
            violations.append("high_cost")
        if token_score > 0.8:
            violations.append("high_tokens")
        
        # Determine label
        if score > 0.8:
            label = SignalLabel.VIOLATION
        elif score > 0.5:
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
                "token_count": token_count,
                "cost_usd": cost_usd,
                "thresholds": {
                    "latency_ms": latency_threshold_ms,
                    "cost_usd": cost_threshold_usd,
                    "tokens": token_threshold
                },
                "scores": {
                    "latency": latency_score,
                    "cost": cost_score,
                    "tokens": token_score
                },
                "violations": violations
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
