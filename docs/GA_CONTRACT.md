# AI Quality Kit - General Availability Contract (v1.0)

This document defines the public API surface, operating policies, and quality gates for the AI Quality Kit GA release. These specifications constitute the contractual interface and must remain stable within major versions.

## 1. API Surface (v1.0)

### Core Endpoints

| **Method** | **Path** | **Purpose** | **Auth Required** |
|------------|----------|-------------|-------------------|
| POST | `/ask` | RAG query with provider selection | Yes |
| POST | `/orchestrator/run_tests` | Execute test suites with optional custom data | Yes |
| POST | `/testdata/upload` | Upload test data files (multipart) | Yes |
| POST | `/testdata/by_url` | Ingest test data from URLs | Yes |
| POST | `/testdata/paste` | Submit test data via direct content | Yes |
| GET | `/testdata/{testdata_id}/meta` | Retrieve test data metadata | Yes |
| GET | `/healthz` | Health check endpoint | No |
| GET | `/readyz` | Readiness check endpoint | No |

### Response Codes

| **Code** | **Meaning** | **When** |
|----------|-------------|----------|
| 200 | Success | Request completed successfully |
| 400 | Bad Request | Invalid payload, missing required fields |
| 401 | Unauthorized | Missing or invalid authentication |
| 403 | Forbidden | Valid auth but insufficient permissions |
| 404 | Not Found | Resource does not exist |
| 413 | Payload Too Large | Exceeds INTAKE_MAX_MB or INTAKE_MAX_RECORDS |
| 422 | Unprocessable Entity | Valid format but semantic validation failed |
| 429 | Too Many Requests | Rate limit exceeded (includes Retry-After header) |
| 500 | Internal Server Error | Unexpected server failure |
| 502 | Bad Gateway | External provider failure |
| 503 | Service Unavailable | Temporary overload or maintenance |
| 504 | Gateway Timeout | External provider timeout |

### Breaking Change Policy

- **v1.x**: No breaking changes to request/response schemas, endpoint paths, or authentication mechanisms
- **Major version bump required for**: removing endpoints, changing required fields, modifying authentication requirements
- **Minor version allowed for**: adding optional fields, new endpoints, backward-compatible enhancements

## 2. Report Schema (v1.0)

### JSON Report Structure

```json
{
  "summary": {
    "run_id": "string",
    "timestamp": "ISO8601",
    "total_tests": "integer",
    "passed": "integer",
    "failed": "integer",
    "success_rate": "float"
  },
  "detailed": [
    {
      "test_id": "string",
      "suite": "string",
      "status": "passed|failed|error",
      "score": "float|null",
      "execution_time_ms": "integer"
    }
  ],
  "api_details": [
    {
      "request_id": "string",
      "provider": "string",
      "model": "string", 
      "latency_ms": "integer",
      "tokens_used": "integer|null",
      "cost_estimate": "float|null"
    }
  ],
  "inputs_and_expected": [
    {
      "test_id": "string",
      "input_query": "string",
      "expected_answer": "string|null",
      "actual_answer": "string",
      "context_used": "array[string]"
    }
  ],
  "adversarial_details": [
    {
      "run_id": "string",
      "request_id": "string", 
      "attack_text": "string",
      "response_snippet": "string",
      "safety_flags": "array[string]",
      "blocked": "boolean"
    }
  ],
  "coverage": {
    "modules_tested": "array[string]",
    "coverage_percentage": "float",
    "lines_covered": "integer",
    "lines_total": "integer"
  }
}
```

### Excel Report Sheets

| **Sheet Name** | **Required Columns** |
|----------------|---------------------|
| Summary | run_id, timestamp, total_tests, passed, failed, success_rate |
| Detailed | test_id, suite, status, score, execution_time_ms, error_message |
| API_Details | request_id, provider, model, latency_ms, tokens_used, cost_estimate |
| Inputs_And_Expected | test_id, input_query, expected_answer, actual_answer, context_used |
| Adversarial_Details | run_id, request_id, attack_text, response_snippet, safety_flags, blocked |
| Coverage | module_name, coverage_percentage, lines_covered, lines_total |

### Schema Stability

- **v1.x**: Column order and names must remain stable
- **New columns**: May be added to the right of existing columns
- **Breaking changes**: Require major version bump

## 3. Auth & RBAC

### Production Requirements

- **AUTH_MODE**: Must be `jwt` in production environments
- **JWT Requirements**: 
  - Valid `iss` (issuer) claim matching `JWT_ISSUER` environment variable
  - Valid `aud` (audience) claim matching `JWT_AUDIENCE` environment variable
  - RS256 or HS256 signatures supported
  - JWKS endpoint support for RS256

### Development Mode

- **AUTH_MODE**: `token` allowed for development only
- **Token format**: `role:secret` pairs in `AUTH_TOKENS`

### Role-Based Access Control

| **Role** | **Permitted Routes** |
|----------|---------------------|
| user | `/ask`, `/testdata/*` (read-only meta) |
| admin | All endpoints including `/orchestrator/*`, `/testdata/*` (full access) |

### Authentication Flow

1. Extract Bearer token from `Authorization` header
2. Validate token format and signature
3. Extract roles from JWT claims or token prefix
4. Authorize route access based on RBAC rules
5. Return 401 for invalid auth, 403 for insufficient permissions

## 4. Rate Limits

### Baseline Limits

| **Scope** | **Limit** | **Burst** | **Reset Window** |
|-----------|-----------|-----------|------------------|
| Per Token | 60 requests/minute | 10 requests/second | 60 seconds |
| Per IP | 120 requests/minute | 20 requests/second | 60 seconds |
| Upload Endpoint | 10 uploads/hour | 2 uploads/minute | 3600 seconds |

### Rate Limit Headers

```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1640995200
Retry-After: 30
```

### Enforcement

- **429 Response**: Include `Retry-After` header with seconds until reset
- **Token Bucket Algorithm**: Sustained rate with burst capacity
- **Graceful Degradation**: Non-essential requests deprioritized under load

## 5. Test Data Storage Policy

### Storage Backend

- **Primary**: Redis with configurable TTL (default 24 hours)
- **Fallback**: In-memory with process lifecycle limits
- **No Persistence**: User test data must not be written to permanent storage

### Data Retention

- **Test Data Bundles**: Automatic expiration via TTL
- **Metadata Only**: May be retained for observability (anonymized)
- **PII Redaction**: All logged content must be scrubbed of sensitive information

### Size Limits

| **Resource** | **Limit** | **Configurable Via** |
|--------------|-----------|---------------------|
| Upload File Size | 50MB default | `INTAKE_MAX_MB` |
| Records per Bundle | 10,000 default | `INTAKE_MAX_RECORDS` |
| Concurrent Bundles | 1,000 per instance | `INTAKE_MAX_CONCURRENT` |

## 6. Observability

### Required Headers

| **Header** | **Purpose** | **Format** |
|------------|-------------|------------|
| `X-Perf-Phase` | cold/warm classification | `cold` or `warm` |
| `X-Latency-MS` | Request processing time | Integer milliseconds |
| `X-Request-ID` | Unique request identifier | UUID v4 |

### Optional Headers (Feature-Flagged)

| **Header** | **Purpose** | **Flag** |
|------------|-------------|----------|
| `X-P50-MS` | 50th percentile latency | `PERF_PERCENTILES_ENABLED=true` |
| `X-P95-MS` | 95th percentile latency | `PERF_PERCENTILES_ENABLED=true` |

### Metrics Collection

- **Request Counts**: By endpoint, status code, auth method
- **Latency Distributions**: Cold/warm, per endpoint
- **Error Rates**: 4xx vs 5xx classification
- **Test Data Ingestion**: Bytes processed, validation failures

## 7. Resilience & Error Semantics

### Timeout Policies

| **Operation** | **Timeout** | **Configurable Via** |
|---------------|-------------|---------------------|
| LLM Provider Calls | 30 seconds | `LLM_TIMEOUT_SECONDS` |
| File Upload Processing | 60 seconds | `UPLOAD_TIMEOUT_SECONDS` |
| Test Suite Execution | 300 seconds | `ORCHESTRATOR_TIMEOUT_SECONDS` |

### Retry Behavior

- **Exponential Backoff**: Base 100ms, max 5 seconds
- **Jitter**: ±25% randomization to prevent thundering herd
- **Circuit Breaker**: 5 failures in 60 seconds triggers 30-second open state
- **Retryable Errors**: 5xx responses, network timeouts, rate limits (429)

### Error Classification

| **Category** | **Codes** | **Client Action** |
|--------------|-----------|-------------------|
| Client Error | 4xx | Fix request and retry |
| Rate Limited | 429 | Wait for Retry-After, then retry |
| Server Error | 5xx | Retry with backoff |
| Provider Error | 502, 504 | Retry or switch provider |

## 8. Audit & Privacy

### Required Audit Fields

Every test execution must log:

```json
{
  "timestamp": "ISO8601",
  "actor": "user_id_or_token_hash",
  "run_id": "uuid",
  "suites": ["array", "of", "suite", "names"],
  "testdata_id": "uuid_or_null",
  "provider": "string",
  "model": "string", 
  "target_mode": "api|mcp|codebase",
  "verdict_summary": {
    "total_tests": "integer",
    "passed": "integer", 
    "failed": "integer",
    "success_rate": "float"
  }
}
```

### Privacy Controls

- **PII Redaction**: Email addresses, phone numbers, API keys, tokens
- **Content Sanitization**: User inputs logged only in hashed form
- **Data Minimization**: Only essential fields for debugging and audit
- **Retention Limits**: Audit logs expire after 90 days unless required for compliance

### Compliance Readiness

- **GDPR**: Right to erasure, data portability, processing lawfulness
- **SOC 2**: Access controls, change management, monitoring
- **HIPAA**: If enabled, additional encryption and access logging

## 9. CI/CD Quality Gates

### Code Coverage Requirements

| **Module** | **Minimum Coverage** |
|------------|---------------------|
| `apps/` | 80% |
| `llm/` | 80% |
| `frontend/operator-ui/src/` | 70% |

### Security Scanning

- **SAST**: Static analysis for code vulnerabilities
- **Dependency Scanning**: Known vulnerabilities in dependencies  
- **Secret Scanning**: Prevent credential leakage
- **Container Scanning**: Base image vulnerabilities

### Test Requirements

| **Test Type** | **Requirement** |
|---------------|-----------------|
| Unit Tests | 100% pass rate |
| Integration Tests | 100% pass rate |
| API Contract Tests | 100% pass rate |
| Security Tests | No high/critical findings |

### Performance Benchmarks

- **Cold Start**: < 2 seconds for `/ask` endpoint
- **Warm Requests**: < 500ms for `/ask` endpoint  
- **Upload Processing**: < 10 seconds for 10MB files
- **Test Suite Execution**: < 5 minutes for full suite

## 10. Change Control & Deprecation

### Semantic Versioning

- **MAJOR**: Breaking API changes, schema modifications, auth changes
- **MINOR**: New features, optional parameters, new endpoints
- **PATCH**: Bug fixes, security updates, documentation

### Deprecation Process

1. **Announcement**: At least one minor release before removal
2. **Warning Headers**: `X-Deprecated: true` on deprecated endpoints
3. **Documentation**: Update API docs with migration guidance
4. **Sunset Timeline**: Minimum 6 months notice for major endpoints

### Backward Compatibility

| **Component** | **Stability Promise** |
|---------------|--------------------|
| API Endpoints | Stable within major version |
| Request/Response Schemas | Stable within major version |
| Authentication Methods | Stable within major version |
| Report Formats | Stable within major version |
| Environment Variables | Best effort, with migration notes |

### Change Approval

- **Breaking Changes**: Architecture review + customer impact assessment
- **New Features**: Product review + security assessment  
- **Bug Fixes**: Code review + test validation
- **Security Updates**: Expedited process with post-deployment review

---

**Document Version**: 1.0  
**Effective Date**: 2024-12-29  
**Next Review**: 2025-06-29  
**Approval**: Architecture Council, Product Management, Security Team
