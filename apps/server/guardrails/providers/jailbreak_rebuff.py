"""Prompt injection/jailbreak detection using Rebuff heuristics."""

import logging
import re
from typing import Optional, Dict, Any, List
from ..interfaces import GuardrailProvider, SignalResult, SignalLabel, GuardrailCategory
from ..registry import register_provider

logger = logging.getLogger(__name__)


@register_provider("jailbreak.rebuff", GuardrailCategory.JAILBREAK)
class RebuffJailbreakProvider(GuardrailProvider):
    """Prompt injection detection using Rebuff-inspired heuristics."""
    
    def __init__(self):
        super().__init__("jailbreak.rebuff", GuardrailCategory.JAILBREAK)
        self.requires_llm = False  # Heuristic-based, no LLM needed
        self._patterns = self._load_patterns()
        self._available = True
    
    def _load_patterns(self) -> List[Dict[str, Any]]:
        """Load canonical prompt injection patterns."""
        return [
            # Direct instruction override
            {
                "pattern": r"(?i)(ignore|forget|disregard).*(previous|above|prior).*(instruction|prompt|rule)",
                "weight": 0.8,
                "category": "instruction_override"
            },
            # System prompt extraction
            {
                "pattern": r"(?i)(show|tell|reveal|display).*(system|initial|original).*(prompt|instruction)",
                "weight": 0.9,
                "category": "system_extraction"
            },
            # Role playing attacks
            {
                "pattern": r"(?i)(pretend|act|roleplay|imagine).*(you are|you're).*(not bound|without|ignore)",
                "weight": 0.7,
                "category": "roleplay"
            },
            # DAN-style attacks
            {
                "pattern": r"(?i)(do anything now|DAN|jailbreak|unrestricted|no limitations)",
                "weight": 0.9,
                "category": "dan_style"
            },
            # Hypothetical scenarios
            {
                "pattern": r"(?i)(hypothetically|theoretically|in theory|what if).*(ignore|bypass|without)",
                "weight": 0.6,
                "category": "hypothetical"
            },
            # Developer mode
            {
                "pattern": r"(?i)(developer|debug|admin|root).*(mode|access|privilege)",
                "weight": 0.8,
                "category": "developer_mode"
            },
            # Encoding attempts
            {
                "pattern": r"(?i)(base64|hex|rot13|caesar|encode|decode)",
                "weight": 0.5,
                "category": "encoding"
            },
            # Language switching
            {
                "pattern": r"(?i)(translate|in [a-z]+ language|respond in)",
                "weight": 0.4,
                "category": "language_switch"
            }
        ]
    
    def is_available(self) -> bool:
        """Always available (heuristic-based)."""
        return self._available
    
    async def check(self, input_text: str, output_text: Optional[str] = None) -> SignalResult:
        """Check for prompt injection patterns."""
        if not self.is_available():
            return SignalResult(
                id=self.provider_id,
                category=self.category,
                score=0.0,
                label=SignalLabel.UNAVAILABLE,
                confidence=0.0,
                details={"missing_dep": True}
            )
        
        # Focus on input text for jailbreak detection
        text_to_check = input_text or ""
        if not text_to_check:
            return SignalResult(
                id=self.provider_id,
                category=self.category,
                score=0.0,
                label=SignalLabel.CLEAN,
                confidence=1.0,
                details={"matches": [], "max_weight": 0.0}
            )
        
        matches = []
        max_weight = 0.0
        total_score = 0.0
        
        # Check against all patterns
        for pattern_info in self._patterns:
            pattern = pattern_info["pattern"]
            weight = pattern_info["weight"]
            category = pattern_info["category"]
            
            if re.search(pattern, text_to_check):
                matches.append({
                    "category": category,
                    "weight": weight,
                    "pattern_type": pattern_info["category"]
                })
                max_weight = max(max_weight, weight)
                total_score += weight
        
        # Normalize score (cap at 1.0)
        score = min(1.0, total_score / 2.0)  # Divide by 2 to prevent easy saturation
        confidence = min(1.0, max_weight + 0.1) if matches else 0.9
        
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
                "matches": matches,
                "match_count": len(matches),
                "max_weight": max_weight,
                "total_score": total_score
            }
        )
