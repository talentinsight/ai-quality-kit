#!/usr/bin/env python3
"""Smoke test for resilience test suite functionality."""

import json
import requests
import sys
import time
from typing import Dict, Any


BASE_URL = "http://127.0.0.1:8000"


def test_resilience_passive_mode():
    """Test resilience suite in passive mode."""
    print("🧪 Test 1: Resilience suite - passive mode")
    
    payload = {
        "target_mode": "api",
        "suites": ["resilience"],
        "options": {
            "provider": "mock",
            "model": "mock-1",
            "resilience": {
                "mode": "passive",
                "samples": 3,
                "timeout_ms": 5000,
                "retries": 0,
                "concurrency": 5,
                "queue_depth": 20,
                "circuit": {"fails": 3, "reset_s": 30}
            }
        }
    }
    
    response = requests.post(f"{BASE_URL}/orchestrator/run_tests", json=payload)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    result = response.json()
    assert "run_id" in result
    assert "summary" in result
    assert "counts" in result
    
    # Check counts
    counts = result["counts"]
    assert counts.get("total_tests", 0) == 3  # samples = 3
    assert counts.get("resilience_total", 0) == 3
    
    # Check summary has resilience data
    summary = result["summary"]
    assert "resilience" in summary
    
    resilience_summary = summary["resilience"]
    assert resilience_summary["samples"] == 3
    assert "success_rate" in resilience_summary
    assert "timeouts" in resilience_summary
    assert "upstream_5xx" in resilience_summary
    assert "upstream_429" in resilience_summary
    assert "circuit_open_events" in resilience_summary
    
    print(f"  ✅ Passive mode test completed: {resilience_summary['samples']} samples, "
          f"{resilience_summary['success_rate']:.2f} success rate")
    
    return result["run_id"]


def test_resilience_synthetic_mode():
    """Test resilience suite in synthetic mode."""
    print("🧪 Test 2: Resilience suite - synthetic mode")
    
    payload = {
        "target_mode": "api", 
        "suites": ["resilience"],
        "options": {
            "provider": "mock",
            "model": "mock-1",
            "resilience": {
                "mode": "synthetic",
                "samples": 10,  # More samples to get variety
                "timeout_ms": 2000,
                "retries": 0,
                "concurrency": 3,
                "queue_depth": 15,
                "circuit": {"fails": 2, "reset_s": 10}
            }
        }
    }
    
    response = requests.post(f"{BASE_URL}/orchestrator/run_tests", json=payload)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    result = response.json()
    
    # Check counts
    counts = result["counts"]
    assert counts.get("total_tests", 0) == 10
    assert counts.get("resilience_total", 0) == 10
    
    # Check summary
    resilience_summary = result["summary"]["resilience"]
    assert resilience_summary["samples"] == 10
    
    # In synthetic mode, should have some variety of outcomes
    total_failures = (
        resilience_summary["timeouts"] + 
        resilience_summary["upstream_5xx"] + 
        resilience_summary["upstream_429"] +
        resilience_summary["circuit_open_events"]
    )
    
    # Should have at least some successes and some failures
    assert resilience_summary["success_rate"] > 0, "Should have some successes"
    assert total_failures > 0, "Should have some failures in synthetic mode"
    
    print(f"  ✅ Synthetic mode test completed: {resilience_summary['samples']} samples, "
          f"success_rate={resilience_summary['success_rate']:.2f}, "
          f"timeouts={resilience_summary['timeouts']}, "
          f"5xx={resilience_summary['upstream_5xx']}, "
          f"429={resilience_summary['upstream_429']}")
    
    return result["run_id"]


def test_backward_compatibility():
    """Test gibberish -> resilience alias."""
    print("🧪 Test 3: Backward compatibility - gibberish alias")
    
    payload = {
        "target_mode": "api",
        "suites": ["gibberish"],  # Using deprecated suite name
        "options": {
            "provider": "mock",
            "model": "mock-1"
        }
    }
    
    response = requests.post(f"{BASE_URL}/orchestrator/run_tests", json=payload)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    result = response.json()
    
    # Should have run resilience tests
    counts = result["counts"]
    assert counts.get("resilience_total", 0) > 0, "Should have run resilience tests"
    
    # Should have deprecation note in summary
    summary = result["summary"]
    assert "_deprecated_note" in summary, "Should have deprecation note"
    assert "gibberish → resilience" in summary["_deprecated_note"], "Should mention alias"
    
    print(f"  ✅ Backward compatibility verified: gibberish mapped to resilience")
    print(f"  ℹ️  Deprecation note: {summary['_deprecated_note']}")
    
    return result["run_id"]


def check_json_report_structure(run_id: str):
    """Check JSON report includes resilience data."""
    print("🧪 Test 4: JSON report structure")
    
    response = requests.get(f"{BASE_URL}/orchestrator/report/{run_id}.json")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    report = response.json()
    
    # Check report structure
    assert "resilience" in report, "Report should have resilience section"
    
    resilience_section = report["resilience"]
    assert "summary" in resilience_section, "Should have resilience summary"
    assert "details" in resilience_section, "Should have resilience details"
    
    # Check summary structure
    summary = resilience_section["summary"]
    required_fields = ["samples", "success_rate", "timeouts", "upstream_5xx", "upstream_429", "circuit_open_events"]
    for field in required_fields:
        assert field in summary, f"Summary should have {field}"
    
    # Check details structure
    details = resilience_section["details"]
    assert len(details) > 0, "Should have resilience detail records"
    
    detail = details[0]
    required_detail_fields = ["run_id", "timestamp", "provider", "model", "request_id", "outcome", "attempts", "latency_ms", "mode"]
    for field in required_detail_fields:
        assert field in detail, f"Detail record should have {field}"
    
    assert detail["outcome"] in ["success", "timeout", "upstream_5xx", "upstream_429", "circuit_open"], f"Invalid outcome: {detail['outcome']}"
    
    print(f"  ✅ JSON report structure verified: {len(details)} detail records")
    

def check_excel_report_available(run_id: str):
    """Check Excel report is available."""
    print("🧪 Test 5: Excel report availability")
    
    response = requests.get(f"{BASE_URL}/orchestrator/report/{run_id}.xlsx")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    # Check it's actually Excel content
    assert response.headers.get("content-type") == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    
    content_length = len(response.content)
    assert content_length > 1000, f"Excel file too small: {content_length} bytes"
    
    print(f"  ✅ Excel report available: {content_length} bytes")


def test_mixed_suites():
    """Test resilience with other suites."""
    print("🧪 Test 6: Mixed suites with resilience")
    
    payload = {
        "target_mode": "api",
        "suites": ["resilience", "performance"],
        "options": {
            "provider": "mock",
            "model": "mock-1",
            "resilience": {
                "mode": "passive",
                "samples": 2
            },
            "perf_repeats": 2
        }
    }
    
    response = requests.post(f"{BASE_URL}/orchestrator/run_tests", json=payload)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    result = response.json()
    
    # Should have both suite results
    summary = result["summary"]
    assert "resilience" in summary, "Should have resilience results"
    assert "performance" in summary, "Should have performance results"
    
    counts = result["counts"]
    assert counts.get("resilience_total", 0) == 2, "Should have 2 resilience tests"
    assert counts.get("performance_total", 0) == 2, "Should have 2 performance tests"
    assert counts.get("total_tests", 0) == 4, "Should have 4 total tests"
    
    print(f"  ✅ Mixed suites test completed: resilience + performance")


def main():
    """Run all smoke tests."""
    print("🚀 Starting resilience suite smoke tests...")
    print(f"🎯 Target: {BASE_URL}")
    
    try:
        # Test basic health
        response = requests.get(f"{BASE_URL}/healthz", timeout=5)
        assert response.status_code == 200, "Health check failed"
        print("✅ Health check passed")
        
        # Run test sequence
        run_id1 = test_resilience_passive_mode()
        run_id2 = test_resilience_synthetic_mode()
        run_id3 = test_backward_compatibility()
        
        # Test reports with most recent run
        check_json_report_structure(run_id2)
        check_excel_report_available(run_id2)
        
        # Test mixed suites
        test_mixed_suites()
        
        print("\n🎉 All resilience smoke tests PASSED!")
        print("✅ Resilience suite is working correctly")
        print("✅ Backward compatibility maintained")
        print("✅ Reports include resilience data")
        
    except Exception as e:
        print(f"\n❌ Smoke test FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
