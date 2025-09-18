#!/usr/bin/env python3
"""
Debug script to understand cache store issues.
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

def debug_cache_store():
    """Debug the cache store to understand the ARRAY_CONSTRUCT issue."""
    print("🔍 Debugging cache store...")
    
    try:
        # Import cache store
        from apps.cache.cache_store import set_cache
        
        print("✅ Cache store imported successfully")
        
        # Check the actual function
        import inspect
        source = inspect.getsource(set_cache)
        print("\n📝 Cache store source code:")
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
            
    except Exception as e:
        print(f"❌ Debug failed: {e}")

def main():
    """Main debug function."""
    print("🚀 Debugging Cache Store Issues")
    print("=" * 40)
    
    debug_cache_store()
    
    print("\n" + "=" * 40)
    print("📊 DEBUG COMPLETED")
    print("=" * 40)

if __name__ == "__main__":
    main()
