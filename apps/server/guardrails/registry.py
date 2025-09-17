"""Provider registry for guardrails system."""

from typing import Dict, Type, List
from .interfaces import GuardrailProvider, GuardrailCategory


class ProviderRegistry:
    """Registry for guardrail providers."""
    
    def __init__(self):
        self._providers: Dict[str, Type[GuardrailProvider]] = {}
        self._category_providers: Dict[GuardrailCategory, List[str]] = {}
    
    def register(self, provider_id: str, provider_class: Type[GuardrailProvider], category: GuardrailCategory):
        """Register a provider."""
        self._providers[provider_id] = provider_class
        if category not in self._category_providers:
            self._category_providers[category] = []
        self._category_providers[category].append(provider_id)
    
    def get_provider(self, provider_id: str) -> Type[GuardrailProvider]:
        """Get provider class by ID."""
        if provider_id not in self._providers:
            raise ValueError(f"Unknown provider: {provider_id}")
        return self._providers[provider_id]
    
    def get_providers_for_category(self, category: GuardrailCategory) -> List[str]:
        """Get all provider IDs for a category."""
        return self._category_providers.get(category, [])
    
    def list_providers(self) -> List[str]:
        """List all registered provider IDs."""
        return list(self._providers.keys())


# Global registry instance
registry = ProviderRegistry()


def register_provider(provider_id: str, category: GuardrailCategory):
    """Decorator to register a provider."""
    def decorator(provider_class: Type[GuardrailProvider]):
        registry.register(provider_id, provider_class, category)
        return provider_class
    return decorator
