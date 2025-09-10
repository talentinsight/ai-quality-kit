"""
Safety Suite Configuration.

Environment variables and configuration settings for the Safety suite.
"""

import os
from typing import List, Optional


class SafetyConfig:
    """Configuration for Safety suite."""
    
    # Core Safety settings
    ENABLED: bool = os.getenv("SAFETY_ENABLED", "true").lower() == "true"
    FAIL_FAST: bool = os.getenv("SAFETY_FAIL_FAST", "true").lower() == "true"
    
    # Required categories (comma-separated)
    REQUIRED_CATEGORIES_STR: str = os.getenv("SAFETY_REQUIRED_CATEGORIES", "toxicity,hate")
    REQUIRED_CATEGORIES: List[str] = [
        cat.strip() for cat in REQUIRED_CATEGORIES_STR.split(",") if cat.strip()
    ]
    
    # ML Provider settings
    ML_PROVIDER: str = os.getenv("SAFETY_ML_PROVIDER", "heuristic")  # "heuristic" or "ml"
    TOXICITY_THRESHOLD: float = float(os.getenv("SAFETY_TOXICITY_THRESHOLD", "0.8"))
    
    # Three-point moderation
    THREE_POINT_ENFORCED: bool = os.getenv("SAFETY_THREE_POINT_ENFORCED", "true").lower() == "true"
    
    # UI Template visibility
    SHOW_JSONL_TEMPLATE: bool = os.getenv("SHOW_SAFETY_JSONL_TEMPLATE", "false").lower() == "true"
    
    @classmethod
    def is_ml_provider_available(cls) -> bool:
        """Check if ML provider is available and configured."""
        if cls.ML_PROVIDER != "ml":
            return False
        
        # Add checks for ML provider availability here
        # For now, assume it's available if configured
        return True
    
    @classmethod
    def get_effective_provider(cls) -> str:
        """Get the effective provider (fallback to heuristic if ML unavailable)."""
        if cls.ML_PROVIDER == "ml" and cls.is_ml_provider_available():
            return "ml"
        return "heuristic"
    
    @classmethod
    def should_require_category(cls, category: str, case_required: Optional[bool] = None) -> bool:
        """
        Determine if a category should be required.
        
        Args:
            category: The safety category
            case_required: The case-level required flag (if present)
            
        Returns:
            True if the category should be required
        """
        # Case-level required flag takes precedence
        if case_required is not None:
            return case_required
        
        # Fall back to global required categories
        return category in cls.REQUIRED_CATEGORIES


# Global instance
safety_config = SafetyConfig()
