"""Interfaces and types for guardrails system."""

from typing import Dict, List, Optional, Union, Literal, Any
from pydantic import BaseModel, Field
from enum import Enum


class GuardrailCategory(str, Enum):
    """Supported guardrail categories."""
    PII = "pii"
    JAILBREAK = "jailbreak"
    TOXICITY = "toxicity"
    RATE_COST = "rateCost"
    LATENCY = "latency"
    SCHEMA = "schema"
    RESILIENCE = "resilience"
    BIAS = "bias"
    TOPICS = "topics"
    ADULT = "adult"
    SELF_HARM = "self_harm"


class SignalLabel(str, Enum):
    """Signal result labels."""
    HIT = "hit"
    CLEAN = "clean"
    VIOLATION = "violation"
    UNAVAILABLE = "unavailable"


class GuardrailMode(str, Enum):
    """Guardrail enforcement modes."""
    HARD_GATE = "hard_gate"
    MIXED = "mixed"
    ADVISORY = "advisory"


class SignalResult(BaseModel):
    """Result from a single guardrail provider."""
    id: str  # provider id (e.g., "pii.presidio")
    category: GuardrailCategory
    score: float  # normalized 0..1 (higher = riskier)
    label: SignalLabel
    confidence: float  # 0..1
    details: Dict[str, Any]  # numbers/flags only, never raw text
    requires: Optional[Dict[str, bool]] = None  # hints like {"rag": True}


class GuardrailRule(BaseModel):
    """Individual guardrail rule configuration."""
    id: str
    category: GuardrailCategory
    enabled: bool
    threshold: Optional[float] = None
    mode: GuardrailMode
    applicability: Literal["agnostic", "requiresRag", "requiresTools"]
    source: Optional[str] = None
    provider_id: Optional[str] = None  # override default provider


class GuardrailsConfig(BaseModel):
    """Guardrails configuration."""
    mode: GuardrailMode
    thresholds: Dict[str, float]
    rules: List[GuardrailRule]
    rag_policy: Optional[Dict[str, Any]] = None


class TargetConfig(BaseModel):
    """Target system configuration."""
    mode: Literal["api", "mcp"]
    provider: Literal["openai", "anthropic", "openai_compat", "custom_rest", "mcp"]
    endpoint: str
    headers: Dict[str, str]
    model: Optional[str] = None
    timeoutMs: int = 30000


class PreflightRequest(BaseModel):
    """Request for guardrails preflight check."""
    llmType: Literal["rag", "agent", "plain", "tools"]
    target: TargetConfig
    guardrails: GuardrailsConfig


class PreflightResponse(BaseModel):
    """Response from guardrails preflight check."""
    pass_: bool = Field(alias="pass")  # "pass" is a Python keyword
    reasons: List[str]
    signals: List[SignalResult]
    metrics: Dict[str, Any]

    class Config:
        populate_by_name = True


class GuardrailProvider:
    """Base interface for guardrail providers."""
    
    def __init__(self, provider_id: str, category: GuardrailCategory):
        self.provider_id = provider_id
        self.category = category
        self.requires_llm = True
    
    async def check(self, input_text: str, output_text: Optional[str] = None) -> SignalResult:
        """Check input/output text and return signal result."""
        raise NotImplementedError
    
    def is_available(self) -> bool:
        """Check if provider dependencies are available."""
        raise NotImplementedError


# Field is now imported above
