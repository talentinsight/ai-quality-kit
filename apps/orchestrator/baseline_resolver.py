"""
Baseline model auto-selection utility for Compare Mode.

This module implements the logic to resolve baseline vendor models for comparison:
1. SAME model detection from PRIMARY response metadata
2. NEAR-TIER suggestions when same model cannot be determined
3. Deterministic decoding defaults and configuration merging
"""

import logging
from typing import Dict, Any, Optional, Tuple
import re

logger = logging.getLogger(__name__)

# Tier classification mapping (heuristic, extendable)
TIER_KEYWORDS = {
    "economy": ["mini", "haiku", "flash", "lite", "small"],
    "balanced": ["sonnet", "gpt-4o", "mid", "standard", "pro"],
    "premium": ["opus", "ultra", "o4", "largest", "max", "claude-3-opus"]
}

# Default candidates per tier (priority order: openai -> anthropic -> gemini)
TIER_CANDIDATES = {
    "economy": [
        ("openai", "gpt-4o-mini"),
        ("anthropic", "claude-3-5-haiku"),
        ("gemini", "gemini-1.5-flash")
    ],
    "balanced": [
        ("openai", "gpt-4o"),
        ("anthropic", "claude-3-5-sonnet"),
        ("gemini", "gemini-1.5-pro")
    ],
    "premium": [
        ("openai", "o4"),
        ("anthropic", "claude-3-opus"),
        ("gemini", "gemini-1.5-ultra")
    ]
}

# Default decoding parameters for deterministic behavior
DEFAULT_DECODING = {
    "temperature": 0,
    "top_p": 1,
    "max_tokens": 1024
}


class BaselineResolver:
    """Resolves baseline model configuration for Compare Mode."""
    
    def __init__(self, supported_vendors: Optional[set] = None):
        """
        Initialize resolver with supported vendor list.
        
        Args:
            supported_vendors: Set of supported vendor names (e.g., {"openai", "anthropic", "gemini"})
                              If None, uses default supported vendors from client factory.
        """
        self.supported_vendors = supported_vendors if supported_vendors is not None else {"openai", "anthropic", "gemini", "mock"}
        self._resolved_baseline = None  # Cache for run-level resolution
    
    def resolve_baseline_model(
        self,
        compare_config: Dict[str, Any],
        primary_meta_model: Optional[str] = None,
        primary_header_model: Optional[str] = None,
        primary_preset: Optional[str] = None,
        primary_model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Resolve baseline model configuration from compare_with config and primary sources.
        
        Args:
            compare_config: The compare_with configuration block
            primary_meta_model: Model from PRIMARY response meta.model field
            primary_header_model: Model from PRIMARY response x-model header
            primary_preset: PRIMARY target preset (if vendor preset mode)
            primary_model: PRIMARY target model (if vendor preset mode)
            
        Returns:
            Dictionary with resolved baseline configuration:
            {
                "preset": str,
                "model": str,
                "decoding": dict,
                "resolved_via": str,  # "explicit" | "same_model" | "near_tier" | "fallback"
                "source": str  # description of resolution source
            }
            
        Raises:
            ValueError: If no suitable baseline can be resolved
        """
        # If already resolved for this run, return cached result
        if self._resolved_baseline:
            return self._resolved_baseline
        
        # 1. Check for explicit baseline configuration
        baseline_config = compare_config.get("baseline", {})
        if baseline_config.get("preset") and baseline_config.get("model"):
            result = {
                "preset": baseline_config["preset"],
                "model": baseline_config["model"],
                "decoding": self._merge_decoding(baseline_config.get("decoding", {})),
                "resolved_via": "explicit",
                "source": "User-specified baseline.preset and baseline.model"
            }
            self._resolved_baseline = result
            return result
        
        # 2. Auto-select logic (if enabled and baseline not fully specified)
        auto_select = compare_config.get("auto_select", {})
        if not auto_select.get("enabled", True):
            raise ValueError("Auto-select disabled and baseline not fully specified")
        
        # 3. Try SAME model detection (priority order)
        same_model_result = self._try_same_model_detection(
            primary_meta_model, primary_header_model, primary_preset, primary_model
        )
        if same_model_result:
            result = {
                **same_model_result,
                "decoding": self._merge_decoding(baseline_config.get("decoding", {})),
                "resolved_via": "same_model"
            }
            self._resolved_baseline = result
            return result
        
        # 4. NEAR-TIER suggestion
        hint_tier = auto_select.get("hint_tier")
        near_tier_result = self._try_near_tier_suggestion(
            primary_meta_model, primary_header_model, hint_tier
        )
        if near_tier_result:
            result = {
                **near_tier_result,
                "decoding": self._merge_decoding(baseline_config.get("decoding", {})),
                "resolved_via": "near_tier"
            }
            self._resolved_baseline = result
            return result
        
        # 5. Fallback to balanced tier default
        fallback_result = self._get_fallback_candidate()
        if fallback_result:
            result = {
                **fallback_result,
                "decoding": self._merge_decoding(baseline_config.get("decoding", {})),
                "resolved_via": "fallback"
            }
            self._resolved_baseline = result
            return result
        
        raise ValueError("No suitable baseline candidate found - no supported vendors available")
    
    def _try_same_model_detection(
        self,
        meta_model: Optional[str],
        header_model: Optional[str],
        primary_preset: Optional[str],
        primary_model: Optional[str]
    ) -> Optional[Dict[str, str]]:
        """Try to detect and use the same model as PRIMARY."""
        
        # Priority order: meta.model -> header -> primary config
        candidates = [
            (meta_model, "PRIMARY response meta.model"),
            (header_model, "PRIMARY response x-model header"),
            (primary_model if primary_preset else None, f"PRIMARY config {primary_preset}:{primary_model}" if primary_preset else None)
        ]
        
        for model_name, source in candidates:
            if not model_name:
                continue
            
            # Normalize and detect vendor
            normalized = self._normalize_model_name(model_name)
            vendor = self._detect_vendor(normalized)
            
            if vendor and vendor in self.supported_vendors:
                logger.info(f"Same model detected: {vendor}:{model_name} from {source}")
                return {
                    "preset": vendor,
                    "model": model_name,
                    "source": source
                }
        
        return None
    
    def _try_near_tier_suggestion(
        self,
        meta_model: Optional[str],
        header_model: Optional[str],
        hint_tier: Optional[str]
    ) -> Optional[Dict[str, str]]:
        """Try to suggest a near-tier model."""
        
        # Use explicit hint_tier if provided
        if hint_tier and hint_tier in TIER_CANDIDATES:
            candidate = self._get_first_supported_candidate(hint_tier)
            if candidate:
                preset, model = candidate
                return {
                    "preset": preset,
                    "model": model,
                    "source": f"Explicit hint_tier: {hint_tier}"
                }
        
        # Classify tier from primary model names
        for model_name in [meta_model, header_model]:
            if not model_name:
                continue
            
            tier = self._classify_model_tier(model_name)
            if tier:
                candidate = self._get_first_supported_candidate(tier)
                if candidate:
                    preset, model = candidate
                    return {
                        "preset": preset,
                        "model": model,
                        "source": f"Tier classification: {tier} (from {model_name})"
                    }
        
        return None
    
    def _get_fallback_candidate(self) -> Optional[Dict[str, str]]:
        """Get fallback candidate from balanced tier."""
        candidate = self._get_first_supported_candidate("balanced")
        if candidate:
            preset, model = candidate
            return {
                "preset": preset,
                "model": model,
                "source": "Fallback to balanced tier default"
            }
        return None
    
    def _normalize_model_name(self, model_name: str) -> str:
        """Normalize model name for comparison."""
        return model_name.lower().strip()
    
    def _detect_vendor(self, normalized_model: str) -> Optional[str]:
        """Detect vendor from normalized model name."""
        # OpenAI patterns
        if any(pattern in normalized_model for pattern in ["gpt", "o4", "gpt-4o"]):
            return "openai"
        
        # Anthropic patterns
        if "claude" in normalized_model:
            return "anthropic"
        
        # Gemini patterns
        if "gemini" in normalized_model:
            return "gemini"
        
        return None
    
    def _classify_model_tier(self, model_name: str) -> Optional[str]:
        """Classify model tier based on name hints."""
        normalized = self._normalize_model_name(model_name)
        
        # Check in specific order: premium -> economy -> balanced
        # This handles conflicts like "pro" which could match multiple tiers
        tier_order = ["premium", "economy", "balanced"]
        
        for tier in tier_order:
            keywords = TIER_KEYWORDS[tier]
            if any(keyword in normalized for keyword in keywords):
                return tier
        
        return None
    
    def _get_first_supported_candidate(self, tier: str) -> Optional[Tuple[str, str]]:
        """Get first supported candidate from tier."""
        candidates = TIER_CANDIDATES.get(tier, [])
        for preset, model in candidates:
            if preset in self.supported_vendors:
                return (preset, model)
        return None
    
    def _merge_decoding(self, user_decoding: Dict[str, Any]) -> Dict[str, Any]:
        """Merge user decoding overrides with deterministic defaults."""
        result = DEFAULT_DECODING.copy()
        result.update(user_decoding)
        return result
    
    def reset_cache(self):
        """Reset the cached baseline resolution for a new run."""
        self._resolved_baseline = None


def resolve_baseline_model(
    compare_config: Dict[str, Any],
    primary_meta_model: Optional[str] = None,
    primary_header_model: Optional[str] = None,
    primary_preset: Optional[str] = None,
    primary_model: Optional[str] = None,
    supported_vendors: Optional[set] = None
) -> Dict[str, Any]:
    """
    Convenience function to resolve baseline model configuration.
    
    This is a stateless wrapper around BaselineResolver for single-use resolution.
    For run-level caching, use BaselineResolver directly.
    """
    resolver = BaselineResolver(supported_vendors)
    return resolver.resolve_baseline_model(
        compare_config, primary_meta_model, primary_header_model, 
        primary_preset, primary_model
    )
