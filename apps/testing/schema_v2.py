"""Test schema v2 for enhanced quality and evaluation."""

from typing import Dict, List, Optional, Any, Literal, Union
from pydantic import BaseModel, Field


# Type definitions for enhanced test cases
OracleType = Literal["exact", "contains", "regex", "semantic"]
SeverityLevel = Literal["critical", "major", "minor"]


class Acceptance(BaseModel):
    """Acceptance thresholds for test evaluation."""
    min_semantic: Optional[float] = Field(None, ge=0.0, le=1.0, description="Minimum semantic similarity score")
    max_false_positive_rate: Optional[float] = Field(None, ge=0.0, le=1.0, description="Maximum acceptable false positive rate")
    
    
class QualityGuardOptions(BaseModel):
    """Options for quality guard mechanisms."""
    enabled: bool = Field(True, description="Enable quality guard features")
    repeat_n: int = Field(2, ge=1, le=5, description="Number of repeats for anti-flake detection")
    sample_criticals: int = Field(5, ge=1, le=20, description="Max critical cases to sample for repeat testing")


class TestCaseV2(BaseModel):
    """Enhanced test case schema with v2 quality fields."""
    # Core fields (existing)
    test_id: str
    query: str
    expected_answer: Optional[str] = None
    context: Optional[List[str]] = None
    
    # V2 Quality fields (optional, additive)
    oracle_type: Optional[OracleType] = Field(None, description="Type of oracle for evaluation")
    acceptance: Optional[Acceptance] = Field(None, description="Acceptance thresholds")
    severity: Optional[SeverityLevel] = Field("major", description="Test case severity level")
    deterministic_seed: Optional[int] = Field(42, description="Seed for deterministic behavior")
    metamorphic_group: Optional[str] = Field(None, description="Group for metamorphic consistency checks")
    tags: Optional[List[str]] = Field(None, description="Categorization tags")
    
    # Runtime quality tracking (computed)
    unstable: Optional[bool] = Field(None, description="Whether case shows unstable behavior")
    metamorphic_break: Optional[bool] = Field(None, description="Whether case breaks metamorphic consistency")


class TestSuiteResults(BaseModel):
    """Enhanced test suite results with quality metrics."""
    # Existing fields remain unchanged
    suite_name: str
    total_cases: int
    passed_cases: int
    failed_cases: int
    
    # V2 Quality metrics (additive)
    unstable_cases: Optional[int] = Field(0, description="Number of unstable cases quarantined")
    quarantined_cases: Optional[int] = Field(0, description="Number of cases excluded from pass/fail")
    metamorphic_breaks: Optional[int] = Field(0, description="Number of metamorphic consistency violations")
    critical_failures: Optional[int] = Field(0, description="Number of critical severity failures")


class ComplianceMatch(BaseModel):
    """Enhanced compliance match with detailed metadata."""
    pattern_id: str = Field(..., description="Identifier of the matched pattern")
    match_span: tuple[int, int] = Field(..., description="Start and end positions of match")
    normalized_snippet: str = Field(..., description="Normalized text snippet that matched")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Confidence score for the match")


def parse_test_case_v2(data: Dict[str, Any]) -> TestCaseV2:
    """Parse a test case with v2 schema support, falling back gracefully."""
    try:
        return TestCaseV2(**data)
    except Exception:
        # Fallback: create minimal v2 case from legacy data
        return TestCaseV2(
            test_id=data.get("test_id", "unknown"),
            query=data.get("query", ""),
            expected_answer=data.get("expected_answer"),
            context=data.get("context", []),
            oracle_type=None,
            acceptance=None,
            severity="major",
            deterministic_seed=42,
            metamorphic_group=None,
            tags=None,
            unstable=None,
            metamorphic_break=None
        )


def get_effective_oracle_type(case: TestCaseV2) -> OracleType:
    """Get the effective oracle type for a test case."""
    if case.oracle_type:
        return case.oracle_type
    
    # Fallback logic based on existing patterns
    if case.expected_answer:
        return "contains"  # Default for most cases
    else:
        return "semantic"  # For cases without explicit expected answers


def is_critical_case(case: TestCaseV2) -> bool:
    """Check if a test case is critical severity."""
    return case.severity == "critical"


def should_repeat_for_stability(case: TestCaseV2, options: QualityGuardOptions) -> bool:
    """Determine if a case should be repeated for stability testing."""
    if not options.enabled:
        return False
    
    # Always repeat critical cases (up to sample limit)
    if is_critical_case(case):
        return True
    
    # Could add other heuristics here (random sampling, etc.)
    return False
