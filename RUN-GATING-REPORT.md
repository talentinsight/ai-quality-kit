# RUN-GATING-REPORT.md

**Repository**: ai-quality-kit  
**Date**: 2025-01-03 18:40:36Z  
**Git Ref**: c4d5d37 (HEAD -> newtest, origin/newtest) mjaor ui changes  

---

## 1) Executive Summary

• **LLM Targeting**: System supports 5 adapter modes: OpenAI/Anthropic/Gemini presets (using SDK defaults), Custom REST (requires server_url), and MCP (requires mcp_endpoint). Mock provider available for testing. All adapters use unified `BaseClient` interface via `client_factory.py:122`.

• **Run Button Gating**: "Run Tests" is disabled when: (1) missing target_mode/provider/model, (2) required test data artifacts missing per suite requirements, (3) server_url missing for Custom REST, (4) mcp_endpoint missing for MCP mode. Logic in `frontend/operator-ui/src/ui/App.tsx:1521`.

• **RAG GT Modes**: Ground Truth "available" requires qaset.jsonl and enables 6 metrics (faithfulness, answer_relevancy, context_precision, context_recall, answer_correctness, answer_similarity). "Not available" mode uses 3 GT-agnostic metrics via RAGAS fallback or internal scorers. Implementation in `apps/orchestrator/rag_runner.py:38`.

• **Top 5 Risks**: (1) Server URL required for OpenAI presets but should be optional, (2) Context metrics selectable without passages upload warning, (3) MCP mode is stub implementation, (4) No centralized requirements validation between UI and backend, (5) Retrieval metrics depend on contexts_jsonpath but no validation if path is invalid.

• **Quick Wins**: Centralize data requirements in single source of truth, add tooltips for missing data, validate JSONPath expressions, implement real MCP client, align UI gating with backend validation.

---

## 2) Architecture Map

### Repository Structure
```
ai-quality-kit/
├── apps/
│   ├── orchestrator/          # Core test execution engine
│   │   ├── run_tests.py       # Main TestRunner class
│   │   ├── router.py          # FastAPI endpoints (/run_tests, /start)
│   │   ├── client_factory.py  # Provider abstraction (API/MCP)
│   │   ├── rag_runner.py      # RAG-specific evaluation logic
│   │   ├── run_profiles.py    # Smoke/Full profiles + rate limiting
│   │   └── suites/            # Test suite implementations
│   ├── testdata/              # Test data intake & validation
│   │   ├── router.py          # Upload endpoints (/testdata/)
│   │   ├── validators_rag.py  # Schema/ref/duplicate validation
│   │   ├── loaders_rag.py     # JSONL file loading
│   │   └── store.py           # Redis-backed TTL storage
│   ├── reporters/             # Excel/JSON report generation
│   │   └── excel_reporter.py  # Multi-sheet XLSX v2 format
│   └── rag_service/           # RAG pipeline (embeddings/retrieval)
├── frontend/operator-ui/      # React/Vite UI
│   ├── src/ui/App.tsx         # Main application with run gating
│   ├── src/components/        # Test suite selectors, data panels
│   └── src/lib/               # Requirements matrix, API client
└── llm/provider.py            # LLM provider implementations
```

### RAG Run Sequence Diagram
```
UI (App.tsx) → POST /orchestrator/run_tests → TestRunner.run_all_tests()
    ↓
TestRunner → client_factory.make_client() → ApiClient/McpClient
    ↓
RAGRunner.run_rag_quality() → load_passages/qaset → generate responses
    ↓
evaluate_ragas() OR internal_scorers → compute metrics
    ↓
ExcelReporter.write_excel() → Summary/Detailed/Coverage sheets
```

---

## 3) LLM Targeting — Control Flow (UI → Backend)

### UI State Management (`frontend/operator-ui/src/ui/App.tsx`)
- `targetMode`: "api"|"mcp"|"" (line 34)
- `provider`: string from preset selection (OpenAI/Anthropic/Gemini/Custom/Mock)
- `model`: string model name
- `apiBaseUrl`: server URL for API mode (line 31)
- `mcpServerUrl`: MCP endpoint URL (line 32)
- `token`: bearer token (line 33)
- `hasGroundTruth`: boolean GT toggle (line 40)
- `testdataId`: uploaded test data bundle ID (line 48)
- `retrievalJsonPath/retrievalTopK`: retrieval metrics config (lines 43-44)
- `runProfile`: "smoke"|"full" (line 45)

### Payload Builder (`frontend/operator-ui/src/lib/api.ts:mapRunConfigToRequest`)
```typescript
// File: frontend/operator-ui/src/lib/api.ts:45-80
export function mapRunConfigToRequest(cfg: RunConfig): OrchestratorRequest {
  return {
    target_mode: cfg.target_mode,
    provider: cfg.provider,
    model: cfg.model,
    server_url: cfg.url,           // Maps to server_url for API mode
    mcp_endpoint: cfg.mcp_endpoint, // Maps to mcp_endpoint for MCP mode
    suites: cfg.test_suites,
    ground_truth: cfg.ground_truth,
    testdata_id: cfg.testdata_id,
    retrieval: cfg.retrieval,      // contexts_jsonpath, top_k, note
    // ... other fields
  }
}
```

### Backend Request Schema (`apps/orchestrator/run_tests.py:299-340`)
```python
class OrchestratorRequest(BaseModel):
    target_mode: TargetMode                    # Required: "api"|"mcp"
    provider: str = "openai"                   # Default: openai
    model: str = "gpt-4"                       # Default: gpt-4
    server_url: Optional[str] = None           # API mode URL
    mcp_endpoint: Optional[str] = None         # MCP mode endpoint
    suites: List[TestSuiteName]                # Required: test suites list
    testdata_id: Optional[str] = None          # Test data bundle ID
    ground_truth: Optional[str] = "not_available"  # "available"|"not_available"
    retrieval: Optional[Dict[str, Any]] = None # contexts_jsonpath, top_k, note
    thresholds: Optional[Dict[str, float]] = None
    determinism: Optional[Dict[str, Any]] = None
```

---

## 4) Run-Gating Requirements Matrix

| GT Mode | Adapter | Metric Group | Needs Passages? | Needs QA Set? | Needs Server URL? | Needs Output JSONPath? | Needs Contexts JSONPath? | Needs MCP Endpoint? |
|---------|---------|--------------|----------------|---------------|-------------------|----------------------|-------------------------|-------------------|
| available | OpenAI | Core RAG | ✅ `requirements.ts:26` | ✅ `requirements.ts:27` | ❌ Uses SDK default | ❌ Not implemented | Optional `rag_runner.py:338` | ❌ |
| available | Anthropic | Core RAG | ✅ `requirements.ts:26` | ✅ `requirements.ts:27` | ❌ Uses SDK default | ❌ Not implemented | Optional `rag_runner.py:338` | ❌ |
| available | Gemini | Core RAG | ✅ `requirements.ts:26` | ✅ `requirements.ts:27` | ❌ Uses SDK default | ❌ Not implemented | Optional `rag_runner.py:338` | ❌ |
| available | Custom REST | Core RAG | ✅ `requirements.ts:26` | ✅ `requirements.ts:27` | ✅ `client_factory.py:147` | ❌ Not implemented | Optional `rag_runner.py:338` | ❌ |
| available | MCP | Core RAG | ✅ `requirements.ts:26` | ✅ `requirements.ts:27` | ❌ | ❌ Not implemented | Optional `rag_runner.py:338` | ✅ `client_factory.py:159` |
| not_available | OpenAI | GT-Agnostic | Optional | ❌ | ❌ Uses SDK default | ❌ Not implemented | Optional `rag_runner.py:338` | ❌ |
| not_available | Anthropic | GT-Agnostic | Optional | ❌ | ❌ Uses SDK default | ❌ Not implemented | Optional `rag_runner.py:338` | ❌ |
| not_available | Gemini | GT-Agnostic | Optional | ❌ | ❌ Uses SDK default | ❌ Not implemented | Optional `rag_runner.py:338` | ❌ |
| not_available | Custom REST | GT-Agnostic | Optional | ❌ | ✅ `client_factory.py:147` | ❌ Not implemented | Optional `rag_runner.py:338` | ❌ |
| not_available | MCP | GT-Agnostic | Optional | ❌ | ❌ | ❌ Not implemented | Optional `rag_runner.py:338` | ✅ `client_factory.py:159` |

**Context-based metrics** (Context Recall/Entities/Precision/Rel.) require passages in both GT modes.
**Retrieval@K metrics** (recall@k/MRR@k/nDCG@k) require contexts_jsonpath; if absent → "N/A" in reports.

---

## 5) Current Disabled-State Logic

### Primary Gating Logic (`frontend/operator-ui/src/ui/App.tsx:1506-1521`)
```typescript
const requiredFields = [];
// ... field validation logic ...
const isDisabled = requiredFields.length > 0 || !targetMode || !provider || !model;
```

### Guard Conditions with User-Visible Messages:
- **Missing Target Mode**: "Select API or MCP mode" (implicit from `!targetMode`)
- **Missing Provider**: "Select LLM provider" (implicit from `!provider`) 
- **Missing Model**: "Select model" (implicit from `!model`)
- **Missing Test Data**: "Missing: Passages (required by Context metrics)" (`App.tsx:1527`)
- **Missing Server URL**: For Custom REST adapter (validated in `client_factory.py:147`)
- **Missing MCP Endpoint**: For MCP mode (validated in `client_factory.py:159`)

### UI/Backend Validation Mismatch:
- **Issue**: UI requires Server URL for OpenAI presets, but backend uses SDK defaults (`client_factory.py:148`)
- **Issue**: UI shows Context metrics as selectable without passages warning until "Show Requirements" clicked
- **Issue**: No validation of contexts_jsonpath syntax in UI

---

## 6) Adapter Behavior Matrix

| Adapter | Uses SDK? | Uses Server URL? | Needs output_jsonpath? | Supports contexts_jsonpath? | Token Source | Retries/Backoff? | Timeout Knobs? |
|---------|-----------|------------------|----------------------|---------------------------|--------------|------------------|----------------|
| OpenAI | ✅ `llm/provider.py:75` | ❌ SDK default | ❌ Not implemented | ✅ Via retrieval config | `OPENAI_API_KEY` env | ✅ `resilient_client.py` | ✅ Circuit breaker |
| Anthropic | ✅ `llm/provider.py:150` | ❌ SDK default | ❌ Not implemented | ✅ Via retrieval config | `ANTHROPIC_API_KEY` env | ✅ `resilient_client.py` | ✅ Circuit breaker |
| Gemini | ✅ `llm/provider.py:220` | ❌ SDK default | ❌ Not implemented | ✅ Via retrieval config | `GEMINI_API_KEY` env | ✅ `resilient_client.py` | ✅ Circuit breaker |
| Custom REST | ❌ | ✅ Required `client_factory.py:147` | ❌ Not implemented | ✅ Via retrieval config | Bearer token | ✅ `resilient_client.py` | ✅ Circuit breaker |
| MCP | ❌ Stub only | ❌ | ❌ Not implemented | ✅ Via retrieval config | None | ❌ TODO | ❌ TODO |
| Mock | ❌ | ❌ | ❌ Not implemented | ✅ Via retrieval config | None | ❌ | ❌ |

**Key Files**:
- Provider factory: `llm/provider.py:30`
- Client factory: `apps/orchestrator/client_factory.py:122`
- Resilient client: `llm/resilient_client.py`

---

## 7) RAG Execution — With vs Without Ground Truth

### With Ground Truth (`gt_mode="available"`)
**Inputs Required**: passages.jsonl + qaset.jsonl with expected_answer fields
**Metrics Computed**: 6 metrics via RAGAS or internal scorers
- faithfulness, answer_relevancy, context_precision (GT-agnostic)
- context_recall, answer_correctness, answer_similarity (GT-dependent)
**Gating**: Applied via `RAGThresholds` (`apps/orchestrator/rag_runner.py:18-28`)
**Implementation**: `apps/orchestrator/rag_runner.py:180-208`

### Without Ground Truth (`gt_mode="not_available"`)
**Inputs Required**: passages.jsonl (qaset optional for question generation)
**Metrics Computed**: 3 GT-agnostic metrics only
- faithfulness, answer_relevancy, context_precision
**Gating**: Relaxed thresholds, focuses on prompt robustness
**Implementation**: `apps/orchestrator/rag_runner.py:210-242`

### Retrieval Metrics (Both Modes)
**Trigger**: `retrieval.contexts_jsonpath` is set in request
**Computation**: recall@k, MRR@k, nDCG@k where k = len(retrieved_contexts)
**Fallback**: If JSONPath resolves to empty → "N/A" in Detailed sheet + warning
**Location**: Retrieved contexts extraction logic in RAG pipeline

### Prompt Robustness / Profiles
**Smoke Profile**: `qa_sample_size: 20` (`apps/orchestrator/run_profiles.py:132`)
**Full Profile**: `qa_sample_size: null` (no limit)
**Perturbations**: Applied when GT=false OR "Prompt Robustness" selected
**Catalog**: `["typo_noise", "casing_flip", "negation_insert", "distractor_suffix"]`

### Deterministic Scoring
All metrics computed deterministically without "another AI interprets results". RAGAS uses external LLM APIs but with fixed temperature=0, seed=42 (`apps/orchestrator/client_factory.py:14-18`).

---

## 8) Test Data Intake & Validators

### Upload Flow
**Upload/URL/Paste** → `POST /testdata/` → `testdata_id` → **manifest resolution** → **validators**

### Endpoints (`apps/testdata/router.py`)
- `POST /testdata/` - Named fields (passages/qaset/attacks/schema) OR legacy files[]+kinds[]
- `GET /testdata/{id}/manifest` - Retrieve manifest with TTL info
- Template downloads for Excel/JSONL formats

### Validation Pipeline (`apps/testdata/validators_rag.py:169`)
```python
def validate_rag_data(passages: List[Dict], qaset: List[Dict]) -> RAGValidationResult:
    # Schema validation (required fields)
    # Reference validation (contexts point to valid passage IDs)  
    # Duplicate detection (duplicate IDs, questions)
    # Leakage heuristics (questions appearing in passages)
    # Distribution statistics (length, categories)
```

### Suite Requirements (`frontend/operator-ui/src/lib/requirements.ts:24`)
```typescript
export const SUITE_REQUIREMENTS: Record<string, Requirement[]> = {
  rag_quality: [
    R('passages','required','JSONL passages with {"id","text","meta"}'),
    R('qaset','required','JSONL Q/A with {"qid","question","expected_answer"}'),
    R('schema','optional','Response schema (if you want schema validation)'),
  ],
  red_team: [R('attacks','required','TXT (one per line) or YAML list')],
  safety: [R('attacks','optional'), R('schema','optional')],
  // ... other suites
}
```

### TTL/Cleanup (`apps/testdata/store.py`)
- **Default TTL**: 2 hours (`TESTDATA_TTL_HOURS=2`)
- **Storage**: Redis-backed with automatic cleanup task (30min intervals)
- **No Retention**: Raw API responses not persisted, only derived metrics

---

## 9) Reporting Surfaces (JSON & XLSX v2)

### Sheet Structure (`apps/reporters/excel_reporter.py`)

**Summary Sheet** (`_create_summary_sheet:78-130`):
- Always: run_id, started_at, target_mode, ground_truth, suites, total_tests, pass_rate, provider, model, gate, elapsed_ms
- GT-dependent: faithfulness_avg, context_recall_avg (only if GT=available)
- Retrieval-dependent: retrieval_top_k, retrieval_note (only if contexts_jsonpath set)
- Profile-dependent: profile, concurrency (from run_profiles)

**Detailed Sheet** (`_create_detailed_sheet:283-311`):
- Always: suite, case_id, provider, model, question, predicted, expected, pass_fail_reason, latency_ms, timestamp
- GT-dependent: faithfulness, context_recall, answer_correctness, answer_similarity
- Retrieval-dependent: retrieved_count, recall_at_k, mrr_at_k, ndcg_at_k
- Robustness: perturbations_applied (array of applied perturbation names)

**Coverage Sheet**:
- Always: total_tests, passed, failed, errors
- Retrieval-dependent: contexts_missing, perturbed_sampled counts

**N/A Handling**:
- Missing contexts_jsonpath → "N/A" in retrieval metric columns
- GT=not_available → "N/A" in GT-dependent metric columns
- Failed JSONPath resolution → "N/A" + warning in manifest

### JSON Report Structure
Same data as Excel but in nested JSON format. Raw API responses are NOT included, only derived metrics and metadata.

---

## 10) Error Handling & Edge Cases

### HTTP Error Handling (`llm/resilient_client.py`)
- **401/403**: Authentication errors, no retry
- **404**: Not found, no retry  
- **429**: Rate limit, exponential backoff with jitter
- **5xx**: Server errors, circuit breaker pattern
- **Timeouts**: Configurable per provider, default circuit breaker

### MCP Error Handling (`apps/orchestrator/client_factory.py:88`)
**Current**: Stub implementation returns mock responses
**TODO**: Real MCP client with proper error surfacing

### JSONPath Edge Cases
- **Wrong JSONPath**: No validation in UI, backend returns empty contexts → "N/A" metrics
- **Missing contexts field**: Graceful degradation to "N/A" with warning
- **Invalid JSON response**: Parser error → case marked as failed

### Rate Limiting (`apps/orchestrator/run_profiles.py:38`)
- **Concurrency Cap**: 2-4 concurrent requests when perf_repeats > 1
- **Backoff Strategy**: Jittered exponential backoff on 429/503
- **Circuit Breaker**: Opens after consecutive failures, prevents cascade

---

## 11) Coverage Snapshot

### Backend Coverage (from `coverage.json`)
**Overall**: 12% coverage (69/565 statements)

**Lowest Coverage Files** (0% coverage):
1. `apps/cache/cache_store.py` - 0/80 statements
2. `apps/db/eval_logger.py` - 0/36 statements  
3. `apps/observability/live_eval.py` - 0/78 statements
4. `apps/observability/log_service.py` - 0/66 statements
5. `apps/rag_service/config.py` - 0/24 statements
6. `apps/rag_service/main.py` - 0/92 statements
7. `apps/rag_service/rag_pipeline.py` - 0/60 statements
8. `apps/utils/hash_utils.py` - 0/11 statements
9. `apps/utils/json_utils.py` - 0/24 statements
10. `apps/db/run_context.py` - 0/9 statements

**Highest Coverage Files**:
1. `apps/testing/neg_utils.py` - 88% (22/25 statements)
2. `apps/db/snowflake_client.py` - 78% (47/60 statements)

### Frontend Tests
**Status**: Not configured - no vitest/jest setup found in `frontend/operator-ui/`
**Test Files**: 2,798 Python test files found, no frontend test files

### Coverage Gates
**Current**: No `--cov-fail-under` threshold set in `pytest.ini`
**Recommendation**: Set minimum 70% coverage gate for new code

---

## 12) Known Bugs & Inconsistencies

### 1. Server URL Required for Presets (`client_factory.py:147-148`)
**Issue**: UI may require server URL for OpenAI preset, but backend uses SDK defaults
**Repro**: Select OpenAI preset → UI may show "Missing Server URL" but backend works fine
**Fix**: Remove server URL requirement for preset providers in UI validation

### 2. Context Metrics Without Passages (`requirements.ts:26`)
**Issue**: Context metrics selectable in UI without passages upload warning
**Repro**: Select context metrics → no immediate warning until "Show Requirements" clicked
**Fix**: Add real-time validation tooltip when context metrics selected without passages

### 3. MCP Mode Stub Implementation (`client_factory.py:88`)
**Issue**: MCP client returns mock responses, not real MCP communication
**Repro**: Set target_mode=mcp → gets mock response instead of real MCP call
**Fix**: Implement real MCP client with proper protocol handling

### 4. JSONPath Validation Missing (`rag_runner.py:338`)
**Issue**: No syntax validation of contexts_jsonpath in UI or backend
**Repro**: Enter invalid JSONPath → runtime error or empty results
**Fix**: Add JSONPath syntax validation in UI with preview

### 5. Requirements Validation Mismatch
**Issue**: UI requirements logic separate from backend validation
**Repro**: UI allows run but backend rejects due to different validation rules
**Fix**: Centralize requirements in shared schema/config

---

## 13) Quick-Fix Checklist

• **Centralize Requirements**: Move `SUITE_REQUIREMENTS` to shared backend endpoint, consume in UI (`requirements.ts:24` → API call)

• **Add JSONPath Validation**: Client-side JSONPath syntax check with preview (`App.tsx:43` add validation)

• **Fix Server URL Logic**: Remove server URL requirement for presets in UI (`client_factory.py:147-148` align with UI)

• **Add Context Tooltips**: Real-time tooltip when context metrics selected without passages (`TestSuiteSelector.tsx` add validation)

• **Implement MCP Client**: Replace stub with real MCP protocol client (`client_factory.py:88` implement)

• **Add Coverage Gate**: Set `--cov-fail-under=70` in `pytest.ini`

• **Sync Validation**: Backend `/validate` endpoint that mirrors UI requirements logic

• **Add Frontend Tests**: Setup vitest for component testing in `frontend/operator-ui/`

---

## 14) How to Exercise Retrieval Metrics

### Mock Adapter with Contexts
**Available**: Mock provider in `llm/provider.py:58` returns structured responses
**JSONPath Example**: Use `"$.contexts"` or `"$.retrieved"` for mock responses
**Test Shape**: Mock can return `{"answer": "...", "contexts": ["ctx1", "ctx2"]}`

### JSONPath Suggester
**Status**: Not implemented
**Recommendation**: Add endpoint `GET /testdata/{id}/suggest_jsonpath` that analyzes sample responses and suggests common paths

### Tiny Endpoint Stub
```python
# Add to apps/rag_service/main.py
@app.post("/mock_rag")
async def mock_rag_with_contexts(query: str):
    return {
        "answer": f"Mock answer for: {query}",
        "contexts": ["Retrieved context 1", "Retrieved context 2"],
        "confidence": 0.85
    }
```

---

## 15) Appendix

### Glossary
- **retrieval**: Process of finding relevant passages for a query using embeddings or TF-IDF
- **contexts_jsonpath**: JSONPath expression to extract retrieved contexts from LLM response (e.g., "$.contexts")
- **output_jsonpath**: JSONPath for extracting structured output (not implemented)
- **profiles**: Run configurations (smoke=20 samples, full=unlimited)
- **GT vs no-GT**: Ground Truth available (6 metrics) vs not available (3 metrics)

### Environment Variables (values masked)
```bash
# LLM Provider Keys
OPENAI_API_KEY=sk-***
ANTHROPIC_API_KEY=***
GEMINI_API_KEY=***

# Test Data Storage  
REDIS_URL=redis://localhost:6379
TESTDATA_TTL_HOURS=2

# Orchestrator Config
PROVIDER=openai
MODEL_NAME=gpt-4o-mini
INTAKE_MAX_MB=10
INTAKE_HTTP_TIMEOUT=15

# Optional Integrations
SNOWFLAKE_ACCOUNT=***
SNOWFLAKE_USER=***
SNOWFLAKE_PASSWORD=***
```

### Current Gating Logic (Pseudocode)
```typescript
// UI Gating (App.tsx:1506-1521)
function isRunDisabled(): boolean {
  const requiredFields = computeRequiredFields(selectedSuites, uploadedData, groundTruth);
  return requiredFields.length > 0 || !targetMode || !provider || !model;
}

// Backend Client Factory (client_factory.py:122)
function makeClient(request): BaseClient {
  if (request.target_mode === "api") {
    if (!request.server_url && !isPresetProvider(request.provider)) {
      throw "Server URL required for custom providers";
    }
    return new ApiClient(request.provider, request.model);
  } else if (request.target_mode === "mcp") {
    if (!request.mcp_endpoint) {
      throw "MCP endpoint required";
    }
    return new McpClient(request.provider, request.model, request.mcp_endpoint);
  }
}
```

---

## Next 48 Hours Plan

### Priority 1: Critical Alignment Issues
1. **Fix Server URL Logic** - Remove server URL requirement for OpenAI/Anthropic/Gemini presets in UI validation
2. **Centralize Requirements** - Create `/api/requirements` endpoint, consume in UI to eliminate validation mismatches
3. **Add JSONPath Validation** - Client-side syntax validation with preview for contexts_jsonpath

### Priority 2: User Experience  
4. **Real-time Tooltips** - Show "Missing passages for context metrics" immediately when metrics selected
5. **MCP Implementation** - Replace stub with basic MCP protocol client for real testing

### Priority 3: Quality Gates
6. **Coverage Threshold** - Set `--cov-fail-under=70` and add frontend test setup
7. **Integration Tests** - Add end-to-end tests for complete RAG runs with different GT modes
8. **Error Boundaries** - Better error handling for invalid JSONPath and missing test data scenarios

**Success Criteria**: Run button enabled only when truly required inputs present, no UI/backend validation conflicts, retrieval metrics work with valid JSONPath expressions.
