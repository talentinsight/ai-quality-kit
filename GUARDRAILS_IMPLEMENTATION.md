# Guardrails Preflight Implementation

## Overview

This implementation provides a minimal but complete Guardrails Preflight system that enables the new UI's "Run Preflight" functionality to return real PASS/FAIL results with detailed reasons.

## Architecture

### Core Components

1. **Interfaces** (`apps/server/guardrails/interfaces.py`)
   - Type definitions for requests, responses, and provider contracts
   - Pydantic models for validation and serialization

2. **Provider Registry** (`apps/server/guardrails/registry.py`)
   - Dynamic provider registration system
   - Category-based provider mapping

3. **Signal Providers**
   - **PII Provider** (`apps/server/guardrails/providers/pii_presidio.py`) - Microsoft Presidio integration
   - **Toxicity Provider** (`apps/server/guardrails/providers/toxicity_detoxify.py`) - Detoxify integration

4. **Aggregator** (`apps/server/guardrails/aggregator.py`)
   - Orchestrates provider execution
   - Applies thresholds and enforcement modes
   - Produces deterministic pass/fail decisions

5. **SUT Adapter** (`apps/server/sut.py`)
   - Factory for creating System Under Test adapters
   - Supports OpenAI, Anthropic, OpenAI-compatible, and Custom REST APIs

6. **API Route** (`apps/api/routes/guardrails.py`)
   - FastAPI endpoint: `POST /guardrails/preflight`
   - Integrated with existing authentication system

## API Contract

### Request Format

```json
{
  "llmType": "plain|rag|agent|tools",
  "target": {
    "mode": "api|mcp",
    "provider": "openai|anthropic|openai_compat|custom_rest|mcp",
    "endpoint": "https://api.openai.com/v1",
    "headers": {"Authorization": "Bearer your-key"},
    "model": "gpt-3.5-turbo",
    "timeoutMs": 30000
  },
  "guardrails": {
    "mode": "hard_gate|mixed|advisory",
    "thresholds": {"pii": 0.0, "toxicity": 0.3},
    "rules": [
      {
        "id": "pii-check",
        "category": "pii",
        "enabled": true,
        "threshold": 0.0,
        "mode": "hard_gate",
        "applicability": "agnostic"
      }
    ]
  }
}
```

### Response Format

```json
{
  "pass": true,
  "reasons": ["pii: 0.000 < 0.000 ✓", "toxicity: 0.120 < 0.300 ✓"],
  "signals": [
    {
      "id": "pii.presidio",
      "category": "pii",
      "score": 0.0,
      "label": "clean",
      "confidence": 1.0,
      "details": {"total_hits": 0, "entity_types": []}
    }
  ],
  "metrics": {
    "tests": 2,
    "duration_ms": 245.7,
    "providers_run": 2,
    "providers_unavailable": 0
  }
}
```

## Key Features

### Privacy & Security
- **No raw text persistence** - Only numeric metrics and flags are stored
- **No payload logging** - Input/output text never appears in logs
- **In-memory only** - No disk writes during execution
- **PII masking** - Sensitive data is redacted from all outputs

### Graceful Degradation
- **Missing dependencies** - Providers return "unavailable" status instead of crashing
- **Network failures** - SUT adapter failures are handled gracefully
- **Provider errors** - Individual provider failures don't crash the entire request

### Enforcement Modes
- **Hard Gate** - Any violation above threshold fails the preflight
- **Mixed** - Critical categories (PII, jailbreak) fail; others are advisory
- **Advisory** - Never fails, provides warnings only

### Deterministic Behavior
- **Idempotent** - Same inputs always produce same outputs
- **Threshold-based** - Clear, configurable decision boundaries
- **Consistent scoring** - Normalized 0-1 scores across all providers

## Provider Details

### PII Provider (Presidio)
- **Dependency**: `presidio-analyzer`
- **Scope**: Input and output text scanning
- **Metrics**: Hit count, entity types, confidence scores
- **Privacy**: Never returns actual PII matches, only counts and types

### Toxicity Provider (Detoxify)
- **Dependency**: `detoxify` (and `torch` or `onnxruntime`)
- **Scope**: Output text evaluation (what the model generates)
- **Metrics**: Toxicity score, per-category breakdowns
- **Thresholds**: 0.1+ = hit, 0.5+ = violation

## Integration Points

### Frontend Integration
- The existing Preflight UI's "Run Preflight" button calls `POST /guardrails/preflight`
- Response is rendered showing pass/fail status, reasons, and provider availability
- Unavailable providers show subtle "provider unavailable" indicators

### Backend Integration
- Route is automatically registered in `apps/rag_service/main.py`
- Uses existing authentication system (`require_user_or_admin`)
- Follows existing error handling patterns
- Compatible with all existing endpoints (no breaking changes)

## Testing

### Test Coverage
- **Unit tests** - Individual provider functionality
- **Integration tests** - End-to-end API flow
- **Smoke tests** - Basic import and structure validation
- **Privacy tests** - Verify no raw text in outputs
- **Idempotence tests** - Consistent results for same inputs

### Test Files
- `tests/test_guardrails_preflight.py` - Comprehensive unit tests
- `tests/test_guardrails_smoke.py` - Minimal dependency smoke tests
- `tests/integration/test_guardrails_e2e.py` - End-to-end integration tests

## Dependencies

### Required (Core)
- `fastapi` - API framework
- `pydantic` - Data validation
- `httpx` - HTTP client for SUT adapter

### Optional (Providers)
- `presidio-analyzer` - PII detection
- `detoxify` - Toxicity detection
- `torch` or `onnxruntime` - ML model runtime

### Graceful Handling
- Missing optional dependencies result in "unavailable" provider status
- Core functionality works even if all ML providers are unavailable
- No crashes or 500 errors due to missing dependencies

## Configuration

### Default Thresholds
```python
{
    "pii": 0.0,           # Any PII detection fails
    "toxicity": 0.3,      # Moderate toxicity threshold
    "jailbreak": 0.15,    # Low jailbreak tolerance
    "adult": 0.0,         # Any adult content fails
    "selfharm": 0.0,      # Any self-harm content fails
    "latency_p95_ms": 3000,
    "cost_per_test": 0.01
}
```

### Extensibility
- New providers can be added by implementing `GuardrailProvider` interface
- Automatic registration via `@register_provider` decorator
- Category-based provider mapping supports multiple providers per category

## Deployment Notes

### Environment Setup
1. Install core dependencies (already in requirements)
2. Optionally install ML dependencies: `pip install presidio-analyzer detoxify`
3. Start server normally - guardrails route is auto-registered

### Performance Considerations
- **Lightweight probe** - Single "Hello" test call to SUT
- **Local processing** - All ML inference runs locally
- **Concurrent providers** - Multiple providers can run in parallel
- **Timeout handling** - Configurable timeouts prevent hanging

### Monitoring
- **Metrics included** - Duration, provider counts, availability status
- **Structured logging** - Provider IDs and scores (no raw text)
- **Error tracking** - Graceful degradation with detailed error context

## Future Enhancements

### Additional Providers (Not in P0)
- **Jailbreak detection** - Pattern matching and ML-based detection
- **Schema validation** - JSON schema compliance checking
- **Rate/cost limits** - Request rate and token budget enforcement
- **Bias detection** - Demographic bias analysis

### Advanced Features (Not in P0)
- **Provider caching** - Cache ML model results for identical inputs
- **Batch processing** - Process multiple inputs in single provider call
- **Custom thresholds** - Per-rule threshold overrides
- **Webhook notifications** - Alert on policy violations

## Acceptance Criteria ✅

- [x] **Real PASS/FAIL results** - Clicking "Run Preflight" produces actual decisions
- [x] **Local signal providers** - PII (Presidio) and Toxicity (Detoxify) working
- [x] **Multi-provider support** - Works with OpenAI, Anthropic, OpenAI-compatible, Custom REST
- [x] **Privacy compliant** - No payload persistence, metrics-only logs
- [x] **Graceful degradation** - Missing providers don't crash requests
- [x] **Backward compatibility** - Classic Form and existing endpoints unchanged
- [x] **Comprehensive tests** - Unit, integration, and E2E test coverage
- [x] **Idempotent behavior** - Same inputs produce identical results
- [x] **Proper error handling** - 200 responses even with provider failures

The implementation is complete and ready for production use.
