"""Pydantic models for test data intake."""

import os
from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, field_validator, model_validator
import json
import yaml

# Configuration
INTAKE_MAX_MB = int(os.getenv("INTAKE_MAX_MB", "10"))
MAX_FILE_SIZE = INTAKE_MAX_MB * 1024 * 1024  # Convert to bytes


class PassageRecord(BaseModel):
    """Individual passage record validation."""
    id: str = Field(..., description="Unique passage identifier")
    text: str = Field(..., min_length=1, description="Passage content")
    meta: Optional[Dict[str, Any]] = Field(None, description="Optional metadata")


class RobustnessConfig(BaseModel):
    """Optional robustness configuration for embedding robustness subtest."""
    paraphrases: Optional[List[str]] = Field(None, description="Human-written or system-generated paraphrases")
    synonyms: Optional[List[str]] = Field(None, description="Domain synonyms for lexical expansion (BM25 branch)")
    require_hybrid: Optional[bool] = Field(None, description="Force dense+BM25 for this QID")
    mmr_lambda: Optional[float] = Field(None, ge=0.0, le=1.0, description="MMR lambda parameter (0..1, default 0.4)")


class QARecord(BaseModel):
    """Individual QA record validation."""
    qid: str = Field(..., description="Unique question identifier")
    question: str = Field(..., min_length=1, description="Question text")
    expected_answer: str = Field(..., min_length=1, description="Expected answer")
    contexts: Optional[List[str]] = Field(None, description="Optional context passages")
    meta: Optional[Dict[str, Any]] = Field(None, description="Optional metadata")
    # Additive fields for embedding robustness subtest
    required: Optional[bool] = Field(None, description="Gates only if true and subtest selected")
    robustness: Optional[RobustnessConfig] = Field(None, description="Optional robustness configuration")


class ValidationError(BaseModel):
    """Validation error details."""
    field: str = Field(..., description="Field name that failed validation")
    message: str = Field(..., description="Error message")
    line_number: Optional[int] = Field(None, description="Line number for JSONL files")


class ArtifactInfo(BaseModel):
    """Information about a single artifact."""
    present: bool = Field(..., description="Whether artifact is present")
    count: Optional[int] = Field(None, description="Number of records/lines")
    sha256: Optional[str] = Field(None, description="SHA256 digest of raw content")
    validation_errors: List[ValidationError] = Field(default_factory=list, description="Validation errors")


class TestDataBundle(BaseModel):
    """Complete test data bundle."""
    testdata_id: str = Field(..., description="Unique bundle identifier")
    created_at: datetime = Field(..., description="Creation timestamp")
    expires_at: datetime = Field(..., description="Expiration timestamp")
    passages: Optional[List[PassageRecord]] = Field(None, description="Passage records")
    qaset: Optional[List[QARecord]] = Field(None, description="QA records")
    attacks: Optional[List[str]] = Field(None, description="Attack patterns")
    safety: Optional[List[str]] = Field(None, description="Safety test cases")
    bias: Optional[Any] = Field(None, description="Bias test cases (can be dict or list)")
    performance: Optional[List[str]] = Field(None, description="Performance scenarios")
    json_schema: Optional[Dict[str, Any]] = Field(None, description="JSON Schema")
    raw_payloads: Dict[str, str] = Field(default_factory=dict, description="Raw content for SHA256")


class TestDataMeta(BaseModel):
    """Metadata about test data bundle."""
    testdata_id: str = Field(..., description="Bundle identifier")
    created_at: datetime = Field(..., description="Creation timestamp")
    expires_at: datetime = Field(..., description="Expiration timestamp")
    artifacts: Dict[str, ArtifactInfo] = Field(..., description="Artifact information")


class UploadResponse(BaseModel):
    """Response from upload endpoint."""
    testdata_id: str = Field(..., description="Generated bundle identifier")
    artifacts: List[str] = Field(..., description="Successfully processed artifacts")
    counts: Dict[str, int] = Field(..., description="Record counts per artifact")
    # Enhanced response fields for RAG integration
    manifest: Optional[Dict[str, Any]] = Field(None, description="File manifest with paths")
    stats: Optional[Dict[str, Any]] = Field(None, description="Validation statistics")
    warnings: Optional[List[str]] = Field(None, description="Validation warnings")


class URLRequest(BaseModel):
    """Request for URL-based ingestion."""
    urls: Dict[str, str] = Field(..., description="URLs for each artifact type")
    
    @field_validator('urls')
    @classmethod
    def validate_urls(cls, v):
        """Validate that at least one URL is provided."""
        if not v:
            raise ValueError("At least one URL must be provided")
        allowed_keys = {"passages", "qaset", "attacks", "schema"}
        invalid_keys = set(v.keys()) - allowed_keys
        if invalid_keys:
            raise ValueError(f"Invalid artifact types: {invalid_keys}")
        return v


class PasteRequest(BaseModel):
    """Request for paste-based ingestion."""
    passages: Optional[str] = Field(None, description="Passages JSONL content")
    qaset: Optional[str] = Field(None, description="QA JSONL content")
    attacks: Optional[str] = Field(None, description="Attack patterns (text or YAML)")
    json_schema: Optional[str] = Field(None, description="JSON Schema content")
    
    @model_validator(mode='after')
    def validate_at_least_one_field(self):
        """Ensure at least one content field is provided."""
        provided_fields = sum(1 for v in [self.passages, self.qaset, self.attacks, self.json_schema] if v is not None)
        if provided_fields == 0:
            raise ValueError("At least one content field must be provided")
        return self


def validate_jsonl_content(content: str, record_class: type) -> tuple[List[Any], List[ValidationError]]:
    """Validate JSONL content against a record class."""
    records = []
    errors = []
    
    if not content.strip():
        return records, [ValidationError(field="content", message="Empty content provided", line_number=None)]
    
    lines = content.strip().split('\n')
    for line_num, line in enumerate(lines, 1):
        line = line.strip()
        if not line:
            continue
            
        try:
            data = json.loads(line)
            record = record_class(**data)
            records.append(record)
        except json.JSONDecodeError as e:
            errors.append(ValidationError(
                field="json",
                message=f"Invalid JSON: {str(e)}",
                line_number=line_num
            ))
        except Exception as e:
            errors.append(ValidationError(
                field="validation",
                message=str(e),
                line_number=line_num
            ))
    
    return records, errors


def validate_bias_content(content: str) -> tuple[Any, List[ValidationError]]:
    """Validate bias content (YAML, JSON, or JSONL format)."""
    errors = []
    
    if not content.strip():
        return None, [ValidationError(field="content", message="Empty content provided", line_number=None)]
    
    try:
        # Parse the content as JSON/YAML to preserve original structure
        import json
        import yaml
        
        # Try JSON first
        try:
            parsed_data = json.loads(content)
        except json.JSONDecodeError:
            # Try YAML
            try:
                parsed_data = yaml.safe_load(content)
            except yaml.YAMLError as e:
                return None, [ValidationError(field="bias", message=f"Invalid JSON/YAML format: {str(e)}", line_number=None)]
        
        # Validate using bias loader
        from apps.orchestrator.suites.bias.loader import validate_bias_content as validate_bias_dataset
        
        validation_result = validate_bias_dataset(content)
        
        if not validation_result.valid:
            for error in validation_result.errors:
                errors.append(ValidationError(field="bias", message=error, line_number=None))
            return None, errors
        
        # Return the parsed data (preserving original structure)
        return parsed_data, errors
        
    except Exception as e:
        errors.append(ValidationError(field="bias", message=f"Bias validation failed: {str(e)}", line_number=None))
        return None, errors


def validate_perf_content(content: str) -> tuple[List[str], List[ValidationError]]:
    """Validate performance content (YAML, JSON, or JSONL format)."""
    errors = []
    
    if not content.strip():
        return [], [ValidationError(field="content", message="Empty content provided", line_number=None)]
    
    try:
        # Use the performance loader for validation
        from apps.orchestrator.suites.performance.loader import validate_perf_content as validate_perf_dataset
        
        validation_result = validate_perf_dataset(content)
        
        if not validation_result.valid:
            for error in validation_result.errors:
                errors.append(ValidationError(field="performance", message=error, line_number=None))
            return [], errors
        
        # Return scenario IDs as records for consistency
        scenario_ids = []
        try:
            from apps.orchestrator.suites.performance.loader import parse_perf_content
            normalized_perf = parse_perf_content(content)
            scenario_ids = [scenario.id for scenario in normalized_perf.scenarios]
        except Exception as e:
            errors.append(ValidationError(field="performance", message=f"Failed to extract scenario IDs: {str(e)}", line_number=None))
        
        return scenario_ids, errors
        
    except Exception as e:
        errors.append(ValidationError(field="performance", message=f"Performance validation failed: {str(e)}", line_number=None))
        return [], errors


def validate_attacks_content(content: str) -> tuple[List[str], List[ValidationError]]:
    """Validate attacks content (text or YAML format)."""
    errors = []
    
    if not content.strip():
        return [], [ValidationError(field="content", message="Empty content provided", line_number=None)]
    
    # Try YAML first
    try:
        data = yaml.safe_load(content)
        if isinstance(data, dict) and "attacks" in data:
            attacks = data["attacks"]
            if isinstance(attacks, list) and all(isinstance(a, str) for a in attacks):
                return attacks, errors
            else:
                errors.append(ValidationError(
                    field="attacks",
                    message="YAML attacks field must be a list of strings",
                    line_number=None
                ))
                # Fall back to text format
                attacks = [line.strip() for line in content.strip().split('\n') 
                          if line.strip() and not line.strip().startswith('#')]
                return attacks, errors
        else:
            # Fall back to text format (one line per attack)
            attacks = [line.strip() for line in content.strip().split('\n') 
                      if line.strip() and not line.strip().startswith('#')]
            return attacks, errors
    except yaml.YAMLError:
        # Fall back to text format
        attacks = [line.strip() for line in content.strip().split('\n') 
                  if line.strip() and not line.strip().startswith('#')]
        return attacks, errors
    
    return [], errors


def validate_schema_content(content: str) -> tuple[Optional[Dict[str, Any]], List[ValidationError]]:
    """Validate JSON Schema content."""
    errors = []
    
    if not content.strip():
        return None, [ValidationError(field="content", message="Empty content provided", line_number=None)]
    
    try:
        schema = json.loads(content)
        if not isinstance(schema, dict):
            errors.append(ValidationError(
                field="schema",
                message="Schema must be a JSON object",
                line_number=None
            ))
            return None, errors
        
        # Basic JSON Schema validation (check for required fields)
        if "$schema" not in schema and "type" not in schema and "properties" not in schema:
            errors.append(ValidationError(
                field="schema",
                message="Does not appear to be a valid JSON Schema (missing $schema, type, or properties)",
                line_number=None
            ))
        
        return schema, errors
    except json.JSONDecodeError as e:
        errors.append(ValidationError(
            field="json",
            message=f"Invalid JSON: {str(e)}",
            line_number=None
        ))
        return None, errors
