"""Adaptive Test Generation Configuration."""

import os
from typing import Optional


# Main adaptive test generation settings
ADAPTIVE_TESTS_ENABLED = os.getenv("ADAPTIVE_TESTS_ENABLED", "true").lower() == "true"
ADAPTIVE_COMPLIANCE_ENABLED = os.getenv("ADAPTIVE_COMPLIANCE_ENABLED", "true").lower() == "true"
ADAPTIVE_BIAS_ENABLED = os.getenv("ADAPTIVE_BIAS_ENABLED", "true").lower() == "true"
ADAPTIVE_FALLBACK_ENABLED = os.getenv("ADAPTIVE_FALLBACK_ENABLED", "true").lower() == "true"

# LLM Profiling settings
LLM_PROFILING_ENABLED = os.getenv("LLM_PROFILING_ENABLED", "true").lower() == "true"
LLM_PROFILE_CACHE_TTL = int(os.getenv("LLM_PROFILE_CACHE_TTL", "3600"))

# Cultural/Language adaptation
ADAPTIVE_CULTURAL_CONTEXT = os.getenv("ADAPTIVE_CULTURAL_CONTEXT", "auto")
ADAPTIVE_PRIMARY_LANGUAGE = os.getenv("ADAPTIVE_PRIMARY_LANGUAGE", "auto")

# Industry-specific tests
ADAPTIVE_DEFAULT_INDUSTRY = os.getenv("ADAPTIVE_DEFAULT_INDUSTRY", "general")
ADAPTIVE_DOMAIN_TESTS_ENABLED = os.getenv("ADAPTIVE_DOMAIN_TESTS_ENABLED", "true").lower() == "true"

# Validation
assert ADAPTIVE_CULTURAL_CONTEXT in ["auto", "western", "turkish", "european"], \
    "ADAPTIVE_CULTURAL_CONTEXT must be one of: auto, western, turkish, european"

assert ADAPTIVE_PRIMARY_LANGUAGE in ["auto", "en", "tr", "de"], \
    "ADAPTIVE_PRIMARY_LANGUAGE must be one of: auto, en, tr, de"

assert ADAPTIVE_DEFAULT_INDUSTRY in ["general", "healthcare", "finance", "education"], \
    "ADAPTIVE_DEFAULT_INDUSTRY must be one of: general, healthcare, finance, education"

assert 60 <= LLM_PROFILE_CACHE_TTL <= 86400, \
    "LLM_PROFILE_CACHE_TTL must be between 60 and 86400 seconds"


def get_adaptive_config() -> dict:
    """Get current adaptive configuration."""
    return {
        "adaptive_tests_enabled": ADAPTIVE_TESTS_ENABLED,
        "adaptive_compliance_enabled": ADAPTIVE_COMPLIANCE_ENABLED,
        "adaptive_bias_enabled": ADAPTIVE_BIAS_ENABLED,
        "adaptive_fallback_enabled": ADAPTIVE_FALLBACK_ENABLED,
        "llm_profiling_enabled": LLM_PROFILING_ENABLED,
        "llm_profile_cache_ttl": LLM_PROFILE_CACHE_TTL,
        "adaptive_cultural_context": ADAPTIVE_CULTURAL_CONTEXT,
        "adaptive_primary_language": ADAPTIVE_PRIMARY_LANGUAGE,
        "adaptive_default_industry": ADAPTIVE_DEFAULT_INDUSTRY,
        "adaptive_domain_tests_enabled": ADAPTIVE_DOMAIN_TESTS_ENABLED
    }


def is_adaptive_enabled(test_type: str) -> bool:
    """Check if adaptive generation is enabled for a specific test type."""
    if not ADAPTIVE_TESTS_ENABLED:
        return False
    
    if test_type == "compliance_smoke":
        return ADAPTIVE_COMPLIANCE_ENABLED
    elif test_type == "bias_smoke":
        return ADAPTIVE_BIAS_ENABLED
    else:
        return True  # Default to enabled for other types
