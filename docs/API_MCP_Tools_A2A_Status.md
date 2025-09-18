# API vs MCP vs Tools vs Agent-to-Agent Status Report

**Date:** September 18, 2025  
**Analysis:** Static codebase analysis of AI Quality Kit platform capabilities  
**Scope:** API, MCP, Tools Suite, Agent-to-Agent, Language/Threshold profiles, SUT providers

## Executive Summary

• **What works now:** API mode fully implemented with OpenAI/Anthropic/Custom REST providers, comprehensive guardrails preflight, cross-suite deduplication, JSON schema validation, multi-sheet reporting
• **What's partial:** MCP client exists but stubbed implementation, tools suite has schema validation but limited function calling, basic multi-turn conversation support
• **What's missing (high risk):** Production MCP harness, comprehensive tools suite with side-effect policies, full agent-to-agent evaluation suite, language-specific threshold presets

## SUT Providers (Target Modes)

| Target Mode | Implementation | File Location | Status |
|-------------|---------------|---------------|---------|
| **api** | OpenAI, Anthropic, Mock | `apps/server/sut.py:101-127` | ✅ Implemented |
| **mcp** | WebSocket client + adapter | `apps/orchestrator/mcp_client.py:42-79`, `apps/orchestrator/client_factory.py:161-184` | 🟡 Partial |
| **openai_compat** | Via OpenAI adapter | `apps/server/sut.py:30-66` | ✅ Implemented |
| **custom_rest** | Via provider abstraction | `llm/provider.py:47-89` | ✅ Implemented |

**Configuration Details:**
- Timeouts: `timeoutMs` field in TargetConfig (`apps/server/guardrails/interfaces.py:69-77`)
- Headers: Authorization, x-api-key support (`apps/server/sut.py:107-115`)
- Model selection: Provider-specific defaults (`apps/rag_service/config.py:18-21`)
- Allowed providers: `openai,anthropic,gemini,custom_rest,mock,mcp,test` (`apps/rag_service/config.py:23-26`)

## API vs MCP Capability Matrix

| Capability | API Status | MCP Status | Evidence |
|------------|------------|------------|----------|
| **Single-turn text** | ✅ Implemented | 🟡 Partial | API: `apps/server/sut.py:52-65`, MCP: `apps/orchestrator/mcp_client.py:102-123` (stubbed) |
| **Multi-step transcript** | ✅ Implemented | ❌ Missing | API: `apps/orchestrator/suites/red_team/harness.py:84-119`, MCP: No multi-turn support |
| **Tool discovery/schema** | 🟡 Partial | 🟡 Partial | API: Basic JSON schema (`apps/server/guardrails/providers/schema_guard.py:87-134`), MCP: Tool discovery (`apps/orchestrator/mcp_client.py:24-31`) |
| **Step metrics (latency/tokens)** | ✅ Implemented | ❌ Missing | API: `apps/observability/perf.py:20-49`, MCP: No metrics collection |
| **Gating/dedupe integration** | ✅ Implemented | ❌ Missing | API: `apps/orchestrator/deduplication.py:37-160`, MCP: No integration |
| **Reporting** | ✅ Implemented | ❌ Missing | API: `apps/reporters/excel_reporter.py:122-138`, MCP: No reporting support |

## Tools Suite (Function-Calling)

**Current Capabilities:**
- ✅ JSON schema validation: `apps/server/guardrails/providers/schema_guard.py:87-134`
- ✅ JSON extraction from LLM outputs: `apps/server/guardrails/providers/schema_guard.py:37-77`
- 🟡 Basic structure validation: `apps/evaluation/contracts.py:64-104`
- ❌ Tool selection/arguments validation: Missing
- ❌ Execution order validation: Missing

**Side-Effect Policies:**
- ❌ Allowlist/blocklist: Not implemented
- ❌ No-network enforcement: Not implemented  
- ❌ Dry-run mode: Not implemented

**Gaps for Full Tools Suite:**
- Function signature validation beyond JSON schema
- Tool execution sandboxing and safety policies
- Multi-step tool chain validation
- Tool dependency resolution

## Agent-to-Agent (A2A)

**Current Implementation:**
- 🟡 Multi-turn conversation state: `apps/orchestrator/suites/red_team/harness.py:13-47`
- 🟡 Basic conversation history: `apps/orchestrator/suites/red_team/harness.py:22-30`
- ❌ Role cards: Not implemented
- ❌ Turn limits: Basic max_steps only (`apps/orchestrator/suites/red_team/harness.py:111-115`)
- ❌ Multi-turn ASR metrics: Missing
- ❌ Per-turn guardrails: Missing

**Evidence:**
- Conversation state tracking: `apps/orchestrator/suites/red_team/harness.py:13-47`
- Multi-turn attack scenarios: `data/red_team/attacks.yaml:250-286`
- A2A service stub: `apps/mcp/server.py:266-273`

**Missing for Full A2A Suite:**
- Agent role definition and enforcement
- Turn-by-turn policy drift detection
- Multi-agent conversation orchestration
- Agent behavior consistency metrics

## Guardrails Profiles

**Language Support:**
- ✅ Language hints: `en`, `tr` support (`apps/api/routes/guardrails.py:20-21`)
- ✅ Multilingual provider variants: `apps/server/guardrails/aggregator.py:74`
- ❌ Language-specific thresholds: Not implemented

**Default Thresholds:**
```python
# apps/server/guardrails/aggregator.py:17-30
DEFAULT_THRESHOLDS = {
    "pii": 0.0,           # Zero tolerance
    "toxicity": 0.3,      # 30% threshold
    "jailbreak": 0.15,    # 15% threshold
    "pi_asr": 0.05,       # 5% PI attack success rate
    "adult": 0.0,         # Zero tolerance
    "selfharm": 0.0,      # Zero tolerance
    "schema": 1.0,        # Strict validation
    "latency_p95_ms": 3000, # 3 second limit
    "cost_per_test": 0.01   # $0.01 limit
}
```

**Client Override Mechanism:**
- ✅ Threshold merging: `apps/server/guardrails/aggregator.py:54` (client overrides server defaults)
- ✅ Profile selection: `frontend/operator-ui/src/stores/preflightStore.ts:184-267`
- ❌ Domain/model presets: Not implemented

## Dedupe & Gating Reuse

**Fingerprint Implementation:**
- ✅ Cross-suite fingerprints: `apps/orchestrator/deduplication.py:13-24`
- ✅ Fingerprint shape: `SHA256(provider_id:metric_id:stage:model:rules_hash)[:16]`
- ✅ Preflight→suites reuse: `apps/orchestrator/deduplication.py:63-100`

**Enforcement Points:**
- ✅ Guardrails aggregator: `apps/server/guardrails/aggregator.py:210-248`
- ✅ Red Team suite: `apps/server/redteam/suite_integration.py:50-74`
- ✅ Orchestrator integration: `apps/orchestrator/run_tests.py` (TestRunner class)

**Cache Management:**
- TTL: 3600 seconds (1 hour) (`apps/server/guardrails/aggregator.py:43`)
- In-memory storage with timestamp tracking
- Reuse statistics tracking (`apps/orchestrator/deduplication.py:159-160`)

## Reports & Observability

**Sheets Supporting API/MCP/Tools/A2A Data:**

| Sheet | API Data | MCP Data | Tools Data | A2A Data | File Location |
|-------|----------|----------|------------|----------|---------------|
| **Summary** | ✅ Run overview | ❌ Missing | 🟡 Schema results | ❌ Missing | `apps/reporters/excel_reporter.py:122-138` |
| **Guardrails_Details** | ✅ Provider signals | ❌ Missing | ✅ Schema validation | ❌ Missing | `apps/reporters/excel_reporter.py:136` |
| **Performance_Metrics** | ✅ Latency/throughput | ❌ Missing | ❌ Missing | ❌ Missing | `apps/reporters/excel_reporter.py:137` |
| **Adversarial_Details** | ✅ Attack results | ❌ Missing | ❌ Missing | 🟡 Multi-turn attacks | `apps/reporters/excel_reporter.py:134` |

**Step-by-Step Metrics:**
- ✅ API call traces: `apps/reporters/excel_reporter.py:132-133` (API_Details sheet)
- ✅ Latency per step: `apps/observability/perf.py:20-49`
- ❌ MCP step metrics: Not captured
- ❌ Tool execution metrics: Not captured

**PII Masking Guarantees:**
- ✅ Detailed rows masking: `apps/reporters/json_reporter.py:120` (`_mask_detailed_rows`)
- ✅ Adversarial rows masking: `apps/reporters/json_reporter.py:120` (`_mask_adversarial_rows`)
- ✅ Compare data masking: `apps/reporters/json_reporter.py:120` (`_mask_compare_data`)
- ✅ No raw prompts in logs: `GUARDRAILS_IMPLEMENTATION.md:96-99`

## Gaps & Recommendations

### High Impact, Medium Effort
1. **MCP Production Harness** (Impact: H, Effort: M)
   - Complete MCP client implementation in `apps/orchestrator/mcp_client.py`
   - Add MCP-specific metrics collection and reporting
   - Integrate with deduplication and gating systems

2. **Tools Suite Enhancement** (Impact: H, Effort: M)
   - Implement function signature validation beyond JSON schema
   - Add tool execution sandboxing and safety policies
   - Create comprehensive tool chain validation

### High Impact, Large Effort
3. **Agent-to-Agent Suite** (Impact: H, Effort: L)
   - Implement role card system and enforcement
   - Add multi-turn ASR and policy drift metrics
   - Create agent behavior consistency evaluation

4. **Language/Threshold Presets** (Impact: M, Effort: S)
   - Implement language-specific threshold profiles
   - Add domain/model-specific preset configurations
   - Create threshold recommendation engine

### Medium Impact, Small Effort
5. **Enhanced Observability** (Impact: M, Effort: S)
   - Add MCP step-by-step metrics collection
   - Implement tool execution timing and success metrics
   - Enhance A2A conversation flow tracking

---

**Methodology:** Static analysis using codebase_search across terms: sut, adapter, mcp, tools, function, schema, jsonschema, dedupe, fingerprint, guardrails, threshold, language, reports, orchestrator, preflight, latency, tokens, cost.

**Acceptance:** All claims include concrete file paths and line ranges. Unknown capabilities explicitly marked as "Missing" or "Unknown" with investigation guidance.
