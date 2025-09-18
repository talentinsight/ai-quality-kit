"""Cross-suite deduplication service for reusing Guardrails Preflight signals."""

import hashlib
import logging
from typing import Dict, Any, Optional, List, Set, Tuple
from dataclasses import dataclass
from apps.server.guardrails.interfaces import SignalResult

logger = logging.getLogger(__name__)


@dataclass
class DeduplicationFingerprint:
    """Fingerprint for cross-suite deduplication."""
    provider_id: str
    metric_id: str
    stage: str
    model: str
    rules_hash: str
    
    def to_key(self) -> str:
        """Convert fingerprint to cache key."""
        content = f"{self.provider_id}:{self.metric_id}:{self.stage}:{self.model}:{self.rules_hash}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]


@dataclass
class ReusedSignal:
    """Signal that was reused from preflight."""
    original_signal: SignalResult
    reused_from: str  # "preflight"
    fingerprint: str
    suite: str
    test_id: str


class CrossSuiteDeduplicationService:
    """Service for managing cross-suite deduplication of signals."""
    
    def __init__(self, run_id: str):
        self.run_id = run_id
        self._signal_cache: Dict[str, SignalResult] = {}
        self._reused_signals: Dict[str, ReusedSignal] = {}
        self._fingerprint_to_suite_map: Dict[str, str] = {}
        
    def create_fingerprint(
        self, 
        provider_id: str, 
        metric_id: str, 
        stage: str, 
        model: str, 
        rules_hash: str
    ) -> DeduplicationFingerprint:
        """Create a deduplication fingerprint."""
        return DeduplicationFingerprint(
            provider_id=provider_id,
            metric_id=metric_id,
            stage=stage,
            model=model,
            rules_hash=rules_hash
        )
    
    def store_preflight_signal(self, signal: SignalResult, model: str, rules_hash: str) -> None:
        """Store a preflight signal for potential reuse."""
        # Extract or create fingerprint components
        provider_id = signal.id
        metric_id = signal.category.value
        stage = "preflight"
        
        fingerprint = self.create_fingerprint(
            provider_id=provider_id,
            metric_id=metric_id,
            stage=stage,
            model=model,
            rules_hash=rules_hash
        )
        
        fingerprint_key = fingerprint.to_key()
        
        # Store signal with enhanced details
        enhanced_signal = SignalResult(
            id=signal.id,
            category=signal.category,
            score=signal.score,
            label=signal.label,
            confidence=signal.confidence,
            details={
                **signal.details,
                "fingerprint": fingerprint_key,
                "dedup_stage": stage,
                "dedup_model": model,
                "dedup_rules_hash": rules_hash
            },
            requires=signal.requires
        )
        
        self._signal_cache[fingerprint_key] = enhanced_signal
        self._fingerprint_to_suite_map[fingerprint_key] = "preflight"
        
        logger.debug(f"Stored preflight signal {provider_id} with fingerprint {fingerprint_key}")
    
    def check_signal_reusable(
        self, 
        provider_id: str, 
        metric_id: str, 
        stage: str, 
        model: str, 
        rules_hash: str
    ) -> Optional[SignalResult]:
        """Check if a signal can be reused from preflight."""
        fingerprint = self.create_fingerprint(
            provider_id=provider_id,
            metric_id=metric_id,
            stage=stage,
            model=model,
            rules_hash=rules_hash
        )
        
        fingerprint_key = fingerprint.to_key()
        
        if fingerprint_key in self._signal_cache:
            original_signal = self._signal_cache[fingerprint_key]
            logger.debug(f"Found reusable signal for {provider_id} from {self._fingerprint_to_suite_map.get(fingerprint_key, 'unknown')}")
            return original_signal
        
        return None
    
    def mark_signal_reused(
        self, 
        signal: SignalResult, 
        suite: str, 
        test_id: str
    ) -> ReusedSignal:
        """Mark a signal as reused and track it."""
        fingerprint_key = signal.details.get("fingerprint", "")
        original_suite = self._fingerprint_to_suite_map.get(fingerprint_key, "preflight")
        
        reused_signal = ReusedSignal(
            original_signal=signal,
            reused_from=original_suite,
            fingerprint=fingerprint_key,
            suite=suite,
            test_id=test_id
        )
        
        reuse_key = f"{suite}:{test_id}:{fingerprint_key}"
        self._reused_signals[reuse_key] = reused_signal
        
        logger.info(f"Marked signal {signal.id} as reused from {original_suite} in {suite}:{test_id}")
        return reused_signal
    
    def get_reused_signals_for_suite(self, suite: str) -> List[ReusedSignal]:
        """Get all reused signals for a specific suite."""
        return [
            reused for reused in self._reused_signals.values()
            if reused.suite == suite
        ]
    
    def get_reuse_statistics(self) -> Dict[str, Any]:
        """Get statistics about signal reuse."""
        total_cached = len(self._signal_cache)
        total_reused = len(self._reused_signals)
        
        reuse_by_suite = {}
        for reused in self._reused_signals.values():
            suite = reused.suite
            if suite not in reuse_by_suite:
                reuse_by_suite[suite] = 0
            reuse_by_suite[suite] += 1
        
        return {
            "total_cached_signals": total_cached,
            "total_reused_signals": total_reused,
            "reuse_by_suite": reuse_by_suite,
            "reuse_rate": total_reused / max(total_cached, 1)
        }
    
    def create_enhanced_signal_for_reuse(
        self, 
        original_signal: SignalResult, 
        suite: str, 
        test_id: str
    ) -> SignalResult:
        """Create an enhanced signal marked as reused."""
        return SignalResult(
            id=original_signal.id,
            category=original_signal.category,
            score=original_signal.score,
            label=original_signal.label,
            confidence=original_signal.confidence,
            details={
                **original_signal.details,
                "reused_from_preflight": True,
                "reused_in_suite": suite,
                "reused_in_test": test_id,
                "original_stage": original_signal.details.get("dedup_stage", "preflight")
            },
            requires=original_signal.requires
        )


class SuiteDeduplicationHelper:
    """Helper class for suite-specific deduplication logic."""
    
    def __init__(self, dedup_service: CrossSuiteDeduplicationService):
        self.dedup_service = dedup_service
    
    def check_safety_signal_reusable(
        self, 
        provider_id: str, 
        category: str, 
        model: str, 
        rules_hash: str
    ) -> Optional[SignalResult]:
        """Check if a safety signal can be reused."""
        return self.dedup_service.check_signal_reusable(
            provider_id=provider_id,
            metric_id=category,
            stage="safety",
            model=model,
            rules_hash=rules_hash
        )
    
    def check_red_team_signal_reusable(
        self, 
        provider_id: str, 
        attack_type: str, 
        model: str, 
        rules_hash: str
    ) -> Optional[SignalResult]:
        """Check if a red team signal can be reused."""
        return self.dedup_service.check_signal_reusable(
            provider_id=provider_id,
            metric_id=attack_type,
            stage="red_team",
            model=model,
            rules_hash=rules_hash
        )
    
    def check_performance_signal_reusable(
        self, 
        provider_id: str, 
        metric_type: str, 
        model: str, 
        rules_hash: str
    ) -> Optional[SignalResult]:
        """Check if a performance signal can be reused."""
        return self.dedup_service.check_signal_reusable(
            provider_id=provider_id,
            metric_id=metric_type,
            stage="performance",
            model=model,
            rules_hash=rules_hash
        )
    
    def check_bias_signal_reusable(
        self, 
        provider_id: str, 
        bias_type: str, 
        model: str, 
        rules_hash: str
    ) -> Optional[SignalResult]:
        """Check if a bias signal can be reused."""
        return self.dedup_service.check_signal_reusable(
            provider_id=provider_id,
            metric_id=bias_type,
            stage="bias",
            model=model,
            rules_hash=rules_hash
        )
    
    def check_pi_quickset_signal_reusable(
        self, 
        provider_id: str, 
        quickset_item_id: str, 
        model: str, 
        rules_hash: str
    ) -> Optional[SignalResult]:
        """Check if a PI quickset signal can be reused."""
        return self.dedup_service.check_signal_reusable(
            provider_id=provider_id,
            metric_id=quickset_item_id,
            stage="preflight",
            model=model,
            rules_hash=rules_hash
        )
    
    def check_pi_quickset_asr_reusable(
        self, 
        provider_id: str, 
        model: str, 
        rules_hash: str
    ) -> Optional[SignalResult]:
        """Check if a PI quickset ASR signal can be reused."""
        return self.dedup_service.check_signal_reusable(
            provider_id=provider_id,
            metric_id="asr",
            stage="preflight",
            model=model,
            rules_hash=rules_hash
        )
    
    def check_pi_quickset_item_reusable(
        self, 
        provider_id: str, 
        item_id: str,
        model: str, 
        rules_hash: str
    ) -> Optional[SignalResult]:
        """Check if a specific PI quickset item can be reused."""
        return self.dedup_service.check_signal_reusable(
            provider_id=provider_id,
            metric_id=item_id,
            stage="preflight",
            model=model,
            rules_hash=rules_hash
        )
    
    def check_rag_signal_reusable(
        self, 
        provider_id: str, 
        rag_metric: str, 
        model: str, 
        rules_hash: str
    ) -> Optional[SignalResult]:
        """Check if a RAG signal can be reused."""
        return self.dedup_service.check_signal_reusable(
            provider_id=provider_id,
            metric_id=rag_metric,
            stage="rag",
            model=model,
            rules_hash=rules_hash
        )


def create_rules_hash(config: Dict[str, Any]) -> str:
    """Create a hash of the rules configuration for fingerprinting."""
    # Sort the config to ensure consistent hashing
    config_str = str(sorted(config.items())) if config else ""
    return hashlib.sha256(config_str.encode()).hexdigest()[:16]


def extract_provider_mapping() -> Dict[str, Set[str]]:
    """Extract mapping of guardrail categories to suite providers."""
    return {
        "pii": {"safety", "red_team"},
        "jailbreak": {"red_team", "safety"},
        "toxicity": {"safety", "red_team"},
        "adult": {"safety"},
        "self_harm": {"safety"},
        "bias": {"bias"},
        "latency": {"performance"},
        "rate_cost": {"performance"},
        "schema": {"rag"},
        "resilience": {"performance", "red_team"}
    }
