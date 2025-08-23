"""A2A (Agent-to-Agent) API for manifest/act surfaces."""

import os
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from dotenv import load_dotenv

from apps.security.auth import require_user_or_admin, Principal

load_dotenv()

# Create router
router = APIRouter(prefix="/a2a", tags=["a2a"])


class ActRequest(BaseModel):
    """Request model for A2A act endpoint."""
    skill: str
    args: Dict[str, Any]


def is_a2a_enabled() -> bool:
    """Check if A2A is enabled."""
    return os.getenv("A2A_ENABLED", "true").lower() == "true"


@router.get("/manifest")
async def get_manifest() -> Dict[str, Any]:
    """
    Get A2A agent manifest.
    
    Returns:
        Agent manifest with available skills
    """
    if not is_a2a_enabled():
        raise HTTPException(
            status_code=503,
            detail="A2A is disabled"
        )
    
    return {
        "agent": "quality-agent",
        "version": "0.1",
        "description": "AI Quality Kit agent for LLM testing and evaluation",
        "skills": [
            {
                "name": "ask_rag",
                "description": "Ask the RAG system a question",
                "parameters": {
                    "query": {"type": "string", "required": True, "description": "Question to ask"},
                    "provider": {"type": "string", "required": False, "description": "LLM provider override"},
                    "model": {"type": "string", "required": False, "description": "Model name override"}
                },
                "returns": {
                    "answer": "string",
                    "context": "array",
                    "provider": "string",
                    "model": "string",
                    "latency_ms": "number",
                    "source": "string"
                }
            },
            {
                "name": "eval_rag",
                "description": "Evaluate RAG response quality",
                "parameters": {
                    "query": {"type": "string", "required": True, "description": "Original query"},
                    "answer": {"type": "string", "required": False, "description": "Answer to evaluate"},
                    "provider": {"type": "string", "required": False, "description": "LLM provider override"},
                    "model": {"type": "string", "required": False, "description": "Model name override"}
                },
                "returns": {
                    "faithfulness": "number",
                    "context_recall": "number",
                    "notes": "string"
                }
            },
            {
                "name": "run_tests",
                "description": "Run test suites",
                "parameters": {
                    "config": {
                        "type": "object",
                        "required": True,
                        "description": "Test configuration",
                        "properties": {
                            "suites": {"type": "array", "items": {"type": "string"}},
                            "provider": {"type": "string"},
                            "model": {"type": "string"}
                        }
                    }
                },
                "returns": {
                    "run_id": "string",
                    "summary": "object",
                    "counts": "object"
                }
            },
            {
                "name": "list_tests",
                "description": "List available test suites",
                "parameters": {},
                "returns": {
                    "suites": "array",
                    "total_suites": "number"
                }
            }
        ],
        "capabilities": [
            "read_only",
            "no_side_effects",
            "quality_evaluation",
            "test_orchestration"
        ],
        "endpoints": {
            "manifest": "/a2a/manifest",
            "act": "/a2a/act"
        }
    }


@router.post("/act")
async def act(
    request: ActRequest,
    principal: Optional[Principal] = Depends(require_user_or_admin())
) -> Dict[str, Any]:
    """
    Execute an A2A skill.
    
    Args:
        request: Act request with skill name and arguments
        principal: Authenticated principal (if auth enabled)
        
    Returns:
        Skill execution result
    """
    if not is_a2a_enabled():
        raise HTTPException(
            status_code=503,
            detail="A2A is disabled"
        )
    
    try:
        # Dispatch to appropriate skill
        if request.skill == "ask_rag":
            return await _execute_ask_rag(request.args)
        elif request.skill == "eval_rag":
            return await _execute_eval_rag(request.args)
        elif request.skill == "run_tests":
            return await _execute_run_tests(request.args)
        elif request.skill == "list_tests":
            return await _execute_list_tests(request.args)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown skill: {request.skill}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Skill execution failed: {str(e)}"
        )


async def _execute_ask_rag(args: Dict[str, Any]) -> Dict[str, Any]:
    """Execute ask_rag skill."""
    from apps.mcp.server import ask_rag
    
    query = args.get("query")
    if not query:
        raise HTTPException(status_code=400, detail="query parameter is required")
    
    provider = args.get("provider")
    model = args.get("model")
    
    result = ask_rag(query, provider, model)
    
    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])
    
    return result


async def _execute_eval_rag(args: Dict[str, Any]) -> Dict[str, Any]:
    """Execute eval_rag skill."""
    from apps.mcp.server import eval_rag
    
    query = args.get("query")
    if not query:
        raise HTTPException(status_code=400, detail="query parameter is required")
    
    answer = args.get("answer")
    provider = args.get("provider")
    model = args.get("model")
    
    result = eval_rag(query, answer, provider, model)
    
    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])
    
    return result


async def _execute_run_tests(args: Dict[str, Any]) -> Dict[str, Any]:
    """Execute run_tests skill."""
    from apps.mcp.server import run_tests
    
    config = args.get("config")
    if not config:
        raise HTTPException(status_code=400, detail="config parameter is required")
    
    result = run_tests(config)
    
    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])
    
    return result


async def _execute_list_tests(args: Dict[str, Any]) -> Dict[str, Any]:
    """Execute list_tests skill."""
    from apps.mcp.server import list_tests
    
    result = list_tests()
    
    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])
    
    return result
