"""
Test Performance Dataset Loader Parity.

Tests for ensuring YAML, JSON, and JSONL formats produce equivalent results.
"""

import pytest
import json
import yaml
from apps.orchestrator.suites.performance.loader import (
    parse_perf_content, validate_perf_content, discover_taxonomy
)


def test_perf_loader_yaml_json_parity():
    """Test that YAML and JSON formats produce identical normalized results."""
    
    # Sample performance data
    perf_data = {
        "scenarios": [
            {
                "id": "cold_start_test",
                "category": "cold_start",
                "subtype": "closed_loop",
                "description": "Cold start latency test",
                "required": True,
                "request": {
                    "input_template": "What is artificial intelligence?",
                    "repeats": 3
                },
                "load": {
                    "mode": "closed_loop",
                    "concurrency": 1,
                    "duration_sec": 30,
                    "think_time_ms": 1000
                },
                "segmentation": {
                    "cold_n": 2,
                    "warmup_exclude_n": 0,
                    "phase_headers": True
                },
                "thresholds": {
                    "p95_ms_max": 3000,
                    "error_rate_max": 0.05
                }
            },
            {
                "id": "throughput_test",
                "category": "throughput",
                "subtype": "open_loop",
                "description": "Throughput test",
                "required": True,
                "request": {
                    "input_template": "Explain machine learning"
                },
                "load": {
                    "mode": "open_loop",
                    "rate_rps": 10,
                    "duration_sec": 60
                },
                "thresholds": {
                    "p95_ms_max": 2000,
                    "throughput_min_rps": 8
                }
            }
        ]
    }
    
    # Convert to YAML and JSON
    yaml_content = yaml.dump(perf_data, default_flow_style=False)
    json_content = json.dumps(perf_data, indent=2)
    
    # Parse both formats
    yaml_result = parse_perf_content(yaml_content)
    json_result = parse_perf_content(json_content)
    
    # Compare scenarios
    assert len(yaml_result.scenarios) == len(json_result.scenarios)
    assert len(yaml_result.scenarios) == 2
    
    for yaml_scenario, json_scenario in zip(yaml_result.scenarios, json_result.scenarios):
        assert yaml_scenario.id == json_scenario.id
        assert yaml_scenario.category == json_scenario.category
        assert yaml_scenario.subtype == json_scenario.subtype
        assert yaml_scenario.description == json_scenario.description
        assert yaml_scenario.required == json_scenario.required
        
        # Compare request config
        assert yaml_scenario.request.input_template == json_scenario.request.input_template
        
        # Compare load config
        assert yaml_scenario.load.mode == json_scenario.load.mode
        assert yaml_scenario.load.duration_sec == json_scenario.load.duration_sec
    
    # Compare taxonomy
    assert yaml_result.taxonomy == json_result.taxonomy
    expected_taxonomy = {
        "cold_start": ["closed_loop"],
        "throughput": ["open_loop"]
    }
    assert yaml_result.taxonomy == expected_taxonomy


def test_perf_loader_jsonl_parity():
    """Test that JSONL format produces equivalent results to JSON."""
    
    # Sample scenarios as individual objects
    scenarios = [
        {
            "id": "memory_test",
            "category": "memory",
            "subtype": "soak",
            "description": "Memory usage test",
            "required": False,
            "request": {
                "input_template": "Generate a long response about climate change"
            },
            "load": {
                "mode": "closed_loop",
                "concurrency": 4,
                "duration_sec": 300
            },
            "thresholds": {
                "memory_peak_mb_max": 512
            }
        },
        {
            "id": "stress_test",
            "category": "stress",
            "subtype": "spike",
            "description": "High load stress test",
            "required": True,
            "request": {
                "input_template": "Explain quantum computing"
            },
            "load": {
                "mode": "closed_loop",
                "concurrency": 20,
                "duration_sec": 90
            },
            "thresholds": {
                "p95_ms_max": 5000,
                "error_rate_max": 0.10
            }
        }
    ]
    
    # Create JSON and JSONL formats
    json_data = {"scenarios": scenarios}
    json_content = json.dumps(json_data, indent=2)
    
    jsonl_content = "\n".join(json.dumps(scenario) for scenario in scenarios)
    
    # Parse both formats
    json_result = parse_perf_content(json_content)
    jsonl_result = parse_perf_content(jsonl_content)
    
    # Compare results
    assert len(json_result.scenarios) == len(jsonl_result.scenarios)
    assert len(json_result.scenarios) == 2
    
    for json_scenario, jsonl_scenario in zip(json_result.scenarios, jsonl_result.scenarios):
        assert json_scenario.id == jsonl_scenario.id
        assert json_scenario.category == jsonl_scenario.category
        assert json_scenario.subtype == jsonl_scenario.subtype
        assert json_scenario.required == jsonl_scenario.required
    
    # Compare taxonomy
    assert json_result.taxonomy == jsonl_result.taxonomy
    expected_taxonomy = {
        "memory": ["soak"],
        "stress": ["spike"]
    }
    assert json_result.taxonomy == expected_taxonomy


def test_perf_taxonomy_discovery():
    """Test taxonomy discovery from performance scenarios."""
    
    scenarios_data = [
        {"id": "test1", "category": "cold_start", "subtype": "closed_loop", "description": "Test", "required": True, 
         "request": {"input_template": "test"}, "load": {"mode": "closed_loop", "concurrency": 1, "duration_sec": 10}},
        {"id": "test2", "category": "cold_start", "subtype": "open_loop", "description": "Test", "required": True,
         "request": {"input_template": "test"}, "load": {"mode": "open_loop", "rate_rps": 5, "duration_sec": 10}},
        {"id": "test3", "category": "warm", "subtype": "closed_loop", "description": "Test", "required": True,
         "request": {"input_template": "test"}, "load": {"mode": "closed_loop", "concurrency": 4, "duration_sec": 10}},
        {"id": "test4", "category": "throughput", "subtype": "sustained", "description": "Test", "required": True,
         "request": {"input_template": "test"}, "load": {"mode": "open_loop", "rate_rps": 10, "duration_sec": 10}},
        {"id": "test5", "category": "stress", "subtype": "spike", "description": "Test", "required": False,
         "request": {"input_template": "test"}, "load": {"mode": "closed_loop", "concurrency": 50, "duration_sec": 10}},
        {"id": "test6", "category": "memory", "subtype": "soak", "description": "Test", "required": False,
         "request": {"input_template": "test"}, "load": {"mode": "closed_loop", "concurrency": 8, "duration_sec": 10}}
    ]
    
    json_content = json.dumps({"scenarios": scenarios_data})
    result = parse_perf_content(json_content)
    
    expected_taxonomy = {
        "cold_start": ["closed_loop", "open_loop"],
        "warm": ["closed_loop"],
        "throughput": ["sustained"],
        "stress": ["spike"],
        "memory": ["soak"]
    }
    
    assert result.taxonomy == expected_taxonomy


def test_perf_validation_success():
    """Test successful performance dataset validation."""
    
    valid_content = """
scenarios:
  - id: "test_scenario"
    category: "warm"
    subtype: "baseline"
    description: "Basic warm performance test"
    required: true
    request:
      input_template: "What is machine learning?"
    load:
      mode: "closed_loop"
      concurrency: 2
      duration_sec: 30
    thresholds:
      p95_ms_max: 2000
      error_rate_max: 0.02
"""
    
    validation_result = validate_perf_content(valid_content)
    
    assert validation_result.valid is True
    assert validation_result.format == "yaml"
    assert validation_result.counts_by_category["warm"] == 1
    assert validation_result.taxonomy["warm"] == ["baseline"]
    assert validation_result.required_count == 1
    assert len(validation_result.errors) == 0


def test_perf_validation_errors():
    """Test performance dataset validation with errors."""
    
    invalid_content = """
scenarios:
  - id: ""
    category: "invalid_category"
    subtype: "test"
    description: "Invalid test"
    required: true
    request:
      input_template: ""
    load:
      mode: "invalid_mode"
      duration_sec: -1
"""
    
    validation_result = validate_perf_content(invalid_content)
    
    assert validation_result.valid is False
    assert len(validation_result.errors) > 0
    assert validation_result.counts_by_category == {}
    assert validation_result.taxonomy == {}


def test_perf_validation_warnings():
    """Test performance dataset validation with warnings."""
    
    content_with_warnings = """
scenarios:
  - id: "short_test"
    category: "cold_start"
    subtype: "quick"
    description: "Very short test"
    required: true
    request:
      input_template: "Quick test"
    load:
      mode: "closed_loop"
      concurrency: 100
      duration_sec: 5
    thresholds:
      p95_ms_max: 1000
"""
    
    validation_result = validate_perf_content(content_with_warnings)
    
    assert validation_result.valid is True
    assert len(validation_result.warnings) > 0
    # Should warn about short duration and high concurrency
    warning_text = " ".join(validation_result.warnings)
    assert "duration_sec=5" in warning_text or "concurrency=100" in warning_text


def test_perf_legacy_list_format():
    """Test that legacy list format (without 'scenarios' key) works."""
    
    legacy_content = """
- id: "legacy_test"
  category: "throughput"
  subtype: "legacy"
  description: "Legacy format test"
  required: true
  request:
    input_template: "Legacy test prompt"
  load:
    mode: "open_loop"
    rate_rps: 5
    duration_sec: 60
"""
    
    result = parse_perf_content(legacy_content)
    
    assert len(result.scenarios) == 1
    assert result.scenarios[0].id == "legacy_test"
    assert result.scenarios[0].category.value == "throughput"
    assert result.scenarios[0].subtype == "legacy"
    assert result.taxonomy["throughput"] == ["legacy"]
