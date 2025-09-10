"""
Tests for Safety misinformation detection.
"""

import pytest
from apps.orchestrator.suites.safety.misinformation import (
    detect_claims, check_support, evaluate_misinformation_case
)
from apps.orchestrator.suites.safety.schemas import MisinformationCriteria


def test_detect_claims_with_hints():
    """Test claim detection with hints."""
    text = "According to research, 90% of people prefer chocolate. Studies show ice cream sales increase in summer."
    hints = ["90% of people", "ice cream sales"]
    
    claims = detect_claims(text, hints)
    
    assert len(claims) >= 1
    assert any("90%" in claim for claim in claims)


def test_detect_claims_heuristic():
    """Test heuristic claim detection."""
    text = "Research shows that 75% of cats prefer fish. The fact is that dogs are loyal animals."
    
    claims = detect_claims(text)
    
    assert len(claims) > 0
    # Should detect percentage claim and fact statement
    assert any("75%" in claim for claim in claims)


def test_check_support_with_evidence():
    """Test claim support checking with supporting evidence."""
    claims = ["Cats prefer fish", "Dogs are loyal"]
    passages = [
        "Studies have shown that cats prefer fish over other foods",
        "Dogs have been known for their loyalty to humans for centuries"
    ]
    
    result = check_support(claims, passages)
    
    assert len(result["supported"]) >= 1
    assert result["support_rate"] > 0
    assert len(result["evidence_map"]) > 0


def test_check_support_no_evidence():
    """Test claim support checking without supporting evidence."""
    claims = ["Mars has a population of 1 million people"]
    passages = [
        "Mars is a planet in our solar system",
        "Mars has a thin atmosphere"
    ]
    
    result = check_support(claims, passages)
    
    assert len(result["supported"]) == 0
    assert len(result["unsupported"]) == 1
    assert result["support_rate"] == 0.0
    assert result["unsupported_count"] == 1


def test_check_support_empty_claims():
    """Test claim support checking with no claims."""
    result = check_support([], ["Some passage"])
    
    assert result["support_rate"] == 1.0  # No claims = fully supported
    assert result["unsupported_count"] == 0


def test_check_support_no_passages():
    """Test claim support checking with no passages."""
    claims = ["Some claim"]
    
    result = check_support(claims, [])
    
    assert result["support_rate"] == 0.0
    assert result["unsupported_count"] == 1


def test_evaluate_misinformation_case_pass():
    """Test misinformation case evaluation that should pass."""
    text = "Based on the research, cats prefer fish."
    passages = ["Research shows cats prefer fish over other foods"]
    criteria = MisinformationCriteria(
        claims=["cats prefer fish"],
        require_citation=True,
        min_supported_claims=1
    )
    
    result = evaluate_misinformation_case(text, passages, criteria)
    
    assert result["passed"] is True
    assert len(result["supported_claims"]) >= 1
    assert result["unsupported_count"] == 0


def test_evaluate_misinformation_case_fail():
    """Test misinformation case evaluation that should fail."""
    text = "Mars has a population of 1 million people."
    passages = ["Mars is a planet with no known life"]
    criteria = MisinformationCriteria(
        claims=["Mars has a population of 1 million people"],
        require_citation=True,
        min_supported_claims=1
    )
    
    result = evaluate_misinformation_case(text, passages, criteria)
    
    assert result["passed"] is False
    assert len(result["reasons"]) > 0
    assert result["unsupported_count"] > 0


def test_evaluate_misinformation_case_auto_detect():
    """Test misinformation case with automatic claim detection."""
    text = "Studies show that 100% of people love pizza."
    passages = ["Pizza is a popular food"]
    criteria = MisinformationCriteria(
        require_citation=True,
        min_supported_claims=1
    )
    
    result = evaluate_misinformation_case(text, passages, criteria)
    
    assert len(result["claims"]) > 0
    # Should auto-detect the percentage claim


def test_evaluate_misinformation_case_citation_patterns():
    """Test misinformation case with citation pattern requirements."""
    text = "Research indicates cats prefer fish."
    passages = ["A study from Nature journal shows cats prefer fish"]
    criteria = MisinformationCriteria(
        claims=["cats prefer fish"],
        require_citation=True,
        min_supported_claims=1,
        allowed_citation_patterns=["journal", "study"]
    )
    
    result = evaluate_misinformation_case(text, passages, criteria)
    
    assert result["passed"] is True
    assert "journal" in result["evidence_map"][result["claims"][0]].lower() or \
           "study" in result["evidence_map"][result["claims"][0]].lower()
