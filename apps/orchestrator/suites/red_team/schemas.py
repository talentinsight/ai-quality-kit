"""Pydantic schemas for Red Team adversarial testing."""

from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class Channel(str, Enum):
    """Attack injection channels."""
    USER = "user"
    PASSAGE = "passage"
    METADATA = "metadata"
    SYSTEM = "system"


class Category(str, Enum):
    """Attack categories for classification."""
    PROMPT_INJECTION = "prompt_injection"
    JAILBREAK = "jailbreak"
    DATA_EXTRACTION = "data_extraction"
    CONTEXT_POISONING = "context_poisoning"
    SOCIAL_ENGINEERING = "social_engineering"


class LeakType(str, Enum):
    """Types of information leaks to detect."""
    SYSTEM_PROMPT = "system_prompt"
    API_KEY = "api_key"
    PII = "pii"
    TOOL_SECRET = "tool_secret"


class AttackStep(BaseModel):
    """Single step in a multi-turn attack sequence."""
    role: Channel = Field(..., description="Channel for this attack step")
    content: str = Field(..., description="Attack payload content")


class SuccessCriteria(BaseModel):
    """Criteria for determining attack success."""
    must_contain_any: List[str] = Field(default_factory=list, description="Response must contain at least one of these")
    must_not_contain_any: List[str] = Field(default_factory=list, description="Response must not contain any of these")
    leak_types: List[LeakType] = Field(default_factory=list, description="Types of leaks to detect")


class AttackCase(BaseModel):
    """Complete attack case definition."""
    id: str = Field(..., description="Unique attack identifier")
    category: Category = Field(..., description="Attack category")
    subtype: Optional[str] = Field(None, description="Attack subtype for granular classification")
    description: str = Field(..., description="Human-readable attack description")
    required: bool = Field(False, description="Whether this attack is required for gating")
    steps: List[AttackStep] = Field(..., description="Multi-turn attack sequence")
    success: SuccessCriteria = Field(..., description="Success detection criteria")


class AttackResult(BaseModel):
    """Result of executing an attack case."""
    id: str = Field(..., description="Attack case identifier")
    category: Category = Field(..., description="Attack category")
    passed: bool = Field(..., description="Whether the attack was successfully defended against")
    reason: str = Field(..., description="Explanation of pass/fail determination")
    evidence: Dict[str, str] = Field(default_factory=dict, description="Masked evidence of attack execution")
    latency_ms: Optional[float] = Field(None, description="Total attack execution latency")
    turn_count: int = Field(1, description="Number of turns in the attack sequence")


class RedTeamConfig(BaseModel):
    """Configuration for Red Team testing."""
    enabled: bool = Field(True, description="Whether Red Team testing is enabled")
    fail_fast: bool = Field(True, description="Stop pipeline when required attack fails")
    max_steps: int = Field(6, description="Safety cap for multi-turn attacks")
    seed: int = Field(0, description="Random seed for reproducible testing")
    mask_secrets: bool = Field(True, description="Mask secrets in evidence and logs")
    required_metrics: List[str] = Field(
        default_factory=lambda: ["prompt_injection", "data_extraction"],
        description="Required attack categories for gating"
    )
