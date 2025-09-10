"""
Bias Detection Schemas.

Pydantic models for bias testing data structures.
"""

from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field, validator
from enum import Enum


class BiasCategory(str, Enum):
    """Bias test categories."""
    DEMOGRAPHIC_PARITY = "demographic_parity"
    REFUSAL_RATE = "refusal_rate"
    RESPONSE_LENGTH = "response_length"


class GroupSpec(BaseModel):
    """Specification for a demographic group."""
    id: str = Field(..., description="Unique group identifier")
    persona: str = Field(..., description="Persona text to insert into prompt template")
    
    @validator('id')
    def validate_id_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("Group id must be non-empty")
        return v.strip()
    
    @validator('persona')
    def validate_persona_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("Group persona must be non-empty")
        return v.strip()


class BiasDetectors(BaseModel):
    """Optional detection overrides for a bias case."""
    refusal_markers: Optional[List[str]] = Field(None, description="Custom refusal markers for this case")


class BiasThresholds(BaseModel):
    """Optional threshold overrides for a bias case."""
    max_refusal_gap_pp: Optional[float] = Field(None, description="Max refusal gap in percentage points")
    alpha: Optional[float] = Field(None, description="Significance level")
    max_length_rel_gap: Optional[float] = Field(None, description="Max relative length gap")
    
    @validator('alpha')
    def validate_alpha(cls, v):
        if v is not None and not (0 < v < 1):
            raise ValueError("Alpha must be between 0 and 1")
        return v
    
    @validator('max_refusal_gap_pp', 'max_length_rel_gap')
    def validate_non_negative(cls, v):
        if v is not None and v < 0:
            raise ValueError("Threshold must be non-negative")
        return v


class BiasCase(BaseModel):
    """A single bias test case."""
    id: str = Field(..., description="Unique case identifier")
    category: BiasCategory = Field(..., description="Bias category")
    subtype: str = Field(..., description="Subtest key (e.g., gender, age, accent)")
    description: str = Field(..., description="Human-readable description")
    required: bool = Field(..., description="Whether this case is required for gating")
    prompt_template: str = Field(..., description="Template with ${persona} placeholder")
    groups: List[GroupSpec] = Field(..., min_items=2, description="Demographic groups to test")
    repeats: int = Field(3, description="Number of calls per group")
    detectors: Optional[BiasDetectors] = Field(None, description="Optional detection overrides")
    thresholds: Optional[BiasThresholds] = Field(None, description="Optional threshold overrides")
    
    @validator('id')
    def validate_id_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("Case id must be non-empty")
        return v.strip()
    
    @validator('subtype')
    def validate_subtype_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("Subtype must be non-empty")
        return v.strip()
    
    @validator('prompt_template')
    def validate_prompt_template(cls, v):
        if not v or not v.strip():
            raise ValueError("Prompt template must be non-empty")
        if "${persona}" not in v:
            raise ValueError("Prompt template must contain ${persona} placeholder")
        return v.strip()
    
    @validator('repeats')
    def validate_repeats_positive(cls, v):
        if v < 1:
            raise ValueError("Repeats must be at least 1")
        return v
    
    @validator('groups')
    def validate_unique_group_ids(cls, v):
        group_ids = [group.id for group in v]
        if len(group_ids) != len(set(group_ids)):
            raise ValueError("Group ids must be unique")
        return v


class BiasFile(BaseModel):
    """Root structure for bias dataset files."""
    cases: List[BiasCase] = Field(..., min_items=1, description="List of bias test cases")


class NormalizedBias(BaseModel):
    """Normalized bias data with taxonomy."""
    cases: List[BiasCase]
    taxonomy: Dict[str, List[str]]  # category -> list of subtypes


class GroupStats(BaseModel):
    """Statistics for a single demographic group."""
    group_id: str
    n: int
    refusal_rate: float
    mean_length: float
    median_length: float
    stdev_length: float


class ComparisonStats(BaseModel):
    """Statistical comparison between two groups."""
    group_id: str
    baseline_id: str
    # Refusal rate comparison
    gap_pp: float  # percentage points
    z: float
    p: float
    cohens_h: float
    # Length comparison
    len_diff: float
    len_rel_gap: float
    ci_lo: float
    ci_hi: float


class BiasResult(BaseModel):
    """Result of a single bias test case."""
    id: str
    category: str
    subtype: str
    required: bool
    passed: bool
    reason: str
    group_stats: List[GroupStats]
    comparisons: List[ComparisonStats]
    latency_p95_ms: float


class BiasValidationResult(BaseModel):
    """Result of bias dataset validation."""
    valid: bool
    format: str  # "yaml", "json", "jsonl"
    counts_by_category: Dict[str, int]
    taxonomy: Dict[str, List[str]]
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    required_count: int = 0


class BiasConfig(BaseModel):
    """Configuration for bias suite execution."""
    enabled: bool = True
    subtests: Optional[Dict[str, List[str]]] = None  # category -> selected subtypes
