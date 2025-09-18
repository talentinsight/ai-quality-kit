"""FastAPI routes for guardrails endpoints."""

import logging
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from apps.security.auth import require_user_or_admin, Principal
from apps.server.guardrails.interfaces import PreflightRequest, PreflightResponse
from apps.server.guardrails.aggregator import GuardrailsAggregator
from apps.server.guardrails.health import get_all_providers_health, get_providers_by_category, get_category_availability
from apps.server.sut import create_sut_adapter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/guardrails", tags=["guardrails"])


@router.post("/preflight", response_model=PreflightResponse)
async def run_preflight(
    request: PreflightRequest,
    language: str = "en",
    principal: Principal = Depends(require_user_or_admin)
) -> PreflightResponse:
    """Run guardrails preflight check."""
    try:
        logger.info(f"Starting guardrails preflight for {request.llmType} target")
        
        # Create SUT adapter
        sut_adapter = None
        try:
            sut_adapter = create_sut_adapter(request.target.dict())
            logger.debug("SUT adapter created successfully")
        except Exception as e:
            logger.warning(f"Failed to create SUT adapter: {e}")
            # Continue without SUT adapter - some providers might not need it
        
        # Extract feature flags from request (if any)
        feature_flags = getattr(request, 'feature_flags', {})
        
        # Create aggregator with new features
        aggregator = GuardrailsAggregator(
            config=request.guardrails,
            sut_adapter=sut_adapter,
            language=language,
            feature_flags=feature_flags
        )
        
        # Run preflight
        result = await aggregator.run_preflight()
        
        logger.info(f"Preflight completed: pass={result.pass_}, signals={len(result.signals)}, cached={result.metrics.get('cached_results', 0)}")
        
        return result
        
    except Exception as e:
        logger.error(f"Preflight failed: {e}")
        raise HTTPException(status_code=500, detail=f"Preflight check failed: {str(e)}")


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
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")


@router.get("/health/by-category")
async def get_guardrails_health_by_category() -> Dict[str, List[Dict[str, Any]]]:
    """Get health status grouped by category."""
    try:
        return get_providers_by_category()
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")


@router.get("/health/category/{category}")
async def get_category_health(category: str) -> Dict[str, Any]:
    """Get health status for a specific category."""
    try:
        return get_category_availability(category)
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")
