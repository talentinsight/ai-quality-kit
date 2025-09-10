"""
Performance Testing Schemas.

Pydantic models for performance testing data structures.
"""

from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field, validator, model_validator
from enum import Enum


class PerfCategory(str, Enum):
    """Performance test categories."""
    COLD_START = "cold_start"
    WARM = "warm"
    THROUGHPUT = "throughput"
    STRESS = "stress"
    MEMORY = "memory"


class LoadMode(str, Enum):
    """Load generation modes."""
    CLOSED_LOOP = "closed_loop"
    OPEN_LOOP = "open_loop"


class RampType(str, Enum):
    """Ramp-up types."""
    NONE = "none"
    LINEAR = "linear"
    STEP = "step"
    SPIKE = "spike"


class RampConfig(BaseModel):
    """Ramp-up configuration."""
    type: RampType = Field(RampType.NONE, description="Ramp type")
    from_: Optional[float] = Field(None, alias="from", description="Starting value")
    to: Optional[float] = Field(None, description="Target value")
    duration_sec: Optional[int] = Field(None, description="Ramp duration in seconds")
    step_sec: Optional[int] = Field(None, description="Step duration for step ramp")
    
    @validator('duration_sec', 'step_sec')
    def validate_positive(cls, v):
        if v is not None and v <= 0:
            raise ValueError("Duration must be positive")
        return v


class RequestConfig(BaseModel):
    """Request configuration."""
    input_template: str = Field(..., description="User message/prompt template")
    headers: Optional[Dict[str, str]] = Field(None, description="Extra headers")
    repeats: Optional[int] = Field(5, description="Number of repeats for cold/warm scenarios")
    
    @validator('input_template')
    def validate_input_template_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("Input template must be non-empty")
        return v.strip()
    
    @validator('repeats')
    def validate_repeats_positive(cls, v):
        if v is not None and v <= 0:
            raise ValueError("Repeats must be positive")
        return v


class LoadConfig(BaseModel):
    """Load generation configuration."""
    mode: LoadMode = Field(..., description="Load generation mode")
    concurrency: Optional[int] = Field(None, description="Concurrency for closed-loop mode")
    rate_rps: Optional[float] = Field(None, description="Target RPS for open-loop mode")
    duration_sec: int = Field(..., description="Total wall time for the scenario")
    ramp: Optional[RampConfig] = Field(None, description="Ramp-up configuration")
    think_time_ms: Optional[int] = Field(0, description="Per-iteration client think time")
    
    @validator('duration_sec')
    def validate_duration_positive(cls, v):
        if v <= 0:
            raise ValueError("Duration must be positive")
        return v
    
    @validator('concurrency')
    def validate_concurrency_positive(cls, v):
        if v is not None and v <= 0:
            raise ValueError("Concurrency must be positive")
        return v
    
    @validator('rate_rps')
    def validate_rate_positive(cls, v):
        if v is not None and v <= 0:
            raise ValueError("Rate RPS must be positive")
        return v
    
    @validator('think_time_ms')
    def validate_think_time_non_negative(cls, v):
        if v is not None and v < 0:
            raise ValueError("Think time must be non-negative")
        return v
    
    @model_validator(mode='after')
    def validate_mode_requirements(cls, values):
        if values.mode == LoadMode.CLOSED_LOOP and values.concurrency is None:
            raise ValueError("Closed-loop mode requires concurrency")
        if values.mode == LoadMode.OPEN_LOOP and values.rate_rps is None:
            raise ValueError("Open-loop mode requires rate_rps")
        return values


class SegmentationConfig(BaseModel):
    """Cold/warm segmentation configuration."""
    cold_n: Optional[int] = Field(1, description="First N requests tagged as COLD")
    warmup_exclude_n: Optional[int] = Field(0, description="Ignore first N results in warm stats")
    phase_headers: Optional[bool] = Field(True, description="Send X-Perf-Phase headers")
    
    @validator('cold_n', 'warmup_exclude_n')
    def validate_non_negative(cls, v):
        if v is not None and v < 0:
            raise ValueError("Count must be non-negative")
        return v


class PerfThresholds(BaseModel):
    """Performance threshold overrides."""
    p95_ms_max: Optional[float] = Field(None, description="Max P95 latency in ms")
    error_rate_max: Optional[float] = Field(None, description="Max error rate (0-1)")
    timeout_rate_max: Optional[float] = Field(None, description="Max timeout rate (0-1)")
    throughput_min_rps: Optional[float] = Field(None, description="Min throughput RPS")
    tokens_per_sec_min: Optional[float] = Field(None, description="Min tokens per second")
    cost_per_request_max: Optional[float] = Field(None, description="Max cost per request")
    memory_peak_mb_max: Optional[float] = Field(None, description="Max memory peak MB")
    
    @validator('p95_ms_max', 'throughput_min_rps', 'tokens_per_sec_min', 'cost_per_request_max', 'memory_peak_mb_max')
    def validate_positive_thresholds(cls, v):
        if v is not None and v <= 0:
            raise ValueError("Threshold must be positive")
        return v
    
    @validator('error_rate_max', 'timeout_rate_max')
    def validate_rate_thresholds(cls, v):
        if v is not None and not (0 <= v <= 1):
            raise ValueError("Rate threshold must be between 0 and 1")
        return v


class PerfCase(BaseModel):
    """A single performance test case."""
    id: str = Field(..., description="Unique case identifier")
    category: PerfCategory = Field(..., description="Performance category")
    subtype: str = Field(..., description="Subtest key")
    description: str = Field(..., description="Human-readable description")
    required: bool = Field(..., description="Whether this case is required for gating")
    request: RequestConfig = Field(..., description="Request configuration")
    load: LoadConfig = Field(..., description="Load generation configuration")
    segmentation: Optional[SegmentationConfig] = Field(None, description="Cold/warm segmentation")
    thresholds: Optional[PerfThresholds] = Field(None, description="Threshold overrides")
    
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


class PerfFile(BaseModel):
    """Root structure for performance dataset files."""
    scenarios: List[PerfCase] = Field(..., min_items=1, description="List of performance scenarios")


class NormalizedPerf(BaseModel):
    """Normalized performance data with taxonomy."""
    scenarios: List[PerfCase]
    taxonomy: Dict[str, List[str]]  # category -> list of subtypes


class LatencyMetrics(BaseModel):
    """Latency statistics."""
    p50: float
    p90: float
    p95: float
    p99: float
    max: float
    mean: float
    std: float


class PerfMetrics(BaseModel):
    """Performance metrics for a scenario."""
    total: int
    completed: int
    errors: int
    timeouts: int
    error_rate: float
    timeout_rate: float
    latency_ms: LatencyMetrics
    throughput_rps: float
    tokens_out_total: Optional[int] = None
    tokens_out_rate: Optional[float] = None
    tokens_per_sec: Optional[float] = None
    cost_total: Optional[float] = None
    cost_per_request: Optional[float] = None
    memory_peak_mb: Optional[float] = None
    cpu_peak_pct: Optional[float] = None


class PerfResult(BaseModel):
    """Result of a single performance test case."""
    id: str
    category: str
    subtype: str
    required: bool
    passed: bool
    reason: str
    driver: str  # "closed_loop" or "open_loop"
    load: Dict[str, Any]  # Load configuration used
    metrics: Dict[str, PerfMetrics]  # "overall", "cold", "warm"
    latency_p95_ms: float
    throughput_rps: float
    error_rate: float
    timeout_rate: float
    tokens_per_sec: Optional[float] = None
    memory_peak_mb: Optional[float] = None
    cpu_peak_pct: Optional[float] = None
    headers_observed: Dict[str, bool] = Field(default_factory=dict)


class PerfValidationResult(BaseModel):
    """Result of performance dataset validation."""
    valid: bool
    format: str  # "yaml", "json", "jsonl"
    counts_by_category: Dict[str, int]
    taxonomy: Dict[str, List[str]]
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    required_count: int = 0


class PerfConfig(BaseModel):
    """Configuration for performance suite execution."""
    enabled: bool = True
    subtests: Optional[Dict[str, List[str]]] = None  # category -> selected subtypes
