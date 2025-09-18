"""Guardrails API router."""

from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from .health import get_all_providers_health, get_providers_by_category, get_category_availability

router = APIRouter(prefix="/guardrails", tags=["guardrails"])


@router.get("/health")
async def get_guardrails_health() -> List[Dict[str, Any]]:
    """Get health status of all guardrail providers.
    
    Returns:
        Array of provider health status objects with:
        - id: provider identifier
        - available: boolean availability status
        - version: optional version string
        - missing_deps: array of missing dependencies
        - category: guardrail category
    """
    try:
        return get_all_providers_health()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")


@router.get("/health/by-category")
async def get_guardrails_health_by_category() -> Dict[str, List[Dict[str, Any]]]:
    """Get health status grouped by category."""
    try:
        return get_providers_by_category()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")


@router.get("/health/category/{category}")
async def get_category_health(category: str) -> Dict[str, Any]:
    """Get health status for a specific category."""
    try:
        return get_category_availability(category)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")
