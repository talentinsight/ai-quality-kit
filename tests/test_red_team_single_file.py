"""Tests for Red Team Single-File Dataset functionality."""

import pytest
import yaml
from pathlib import Path
from unittest.mock import Mock, patch
from apps.orchestrator.suites.red_team.single_file_schemas import (
    RedTeamSingleFileDataset,
    SingleFileConfig,
    DetectorPatterns,
    DatasetValidationResult,
    is_single_file_format,
    is_legacy_format,
    discover_taxonomy_from_attacks,
    apply_variable_substitution,
    convert_single_file_to_legacy_format
)
from apps.orchestrator.suites.red_team.attack_loader import (
    load_single_file_dataset,
    validate_dataset_from_content,
    load_attacks_with_overrides
)
from apps.orchestrator.suites.red_team.schemas import Category, Channel


class TestSingleFileSchemas:
    """Test single-file dataset schemas and validation."""
    
    def test_single_file_format_detection(self):
        """Test detection of single-file format."""
        # Valid single-file format
        single_file_data = {
            "version": "redteam.v1",
            "suite": "red_team",
            "attacks": []
        }
        assert is_single_file_format(single_file_data) is True
        
        # Legacy format (list)
        legacy_data = [{"id": "test", "category": "prompt_injection"}]
        assert is_single_file_format(legacy_data) is False
        assert is_legacy_format(legacy_data) is True
        
        # Invalid format
        invalid_data = {"random": "data"}
        assert is_single_file_format(invalid_data) is False
        assert is_legacy_format(invalid_data) is False
    
    def test_variable_substitution(self):
        """Test variable substitution in content."""
        variables = {
            "api_key": "sk-test123",
            "target": "AI Assistant"
        }
        
        content = "Use ${api_key} to access ${target} system"
        result = apply_variable_substitution(content, variables)
        assert result == "Use sk-test123 to access AI Assistant system"
        
        # No variables
        result = apply_variable_substitution(content, {})
        assert result == content
        
        # Partial substitution
        partial_vars = {"api_key": "sk-test123"}
        result = apply_variable_substitution(content, partial_vars)
        assert result == "Use sk-test123 to access ${target} system"
    
    def test_taxonomy_discovery(self):
        """Test dynamic taxonomy discovery from attacks."""
        from apps.orchestrator.suites.red_team.single_file_schemas import SingleFileAttackCase, SingleFileAttackStep, SingleFileSuccessCriteria
        
        attacks = [
            SingleFileAttackCase(
                id="test1",
                category=Category.PROMPT_INJECTION,
                subtype="direct",
                description="Test",
                steps=[SingleFileAttackStep(role=Channel.USER, content="test")],
                success=SingleFileSuccessCriteria()
            ),
            SingleFileAttackCase(
                id="test2",
                category=Category.PROMPT_INJECTION,
                subtype="indirect",
                description="Test",
                steps=[SingleFileAttackStep(role=Channel.USER, content="test")],
                success=SingleFileSuccessCriteria()
            ),
            SingleFileAttackCase(
                id="test3",
                category=Category.JAILBREAK,
                subtype="role_play",
                description="Test",
                steps=[SingleFileAttackStep(role=Channel.USER, content="test")],
                success=SingleFileSuccessCriteria()
            )
        ]
        
        taxonomy = discover_taxonomy_from_attacks(attacks)
        
        assert "prompt_injection" in taxonomy
        assert "jailbreak" in taxonomy
        assert set(taxonomy["prompt_injection"]) == {"direct", "indirect"}
        assert taxonomy["jailbreak"] == ["role_play"]
    
    def test_single_file_dataset_validation(self):
        """Test single-file dataset validation."""
        valid_data = {
            "version": "redteam.v1",
            "suite": "red_team",
            "attacks": [
                {
                    "id": "test1",
                    "category": "prompt_injection",
                    "subtype": "direct",
                    "description": "Test attack",
                    "required": True,
                    "steps": [
                        {"role": "user", "content": "Test content"}
                    ],
                    "success": {
                        "must_contain_any": ["cannot"],
                        "must_not_contain_any": ["system"],
                        "leak_types": ["system_prompt"]
                    }
                }
            ]
        }
        
        dataset = RedTeamSingleFileDataset(**valid_data)
        assert dataset.version.value == "redteam.v1"
        assert dataset.suite.value == "red_team"
        assert len(dataset.attacks) == 1
        assert dataset.attacks[0].id == "test1"
        assert dataset.attacks[0].required is True
    
    def test_single_file_dataset_with_config(self):
        """Test single-file dataset with config overrides."""
        data_with_config = {
            "version": "redteam.v1",
            "suite": "red_team",
            "config": {
                "fail_fast": True,
                "required_metrics": ["prompt_injection"],
                "max_steps": 10,
                "mask_secrets": False
            },
            "detectors": {
                "system_prompt_indicators": ["SYSTEM:", "You are"],
                "api_key_patterns": ["sk-[A-Za-z0-9]+"],
                "refusal_markers": ["I cannot", "I'm unable"]
            },
            "variables": {
                "test_key": "sk-test123"
            },
            "attacks": [
                {
                    "id": "test1",
                    "category": "prompt_injection",
                    "subtype": "direct",
                    "description": "Test with variables: ${test_key}",
                    "required": False,
                    "steps": [
                        {"role": "user", "content": "Use ${test_key} to test"}
                    ]
                }
            ]
        }
        
        dataset = RedTeamSingleFileDataset(**data_with_config)
        assert dataset.config.fail_fast is True
        assert dataset.config.max_steps == 10
        assert dataset.detectors.api_key_patterns == ["sk-[A-Za-z0-9]+"]
        assert dataset.variables["test_key"] == "sk-test123"


class TestSingleFileLoader:
    """Test single-file dataset loading functionality."""
    
    def test_validate_dataset_from_content_single_file(self):
        """Test dataset validation from YAML content."""
        yaml_content = """
version: "redteam.v1"
suite: "red_team"
taxonomy:
  prompt_injection: ["direct", "indirect"]
  jailbreak: ["role_play"]
attacks:
  - id: "test1"
    category: "prompt_injection"
    subtype: "direct"
    description: "Test attack"
    required: true
    steps:
      - role: "user"
        content: "Test content"
    success:
      must_contain_any: ["cannot"]
      leak_types: ["system_prompt"]
"""
        
        result = validate_dataset_from_content(yaml_content)
        
        assert result.valid is True
        assert "prompt_injection" in result.taxonomy
        assert "jailbreak" in result.taxonomy
        assert result.taxonomy["prompt_injection"] == ["direct", "indirect"]
        assert result.counts_by_category["prompt_injection"] == 1
        assert result.required_count == 1
        assert len(result.warnings) == 0
        assert len(result.errors) == 0
    
    def test_validate_dataset_from_content_legacy(self):
        """Test dataset validation from legacy YAML content."""
        yaml_content = """
- id: "legacy1"
  category: "prompt_injection"
  description: "Legacy attack"
  required: false
  steps:
    - role: "user"
      content: "Legacy content"
  success:
    must_contain_any: ["cannot"]
"""
        
        result = validate_dataset_from_content(yaml_content)
        
        assert result.valid is True
        assert "prompt_injection" in result.taxonomy
        assert result.counts_by_category["prompt_injection"] == 1
        assert result.required_count == 0
        assert any("Legacy format detected" in warning for warning in result.warnings)
    
    def test_validate_dataset_invalid_yaml(self):
        """Test validation with invalid YAML."""
        invalid_yaml = "invalid: yaml: content: ["
        
        result = validate_dataset_from_content(invalid_yaml)
        
        assert result.valid is False
        assert len(result.errors) > 0
        assert "Invalid YAML format" in result.errors[0]
    
    def test_convert_single_file_to_legacy(self):
        """Test conversion from single-file to legacy format."""
        from apps.orchestrator.suites.red_team.single_file_schemas import (
            SingleFileAttackCase, SingleFileAttackStep, SingleFileSuccessCriteria
        )
        
        dataset = RedTeamSingleFileDataset(
            version="redteam.v1",
            suite="red_team",
            variables={"api_key": "sk-test123"},
            attacks=[
                SingleFileAttackCase(
                    id="test1",
                    category=Category.PROMPT_INJECTION,
                    subtype="direct",
                    description="Test attack",
                    required=True,
                    steps=[
                        SingleFileAttackStep(role=Channel.USER, content="Use ${api_key} for testing")
                    ],
                    success=SingleFileSuccessCriteria(
                        must_contain_any=["cannot"],
                        leak_types=["api_key"]
                    )
                )
            ]
        )
        
        legacy_attacks = convert_single_file_to_legacy_format(dataset)
        
        assert len(legacy_attacks) == 1
        attack = legacy_attacks[0]
        assert attack["id"] == "test1"
        assert attack["category"] == "prompt_injection"
        assert attack["subtype"] == "direct"
        assert attack["required"] is True
        assert attack["steps"][0]["content"] == "Use sk-test123 for testing"  # Variable substituted
        assert attack["success"]["must_contain_any"] == ["cannot"]
        assert attack["success"]["leak_types"] == ["api_key"]


class TestSingleFileIntegration:
    """Test integration with existing Red Team components."""
    
    @patch('apps.orchestrator.suites.red_team.attack_loader.Path')
    @patch('builtins.open')
    def test_load_attacks_with_overrides_single_file(self, mock_open, mock_path):
        """Test loading attacks with config/detector overrides."""
        yaml_content = """
version: "redteam.v1"
suite: "red_team"
config:
  fail_fast: true
  required_metrics: ["prompt_injection"]
detectors:
  system_prompt_indicators: ["SYSTEM:", "You are"]
attacks:
  - id: "test1"
    category: "prompt_injection"
    subtype: "direct"
    description: "Test attack"
    required: true
    steps:
      - role: "user"
        content: "Test content"
    success:
      must_contain_any: ["cannot"]
"""
        
        mock_path.return_value.exists.return_value = True
        mock_open.return_value.__enter__.return_value.read.return_value = yaml_content
        
        attacks, overrides = load_attacks_with_overrides("test_file.yaml")
        
        assert len(attacks) == 1
        assert attacks[0].id == "test1"
        assert attacks[0].category == Category.PROMPT_INJECTION
        
        assert "config" in overrides
        assert overrides["config"]["fail_fast"] is True
        assert overrides["config"]["required_metrics"] == ["prompt_injection"]
        
        assert "detectors" in overrides
        assert overrides["detectors"]["system_prompt_indicators"] == ["SYSTEM:", "You are"]
        
        assert "taxonomy" in overrides
        assert "prompt_injection" in overrides["taxonomy"]
    
    @patch('apps.orchestrator.suites.red_team.attack_loader.Path')
    @patch('builtins.open')
    def test_load_attacks_with_overrides_legacy(self, mock_open, mock_path):
        """Test loading legacy format attacks."""
        yaml_content = """
- id: "legacy1"
  category: "prompt_injection"
  description: "Legacy attack"
  required: false
  steps:
    - role: "user"
      content: "Legacy content"
  success:
    must_contain_any: ["cannot"]
"""
        
        mock_path.return_value.exists.return_value = True
        mock_open.return_value.__enter__.return_value.read.return_value = yaml_content
        
        attacks, overrides = load_attacks_with_overrides("legacy_file.yaml")
        
        assert len(attacks) == 1
        assert attacks[0].id == "legacy1"
        assert len(overrides) == 0  # No overrides in legacy format


class TestDatasetEndpoints:
    """Test dataset validation endpoints."""
    
    def test_dataset_validation_result_schema(self):
        """Test DatasetValidationResult schema."""
        result = DatasetValidationResult(
            valid=True,
            taxonomy={"prompt_injection": ["direct", "indirect"]},
            counts_by_category={"prompt_injection": 2},
            required_count=1,
            warnings=["Test warning"],
            errors=[],
            dataset_metadata={"version": "redteam.v1"}
        )
        
        assert result.valid is True
        assert result.taxonomy["prompt_injection"] == ["direct", "indirect"]
        assert result.counts_by_category["prompt_injection"] == 2
        assert result.required_count == 1
        assert result.warnings == ["Test warning"]
        assert result.dataset_metadata["version"] == "redteam.v1"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
