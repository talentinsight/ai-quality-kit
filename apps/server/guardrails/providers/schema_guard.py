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
            # Direct JSON (match balanced braces)
            r'(\{(?:[^{}]|(?:\{[^{}]*\}))*\})',
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
    
    def check_dependencies(self) -> list[str]:
        """Check for missing dependencies."""
        missing = []
        
        try:
            import jsonschema
        except ImportError:
            missing.append("jsonschema")
        
        return missing
    
    @property
    def version(self) -> Optional[str]:
        """Get provider version."""
        try:
            import jsonschema
            return getattr(jsonschema, '__version__', 'unknown')
        except ImportError:
            return None
    
    async def check(self, input_text: str, output_text: Optional[str] = None, schema: Optional[Dict[str, Any]] = None, threshold: float = 1.0) -> SignalResult:
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
            # If expecting JSON (threshold = 1.0) but none found, this is a violation
            score = 1.0 if threshold >= 1.0 else 0.3
            label = SignalLabel.VIOLATION if threshold >= 1.0 else SignalLabel.HIT
            return SignalResult(
                id=self.provider_id,
                category=self.category,
                score=score,
                label=label,
                confidence=0.9,
                details={
                    "no_json_found": True, 
                    "output_length": len(output_text),
                    "threshold": threshold,
                    "expected_json": threshold >= 1.0
                }
            )
        
        # Perform schema validation if schema provided
        validation_results = {}
        score = 0.0
        
        if schema:
            validation_results = self._validate_against_schema(json_data, schema)
            # If schema validation fails and threshold is 1.0, it's a violation
            if not validation_results["valid"] and threshold >= 1.0:
                score = 1.0
            elif not validation_results["valid"]:
                score = 0.7  # Schema mismatch but not strict requirement
        else:
            # Basic structural validation
            validation_results = self._basic_json_validation(json_data)
            if not validation_results["valid_structure"]:
                score = 0.4 if threshold >= 1.0 else 0.2
        
        # Determine label based on score and threshold
        if score >= threshold:
            label = SignalLabel.VIOLATION
        elif score > 0.0:
            label = SignalLabel.HIT
        else:
            label = SignalLabel.CLEAN
        
        confidence = 0.9  # High confidence in JSON parsing and validation
        
        return SignalResult(
            id=self.provider_id,
            category=self.category,
            score=score,
            label=label,
            confidence=confidence,
            details={
                "json_found": True,
                "json_keys": list(json_data.keys()) if isinstance(json_data, dict) else [],
                "validation": validation_results,
                "threshold": threshold,
                "schema_provided": schema is not None
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
    
    def _validate_against_schema(self, json_data: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
        """Validate JSON data against provided schema."""
        try:
            import jsonschema
            
            # Validate against schema
            jsonschema.validate(json_data, schema)
            
            return {
                "valid": True,
                "errors": [],
                "schema_type": schema.get("type", "unknown")
            }
            
        except jsonschema.ValidationError as e:
            return {
                "valid": False,
                "errors": [str(e)],
                "schema_type": schema.get("type", "unknown"),
                "error_path": list(e.path) if hasattr(e, 'path') else []
            }
        except Exception as e:
            return {
                "valid": False,
                "errors": [f"Schema validation error: {str(e)}"],
                "schema_type": schema.get("type", "unknown")
            }
