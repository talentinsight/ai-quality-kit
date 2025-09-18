"""
Three-Point Moderation System.

Provides moderation capabilities for input, retrieved passages, and output stages.
Supports both heuristic and ML-based approaches.
"""

import re
import time
from typing import List, Optional, Dict, Any
from .schemas import ModerationResult
from apps.config.safety import safety_config


# Heuristic patterns for different safety categories
TOXICITY_PATTERNS = [
    r'\b(?:fuck|shit|damn|bitch|asshole|bastard)\b',
    r'\b(?:kill yourself|kys|die)\b',
    r'\b(?:hate|despise|loathe)\s+(?:you|them|him|her)\b',
]

HATE_PATTERNS = [
    r'\b(?:nazi|hitler|holocaust)\b',
    r'\b(?:terrorist|extremist)\b',
    r'\b(?:racial|ethnic)\s+(?:slur|epithet)\b',
    r'\b(?:supremacist|supremacy)\b',
]

VIOLENCE_PATTERNS = [
    r'\b(?:murder|kill|assassinate|execute)\b',
    r'\b(?:bomb|explosion|weapon|gun|knife)\b',
    r'\b(?:torture|abuse|harm|hurt)\b',
    r'\b(?:fight|attack|assault|violence)\b',
]

ADULT_PATTERNS = [
    r'\b(?:sex|sexual|porn|pornography|nude|naked)\b',
    r'\b(?:explicit|graphic|adult)\s+(?:content|material)\b',
    r'\b(?:erotic|sensual|intimate)\b',
]

SELF_HARM_PATTERNS = [
    r'\b(?:suicide|self-harm|cutting|overdose)\b',
    r'\b(?:depression|anxiety|mental)\s+(?:health|illness)\b',
    r'\b(?:hopeless|worthless|useless)\b',
]

# Pattern mappings
CATEGORY_PATTERNS = {
    "toxicity": TOXICITY_PATTERNS,
    "hate": HATE_PATTERNS,
    "violence": VIOLENCE_PATTERNS,
    "adult": ADULT_PATTERNS,
    "self_harm": SELF_HARM_PATTERNS,
}


def moderate_input(text: str) -> ModerationResult:
    """
    Moderate input text at the INPUT stage.
    
    Args:
        text: Input text to moderate
        
    Returns:
        ModerationResult with moderation decision
    """
    if not text or not text.strip():
        return ModerationResult(blocked=False, labels=[], reasons=[])
    
    provider = safety_config.get_effective_provider()
    
    if provider == "ml":
        return _moderate_with_ml(text)
    else:
        return _moderate_with_heuristics(text)


def moderate_retrieved(passages: List[str]) -> List[ModerationResult]:
    """
    Moderate retrieved passages at the RETRIEVED stage.
    
    Args:
        passages: List of retrieved passages to moderate
        
    Returns:
        List of ModerationResult, one per passage
    """
    results = []
    
    for passage in passages:
        if not passage or not passage.strip():
            results.append(ModerationResult(blocked=False, labels=[], reasons=[]))
            continue
        
        provider = safety_config.get_effective_provider()
        
        if provider == "ml":
            result = _moderate_with_ml(passage)
        else:
            result = _moderate_with_heuristics(passage)
        
        # For retrieved content, we can drop or redact
        if result.blocked:
            # Decide whether to drop or redact based on severity
            if any(label in ["violence", "hate", "self_harm"] for label in result.labels):
                # Drop entirely for severe content
                result.redacted_text = "[CONTENT REMOVED]"
            else:
                # Redact for less severe content
                result.redacted_text = _redact_text(passage, result.labels)
        
        results.append(result)
    
    return results


def moderate_output(text: str) -> ModerationResult:
    """
    Moderate generated output at the OUTPUT stage.
    
    Args:
        text: Generated output text to moderate
        
    Returns:
        ModerationResult with moderation decision
    """
    if not text or not text.strip():
        return ModerationResult(blocked=False, labels=[], reasons=[])
    
    provider = safety_config.get_effective_provider()
    
    if provider == "ml":
        result = _moderate_with_ml(text)
    else:
        result = _moderate_with_heuristics(text)
    
    # For output, we can block or redact
    if result.blocked:
        result.redacted_text = _redact_text(text, result.labels)
    
    return result


def _moderate_with_ml(text: str) -> ModerationResult:
    """
    Moderate text using ML provider.
    
    Args:
        text: Text to moderate
        
    Returns:
        ModerationResult with ML-based moderation
    """
    # Placeholder for ML moderation
    # In a real implementation, this would call an ML service
    
    # For now, fall back to heuristics with a simulated ML score
    heuristic_result = _moderate_with_heuristics(text)
    
    # Add a simulated ML score
    if heuristic_result.blocked:
        heuristic_result.score = 0.85  # High confidence
    else:
        heuristic_result.score = 0.15  # Low confidence
    
    return heuristic_result


def _moderate_with_heuristics(text: str) -> ModerationResult:
    """
    Moderate text using heuristic patterns.
    
    Args:
        text: Text to moderate
        
    Returns:
        ModerationResult with heuristic-based moderation
    """
    text_lower = text.lower()
    labels = []
    reasons = []
    blocked = False
    
    # Check each category
    for category, patterns in CATEGORY_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                labels.append(category)
                reasons.append(f"Matched {category} pattern: {pattern}")
                blocked = True
                break  # One match per category is enough
    
    return ModerationResult(
        blocked=blocked,
        labels=list(set(labels)),  # Remove duplicates
        reasons=reasons
    )


def _redact_text(text: str, labels: List[str]) -> str:
    """
    Redact harmful content from text.
    
    Args:
        text: Original text
        labels: List of detected harmful labels
        
    Returns:
        Redacted text
    """
    redacted = text
    
    # Apply redaction patterns based on detected labels
    for label in labels:
        if label in CATEGORY_PATTERNS:
            for pattern in CATEGORY_PATTERNS[label]:
                redacted = re.sub(pattern, "[REDACTED]", redacted, flags=re.IGNORECASE)
    
    return redacted


def get_moderation_stats(results: List[ModerationResult]) -> Dict[str, Any]:
    """
    Get statistics from moderation results.
    
    Args:
        results: List of moderation results
        
    Returns:
        Dictionary with moderation statistics
    """
    if not results:
        return {
            "total_checked": 0,
            "blocked_count": 0,
            "blocked_rate": 0.0,
            "labels_distribution": {},
            "avg_score": None
        }
    
    blocked_count = sum(1 for r in results if r.blocked)
    all_labels = []
    scores = []
    
    for result in results:
        all_labels.extend(result.labels)
        if result.score is not None:
            scores.append(result.score)
    
    # Count label distribution
    labels_distribution = {}
    for label in all_labels:
        labels_distribution[label] = labels_distribution.get(label, 0) + 1
    
    return {
        "total_checked": len(results),
        "blocked_count": blocked_count,
        "blocked_rate": blocked_count / len(results),
        "labels_distribution": labels_distribution,
        "avg_score": sum(scores) / len(scores) if scores else None
    }
