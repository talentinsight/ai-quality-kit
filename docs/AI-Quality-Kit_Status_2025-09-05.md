# AI Quality Kit Status Report - 2025-09-05

## TL;DR

AI Quality Kit is a comprehensive LLM black-box testing platform for API/MCP targets with RAG, Safety, Red-team, Performance, and Bias evaluation suites. Current state: Core backend and UI operational with 78% test coverage, but missing production-ready features like rate limiting and comprehensive audit logging.

## Capabilities (What exists)

**Backend (FastAPI)**: Complete orchestrator at `apps/orchestrator/router.py` with synchronous/asynchronous test execution, multi-provider LLM abstraction (`llm/provider.py`) supporting OpenAI/Anthropic/Gemini/custom REST/synthetic providers. Test data intake system at `apps/testdata/router.py` with upload/URL/paste endpoints.

**UI (React/Vite)**: Operator interface at `frontend/operator-ui/src/ui/App.tsx` (2196 lines) with target mode selection (API/MCP), test suite configuration, and real-time results display. TestDataPanel integration for data management.

**Suites**: RAG evaluator (`apps/orchestrator/evaluators/rag_evaluator.py`), Safety (`safety_evaluator.py`), Red-team (`red_team_evaluator.py`), Performance (`performance_evaluator.py`), Bias (`bias_evaluator.py`), Resilience, and Compliance smoke tests with structured evaluation framework.

**Reporting**: JSON reporter (`apps/reporters/json_reporter.py`) and Excel reporter (`excel_reporter.py`) generating multi-sheet reports with Summary, Detailed, API_Details, Inputs_And_Expected, Adversarial_Details, Coverage, Resilience, Compliance, and Bias sheets.

## API Surface

**Core Endpoints** (`apps/rag_service/main.py`): POST `/ask` (RAG queries), GET `/healthz` (health), GET `/readyz` (readiness), GET `/config` (provider info).

**Orchestrator** (`apps/orchestrator/router.py`): POST `/orchestrator/run_tests` (sync execution), POST `/orchestrator/start` (async), GET `/orchestrator/report/{run_id}.json|xlsx` (downloads), POST `/orchestrator/cancel/{run_id}` (cancellation).

**Test Data** (`apps/testdata/router.py`): POST `/testdata/upload` (multipart), POST `/testdata/by_url` (URL fetch), POST `/testdata/paste` (direct content), GET `/testdata/{testdata_id}/meta` (metadata).

**Additional**: GET `/a2a/manifest`, POST `/a2a/act` (A2A service), GET `/mcp/tools`, POST `/mcp/call` (MCP integration).

## Suites Snapshot

**RAG Quality**: Faithfulness, context recall, answer relevancy, context precision (RAGAS integration at `apps/orchestrator/evaluators/ragas_adapter.py`). Ground truth evaluation with answer correctness/similarity. Retrieval metrics (recall@k, MRR@k, NDCG@k) present.

**Safety**: Toxicity detection, hate speech scanning via `apps/orchestrator/evaluators/safety_evaluator.py`. Pattern-based violation detection in `apps/observability/live_eval.py:112-149`.

**Red Team**: Prompt injection, jailbreak attempts, adversarial testing via `red_team_evaluator.py`. Attack success rate calculation and vulnerability scoring.

**Performance**: Latency (P50/P95), throughput testing via `performance_evaluator.py`. Cold/warm phase detection in `apps/observability/perf.py:20-49`.

**Bias**: Demographic parity analysis via `bias_evaluator.py`. Group comparison and fairness metrics.

**Resilience**: Circuit breaker, timeout, retry logic. Provider rate limiting simulation. Not found: Comprehensive chaos engineering tests.

## Reporting

**JSON Reports**: Version 2.0 structure with run metadata, summary statistics, detailed per-test results, API call traces, input/expected values. Adversarial details, coverage analysis, resilience metrics, compliance results, bias analysis sections present.

**Excel Reports**: Multi-sheet workbook with Summary (run overview), Detailed (per-test), API_Details (headers/traces), Inputs_And_Expected (test data), Adversarial_Details (red team), Coverage (code coverage), Resilience_Details, Compliance_Details, Bias_Details sheets. Structure sheets for prompt robustness analysis.

**Missing**: HTML reports, Power BI integration templates.

## Privacy/Security/Observability

**No-retention**: `PERSIST_DB=false` by default in `apps/observability/log_service.py:178-180`. In-memory processing with TTL.

**PII Masking**: Comprehensive redaction in `apps/utils/pii_redaction.py:1-76` for emails, phones, SSNs, credit cards, API keys, tokens.

**RBAC**: Role-based access control in `apps/security/auth.py:1-36` with Principal class, JWT support (HS256/RS256), token-role mapping.

**Observability**: Performance headers (X-Perf-Phase, X-Latency-MS) in `apps/observability/perf.py`. Audit logging framework with start/finish tracking. Rate limiting infrastructure in `apps/security/rate_limit.py`.

**Missing**: Comprehensive audit event logging, encryption at rest configuration.

## Gaps & Next Steps

**P0 - Test Coverage**: Currently 78%, target 80%. Core modules need systematic test expansion. Coverage tracking in `htmlcov/index.html`.

**P0 - Rate Limiting**: Infrastructure present (`apps/security/rate_limit.py`) but not fully implemented in production middleware.

**P0 - Production Audit**: Comprehensive audit logging beyond basic performance tracking needed.

**P1 - UI Integration**: TestDataPanel exists but workflow integration incomplete. Adapter mapping UI missing for API/MCP schema configuration.

**P1 - HTML Reports**: Excel/JSON complete, HTML generation missing for browser viewing.

**P2 - Percentile Metrics**: P50/P95 latency tracking infrastructure present, full implementation needed.

**P2 - Horizontal Scaling**: Single-instance deployment, multi-instance coordination not addressed.
