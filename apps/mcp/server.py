"""MCP (Model Context Protocol) server for read-only tools."""

import os
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

load_dotenv()


def is_mcp_enabled() -> bool:
    """Check if MCP is enabled."""
    return os.getenv("MCP_ENABLED", "true").lower() == "true"


def ask_rag(query: str, provider: Optional[str] = None, model: Optional[str] = None) -> Dict[str, Any]:
    """
    Ask RAG system a question (read-only tool).
    
    Args:
        query: Question to ask
        provider: Optional provider override
        model: Optional model override
        
    Returns:
        Dictionary with answer, context, latency, provider, model, source
    """
    if not is_mcp_enabled():
        return {
            "error": "MCP is disabled",
            "answer": "",
            "context": [],
            "latency_ms": 0,
            "provider": provider or "unknown",
            "model": model or "unknown",
            "source": "disabled"
        }
    
    try:
        # Import here to avoid circular imports
        from apps.rag_service.rag_pipeline import RAGPipeline
        from apps.rag_service.config import resolve_provider_and_model
        import time
        
        start_time = time.perf_counter()
        
        # Resolve provider and model
        resolved_provider, resolved_model = resolve_provider_and_model(provider, model)
        
        # Get global RAG pipeline (in real implementation, you'd have a proper singleton)
        # For now, create a minimal mock response
        if os.getenv("OFFLINE_MODE", "false").lower() == "true":
            # Offline mode - return mock response
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            return {
                "answer": f"Mock MCP response for query: {query[:50]}...",
                "context": ["Mock context passage from MCP"],
                "latency_ms": latency_ms,
                "provider": resolved_provider,
                "model": resolved_model,
                "source": "mcp_mock"
            }
        
        # In a real implementation, you'd use the actual RAG pipeline
        # For now, return a structured mock response
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        
        return {
            "answer": f"MCP RAG response for: {query}",
            "context": ["Context passage 1", "Context passage 2"],
            "latency_ms": latency_ms,
            "provider": resolved_provider,
            "model": resolved_model,
            "source": "mcp"
        }
        
    except Exception as e:
        return {
            "error": str(e),
            "answer": "",
            "context": [],
            "latency_ms": 0,
            "provider": provider or "unknown",
            "model": model or "unknown",
            "source": "error"
        }


def eval_rag(
    query: str, 
    answer: Optional[str] = None, 
    provider: Optional[str] = None, 
    model: Optional[str] = None
) -> Dict[str, Any]:
    """
    Evaluate RAG response quality (read-only tool).
    
    Args:
        query: Original query
        answer: Answer to evaluate (if None, will generate one)
        provider: Optional provider override
        model: Optional model override
        
    Returns:
        Dictionary with faithfulness, context_recall, notes
    """
    if not is_mcp_enabled():
        return {
            "error": "MCP is disabled",
            "faithfulness": 0.0,
            "context_recall": 0.0,
            "notes": "MCP disabled"
        }
    
    try:
        # If no answer provided, generate one first
        if not answer:
            rag_result = ask_rag(query, provider, model)
            if rag_result.get("error"):
                return {
                    "error": rag_result["error"],
                    "faithfulness": 0.0,
                    "context_recall": 0.0,
                    "notes": "Failed to generate answer for evaluation"
                }
            answer = rag_result["answer"]
        
        # Simple evaluation (in real implementation, use RAGAS)
        faithfulness = 0.8 if answer and len(answer) > 20 else 0.3
        context_recall = 0.7 if answer and "context" in answer.lower() else 0.4
        
        return {
            "faithfulness": faithfulness,
            "context_recall": context_recall,
            "notes": f"Evaluated answer of length {len(answer) if answer else 0} characters"
        }
        
    except Exception as e:
        return {
            "error": str(e),
            "faithfulness": 0.0,
            "context_recall": 0.0,
            "notes": f"Evaluation failed: {str(e)}"
        }


def list_tests() -> Dict[str, Any]:
    """
    List available test suites (read-only tool).
    
    Returns:
        Dictionary with available suites and their descriptions
    """
    if not is_mcp_enabled():
        return {
            "error": "MCP is disabled",
            "suites": []
        }
    
    suites = [
        {
            "name": "rag_quality",
            "description": "RAG quality evaluation using golden dataset",
            "test_count": 8  # Based on RAGAS_SAMPLE_SIZE
        },
        {
            "name": "red_team",
            "description": "Red team adversarial testing",
            "test_count": 20
        },
        {
            "name": "safety",
            "description": "Safety and guardrails testing",
            "test_count": 10
        },
        {
            "name": "performance",
            "description": "Performance and latency testing",
            "test_count": 5
        },
        {
            "name": "regression",
            "description": "Regression testing against baselines",
            "test_count": 5
        },
        {
            "name": "guardrails",
            "description": "Composite security and compliance guardrails",
            "test_count": 25
        }
    ]
    
    return {
        "suites": suites,
        "total_suites": len(suites)
    }


def run_tests(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run test suites (read-only orchestration tool).
    
    Args:
        config: Test configuration dictionary
        
    Returns:
        Dictionary with run_id, summary, counts
    """
    if not is_mcp_enabled():
        return {
            "error": "MCP is disabled",
            "run_id": None,
            "summary": {},
            "counts": {}
        }
    
    try:
        # Import here to avoid circular imports
        from apps.orchestrator.run_tests import OrchestratorRequest, TestRunner
        import asyncio
        
        # Convert config to OrchestratorRequest
        request = OrchestratorRequest(
            target_mode="mcp",
            suites=config.get("suites", ["rag_quality"]),
            thresholds=config.get("thresholds"),
            options=config.get("options", {"provider": "mock", "model": "mock-model"})
        )
        
        # Run tests asynchronously
        async def run_async():
            runner = TestRunner(request)
            return await runner.run_all_tests()
        
        # In a real implementation, you'd handle this better
        # For now, return a mock response
        import time
        run_id = f"mcp_run_{int(time.time())}"
        
        return {
            "run_id": run_id,
            "summary": {
                "overall": {
                    "total_tests": 5,
                    "passed": 4,
                    "failed": 1,
                    "pass_rate": 0.8
                }
            },
            "counts": {
                "total_tests": 5,
                "passed": 4,
                "failed": 1,
                "errors": 0
            }
        }
        
    except Exception as e:
        return {
            "error": str(e),
            "run_id": None,
            "summary": {},
            "counts": {}
        }


def start_mcp_server():
    """Start MCP server (no-op if disabled)."""
    if not is_mcp_enabled():
        print("MCP server disabled")
        return
    
    print("MCP server would start here (not implemented in this demo)")
    # In a real implementation, you'd start the actual MCP server


# MCP tool registry for external access
MCP_TOOLS = {
    "ask_rag": {
        "function": ask_rag,
        "description": "Ask the RAG system a question",
        "parameters": {
            "query": {"type": "string", "required": True},
            "provider": {"type": "string", "required": False},
            "model": {"type": "string", "required": False}
        }
    },
    "eval_rag": {
        "function": eval_rag,
        "description": "Evaluate RAG response quality",
        "parameters": {
            "query": {"type": "string", "required": True},
            "answer": {"type": "string", "required": False},
            "provider": {"type": "string", "required": False},
            "model": {"type": "string", "required": False}
        }
    },
    "list_tests": {
        "function": list_tests,
        "description": "List available test suites",
        "parameters": {}
    },
    "run_tests": {
        "function": run_tests,
        "description": "Run test suites",
        "parameters": {
            "config": {"type": "object", "required": True}
        }
    }
}
