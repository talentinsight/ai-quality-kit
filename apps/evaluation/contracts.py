"""Contract validation and PII masking utilities."""

import json
import re
from typing import Optional, Dict, Any


def validate_contract(contract_cfg: Dict[str, Any], text_or_json: str) -> Optional[bool]:
    """
    Validate text or JSON against a contract configuration.
    
    Args:
        contract_cfg: Contract configuration with type and schema
        text_or_json: Raw text or JSON string to validate
        
    Returns:
        True if valid, False if invalid, None if validation not supported
    """
    contract_type = contract_cfg.get("type")
    
    if contract_type == "jsonschema":
        return _validate_jsonschema(contract_cfg.get("schema", {}), text_or_json)
    elif contract_type == "ebnf":
        # Stub for future EBNF validation
        return None
    else:
        return None


def mask_pii(s: str) -> str:
    """
    Mask personally identifiable information in text.
    
    Args:
        s: Input string that may contain PII
        
    Returns:
        String with PII patterns masked
    """
    if not isinstance(s, str):
        s = str(s)
    
    # Email addresses
    s = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]', s)
    
    # Phone numbers (various formats)
    s = re.sub(r'\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b', '[PHONE]', s)
    
    # Credit card numbers (basic pattern)
    s = re.sub(r'\b(?:\d{4}[-\s]?){3}\d{4}\b', '[CREDIT_CARD]', s)
    
    # IBAN (basic pattern)
    s = re.sub(r'\b[A-Z]{2}\d{2}[A-Z0-9]{4}\d{7}[A-Z0-9]{0,16}\b', '[IBAN]', s)
    
    # US addresses (basic pattern - street number + street name)
    s = re.sub(r'\b\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Boulevard|Blvd)\b', '[ADDRESS]', s, flags=re.IGNORECASE)
    
    # Social Security Numbers
    s = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', '[SSN]', s)
    
    return s


def _validate_jsonschema(schema: Dict[str, Any], text: str) -> Optional[bool]:
    """
    Validate text against a JSON schema.
    
    Args:
        schema: JSON schema dictionary
        text: Text to validate (will be parsed as JSON)
        
    Returns:
        True if valid, False if invalid
    """
    try:
        import jsonschema
    except ImportError:
        # If jsonschema library not available, return None
        return None
    
    try:
        # Try to parse as JSON
        try:
            data = json.loads(text.strip())
        except json.JSONDecodeError:
            # Fallback: try to extract result for numeric tasks
            if "result" in schema.get("properties", {}):
                # Look for last number in text
                numbers = re.findall(r'-?\d+', text)
                if numbers:
                    data = {"result": int(numbers[-1])}
                else:
                    return False
            else:
                return False
        
        # Validate against schema
        jsonschema.validate(data, schema)
        return True
        
    except jsonschema.ValidationError:
        return False
    except Exception:
        return False
