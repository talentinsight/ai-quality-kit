# AI Quality Kit - Operational Runbooks

Operational runbooks for AI Quality Kit service operations, independent of CI/CD systems.

## 1) Deploy & Canary

### Prerequisites

**Required Environment Variables:**
```bash
# Authentication
AUTH_MODE=jwt                                    # Production: 'jwt', Dev: 'token'
JWT_ISSUER=https://your-auth-provider.com       # Required in JWT mode
JWT_AUDIENCE=https://your-api.com               # Required in JWT mode
JWT_SECRET=your-secret-key-256-bits-minimum     # HS256 mode
# OR
JWT_JWKS_URL=https://auth-provider.com/.well-known/jwks.json  # RS256 mode

# Rate Limiting
RL_ENABLED=true
RL_PER_TOKEN_PER_MIN=60
RL_PER_TOKEN_BURST=10
RL_PER_IP_PER_MIN=120
RL_PER_IP_BURST=20

# Optional Redis
REDIS_URL=redis://your-redis:6379               # For distributed rate limiting & test data
REDIS_PREFIX=aqk:

# Storage & Reports
REPORTS_DIR=./reports
TESTDATA_TTL_HOURS=24

# Provider Resilience
PROVIDER_TIMEOUT_S=20
PROVIDER_MAX_RETRIES=2
PROVIDER_CIRCUIT_FAILS=5
PROVIDER_CIRCUIT_RESET_S=30

# Audit & Observability
AUDIT_ENABLED=true
PERF_PERCENTILES_ENABLED=false                  # Optional feature flag
```

**Snowflake Permissions:**
- Use **read-only role** for cache/logging if Snowflake integration enabled
- Verify `SNOWFLAKE_ROLE` has SELECT permissions only

### Deploy Steps

**Blue/Green Deployment:**
```bash
# 1. Deploy new version (green)
docker run -d --name ai-quality-kit-green \
  -p 8001:8000 \
  --env-file .env.prod \
  ai-quality-kit:${NEW_VERSION}

# 2. Wait for startup
sleep 30

# 3. Verify green instance
curl -f http://localhost:8001/healthz || exit 1

# 4. Switch traffic (load balancer config)
# Update LB to route to port 8001

# 5. Stop old version
docker stop ai-quality-kit-blue
docker rm ai-quality-kit-blue

# 6. Rename green to blue
docker rename ai-quality-kit-green ai-quality-kit-blue
```

**Rolling Deployment:**
```bash
# 1. Update with health checks
docker service update \
  --image ai-quality-kit:${NEW_VERSION} \
  --update-delay 30s \
  --update-monitor 60s \
  --update-failure-action rollback \
  ai-quality-kit

# 2. Monitor rollout
docker service ps ai-quality-kit
```

### Canary Plan

**Traffic Progression:** 10% → 50% → 100%

**Success Criteria for Each Stage:**
- Error rate < 1% (HTTP 4xx/5xx)
- X-Latency-MS p95 within 1.5× baseline
- No spike in `ratelimit.blocked_total` (if RL enabled)
- No circuit breaker opens (`X-Circuit-Open` header absent)

**Stage Commands:**
```bash
# Monitor error rate
curl -s http://<host>:<port>/ask | jq '.status'

# Check latency percentiles (if enabled)
curl -i http://<host>:<port>/ask | grep -E 'X-Latency-MS|X-P95-MS'

# Monitor rate limiting
curl -s http://<host>:<port>/testdata/metrics | jq '.["ratelimit.blocked_total"]'
```

### Health Checks

```bash
# Basic health
curl -s -o /dev/null -w "%{http_code}\n" http://<host>:<port>/healthz
# Expected: 200

# Readiness check
curl -s -o /dev/null -w "%{http_code}\n" http://<host>:<port>/readyz  
# Expected: 200

# Detailed health with response time
curl -w "@-" -s http://<host>:<port>/health <<'EOF'
     time_namelookup:  %{time_namelookup}\n
        time_connect:  %{time_connect}\n
           time_total:  %{time_total}\n
          http_code:   %{http_code}\n
EOF

# Check observability headers
curl -i http://<host>:<port>/ask \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"query":"test","provider":"mock"}' | grep -E 'X-Perf-Phase|X-Latency-MS'
```

## 2) Rollback

### Rollback Conditions

**Automatic Triggers:**
- Error rate > 1% sustained for 5 minutes
- X-Latency-MS p95 > 1.5× baseline for 3 minutes
- Circuit breaker opened on any provider (`X-Circuit-Open: true`)
- `ratelimit.blocked_total` spike indicating overload

### Rollback Steps

**Container Rollback:**
```bash
# 1. Stop current version
docker stop ai-quality-kit-current

# 2. Start previous version
docker run -d --name ai-quality-kit-rollback \
  -p 8000:8000 \
  --env-file .env.prod \
  ai-quality-kit:${PREVIOUS_VERSION}

# 3. Update load balancer to previous version
# Update LB configuration

# 4. Clean up failed version
docker rm ai-quality-kit-current
```

**Service Rollback:**
```bash
# Docker Swarm
docker service rollback ai-quality-kit

# Kubernetes
kubectl rollout undo deployment/ai-quality-kit
kubectl rollout status deployment/ai-quality-kit
```

### Post-Rollback Verification

```bash
# Verify health
curl -f http://<host>:<port>/healthz

# Test core functionality
curl -X POST http://<host>:<port>/ask \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"query":"rollback test","provider":"mock"}'

# Check version/artifact
curl -s http://<host>:<port>/health | jq '.version'

# Monitor latency recovery
for i in {1..5}; do
  curl -s -i http://<host>:<port>/ask \
    -H "Authorization: Bearer <token>" \
    -d '{"query":"test"}' | grep X-Latency-MS
  sleep 10
done
```

## 3) Incident Response (Triage)

### Quick Checklist

**1. Basic Health:**
```bash
curl -f http://<host>:<port>/healthz
curl -f http://<host>:<port>/readyz
```

**2. Inspect Audit Logs:**
```bash
# Recent orchestrator runs
grep '"event":"orchestrator_run_started"' <logfile> | tail -10

# Failed runs with details
grep '"event":"orchestrator_run_finished"' <logfile> | grep '"success":false'

# Authentication failures
grep '"event":"auth_failure"' <logfile> | tail -5
```

**3. Provider Health:**
```bash
# Check for circuit breaker
curl -i http://<host>:<port>/ask | grep -i "X-Circuit-Open"

# Provider retry patterns
grep '"event":"retry"' <logfile> | tail -10

# Circuit state changes
grep -E '"event":"circuit_(open|close|half_open)"' <logfile>
```

**4. Rate Limiting:**
```bash
# Check rate limit metrics
curl -s http://<host>:<port>/testdata/metrics | jq '{"blocked": .["ratelimit.blocked_total"], "allowed": .["ratelimit.allowed_total"]}'

# Recent rate limit blocks
grep "429" <logfile> | tail -10
```

### Commands

**Log Monitoring:**
```bash
# Docker logs
docker logs ai-quality-kit --since 15m | jq 'select(.event != null)'

# Kubernetes logs  
kubectl logs -l app=ai-quality-kit --since=15m | jq 'select(.event != null)'

# System logs
journalctl -u ai-quality-kit --since "15 minutes ago"
```

**Audit Log Analysis:**
```bash
# Extract request flow for specific run_id
grep '"run_id":"<run_id>"' <logfile> | jq -r '.timestamp + " " + .event + " " + (.message // "")'

# Recent run summary
grep '"event":"orchestrator_run_finished"' <logfile> | tail -5 | jq '{run_id, success, suites, provider, model}'

# Auth failures by IP
grep '"event":"auth_failure"' <logfile> | jq -r '.client_ip' | sort | uniq -c | sort -nr
```

**Probe Services:**
```bash
# Test orchestrator
curl -X POST http://<host>:<port>/orchestrator/run_tests \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "suites": ["rag_quality"],
    "options": {"provider": "mock"},
    "target_mode": "api"
  }'

# Test data intake
curl -X POST http://<host>:<port>/testdata/paste \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"passages": "{\"id\":\"test\",\"text\":\"probe\"}"}'
```

### Report Retrieval

**Location:** `${REPORTS_DIR}` (default: `./reports`)
**Auto-delete:** `REPORT_AUTO_DELETE_MINUTES` (default: 10 minutes)

```bash
# List recent reports
ls -la ${REPORTS_DIR}/*.{json,xlsx} | head -10

# Download before auto-delete
curl -O http://<host>:<port>/reports/<run_id>/report.json
curl -O http://<host>:<port>/reports/<run_id>/report.xlsx

# Check report structure
jq '.adversarial_details | length' ${REPORTS_DIR}/<run_id>.json
```

## 4) JWT Key Rotation (HS256 or JWKS)

### HS256 Rotation

**Generate New Key:**
```bash
NEW_SECRET=$(openssl rand -base64 32)
echo "New JWT_SECRET: $NEW_SECRET"
```

**Staged Rollout:**
```bash
# 1. Add new secret as secondary (if gateway supports dual validation)
# Update gateway/proxy configuration

# 2. Update application
export JWT_SECRET="$NEW_SECRET"
docker restart ai-quality-kit

# 3. Wait for propagation (2-3 minutes)
sleep 180

# 4. Validate new tokens work
python3 -c "
import jwt
from datetime import datetime, timedelta, timezone

token = jwt.encode({
    'sub': 'test-user',
    'iss': '${JWT_ISSUER}',
    'aud': '${JWT_AUDIENCE}',
    'roles': ['user'],
    'exp': datetime.now(timezone.utc) + timedelta(hours=1)
}, '${NEW_SECRET}', algorithm='HS256')

print('Test token:', token)
"

# 5. Test with new token
curl -X POST http://<host>:<port>/ask \
  -H "Authorization: Bearer <new_token>" \
  -H "Content-Type: application/json" \
  -d '{"query":"key rotation test","provider":"mock"}'

# 6. Remove old secret from gateway
```

### JWKS Rotation

**JWKS Endpoint Update:**
```bash
# 1. Publish new key in JWKS endpoint
# Update your auth provider's JWKS

# 2. Wait for cache TTL (10 minutes default)
sleep 600

# 3. Start issuing tokens with new key ID
# Update your token issuer to use new 'kid'

# 4. Test new tokens
curl -X POST http://<host>:<port>/ask \
  -H "Authorization: Bearer <token_with_new_kid>" \
  -d '{"query":"jwks rotation test"}'

# 5. Wait grace period (24 hours recommended)
# 6. Remove old key from JWKS
```

### Validation Tests

```bash
# Good token → 200
curl -X POST http://<host>:<port>/ask \
  -H "Authorization: Bearer <valid_token>" \
  -H "Content-Type: application/json" \
  -d '{"query":"test"}' \
  -w "HTTP Status: %{http_code}\n"

# Wrong issuer → 401
curl -X POST http://<host>:<port>/ask \
  -H "Authorization: Bearer <wrong_iss_token>" \
  -d '{"query":"test"}' \
  -w "HTTP Status: %{http_code}\n"

# Expired token → 401
curl -X POST http://<host>:<port>/ask \
  -H "Authorization: Bearer <expired_token>" \
  -d '{"query":"test"}' \
  -w "HTTP Status: %{http_code}\n"

# Verify error response doesn't echo token
curl -X POST http://<host>:<port>/ask \
  -H "Authorization: Bearer invalid_token_content" \
  -d '{"query":"test"}' 2>&1 | grep -v "invalid_token_content"
```

## 5) Test Data Purge (Redis)

### Safeguards

**Always verify prefix before deletion:**
```bash
echo "Redis prefix: ${REDIS_PREFIX:-aqk:}"
redis-cli PING
```

### Inspection Commands

```bash
# List all test data keys
redis-cli --scan --pattern "${REDIS_PREFIX:-aqk:}testdata:*" | head -20

# Count total test data bundles
redis-cli --scan --pattern "${REDIS_PREFIX:-aqk:}testdata:*:meta" | wc -l

# Check specific bundle
TESTDATA_ID="<id>"
redis-cli HGETALL ${REDIS_PREFIX:-aqk:}testdata:${TESTDATA_ID}:meta

# Check TTL
redis-cli TTL ${REDIS_PREFIX:-aqk:}testdata:${TESTDATA_ID}:payloads
redis-cli TTL ${REDIS_PREFIX:-aqk:}testdata:${TESTDATA_ID}:meta
```

### Purge Operations

**Single Bundle:**
```bash
TESTDATA_ID="<id>"
PREFIX="${REDIS_PREFIX:-aqk:}"

# Delete both keys
redis-cli DEL ${PREFIX}testdata:${TESTDATA_ID}:payloads
redis-cli DEL ${PREFIX}testdata:${TESTDATA_ID}:meta

# Verify deletion
redis-cli EXISTS ${PREFIX}testdata:${TESTDATA_ID}:payloads
redis-cli EXISTS ${PREFIX}testdata:${TESTDATA_ID}:meta
```

**Bulk Purge (Use with extreme caution):**
```bash
PREFIX="${REDIS_PREFIX:-aqk:}"

# Dry run - list what would be deleted
redis-cli --scan --pattern "${PREFIX}testdata:*" | head -50

# Confirm prefix and count
echo "About to delete $(redis-cli --scan --pattern "${PREFIX}testdata:*" | wc -l) keys"
read -p "Are you sure? (yes/no): " confirmation

if [ "$confirmation" = "yes" ]; then
  # Delete in batches to avoid blocking Redis
  redis-cli --scan --pattern "${PREFIX}testdata:*" | xargs -n 50 redis-cli DEL
  echo "Purge completed"
else
  echo "Purge cancelled"
fi
```

### Post-Purge Verification

```bash
# Test API returns 404/410 for purged data
curl -s -o /dev/null -w "%{http_code}\n" \
  http://<host>:<port>/testdata/<purged_id>/meta
# Expected: 404

# Verify Redis cleanup
redis-cli --scan --pattern "${REDIS_PREFIX:-aqk:}testdata:*" | wc -l

# Check memory usage reduction
redis-cli INFO memory | grep used_memory_human
```

## 6) Rate Limit Tuning

### Environment Variables

**Current Implementation:**
```bash
# Enable/disable rate limiting
RL_ENABLED=true

# Per-token limits (authenticated requests)
RL_PER_TOKEN_PER_MIN=60        # 60 requests per minute sustained
RL_PER_TOKEN_BURST=10          # 10 requests burst capacity

# Per-IP limits (all requests from same IP)  
RL_PER_IP_PER_MIN=120          # 120 requests per minute sustained
RL_PER_IP_BURST=20             # 20 requests burst capacity

# Optional distributed backend
REDIS_URL=redis://localhost:6379
```

### Testing Rate Limits

**Burst Test:**
```bash
# Test burst capacity (should get some 429s)
for i in {1..25}; do
  curl -s -o /dev/null -w "%{http_code} " \
    -H "Authorization: Bearer <token>" \
    http://<host>:<port>/ask
done
echo ""

# Check for 429 responses and Retry-After headers
curl -i -H "Authorization: Bearer <token>" \
  http://<host>:<port>/ask | grep -E "HTTP|Retry-After"
```

**Sustained Rate Test:**
```bash
# Test sustained rate over time
for i in {1..120}; do
  curl -s -o /dev/null -w "%{http_code}\n" \
    -H "Authorization: Bearer <token>" \
    http://<host>:<port>/ask
  sleep 1
done | sort | uniq -c
```

**Monitor Rate Limit Metrics:**
```bash
# Check blocked vs allowed counts
curl -s http://<host>:<port>/testdata/metrics | \
  jq '{blocked: .["ratelimit.blocked_total"], allowed: .["ratelimit.allowed_total"]}'

# Calculate block rate
curl -s http://<host>:<port>/testdata/metrics | \
  jq '(.["ratelimit.blocked_total"] / (.["ratelimit.blocked_total"] + .["ratelimit.allowed_total"])) * 100'
```

## 7) Feature Flags & Observability

### Feature Flags

```bash
# Performance percentiles (p50/p95 headers)
PERF_PERCENTILES_ENABLED=true
PERF_WINDOW=500

# Service modes
UI_ENABLED=false
A2A_ENABLED=true  
OFFLINE_MODE=false

# Logging & audit
AUDIT_ENABLED=true
AUDIT_REDACT_FIELDS=answer,text,inputs,content,response
```

### Header Inspection

```bash
# Check all performance headers
curl -i -H "Authorization: Bearer <token>" \
  http://<host>:<port>/ask \
  -d '{"query":"test","provider":"mock"}' | \
  grep -E 'X-Latency-MS|X-P(50|95)-MS|X-Perf-Phase'

# Expected output:
# X-Perf-Phase: cold|warm
# X-Latency-MS: <milliseconds>
# X-P50-MS: <milliseconds>     (if PERF_PERCENTILES_ENABLED=true)
# X-P95-MS: <milliseconds>     (if PERF_PERCENTILES_ENABLED=true)

# Test different endpoints for per-route percentiles
curl -i http://<host>:<port>/testdata/metrics | grep -E 'X-P(50|95)-MS'
curl -i http://<host>:<port>/orchestrator/run_tests | grep -E 'X-P(50|95)-MS'
```

### Observability Dashboards

**Key Metrics to Monitor:**
- **Latency p95**: X-Latency-MS values over time
- **Error Rate**: 4xx/5xx status codes percentage  
- **Rate Limit Blocks**: `ratelimit.blocked_total` growth rate
- **Provider Circuit Breaker**: `X-Circuit-Open` header occurrences
- **Cold vs Warm**: X-Perf-Phase distribution

**Sample Queries:**
```bash
# Latency trend (requires log aggregation)
grep "X-Latency-MS" <logfile> | awk '{print $NF}' | sort -n | tail -20

# Error rate calculation
total=$(grep -c "HTTP" <logfile>)
errors=$(grep -c "HTTP [45][0-9][0-9]" <logfile>)
echo "Error rate: $(echo "scale=2; $errors / $total * 100" | bc)%"

# Circuit breaker alerts
grep -c "X-Circuit-Open: true" <logfile>
```

## 8) Minimal Smoke Suite

### End-to-End Test Sequence

**1. Upload Test Data:**
```bash
# Create test bundle
TESTDATA_RESPONSE=$(curl -s -X POST http://<host>:<port>/testdata/paste \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "passages": "{\"id\":\"smoke-1\",\"text\":\"Test passage for smoke testing\"}",
    "qaset": "{\"qid\":\"q1\",\"question\":\"What is this?\",\"expected_answer\":\"A test\"}"
  }')

TESTDATA_ID=$(echo $TESTDATA_RESPONSE | jq -r '.testdata_id')
echo "Test Data ID: $TESTDATA_ID"
```

**2. Verify Metadata:**
```bash
# Check bundle metadata
curl -s http://<host>:<port>/testdata/${TESTDATA_ID}/meta \
  -H "Authorization: Bearer <token>" | jq '{
    testdata_id: .testdata_id,
    passages: .artifacts.passages.count,
    qaset: .artifacts.qaset.count,
    expires_at: .expires_at
  }'
```

**3. Run Test Suite:**
```bash
# Execute orchestrator run
RUN_RESPONSE=$(curl -s -X POST http://<host>:<port>/orchestrator/run_tests \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d "{
    \"suites\": [\"rag_quality\", \"red_team\"],
    \"testdata_id\": \"${TESTDATA_ID}\",
    \"options\": {\"provider\": \"mock\"},
    \"target_mode\": \"api\"
  }")

RUN_ID=$(echo $RUN_RESPONSE | jq -r '.run_id')
echo "Run ID: $RUN_ID"
```

**4. Verify Outputs:**
```bash
# Check JSON report structure
JSON_REPORT="${REPORTS_DIR}/${RUN_ID}.json"
if [ -f "$JSON_REPORT" ]; then
  echo "✓ JSON report exists"
  
  # Verify required sections
  jq -e '.adversarial_details | type == "array"' $JSON_REPORT && echo "✓ adversarial_details[] present"
  jq -e '.coverage | type == "object"' $JSON_REPORT && echo "✓ coverage{} present"
else
  echo "✗ JSON report missing: $JSON_REPORT"
fi

# Check Excel report
XLSX_REPORT="${REPORTS_DIR}/${RUN_ID}.xlsx"
if [ -f "$XLSX_REPORT" ]; then
  echo "✓ Excel report exists"
  
  # Use file command to verify it's actually an Excel file
  file $XLSX_REPORT | grep -q "Excel" && echo "✓ Valid Excel format"
else
  echo "✗ Excel report missing: $XLSX_REPORT"
fi
```

### Expected Results

**Successful Smoke Test:**
- ✓ Upload returns `testdata_id`
- ✓ Metadata shows correct counts and TTL
- ✓ Orchestrator returns `run_id`
- ✓ JSON report contains `adversarial_details[]` array
- ✓ JSON report contains `coverage{}` object
- ✓ Excel file exists with **Adversarial_Details** and **Coverage** sheets
- ✓ All API calls return appropriate performance headers

**Failure Investigation:**
```bash
# Check recent audit logs for the run
grep "\"run_id\":\"${RUN_ID}\"" <logfile> | jq -r '.timestamp + " " + .event + " " + (.message // "")'

# Verify auth was successful
grep "\"run_id\":\"${RUN_ID}\"" <logfile> | jq 'select(.event == "request_accepted")'

# Check for provider issues
grep "\"run_id\":\"${RUN_ID}\"" <logfile> | jq 'select(.event | contains("provider"))'
```

---

**Notes:**
- Replace `<host>`, `<port>`, `<token>`, `<id>` placeholders with actual values
- Verify `REDIS_PREFIX` and `REPORTS_DIR` environment variables before operations
- Always test commands in non-production environment first
- Keep runbook commands copy-pasteable for incident response speed
