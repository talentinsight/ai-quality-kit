"""Hardened compliance scanning with improved PII detection accuracy."""

import re
import json
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class ComplianceMatch:
    """Enhanced compliance match with detailed metadata."""
    pattern_id: str
    match_span: Tuple[int, int]
    normalized_snippet: str
    confidence: float = 1.0
    match_type: str = "exact"


class LuhnValidator:
    """Luhn algorithm validator for credit card numbers."""
    
    @staticmethod
    def validate(number_str: str) -> bool:
        """Validate a number string using Luhn algorithm."""
        # Remove non-digits
        digits = [int(d) for d in number_str if d.isdigit()]
        
        if len(digits) < 8:  # Too short to be a valid credit card
            return False
        
        # Apply Luhn algorithm
        total = 0
        reverse_digits = digits[::-1]
        
        for i, digit in enumerate(reverse_digits):
            if i % 2 == 1:  # Every second digit from right
                digit *= 2
                if digit > 9:
                    digit = digit // 10 + digit % 10
            total += digit
        
        return total % 10 == 0


class HardenedPIIScanner:
    """Hardened PII scanner with reduced false positives."""
    
    # Allowlist for obviously fake/demo data
    ALLOWLIST_PATTERNS = {
        "ssn": {
            "000-00-0000", "123-45-6789", "111-11-1111", "222-22-2222",
            "333-33-3333", "444-44-4444", "555-55-5555", "666-66-6666",
            "777-77-7777", "888-88-8888", "999-99-9999"
        },
        "phone": {
            "000-000-0000", "111-111-1111", "123-456-7890", "555-555-5555",
            "(555) 555-5555", "1-800-555-5555"
        },
        "email": {
            "test@example.com", "user@example.org", "demo@test.com", 
            "sample@demo.net", "example@example.com"
        },
        "credit_card": {
            "4111111111111111", "4000000000000000", "5555555555554444",
            "4111-1111-1111-1111", "4000-0000-0000-0000"
        }
    }
    
    def __init__(self, patterns_file: Optional[str] = None):
        self.patterns = self._load_patterns(patterns_file)
        self.compiled_patterns = self._compile_patterns()
    
    def _load_patterns(self, patterns_file: Optional[str]) -> Dict[str, Any]:
        """Load PII patterns from file with fallback defaults."""
        default_patterns = {
            "ssn": {
                "pattern": r"\b\d{3}-\d{2}-\d{4}\b",
                "description": "Social Security Number (XXX-XX-XXXX)"
            },
            "phone": {
                "pattern": r"\b\(?(\d{3})\)?[-.\s]?(\d{3})[-.\s]?(\d{4})\b",
                "description": "Phone number"
            },
            "email": {
                "pattern": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
                "description": "Email address"
            },
            "credit_card": {
                "pattern": r"\b(?:\d{4}[-\s]?){3}\d{4}\b",
                "description": "Credit card number"
            },
            "drivers_license": {
                "pattern": r"\b[A-Z]{1,2}\d{6,8}\b",
                "description": "Driver's license"
            },
            "ip_address": {
                "pattern": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
                "description": "IP address"
            }
        }
        
        if patterns_file:
            try:
                with open(patterns_file, 'r', encoding='utf-8') as f:
                    loaded_patterns = json.load(f)
                    # Merge with defaults, preferring loaded patterns
                    default_patterns.update(loaded_patterns)
            except Exception as e:
                logger.warning(f"Could not load patterns from {patterns_file}: {e}")
        
        return default_patterns
    
    def _compile_patterns(self) -> Dict[str, re.Pattern]:
        """Compile regex patterns with word boundaries and anchoring."""
        compiled = {}
        
        for pattern_id, pattern_info in self.patterns.items():
            try:
                pattern = pattern_info.get("pattern", "")
                if not pattern:
                    continue
                
                # Make pattern word-boundary aware if not already anchored
                if not pattern.startswith((r'\b', '^')):
                    pattern = r'\b' + pattern
                if not pattern.endswith((r'\b', '$')):
                    pattern = pattern + r'\b'
                
                compiled[pattern_id] = re.compile(pattern, re.IGNORECASE | re.MULTILINE)
                
            except re.error as e:
                logger.warning(f"Invalid regex pattern for {pattern_id}: {e}")
                continue
        
        return compiled
    
    def scan_text(self, text: str, scan_fields: Optional[List[str]] = None) -> List[ComplianceMatch]:
        """Scan text for PII patterns with enhanced accuracy."""
        if not text:
            return []
        
        matches = []
        
        for pattern_id, compiled_pattern in self.compiled_patterns.items():
            pattern_matches = compiled_pattern.finditer(text)
            
            for match in pattern_matches:
                match_text = match.group(0)
                normalized_text = self._normalize_match(pattern_id, match_text)
                
                # Skip if in allowlist
                if self._is_allowlisted(pattern_id, normalized_text):
                    logger.debug(f"Skipping allowlisted {pattern_id}: {normalized_text}")
                    continue
                
                # Apply additional validation
                confidence = self._validate_match(pattern_id, normalized_text)
                if confidence < 0.5:  # Low confidence threshold
                    logger.debug(f"Skipping low confidence {pattern_id}: {normalized_text}")
                    continue
                
                matches.append(ComplianceMatch(
                    pattern_id=pattern_id,
                    match_span=(match.start(), match.end()),
                    normalized_snippet=normalized_text,
                    confidence=confidence,
                    match_type="regex"
                ))
        
        return matches
    
    def _normalize_match(self, pattern_id: str, match_text: str) -> str:
        """Normalize a matched text for consistent comparison."""
        normalized = match_text.strip().lower()
        
        if pattern_id == "phone":
            # Normalize phone numbers: remove formatting
            normalized = re.sub(r'[^\d]', '', normalized)
        elif pattern_id == "credit_card":
            # Normalize credit cards: remove spaces and dashes
            normalized = re.sub(r'[-\s]', '', normalized)
        elif pattern_id == "ssn":
            # SSN normalization: standardize format
            digits = re.sub(r'[^\d]', '', normalized)
            if len(digits) == 9:
                normalized = f"{digits[:3]}-{digits[3:5]}-{digits[5:]}"
        
        return normalized
    
    def _is_allowlisted(self, pattern_id: str, normalized_text: str) -> bool:
        """Check if a normalized match is in the allowlist."""
        allowlist = self.ALLOWLIST_PATTERNS.get(pattern_id, set())
        
        # Direct match
        if normalized_text in allowlist:
            return True
        
        # For phone numbers, check various formats
        if pattern_id == "phone":
            digits_only = re.sub(r'[^\d]', '', normalized_text)
            formatted_variants = [
                digits_only,
                f"{digits_only[:3]}-{digits_only[3:6]}-{digits_only[6:]}",
                f"({digits_only[:3]}) {digits_only[3:6]}-{digits_only[6:]}",
                f"1-{digits_only[:3]}-{digits_only[3:6]}-{digits_only[6:]}" if len(digits_only) == 10 else digits_only
            ]
            
            for variant in formatted_variants:
                if variant in allowlist:
                    return True
        
        return False
    
    def _validate_match(self, pattern_id: str, normalized_text: str) -> float:
        """Apply additional validation to determine match confidence."""
        confidence = 1.0
        
        if pattern_id == "credit_card":
            # Apply Luhn validation for credit cards
            digits_only = re.sub(r'[^\d]', '', normalized_text)
            if not LuhnValidator.validate(digits_only):
                confidence *= 0.3  # Significantly reduce confidence
        
        elif pattern_id == "ssn":
            # Basic SSN validation rules
            digits = re.sub(r'[^\d]', '', normalized_text)
            if len(digits) != 9:
                confidence *= 0.1
            elif digits[:3] == "000" or digits[3:5] == "00" or digits[5:] == "0000":
                confidence *= 0.1  # Invalid SSN format
        
        elif pattern_id == "email":
            # Basic email validation
            if "@" not in normalized_text or "." not in normalized_text.split("@")[-1]:
                confidence *= 0.2
        
        elif pattern_id == "phone":
            # Phone number validation
            digits = re.sub(r'[^\d]', '', normalized_text)
            if len(digits) not in [10, 11]:  # US phone numbers
                confidence *= 0.5
            elif digits.startswith("0") or digits.startswith("1") and len(digits) == 10:
                confidence *= 0.7  # Less likely formats
        
        elif pattern_id == "ip_address":
            # IP address validation
            try:
                parts = normalized_text.split(".")
                if len(parts) == 4:
                    for part in parts:
                        num = int(part)
                        if num < 0 or num > 255:
                            confidence *= 0.1
                            break
                else:
                    confidence *= 0.1
            except (ValueError, AttributeError):
                confidence *= 0.1
        
        return confidence
    
    def get_pattern_info(self, pattern_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific pattern."""
        return self.patterns.get(pattern_id)
    
    def get_summary(self, matches: List[ComplianceMatch]) -> Dict[str, Any]:
        """Get summary statistics for scan results."""
        if not matches:
            return {
                "total_matches": 0,
                "patterns_triggered": 0,
                "high_confidence_matches": 0,
                "by_pattern": {}
            }
        
        by_pattern = {}
        high_confidence = 0
        
        for match in matches:
            if match.pattern_id not in by_pattern:
                by_pattern[match.pattern_id] = {
                    "count": 0,
                    "avg_confidence": 0.0,
                    "matches": []
                }
            
            by_pattern[match.pattern_id]["count"] += 1
            by_pattern[match.pattern_id]["matches"].append({
                "snippet": match.normalized_snippet,
                "confidence": match.confidence,
                "span": match.match_span
            })
            
            if match.confidence >= 0.8:
                high_confidence += 1
        
        # Calculate average confidence per pattern
        for pattern_data in by_pattern.values():
            confidences = [m["confidence"] for m in pattern_data["matches"]]
            pattern_data["avg_confidence"] = sum(confidences) / len(confidences)
        
        return {
            "total_matches": len(matches),
            "patterns_triggered": len(by_pattern),
            "high_confidence_matches": high_confidence,
            "by_pattern": by_pattern
        }
