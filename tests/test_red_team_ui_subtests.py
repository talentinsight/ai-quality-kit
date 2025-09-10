"""Tests for Red Team UI subtests functionality."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch
from apps.orchestrator.suites.red_team.runner import _filter_attacks_by_subtests
from apps.orchestrator.suites.red_team.schemas import AttackCase, Category, Channel, AttackStep, SuccessCriteria


class TestRedTeamSubtests:
    """Test Red Team subtests filtering functionality."""
    
    def test_filter_attacks_by_subtests_basic(self):
        """Test basic subtest filtering functionality."""
        # Create mock attack cases
        attacks = [
            AttackCase(
                id="test1",
                category=Category.PROMPT_INJECTION,
                subtype="direct",
                description="Direct injection",
                required=False,
                steps=[AttackStep(role=Channel.USER, content="test")],
                success=SuccessCriteria()
            ),
            AttackCase(
                id="test2", 
                category=Category.PROMPT_INJECTION,
                subtype="indirect",
                description="Indirect injection",
                required=False,
                steps=[AttackStep(role=Channel.USER, content="test")],
                success=SuccessCriteria()
            ),
            AttackCase(
                id="test3",
                category=Category.JAILBREAK,
                subtype="role_play",
                description="Role play jailbreak",
                required=False,
                steps=[AttackStep(role=Channel.USER, content="test")],
                success=SuccessCriteria()
            )
        ]
        
        # Test filtering with specific subtests
        subtests_config = {
            "prompt_injection": ["direct"],
            "jailbreak": []  # No jailbreak subtests selected
        }
        
        filtered = _filter_attacks_by_subtests(attacks, subtests_config)
        
        # Should only include direct prompt injection
        assert len(filtered) == 1
        assert filtered[0].id == "test1"
        assert filtered[0].subtype == "direct"
    
    def test_filter_attacks_by_subtests_no_subtype(self):
        """Test filtering when attack has no subtype."""
        attacks = [
            AttackCase(
                id="test1",
                category=Category.PROMPT_INJECTION,
                description="Generic injection",
                required=False,
                steps=[AttackStep(role=Channel.USER, content="test")],
                success=SuccessCriteria()
            )
        ]
        
        subtests_config = {
            "prompt_injection": ["direct", "indirect"]
        }
        
        filtered = _filter_attacks_by_subtests(attacks, subtests_config)
        
        # Should include attack without subtype when category is enabled
        assert len(filtered) == 1
        assert filtered[0].id == "test1"
    
    def test_filter_attacks_by_subtests_empty_config(self):
        """Test filtering with empty subtests config."""
        attacks = [
            AttackCase(
                id="test1",
                category=Category.PROMPT_INJECTION,
                subtype="direct",
                description="Direct injection",
                required=False,
                steps=[AttackStep(role=Channel.USER, content="test")],
                success=SuccessCriteria()
            )
        ]
        
        # Empty config should return all attacks
        filtered = _filter_attacks_by_subtests(attacks, {})
        assert len(filtered) == 1
        
        # None config should return all attacks
        filtered = _filter_attacks_by_subtests(attacks, None)
        assert len(filtered) == 1


class TestAttacksTemplates:
    """Test attacks template files and endpoints."""
    
    def test_template_files_exist(self):
        """Test that all template files exist and have content."""
        template_dir = Path(__file__).parent.parent / "data" / "templates"
        
        template_files = [
            "attacks.template.yaml",
            "attacks.template.jsonl", 
            "attacks.template.txt"
        ]
        
        for template_file in template_files:
            file_path = template_dir / template_file
            assert file_path.exists(), f"Template file {template_file} should exist"
            
            # Check file has content
            content = file_path.read_text(encoding='utf-8')
            assert len(content) > 0, f"Template file {template_file} should not be empty"
            
            # Check for expected content based on file type
            if template_file.endswith('.yaml'):
                assert 'attacks:' in content
                assert 'category:' in content
                assert 'steps:' in content
            elif template_file.endswith('.jsonl'):
                lines = [line.strip() for line in content.split('\n') if line.strip()]
                assert len(lines) > 0
                # Each line should be valid JSON
                import json
                for line in lines:
                    data = json.loads(line)
                    assert 'id' in data
                    assert 'category' in data
            elif template_file.endswith('.txt'):
                assert 'prompt_injection' in content
                assert 'jailbreak' in content
    
    def test_yaml_template_structure(self):
        """Test YAML template has correct structure."""
        template_path = Path(__file__).parent.parent / "data" / "templates" / "attacks.template.yaml"
        
        import yaml
        with open(template_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        assert 'attacks' in data
        attacks = data['attacks']
        assert len(attacks) > 0
        
        # Check first attack has required fields
        attack = attacks[0]
        required_fields = ['id', 'category', 'description', 'steps', 'success']
        for field in required_fields:
            assert field in attack, f"Attack should have {field} field"
        
        # Check steps structure
        steps = attack['steps']
        assert len(steps) > 0
        step = steps[0]
        assert 'role' in step
        assert 'content' in step
        
        # Check success criteria
        success = attack['success']
        assert isinstance(success, dict)
    
    def test_jsonl_template_structure(self):
        """Test JSONL template has correct structure."""
        template_path = Path(__file__).parent.parent / "data" / "templates" / "attacks.template.jsonl"
        
        import json
        with open(template_path, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip()]
        
        assert len(lines) > 0
        
        for line in lines:
            attack = json.loads(line)
            
            # Check required fields
            required_fields = ['id', 'category', 'description', 'steps', 'success']
            for field in required_fields:
                assert field in attack, f"Attack should have {field} field"
            
            # Check steps structure
            steps = attack['steps']
            assert len(steps) > 0
            step = steps[0]
            assert 'role' in step
            assert 'content' in step


class TestRedTeamOrchestrator:
    """Test Red Team integration with orchestrator."""
    
    def test_red_team_config_parsing(self):
        """Test Red Team configuration parsing in orchestrator."""
        from apps.orchestrator.run_tests import TestRunner, OrchestratorRequest
        
        # Mock request with Red Team subtests config
        request = OrchestratorRequest(
            target_mode="api",
            provider="mock",
            model="test",
            suites=["red_team"],
            options={
                "red_team": {
                    "enabled": True,
                    "subtests": {
                        "prompt_injection": ["direct", "indirect"],
                        "jailbreak": ["role_play"],
                        "data_extraction": [],
                        "context_poisoning": ["ignore_citations"],
                        "social_engineering": ["authority"]
                    }
                }
            }
        )
        
        runner = TestRunner(request)
        
        # Check that Red Team config is accessible
        assert runner.request.options is not None
        assert "red_team" in runner.request.options
        red_team_config = runner.request.options["red_team"]
        assert red_team_config["enabled"] is True
        assert "subtests" in red_team_config
        
        subtests = red_team_config["subtests"]
        assert "prompt_injection" in subtests
        assert len(subtests["prompt_injection"]) == 2
        assert "direct" in subtests["prompt_injection"]
        assert "indirect" in subtests["prompt_injection"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
