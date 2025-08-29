"""Smart provider selection for different test scenarios."""

from typing import Optional, Dict, Any
from .synthetic_provider import SyntheticProvider, create_synthetic_provider


class ProviderSelector:
    """Intelligent provider selection based on test requirements."""
    
    @staticmethod
    def get_optimal_provider(
        suite_name: str, 
        test_type: str, 
        environment: str = "test",
        provider_preference: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Select optimal provider based on test requirements.
        
        Args:
            suite_name: Name of test suite (rag_reliability_robustness, red_team, etc.)
            test_type: Type of test (unit, integration, e2e)
            environment: Environment (test, staging, production)
            provider_preference: User's preferred provider
            
        Returns:
            Provider configuration
        """
        
        # User preference takes priority
        if provider_preference and provider_preference != "auto":
            return {
                "provider": provider_preference,
                "reason": f"User selected {provider_preference}"
            }
        
        # Environment-based selection
        if environment == "test":
            return ProviderSelector._get_test_provider(suite_name, test_type)
        elif environment == "staging":
            return ProviderSelector._get_staging_provider(suite_name)
        else:  # production
            return ProviderSelector._get_production_provider(suite_name)
    
    @staticmethod
    def _get_test_provider(suite_name: str, test_type: str) -> Dict[str, Any]:
        """Get optimal provider for test environment."""
        
        # Unit tests - always synthetic for speed
        if test_type == "unit":
            return {
                "provider": "synthetic",
                "success_rate": 1.0,  # Perfect for unit tests
                "reason": "Unit tests need deterministic results"
            }
        
        # Integration tests - synthetic with realistic errors
        elif test_type == "integration":
            if suite_name == "rag_reliability_robustness":
                return {
                    "provider": "synthetic", 
                    "success_rate": 0.95,
                    "reason": "RAG tests need realistic LLM behavior"
                }
            elif suite_name == "red_team":
                return {
                    "provider": "synthetic",
                    "success_rate": 0.9,  # More failures for red team
                    "reason": "Red team tests need controlled failures"
                }
            else:
                return {
                    "provider": "synthetic",
                    "success_rate": 0.95,
                    "reason": "Default synthetic for integration tests"
                }
        
        # E2E tests - synthetic with high realism
        else:
            return {
                "provider": "synthetic",
                "success_rate": 0.92,
                "reason": "E2E tests need realistic error patterns"
            }
    
    @staticmethod
    def _get_staging_provider(suite_name: str) -> Dict[str, Any]:
        """Get optimal provider for staging environment."""
        # Staging can use real providers for validation
        return {
            "provider": "openai",  # Real provider for staging validation
            "model": "gpt-4o-mini",  # Cost-effective model
            "reason": "Staging validation with real LLM"
        }
    
    @staticmethod
    def _get_production_provider(suite_name: str) -> Dict[str, Any]:
        """Get optimal provider for production environment."""
        # Production uses customer's preferred provider
        return {
            "provider": "openai",  # Default production provider
            "model": "gpt-4",
            "reason": "Production environment"
        }



