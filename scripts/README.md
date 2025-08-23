# Test Scripts

This directory contains production verification scripts for the AI Quality Kit.

## JWT Validation Tests

**File:** `test_jwt_validation.py`

Tests JWT authentication with issuer/audience validation:
- Wrong audience → 401 with `invalid_audience`
- Correct audience → authentication success
- Missing roles → 401 with `insufficient_permissions`

**Usage:**
```bash
# Start server with JWT mode
export AUTH_ENABLED=true AUTH_MODE=jwt JWT_SECRET=test-secret-key
export JWT_ISSUER=https://test-issuer.com JWT_AUDIENCE=https://test-api.com
uvicorn apps.rag_service.main:app --port 8000 &

# Run tests
python scripts/test_jwt_validation.py
```

## Audit Logging Tests

**File:** `test_audit_logging.py`

Tests structured audit logging functionality:
- Request acceptance events
- Orchestrator run start/finish events  
- Authentication failure events
- PII redaction verification

**Usage:**
```bash
# Start server with audit logging
export AUDIT_ENABLED=true AUTH_ENABLED=true AUTH_MODE=jwt
uvicorn apps.rag_service.main:app --port 8000 &

# Run tests (watch server logs for audit events)
python scripts/test_audit_logging.py
```

## Expected Audit Log Format

Audit logs are emitted as JSON lines to stdout:

```json
{"timestamp":1755970843.651284,"event":"request_accepted","iso_timestamp":"2025-08-23T17:40:43Z","route":"/orchestrator/run_tests","actor":"48d191d4","client_ip":"127.0.0.1"}

{"timestamp":1755970843.65165,"event":"orchestrator_run_started","iso_timestamp":"2025-08-23T17:40:43Z","run_id":"run_1755970843_7008bbde","suites":["rag_quality"],"provider":"mock","model":"test-model","actor":"48d191d4"}

{"timestamp":1755970844.090826,"event":"orchestrator_run_finished","iso_timestamp":"2025-08-23T17:40:44Z","run_id":"run_1755970843_7008bbde","success":true,"duration_ms":439.55}
```

## Environment Variables

Both tests require these environment variables:

### JWT Validation
- `AUTH_ENABLED=true`
- `AUTH_MODE=jwt`
- `JWT_SECRET=test-secret-key`
- `JWT_ISSUER=https://test-issuer.com`
- `JWT_AUDIENCE=https://test-api.com`

### Audit Logging  
- `AUDIT_ENABLED=true`
- `AUDIT_REDACT_FIELDS=answer,text,inputs,content,response` (optional)

## Percentile Headers Tests

**File:** `test_percentile_headers.py`

Tests percentile latency headers feature:
- Feature flag behavior (enabled/disabled)
- P50/P95 header appearance after sufficient data
- Monotonic property (P50 ≤ P95)
- Per-route tracking separation

**Usage:**
```bash
# Test with percentiles disabled (default)
python scripts/test_percentile_headers.py

# Test with percentiles enabled
export PERF_PERCENTILES_ENABLED=true
uvicorn apps.rag_service.main:app --port 8000 &
python scripts/test_percentile_headers.py
```

## Expected Headers

### Basic Headers (Always Present)
- `X-Perf-Phase: cold|warm`
- `X-Latency-MS: <milliseconds>`

### Percentile Headers (When Enabled)
- `X-P50-MS: <milliseconds>` (50th percentile)
- `X-P95-MS: <milliseconds>` (95th percentile)

## Notes

- These are smoke tests for production verification
- Check server logs manually for audit events
- Tests use mock provider to avoid external dependencies
- JWT tokens are created with 1-hour expiration
- Percentile headers require 2+ requests to appear
- Ring buffer size configurable via `PERF_WINDOW` (default 500)
