"""Resilience detection using heuristics for unicode, gibberish, and repeat patterns."""

import logging
import re
import unicodedata
from typing import Optional, Dict, Any
from collections import Counter
from ..interfaces import GuardrailProvider, SignalResult, SignalLabel, GuardrailCategory
from ..registry import register_provider

logger = logging.getLogger(__name__)


@register_provider("resilience.heuristics", GuardrailCategory.RESILIENCE)
class ResilienceHeuristicsProvider(GuardrailProvider):
    """Resilience detection using unicode confusables, gibberish, and repeat patterns."""
    
    def __init__(self):
        super().__init__("resilience.heuristics", GuardrailCategory.RESILIENCE)
        self.requires_llm = False
        self._available = True
        self._confusables_available = self._check_confusables()
    
    def _check_confusables(self) -> bool:
        """Check if confusable-homoglyphs is available."""
        try:
            import confusable_homoglyphs
            return True
        except ImportError:
            logger.warning("confusable-homoglyphs not available, unicode detection disabled")
            return False
    
    def is_available(self) -> bool:
        """Always available (basic heuristics work without dependencies)."""
        return self._available
    
    def _detect_unicode_confusables(self, text: str) -> Dict[str, Any]:
        """Detect unicode confusable characters."""
        if not self._confusables_available:
            return {"confusable_chars": 0, "confusable_ratio": 0.0, "available": False}
        
        try:
            from confusable_homoglyphs import confusables
            
            confusable_count = 0
            total_chars = len(text)
            
            for char in text:
                if confusables.is_confusable(char, preferred_aliases=['latin']):
                    confusable_count += 1
            
            ratio = confusable_count / max(1, total_chars)
            
            return {
                "confusable_chars": confusable_count,
                "confusable_ratio": ratio,
                "available": True
            }
        except Exception as e:
            logger.warning(f"Unicode confusables detection failed: {e}")
            return {"confusable_chars": 0, "confusable_ratio": 0.0, "available": False}
    
    def _detect_gibberish(self, text: str) -> Dict[str, Any]:
        """Detect gibberish using entropy and character distribution."""
        if not text:
            return {"entropy": 0.0, "vowel_ratio": 0.0, "is_gibberish": False}
        
        # Calculate character entropy
        char_counts = Counter(text.lower())
        total_chars = len(text)
        entropy = 0.0
        
        import math
        for count in char_counts.values():
            prob = count / total_chars
            if prob > 0:
                entropy -= prob * math.log2(prob)
        
        # Calculate vowel ratio
        vowels = set('aeiouAEIOU')
        vowel_count = sum(1 for char in text if char in vowels)
        vowel_ratio = vowel_count / max(1, len([c for c in text if c.isalpha()]))
        
        # Heuristic: high entropy + low vowel ratio = likely gibberish
        is_gibberish = entropy > 4.0 and vowel_ratio < 0.2
        
        return {
            "entropy": entropy,
            "vowel_ratio": vowel_ratio,
            "is_gibberish": is_gibberish
        }
    
    def _detect_repeat_patterns(self, text: str) -> Dict[str, Any]:
        """Detect excessive repetition patterns."""
        if not text:
            return {"max_repeat": 0, "repeat_ratio": 0.0, "excessive_repeat": False}
        
        # Find maximum consecutive character repetition
        max_repeat = 1
        current_repeat = 1
        
        for i in range(1, len(text)):
            if text[i] == text[i-1]:
                current_repeat += 1
                max_repeat = max(max_repeat, current_repeat)
            else:
                current_repeat = 1
        
        # Calculate overall repetition ratio
        char_counts = Counter(text)
        most_common_count = char_counts.most_common(1)[0][1] if char_counts else 0
        repeat_ratio = most_common_count / max(1, len(text))
        
        # Detect excessive repetition
        excessive_repeat = max_repeat > 10 or repeat_ratio > 0.5
        
        return {
            "max_repeat": max_repeat,
            "repeat_ratio": repeat_ratio,
            "excessive_repeat": excessive_repeat
        }
    
    def _detect_very_long_input(self, text: str) -> Dict[str, Any]:
        """Detect unusually long inputs."""
        length = len(text)
        word_count = len(text.split())
        
        # Thresholds for "very long"
        very_long_chars = length > 10000  # 10k characters
        very_long_words = word_count > 2000  # 2k words
        
        return {
            "char_count": length,
            "word_count": word_count,
            "very_long_chars": very_long_chars,
            "very_long_words": very_long_words,
            "very_long": very_long_chars or very_long_words
        }
    
    async def check(self, input_text: str, output_text: Optional[str] = None) -> SignalResult:
        """Check for resilience issues in input text."""
        if not self.is_available():
            return SignalResult(
                id=self.provider_id,
                category=self.category,
                score=0.0,
                label=SignalLabel.UNAVAILABLE,
                confidence=0.0,
                details={"missing_dep": True}
            )
        
        # Focus on input text for resilience attacks
        text_to_check = input_text or ""
        if not text_to_check:
            return SignalResult(
                id=self.provider_id,
                category=self.category,
                score=0.0,
                label=SignalLabel.CLEAN,
                confidence=1.0,
                details={"no_text": True}
            )
        
        # Run all detection methods
        unicode_result = self._detect_unicode_confusables(text_to_check)
        gibberish_result = self._detect_gibberish(text_to_check)
        repeat_result = self._detect_repeat_patterns(text_to_check)
        length_result = self._detect_very_long_input(text_to_check)
        
        # Calculate composite score
        score_components = []
        
        # Unicode confusables (if available)
        if unicode_result["available"]:
            score_components.append(min(1.0, unicode_result["confusable_ratio"] * 2))
        
        # Gibberish detection
        if gibberish_result["is_gibberish"]:
            score_components.append(0.7)
        
        # Repeat patterns
        if repeat_result["excessive_repeat"]:
            score_components.append(0.8)
        
        # Very long input
        if length_result["very_long"]:
            score_components.append(0.6)
        
        # Composite score (max of components)
        score = max(score_components) if score_components else 0.0
        confidence = 0.8 if score_components else 0.9
        
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
                "unicode": unicode_result,
                "gibberish": gibberish_result,
                "repeat": repeat_result,
                "length": length_result,
                "score_components": score_components
            }
        )
