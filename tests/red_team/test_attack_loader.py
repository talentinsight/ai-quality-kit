"""Tests for Red Team attack loader."""

import pytest
import tempfile
import yaml
from pathlib import Path
from apps.orchestrator.suites.red_team.attack_loader import (
    load_attack_cases, 
    get_attack_statistics,
    validate_required_coverage
)
from apps.orchestrator.suites.red_team.schemas import Category


class TestAttackLoader:
    """Test suite for attack loader functionality."""
    
    def test_load_attack_cases_valid_file(self):
        """Test loading valid attack cases from YAML file."""
        # Create temporary YAML file
        test_data = {
            'attacks': [
                {
                    'id': 'test_attack_1',
                    'category': 'prompt_injection',
                    'description': 'Test attack 1',
                    'required': True,
                    'steps': [{'role': 'user', 'content': 'Test content'}],
                    'success': {'must_not_contain_any': ['secret']}
                },
                {
                    'id': 'test_attack_2', 
                    'category': 'data_extraction',
                    'description': 'Test attack 2',
                    'required': False,
                    'steps': [{'role': 'user', 'content': 'Extract data'}],
                    'success': {'leak_types': ['api_key']}
                }
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(test_data, f)
            temp_path = f.name
        
        try:
            # Load attack cases
            attacks = load_attack_cases(temp_path)
            
            # Verify results
            assert len(attacks) == 2
            assert attacks[0].id == 'test_attack_1'
            assert attacks[0].category == Category.PROMPT_INJECTION
            assert attacks[0].required is True
            assert len(attacks[0].steps) == 1
            
            assert attacks[1].id == 'test_attack_2'
            assert attacks[1].category == Category.DATA_EXTRACTION
            assert attacks[1].required is False
            
        finally:
            Path(temp_path).unlink()
    
    def test_load_attack_cases_missing_file(self):
        """Test loading from non-existent file returns empty list."""
        attacks = load_attack_cases('/nonexistent/path.yaml')
        assert attacks == []
    
    def test_load_attack_cases_invalid_yaml(self):
        """Test loading invalid YAML returns empty list."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("invalid: yaml: content: [")
            temp_path = f.name
        
        try:
            attacks = load_attack_cases(temp_path)
            assert attacks == []
        finally:
            Path(temp_path).unlink()
    
    def test_load_attack_cases_category_filter(self):
        """Test filtering attacks by category."""
        test_data = {
            'attacks': [
                {
                    'id': 'prompt_attack',
                    'category': 'prompt_injection',
                    'description': 'Prompt injection test',
                    'required': True,
                    'steps': [{'role': 'user', 'content': 'Test'}],
                    'success': {}
                },
                {
                    'id': 'data_attack',
                    'category': 'data_extraction', 
                    'description': 'Data extraction test',
                    'required': False,
                    'steps': [{'role': 'user', 'content': 'Extract'}],
                    'success': {}
                }
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(test_data, f)
            temp_path = f.name
        
        try:
            # Filter by prompt injection
            attacks = load_attack_cases(temp_path, category_filter=Category.PROMPT_INJECTION)
            assert len(attacks) == 1
            assert attacks[0].id == 'prompt_attack'
            
            # Filter by data extraction
            attacks = load_attack_cases(temp_path, category_filter=Category.DATA_EXTRACTION)
            assert len(attacks) == 1
            assert attacks[0].id == 'data_attack'
            
        finally:
            Path(temp_path).unlink()
    
    def test_load_attack_cases_required_only(self):
        """Test filtering for required attacks only."""
        test_data = {
            'attacks': [
                {
                    'id': 'required_attack',
                    'category': 'prompt_injection',
                    'description': 'Required test',
                    'required': True,
                    'steps': [{'role': 'user', 'content': 'Test'}],
                    'success': {}
                },
                {
                    'id': 'optional_attack',
                    'category': 'data_extraction',
                    'description': 'Optional test', 
                    'required': False,
                    'steps': [{'role': 'user', 'content': 'Test'}],
                    'success': {}
                }
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(test_data, f)
            temp_path = f.name
        
        try:
            attacks = load_attack_cases(temp_path, required_only=True)
            assert len(attacks) == 1
            assert attacks[0].id == 'required_attack'
            assert attacks[0].required is True
            
        finally:
            Path(temp_path).unlink()
    
    def test_get_attack_statistics(self):
        """Test attack statistics generation."""
        # Create mock attacks
        from apps.orchestrator.suites.red_team.schemas import AttackCase, AttackStep, SuccessCriteria, Channel
        
        attacks = [
            AttackCase(
                id='attack1',
                category=Category.PROMPT_INJECTION,
                description='Test 1',
                required=True,
                steps=[AttackStep(role=Channel.USER, content='test')],
                success=SuccessCriteria()
            ),
            AttackCase(
                id='attack2', 
                category=Category.PROMPT_INJECTION,
                description='Test 2',
                required=False,
                steps=[AttackStep(role=Channel.PASSAGE, content='test')],
                success=SuccessCriteria()
            ),
            AttackCase(
                id='attack3',
                category=Category.DATA_EXTRACTION,
                description='Test 3',
                required=True,
                steps=[AttackStep(role=Channel.USER, content='test')],
                success=SuccessCriteria()
            )
        ]
        
        stats = get_attack_statistics(attacks)
        
        assert stats['total'] == 3
        assert stats['required'] == 2
        assert stats['categories']['prompt_injection'] == 2
        assert stats['categories']['data_extraction'] == 1
        assert stats['channels']['user'] == 2
        assert stats['channels']['passage'] == 1
    
    def test_validate_required_coverage(self):
        """Test validation of required category coverage."""
        from apps.orchestrator.suites.red_team.schemas import AttackCase, AttackStep, SuccessCriteria, Channel
        
        # Create attacks with required coverage
        attacks = [
            AttackCase(
                id='prompt_required',
                category=Category.PROMPT_INJECTION,
                description='Required prompt test',
                required=True,
                steps=[AttackStep(role=Channel.USER, content='test')],
                success=SuccessCriteria()
            ),
            AttackCase(
                id='data_required',
                category=Category.DATA_EXTRACTION,
                description='Required data test',
                required=True,
                steps=[AttackStep(role=Channel.USER, content='test')],
                success=SuccessCriteria()
            ),
            AttackCase(
                id='optional_attack',
                category=Category.JAILBREAK,
                description='Optional test',
                required=False,
                steps=[AttackStep(role=Channel.USER, content='test')],
                success=SuccessCriteria()
            )
        ]
        
        # Test valid coverage
        required_categories = ['prompt_injection', 'data_extraction']
        assert validate_required_coverage(attacks, required_categories) is True
        
        # Test missing coverage
        required_categories = ['prompt_injection', 'data_extraction', 'social_engineering']
        assert validate_required_coverage(attacks, required_categories) is False
    
    def test_load_attack_cases_validation_error(self):
        """Test handling of validation errors in attack cases."""
        test_data = {
            'attacks': [
                {
                    'id': 'valid_attack',
                    'category': 'prompt_injection',
                    'description': 'Valid attack',
                    'required': True,
                    'steps': [{'role': 'user', 'content': 'Test'}],
                    'success': {}
                },
                {
                    # Missing required fields
                    'id': 'invalid_attack',
                    'category': 'invalid_category',  # Invalid category
                    # Missing description, steps, success
                }
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(test_data, f)
            temp_path = f.name
        
        try:
            attacks = load_attack_cases(temp_path)
            # Should only load the valid attack, skip the invalid one
            assert len(attacks) == 1
            assert attacks[0].id == 'valid_attack'
            
        finally:
            Path(temp_path).unlink()
