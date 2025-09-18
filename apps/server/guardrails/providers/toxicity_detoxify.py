"""Toxicity detection provider using Detoxify."""

import logging
from typing import Optional, Dict, Any
from ..interfaces import GuardrailProvider, SignalResult, SignalLabel, GuardrailCategory
from ..registry import register_provider

logger = logging.getLogger(__name__)


@register_provider("toxicity.detoxify", GuardrailCategory.TOXICITY)
class DetoxifyToxicityProvider(GuardrailProvider):
    """Toxicity detection using Detoxify."""
    
    def __init__(self):
        super().__init__("toxicity.detoxify", GuardrailCategory.TOXICITY)
        self.requires_llm = True
        self._model = None
        self._available = None
    
    def is_available(self) -> bool:
        """Check if Detoxify dependencies are available."""
        if self._available is not None:
            return self._available
        
        try:
            from detoxify import Detoxify
            self._model = Detoxify('original')
            self._available = True
            logger.info("Detoxify toxicity provider initialized successfully")
        except ImportError as e:
            logger.warning(f"Detoxify not available: {e}")
            self._available = False
        except Exception as e:
            logger.warning(f"Detoxify initialization failed: {e}")
            self._available = False
        
        return self._available
    
    def check_dependencies(self) -> list[str]:
        """Check for missing dependencies."""
        missing = []
        
        try:
            from detoxify import Detoxify
        except ImportError:
            missing.append("detoxify")
        
        try:
            import torch
        except ImportError:
            missing.append("torch")
        
        return missing
    
    @property
    def version(self) -> Optional[str]:
        """Get provider version."""
        try:
            import detoxify
            return getattr(detoxify, '__version__', 'unknown')
        except ImportError:
            return None
    
    async def check(self, input_text: str, output_text: Optional[str] = None) -> SignalResult:
        """Check for toxicity in output text (primarily)."""
        if not self.is_available():
            return SignalResult(
                id=self.provider_id,
                category=self.category,
                score=0.0,
                label=SignalLabel.UNAVAILABLE,
                confidence=0.0,
                details={"missing_dep": True, "toxicity_score": 0.0}
            )
        
        # Focus on output text for toxicity (what the model generates)
        text_to_check = output_text or input_text
        if not text_to_check:
            return SignalResult(
                id=self.provider_id,
                category=self.category,
                score=0.0,
                label=SignalLabel.CLEAN,
                confidence=1.0,
                details={"toxicity_score": 0.0, "no_text": True}
            )
        
        try:
            # Get toxicity scores
            results = self._model.predict(text_to_check)
            
            # Extract main toxicity score
            toxicity_score = float(results.get('toxicity', 0.0))
            
            # Get all scores for details
            all_scores = {k: float(v) for k, v in results.items()}
            
            # Use toxicity score as main risk indicator
            score = toxicity_score
            confidence = min(1.0, toxicity_score + 0.1)  # Higher confidence for higher toxicity
            
            # Determine label based on score
            if toxicity_score > 0.5:
                label = SignalLabel.VIOLATION
            elif toxicity_score > 0.1:
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
                    "toxicity_score": toxicity_score,
                    "all_scores": all_scores,
                    "max_score": max(all_scores.values())
                }
            )
            
        except Exception as e:
            logger.error(f"Detoxify prediction failed: {e}")
            return SignalResult(
                id=self.provider_id,
                category=self.category,
                score=0.0,
                label=SignalLabel.UNAVAILABLE,
                confidence=0.0,
                details={"error": str(e), "toxicity_score": 0.0}
            )
