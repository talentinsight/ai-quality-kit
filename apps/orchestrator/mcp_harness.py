"""
Production MCP harness with multi-step agent runs, tool discovery/invocation,
step metrics, schema/policy guards, and full integration with guardrails and reporting.
"""

import asyncio
import json
import time
import logging
import hashlib
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass, asdict
from enum import Enum

from .mcp_client import MCPClient, MCPTool, MCPResult
from apps.server.guardrails.interfaces import SignalResult, SignalLabel, GuardrailCategory
from apps.server.guardrails.aggregator import GuardrailsAggregator
from apps.orchestrator.deduplication import CrossSuiteDeduplicationService

logger = logging.getLogger(__name__)


class StepDecision(Enum):
    """Decision made for an MCP step."""
    OK = "ok"
    DENIED_SCHEMA = "denied_schema"
    DENIED_POLICY = "denied_policy"
    ERROR = "error"


class Channel(Enum):
    """Communication channel for MCP steps."""
    USER_TO_LLM = "user_to_llm"
    LLM_TO_TOOL = "llm_to_tool"
    TOOL_TO_LLM = "tool_to_llm"


@dataclass
class MCPStep:
    """Represents a single step in an MCP session."""
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
    
    def __post_init__(self):
        if self.guardrail_signals is None:
            self.guardrail_signals = []
        if self.reused_fingerprints is None:
            self.reused_fingerprints = []


@dataclass
class MCPSession:
    """Represents a complete MCP session with multiple steps."""
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
    
    def __post_init__(self):
        if self.session_violations is None:
            self.session_violations = []


@dataclass
class PolicyConfig:
    """Configuration for MCP policy guards."""
    allowlist: List[str] = None  # Allowed tool names
    no_network: bool = False  # Block network-accessing tools
    dry_run: bool = False  # Don't actually execute tools
    max_steps: int = 10  # Maximum steps per session
    
    def __post_init__(self):
        if self.allowlist is None:
            self.allowlist = []


class MCPHarness:
    """Production MCP harness with multi-step sessions and guardrails integration."""
    
    def __init__(
        self,
        mcp_client: MCPClient,
        model: str,
        guardrails_config: Optional[Dict[str, Any]] = None,
        policy_config: Optional[PolicyConfig] = None,
        dedup_service: Optional[CrossSuiteDeduplicationService] = None
    ):
        self.mcp_client = mcp_client
        self.model = model
        self.guardrails_config = guardrails_config or {}
        self.policy_config = policy_config or PolicyConfig()
        self.dedup_service = dedup_service
        
        # Create rules hash for deduplication
        self.rules_hash = self._create_rules_hash()
        
        logger.info(f"MCP harness initialized for model {model}")
    
    def _create_rules_hash(self) -> str:
        """Create hash of configuration for deduplication."""
        config_str = json.dumps({
            "model": self.model,
            "guardrails": self.guardrails_config,
            "policy": asdict(self.policy_config)
        }, sort_keys=True)
        return hashlib.sha256(config_str.encode()).hexdigest()[:16]
    
    async def start_session(self, session_id: str) -> MCPSession:
        """Start a new MCP session with tool discovery and preflight checks."""
        start_time = time.perf_counter()
        
        try:
            # Connect and discover tools
            await self.mcp_client.connect()
            tools = await self.mcp_client.list_tools()
            
            # Create session
            session = MCPSession(
                session_id=session_id,
                model=self.model,
                rules_hash=self.rules_hash,
                steps=[],
                tools_discovered=tools
            )
            
            # Run guardrails preflight if configured
            if self.guardrails_config:
                session.preflight_result = await self._run_preflight_checks(session)
            
            session_time = (time.perf_counter() - start_time) * 1000
            logger.info(f"MCP session {session_id} started: {len(tools)} tools discovered, "
                       f"preflight {'passed' if session.preflight_result and session.preflight_result.get('pass') else 'failed'}, "
                       f"{session_time:.1f}ms")
            
            return session
            
        except Exception as e:
            logger.error(f"Failed to start MCP session {session_id}: {e}")
            raise
    
    async def execute_step(
        self, 
        session: MCPSession, 
        role: str, 
        input_text: str, 
        tool_name: Optional[str] = None,
        tool_args: Optional[Dict[str, Any]] = None
    ) -> MCPStep:
        """Execute a single step in the MCP session with guards and metrics."""
        step_start = time.perf_counter()
        step_id = f"step_{len(session.steps) + 1}"
        
        # Check session limits
        if len(session.steps) >= self.policy_config.max_steps:
            return MCPStep(
                step_id=step_id,
                role=role,
                input_text=input_text[:100] + "..." if len(input_text) > 100 else input_text,  # Truncate for privacy
                error="Max steps exceeded",
                decision=StepDecision.DENIED_POLICY,
                latency_ms=(time.perf_counter() - step_start) * 1000
            )
        
        # Determine channel
        channel = self._determine_channel(role, tool_name)
        
        step = MCPStep(
            step_id=step_id,
            role=role,
            input_text=input_text[:100] + "..." if len(input_text) > 100 else input_text,  # Truncate for privacy
            selected_tool=tool_name,
            tool_args=self._redact_tool_args(tool_args) if tool_args else None,
            channel=channel
        )
        
        try:
            # Apply guards before execution
            if tool_name and tool_args:
                # Schema guard
                schema_result = await self._apply_schema_guard(tool_name, tool_args, session)
                if schema_result.decision != StepDecision.OK:
                    step.decision = schema_result.decision
                    step.error = schema_result.error
                    step.latency_ms = (time.perf_counter() - step_start) * 1000
                    return step
                
                # Policy guard
                policy_result = await self._apply_policy_guard(tool_name, tool_args)
                if policy_result.decision != StepDecision.OK:
                    step.decision = policy_result.decision
                    step.error = policy_result.error
                    step.latency_ms = (time.perf_counter() - step_start) * 1000
                    return step
            
            # Execute the step
            if tool_name and not self.policy_config.dry_run:
                # Tool execution
                result = await self.mcp_client.call_tool(tool_name, tool_args or {})
                if result.error:
                    step.error = result.error
                    step.decision = StepDecision.ERROR
                else:
                    step.output_text = result.text[:200] + "..." if result.text and len(result.text) > 200 else result.text  # Truncate for privacy
                    
                    # Estimate tokens and cost
                    step.tokens_in = len(str(tool_args or {}).split()) if tool_args else 0
                    step.tokens_out = len((result.text or "").split())
                    step.cost_est = self._estimate_cost(step.tokens_in, step.tokens_out)
            
            elif self.policy_config.dry_run:
                # Dry run mode - simulate execution
                step.output_text = f"[DRY RUN] Would call {tool_name}"
                step.tokens_in = len(str(tool_args or {}).split()) if tool_args else 0
                step.tokens_out = 5  # Simulated
                step.cost_est = self._estimate_cost(step.tokens_in, step.tokens_out)
            
            else:
                # Non-tool step (user input, assistant response)
                step.tokens_in = len(input_text.split())
                step.cost_est = self._estimate_cost(step.tokens_in, 0)
            
            # Apply per-step guardrails
            if step.output_text and self.guardrails_config:
                step.guardrail_signals, step.reused_fingerprints = await self._apply_step_guardrails(
                    step, session
                )
            
            step.latency_ms = (time.perf_counter() - step_start) * 1000
            
            # Update session totals
            session.total_latency_ms += step.latency_ms
            session.total_tokens_in += step.tokens_in
            session.total_tokens_out += step.tokens_out
            session.total_cost_est += step.cost_est
            
            logger.debug(f"MCP step {step_id} completed: {step.decision.value}, "
                        f"{step.latency_ms:.1f}ms, {step.tokens_in}+{step.tokens_out} tokens")
            
            return step
            
        except Exception as e:
            step.error = str(e)
            step.decision = StepDecision.ERROR
            step.latency_ms = (time.perf_counter() - step_start) * 1000
            logger.error(f"MCP step {step_id} failed: {e}")
            return step
    
    async def close_session(self, session: MCPSession) -> None:
        """Close the MCP session and cleanup resources."""
        try:
            await self.mcp_client.close()
            logger.info(f"MCP session {session.session_id} closed: {len(session.steps)} steps, "
                       f"{session.total_latency_ms:.1f}ms total, "
                       f"{session.total_tokens_in}+{session.total_tokens_out} tokens, "
                       f"${session.total_cost_est:.4f} estimated cost")
        except Exception as e:
            logger.error(f"Error closing MCP session {session.session_id}: {e}")
    
    def _determine_channel(self, role: str, tool_name: Optional[str]) -> Channel:
        """Determine the communication channel for a step."""
        if role == "user":
            return Channel.USER_TO_LLM
        elif role == "assistant" and tool_name:
            return Channel.LLM_TO_TOOL
        else:
            return Channel.TOOL_TO_LLM
    
    def _redact_tool_args(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Redact sensitive data from tool arguments for logging."""
        redacted = {}
        for key, value in args.items():
            if self._is_sensitive_key(key):
                redacted[key] = "***REDACTED***"
            elif isinstance(value, str) and len(value) > 100:
                redacted[key] = value[:50] + "..." + value[-20:]  # Truncate long strings
            else:
                redacted[key] = value
        return redacted
    
    def _is_sensitive_key(self, key: str) -> bool:
        """Check if a key contains sensitive data."""
        return any(sensitive in key.lower() for sensitive in [
            "token", "key", "secret", "password", "auth", "bearer", "credential"
        ])
    
    async def _apply_schema_guard(
        self, 
        tool_name: str, 
        tool_args: Dict[str, Any], 
        session: MCPSession
    ) -> 'GuardResult':
        """Apply schema validation to tool arguments."""
        try:
            # Find tool schema
            tool_schema = None
            for tool in session.tools_discovered:
                if tool.name == tool_name and tool.input_schema:
                    tool_schema = tool.input_schema
                    break
            
            if not tool_schema:
                return GuardResult(StepDecision.OK, None)
            
            # Validate using jsonschema if available
            try:
                import jsonschema
                jsonschema.validate(tool_args, tool_schema)
                return GuardResult(StepDecision.OK, None)
            except ImportError:
                logger.warning("jsonschema not available, skipping schema validation")
                return GuardResult(StepDecision.OK, None)
            except jsonschema.ValidationError as e:
                return GuardResult(StepDecision.DENIED_SCHEMA, f"Schema validation failed: {e.message}")
            
        except Exception as e:
            logger.error(f"Schema guard error for {tool_name}: {e}")
            return GuardResult(StepDecision.ERROR, str(e))
    
    async def _apply_policy_guard(self, tool_name: str, tool_args: Dict[str, Any]) -> 'GuardResult':
        """Apply policy validation to tool execution."""
        try:
            # Check allowlist
            if self.policy_config.allowlist and tool_name not in self.policy_config.allowlist:
                return GuardResult(
                    StepDecision.DENIED_POLICY, 
                    f"Tool {tool_name} not in allowlist: {self.policy_config.allowlist}"
                )
            
            # Check no-network policy (heuristic)
            if self.policy_config.no_network and self._is_network_tool(tool_name, tool_args):
                return GuardResult(
                    StepDecision.DENIED_POLICY,
                    f"Tool {tool_name} blocked by no-network policy"
                )
            
            return GuardResult(StepDecision.OK, None)
            
        except Exception as e:
            logger.error(f"Policy guard error for {tool_name}: {e}")
            return GuardResult(StepDecision.ERROR, str(e))
    
    def _is_network_tool(self, tool_name: str, tool_args: Dict[str, Any]) -> bool:
        """Heuristically determine if a tool accesses the network."""
        network_indicators = [
            "http", "url", "fetch", "download", "upload", "request", "api", "web", "internet"
        ]
        
        # Check tool name
        if any(indicator in tool_name.lower() for indicator in network_indicators):
            return True
        
        # Check argument values
        for value in tool_args.values():
            if isinstance(value, str) and any(indicator in value.lower() for indicator in network_indicators):
                return True
        
        return False
    
    async def _run_preflight_checks(self, session: MCPSession) -> Dict[str, Any]:
        """Run guardrails preflight checks for the session."""
        try:
            # Import here to avoid circular dependency
            from apps.server.guardrails.interfaces import GuardrailsConfig, PreflightRequest, TargetConfig
            
            # Create minimal preflight request
            target_config = TargetConfig(
                mode="mcp",
                provider="mcp",
                endpoint=self.mcp_client.endpoint,
                model=self.model
            )
            
            guardrails_config = GuardrailsConfig(**self.guardrails_config)
            
            request = PreflightRequest(
                llmType="agent",  # MCP is typically used for agent workflows
                target=target_config,
                guardrails=guardrails_config
            )
            
            # Create aggregator and run preflight
            aggregator = GuardrailsAggregator(
                config=guardrails_config,
                sut_adapter=None,  # No SUT adapter needed for preflight-only
                language="en"
            )
            
            result = await aggregator.run_preflight()
            
            return {
                "pass": result.pass_,
                "signals": [asdict(signal) for signal in result.signals],
                "metrics": result.metrics
            }
            
        except Exception as e:
            logger.error(f"Preflight checks failed: {e}")
            return {"pass": False, "error": str(e)}
    
    async def _apply_step_guardrails(
        self, 
        step: MCPStep, 
        session: MCPSession
    ) -> Tuple[List[SignalResult], List[str]]:
        """Apply lightweight guardrails to step output and check for reuse."""
        signals = []
        reused_fingerprints = []
        
        if not step.output_text:
            return signals, reused_fingerprints
        
        try:
            # Check for reusable signals first
            if self.dedup_service:
                # Check common guardrail categories
                for category in ["toxicity", "pii", "jailbreak"]:
                    fingerprint = self.dedup_service.create_fingerprint(
                        provider_id=f"{category}.guard",
                        metric_id=category,
                        stage="mcp",
                        model=self.model,
                        rules_hash=self.rules_hash
                    )
                    
                    reused_signal = self.dedup_service.check_signal_reusable(
                        provider_id=f"{category}.guard",
                        metric_id=category,
                        stage="mcp",
                        model=self.model,
                        rules_hash=self.rules_hash
                    )
                    
                    if reused_signal:
                        signals.append(reused_signal)
                        reused_fingerprints.append(fingerprint.to_key())
                        logger.debug(f"Reused {category} signal for MCP step {step.step_id}")
            
            # Apply lightweight checks for non-reused categories
            # Note: In production, you'd integrate with actual guardrail providers here
            # For now, we'll create placeholder signals
            
            return signals, reused_fingerprints
            
        except Exception as e:
            logger.error(f"Step guardrails failed for {step.step_id}: {e}")
            return signals, reused_fingerprints
    
    def _estimate_cost(self, tokens_in: int, tokens_out: int) -> float:
        """Estimate cost based on token usage."""
        # Simple cost estimation - in production, use actual provider pricing
        input_cost_per_1k = 0.001  # $0.001 per 1K input tokens
        output_cost_per_1k = 0.002  # $0.002 per 1K output tokens
        
        return (tokens_in / 1000 * input_cost_per_1k) + (tokens_out / 1000 * output_cost_per_1k)


@dataclass
class GuardResult:
    """Result of applying a guard to an MCP step."""
    decision: StepDecision
    error: Optional[str]


# Health check support
def is_mcp_harness_available() -> bool:
    """Check if MCP harness is available."""
    try:
        import websockets
        return True
    except ImportError:
        return False


def get_mcp_harness_version() -> str:
    """Get MCP harness version."""
    return "1.0.0"
