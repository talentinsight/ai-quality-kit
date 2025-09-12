"""
Safety Suite Schemas and Data Models.

Defines Pydantic models for Safety test cases, moderation results,
and validation responses.
"""

from typing import Dict, List, Optional, Union, Any
from pydantic import BaseModel, Field, validator
from enum import Enum


class SafetyCategory(str, Enum):
    """Safety categories for test cases."""
    TOXICITY = "toxicity"
    HATE = "hate"
    VIOLENCE = "violence"
    ADULT = "adult"
    SELF_HARM = "self_harm"
    MISINFORMATION = "misinformation"


class SafetyInputs(BaseModel):
    """Input content for different moderation stages."""
    user: Optional[str] = None  # Content to moderate at INPUT stage
    retrieved: Optional[List[str]] = None  # Passages to moderate at RETRIEVED stage
    prompt: Optional[str] = None  # Prompt to send to LLM (then moderate OUTPUT)
    
    @validator('*', pre=True)
    def validate_at_least_one_input(cls, v, values):
        """Ensure at least one input is provided."""
        # This will be validated at the model level
        return v


class MisinformationCriteria(BaseModel):
    """Misinformation-specific success criteria."""
    claims: Optional[List[str]] = Field(default_factory=list)
    require_citation: Optional[bool] = False
    min_supported_claims: Optional[int] = 0
    allowed_citation_patterns: Optional[List[str]] = Field(default_factory=list)


class SafetySuccessCriteria(BaseModel):
    """Success criteria for safety test cases."""
    must_flag_any: Optional[List[str]] = Field(default_factory=list)
    must_not_flag_any: Optional[List[str]] = Field(default_factory=list)
    policy_labels: Optional[List[str]] = Field(default_factory=list)
    misinfo: Optional[MisinformationCriteria] = None


class SafetyCase(BaseModel):
    """A single safety test case."""
    id: str
    category: SafetyCategory
    subtype: str  # Used for subtests (e.g., "explicit", "implicit", "contextual")
    description: str
    required: bool
    inputs: SafetyInputs
    success: Optional[SafetySuccessCriteria] = Field(default_factory=SafetySuccessCriteria)
    
    @validator('inputs')
    def validate_inputs_not_empty(cls, v):
        """Ensure at least one input is provided."""
        if not any([v.user, v.retrieved, v.prompt]):
            raise ValueError("At least one of 'user', 'retrieved', or 'prompt' must be provided in inputs")
        return v
    
    @validator('subtype')
    def validate_subtype_not_empty(cls, v):
        """Ensure subtype is not empty."""
        if not v or not v.strip():
            raise ValueError("subtype must be a non-empty string")
        return v.strip()


class ModerationResult(BaseModel):
    """Result of content moderation."""
    blocked: bool
    redacted_text: Optional[str] = None
    labels: List[str] = Field(default_factory=list)
    score: Optional[float] = None
    reasons: Optional[List[str]] = Field(default_factory=list)


class SafetyStageFindings(BaseModel):
    """Findings from different moderation stages."""
    input: Optional[ModerationResult] = None
    retrieved: Optional[List[ModerationResult]] = Field(default_factory=list)
    output: Optional[ModerationResult] = None


class SafetyResult(BaseModel):
    """Result of a safety test case execution."""
    id: str
    category: str
    subtype: str
    required: bool
    passed: bool
    reason: str
    stage_findings: SafetyStageFindings = Field(default_factory=SafetyStageFindings)
    unsupported_claims_count: Optional[int] = None
    retrieved_dropped_count: Optional[int] = None  # Count of passages dropped during RETRIEVED stage
    evidence_snippet: Optional[str] = None
    # Timing information
    latency_input_ms: Optional[float] = None
    latency_retrieved_ms: Optional[float] = None
    latency_output_ms: Optional[float] = None


class SafetyFile(BaseModel):
    """Root model for safety dataset files."""
    cases: List[SafetyCase]
    
    @validator('cases')
    def validate_cases_not_empty(cls, v):
        """Ensure cases list is not empty."""
        if not v:
            raise ValueError("Safety file must contain at least one test case")
        return v
    
    @validator('cases')
    def validate_unique_ids(cls, v):
        """Ensure all case IDs are unique."""
        ids = [case.id for case in v]
        if len(ids) != len(set(ids)):
            raise ValueError("All safety case IDs must be unique")
        return v


class SafetyValidationResult(BaseModel):
    """Result of safety file validation."""
    valid: bool
    format: str  # "yaml", "json", or "jsonl"
    counts_by_category: Dict[str, int]
    required_count: int
    taxonomy: Dict[str, List[str]]  # category -> list of subtypes
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


class NormalizedSafety(BaseModel):
    """Normalized safety dataset after parsing."""
    cases: List[SafetyCase]
    taxonomy: Dict[str, List[str]]  # category -> list of subtypes


class SafetyConfig(BaseModel):
    """Configuration for safety suite execution."""
    enabled: bool = True
    subtests: Optional[Dict[str, List[str]]] = None  # category -> selected subtypes
