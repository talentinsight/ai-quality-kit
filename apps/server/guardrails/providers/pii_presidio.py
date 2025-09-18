"""PII detection provider using Microsoft Presidio."""

import logging
from typing import Optional, Dict, Any
from ..interfaces import GuardrailProvider, SignalResult, SignalLabel, GuardrailCategory
from ..registry import register_provider

logger = logging.getLogger(__name__)


@register_provider("pii.presidio", GuardrailCategory.PII)
class PresidioPIIProvider(GuardrailProvider):
    """PII detection using Microsoft Presidio."""
    
    def __init__(self):
        super().__init__("pii.presidio", GuardrailCategory.PII)
        self.requires_llm = True
        self._analyzer = None
        self._available = None
    
    def is_available(self) -> bool:
        """Check if Presidio dependencies are available."""
        if self._available is not None:
            return self._available
        
        try:
            from presidio_analyzer import AnalyzerEngine
            self._analyzer = AnalyzerEngine()
            self._available = True
            logger.info("Presidio PII provider initialized successfully")
        except ImportError as e:
            logger.warning(f"Presidio not available: {e}")
            self._available = False
        except Exception as e:
            logger.warning(f"Presidio initialization failed: {e}")
            self._available = False
        
        return self._available
    
    def check_dependencies(self) -> list[str]:
        """Check for missing dependencies."""
        missing = []
        
        try:
            from presidio_analyzer import AnalyzerEngine
        except ImportError:
            missing.append("presidio-analyzer")
        
        try:
            import spacy
        except ImportError:
            missing.append("spacy")
        
        return missing
    
    @property
    def version(self) -> Optional[str]:
        """Get provider version."""
        try:
            import presidio_analyzer
            return getattr(presidio_analyzer, '__version__', 'unknown')
        except ImportError:
            return None
    
    async def check(self, input_text: str, output_text: Optional[str] = None) -> SignalResult:
        """Check for PII in input and output text."""
        if not self.is_available():
            return SignalResult(
                id=self.provider_id,
                category=self.category,
                score=0.0,
                label=SignalLabel.UNAVAILABLE,
                confidence=0.0,
                details={"missing_dep": True, "total_hits": 0}
            )
        
        total_hits = 0
        max_confidence = 0.0
        entity_types = set()
        
        # Check input text
        if input_text:
            input_results = self._analyzer.analyze(text=input_text, language="en")
            for result in input_results:
                total_hits += 1
                max_confidence = max(max_confidence, result.score)
                entity_types.add(result.entity_type)
        
        # Check output text
        if output_text:
            output_results = self._analyzer.analyze(text=output_text, language="en")
            for result in output_results:
                total_hits += 1
                max_confidence = max(max_confidence, result.score)
                entity_types.add(result.entity_type)
        
        # Normalize score (0-1, higher = riskier)
        # Use max confidence as the risk score
        score = max_confidence
        
        # Determine label
        if total_hits > 0:
            label = SignalLabel.HIT
        else:
            label = SignalLabel.CLEAN
        
        return SignalResult(
            id=self.provider_id,
            category=self.category,
            score=score,
            label=label,
            confidence=max_confidence,
            details={
                "total_hits": total_hits,
                "entity_types": list(entity_types),
                "max_confidence": max_confidence
            }
        )
