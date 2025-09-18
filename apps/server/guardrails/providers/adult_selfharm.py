"""Adult content and self-harm detection providers (feature-flagged)."""

import logging
from typing import Optional, Dict, Any
from ..interfaces import GuardrailProvider, SignalResult, SignalLabel, GuardrailCategory
from ..registry import register_provider

logger = logging.getLogger(__name__)


@register_provider("adult.detoxify", GuardrailCategory.ADULT)
class AdultContentProvider(GuardrailProvider):
    """Adult content detection using Detoxify (feature-flagged)."""
    
    def __init__(self):
        super().__init__("adult.detoxify", GuardrailCategory.ADULT)
        self.requires_llm = True
        self._model = None
        self._available = None
        self._feature_enabled = False  # Feature flag
    
    def set_feature_enabled(self, enabled: bool):
        """Enable/disable this feature."""
        self._feature_enabled = enabled
    
    def is_available(self) -> bool:
        """Check if available and feature is enabled."""
        if not self._feature_enabled:
            return False
            
        if self._available is not None:
            return self._available
        
        try:
            from detoxify import Detoxify
            self._model = Detoxify('original')
            self._available = True
            logger.info("Adult content provider initialized successfully")
        except ImportError as e:
            logger.warning(f"Detoxify not available for adult content: {e}")
            self._available = False
        except Exception as e:
            logger.warning(f"Adult content provider initialization failed: {e}")
            self._available = False
        
        return self._available
    
    async def check(self, input_text: str, output_text: Optional[str] = None) -> SignalResult:
        """Check for adult content."""
        if not self.is_available():
            return SignalResult(
                id=self.provider_id,
                category=self.category,
                score=0.0,
                label=SignalLabel.UNAVAILABLE,
                confidence=0.0,
                details={"missing_dep": True, "feature_disabled": not self._feature_enabled}
            )
        
        # Check output text primarily
        text_to_check = output_text or input_text or ""
        if not text_to_check:
            return SignalResult(
                id=self.provider_id,
                category=self.category,
                score=0.0,
                label=SignalLabel.CLEAN,
                confidence=1.0,
                details={"no_text": True}
            )
        
        try:
            # Get toxicity scores
            results = self._model.predict(text_to_check)
            
            # Focus on sexual/obscene categories
            sexual_score = float(results.get('sexual_explicit', 0.0))
            obscene_score = float(results.get('obscene', 0.0))
            
            # Adult content score (max of sexual/obscene)
            score = max(sexual_score, obscene_score)
            confidence = min(1.0, score + 0.2)
            
            # Determine label
            if score > 0.7:
                label = SignalLabel.VIOLATION
            elif score > 0.3:
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
                    "sexual_score": sexual_score,
                    "obscene_score": obscene_score,
                    "max_score": score
                }
            )
            
        except Exception as e:
            logger.error(f"Adult content detection failed: {e}")
            return SignalResult(
                id=self.provider_id,
                category=self.category,
                score=0.0,
                label=SignalLabel.UNAVAILABLE,
                confidence=0.0,
                details={"error": str(e)}
            )


@register_provider("selfharm.heuristics", GuardrailCategory.SELF_HARM)
class SelfHarmProvider(GuardrailProvider):
    """Self-harm detection using lightweight heuristics (feature-flagged)."""
    
    def __init__(self):
        super().__init__("selfharm.heuristics", GuardrailCategory.SELF_HARM)
        self.requires_llm = False
        self._available = True
        self._feature_enabled = False  # Feature flag
        self._patterns = self._load_patterns()
    
    def set_feature_enabled(self, enabled: bool):
        """Enable/disable this feature."""
        self._feature_enabled = enabled
    
    def _load_patterns(self) -> list:
        """Load self-harm detection patterns."""
        return [
            # Direct self-harm references
            {
                "pattern": r"(?i)(self.harm|self.hurt|hurt.myself|harm.myself)",
                "weight": 0.9,
                "category": "direct_selfharm"
            },
            # Suicide references
            {
                "pattern": r"(?i)(suicide|kill.myself|end.my.life|take.my.life)",
                "weight": 1.0,
                "category": "suicide"
            },
            # Self-injury
            {
                "pattern": r"(?i)(cut.myself|cutting|self.injury|self.mutilation)",
                "weight": 0.8,
                "category": "self_injury"
            },
            # Depression/hopelessness (lower weight)
            {
                "pattern": r"(?i)(want.to.die|no.point.living|life.not.worth)",
                "weight": 0.7,
                "category": "hopelessness"
            }
        ]
    
    def is_available(self) -> bool:
        """Check if feature is enabled."""
        return self._available and self._feature_enabled
    
    async def check(self, input_text: str, output_text: Optional[str] = None) -> SignalResult:
        """Check for self-harm content."""
        if not self.is_available():
            return SignalResult(
                id=self.provider_id,
                category=self.category,
                score=0.0,
                label=SignalLabel.UNAVAILABLE,
                confidence=0.0,
                details={"missing_dep": True, "feature_disabled": not self._feature_enabled}
            )
        
        # Check both input and output
        text_to_check = f"{input_text or ''} {output_text or ''}".strip()
        if not text_to_check:
            return SignalResult(
                id=self.provider_id,
                category=self.category,
                score=0.0,
                label=SignalLabel.CLEAN,
                confidence=1.0,
                details={"no_text": True}
            )
        
        import re
        matches = []
        max_weight = 0.0
        
        # Check against patterns
        for pattern_info in self._patterns:
            pattern = pattern_info["pattern"]
            weight = pattern_info["weight"]
            category = pattern_info["category"]
            
            if re.search(pattern, text_to_check):
                matches.append({
                    "category": category,
                    "weight": weight
                })
                max_weight = max(max_weight, weight)
        
        # Score based on highest weight match
        score = max_weight
        confidence = 0.8 if matches else 0.9
        
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
                "matches": matches,
                "match_count": len(matches),
                "max_weight": max_weight
            }
        )
