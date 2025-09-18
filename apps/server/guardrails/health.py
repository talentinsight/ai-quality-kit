"""Guardrails provider health checking system."""

import logging
from typing import List, Dict, Any, Optional
from .interfaces import GuardrailCategory
from .registry import registry

logger = logging.getLogger(__name__)


def check_provider_health(provider_id: str) -> Dict[str, Any]:
    """Check health of a single provider."""
    try:
        provider_class = registry.get_provider(provider_id)
        provider = provider_class()
        
        # Basic availability check
        is_available = provider.is_available() if hasattr(provider, 'is_available') else True
        
        # Get version if available
        version = getattr(provider, 'version', None)
        
        # Check for missing dependencies
        missing_deps = []
        if hasattr(provider, 'check_dependencies'):
            missing_deps = provider.check_dependencies()
        
        return {
            "id": provider_id,
            "available": is_available and len(missing_deps) == 0,
            "version": version,
            "missing_deps": missing_deps,
            "category": provider.category.value if hasattr(provider, 'category') else "unknown"
        }
        
    except Exception as e:
        logger.warning(f"Health check failed for provider {provider_id}: {e}")
        return {
            "id": provider_id,
            "available": False,
            "version": None,
            "missing_deps": [str(e)],
            "category": "unknown"
        }


def get_all_providers_health() -> List[Dict[str, Any]]:
    """Get health status for all registered providers."""
    health_results = []
    
    for provider_id in registry.list_providers():
        health_result = check_provider_health(provider_id)
        health_results.append(health_result)
    
    # Add MCP harness health check
    mcp_health = check_mcp_harness_health()
    if mcp_health:
        health_results.append(mcp_health)
    
    # Sort by category and then by id for consistent ordering
    health_results.sort(key=lambda x: (x.get("category", ""), x.get("id", "")))
    
    return health_results


def get_providers_by_category() -> Dict[str, List[Dict[str, Any]]]:
    """Get providers grouped by category with health status."""
    all_health = get_all_providers_health()
    by_category = {}
    
    for provider_health in all_health:
        category = provider_health.get("category", "unknown")
        if category not in by_category:
            by_category[category] = []
        by_category[category].append(provider_health)
    
    return by_category


def get_category_availability(category: str) -> Dict[str, Any]:
    """Get availability summary for a specific category."""
    providers_by_cat = get_providers_by_category()
    category_providers = providers_by_cat.get(category, [])
    
    if not category_providers:
        return {
            "category": category,
            "available": False,
            "total_providers": 0,
            "available_providers": 0,
            "providers": []
        }
    
    available_count = sum(1 for p in category_providers if p.get("available", False))
    
    return {
        "category": category,
        "available": available_count > 0,  # Category available if at least one provider works
        "total_providers": len(category_providers),
        "available_providers": available_count,
        "providers": category_providers
    }


def check_mcp_harness_health() -> Optional[Dict[str, Any]]:
    """Check health of MCP harness."""
    try:
        from apps.orchestrator.mcp_harness import is_mcp_harness_available, get_mcp_harness_version
        
        is_available = is_mcp_harness_available()
        version = get_mcp_harness_version() if is_available else None
        
        missing_deps = []
        if not is_available:
            missing_deps.append("websockets")
        
        return {
            "id": "mcp.harness",
            "available": is_available,
            "version": version,
            "missing_deps": missing_deps,
            "category": "mcp"
        }
        
    except Exception as e:
        logger.warning(f"MCP harness health check failed: {e}")
        return {
            "id": "mcp.harness",
            "available": False,
            "version": None,
            "missing_deps": [str(e)],
            "category": "mcp"
        }
