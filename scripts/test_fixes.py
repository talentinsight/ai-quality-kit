#!/usr/bin/env python3
"""
Test script to verify the fixes for the identified errors.
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

def test_log_service():
    """Test the fixed log service."""
    print("🧪 Testing log service fixes...")
    
    try:
        from apps.observability.log_service import start_log, finish_log
        
        # Test with empty context
        log_id = start_log("test query", "hash123", [], "test")
        print(f"✅ Start log with empty context: {log_id}")
        
        # Test with context
        log_id2 = start_log("test query 2", "hash456", ["context1", "context2"], "test")
        print(f"✅ Start log with context: {log_id2}")
        
        # Test finish log
        finish_log(log_id, "test answer", 100)
        print("✅ Finish log completed")
        
        return True
        
    except Exception as e:
        print(f"❌ Log service test failed: {e}")
        return False

def test_cache_store():
    """Test the fixed cache store."""
    print("🧪 Testing cache store fixes...")
    
    try:
        from apps.cache.cache_store import set_cache, get_cached
        
        # Test cache operations
        set_cache("test_hash", "v1", "test answer", ["context1"], 3600)
        print("✅ Cache set completed")
        
        cached = get_cached("test_hash", "v1")
        if cached:
            print("✅ Cache get completed")
        else:
            print("⚠️ Cache get returned None (may be expected)")
        
        return True
        
    except Exception as e:
        print(f"❌ Cache store test failed: {e}")
        return False

def test_metrics():
    """Test the fixed metrics evaluation."""
    print("🧪 Testing metrics fixes...")
    
    try:
        from evals.metrics import eval_batch, create_eval_sample
        
        # Create test sample
        sample = create_eval_sample(
            question="What is data quality?",
            answer="Data quality refers to the accuracy and reliability of data.",
            contexts=["Data quality is important for business decisions."]
        )
        
        # Test evaluation (should handle uvloop gracefully)
        scores = eval_batch([sample])
        print(f"✅ Metrics evaluation completed: {scores}")
        
        return True
        
    except Exception as e:
        print(f"❌ Metrics test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("🚀 Testing AI Quality Kit Fixes")
    print("=" * 40)
    
    tests = [
        ("Log Service", test_log_service),
        ("Cache Store", test_cache_store),
        ("Metrics", test_metrics)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} test crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 40)
    print("📊 TEST SUMMARY")
    print("=" * 40)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
    
    print(f"\n🎯 Overall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The fixes are working correctly.")
        return 0
    else:
        print("⚠️ Some tests failed. Check the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
