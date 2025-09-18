"""
Unit tests for baseline resolver functionality.
"""

import pytest
from apps.orchestrator.baseline_resolver import BaselineResolver, TIER_CANDIDATES


class TestBaselineResolver:
    """Test cases for BaselineResolver."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.resolver = BaselineResolver()
    
    def test_same_model_detection_openai(self):
        """Test same model detection for OpenAI models."""
        compare_config = {
            "auto_select": {"enabled": True, "strategy": "same_or_near_tier"}
        }
        
        result = self.resolver.resolve_baseline_model(
            compare_config,
            primary_meta_model="gpt-4o-mini"
        )
        
        assert result["resolved_via"] == "same_model"
        assert result["preset"] == "openai"
        assert result["model"] == "gpt-4o-mini"
        assert "PRIMARY response meta.model" in result["source"]
    
    def test_same_model_detection_anthropic(self):
        """Test same model detection for Anthropic models."""
        compare_config = {
            "auto_select": {"enabled": True, "strategy": "same_or_near_tier"}
        }
        
        result = self.resolver.resolve_baseline_model(
            compare_config,
            primary_meta_model="claude-3-sonnet-20240229"
        )
        
        assert result["resolved_via"] == "same_model"
        assert result["preset"] == "anthropic"
        assert result["model"] == "claude-3-sonnet-20240229"
    
    def test_same_model_detection_gemini(self):
        """Test same model detection for Gemini models."""
        compare_config = {
            "auto_select": {"enabled": True, "strategy": "same_or_near_tier"}
        }
        
        result = self.resolver.resolve_baseline_model(
            compare_config,
            primary_meta_model="gemini-1.5-pro"
        )
        
        assert result["resolved_via"] == "same_model"
        assert result["preset"] == "gemini"
        assert result["model"] == "gemini-1.5-pro"
    
    def test_near_tier_suggestion_economy(self):
        """Test near-tier suggestion for economy tier models."""
        compare_config = {
            "auto_select": {"enabled": True, "strategy": "same_or_near_tier"}
        }
        
        result = self.resolver.resolve_baseline_model(
            compare_config,
            primary_meta_model="unknown-mini-model"
        )
        
        assert result["resolved_via"] == "near_tier"
        assert result["preset"] in ["openai", "anthropic", "gemini"]
        assert "economy" in result["source"].lower()
    
    def test_near_tier_suggestion_with_hint(self):
        """Test near-tier suggestion with explicit hint."""
        compare_config = {
            "auto_select": {
                "enabled": True, 
                "strategy": "same_or_near_tier",
                "hint_tier": "premium"
            }
        }
        
        result = self.resolver.resolve_baseline_model(
            compare_config,
            primary_meta_model="unknown-model"
        )
        
        assert result["resolved_via"] == "near_tier"
        assert "premium" in result["source"].lower()
    
    def test_explicit_baseline_configuration(self):
        """Test explicit baseline configuration overrides auto-select."""
        compare_config = {
            "baseline": {
                "preset": "anthropic",
                "model": "claude-3-opus",
                "decoding": {"temperature": 0.1}
            },
            "auto_select": {"enabled": True}
        }
        
        result = self.resolver.resolve_baseline_model(compare_config)
        
        assert result["resolved_via"] == "explicit"
        assert result["preset"] == "anthropic"
        assert result["model"] == "claude-3-opus"
        assert result["decoding"]["temperature"] == 0.1
    
    def test_fallback_to_balanced_tier(self):
        """Test fallback to balanced tier when no detection possible."""
        compare_config = {
            "auto_select": {"enabled": True, "strategy": "same_or_near_tier"}
        }
        
        result = self.resolver.resolve_baseline_model(
            compare_config,
            primary_meta_model="completely-unknown-model"
        )
        
        assert result["resolved_via"] == "fallback"
        assert result["preset"] in ["openai", "anthropic", "gemini"]
        assert "balanced tier default" in result["source"]
    
    def test_unsupported_vendor_filtering(self):
        """Test that unsupported vendors are filtered out."""
        # Create resolver with limited vendor support
        resolver = BaselineResolver(supported_vendors={"openai"})
        
        compare_config = {
            "auto_select": {"enabled": True, "strategy": "same_or_near_tier"}
        }
        
        result = resolver.resolve_baseline_model(
            compare_config,
            primary_meta_model="claude-3-sonnet"  # Anthropic model
        )
        
        # Should fall back to supported vendor (OpenAI)
        assert result["preset"] == "openai"
    
    def test_no_supported_vendors_error(self):
        """Test error when no supported vendors available."""
        resolver = BaselineResolver(supported_vendors=set())
        resolver.reset_cache()  # Ensure no cached results
        
        # Test the helper method directly first
        candidate = resolver._get_first_supported_candidate("balanced")
        assert candidate is None, f"Expected None but got {candidate}"
        
        compare_config = {
            "auto_select": {"enabled": True, "strategy": "same_or_near_tier"}
        }
        
        with pytest.raises(ValueError, match="No suitable baseline candidate found"):
            resolver.resolve_baseline_model(compare_config)
    
    def test_auto_select_disabled_without_explicit_config(self):
        """Test error when auto-select disabled but no explicit config."""
        compare_config = {
            "auto_select": {"enabled": False}
        }
        
        with pytest.raises(ValueError, match="Auto-select disabled and baseline not fully specified"):
            self.resolver.resolve_baseline_model(compare_config)
    
    def test_decoding_defaults_merge(self):
        """Test that decoding defaults are properly merged."""
        compare_config = {
            "baseline": {
                "preset": "openai",
                "model": "gpt-4o",
                "decoding": {"temperature": 0.2}
            }
        }
        
        result = self.resolver.resolve_baseline_model(compare_config)
        
        # Should merge user override with defaults
        assert result["decoding"]["temperature"] == 0.2  # User override
        assert result["decoding"]["top_p"] == 1  # Default
        assert result["decoding"]["max_tokens"] == 1024  # Default
    
    def test_cache_behavior(self):
        """Test that baseline resolution is cached per run."""
        compare_config = {
            "auto_select": {"enabled": True, "strategy": "same_or_near_tier"}
        }
        
        # First resolution
        result1 = self.resolver.resolve_baseline_model(
            compare_config,
            primary_meta_model="gpt-4o"
        )
        
        # Second resolution should return cached result
        result2 = self.resolver.resolve_baseline_model(
            compare_config,
            primary_meta_model="claude-3-sonnet"  # Different model
        )
        
        # Should be identical (cached)
        assert result1 == result2
        
        # Reset cache and try again
        self.resolver.reset_cache()
        result3 = self.resolver.resolve_baseline_model(
            compare_config,
            primary_meta_model="claude-3-sonnet"
        )
        
        # Should be different now (not cached)
        assert result3["preset"] == "anthropic"  # Should detect Claude
    
    def test_tier_classification(self):
        """Test model tier classification logic."""
        # Economy tier models
        assert self.resolver._classify_model_tier("gpt-4o-mini") == "economy"
        assert self.resolver._classify_model_tier("claude-3-haiku") == "economy"
        assert self.resolver._classify_model_tier("gemini-flash") == "economy"
        
        # Balanced tier models
        assert self.resolver._classify_model_tier("claude-3-sonnet") == "balanced"
        assert self.resolver._classify_model_tier("gpt-4o") == "balanced"
        assert self.resolver._classify_model_tier("some-pro-model") == "balanced"
        
        # Premium tier models
        assert self.resolver._classify_model_tier("claude-3-opus") == "premium"
        assert self.resolver._classify_model_tier("gpt-o4") == "premium"
        
        # Unknown models
        assert self.resolver._classify_model_tier("unknown-model") is None


def test_tier_candidates_configuration():
    """Test that tier candidates are properly configured."""
    # Ensure all tiers have candidates
    for tier in ["economy", "balanced", "premium"]:
        assert tier in TIER_CANDIDATES
        assert len(TIER_CANDIDATES[tier]) > 0
        
        # Ensure candidates have both preset and model
        for preset, model in TIER_CANDIDATES[tier]:
            assert isinstance(preset, str)
            assert isinstance(model, str)
            assert preset in ["openai", "anthropic", "gemini"]


def test_convenience_function():
    """Test the convenience function for stateless resolution."""
    from apps.orchestrator.baseline_resolver import resolve_baseline_model
    
    compare_config = {
        "auto_select": {"enabled": True, "strategy": "same_or_near_tier"}
    }
    
    result = resolve_baseline_model(
        compare_config,
        primary_meta_model="gpt-4o-mini",
        supported_vendors={"openai", "anthropic"}
    )
    
    assert result["resolved_via"] == "same_model"
    assert result["preset"] == "openai"
    assert result["model"] == "gpt-4o-mini"
