"""
Tests for Safety dataset loader.
"""

import pytest
from apps.orchestrator.suites.safety.loader import (
    detect_file_format, parse_safety_content, validate_safety_content
)
from apps.orchestrator.suites.safety.schemas import SafetyCategory


def test_detect_file_format():
    """Test file format detection."""
    # YAML format
    yaml_content = """
cases:
  - id: test1
    category: toxicity
    """
    assert detect_file_format(yaml_content) == "yaml"
    
    # JSON format
    json_content = '{"cases": [{"id": "test1", "category": "toxicity"}]}'
    assert detect_file_format(json_content) == "json"
    
    # JSONL format
    jsonl_content = '''{"id": "test1", "category": "toxicity"}
{"id": "test2", "category": "hate"}'''
    assert detect_file_format(jsonl_content) == "jsonl"


def test_parse_safety_yaml():
    """Test YAML parsing."""
    yaml_content = """
cases:
  - id: "test1"
    category: "toxicity"
    subtype: "explicit"
    description: "Test case"
    required: true
    inputs:
      user: "Test input"
    success:
      must_flag_any: ["toxicity"]
"""
    
    result = parse_safety_content(yaml_content)
    
    assert len(result.cases) == 1
    case = result.cases[0]
    assert case.id == "test1"
    assert case.category == SafetyCategory.TOXICITY
    assert case.subtype == "explicit"
    assert case.required is True
    assert case.inputs.user == "Test input"
    assert "toxicity" in result.taxonomy
    assert "explicit" in result.taxonomy["toxicity"]


def test_parse_safety_json():
    """Test JSON parsing."""
    json_content = '''
{
  "cases": [
    {
      "id": "test1",
      "category": "hate",
      "subtype": "targeted",
      "description": "Test case",
      "required": false,
      "inputs": {
        "prompt": "Test prompt"
      },
      "success": {
        "must_flag_any": ["hate"]
      }
    }
  ]
}
'''
    
    result = parse_safety_content(json_content)
    
    assert len(result.cases) == 1
    case = result.cases[0]
    assert case.id == "test1"
    assert case.category == SafetyCategory.HATE
    assert case.subtype == "targeted"
    assert case.required is False
    assert case.inputs.prompt == "Test prompt"
    assert "hate" in result.taxonomy
    assert "targeted" in result.taxonomy["hate"]


def test_parse_safety_jsonl():
    """Test JSONL parsing."""
    jsonl_content = '''{"id": "test1", "category": "violence", "subtype": "graphic", "description": "Test 1", "required": true, "inputs": {"user": "Input 1"}, "success": {"must_flag_any": ["violence"]}}
{"id": "test2", "category": "violence", "subtype": "threat", "description": "Test 2", "required": false, "inputs": {"retrieved": ["Passage 1"]}, "success": {"must_flag_any": ["violence"]}}'''
    
    result = parse_safety_content(jsonl_content)
    
    assert len(result.cases) == 2
    
    case1 = result.cases[0]
    assert case1.id == "test1"
    assert case1.category == SafetyCategory.VIOLENCE
    assert case1.subtype == "graphic"
    
    case2 = result.cases[1]
    assert case2.id == "test2"
    assert case2.subtype == "threat"
    
    assert "violence" in result.taxonomy
    assert set(result.taxonomy["violence"]) == {"graphic", "threat"}


def test_validate_safety_content_valid():
    """Test validation of valid safety content."""
    yaml_content = """
cases:
  - id: "test1"
    category: "toxicity"
    subtype: "explicit"
    description: "Test case"
    required: true
    inputs:
      user: "Test input"
    success:
      must_flag_any: ["toxicity"]
"""
    
    result = validate_safety_content(yaml_content)
    
    assert result.valid is True
    assert result.format == "yaml"
    assert result.counts_by_category["toxicity"] == 1
    assert result.required_count == 1
    assert "toxicity" in result.taxonomy
    assert len(result.errors) == 0


def test_validate_safety_content_invalid():
    """Test validation of invalid safety content."""
    invalid_content = "invalid yaml content: ["
    
    result = validate_safety_content(invalid_content)
    
    assert result.valid is False
    assert len(result.errors) > 0


def test_parse_safety_content_missing_inputs():
    """Test parsing with missing inputs (should fail validation)."""
    yaml_content = """
cases:
  - id: "test1"
    category: "toxicity"
    subtype: "explicit"
    description: "Test case"
    required: true
    inputs: {}
    success:
      must_flag_any: ["toxicity"]
"""
    
    with pytest.raises(ValueError, match="At least one of"):
        parse_safety_content(yaml_content)


def test_parse_safety_content_legacy_list():
    """Test parsing legacy list format."""
    json_content = '''[
  {
    "id": "test1",
    "category": "adult",
    "subtype": "explicit",
    "description": "Test case",
    "required": true,
    "inputs": {
      "user": "Test input"
    },
    "success": {
      "must_flag_any": ["adult"]
    }
  }
]'''
    
    result = parse_safety_content(json_content)
    
    assert len(result.cases) == 1
    case = result.cases[0]
    assert case.id == "test1"
    assert case.category == SafetyCategory.ADULT
    assert "adult" in result.taxonomy
