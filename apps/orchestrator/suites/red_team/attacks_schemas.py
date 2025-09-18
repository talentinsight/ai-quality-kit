"""
Simplified schemas for Red Team Attacks in YAML/JSON format.

This module defines the simplified schema where both YAML and JSON have identical fields.
Subtests are derived from the `subtype` field in each attack case.
"""

from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field, validator
from enum import Enum

from .schemas import Category, Channel


class AttackRole(str, Enum):
    """Valid roles for attack steps."""
    USER = "user"
    PASSAGE = "passage"
    METADATA = "metadata"
    SYSTEM = "system"


class LeakType(str, Enum):
    """Valid leak types for success criteria."""
    SYSTEM_PROMPT = "system_prompt"
    API_KEY = "api_key"
    PII = "pii"
    TOOL_SECRET = "tool_secret"


class AttackStep(BaseModel):
    """Single step in an attack sequence."""
    role: AttackRole = Field(..., description="Role for this step")
    content: str = Field(..., description="Content of the step")


class SuccessCriteria(BaseModel):
    """Success criteria for evaluating attack results."""
    must_contain_any: Optional[List[str]] = Field(default=None, description="Attack succeeds if response contains any of these")
    must_not_contain_any: Optional[List[str]] = Field(default=None, description="Attack fails if response contains any of these")
    leak_types: Optional[List[LeakType]] = Field(default=None, description="Types of information leaks to detect")


class AttackCase(BaseModel):
    """Single attack case definition."""
    id: str = Field(..., description="Unique identifier for the attack")
    category: Category = Field(..., description="Attack category")
    subtype: str = Field(..., description="Attack subtype (used for subtests)")
    description: str = Field(..., description="Human-readable description")
    required: bool = Field(..., description="Whether this attack is required for gating")
    steps: List[AttackStep] = Field(..., description="Attack execution steps")
    success: SuccessCriteria = Field(default_factory=SuccessCriteria, description="Success evaluation criteria")

    @validator('id')
    def validate_id(cls, v):
        """Validate attack ID format."""
        if not v or not v.strip():
            raise ValueError("Attack ID cannot be empty")
        return v.strip()

    @validator('steps')
    def validate_steps(cls, v):
        """Validate attack steps."""
        if not v:
            raise ValueError("Attack must have at least one step")
        return v

    @validator('subtype')
    def validate_subtype(cls, v):
        """Validate subtype format."""
        if not v or not v.strip():
            raise ValueError("Attack subtype cannot be empty")
        return v.strip()


class AttacksFile(BaseModel):
    """Container for attacks file - can be object with attacks key or direct list."""
    attacks: List[AttackCase] = Field(..., description="List of attack cases")

    @validator('attacks')
    def validate_attacks(cls, v):
        """Validate attack cases."""
        if not v:
            raise ValueError("Attacks file must contain at least one attack case")
        
        # Check for duplicate IDs
        ids = [attack.id for attack in v]
        if len(ids) != len(set(ids)):
            raise ValueError("Attack IDs must be unique")
        
        return v


class AttacksValidationResult(BaseModel):
    """Result of attacks file validation."""
    valid: bool
    counts_by_category: Dict[str, int]
    required_count: int
    taxonomy: Dict[str, List[str]]  # category -> list of subtypes
    format: str  # "yaml", "json", or "jsonl"
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


def detect_file_format(content: str) -> str:
    """
    Detect if content is YAML, JSON, or JSONL format.
    
    Args:
        content: File content as string
        
    Returns:
        "yaml", "json", or "jsonl"
    """
    content = content.strip()
    
    # Check for JSONL format (multiple lines, each starting with {)
    lines = content.split('\n')
    if len(lines) > 1 and all(line.strip().startswith('{') for line in lines if line.strip()):
        return "jsonl"
    
    # JSON typically starts with { or [
    if content.startswith('{') or content.startswith('['):
        return "json"
    
    # Default to YAML for everything else
    return "yaml"


def parse_attacks_content(content: str) -> AttacksFile:
    """
    Parse attacks content from YAML, JSON, or JSONL format.
    
    Args:
        content: File content as string
        
    Returns:
        AttacksFile object
        
    Raises:
        ValueError: If parsing fails or format is invalid
    """
    import yaml
    import json
    
    file_format = detect_file_format(content)
    
    try:
        if file_format == "jsonl":
            # Parse JSONL format (one JSON object per line)
            attacks_data = []
            for line_num, line in enumerate(content.strip().split('\n'), 1):
                line = line.strip()
                if line:  # Skip empty lines
                    try:
                        attack = json.loads(line)
                        attacks_data.append(attack)
                    except json.JSONDecodeError as e:
                        raise ValueError(f"Invalid JSON on line {line_num}: {e}")
        elif file_format == "json":
            data = json.loads(content)
            # Handle both object with "attacks" key and direct list
            if isinstance(data, dict) and "attacks" in data:
                attacks_data = data["attacks"]
            elif isinstance(data, list):
                attacks_data = data
            else:
                raise ValueError("JSON file must contain either an object with 'attacks' key or a direct list of attacks")
        else:
            data = yaml.safe_load(content)
            # Handle both object with "attacks" key and direct list
            if isinstance(data, dict) and "attacks" in data:
                attacks_data = data["attacks"]
            elif isinstance(data, list):
                attacks_data = data
            else:
                raise ValueError("YAML file must contain either an object with 'attacks' key or a direct list of attacks")
    except (json.JSONDecodeError, yaml.YAMLError) as e:
        raise ValueError(f"Invalid {file_format.upper()} format: {e}")
    
    # Create AttacksFile object
    return AttacksFile(attacks=attacks_data)


def discover_taxonomy(attacks: List[AttackCase]) -> Dict[str, List[str]]:
    """
    Discover taxonomy by grouping subtypes by category.
    
    Args:
        attacks: List of attack cases
        
    Returns:
        Dictionary mapping categories to lists of subtypes
    """
    taxonomy = {}
    
    for attack in attacks:
        category = attack.category.value
        subtype = attack.subtype
        
        if category not in taxonomy:
            taxonomy[category] = []
        
        if subtype and subtype not in taxonomy[category]:
            taxonomy[category].append(subtype)
    
    # Sort subtypes for consistency
    for category in taxonomy:
        taxonomy[category].sort()
    
    return taxonomy


def validate_attacks_content(content: str) -> AttacksValidationResult:
    """
    Validate attacks content and return validation results.
    
    Args:
        content: File content as string
        
    Returns:
        AttacksValidationResult with validation status and metadata
    """
    try:
        file_format = detect_file_format(content)
        attacks_file = parse_attacks_content(content)
        
        # Count attacks by category
        counts_by_category = {}
        required_count = 0
        
        for attack in attacks_file.attacks:
            category = attack.category.value
            counts_by_category[category] = counts_by_category.get(category, 0) + 1
            if attack.required:
                required_count += 1
        
        # Discover taxonomy
        taxonomy = discover_taxonomy(attacks_file.attacks)
        
        return AttacksValidationResult(
            valid=True,
            counts_by_category=counts_by_category,
            required_count=required_count,
            taxonomy=taxonomy,
            format=file_format,
            warnings=[],
            errors=[]
        )
        
    except ValueError as e:
        return AttacksValidationResult(
            valid=False,
            counts_by_category={},
            required_count=0,
            taxonomy={},
            format=detect_file_format(content),
            warnings=[],
            errors=[str(e)]
        )
    except Exception as e:
        return AttacksValidationResult(
            valid=False,
            counts_by_category={},
            required_count=0,
            taxonomy={},
            format="unknown",
            warnings=[],
            errors=[f"Unexpected error: {str(e)}"]
        )


def convert_to_legacy_format(attacks_file: AttacksFile) -> List[Dict[str, Any]]:
    """
    Convert AttacksFile to legacy format for backward compatibility.
    
    Args:
        attacks_file: AttacksFile object
        
    Returns:
        List of attack dictionaries in legacy format
    """
    legacy_attacks = []
    
    for attack in attacks_file.attacks:
        # Convert steps
        legacy_steps = []
        for step in attack.steps:
            legacy_steps.append({
                "role": step.role.value,
                "content": step.content
            })
        
        # Convert success criteria
        legacy_success = {}
        if attack.success.must_contain_any:
            legacy_success["must_contain_any"] = attack.success.must_contain_any
        if attack.success.must_not_contain_any:
            legacy_success["must_not_contain_any"] = attack.success.must_not_contain_any
        if attack.success.leak_types:
            legacy_success["leak_types"] = [leak.value for leak in attack.success.leak_types]
        
        # Create legacy attack
        legacy_attack = {
            "id": attack.id,
            "category": attack.category.value,
            "subtype": attack.subtype,
            "description": attack.description,
            "required": attack.required,
            "steps": legacy_steps,
            "success": legacy_success
        }
        
        legacy_attacks.append(legacy_attack)
    
    return legacy_attacks
