"""
Tests for Safety moderation system.
"""

import pytest
from apps.orchestrator.suites.safety.moderation import (
    moderate_input, moderate_retrieved, moderate_output, 
    get_moderation_stats
)


def test_moderate_input_toxic():
    """Test input moderation with toxic content."""
    toxic_input = "You are such an idiot and I hate you"
    
    result = moderate_input(toxic_input)
    
    assert result.blocked is True
    assert len(result.labels) > 0
    assert any("toxicity" in label or "hate" in label for label in result.labels)
    assert len(result.reasons) > 0


def test_moderate_input_clean():
    """Test input moderation with clean content."""
    clean_input = "Hello, how are you today?"
    
    result = moderate_input(clean_input)
    
    assert result.blocked is False
    assert len(result.labels) == 0


def test_moderate_retrieved_mixed():
    """Test retrieved passages moderation with mixed content."""
    passages = [
        "This is a normal passage about weather.",
        "Violence and harm are dangerous topics.",
        "Another clean passage about science."
    ]
    
    results = moderate_retrieved(passages)
    
    assert len(results) == 3
    assert results[0].blocked is False  # Clean passage
    assert results[1].blocked is True   # Violent passage
    assert results[2].blocked is False  # Clean passage
    
    # Check redaction for blocked content
    assert results[1].redacted_text is not None


def test_moderate_output_harmful():
    """Test output moderation with harmful content."""
    harmful_output = "Here's how to create weapons and hurt people"
    
    result = moderate_output(harmful_output)
    
    assert result.blocked is True
    assert "violence" in result.labels
    assert result.redacted_text is not None


def test_moderate_empty_content():
    """Test moderation with empty content."""
    result = moderate_input("")
    assert result.blocked is False
    assert len(result.labels) == 0
    
    result = moderate_input(None)
    assert result.blocked is False


def test_get_moderation_stats():
    """Test moderation statistics generation."""
    # Create mock results
    from apps.orchestrator.suites.safety.schemas import ModerationResult
    
    results = [
        ModerationResult(blocked=True, labels=["toxicity"], score=0.9),
        ModerationResult(blocked=False, labels=[], score=0.1),
        ModerationResult(blocked=True, labels=["hate", "toxicity"], score=0.8),
    ]
    
    stats = get_moderation_stats(results)
    
    assert stats["total_checked"] == 3
    assert stats["blocked_count"] == 2
    assert stats["blocked_rate"] == 2/3
    assert stats["labels_distribution"]["toxicity"] == 2
    assert stats["labels_distribution"]["hate"] == 1
    assert stats["avg_score"] == (0.9 + 0.1 + 0.8) / 3


def test_get_moderation_stats_empty():
    """Test moderation statistics with empty results."""
    stats = get_moderation_stats([])
    
    assert stats["total_checked"] == 0
    assert stats["blocked_count"] == 0
    assert stats["blocked_rate"] == 0.0
    assert stats["labels_distribution"] == {}
    assert stats["avg_score"] is None
