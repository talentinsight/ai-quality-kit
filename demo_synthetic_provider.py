#!/usr/bin/env python3
"""Demo script to show synthetic provider capabilities."""

import asyncio
import json
from apps.orchestrator.run_tests import TestRunner, OrchestratorRequest


async def demo_synthetic_vs_mock():
    """Demo comparing synthetic vs mock providers."""
    
    print("🎯 RAG Reliability & Robustness Suite Demo")
    print("=" * 50)
    
    # Test configuration
    base_config = {
        "target_mode": "api",
        "api_base_url": "http://localhost:8000",
        "suites": ["rag_reliability_robustness"],
        "options": {
            "qa_sample_size": 3,  # Small sample for demo
            "rag_reliability_robustness": {
                "faithfulness_eval": {"enabled": True},
                "context_recall": {"enabled": True},
                "ground_truth_eval": {"enabled": True},
                "prompt_robustness": {"enabled": True}
            }
        }
    }
    
    # Test with Mock Provider
    print("\n🎭 MOCK PROVIDER TEST")
    print("-" * 30)
    mock_request = OrchestratorRequest(
        **base_config,
        provider="mock",
        model="mock-1"
    )
    
    mock_runner = TestRunner(mock_request)
    mock_plan = mock_runner.create_test_plan()
    
    print(f"Suite: {mock_plan.suite}")
    print(f"Total Planned: {mock_plan.total_planned}")
    print("Sub-suites:")
    for name, plan in mock_plan.sub_suites.items():
        status = "✅" if plan.enabled else "❌"
        print(f"  {status} {name}: {plan.planned_items} tests")
    
    # Test with Synthetic Provider
    print("\n🤖 SYNTHETIC PROVIDER TEST")
    print("-" * 30)
    synthetic_options = base_config["options"].copy()
    synthetic_options["synthetic_success_rate"] = 0.9
    
    synthetic_request = OrchestratorRequest(
        target_mode=base_config["target_mode"],
        api_base_url=base_config["api_base_url"],
        suites=base_config["suites"],
        provider="synthetic",
        model="synthetic-v1",
        options=synthetic_options
    )
    
    synthetic_runner = TestRunner(synthetic_request)
    synthetic_plan = synthetic_runner.create_test_plan()
    
    print(f"Suite: {synthetic_plan.suite}")
    print(f"Total Planned: {synthetic_plan.total_planned}")
    print("Sub-suites:")
    for name, plan in synthetic_plan.sub_suites.items():
        status = "✅" if plan.enabled else "❌"
        print(f"  {status} {name}: {plan.planned_items} tests")
    
    # Test with Real Provider (OpenAI)
    print("\n🚀 REAL PROVIDER TEST (OpenAI)")
    print("-" * 30)
    openai_request = OrchestratorRequest(
        target_mode=base_config["target_mode"],
        api_base_url="https://api.openai.com/v1",
        suites=base_config["suites"],
        provider="openai",
        model="gpt-4o-mini",
        api_bearer_token="your-api-key-here",  # Would need real key
        options=base_config["options"]
    )
    
    openai_runner = TestRunner(openai_request)
    openai_plan = openai_runner.create_test_plan()
    
    print(f"Suite: {openai_plan.suite}")
    print(f"Total Planned: {openai_plan.total_planned}")
    print("Sub-suites:")
    for name, plan in openai_plan.sub_suites.items():
        status = "✅" if plan.enabled else "❌"
        print(f"  {status} {name}: {plan.planned_items} tests")
    
    # Comparison
    print("\n📊 COMPARISON")
    print("-" * 30)
    print(f"Mock Provider:      {mock_plan.total_planned} tests planned")
    print(f"Synthetic Provider: {synthetic_plan.total_planned} tests planned")
    print(f"Real Provider:      {openai_plan.total_planned} tests planned")
    
    print("\n💡 RECOMMENDATIONS")
    print("-" * 30)
    print("✅ Use SYNTHETIC for:")
    print("   - Development & Testing")
    print("   - CI/CD Pipelines") 
    print("   - Fast Iterations")
    print("   - Cost-free Testing")
    
    print("\n✅ Use REAL PROVIDERS for:")
    print("   - Actual LLM Evaluation")
    print("   - Production Quality Testing")
    print("   - Model Benchmarking")
    print("   - Customer Validation")
    
    print("\n⚠️  IMPORTANT:")
    print("   Synthetic Provider generates test data - it does NOT test real LLMs!")
    print("   Always use real providers (OpenAI/Anthropic/Gemini) for actual LLM evaluation.")


if __name__ == "__main__":
    asyncio.run(demo_synthetic_vs_mock())
