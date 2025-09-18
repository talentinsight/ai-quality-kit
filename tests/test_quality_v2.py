"""Tests for enhanced quality testing framework."""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any

from apps.testing.schema_v2 import (
    TestCaseV2, QualityGuardOptions, OracleType, SeverityLevel,
    parse_test_case_v2, get_effective_oracle_type, is_critical_case
)
from apps.testing.oracles import (
    PrimaryOracles, SecondaryGuards, TestEvaluator, TextNormalizer
)
from apps.testing.anti_flake import AntiFlakeHarness, StabilityResult
from apps.testing.metamorphic import (
    MetamorphicChecker, MetamorphicGenerator, CounterfactualGenerator
)
from apps.testing.compliance_hardened import HardenedPIIScanner, LuhnValidator


def create_test_case(**kwargs) -> TestCaseV2:
    """Helper to create TestCaseV2 with all required parameters."""
    defaults = {
        "test_id": "test-001",
        "query": "What is AI?",
        "expected_answer": "Artificial Intelligence",
        "context": [],
        "oracle_type": None,
        "acceptance": None,
        "severity": "major",
        "deterministic_seed": 42,
        "metamorphic_group": None,
        "tags": None,
        "unstable": None,
        "metamorphic_break": None
    }
    defaults.update(kwargs)
    return TestCaseV2(**defaults)


class TestSchemaV2:
    """Tests for enhanced test case schema."""
    
    def test_test_case_v2_defaults(self):
        """Test v2 test case with default values."""
        case = create_test_case(
            test_id="test_1",
            query="What is AI?",
            expected_answer="Artificial Intelligence"
        )
        
        assert case.severity == "major"
        assert case.deterministic_seed == 42
        assert case.oracle_type is None
        assert case.metamorphic_group is None
        assert case.unstable is None
    
    def test_parse_legacy_case(self):
        """Test parsing legacy test case format."""
        legacy_data = {
            "test_id": "legacy_1",
            "query": "Test query",
            "expected_answer": "Test answer"
        }
        
        case = parse_test_case_v2(legacy_data)
        assert case.test_id == "legacy_1"
        assert case.query == "Test query"
        assert case.severity == "major"  # Default
    
    def test_effective_oracle_type(self):
        """Test oracle type resolution."""
        # Explicit oracle type
        case = create_test_case(
            test_id="test_1",
            query="Test",
            oracle_type="exact"
        )
        assert get_effective_oracle_type(case) == "exact"
        
        # Fallback with expected answer
        case = create_test_case(
            test_id="test_2",
            query="Test",
            expected_answer="Answer"
        )
        assert get_effective_oracle_type(case) == "contains"
        
        # Fallback without expected answer
        case = create_test_case(
            test_id="test_3",
            query="Test",
            expected_answer=None
        )
        assert get_effective_oracle_type(case) == "semantic"
    
    def test_critical_case_detection(self):
        """Test critical case identification."""
        critical_case = create_test_case(
            test_id="crit_1",
            query="Critical test",
            severity="critical"
        )
        assert is_critical_case(critical_case)
        
        major_case = create_test_case(
            test_id="maj_1",
            query="Major test",
            severity="major"
        )
        assert not is_critical_case(major_case)


class TestOracles:
    """Tests for oracle evaluation system."""
    
    def test_text_normalizer(self):
        """Test text normalization."""
        # Basic normalization
        assert TextNormalizer.normalize("  Hello World!  ") == "hello world!"
        
        # Markdown removal
        assert TextNormalizer.normalize('"Hello"') == "hello"
        assert TextNormalizer.normalize("```code```") == "code"
        
        # Punctuation collapse
        assert TextNormalizer.normalize("Hello!!!") == "hello!"
    
    def test_exact_oracle(self):
        """Test exact string equality oracle."""
        result = PrimaryOracles.exact("Hello World", "hello world")
        assert result.passed
        assert result.score == 1.0
        
        result = PrimaryOracles.exact("Hello", "World")
        assert not result.passed
        assert result.score == 0.0
    
    def test_contains_oracle(self):
        """Test substring containment oracle."""
        result = PrimaryOracles.contains("Hello World", "world")
        assert result.passed
        assert result.score == 1.0
        
        result = PrimaryOracles.contains("Hello", "world")
        assert not result.passed
        assert result.score == 0.0
    
    def test_regex_oracle(self):
        """Test regex pattern oracle."""
        # Valid regex
        result = PrimaryOracles.regex("The answer is 42", r"\d+")
        assert result.passed
        assert result.score == 1.0
        
        # No match
        result = PrimaryOracles.regex("No numbers here", r"\d+")
        assert not result.passed
        assert result.score == 0.0
        
        # Invalid regex
        result = PrimaryOracles.regex("Text", r"[invalid")
        assert not result.passed
        assert "Invalid pattern" in result.details.get("error", "")
    
    def test_semantic_oracle(self):
        """Test semantic similarity oracle."""
        # High similarity (simple token overlap)
        result = PrimaryOracles.semantic("AI is artificial intelligence", "artificial intelligence", 0.5)
        assert result.passed
        assert result.score >= 0.5
        
        # Low similarity
        result = PrimaryOracles.semantic("Completely different text", "artificial intelligence", 0.8)
        assert not result.passed
    
    def test_secondary_guards(self):
        """Test secondary guard patterns."""
        # Should trigger forbidden patterns
        forbidden = SecondaryGuards.check_forbidden_patterns("I'm sorry, I cannot help with that")
        assert len(forbidden) > 0
        
        # Should not trigger on normal text
        forbidden = SecondaryGuards.check_forbidden_patterns("The answer is 42")
        assert len(forbidden) == 0
    
    def test_evaluator_integration(self):
        """Test complete evaluation process."""
        evaluator = TestEvaluator()
        
        case = create_test_case(
            test_id="eval_test",
            query="What is 2+2?",
            expected_answer="4",
            oracle_type="exact"
        )
        
        result = evaluator.evaluate_case(case, "4")
        assert result.passed
        assert result.oracle_used == "exact"


class TestAntiFlake:
    """Tests for anti-flake harness."""
    
    def test_quality_guard_options(self):
        """Test quality guard configuration."""
        options = QualityGuardOptions(
            enabled=True,
            repeat_n=3,
            sample_criticals=10
        )
        
        assert options.enabled
        assert options.repeat_n == 3
        assert options.sample_criticals == 10
    
    def test_anti_flake_harness_initialization(self):
        """Test harness initialization."""
        options = QualityGuardOptions(enabled=True, repeat_n=2, sample_criticals=5)
        harness = AntiFlakeHarness(options)
        
        assert harness.options == options
        assert len(harness.quarantined_cases) == 0
        assert len(harness.stability_results) == 0
    
    def test_should_test_stability(self):
        """Test stability testing criteria."""
        options = QualityGuardOptions(enabled=True, repeat_n=2, sample_criticals=2)
        harness = AntiFlakeHarness(options)
        
        # Critical case should be tested
        critical_case = create_test_case(
            test_id="crit_1",
            query="Critical test",
            severity="critical"
        )
        assert harness.should_test_stability(critical_case)
        
        # Non-critical case should not be tested (in current implementation)
        major_case = create_test_case(
            test_id="maj_1",
            query="Major test",
            severity="major"
        )
        assert not harness.should_test_stability(major_case)
    
    def test_unstable_case_detection(self):
        """Test detection of unstable cases."""
        options = QualityGuardOptions(enabled=True, repeat_n=2, sample_criticals=5)
        harness = AntiFlakeHarness(options)
        
        # Mock test runner that returns different results
        def unstable_runner(case):
            if not hasattr(unstable_runner, 'call_count'):
                unstable_runner.call_count = 0
            unstable_runner.call_count += 1
            
            # Return different results on different calls
            if unstable_runner.call_count % 2 == 1:
                return "Success"
            else:
                return "Failure"
        
        case = create_test_case(
            test_id="unstable_test",
            query="Test query",
            expected_answer="Success",
            severity="critical"
        )
        
        result = harness.run_stability_test(case, unstable_runner)
        
        # Should detect instability
        assert not result.is_stable
        assert len(result.results) == 2
        assert case.test_id in harness.quarantined_cases


class TestMetamorphic:
    """Tests for metamorphic consistency checking."""
    
    def test_metamorphic_generator(self):
        """Test metamorphic variant generation."""
        base_case = create_test_case(
            test_id="base_1",
            query="What is AI?",
            expected_answer="Artificial Intelligence",
            oracle_type="contains"
        )
        
        variants = MetamorphicGenerator.create_metamorphic_variants(
            base_case, "group_1"
        )
        
        # Should generate some variants
        assert len(variants) > 0
        
        # All variants should be in the same metamorphic group
        for variant in variants:
            assert variant.metamorphic_group == "group_1"
            assert variant.tags and "metamorphic" in variant.tags
    
    def test_counterfactual_generation(self):
        """Test counterfactual pair generation."""
        base_case = create_test_case(
            test_id="cf_base",
            query="Advice for a young professional",
            expected_answer="General advice",
            oracle_type="semantic"
        )
        
        substitutions = {"young": "elderly", "professional": "worker"}
        pair = CounterfactualGenerator.create_counterfactual_pair(
            base_case, substitutions
        )
        
        assert pair is not None
        assert "elderly" in pair.case_b.query
        assert "worker" in pair.case_b.query
        assert pair.substitution == {"young": "elderly", "professional": "worker"}
    
    def test_metamorphic_checker(self):
        """Test metamorphic consistency checking."""
        checker = MetamorphicChecker()
        
        # Create test cases in same group
        case1 = create_test_case(
            test_id="meta_1",
            query="What is AI?",
            metamorphic_group="ai_group"
        )
        case2 = create_test_case(
            test_id="meta_2", 
            query="What is Artificial Intelligence?",
            metamorphic_group="ai_group"
        )
        
        checker.register_case(case1)
        checker.register_case(case2)
        
        # Mock consistent results
        from apps.testing.oracles import EvaluationResult
        checker.add_result("meta_1", case1, EvaluationResult(passed=True, score=1.0))
        checker.add_result("meta_2", case2, EvaluationResult(passed=True, score=1.0))
        
        summary = checker.check_all_consistency()
        assert summary["consistent_groups"] == 1
        assert summary["total_violations"] == 0


class TestComplianceHardened:
    """Tests for hardened compliance scanning."""
    
    def test_luhn_validator(self):
        """Test Luhn algorithm validation."""
        # Valid credit card numbers (test data)
        assert LuhnValidator.validate("4111111111111111")  # Test Visa
        assert LuhnValidator.validate("5555555555554444")  # Test Mastercard
        
        # Invalid numbers
        assert not LuhnValidator.validate("1234567890123456")
        assert not LuhnValidator.validate("1111111111111111")
        
        # Too short
        assert not LuhnValidator.validate("123456")
    
    def test_pii_scanner_initialization(self):
        """Test PII scanner initialization."""
        scanner = HardenedPIIScanner()
        
        # Should load default patterns
        assert "ssn" in scanner.patterns
        assert "email" in scanner.patterns
        assert "credit_card" in scanner.patterns
    
    def test_allowlist_filtering(self):
        """Test allowlist filtering for test data."""
        scanner = HardenedPIIScanner()
        
        # Test allowlisted SSN
        matches = scanner.scan_text("My SSN is 123-45-6789")
        assert len(matches) == 0  # Should be filtered out
        
        # Test allowlisted email
        matches = scanner.scan_text("Contact test@example.com")
        assert len(matches) == 0  # Should be filtered out
    
    def test_luhn_validation_filtering(self):
        """Test Luhn validation for credit cards."""
        scanner = HardenedPIIScanner()
        
        # Invalid Luhn number (should be filtered)
        matches = scanner.scan_text("Card number: 1111-1111-1111-1111")
        assert len(matches) == 0  # Should fail Luhn check
        
        # Valid Luhn but allowlisted (should be filtered)
        matches = scanner.scan_text("Card number: 4111-1111-1111-1111")
        assert len(matches) == 0  # Valid Luhn but allowlisted
    
    def test_confidence_scoring(self):
        """Test confidence scoring for matches."""
        scanner = HardenedPIIScanner()
        
        # Create a mock pattern that would match
        test_text = "Contact info: real.user@company.com"
        matches = scanner.scan_text(test_text)
        
        # Should find email but not allowlisted ones
        if matches:
            for match in matches:
                assert match.confidence > 0.5
                assert match.pattern_id == "email"
    
    def test_anchor_patterns(self):
        """Test word-boundary anchored patterns."""
        scanner = HardenedPIIScanner()
        
        # Should not match partial words
        text = "The word password123 contains numbers"
        matches = scanner.scan_text(text)
        
        # Should not detect partial SSN in the middle of a word
        # (assuming patterns are properly anchored)
        partial_matches = [m for m in matches if "123" in m.normalized_snippet]
        assert len(partial_matches) == 0


class TestIntegration:
    """Integration tests for quality system."""
    
    def test_end_to_end_quality_evaluation(self):
        """Test complete quality evaluation pipeline."""
        # Create a test case with v2 features
        case = create_test_case(
            test_id="e2e_test",
            query="What is 2 + 2?",
            expected_answer="4",
            oracle_type="exact",
            severity="critical",
            metamorphic_group="math_basic"
        )
        
        # Create evaluator
        evaluator = TestEvaluator()
        
        # Test correct answer
        result = evaluator.evaluate_case(case, "4")
        assert result.passed
        assert result.oracle_used == "exact"
        
        # Test incorrect answer
        result = evaluator.evaluate_case(case, "5")
        assert not result.passed
    
    def test_quality_guard_disabled(self):
        """Test that system works with quality guard disabled."""
        options = QualityGuardOptions(enabled=False, repeat_n=2, sample_criticals=5)
        harness = AntiFlakeHarness(options)
        
        case = create_test_case(
            test_id="disabled_test",
            query="Test",
            severity="critical"
        )
        
        # Should not test stability when disabled
        assert not harness.should_test_stability(case)
    
    @patch('apps.testing.oracles.SemanticScorer.compute_similarity')
    def test_semantic_fallback(self, mock_similarity):
        """Test semantic oracle fallback to contains."""
        # Mock semantic scoring to raise exception
        mock_similarity.side_effect = Exception("Model not available")
        
        result = PrimaryOracles.semantic("AI is artificial intelligence", "AI", 0.8)
        
        # Should fallback to contains behavior
        assert "fallback" in result.details.get("oracle_type", "")
        # Contains logic: "AI" in "ai is artificial intelligence" -> True
        assert result.passed
