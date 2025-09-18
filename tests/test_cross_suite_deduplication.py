"""Tests for cross-suite deduplication functionality."""

import pytest
from unittest.mock import Mock, patch
from apps.orchestrator.deduplication import (
    CrossSuiteDeduplicationService,
    SuiteDeduplicationHelper,
    DeduplicationFingerprint,
    create_rules_hash
)
from apps.server.guardrails.interfaces import SignalResult, SignalLabel, GuardrailCategory


class TestDeduplicationFingerprint:
    """Test the fingerprint generation system."""
    
    def test_fingerprint_creation(self):
        """Test creating a deduplication fingerprint."""
        fingerprint = DeduplicationFingerprint(
            provider_id="pii.presidio",
            metric_id="pii",
            stage="preflight",
            model="gpt-4",
            rules_hash="abc123"
        )
        
        assert fingerprint.provider_id == "pii.presidio"
        assert fingerprint.metric_id == "pii"
        assert fingerprint.stage == "preflight"
        assert fingerprint.model == "gpt-4"
        assert fingerprint.rules_hash == "abc123"
    
    def test_fingerprint_to_key(self):
        """Test converting fingerprint to cache key."""
        fingerprint = DeduplicationFingerprint(
            provider_id="pii.presidio",
            metric_id="pii",
            stage="preflight",
            model="gpt-4",
            rules_hash="abc123"
        )
        
        key = fingerprint.to_key()
        assert isinstance(key, str)
        assert len(key) == 16  # SHA256 truncated to 16 chars
        
        # Same fingerprint should produce same key
        fingerprint2 = DeduplicationFingerprint(
            provider_id="pii.presidio",
            metric_id="pii",
            stage="preflight",
            model="gpt-4",
            rules_hash="abc123"
        )
        assert fingerprint2.to_key() == key
    
    def test_fingerprint_uniqueness(self):
        """Test that different fingerprints produce different keys."""
        fp1 = DeduplicationFingerprint("pii.presidio", "pii", "preflight", "gpt-4", "abc123")
        fp2 = DeduplicationFingerprint("toxicity.guard", "toxicity", "preflight", "gpt-4", "abc123")
        fp3 = DeduplicationFingerprint("pii.presidio", "pii", "safety", "gpt-4", "abc123")
        fp4 = DeduplicationFingerprint("pii.presidio", "pii", "preflight", "gpt-3.5", "abc123")
        fp5 = DeduplicationFingerprint("pii.presidio", "pii", "preflight", "gpt-4", "def456")
        
        keys = [fp1.to_key(), fp2.to_key(), fp3.to_key(), fp4.to_key(), fp5.to_key()]
        assert len(set(keys)) == 5  # All keys should be unique


class TestCrossSuiteDeduplicationService:
    """Test the main deduplication service."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.service = CrossSuiteDeduplicationService("test_run_123")
        self.sample_signal = SignalResult(
            id="pii.presidio",
            category=GuardrailCategory.PII,
            score=0.0,
            label=SignalLabel.CLEAN,
            confidence=1.0,
            details={"total_hits": 0, "entity_types": []}
        )
    
    def test_service_initialization(self):
        """Test service initialization."""
        assert self.service.run_id == "test_run_123"
        assert len(self.service._signal_cache) == 0
        assert len(self.service._reused_signals) == 0
        assert len(self.service._fingerprint_to_suite_map) == 0
    
    def test_store_preflight_signal(self):
        """Test storing a preflight signal."""
        self.service.store_preflight_signal(
            signal=self.sample_signal,
            model="gpt-4",
            rules_hash="abc123"
        )
        
        assert len(self.service._signal_cache) == 1
        assert len(self.service._fingerprint_to_suite_map) == 1
        
        # Check that the signal was enhanced with dedup info
        cached_signals = list(self.service._signal_cache.values())
        cached_signal = cached_signals[0]
        assert "fingerprint" in cached_signal.details
        assert "dedup_stage" in cached_signal.details
        assert "dedup_model" in cached_signal.details
        assert "dedup_rules_hash" in cached_signal.details
        assert cached_signal.details["dedup_stage"] == "preflight"
        assert cached_signal.details["dedup_model"] == "gpt-4"
        assert cached_signal.details["dedup_rules_hash"] == "abc123"
    
    def test_check_signal_reusable(self):
        """Test checking if a signal can be reused."""
        # Store a signal first
        self.service.store_preflight_signal(
            signal=self.sample_signal,
            model="gpt-4",
            rules_hash="abc123"
        )
        
        # Check for reusable signal with same parameters
        reusable = self.service.check_signal_reusable(
            provider_id="pii.presidio",
            metric_id="pii",
            stage="safety",  # Different stage but same provider/model/rules
            model="gpt-4",
            rules_hash="abc123"
        )
        
        assert reusable is not None
        assert reusable.id == "pii.presidio"
        assert reusable.category == GuardrailCategory.PII
    
    def test_check_signal_not_reusable(self):
        """Test checking for non-existent signal."""
        # Don't store any signals
        
        reusable = self.service.check_signal_reusable(
            provider_id="pii.presidio",
            metric_id="pii",
            stage="safety",
            model="gpt-4",
            rules_hash="abc123"
        )
        
        assert reusable is None
    
    def test_mark_signal_reused(self):
        """Test marking a signal as reused."""
        # Store a signal first
        self.service.store_preflight_signal(
            signal=self.sample_signal,
            model="gpt-4",
            rules_hash="abc123"
        )
        
        # Get the cached signal
        cached_signal = list(self.service._signal_cache.values())[0]
        
        # Mark it as reused
        reused_signal = self.service.mark_signal_reused(
            signal=cached_signal,
            suite="safety",
            test_id="safety_test_1"
        )
        
        assert reused_signal.original_signal == cached_signal
        assert reused_signal.reused_from == "preflight"
        assert reused_signal.suite == "safety"
        assert reused_signal.test_id == "safety_test_1"
        
        # Check that it was added to reused signals
        assert len(self.service._reused_signals) == 1
    
    def test_get_reused_signals_for_suite(self):
        """Test getting reused signals for a specific suite."""
        # Store and mark signals as reused for different suites
        self.service.store_preflight_signal(self.sample_signal, "gpt-4", "abc123")
        cached_signal = list(self.service._signal_cache.values())[0]
        
        self.service.mark_signal_reused(cached_signal, "safety", "safety_test_1")
        self.service.mark_signal_reused(cached_signal, "red_team", "red_team_test_1")
        
        safety_reused = self.service.get_reused_signals_for_suite("safety")
        red_team_reused = self.service.get_reused_signals_for_suite("red_team")
        bias_reused = self.service.get_reused_signals_for_suite("bias")
        
        assert len(safety_reused) == 1
        assert len(red_team_reused) == 1
        assert len(bias_reused) == 0
        
        assert safety_reused[0].suite == "safety"
        assert red_team_reused[0].suite == "red_team"
    
    def test_get_reuse_statistics(self):
        """Test getting reuse statistics."""
        # Initially empty
        stats = self.service.get_reuse_statistics()
        assert stats["total_cached_signals"] == 0
        assert stats["total_reused_signals"] == 0
        assert stats["reuse_by_suite"] == {}
        assert stats["reuse_rate"] == 0.0
        
        # Store and reuse some signals
        self.service.store_preflight_signal(self.sample_signal, "gpt-4", "abc123")
        cached_signal = list(self.service._signal_cache.values())[0]
        
        self.service.mark_signal_reused(cached_signal, "safety", "safety_test_1")
        self.service.mark_signal_reused(cached_signal, "red_team", "red_team_test_1")
        
        stats = self.service.get_reuse_statistics()
        assert stats["total_cached_signals"] == 1
        assert stats["total_reused_signals"] == 2
        assert stats["reuse_by_suite"] == {"safety": 1, "red_team": 1}
        assert stats["reuse_rate"] == 2.0  # 2 reused / 1 cached
    
    def test_create_enhanced_signal_for_reuse(self):
        """Test creating enhanced signal for reuse."""
        enhanced = self.service.create_enhanced_signal_for_reuse(
            original_signal=self.sample_signal,
            suite="safety",
            test_id="safety_test_1"
        )
        
        assert enhanced.id == self.sample_signal.id
        assert enhanced.category == self.sample_signal.category
        assert enhanced.score == self.sample_signal.score
        assert enhanced.label == self.sample_signal.label
        assert enhanced.confidence == self.sample_signal.confidence
        
        # Check enhanced details
        assert enhanced.details["reused_from_preflight"] is True
        assert enhanced.details["reused_in_suite"] == "safety"
        assert enhanced.details["reused_in_test"] == "safety_test_1"
        assert enhanced.details["original_stage"] == "preflight"


class TestSuiteDeduplicationHelper:
    """Test the suite-specific deduplication helper."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.service = CrossSuiteDeduplicationService("test_run_123")
        self.helper = SuiteDeduplicationHelper(self.service)
        
        # Store a sample signal
        self.sample_signal = SignalResult(
            id="pii.presidio",
            category=GuardrailCategory.PII,
            score=0.0,
            label=SignalLabel.CLEAN,
            confidence=1.0,
            details={"total_hits": 0, "entity_types": []}
        )
        self.service.store_preflight_signal(self.sample_signal, "gpt-4", "abc123")
    
    def test_check_safety_signal_reusable(self):
        """Test checking safety signal reusability."""
        reusable = self.helper.check_safety_signal_reusable(
            provider_id="pii.presidio",
            category="pii",
            model="gpt-4",
            rules_hash="abc123"
        )
        
        assert reusable is not None
        assert reusable.id == "pii.presidio"
    
    def test_check_red_team_signal_reusable(self):
        """Test checking red team signal reusability."""
        reusable = self.helper.check_red_team_signal_reusable(
            provider_id="pii.presidio",
            attack_type="pii",
            model="gpt-4",
            rules_hash="abc123"
        )
        
        assert reusable is not None
        assert reusable.id == "pii.presidio"
    
    def test_check_performance_signal_reusable(self):
        """Test checking performance signal reusability."""
        reusable = self.helper.check_performance_signal_reusable(
            provider_id="pii.presidio",
            metric_type="pii",
            model="gpt-4",
            rules_hash="abc123"
        )
        
        assert reusable is not None
        assert reusable.id == "pii.presidio"
    
    def test_check_bias_signal_reusable(self):
        """Test checking bias signal reusability."""
        reusable = self.helper.check_bias_signal_reusable(
            provider_id="pii.presidio",
            bias_type="pii",
            model="gpt-4",
            rules_hash="abc123"
        )
        
        assert reusable is not None
        assert reusable.id == "pii.presidio"
    
    def test_check_rag_signal_reusable(self):
        """Test checking RAG signal reusability."""
        reusable = self.helper.check_rag_signal_reusable(
            provider_id="pii.presidio",
            rag_metric="pii",
            model="gpt-4",
            rules_hash="abc123"
        )
        
        assert reusable is not None
        assert reusable.id == "pii.presidio"


class TestUtilityFunctions:
    """Test utility functions."""
    
    def test_create_rules_hash(self):
        """Test creating rules hash."""
        config1 = {"mode": "hard_gate", "rules": [{"id": "pii", "enabled": True}]}
        config2 = {"mode": "hard_gate", "rules": [{"id": "pii", "enabled": True}]}
        config3 = {"mode": "advisory", "rules": [{"id": "pii", "enabled": True}]}
        
        hash1 = create_rules_hash(config1)
        hash2 = create_rules_hash(config2)
        hash3 = create_rules_hash(config3)
        
        assert isinstance(hash1, str)
        assert len(hash1) == 16
        assert hash1 == hash2  # Same config should produce same hash
        assert hash1 != hash3  # Different config should produce different hash
    
    def test_create_rules_hash_empty(self):
        """Test creating rules hash with empty config."""
        hash_empty = create_rules_hash({})
        hash_none = create_rules_hash(None)
        
        assert isinstance(hash_empty, str)
        assert isinstance(hash_none, str)
        assert len(hash_empty) == 16
        assert len(hash_none) == 16


class TestIntegrationScenarios:
    """Test integration scenarios matching the requirements."""
    
    def setup_method(self):
        """Set up integration test fixtures."""
        self.service = CrossSuiteDeduplicationService("integration_test_run")
        
        # Create sample signals for different categories
        self.pii_signal = SignalResult(
            id="pii.presidio",
            category=GuardrailCategory.PII,
            score=0.0,
            label=SignalLabel.CLEAN,
            confidence=1.0,
            details={"total_hits": 0, "entity_types": []}
        )
        
        self.jailbreak_signal = SignalResult(
            id="jailbreak.hybrid",
            category=GuardrailCategory.JAILBREAK,
            score=0.1,
            label=SignalLabel.CLEAN,
            confidence=0.9,
            details={"pattern_score": 0.05, "vector_score": 0.15}
        )
        
        self.toxicity_signal = SignalResult(
            id="toxicity.detoxify",
            category=GuardrailCategory.TOXICITY,
            score=0.05,
            label=SignalLabel.CLEAN,
            confidence=0.95,
            details={"toxicity": 0.05, "severe_toxicity": 0.01}
        )
    
    def test_preflight_plus_safety_zero_duplicates(self):
        """Test Preflight+Safety: zero duplicate executions; reused count > 0."""
        # Store preflight signals
        model = "gpt-4"
        rules_hash = "test_rules_123"
        
        self.service.store_preflight_signal(self.pii_signal, model, rules_hash)
        self.service.store_preflight_signal(self.toxicity_signal, model, rules_hash)
        
        # Simulate safety suite checking for reusable signals
        helper = SuiteDeduplicationHelper(self.service)
        
        # Safety suite would check for overlapping categories
        pii_reusable = helper.check_safety_signal_reusable("pii.presidio", "pii", model, rules_hash)
        toxicity_reusable = helper.check_safety_signal_reusable("toxicity.detoxify", "toxicity", model, rules_hash)
        jailbreak_reusable = helper.check_safety_signal_reusable("jailbreak.hybrid", "jailbreak", model, rules_hash)
        
        # Should find reusable signals for PII and toxicity
        assert pii_reusable is not None
        assert toxicity_reusable is not None
        assert jailbreak_reusable is None  # Not stored in preflight
        
        # Mark signals as reused
        if pii_reusable:
            self.service.mark_signal_reused(pii_reusable, "safety", "safety_pii_test")
        if toxicity_reusable:
            self.service.mark_signal_reused(toxicity_reusable, "safety", "safety_toxicity_test")
        
        # Check statistics
        stats = self.service.get_reuse_statistics()
        assert stats["total_cached_signals"] == 2
        assert stats["total_reused_signals"] == 2
        assert stats["reuse_by_suite"]["safety"] == 2
        assert stats["reuse_rate"] == 1.0  # 100% reuse rate
    
    def test_preflight_plus_red_team_partial_overlap(self):
        """Test Preflight+Red Team: only non-overlapping PI variants run."""
        # Store preflight signals
        model = "gpt-4"
        rules_hash = "test_rules_123"
        
        self.service.store_preflight_signal(self.jailbreak_signal, model, rules_hash)
        self.service.store_preflight_signal(self.pii_signal, model, rules_hash)
        
        # Simulate red team suite checking for reusable signals
        helper = SuiteDeduplicationHelper(self.service)
        
        # Red team would check for overlapping attack types
        jailbreak_reusable = helper.check_red_team_signal_reusable("jailbreak.hybrid", "jailbreak", model, rules_hash)
        pii_reusable = helper.check_red_team_signal_reusable("pii.presidio", "pii", model, rules_hash)
        
        # Should find reusable signals
        assert jailbreak_reusable is not None
        assert pii_reusable is not None
        
        # Mark signals as reused
        self.service.mark_signal_reused(jailbreak_reusable, "red_team", "red_team_jailbreak_test")
        self.service.mark_signal_reused(pii_reusable, "red_team", "red_team_pii_test")
        
        # Check that red team suite would skip these variants
        red_team_reused = self.service.get_reused_signals_for_suite("red_team")
        assert len(red_team_reused) == 2
        
        # Verify categories that were reused
        reused_categories = [rs.original_signal.category.value for rs in red_team_reused]
        assert "jailbreak" in reused_categories
        assert "pii" in reused_categories
    
    def test_determinism_same_inputs_identical_reuse_map(self):
        """Test Determinism: same inputs → identical reuse map."""
        model = "gpt-4"
        rules_hash = "deterministic_test_123"
        
        # Run 1: Store signals
        service1 = CrossSuiteDeduplicationService("run_1")
        service1.store_preflight_signal(self.pii_signal, model, rules_hash)
        service1.store_preflight_signal(self.jailbreak_signal, model, rules_hash)
        
        # Run 2: Store same signals
        service2 = CrossSuiteDeduplicationService("run_2")
        service2.store_preflight_signal(self.pii_signal, model, rules_hash)
        service2.store_preflight_signal(self.jailbreak_signal, model, rules_hash)
        
        # Both services should have identical fingerprints
        fingerprints1 = set(service1._signal_cache.keys())
        fingerprints2 = set(service2._signal_cache.keys())
        
        assert fingerprints1 == fingerprints2
        
        # Both should find the same reusable signals
        helper1 = SuiteDeduplicationHelper(service1)
        helper2 = SuiteDeduplicationHelper(service2)
        
        pii_reusable1 = helper1.check_safety_signal_reusable("pii.presidio", "pii", model, rules_hash)
        pii_reusable2 = helper2.check_safety_signal_reusable("pii.presidio", "pii", model, rules_hash)
        
        assert (pii_reusable1 is not None) == (pii_reusable2 is not None)
        if pii_reusable1 and pii_reusable2:
            assert pii_reusable1.id == pii_reusable2.id
            assert pii_reusable1.category == pii_reusable2.category
            assert pii_reusable1.score == pii_reusable2.score
    
    def test_cross_suite_reuse_statistics(self):
        """Test comprehensive cross-suite reuse statistics."""
        model = "gpt-4"
        rules_hash = "comprehensive_test_123"
        
        # Store multiple signals
        self.service.store_preflight_signal(self.pii_signal, model, rules_hash)
        self.service.store_preflight_signal(self.jailbreak_signal, model, rules_hash)
        self.service.store_preflight_signal(self.toxicity_signal, model, rules_hash)
        
        helper = SuiteDeduplicationHelper(self.service)
        
        # Simulate reuse across multiple suites
        cached_signals = list(self.service._signal_cache.values())
        
        # Safety suite reuses PII and toxicity
        self.service.mark_signal_reused(cached_signals[0], "safety", "safety_test_1")
        self.service.mark_signal_reused(cached_signals[2], "safety", "safety_test_2")
        
        # Red team reuses jailbreak and PII
        self.service.mark_signal_reused(cached_signals[1], "red_team", "red_team_test_1")
        self.service.mark_signal_reused(cached_signals[0], "red_team", "red_team_test_2")
        
        # Performance reuses PII (for latency checks)
        self.service.mark_signal_reused(cached_signals[0], "performance", "perf_test_1")
        
        # Check final statistics
        stats = self.service.get_reuse_statistics()
        
        assert stats["total_cached_signals"] == 3
        assert stats["total_reused_signals"] == 5
        assert stats["reuse_by_suite"]["safety"] == 2
        assert stats["reuse_by_suite"]["red_team"] == 2
        assert stats["reuse_by_suite"]["performance"] == 1
        assert abs(stats["reuse_rate"] - (5/3)) < 0.01  # ~1.67 reuse rate


if __name__ == "__main__":
    pytest.main([__file__])
