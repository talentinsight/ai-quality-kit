#!/usr/bin/env python3
"""
Test script to test cache store from main.py perspective.
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

def test_main_cache_import():
    """Test cache store import from main.py perspective."""
    print("🔍 Testing cache store import from main.py perspective...")
    
    try:
        # Import the same way main.py does
        from apps.cache.cache_store import get_cached, set_cache, get_cache_ttl, get_context_version
        
        print("✅ Cache store imported successfully from main.py perspective")
        
        # Check the actual function
        import inspect
        source = inspect.getsource(set_cache)
        print("\n📝 Cache store source code from main.py import:")
        print("=" * 50)
        print(source)
        print("=" * 50)
        
        # Check if ARRAY_CONSTRUCT exists in the code
        if "ARRAY_CONSTRUCT" in source:
            print("❌ ARRAY_CONSTRUCT found in source code!")
        else:
            print("✅ ARRAY_CONSTRUCT NOT found in source code")
        
        # Check if array literal syntax exists
        if "[" in source and "]" in source:
            print("✅ Array literal syntax found in source code")
        else:
            print("❌ Array literal syntax NOT found in source code")
            
        # Test the function
        print("\n🧪 Testing set_cache function...")
        set_cache("test_hash_main", "v1", "test answer", ["context1"], 3600)
        print("✅ set_cache function executed successfully")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Main test function."""
    print("🚀 Testing Cache Store from Main.py Perspective")
    print("=" * 50)
    
    test_main_cache_import()
    
    print("\n" + "=" * 50)
    print("📊 TEST COMPLETED")
    print("=" * 50)

if __name__ == "__main__":
    main()
