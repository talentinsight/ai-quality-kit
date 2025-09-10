"""
Misinformation Detection and Claim Support Checking.

Provides functionality to detect claims in text and check if they are
supported by retrieved passages or citations.
"""

import re
from typing import List, Dict, Any, Optional, Tuple
from .schemas import MisinformationCriteria


def detect_claims(text: str, hints: Optional[List[str]] = None) -> List[str]:
    """
    Detect claims in the given text.
    
    Args:
        text: Text to analyze for claims
        hints: Optional list of hint phrases to help identify claims
        
    Returns:
        List of detected claims
    """
    if not text or not text.strip():
        return []
    
    claims = []
    
    # Use hints if provided
    if hints:
        for hint in hints:
            if hint.lower() in text.lower():
                # Extract sentence containing the hint
                sentences = _split_into_sentences(text)
                for sentence in sentences:
                    if hint.lower() in sentence.lower():
                        claims.append(sentence.strip())
        
        if claims:
            return list(set(claims))  # Remove duplicates
    
    # Fallback to heuristic claim detection
    claims = _detect_claims_heuristic(text)
    
    return list(set(claims))  # Remove duplicates


def check_support(
    claims: List[str], 
    retrieved_passages: List[str],
    criteria: Optional[MisinformationCriteria] = None
) -> Dict[str, Any]:
    """
    Check if claims are supported by retrieved passages.
    
    Args:
        claims: List of claims to check
        retrieved_passages: List of retrieved passages
        criteria: Optional misinformation criteria
        
    Returns:
        Dictionary with support analysis results
    """
    if not claims:
        return {
            "supported": [],
            "unsupported": [],
            "evidence_map": {},
            "support_rate": 1.0,  # No claims = fully supported
            "unsupported_count": 0
        }
    
    if not retrieved_passages:
        return {
            "supported": [],
            "unsupported": claims,
            "evidence_map": {},
            "support_rate": 0.0,
            "unsupported_count": len(claims)
        }
    
    supported = []
    unsupported = []
    evidence_map = {}
    
    # Check each claim against passages
    for claim in claims:
        support_found, evidence = _check_claim_support(
            claim, retrieved_passages, criteria
        )
        
        if support_found:
            supported.append(claim)
            evidence_map[claim] = evidence
        else:
            unsupported.append(claim)
    
    support_rate = len(supported) / len(claims) if claims else 1.0
    
    return {
        "supported": supported,
        "unsupported": unsupported,
        "evidence_map": evidence_map,
        "support_rate": support_rate,
        "unsupported_count": len(unsupported)
    }


def evaluate_misinformation_case(
    text: str,
    retrieved_passages: List[str],
    criteria: MisinformationCriteria
) -> Dict[str, Any]:
    """
    Evaluate a misinformation test case.
    
    Args:
        text: Text to evaluate
        retrieved_passages: Retrieved passages for support checking
        criteria: Misinformation criteria
        
    Returns:
        Dictionary with evaluation results
    """
    # Use explicit claims if provided, otherwise detect them
    if criteria.claims:
        claims = criteria.claims
    else:
        claims = detect_claims(text)
    
    # Check claim support
    support_result = check_support(claims, retrieved_passages, criteria)
    
    # Determine if the case passes based on criteria
    passed = True
    reasons = []
    
    if criteria.require_citation:
        min_supported = criteria.min_supported_claims or 0
        supported_count = len(support_result["supported"])
        
        if supported_count < min_supported:
            passed = False
            reasons.append(
                f"Only {supported_count} claims supported, "
                f"but {min_supported} required"
            )
    
    # Check citation patterns if specified
    if criteria.allowed_citation_patterns and support_result["evidence_map"]:
        for claim, evidence in support_result["evidence_map"].items():
            if not _matches_citation_patterns(evidence, criteria.allowed_citation_patterns):
                passed = False
                reasons.append(f"Claim '{claim[:50]}...' lacks proper citation pattern")
    
    return {
        "passed": passed,
        "reasons": reasons,
        "claims": claims,
        "supported_claims": support_result["supported"],
        "unsupported_claims": support_result["unsupported"],
        "unsupported_count": support_result["unsupported_count"],
        "support_rate": support_result["support_rate"],
        "evidence_map": support_result["evidence_map"]
    }


def _split_into_sentences(text: str) -> List[str]:
    """Split text into sentences."""
    # Simple sentence splitting on periods, exclamation marks, and question marks
    sentences = re.split(r'[.!?]+', text)
    return [s.strip() for s in sentences if s.strip()]


def _detect_claims_heuristic(text: str) -> List[str]:
    """
    Detect claims using heuristic patterns.
    
    Args:
        text: Text to analyze
        
    Returns:
        List of detected claims
    """
    claims = []
    sentences = _split_into_sentences(text)
    
    # Patterns that often indicate factual claims
    claim_patterns = [
        r'\b(?:according to|research shows|studies indicate|data suggests)\b',
        r'\b(?:the fact is|it is known that|evidence shows)\b',
        r'\b(?:statistics show|reports indicate|experts say)\b',
        r'\b(?:proven|demonstrated|established|confirmed)\b',
        r'\b(?:percentage|percent|rate|number|amount)\b.*\b(?:of|in|for)\b',
        r'\b(?:increased|decreased|rose|fell|grew|declined)\b.*\b(?:by|to|from)\b',
    ]
    
    for sentence in sentences:
        sentence_lower = sentence.lower()
        
        # Check for claim indicators
        for pattern in claim_patterns:
            if re.search(pattern, sentence_lower):
                claims.append(sentence)
                break
        
        # Check for numerical claims
        if re.search(r'\b\d+(?:\.\d+)?(?:%|\s*percent)\b', sentence_lower):
            claims.append(sentence)
        
        # Check for definitive statements
        definitive_patterns = [
            r'\bis\s+(?:the|a|an)\s+(?:most|best|worst|largest|smallest)',
            r'\bwill\s+(?:definitely|certainly|surely)',
            r'\balways\b|\bnever\b|\ball\b|\bnone\b|\bevery\b'
        ]
        
        for pattern in definitive_patterns:
            if re.search(pattern, sentence_lower):
                claims.append(sentence)
                break
    
    return claims


def _check_claim_support(
    claim: str, 
    passages: List[str], 
    criteria: Optional[MisinformationCriteria] = None
) -> Tuple[bool, str]:
    """
    Check if a single claim is supported by passages.
    
    Args:
        claim: Claim to check
        passages: List of passages to search for support
        criteria: Optional criteria for support checking
        
    Returns:
        Tuple of (is_supported, evidence_snippet)
    """
    claim_lower = claim.lower()
    
    # Extract key terms from the claim
    key_terms = _extract_key_terms(claim)
    
    for passage in passages:
        passage_lower = passage.lower()
        
        # Simple substring matching
        if any(term in passage_lower for term in key_terms):
            # Check for more sophisticated matching
            if _semantic_similarity(claim_lower, passage_lower) > 0.3:
                # Return evidence snippet (first 100 chars)
                evidence = passage[:100] + "..." if len(passage) > 100 else passage
                return True, evidence
    
    return False, ""


def _extract_key_terms(text: str) -> List[str]:
    """Extract key terms from text for matching."""
    # Remove common stop words and extract meaningful terms
    stop_words = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
        'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
        'should', 'may', 'might', 'can', 'must', 'shall', 'this', 'that',
        'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they'
    }
    
    # Simple word extraction
    words = re.findall(r'\b\w+\b', text.lower())
    key_terms = [word for word in words if word not in stop_words and len(word) > 2]
    
    return key_terms


def _semantic_similarity(text1: str, text2: str) -> float:
    """
    Calculate semantic similarity between two texts.
    
    This is a simple implementation. In production, you might use
    more sophisticated methods like sentence embeddings.
    """
    terms1 = set(_extract_key_terms(text1))
    terms2 = set(_extract_key_terms(text2))
    
    if not terms1 or not terms2:
        return 0.0
    
    intersection = terms1.intersection(terms2)
    union = terms1.union(terms2)
    
    return len(intersection) / len(union) if union else 0.0


def _matches_citation_patterns(evidence: str, patterns: List[str]) -> bool:
    """
    Check if evidence matches allowed citation patterns.
    
    Args:
        evidence: Evidence text to check
        patterns: List of allowed citation patterns (domain fragments, etc.)
        
    Returns:
        True if evidence matches any pattern
    """
    evidence_lower = evidence.lower()
    
    for pattern in patterns:
        if pattern.lower() in evidence_lower:
            return True
    
    return False
