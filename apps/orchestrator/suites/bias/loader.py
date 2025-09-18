"""
Bias Dataset Loader.

Handles loading and parsing of bias datasets from YAML, JSON, and JSONL formats.
"""

import json
import yaml
from typing import Dict, List
from pydantic import ValidationError

from .schemas import BiasCase, BiasFile, NormalizedBias, BiasValidationResult


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


def parse_bias_content(content: str) -> NormalizedBias:
    """
    Parse bias content from YAML, JSON, or JSONL format.
    
    Args:
        content: File content as string
        
    Returns:
        NormalizedBias object
        
    Raises:
        ValueError: If parsing fails or format is invalid
    """
    file_format = detect_file_format(content)
    
    try:
        if file_format == "jsonl":
            # Parse JSONL format (one JSON object per line)
            cases_data = []
            
            for line_num, line in enumerate(content.strip().split('\n'), 1):
                line = line.strip()
                if not line:  # Skip empty lines
                    continue
                
                try:
                    obj = json.loads(line)
                    
                    # Check if this is a metadata line (ignore)
                    if obj.get("type") == "meta":
                        continue
                    
                    # This is a BiasCase
                    cases_data.append(obj)
                        
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid JSON on line {line_num}: {e}")
                    
        elif file_format == "json":
            data = json.loads(content)
            
            # Handle both object with "cases" key and direct list
            if isinstance(data, dict) and "cases" in data:
                cases_data = data["cases"]
            elif isinstance(data, list):
                cases_data = data
            else:
                raise ValueError("JSON file must contain either an object with 'cases' key or a direct list of cases")
                
        else:  # yaml
            data = yaml.safe_load(content)
            
            # Handle both object with "cases" key and direct list
            if isinstance(data, dict) and "cases" in data:
                cases_data = data["cases"]
            elif isinstance(data, list):
                cases_data = data
            else:
                raise ValueError("YAML file must contain either an object with 'cases' key or a direct list of cases")
                
    except (json.JSONDecodeError, yaml.YAMLError) as e:
        raise ValueError(f"Invalid {file_format.upper()} format: {e}")
    
    # Create BiasFile object and validate
    bias_file = BiasFile(cases=cases_data)
    
    # Build taxonomy from cases
    taxonomy = discover_taxonomy(bias_file.cases)
    
    return NormalizedBias(cases=bias_file.cases, taxonomy=taxonomy)


def discover_taxonomy(cases: List[BiasCase]) -> Dict[str, List[str]]:
    """
    Discover taxonomy from bias cases.
    
    Args:
        cases: List of bias cases
        
    Returns:
        Dictionary mapping categories to lists of subtypes
    """
    taxonomy = {}
    
    for case in cases:
        category = case.category.value
        subtype = case.subtype
        
        if category not in taxonomy:
            taxonomy[category] = []
        
        if subtype not in taxonomy[category]:
            taxonomy[category].append(subtype)
    
    # Sort subtypes for consistent ordering
    for category in taxonomy:
        taxonomy[category].sort()
    
    return taxonomy


def validate_bias_content(content: str) -> BiasValidationResult:
    """
    Validate bias content and return validation result.
    
    Args:
        content: File content as string
        
    Returns:
        BiasValidationResult with validation details
    """
    try:
        file_format = detect_file_format(content)
        normalized_bias = parse_bias_content(content)
        
        # Count cases by category
        counts_by_category = {}
        required_count = 0
        
        for case in normalized_bias.cases:
            category = case.category.value
            counts_by_category[category] = counts_by_category.get(category, 0) + 1
            if case.required:
                required_count += 1
        
        # Generate warnings
        warnings = []
        
        # Check for missing persona placeholders
        for case in normalized_bias.cases:
            if "${persona}" not in case.prompt_template:
                warnings.append(f"Case {case.id}: prompt_template missing ${persona} placeholder")
        
        # Check for small repeat counts
        for case in normalized_bias.cases:
            if case.repeats < 3:
                warnings.append(f"Case {case.id}: repeats={case.repeats} may be too small for reliable statistics")
        
        # Check for intersectionality naming
        for case in normalized_bias.cases:
            if "_x_" in case.subtype or "_and_" in case.subtype:
                warnings.append(f"Case {case.id}: subtype '{case.subtype}' appears to be intersectional")
        
        return BiasValidationResult(
            valid=True,
            format=file_format,
            counts_by_category=counts_by_category,
            taxonomy=normalized_bias.taxonomy,
            warnings=warnings,
            required_count=required_count
        )
        
    except ValidationError as e:
        errors = []
        for error in e.errors():
            field = " -> ".join(str(x) for x in error["loc"])
            errors.append(f"{field}: {error['msg']}")
        
        return BiasValidationResult(
            valid=False,
            format="unknown",
            counts_by_category={},
            taxonomy={},
            errors=errors
        )
        
    except ValueError as e:
        return BiasValidationResult(
            valid=False,
            format="unknown", 
            counts_by_category={},
            taxonomy={},
            errors=[str(e)]
        )


def load_bias_file(file_path: str) -> NormalizedBias:
    """
    Load bias dataset from file.
    
    Args:
        file_path: Path to bias dataset file
        
    Returns:
        NormalizedBias object
        
    Raises:
        ValueError: If file cannot be loaded or parsed
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return parse_bias_content(content)
    except FileNotFoundError:
        raise ValueError(f"Bias file not found: {file_path}")
    except Exception as e:
        raise ValueError(f"Failed to load bias file {file_path}: {e}")
