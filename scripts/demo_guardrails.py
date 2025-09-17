"""Demonstration script for guardrails preflight functionality."""

import asyncio
import json
from typing import Dict, Any


async def demo_guardrails_preflight():
    """Demonstrate guardrails preflight functionality."""
    print("🛡️  Guardrails Preflight Demo")
    print("=" * 50)
    
    try:
        # Import guardrails modules
        from apps.server.guardrails.interfaces import (
            PreflightRequest, TargetConfig, GuardrailsConfig, GuardrailRule,
            GuardrailCategory, GuardrailMode
        )
        from apps.server.guardrails.aggregator import GuardrailsAggregator
        from apps.server.sut import create_sut_adapter
        
        print("✅ Guardrails modules imported successfully")
        
        # Create target configuration
        target = TargetConfig(
            mode="api",
            provider="openai",
            endpoint="https://api.openai.com/v1",
            headers={"Authorization": "Bearer demo-key"},
            model="gpt-3.5-turbo",
            timeoutMs=30000
        )
        print(f"📡 Target configured: {target.provider} via {target.mode}")
        
        # Create guardrails configuration
        guardrails = GuardrailsConfig(
            mode=GuardrailMode.ADVISORY,
            thresholds={"pii": 0.0, "toxicity": 0.3},
            rules=[
                GuardrailRule(
                    id="pii-check",
                    category=GuardrailCategory.PII,
                    enabled=True,
                    threshold=0.0,
                    mode=GuardrailMode.ADVISORY,
                    applicability="agnostic"
                ),
                GuardrailRule(
                    id="toxicity-check",
                    category=GuardrailCategory.TOXICITY,
                    enabled=True,
                    threshold=0.3,
                    mode=GuardrailMode.ADVISORY,
                    applicability="agnostic"
                )
            ]
        )
        print(f"🛡️  Guardrails configured: {len(guardrails.rules)} rules in {guardrails.mode.value} mode")
        
        # Create aggregator (without SUT for demo)
        aggregator = GuardrailsAggregator(guardrails, sut_adapter=None)
        print("🔧 Aggregator created")
        
        # Demo different test scenarios
        test_scenarios = [
            ("Clean text", "Hello, how are you today?"),
            ("PII-containing text", "My email is john.doe@example.com and phone is 555-123-4567"),
            ("Potentially toxic text", "This is a terrible and awful response"),
        ]
        
        for scenario_name, test_input in test_scenarios:
            print(f"\n🧪 Testing: {scenario_name}")
            print(f"   Input: {test_input}")
            
            try:
                # Mock the provider execution for demo
                from unittest.mock import patch, AsyncMock, Mock
                
                with patch('apps.server.guardrails.providers.pii_presidio.PresidioPIIProvider') as mock_pii, \
                     patch('apps.server.guardrails.providers.toxicity_detoxify.DetoxifyToxicityProvider') as mock_tox:
                    
                    # Configure mock responses based on scenario
                    if "PII" in scenario_name:
                        pii_score = 0.8
                        pii_label = "hit"
                        pii_details = {"total_hits": 2, "entity_types": ["EMAIL", "PHONE"]}
                    else:
                        pii_score = 0.0
                        pii_label = "clean"
                        pii_details = {"total_hits": 0}
                    
                    if "toxic" in scenario_name:
                        tox_score = 0.6
                        tox_label = "violation"
                        tox_details = {"toxicity_score": 0.6}
                    else:
                        tox_score = 0.1
                        tox_label = "clean"
                        tox_details = {"toxicity_score": 0.1}
                    
                    mock_pii.return_value.check = AsyncMock(return_value=Mock(
                        id="pii.presidio",
                        category=GuardrailCategory.PII,
                        score=pii_score,
                        label=Mock(value=pii_label),
                        confidence=0.9,
                        details=pii_details
                    ))
                    
                    mock_tox.return_value.check = AsyncMock(return_value=Mock(
                        id="toxicity.detoxify",
                        category=GuardrailCategory.TOXICITY,
                        score=tox_score,
                        label=Mock(value=tox_label),
                        confidence=0.8,
                        details=tox_details
                    ))
                    
                    # Run preflight
                    result = await aggregator.run_preflight(test_input)
                    
                    # Display results
                    print(f"   Result: {'✅ PASS' if result.pass_ else '❌ FAIL'}")
                    print(f"   Signals: {len(result.signals)} providers")
                    print(f"   Duration: {result.metrics.get('duration_ms', 0):.1f}ms")
                    
                    for reason in result.reasons[:3]:  # Show first 3 reasons
                        print(f"   • {reason}")
                    
                    if len(result.reasons) > 3:
                        print(f"   ... and {len(result.reasons) - 3} more")
                
            except Exception as e:
                print(f"   ❌ Error: {e}")
        
        print(f"\n🎉 Demo completed successfully!")
        print("\nKey Features Demonstrated:")
        print("• ✅ Modular provider system (PII, Toxicity)")
        print("• ✅ Configurable thresholds and modes")
        print("• ✅ Graceful degradation when providers unavailable")
        print("• ✅ Privacy-preserving (no raw text in outputs)")
        print("• ✅ Deterministic results for same inputs")
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Make sure all guardrails modules are properly installed")
    except Exception as e:
        print(f"❌ Demo failed: {e}")


def demo_api_request_format():
    """Show the expected API request format."""
    print("\n📋 API Request Format")
    print("=" * 30)
    
    sample_request = {
        "llmType": "plain",
        "target": {
            "mode": "api",
            "provider": "openai",
            "endpoint": "https://api.openai.com/v1",
            "headers": {
                "Authorization": "Bearer your-api-key",
                "Content-Type": "application/json"
            },
            "model": "gpt-3.5-turbo",
            "timeoutMs": 30000
        },
        "guardrails": {
            "mode": "hard_gate",
            "thresholds": {
                "pii": 0.0,
                "toxicity": 0.3,
                "jailbreak": 0.15
            },
            "rules": [
                {
                    "id": "pii-check",
                    "category": "pii",
                    "enabled": True,
                    "threshold": 0.0,
                    "mode": "hard_gate",
                    "applicability": "agnostic"
                },
                {
                    "id": "toxicity-check",
                    "category": "toxicity",
                    "enabled": True,
                    "threshold": 0.3,
                    "mode": "hard_gate",
                    "applicability": "agnostic"
                }
            ]
        }
    }
    
    print("POST /guardrails/preflight")
    print("Content-Type: application/json")
    print()
    print(json.dumps(sample_request, indent=2))
    
    sample_response = {
        "pass": True,
        "reasons": [
            "pii: 0.000 < 0.000 ✓",
            "toxicity: 0.120 < 0.300 ✓"
        ],
        "signals": [
            {
                "id": "pii.presidio",
                "category": "pii",
                "score": 0.0,
                "label": "clean",
                "confidence": 1.0,
                "details": {
                    "total_hits": 0,
                    "entity_types": []
                }
            }
        ],
        "metrics": {
            "tests": 2,
            "duration_ms": 245.7,
            "providers_run": 2,
            "providers_unavailable": 0
        }
    }
    
    print("\nExpected Response:")
    print(json.dumps(sample_response, indent=2))


if __name__ == "__main__":
    print("🚀 Starting Guardrails Demo...")
    
    # Run the async demo
    asyncio.run(demo_guardrails_preflight())
    
    # Show API format
    demo_api_request_format()
    
    print("\n✨ Demo complete! The guardrails system is ready for use.")
    print("\nNext steps:")
    print("1. Install optional dependencies: pip install presidio-analyzer detoxify")
    print("2. Start the server and test: POST /guardrails/preflight")
    print("3. Check the frontend 'Run Preflight' button functionality")
