"""
Performance Dataset Loader.

Handles loading and parsing of performance datasets from YAML, JSON, and JSONL formats.
"""

import json
import yaml
from typing import Dict, List
from pydantic import ValidationError

from .schemas import PerfCase, PerfFile, NormalizedPerf, PerfValidationResult


def detect_file_format(content: str) -> str:
    """
    Detect file format based on content.
    
    Args:
        content: File content as string
        
    Returns:
        Format string: "yaml", "json", or "jsonl"
    """
    content = content.strip()
    
    # Check for JSONL (multiple lines, each starting with {)
    lines = content.split('\n')
    if len(lines) > 1:
        non_empty_lines = [line.strip() for line in lines if line.strip()]
        if len(non_empty_lines) > 1 and all(line.startswith('{') for line in non_empty_lines):
            return "jsonl"
    
    # Check for JSON (starts with { or [)
    if content.startswith('{') or content.startswith('['):
        return "json"
    
    # Default to YAML for everything else
    return "yaml"


def parse_perf_content(content: str) -> NormalizedPerf:
    """
    Parse performance content from YAML, JSON, or JSONL format.
    
    Args:
        content: File content as string
        
    Returns:
        NormalizedPerf object
        
    Raises:
        ValueError: If parsing fails or format is invalid
    """
    file_format = detect_file_format(content)
    
    try:
        if file_format == "jsonl":
            # Parse JSONL format (one JSON object per line)
            scenarios_data = []
            
            for line_num, line in enumerate(content.strip().split('\n'), 1):
                line = line.strip()
                if not line:  # Skip empty lines
                    continue
                
                try:
                    obj = json.loads(line)
                    
                    # Check if this is a metadata line (ignore)
                    if obj.get("type") == "meta":
                        continue
                    
                    # This is a PerfCase
                    scenarios_data.append(obj)
                        
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid JSON on line {line_num}: {e}")
                    
        elif file_format == "json":
            data = json.loads(content)
            
            # Handle both object with "scenarios" key and direct list
            if isinstance(data, dict) and "scenarios" in data:
                scenarios_data = data["scenarios"]
            elif isinstance(data, list):
                scenarios_data = data
            else:
                raise ValueError("JSON file must contain either an object with 'scenarios' key or a direct list of scenarios")
                
        else:  # yaml
            data = yaml.safe_load(content)
            
            # Handle both object with "scenarios" key and direct list
            if isinstance(data, dict) and "scenarios" in data:
                scenarios_data = data["scenarios"]
            elif isinstance(data, list):
                scenarios_data = data
            else:
                raise ValueError("YAML file must contain either an object with 'scenarios' key or a direct list of scenarios")
                
    except (json.JSONDecodeError, yaml.YAMLError) as e:
        raise ValueError(f"Invalid {file_format.upper()} format: {e}")
    
    # Create PerfFile object and validate
    perf_file = PerfFile(scenarios=scenarios_data)
    
    # Build taxonomy from scenarios
    taxonomy = discover_taxonomy(perf_file.scenarios)
    
    return NormalizedPerf(scenarios=perf_file.scenarios, taxonomy=taxonomy)


def discover_taxonomy(scenarios: List[PerfCase]) -> Dict[str, List[str]]:
    """
    Discover taxonomy from performance scenarios.
    
    Args:
        scenarios: List of performance scenarios
        
    Returns:
        Dictionary mapping categories to lists of subtypes
    """
    taxonomy = {}
    
    for scenario in scenarios:
        category = scenario.category.value
        subtype = scenario.subtype
        
        if category not in taxonomy:
            taxonomy[category] = []
        
        if subtype not in taxonomy[category]:
            taxonomy[category].append(subtype)
    
    # Sort subtypes for consistent ordering
    for category in taxonomy:
        taxonomy[category].sort()
    
    return taxonomy


def validate_perf_content(content: str) -> PerfValidationResult:
    """
    Validate performance content and return validation result.
    
    Args:
        content: File content as string
        
    Returns:
        PerfValidationResult with validation details
    """
    try:
        file_format = detect_file_format(content)
        normalized_perf = parse_perf_content(content)
        
        # Count scenarios by category
        counts_by_category = {}
        required_count = 0
        
        for scenario in normalized_perf.scenarios:
            category = scenario.category.value
            counts_by_category[category] = counts_by_category.get(category, 0) + 1
            if scenario.required:
                required_count += 1
        
        # Generate warnings
        warnings = []
        
        # Check for missing input templates
        for scenario in normalized_perf.scenarios:
            if not scenario.request.input_template.strip():
                warnings.append(f"Scenario {scenario.id}: input_template is empty")
        
        # Check for very short durations
        for scenario in normalized_perf.scenarios:
            if scenario.load.duration_sec < 10:
                warnings.append(f"Scenario {scenario.id}: duration_sec={scenario.load.duration_sec} may be too short for reliable metrics")
        
        # Check for high concurrency without warning
        for scenario in normalized_perf.scenarios:
            if scenario.load.concurrency and scenario.load.concurrency > 50:
                warnings.append(f"Scenario {scenario.id}: concurrency={scenario.load.concurrency} is quite high")
        
        # Check for very high RPS targets
        for scenario in normalized_perf.scenarios:
            if scenario.load.rate_rps and scenario.load.rate_rps > 100:
                warnings.append(f"Scenario {scenario.id}: rate_rps={scenario.load.rate_rps} is quite high")
        
        # Check for memory scenarios without memory thresholds
        for scenario in normalized_perf.scenarios:
            if scenario.category.value == "memory" and (not scenario.thresholds or scenario.thresholds.memory_peak_mb_max is None):
                warnings.append(f"Scenario {scenario.id}: memory category should have memory_peak_mb_max threshold")
        
        return PerfValidationResult(
            valid=True,
            format=file_format,
            counts_by_category=counts_by_category,
            taxonomy=normalized_perf.taxonomy,
            warnings=warnings,
            required_count=required_count
        )
        
    except ValidationError as e:
        errors = []
        for error in e.errors():
            field = " -> ".join(str(x) for x in error["loc"])
            errors.append(f"{field}: {error['msg']}")
        
        return PerfValidationResult(
            valid=False,
            format="unknown",
            counts_by_category={},
            taxonomy={},
            errors=errors
        )
        
    except ValueError as e:
        return PerfValidationResult(
            valid=False,
            format="unknown", 
            counts_by_category={},
            taxonomy={},
            errors=[str(e)]
        )


def load_perf_file(file_path: str) -> NormalizedPerf:
    """
    Load performance dataset from file.
    
    Args:
        file_path: Path to performance dataset file
        
    Returns:
        NormalizedPerf object
        
    Raises:
        ValueError: If file cannot be loaded or parsed
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return parse_perf_content(content)
    except FileNotFoundError:
        raise ValueError(f"Performance file not found: {file_path}")
    except Exception as e:
        raise ValueError(f"Failed to load performance file {file_path}: {e}")
