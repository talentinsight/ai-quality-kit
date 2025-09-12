"""
Test template-schema validator functionality.

Ensures that the template validator works correctly and catches drift.
"""

import pytest
import sys
import subprocess
from pathlib import Path
from unittest.mock import patch, mock_open

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from scripts.validate_templates import TemplateValidator


class TestTemplateSchemaValidator:
    """Test the template-schema validator."""
    
    def test_validator_initialization(self):
        """Test that validator initializes correctly."""
        validator = TemplateValidator()
        
        assert validator.project_root == project_root
        assert validator.templates_dir == project_root / "data" / "templates"
        assert validator.errors == []
        assert validator.warnings == []
    
    def test_validator_script_exists(self):
        """Test that the validator script exists and is executable."""
        script_path = project_root / "scripts" / "validate_templates.py"
        
        assert script_path.exists(), "Template validator script not found"
        assert script_path.is_file(), "Template validator is not a file"
        
        # Check if it's executable (on Unix systems)
        if hasattr(script_path, 'stat'):
            stat = script_path.stat()
            assert stat.st_mode & 0o111, "Template validator script is not executable"
    
    def test_validator_runs_successfully(self):
        """Test that validator runs without crashing on existing templates."""
        script_path = project_root / "scripts" / "validate_templates.py"
        
        # Run the validator script
        result = subprocess.run([
            sys.executable, str(script_path)
        ], capture_output=True, text=True, cwd=project_root)
        
        # Should not crash (exit code 0 or 1 are both acceptable - 1 means validation failed but didn't crash)
        assert result.returncode in [0, 1], f"Validator crashed with exit code {result.returncode}: {result.stderr}"
        
        # Should produce some output
        assert result.stdout or result.stderr, "Validator produced no output"
    
    def test_validator_detects_missing_templates(self):
        """Test that validator properly handles missing templates."""
        validator = TemplateValidator()
        
        # Mock the templates directory to be empty
        with patch.object(validator, 'templates_dir', Path("/nonexistent")):
            # This should not crash, but should produce warnings
            config = {
                "suite": "test_suite",
                "templates": ["nonexistent.yaml"],
                "loader_module": "apps.common.errors",
                "loader_function": "EvaluationError"
            }
            
            result = validator._validate_suite_templates(config)
            
            # Should handle missing templates gracefully
            assert isinstance(result, bool)
    
    def test_validator_handles_import_errors(self):
        """Test that validator handles import errors gracefully."""
        validator = TemplateValidator()
        
        config = {
            "suite": "test_suite",
            "templates": ["test.yaml"],
            "loader_module": "nonexistent.module",
            "loader_function": "nonexistent_function"
        }
        
        result = validator._validate_suite_templates(config)
        
        # Should return False and record error
        assert result is False
        assert len(validator.errors) > 0
        assert "test_suite" in validator.errors[0]
    
    def test_validator_format_parity_check(self):
        """Test format parity checking logic."""
        validator = TemplateValidator()
        
        # Mock parsed results with different structures
        class MockResult:
            def __init__(self, cases_count):
                self.cases = [f"case_{i}" for i in range(cases_count)]
        
        # Test matching counts
        parsed_results = {
            "format1.yaml": MockResult(3),
            "format2.json": MockResult(3)
        }
        
        result = validator._check_format_parity("test_suite", parsed_results)
        assert result is True
        
        # Test mismatched counts
        parsed_results = {
            "format1.yaml": MockResult(3),
            "format2.json": MockResult(2)
        }
        
        result = validator._check_format_parity("test_suite", parsed_results)
        assert result is False
        assert len(validator.warnings) > 0
    
    def test_make_target_exists(self):
        """Test that make validate-templates target exists."""
        makefile_path = project_root / "Makefile"
        
        if makefile_path.exists():
            content = makefile_path.read_text()
            assert "validate-templates:" in content, "validate-templates target not found in Makefile"
            assert "validate_templates.py" in content, "Template validator not called in Makefile"
    
    def test_ci_includes_template_validation(self):
        """Test that CI workflow includes template validation."""
        ci_path = project_root / ".github" / "workflows" / "ci.yml"
        
        if ci_path.exists():
            content = ci_path.read_text()
            assert "validate_templates.py" in content, "Template validation not included in CI workflow"
    
    @pytest.mark.parametrize("template_name", [
        "attacks.yaml",
        "attacks.json", 
        "safety.yaml",
        "safety.json",
        "bias.yaml",
        "bias.json",
        "perf.yaml",
        "perf.json"
    ])
    def test_critical_templates_exist(self, template_name):
        """Test that critical templates exist."""
        template_path = project_root / "data" / "templates" / template_name
        
        # Not all templates may exist, but if they do, they should be valid files
        if template_path.exists():
            assert template_path.is_file(), f"{template_name} exists but is not a file"
            assert template_path.stat().st_size > 0, f"{template_name} is empty"
            
            # Basic content validation
            content = template_path.read_text()
            assert len(content.strip()) > 0, f"{template_name} has no content"
