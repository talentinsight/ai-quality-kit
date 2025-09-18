#!/usr/bin/env python3
"""
Demonstration script for MCP Production Harness.

This script shows how to use the MCP harness with multi-step agent runs,
tool discovery/invocation, step metrics, schema/policy guards, and 
integration with guardrails and reporting.
"""

import asyncio
import json
import logging
from typing import Dict, Any
from dataclasses import asdict

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class MockMCPClient:
    """Mock MCP client for demonstration purposes."""
    
    def __init__(self, endpoint: str):
        self.endpoint = endpoint
        self._connected = False
        self._tools = [
            {
                "name": "search_web",
                "description": "Search the web for information",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "max_results": {"type": "integer", "default": 5}
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "calculate",
                "description": "Perform mathematical calculations",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "expression": {"type": "string"}
                    },
                    "required": ["expression"]
                }
            },
            {
                "name": "get_weather",
                "description": "Get weather information",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "location": {"type": "string"}
                    },
                    "required": ["location"]
                }
            }
        ]
    
    async def connect(self):
        """Mock connection."""
        logger.info(f"🔌 Connecting to MCP server at {self.endpoint}")
        await asyncio.sleep(0.1)  # Simulate connection time
        self._connected = True
        logger.info("✅ Connected to MCP server")
    
    async def list_tools(self):
        """Mock tool discovery."""
        if not self._connected:
            raise Exception("Not connected to MCP server")
        
        logger.info(f"🔍 Discovering tools...")
        await asyncio.sleep(0.05)  # Simulate discovery time
        
        from apps.orchestrator.mcp_client import MCPTool
        tools = []
        for tool_data in self._tools:
            tools.append(MCPTool(
                name=tool_data["name"],
                description=tool_data["description"],
                input_schema=tool_data.get("inputSchema")
            ))
        
        logger.info(f"🛠️  Discovered {len(tools)} tools: {[t.name for t in tools]}")
        return tools
    
    async def call_tool(self, name: str, args: Dict[str, Any]):
        """Mock tool execution."""
        if not self._connected:
            raise Exception("Not connected to MCP server")
        
        logger.info(f"🔧 Calling tool '{name}' with args: {args}")
        await asyncio.sleep(0.2)  # Simulate tool execution time
        
        from apps.orchestrator.mcp_client import MCPResult
        
        # Mock responses based on tool
        if name == "search_web":
            query = args.get("query", "")
            return MCPResult(
                raw={"results": [f"Search result for: {query}"]},
                text=f"Found information about: {query}. The weather is sunny today."
            )
        elif name == "calculate":
            expression = args.get("expression", "")
            try:
                # Simple evaluation for demo (in production, use safe evaluation)
                result = eval(expression.replace("^", "**"))  # Basic math only
                return MCPResult(
                    raw={"result": result},
                    text=f"The result of {expression} is {result}"
                )
            except:
                return MCPResult(
                    raw={},
                    error=f"Cannot evaluate expression: {expression}"
                )
        elif name == "get_weather":
            location = args.get("location", "")
            return MCPResult(
                raw={"weather": {"location": location, "temperature": "22°C", "condition": "sunny"}},
                text=f"Weather in {location}: 22°C, sunny"
            )
        else:
            return MCPResult(
                raw={},
                error=f"Unknown tool: {name}"
            )
    
    async def close(self):
        """Mock connection close."""
        logger.info("🔌 Closing MCP connection")
        self._connected = False


async def demonstrate_mcp_harness():
    """Demonstrate MCP harness functionality."""
    print("=" * 80)
    print("🚀 MCP Production Harness Demonstration")
    print("=" * 80)
    
    try:
        # Import MCP harness components
        from apps.orchestrator.mcp_harness import MCPHarness, PolicyConfig
        from apps.orchestrator.deduplication import CrossSuiteDeduplicationService
        
        # Create mock MCP client
        mock_client = MockMCPClient("ws://localhost:8080/mcp")
        
        # Configure policy (restrictive for demo)
        policy_config = PolicyConfig(
            allowlist=["search_web", "calculate", "get_weather"],
            no_network=False,  # Allow network tools for demo
            dry_run=False,     # Actually execute tools
            max_steps=10
        )
        
        # Configure guardrails
        guardrails_config = {
            "mode": "mixed",
            "thresholds": {
                "toxicity": 0.3,
                "pii": 0.0,
                "jailbreak": 0.15
            }
        }
        
        # Create deduplication service
        dedup_service = CrossSuiteDeduplicationService("demo_run_123")
        
        # Create MCP harness
        harness = MCPHarness(
            mcp_client=mock_client,
            model="gpt-4",
            guardrails_config=guardrails_config,
            policy_config=policy_config,
            dedup_service=dedup_service
        )
        
        print(f"📋 Configuration:")
        print(f"   Model: gpt-4")
        print(f"   Policy: allowlist={policy_config.allowlist}, dry_run={policy_config.dry_run}")
        print(f"   Guardrails: {guardrails_config['mode']} mode")
        print()
        
        # Start session
        print("🎬 Starting MCP session...")
        session = await harness.start_session("demo_session_001")
        print(f"✅ Session started: {session.session_id}")
        print(f"🛠️  Tools available: {[t.name for t in session.tools_discovered]}")
        print()
        
        # Demonstrate multi-step conversation
        print("💬 Multi-step conversation demonstration:")
        print()
        
        # Step 1: User asks about weather
        print("👤 User: What's the weather like in San Francisco?")
        step1 = await harness.execute_step(
            session=session,
            role="user",
            input_text="What's the weather like in San Francisco?"
        )
        session.steps.append(step1)
        print(f"   ⏱️  Step 1: {step1.decision.value} ({step1.latency_ms:.1f}ms)")
        
        # Step 2: Assistant calls weather tool
        print("🤖 Assistant: I'll check the weather for you...")
        step2 = await harness.execute_step(
            session=session,
            role="assistant",
            input_text="I'll check the weather information",
            tool_name="get_weather",
            tool_args={"location": "San Francisco"}
        )
        session.steps.append(step2)
        print(f"   🔧 Tool call: get_weather(location='San Francisco')")
        print(f"   📤 Result: {step2.output_text}")
        print(f"   ⏱️  Step 2: {step2.decision.value} ({step2.latency_ms:.1f}ms, {step2.tokens_in}+{step2.tokens_out} tokens)")
        
        # Step 3: User asks for calculation
        print("👤 User: Can you calculate 15 * 23 + 7?")
        step3 = await harness.execute_step(
            session=session,
            role="user",
            input_text="Can you calculate 15 * 23 + 7?"
        )
        session.steps.append(step3)
        print(f"   ⏱️  Step 3: {step3.decision.value} ({step3.latency_ms:.1f}ms)")
        
        # Step 4: Assistant calls calculate tool
        print("🤖 Assistant: I'll calculate that for you...")
        step4 = await harness.execute_step(
            session=session,
            role="assistant",
            input_text="I'll perform the calculation",
            tool_name="calculate",
            tool_args={"expression": "15 * 23 + 7"}
        )
        session.steps.append(step4)
        print(f"   🔧 Tool call: calculate(expression='15 * 23 + 7')")
        print(f"   📤 Result: {step4.output_text}")
        print(f"   ⏱️  Step 4: {step4.decision.value} ({step4.latency_ms:.1f}ms, {step4.tokens_in}+{step4.tokens_out} tokens)")
        
        # Step 5: Demonstrate policy guard (blocked tool)
        print("🤖 Assistant: Let me try to use a blocked tool...")
        step5 = await harness.execute_step(
            session=session,
            role="assistant",
            input_text="I'll try to use a blocked tool",
            tool_name="blocked_tool",  # Not in allowlist
            tool_args={"param": "value"}
        )
        session.steps.append(step5)
        print(f"   🚫 Policy guard: {step5.error}")
        print(f"   ⏱️  Step 5: {step5.decision.value} ({step5.latency_ms:.1f}ms)")
        
        print()
        
        # Display session summary
        print("📊 Session Summary:")
        print(f"   Session ID: {session.session_id}")
        print(f"   Total steps: {len(session.steps)}")
        print(f"   Total latency: {session.total_latency_ms:.1f}ms")
        print(f"   Total tokens: {session.total_tokens_in} in + {session.total_tokens_out} out = {session.total_tokens_in + session.total_tokens_out}")
        print(f"   Estimated cost: ${session.total_cost_est:.4f}")
        print()
        
        # Show step decisions
        decisions = {}
        for step in session.steps:
            decision = step.decision.value
            decisions[decision] = decisions.get(decision, 0) + 1
        
        print("📈 Step Decisions:")
        for decision, count in decisions.items():
            print(f"   {decision}: {count}")
        print()
        
        # Demonstrate schema guard
        print("🛡️  Schema Guard Demonstration:")
        print("🤖 Assistant: Trying to call search_web without required 'query' parameter...")
        step_schema = await harness.execute_step(
            session=session,
            role="assistant",
            input_text="Invalid tool call",
            tool_name="search_web",
            tool_args={"max_results": 10}  # Missing required 'query'
        )
        print(f"   🚫 Schema guard: {step_schema.error}")
        print(f"   ⏱️  Schema check: {step_schema.decision.value} ({step_schema.latency_ms:.1f}ms)")
        print()
        
        # Generate report data
        print("📋 Generating Report Data...")
        session_dict = asdict(session)
        
        mcp_details = {
            "sessions": [session_dict],
            "summary": {
                "total_sessions": 1,
                "total_steps": len(session.steps),
                "total_latency_ms": session.total_latency_ms,
                "total_tokens_in": session.total_tokens_in,
                "total_tokens_out": session.total_tokens_out,
                "total_cost_est": session.total_cost_est,
                "tools_used": list(set(step.selected_tool for step in session.steps if step.selected_tool)),
                "decisions": decisions,
                "channels": {
                    "user_to_llm": sum(1 for step in session.steps if step.channel.value == "user_to_llm"),
                    "llm_to_tool": sum(1 for step in session.steps if step.channel.value == "llm_to_tool"),
                    "tool_to_llm": sum(1 for step in session.steps if step.channel.value == "tool_to_llm")
                }
            }
        }
        
        print("✅ Report data generated:")
        print(f"   Sessions: {mcp_details['summary']['total_sessions']}")
        print(f"   Steps: {mcp_details['summary']['total_steps']}")
        print(f"   Tools used: {mcp_details['summary']['tools_used']}")
        print()
        
        # Close session
        print("🔚 Closing session...")
        await harness.close_session(session)
        print("✅ Session closed successfully")
        print()
        
        print("=" * 80)
        print("🎉 MCP Production Harness demonstration completed!")
        print("=" * 80)
        print()
        print("Key features demonstrated:")
        print("✅ Multi-step session management")
        print("✅ Tool discovery and invocation")
        print("✅ Schema validation guards")
        print("✅ Policy enforcement guards")
        print("✅ Step-by-step metrics collection")
        print("✅ Privacy-aware logging (no raw payloads)")
        print("✅ Report data generation")
        print("✅ Graceful error handling")
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("💡 This is expected in environments without the full dependency stack.")
        print("   The MCP harness is designed to work with the complete AI Quality Kit platform.")
    except Exception as e:
        print(f"❌ Error during demonstration: {e}")
        logger.exception("Demonstration failed")


if __name__ == "__main__":
    print("🚀 Starting MCP Production Harness Demonstration...")
    print()
    asyncio.run(demonstrate_mcp_harness())
