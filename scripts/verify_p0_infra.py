#!/usr/bin/env python3
"""
P0 Infrastructure Verification Script.

Verifies that all P0 infrastructure components are properly implemented
and working as expected.
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def verify_coverage_gate():
    """Verify coverage gate configuration."""
    print("🔍 Verifying Coverage Gate...")
    
    # Check pytest.ini
    pytest_ini = project_root / "pytest.ini"
    if pytest_ini.exists():
        content = pytest_ini.read_text()
        if "--cov-branch" in content:
            print("  ✅ Branch coverage enabled in pytest.ini")
        else:
            print("  ❌ Branch coverage not found in pytest.ini")
            return False
    
    # Check CI workflow
    ci_yml = project_root / ".github" / "workflows" / "ci.yml"
    if ci_yml.exists():
        content = ci_yml.read_text()
        if "--cov-fail-under=80" in content:
            print("  ✅ 80% coverage threshold set in CI")
        else:
            print("  ❌ 80% coverage threshold not found in CI")
            return False
    
    return True

def verify_exception_handling():
    """Verify exception handling implementation."""
    print("🔍 Verifying Exception Handling...")
    
    try:
        from apps.common.errors import (
            EvaluationError, DatasetValidationError, SuiteExecutionError,
            ProviderError, ReportError, ConfigurationError, GatingError
        )
        print("  ✅ All exception classes imported successfully")
        
        # Test basic functionality
        error = DatasetValidationError("Test error", dataset_type="safety")
        error_dict = error.to_dict()
        if "error_type" in error_dict and "message" in error_dict:
            print("  ✅ Exception serialization working")
        else:
            print("  ❌ Exception serialization failed")
            return False
            
    except ImportError as e:
        print(f"  ❌ Failed to import exception classes: {e}")
        return False
    
    return True

def verify_logging_redaction():
    """Verify logging and redaction functionality."""
    print("🔍 Verifying Logging & Redaction...")
    
    try:
        from apps.common.logging import redact, get_logger, get_redacting_logger
        print("  ✅ Logging modules imported successfully")
        
        # Test redaction
        test_cases = [
            ("sk-1234567890abcdef1234567890abcdef", "sk-***REDACTED***"),
            ("user@example.com", "***EMAIL_REDACTED***"),
            ("555-123-4567", "***PHONE_REDACTED***")
        ]
        
        all_passed = True
        for original, expected_pattern in test_cases:
            result = redact(original)
            if expected_pattern in result:
                print(f"  ✅ Redacted: {original[:10]}... → {result}")
            else:
                print(f"  ❌ Failed to redact: {original}")
                all_passed = False
        
        return all_passed
        
    except ImportError as e:
        print(f"  ❌ Failed to import logging modules: {e}")
        return False

def verify_http_handlers():
    """Verify HTTP exception handlers."""
    print("🔍 Verifying HTTP Exception Handlers...")
    
    try:
        from apps.common.http_handlers import install_exception_handlers, create_error_response
        print("  ✅ HTTP handler modules imported successfully")
        
        # Test error response creation
        response = create_error_response(400, "TEST_ERROR", "Test message")
        if hasattr(response, 'status_code') and response.status_code == 400:
            print("  ✅ Error response creation working")
        else:
            print("  ❌ Error response creation failed")
            return False
            
    except ImportError as e:
        print(f"  ❌ Failed to import HTTP handler modules: {e}")
        return False
    
    return True

def verify_template_validator():
    """Verify template validator implementation."""
    print("🔍 Verifying Template Validator...")
    
    # Check script exists
    script_path = project_root / "scripts" / "validate_templates.py"
    if not script_path.exists():
        print("  ❌ Template validator script not found")
        return False
    
    print("  ✅ Template validator script exists")
    
    # Check Makefile target
    makefile = project_root / "Makefile"
    if makefile.exists():
        content = makefile.read_text()
        if "validate-templates:" in content:
            print("  ✅ Makefile target exists")
        else:
            print("  ❌ Makefile target not found")
            return False
    
    # Check CI integration
    ci_yml = project_root / ".github" / "workflows" / "ci.yml"
    if ci_yml.exists():
        content = ci_yml.read_text()
        if "validate_templates.py" in content:
            print("  ✅ CI integration exists")
        else:
            print("  ❌ CI integration not found")
            return False
    
    return True

def verify_fastapi_integration():
    """Verify FastAPI integration."""
    print("🔍 Verifying FastAPI Integration...")
    
    # Check that main.py has exception handler installation
    main_py = project_root / "apps" / "rag_service" / "main.py"
    if main_py.exists():
        content = main_py.read_text()
        if "install_exception_handlers" in content:
            print("  ✅ Exception handlers installed in FastAPI app")
        else:
            print("  ❌ Exception handlers not installed in FastAPI app")
            return False
    
    return True

def verify_tests():
    """Verify test infrastructure."""
    print("🔍 Verifying Test Infrastructure...")
    
    test_files = [
        "tests/infra/test_common_errors.py",
        "tests/infra/test_common_logging.py", 
        "tests/infra/test_http_handlers.py",
        "tests/infra/test_coverage_floor.py",
        "tests/infra/test_template_schema_validator.py"
    ]
    
    all_exist = True
    for test_file in test_files:
        path = project_root / test_file
        if path.exists():
            print(f"  ✅ {test_file}")
        else:
            print(f"  ❌ {test_file} missing")
            all_exist = False
    
    return all_exist

def main():
    """Main verification function."""
    print("=" * 60)
    print("P0 INFRASTRUCTURE VERIFICATION")
    print("=" * 60)
    
    verifications = [
        ("Coverage Gate", verify_coverage_gate),
        ("Exception Handling", verify_exception_handling),
        ("Logging & Redaction", verify_logging_redaction),
        ("HTTP Handlers", verify_http_handlers),
        ("Template Validator", verify_template_validator),
        ("FastAPI Integration", verify_fastapi_integration),
        ("Test Infrastructure", verify_tests)
    ]
    
    results = []
    for name, verify_func in verifications:
        try:
            result = verify_func()
            results.append((name, result))
            print()
        except Exception as e:
            print(f"  ❌ Verification failed with exception: {e}")
            results.append((name, False))
            print()
    
    # Summary
    print("=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    
    passed = 0
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{name:.<40} {status}")
        if result:
            passed += 1
    
    print("-" * 60)
    print(f"Overall: {passed}/{total} verifications passed")
    
    if passed == total:
        print("\n🎉 All P0 infrastructure components verified successfully!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} verification(s) failed. Please review the output above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
