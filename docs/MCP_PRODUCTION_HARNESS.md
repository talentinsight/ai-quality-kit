# MCP Production Harness Implementation

**Date:** September 18, 2025  
**Implementation:** MCP Production Harness with multi-step agent runs, tool discovery/invocation, step metrics, schema/policy guards, and full integration with guardrails and reporting.

## Executive Summary

Successfully implemented a comprehensive MCP (Model Context Protocol) production harness that transforms the existing MCP adapter into a full-featured system supporting:

- ✅ **Multi-step agent sessions** with stable lifecycle management
- ✅ **Tool discovery and invocation** with schema/policy guards
- ✅ **Step-by-step metrics collection** (latency/tokens/cost)
- ✅ **Guardrails integration** with preflight checks and per-step validation
- ✅ **Cross-suite deduplication** with fingerprint-based reuse
- ✅ **Reports v2 integration** with MCP step traces and performance metrics
- ✅ **Privacy-first design** with no raw payload logging
- ✅ **Comprehensive test coverage** with deterministic behavior

## Architecture Overview

### Core Components

1. **MCPHarness** (`apps/orchestrator/mcp_harness.py`)
   - Main orchestrator for MCP sessions
   - Integrates with guardrails, deduplication, and policy enforcement
   - Manages session lifecycle and step execution

2. **MCPSession & MCPStep** (Data Models)
   - `MCPSession`: Complete session with multiple steps and metrics
   - `MCPStep`: Individual step with role, tool, metrics, and guardrails data
   - Serializable for reporting and persistence

3. **PolicyConfig** (Configuration)
   - Tool allowlist/blocklist management
   - No-network enforcement
   - Dry-run mode support
   - Step limits and safety controls

4. **Guard Systems**
   - **Schema Guard**: JSON schema validation for tool arguments
   - **Policy Guard**: Allowlist, no-network, and side-effect policies
   - **Guardrails Integration**: Preflight and per-step safety checks

## Key Features

### A) MCP Client & Session Management

```python
# Stable lifecycle with tool discovery
session = await harness.start_session("session_id")
# Multi-step transcript with metrics
step = await harness.execute_step(session, role, input_text, tool_name, tool_args)
# Graceful cleanup
await harness.close_session(session)
```

**Features:**
- WebSocket connection management with retries
- Tool discovery and caching
- Session-level preflight guardrails checks
- Deterministic configuration hashing for reproducibility

### B) Tool Invocation & Guards

**Schema Guard:**
- Validates tool arguments against JSON schema
- Returns `DENIED_SCHEMA` decision on validation failure
- Supports optional schemas (graceful degradation)

**Policy Guard:**
- Allowlist enforcement (`allowlist: ["tool1", "tool2"]`)
- No-network policy (heuristic detection of network tools)
- Dry-run mode (simulates execution without actual calls)
- Step limits (prevents runaway sessions)

**Decision Flow:**
```
Input → Schema Guard → Policy Guard → Tool Execution → Guardrails → Output
```

### C) Guardrails Integration

**Preflight Checks:**
- Run at session start using existing guardrails aggregator
- Enforces configured mode (hard_gate/mixed/advisory)
- Results stored in session for reporting

**Per-Step Checks:**
- Lightweight guardrails on tool outputs
- Reuse signals from preflight when possible
- Track violations and reused fingerprints

### D) Cross-Suite Deduplication

**Fingerprint Generation:**
```python
fingerprint = SHA256(provider_id:metric_id:stage="mcp":model:rules_hash)[:16]
```

**Reuse Logic:**
- Check for existing signals before computation
- Mark reused signals with "Reused from Preflight" 
- Exclude reused items from cost/time estimators

### E) Reports v2 Integration

**JSON Reporter Extensions:**
- New `mcp_details` section with session data
- PII masking for input/output text and tool arguments
- Session-level and step-level metrics

**Excel Reporter Extensions:**
- New `MCP_Details` sheet with step-by-step traces
- Columns: Session ID, Step ID, Role, Channel, Tool Name, Decision, Metrics, Violations, Reused Fingerprints
- Privacy-aware display (truncated sensitive fields)

**Report Structure:**
```json
{
  "mcp_details": {
    "sessions": [
      {
        "session_id": "session_123",
        "model": "gpt-4",
        "steps": [
          {
            "step_id": "step_1",
            "role": "assistant",
            "channel": "llm_to_tool",
            "selected_tool": "search_web",
            "decision": "ok",
            "latency_ms": 150.5,
            "tokens_in": 10,
            "tokens_out": 20,
            "cost_est": 0.001,
            "guardrail_signals": [...],
            "reused_fingerprints": ["fp_abc123"]
          }
        ],
        "total_latency_ms": 380.0,
        "total_cost_est": 0.007
      }
    ],
    "summary": {
      "total_sessions": 1,
      "total_steps": 4,
      "tools_used": ["search_web", "calculate"],
      "decisions": {"ok": 3, "denied_policy": 1}
    }
  }
}
```

### F) Observability & Health

**Health Checks:**
- Extended `/guardrails/health` endpoint with MCP harness status
- Dependency checking (websockets library)
- Version reporting

**Logging:**
- No raw payloads in logs (privacy-first)
- Structured logging with step IDs and metrics
- Sensitive data redaction for tool arguments

**Metrics Collection:**
- Per-step latency, tokens, and cost estimation
- Session-level aggregations
- Channel distribution (user→LLM, LLM→tool, tool→LLM)
- Decision distribution (OK, denied_schema, denied_policy, error)

## Implementation Files

### Core Implementation
- `apps/orchestrator/mcp_harness.py` - Main harness implementation (383 lines)
- `apps/server/guardrails/health.py` - Extended health checks (28 lines added)

### Reporting Integration
- `apps/reporters/json_reporter.py` - JSON report extensions (40 lines added)
- `apps/reporters/excel_reporter.py` - Excel report extensions (72 lines added)

### Testing & Documentation
- `tests/test_mcp_harness.py` - Comprehensive unit tests (650+ lines)
- `tests/test_mcp_orchestrator_integration.py` - Integration tests (500+ lines)
- `scripts/demo_mcp_harness.py` - Demonstration script (300+ lines)

### Data Structures

**MCPStep:**
```python
@dataclass
class MCPStep:
    step_id: str
    role: str  # "user", "assistant", "tool"
    input_text: str
    selected_tool: Optional[str] = None
    tool_args: Optional[Dict[str, Any]] = None
    output_text: Optional[str] = None
    error: Optional[str] = None
    decision: StepDecision = StepDecision.OK
    channel: Channel = Channel.USER_TO_LLM
    
    # Metrics
    latency_ms: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    cost_est: float = 0.0
    
    # Guardrails
    guardrail_signals: List[SignalResult] = None
    reused_fingerprints: List[str] = None
```

**MCPSession:**
```python
@dataclass
class MCPSession:
    session_id: str
    model: str
    rules_hash: str
    steps: List[MCPStep]
    tools_discovered: List[MCPTool]
    
    # Session-level metrics
    total_latency_ms: float = 0.0
    total_tokens_in: int = 0
    total_tokens_out: int = 0
    total_cost_est: float = 0.0
    
    # Guardrails
    preflight_result: Optional[Any] = None
    session_violations: List[SignalResult] = None
```

## Usage Examples

### Basic Session
```python
from apps.orchestrator.mcp_harness import MCPHarness, PolicyConfig
from apps.orchestrator.mcp_client import MCPClient

# Create client and harness
client = MCPClient("ws://localhost:8080/mcp")
harness = MCPHarness(client, model="gpt-4")

# Run session
session = await harness.start_session("demo_session")
step = await harness.execute_step(
    session, "assistant", "Search for weather", 
    tool_name="search_web", tool_args={"query": "weather"}
)
await harness.close_session(session)
```

### With Policy Guards
```python
policy = PolicyConfig(
    allowlist=["search_web", "calculate"],
    no_network=True,
    dry_run=False,
    max_steps=10
)

harness = MCPHarness(client, model="gpt-4", policy_config=policy)
```

### With Guardrails
```python
guardrails_config = {
    "mode": "mixed",
    "thresholds": {"toxicity": 0.3, "pii": 0.0}
}

harness = MCPHarness(
    client, model="gpt-4", 
    guardrails_config=guardrails_config
)
```

## Testing Strategy

### Unit Tests (`test_mcp_harness.py`)
- ✅ Session lifecycle (start/execute/close)
- ✅ Tool execution with success/failure scenarios
- ✅ Schema guard validation (pass/fail cases)
- ✅ Policy guard enforcement (allowlist, no-network, dry-run)
- ✅ Step limits and error handling
- ✅ Guardrails integration and signal reuse
- ✅ Privacy functions (redaction, sensitive key detection)
- ✅ Cost estimation and metrics calculation
- ✅ Health check functions

### Integration Tests (`test_mcp_orchestrator_integration.py`)
- ✅ Deduplication service integration
- ✅ Report generation (JSON/Excel with MCP data)
- ✅ PII masking in reports
- ✅ Multi-step conversation scenarios
- ✅ Error handling and recovery
- ✅ Performance metrics aggregation
- ✅ Guardrails enforcement scenarios

### Demonstration (`demo_mcp_harness.py`)
- ✅ Complete workflow demonstration
- ✅ Multi-step conversation with tool calls
- ✅ Policy and schema guard demonstrations
- ✅ Metrics collection and reporting
- ✅ Error scenarios and handling

## Privacy & Security

### Privacy Guarantees
- **No raw payloads in logs** - Only metrics and IDs logged
- **Text truncation** - Input/output text limited to 100-200 chars in storage
- **Sensitive data redaction** - API keys, tokens, passwords masked
- **PII masking in reports** - Email, phone, SSN automatically redacted

### Security Features
- **Tool allowlisting** - Restrict available tools per session
- **No-network enforcement** - Block network-accessing tools
- **Schema validation** - Prevent malformed tool arguments
- **Step limits** - Prevent runaway sessions
- **Dry-run mode** - Test without actual execution

## Performance Characteristics

### Metrics Collected
- **Latency**: Per-step and session-level timing
- **Tokens**: Input/output token counts with cost estimation
- **Tool Usage**: Which tools called, success/failure rates
- **Guard Decisions**: Schema/policy violations tracked
- **Reuse Efficiency**: Deduplication savings measured

### Scalability Features
- **Lazy imports** - Minimize memory footprint
- **In-memory sessions** - No persistent storage required
- **Configurable limits** - Max steps, timeouts, retries
- **Graceful degradation** - Continue on non-critical failures

## Acceptance Criteria ✅

1. **✅ MCP runs support multi-step with tools** - MCPHarness manages complete sessions with tool discovery and invocation
2. **✅ Schema/policy guards enforce decisions** - Guards block invalid calls with appropriate error messages
3. **✅ Per-step metrics recorded** - Latency, tokens, cost tracked for every step
4. **✅ Guardrails gating applied** - Preflight checks and per-step validation integrated
5. **✅ Dedupe active between Preflight and MCP** - Cross-suite fingerprinting and reuse implemented
6. **✅ Reports v2 include MCP step traces** - JSON/Excel reports extended with MCP_Details sheet
7. **✅ All tests pass** - Comprehensive test suite with 100+ test cases
8. **✅ Behavior deterministic** - Same config produces identical results
9. **✅ No raw user text in logs** - Privacy-first logging with redaction

## Future Enhancements

### Potential Improvements
- **Real-time streaming** - Support for streaming tool responses
- **Tool chaining** - Automatic tool dependency resolution
- **Advanced policies** - More sophisticated side-effect detection
- **Performance optimization** - Connection pooling, caching strategies
- **Monitoring integration** - Prometheus metrics, distributed tracing

### Integration Opportunities
- **Agent frameworks** - Integration with LangChain, AutoGPT
- **Workflow engines** - Support for complex multi-agent workflows
- **External tool registries** - Dynamic tool discovery from external sources

---

**Status:** ✅ **COMPLETED**  
**All acceptance criteria met with comprehensive implementation, testing, and documentation.**
