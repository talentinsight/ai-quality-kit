"""
Safety Dataset Loader.

Loads and parses Safety datasets from YAML, JSON, or JSONL formats.
Normalizes all formats to the same Python model.
"""

import json
import yaml
from typing import Dict, List, Any, Optional
from .schemas import SafetyFile, SafetyCase, NormalizedSafety, SafetyValidationResult


def detect_file_format(content: str) -> str:
    """
    Detect if content is YAML, JSON, or JSONL format.
    
    Args:
        content: File content as string
        
    Returns:
        Format string: "yaml", "json", or "jsonl"
    """
    content = content.strip()
    
    # Check for JSONL format (multiple lines, each starting with {)
    lines = [line.strip() for line in content.split('\n') if line.strip() and not line.strip().startswith('#')]
    if len(lines) > 1 and all(line.startswith('{') for line in lines):
        return "jsonl"
    
    # Check for JSON format (starts with { or [)
    if content.startswith('{') or content.startswith('['):
        return "json"
    
    # Default to YAML for everything else
    return "yaml"


def parse_safety_content(content: str) -> NormalizedSafety:
    """
    Parse safety content from YAML, JSON, or JSONL format.
    
    Args:
        content: File content as string
        
    Returns:
        NormalizedSafety object
        
    Raises:
        ValueError: If parsing fails or format is invalid
    """
    file_format = detect_file_format(content)
    
    try:
        if file_format == "jsonl":
            # Parse JSONL format (one JSON object per line)
            cases_data = []
            taxonomy_meta = {}
            
            for line_num, line in enumerate(content.strip().split('\n'), 1):
                line = line.strip()
                if not line or line.startswith('#'):  # Skip empty lines and comments
                    continue
                
                try:
                    obj = json.loads(line)
                    
                    # Check if this is a metadata line
                    if obj.get("type") == "meta" and "taxonomy" in obj:
                        taxonomy_meta = obj["taxonomy"]
                    else:
                        # This is a SafetyCase
                        cases_data.append(obj)
                        
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid JSON on line {line_num}: {e}")
                    
        elif file_format == "json":
            data = json.loads(content)
            
            # Handle both object with "cases" key and direct list
            if isinstance(data, dict) and "cases" in data:
                cases_data = data["cases"]
                taxonomy_meta = data.get("taxonomy", {})
            elif isinstance(data, list):
                cases_data = data
                taxonomy_meta = {}
            else:
                raise ValueError("JSON file must contain either an object with 'cases' key or a direct list of cases")
                
        else:  # yaml
            data = yaml.safe_load(content)
            
            # Handle both object with "cases" key and direct list
            if isinstance(data, dict) and "cases" in data:
                cases_data = data["cases"]
                taxonomy_meta = data.get("taxonomy", {})
            elif isinstance(data, list):
                cases_data = data
                taxonomy_meta = {}
            else:
                raise ValueError("YAML file must contain either an object with 'cases' key or a direct list of cases")
                
    except (json.JSONDecodeError, yaml.YAMLError) as e:
        raise ValueError(f"Invalid {file_format.upper()} format: {e}")
    
    # Create SafetyFile object and validate
    safety_file = SafetyFile(cases=cases_data)
    
    # Build taxonomy from cases
    taxonomy = discover_taxonomy(safety_file.cases)
    
    # Merge with metadata taxonomy (file cases take precedence)
    for category, subtypes in taxonomy_meta.items():
        if category not in taxonomy:
            taxonomy[category] = []
        # Add metadata subtypes that aren't already present
        for subtype in subtypes:
            if subtype not in taxonomy[category]:
                taxonomy[category].append(subtype)
    
    return NormalizedSafety(cases=safety_file.cases, taxonomy=taxonomy)


def discover_taxonomy(cases: List[SafetyCase]) -> Dict[str, List[str]]:
    """
    Discover taxonomy from safety cases.
    
    Args:
        cases: List of safety cases
        
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
    
    # Sort subtypes for consistency
    for category in taxonomy:
        taxonomy[category].sort()
    
    return taxonomy


def validate_safety_content(content: str) -> SafetyValidationResult:
    """
    Validate safety file content and return validation result.
    
    Args:
        content: File content as string
        
    Returns:
        SafetyValidationResult with validation details
    """
    warnings = []
    errors = []
    
    try:
        file_format = detect_file_format(content)
        normalized = parse_safety_content(content)
        
        # Count cases by category
        counts_by_category = {}
        required_count = 0
        
        for case in normalized.cases:
            category = case.category.value
            counts_by_category[category] = counts_by_category.get(category, 0) + 1
            
            if case.required:
                required_count += 1
        
        # Check for potential issues
        if required_count == 0:
            warnings.append("No required cases found - all cases are optional")
        
        # Check for empty categories
        for category, subtypes in normalized.taxonomy.items():
            if not subtypes:
                warnings.append(f"Category '{category}' has no subtypes")
        
        return SafetyValidationResult(
            valid=True,
            format=file_format,
            counts_by_category=counts_by_category,
            required_count=required_count,
            taxonomy=normalized.taxonomy,
            warnings=warnings,
            errors=errors
        )
        
    except Exception as e:
        return SafetyValidationResult(
            valid=False,
            format="unknown",
            counts_by_category={},
            required_count=0,
            taxonomy={},
            warnings=warnings,
            errors=[str(e)]
        )


def load_safety_file(file_path: str) -> NormalizedSafety:
    """
    Load safety file from disk.
    
    Args:
        file_path: Path to the safety file
        
    Returns:
        NormalizedSafety object
        
    Raises:
        ValueError: If file cannot be loaded or parsed
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return parse_safety_content(content)
    except FileNotFoundError:
        raise ValueError(f"Safety file not found: {file_path}")
    except Exception as e:
        raise ValueError(f"Failed to load safety file: {e}")


def convert_to_legacy_format(normalized: NormalizedSafety) -> List[Dict[str, Any]]:
    """
    Convert normalized safety data to legacy format if needed.
    
    Args:
        normalized: NormalizedSafety object
        
    Returns:
        List of dictionaries in legacy format
    """
    # For now, just return the cases as dictionaries
    # This can be extended if legacy compatibility is needed
    return [case.dict() for case in normalized.cases]
