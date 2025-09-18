"""
Pydantic schemas for Red Team Single-File Dataset format.

This module defines the schema for the new single-file YAML format that can
drive the entire Red Team suite including categories, subtests, config overrides,
and detector patterns.
"""

from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field, validator
from enum import Enum

from .schemas import Category, Channel, AttackStep, SuccessCriteria


class RedTeamVersion(str, Enum):
    """Supported Red Team dataset versions."""
    V1 = "redteam.v1"


class RedTeamSuite(str, Enum):
    """Supported Red Team suite names."""
    RED_TEAM = "red_team"


class SingleFileConfig(BaseModel):
    """Optional configuration overrides for Red Team execution."""
    fail_fast: Optional[bool] = None
    required_metrics: Optional[List[str]] = None
    max_steps: Optional[int] = None
    mask_secrets: Optional[bool] = None


class DetectorPatterns(BaseModel):
    """Optional detector pattern overrides for Red Team execution."""
    system_prompt_indicators: Optional[List[str]] = None
    api_key_patterns: Optional[List[str]] = None
    base64_min_len: Optional[int] = None
    refusal_markers: Optional[List[str]] = None
    pii_patterns: Optional[Dict[str, str]] = None


class SingleFileAttackStep(BaseModel):
    """Attack step with variable substitution support."""
    role: Channel
    content: str = Field(..., description="Step content with optional ${var} substitutions")


class SingleFileSuccessCriteria(BaseModel):
    """Success criteria for attack evaluation."""
    must_contain_any: Optional[List[str]] = Field(default_factory=list)
    must_not_contain_any: Optional[List[str]] = Field(default_factory=list)
    leak_types: Optional[List[str]] = Field(default_factory=list)


class SingleFileAttackCase(BaseModel):
    """Single attack case in the dataset."""
    id: str = Field(..., description="Unique identifier for the attack")
    category: Category = Field(..., description="Attack category")
    subtype: str = Field(..., description="Attack subtype (free-form)")
    description: str = Field(..., description="Human-readable description")
    required: bool = Field(False, description="Whether this attack is required for gating")
    steps: List[SingleFileAttackStep] = Field(..., description="Attack execution steps")
    success: SingleFileSuccessCriteria = Field(default_factory=SingleFileSuccessCriteria)

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


class RedTeamSingleFileDataset(BaseModel):
    """Complete Red Team dataset in single-file format."""
    version: RedTeamVersion = Field(..., description="Dataset format version")
    suite: RedTeamSuite = Field(..., description="Suite identifier")
    config: Optional[SingleFileConfig] = Field(None, description="Optional config overrides")
    taxonomy: Optional[Dict[str, List[str]]] = Field(None, description="Static taxonomy definition")
    detectors: Optional[DetectorPatterns] = Field(None, description="Detector pattern overrides")
    variables: Optional[Dict[str, str]] = Field(default_factory=dict, description="Variables for ${var} substitution")
    attacks: List[SingleFileAttackCase] = Field(..., description="List of attack cases")

    @validator('attacks')
    def validate_attacks(cls, v):
        """Validate attack cases."""
        if not v:
            raise ValueError("Dataset must contain at least one attack case")
        
        # Check for duplicate IDs
        ids = [attack.id for attack in v]
        if len(ids) != len(set(ids)):
            raise ValueError("Attack IDs must be unique")
        
        return v

    @validator('taxonomy')
    def validate_taxonomy(cls, v):
        """Validate taxonomy format."""
        if v is not None:
            valid_categories = {cat.value for cat in Category}
            for category in v.keys():
                if category not in valid_categories:
                    raise ValueError(f"Invalid category in taxonomy: {category}")
        return v


class DatasetValidationResult(BaseModel):
    """Result of dataset validation."""
    valid: bool
    taxonomy: Dict[str, List[str]]
    counts_by_category: Dict[str, int]
    required_count: int
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    dataset_metadata: Optional[Dict[str, Any]] = None


class DatasetCounts(BaseModel):
    """Attack counts by category."""
    total: int
    required: int
    by_category: Dict[str, int]
    by_subtype: Dict[str, int]


def is_single_file_format(data: Any) -> bool:
    """
    Check if the provided data is in single-file format.
    
    Args:
        data: Parsed YAML data
        
    Returns:
        True if data appears to be single-file format
    """
    if not isinstance(data, dict):
        return False
    
    # Check for required single-file keys
    has_version = 'version' in data
    has_suite = 'suite' in data
    has_attacks = 'attacks' in data and isinstance(data['attacks'], list)
    
    return has_version and has_suite and has_attacks


def is_legacy_format(data: Any) -> bool:
    """
    Check if the provided data is in legacy format (simple list).
    
    Args:
        data: Parsed YAML data
        
    Returns:
        True if data appears to be legacy format
    """
    return isinstance(data, list) and len(data) > 0


def discover_taxonomy_from_attacks(attacks: List[SingleFileAttackCase]) -> Dict[str, List[str]]:
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


def apply_variable_substitution(content: str, variables: Dict[str, str]) -> str:
    """
    Apply simple ${var} variable substitution to content.
    
    Args:
        content: Content string with potential ${var} placeholders
        variables: Dictionary of variable name -> value mappings
        
    Returns:
        Content with variables substituted
    """
    if not variables:
        return content
    
    result = content
    for var_name, var_value in variables.items():
        placeholder = f"${{{var_name}}}"
        result = result.replace(placeholder, var_value)
    
    return result


def convert_single_file_to_legacy_format(dataset: RedTeamSingleFileDataset) -> List[Dict[str, Any]]:
    """
    Convert single-file dataset to legacy format for backward compatibility.
    
    Args:
        dataset: Single-file dataset
        
    Returns:
        List of attack dictionaries in legacy format
    """
    legacy_attacks = []
    
    for attack in dataset.attacks:
        # Apply variable substitution to steps
        processed_steps = []
        for step in attack.steps:
            processed_content = apply_variable_substitution(step.content, dataset.variables or {})
            processed_steps.append({
                "role": step.role.value,
                "content": processed_content
            })
        
        # Convert to legacy format
        legacy_attack = {
            "id": attack.id,
            "category": attack.category.value,
            "subtype": attack.subtype,
            "description": attack.description,
            "required": attack.required,
            "steps": processed_steps,
            "success": {
                "must_contain_any": attack.success.must_contain_any or [],
                "must_not_contain_any": attack.success.must_not_contain_any or [],
                "leak_types": attack.success.leak_types or []
            }
        }
        
        legacy_attacks.append(legacy_attack)
    
    return legacy_attacks
