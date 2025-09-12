"""
Test coverage floor validation.

Ensures that coverage reporting is properly configured and working.
"""

import os
import pytest
import subprocess
import sys
from pathlib import Path


class TestCoverageFloor:
    """Test coverage configuration and reporting."""
    
    def test_coverage_config_exists(self):
        """Test that coverage configuration exists."""
        project_root = Path(__file__).parent.parent.parent
        
        # Check for pytest.ini or pyproject.toml with coverage config
        pytest_ini = project_root / "pytest.ini"
        pyproject_toml = project_root / "pyproject.toml"
        
        has_pytest_ini = pytest_ini.exists()
        has_pyproject = pyproject_toml.exists()
        
        assert has_pytest_ini or has_pyproject, "No pytest configuration file found"
        
        if has_pytest_ini:
            content = pytest_ini.read_text()
            assert "--cov-branch" in content, "Branch coverage not enabled in pytest.ini"
    
    def test_coverage_packages_available(self):
        """Test that coverage packages are available."""
        try:
            import coverage
            import pytest_cov
        except ImportError as e:
            pytest.fail(f"Coverage packages not available: {e}")
    
    @pytest.mark.skipif(
        not os.getenv("CI"), 
        reason="Coverage floor test only runs in CI environment"
    )
    def test_coverage_floor_in_ci(self):
        """Test that coverage meets minimum threshold in CI."""
        # This test only runs in CI to avoid local development friction
        project_root = Path(__file__).parent.parent.parent
        
        # Run a minimal coverage test
        result = subprocess.run([
            sys.executable, "-m", "pytest", 
            "--cov=apps.common", 
            "--cov-report=term-missing",
            "--cov-fail-under=80",
            str(project_root / "tests" / "infra"),
            "-v"
        ], capture_output=True, text=True, cwd=project_root)
        
        # The test should pass (coverage should be adequate for common module)
        assert result.returncode == 0, f"Coverage test failed: {result.stdout}\n{result.stderr}"
    
    def test_coverage_command_available(self):
        """Test that coverage command is available."""
        result = subprocess.run([
            sys.executable, "-m", "coverage", "--version"
        ], capture_output=True, text=True)
        
        assert result.returncode == 0, "Coverage command not available"
        assert "coverage" in result.stdout.lower(), "Coverage version not reported correctly"
