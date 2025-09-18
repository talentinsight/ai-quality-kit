"""Attack case loader for Red Team testing with YAML validation."""

import os
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
import yaml
from pydantic import ValidationError

from .schemas import AttackCase, Category
from .attacks_schemas import (
    AttacksFile,
    AttacksValidationResult,
    parse_attacks_content,
    validate_attacks_content,
    discover_taxonomy,
    convert_to_legacy_format,
    detect_file_format
)

logger = logging.getLogger(__name__)


def load_attack_cases(
    file_path: Optional[str] = None,
    category_filter: Optional[Category] = None,
    required_only: bool = False
) -> List[AttackCase]:
    """
    Load attack cases from YAML file with validation and filtering.
    
    Args:
        file_path: Path to attacks YAML file. Defaults to data/red_team/attacks.yaml
        category_filter: Only return attacks of this category
        required_only: Only return required attacks
        
    Returns:
        List of validated AttackCase objects
        
    Raises:
        Never crashes - returns empty list and logs warnings on errors
    """
    if file_path is None:
        # Default to data/red_team/attacks.yaml relative to project root
        project_root = Path(__file__).parent.parent.parent.parent.parent
        file_path = project_root / "data" / "red_team" / "attacks.yaml"
    
    file_path = Path(file_path)
    
    # Check if file exists
    if not file_path.exists():
        logger.warning(f"Red Team attacks file not found: {file_path}")
        return []
    
    try:
        # Load YAML content
        with open(file_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        if not data or 'attacks' not in data:
            logger.warning(f"No 'attacks' section found in {file_path}")
            return []
        
        attacks = []
        for attack_data in data['attacks']:
            try:
                # Validate and create AttackCase
                attack = AttackCase(**attack_data)
                attacks.append(attack)
            except ValidationError as e:
                logger.warning(f"Invalid attack case in {file_path}: {attack_data.get('id', 'unknown')} - {e}")
                continue
        
        # Apply filters
        filtered_attacks = attacks
        
        if category_filter:
            filtered_attacks = [a for a in filtered_attacks if a.category == category_filter]
        
        if required_only:
            filtered_attacks = [a for a in filtered_attacks if a.required]
        
        logger.info(f"Loaded {len(filtered_attacks)} attack cases from {file_path}")
        if category_filter:
            logger.info(f"Filtered to category: {category_filter}")
        if required_only:
            logger.info(f"Filtered to required attacks only")
        
        return filtered_attacks
        
    except yaml.YAMLError as e:
        logger.warning(f"YAML parsing error in {file_path}: {e}")
        return []
    except Exception as e:
        logger.warning(f"Unexpected error loading attacks from {file_path}: {e}")
        return []


def get_attack_statistics(attacks: List[AttackCase]) -> dict:
    """
    Get statistics about loaded attack cases.
    
    Args:
        attacks: List of AttackCase objects
        
    Returns:
        Dictionary with attack statistics
    """
    if not attacks:
        return {"total": 0, "required": 0, "categories": {}, "channels": {}}
    
    stats = {
        "total": len(attacks),
        "required": sum(1 for a in attacks if a.required),
        "categories": {},
        "channels": {}
    }
    
    # Count by category
    for attack in attacks:
        category = attack.category.value
        stats["categories"][category] = stats["categories"].get(category, 0) + 1
    
    # Count by channel (from first step of each attack)
    for attack in attacks:
        if attack.steps:
            channel = attack.steps[0].role.value
            stats["channels"][channel] = stats["channels"].get(channel, 0) + 1
    
    return stats


def validate_required_coverage(attacks: List[AttackCase], required_categories: List[str]) -> bool:
    """
    Validate that all required categories have at least one required attack.
    
    Args:
        attacks: List of AttackCase objects
        required_categories: List of category names that must have required attacks
        
    Returns:
        True if all required categories are covered
    """
    required_attacks = [a for a in attacks if a.required]
    covered_categories = {a.category.value for a in required_attacks}
    
    missing_categories = set(required_categories) - covered_categories
    
    if missing_categories:
        logger.warning(f"Missing required attacks for categories: {missing_categories}")
        return False
    
    return True




def load_attacks_file(file_path: str) -> Tuple[List[AttackCase], Dict[str, List[str]]]:
    """
    Load attacks from YAML or JSON file with simplified schema.
    
    Args:
        file_path: Path to the attacks file (.yaml, .yml, or .json)
        
    Returns:
        Tuple of (attack_cases, taxonomy)
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse content using simplified schema
        attacks_file = parse_attacks_content(content)
        
        # Convert to legacy AttackCase objects for compatibility
        legacy_attacks = convert_to_legacy_format(attacks_file)
        attack_cases = []
        
        for attack_data in legacy_attacks:
            try:
                attack = AttackCase(**attack_data)
                attack_cases.append(attack)
            except ValidationError as e:
                logger.warning(f"Skipping invalid attack {attack_data.get('id', 'unknown')}: {e}")
        
        # Discover taxonomy
        taxonomy = discover_taxonomy(attacks_file.attacks)
        
        file_format = detect_file_format(content)
        logger.info(f"Loaded {len(attack_cases)} attacks from {file_format.upper()} file with {len(taxonomy)} categories")
        
        return attack_cases, taxonomy
        
    except Exception as e:
        logger.error(f"Failed to load attacks file: {e}")
        return [], {}


def validate_attacks_file_content(content: str) -> AttacksValidationResult:
    """
    Validate attacks file content using simplified schema.
    
    Args:
        content: File content as string
        
    Returns:
        AttacksValidationResult with validation status and metadata
    """
    return validate_attacks_content(content)


def load_single_file_dataset(file_path: str) -> Tuple[List[AttackCase], Dict[str, Any]]:
    """
    Load single-file dataset format.
    
    Args:
        file_path: Path to the attacks file
        
    Returns:
        Tuple of (attack_cases, metadata)
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        data = yaml.safe_load(content)
        
        if isinstance(data, dict) and 'attacks' in data:
            # Single-file format
            attacks = []
            for attack_data in data['attacks']:
                try:
                    attack = AttackCase(**attack_data)
                    attacks.append(attack)
                except ValidationError as e:
                    logger.warning(f"Skipping invalid attack case: {e}")
                    continue
            
            metadata = {
                'version': data.get('version', 'unknown'),
                'suite': data.get('suite', 'red_team'),
                'total_attacks': len(attacks)
            }
            
            return attacks, metadata
        else:
            # Legacy format
            attacks, _ = load_attacks_file(file_path)
            metadata = {'format': 'legacy', 'total_attacks': len(attacks)}
            return attacks, metadata
            
    except Exception as e:
        logger.error(f"Error loading single-file dataset {file_path}: {e}")
        return [], {}


def validate_dataset_from_content(content: str) -> AttacksValidationResult:
    """
    Validate dataset content and return validation result.
    
    Args:
        content: File content as string
        
    Returns:
        AttacksValidationResult with validation details
    """
    return validate_attacks_file_content(content)


def load_attacks_with_overrides(file_path: str) -> Tuple[List[AttackCase], Dict[str, Any]]:
    """
    Load attacks with override support.
    
    Args:
        file_path: Path to the attacks file
        
    Returns:
        Tuple of (attack_cases, overrides)
    """
    try:
        attacks, metadata = load_single_file_dataset(file_path)
        
        # Extract overrides from metadata if available
        overrides = metadata.get('overrides', {})
        
        return attacks, overrides
        
    except Exception as e:
        logger.error(f"Error loading attacks with overrides {file_path}: {e}")
        return [], {}
