"""Schema validation provider for Tools/Function JSON outputs."""

import logging
import json
from typing import Optional, Dict, Any
from ..interfaces import GuardrailProvider, SignalResult, SignalLabel, GuardrailCategory
from ..registry import register_provider

logger = logging.getLogger(__name__)


@register_provider("schema.guard", GuardrailCategory.SCHEMA)
class SchemaGuardProvider(GuardrailProvider):
    """Schema validation for JSON outputs using jsonschema."""
    
    def __init__(self):
        super().__init__("schema.guard", GuardrailCategory.SCHEMA)
        self.requires_llm = True  # Needs LLM output to validate
        self._validator = None
        self._available = None
    
    def is_available(self) -> bool:
        """Check if jsonschema is available."""
        if self._available is not None:
            return self._available
        
        try:
            import jsonschema
            self._available = True
            logger.info("Schema guard provider initialized successfully")
        except ImportError as e:
            logger.warning(f"jsonschema not available: {e}")
            self._available = False
        
        return self._available
    
    def _extract_json_from_output(self, output_text: str) -> Optional[Dict[str, Any]]:
        """Extract JSON from LLM output text."""
        if not output_text:
            return None
        
        # Try to find JSON in the output
        # Look for JSON blocks or direct JSON
        json_patterns = [
            # JSON code blocks
            r'```json\s*(\{.*?\})\s*```',
            r'```\s*(\{.*?\})\s*```',
            # Direct JSON (simple heuristic)
            r'(\{[^{}]*\})',
        ]
        
        import re
        for pattern in json_patterns:
            matches = re.findall(pattern, output_text, re.DOTALL | re.IGNORECASE)
            for match in matches:
                try:
                    return json.loads(match.strip())
                except json.JSONDecodeError:
                    continue
        
        # Try parsing the entire output as JSON
        try:
            return json.loads(output_text.strip())
        except json.JSONDecodeError:
            return None
    
    async def check(self, input_text: str, output_text: Optional[str] = None) -> SignalResult:
        """Validate JSON output against schema."""
        if not self.is_available():
            return SignalResult(
                id=self.provider_id,
                category=self.category,
                score=0.0,
                label=SignalLabel.UNAVAILABLE,
                confidence=0.0,
                details={"missing_dep": True}
            )
        
        # Need output text to validate
        if not output_text:
            return SignalResult(
                id=self.provider_id,
                category=self.category,
                score=0.0,
                label=SignalLabel.CLEAN,
                confidence=0.5,
                details={"no_output": True, "validation_skipped": True}
            )
        
        # Extract JSON from output
        json_data = self._extract_json_from_output(output_text)
        if json_data is None:
            return SignalResult(
                id=self.provider_id,
                category=self.category,
                score=0.3,  # Mild concern if expecting JSON but none found
                label=SignalLabel.HIT,
                confidence=0.7,
                details={"no_json_found": True, "output_length": len(output_text)}
            )
        
        # For now, perform basic JSON structure validation
        # In a real implementation, this would validate against a provided schema
        validation_results = self._basic_json_validation(json_data)
        
        # Calculate score based on validation results
        score = 0.0
        if not validation_results["valid_structure"]:
            score += 0.4
        if validation_results["missing_common_fields"]:
            score += 0.3
        if validation_results["suspicious_content"]:
            score += 0.5
        
        score = min(1.0, score)
        confidence = 0.8
        
        # Determine label
        if score > 0.6:
            label = SignalLabel.VIOLATION
        elif score > 0.2:
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
                "json_found": True,
                "json_keys": list(json_data.keys()) if isinstance(json_data, dict) else [],
                "validation": validation_results
            }
        )
    
    def _basic_json_validation(self, json_data: Dict[str, Any]) -> Dict[str, Any]:
        """Perform basic JSON structure validation."""
        if not isinstance(json_data, dict):
            return {
                "valid_structure": False,
                "missing_common_fields": True,
                "suspicious_content": False,
                "error": "JSON is not an object"
            }
        
        # Check for common function call fields
        common_fields = ["name", "function", "action", "parameters", "args", "arguments"]
        has_common_field = any(field in json_data for field in common_fields)
        
        # Check for suspicious content (very basic)
        suspicious_patterns = ["ignore", "bypass", "override", "system", "prompt"]
        suspicious_content = False
        
        for value in json_data.values():
            if isinstance(value, str):
                if any(pattern in value.lower() for pattern in suspicious_patterns):
                    suspicious_content = True
                    break
        
        return {
            "valid_structure": True,
            "missing_common_fields": not has_common_field,
            "suspicious_content": suspicious_content,
            "field_count": len(json_data),
            "has_common_field": has_common_field
        }
