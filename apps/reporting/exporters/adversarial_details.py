"""Adversarial Details exporter for Red Team testing results."""

import logging
from typing import List, Dict, Any, Optional
from apps.orchestrator.suites.red_team.schemas import AttackResult

logger = logging.getLogger(__name__)


def generate_adversarial_details_data(
    attack_results: List[AttackResult],
    include_evidence: bool = True,
    mask_secrets: bool = True,
    selected_subtests: Optional[Dict[str, List[str]]] = None
) -> List[Dict[str, Any]]:
    """
    Generate adversarial details data for reporting.
    
    Args:
        attack_results: List of AttackResult objects
        include_evidence: Whether to include evidence snippets
        mask_secrets: Whether to mask secrets in evidence
        
    Returns:
        List of dictionaries suitable for JSON/XLSX export
    """
    if not attack_results:
        logger.info("No attack results provided for adversarial details")
        return []
    
    details_data = []
    
    for result in attack_results:
        # Extract evidence snippet
        evidence_snippet = ""
        if include_evidence and result.evidence:
            # Combine evidence into a readable snippet
            evidence_parts = []
            for key, value in result.evidence.items():
                if mask_secrets and any(secret_word in key.lower() for secret_word in ['key', 'token', 'password', 'secret']):
                    # Mask secret evidence
                    if len(value) > 8:
                        masked_value = value[:4] + "*" * (len(value) - 8) + value[-4:]
                    else:
                        masked_value = "*" * len(value)
                    evidence_parts.append(f"{key}: {masked_value}")
                else:
                    # Truncate long evidence for readability
                    truncated_value = value[:100] + "..." if len(value) > 100 else value
                    evidence_parts.append(f"{key}: {truncated_value}")
            
            evidence_snippet = " | ".join(evidence_parts)
        
        # Determine subtype from attack ID or evidence
        subtype = ""
        if hasattr(result, 'subtype') and result.subtype:
            subtype = result.subtype
        else:
            # Extract subtype from attack ID pattern
            id_parts = result.id.split('_')
            if len(id_parts) > 2:
                subtype = '_'.join(id_parts[2:])  # Everything after category
        
        # Create row data
        row_data = {
            'id': result.id,
            'category': result.category.value,
            'subtype': subtype,
            'required': _is_attack_required(result.id),
            'passed': result.passed,
            'reason': result.reason,
            'latency_ms': result.latency_ms or 0,
            'evidence_snippet': evidence_snippet,
            'turn_count': result.turn_count,
            'selected_subtests_snapshot': _format_selected_subtests(selected_subtests) if selected_subtests else ''
        }
        
        details_data.append(row_data)
    
    # Sort by category, then by required status, then by ID
    details_data.sort(key=lambda x: (x['category'], not x['required'], x['id']))
    
    logger.info(f"Generated adversarial details for {len(details_data)} attacks")
    return details_data


def _is_attack_required(attack_id: str) -> bool:
    """
    Determine if an attack is required based on its ID.
    
    This is a fallback method when the original AttackCase is not available.
    In practice, this information should be preserved in the AttackResult.
    
    Args:
        attack_id: Attack identifier
        
    Returns:
        True if attack is likely required
    """
    # Load attack cases to check required status
    try:
        from apps.orchestrator.suites.red_team.attack_loader import load_attack_cases
        attacks = load_attack_cases()
        
        for attack in attacks:
            if attack.id == attack_id:
                return attack.required
        
        # Fallback: assume certain attack types are required
        required_patterns = [
            'prompt_injection_direct',
            'prompt_injection_passage_embedded', 
            'data_extraction_system_prompt'
        ]
        
        return attack_id in required_patterns
        
    except Exception as e:
        logger.warning(f"Could not determine required status for {attack_id}: {e}")
        return False


def _format_selected_subtests(selected_subtests: Dict[str, List[str]]) -> str:
    """
    Format selected subtests for reporting.
    
    Args:
        selected_subtests: Dictionary mapping categories to selected subtests
        
    Returns:
        Formatted string representation of selected subtests
    """
    if not selected_subtests:
        return ""
    
    formatted_parts = []
    for category, subtests in selected_subtests.items():
        if subtests:
            formatted_parts.append(f"{category}: {', '.join(subtests)}")
    
    return " | ".join(formatted_parts)


def format_adversarial_details_for_excel(details_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Format adversarial details data for Excel export.
    
    Args:
        details_data: List of adversarial details dictionaries
        
    Returns:
        Dictionary with Excel sheet configuration
    """
    if not details_data:
        return {
            'sheet_name': 'Adversarial_Details',
            'headers': ['id', 'category', 'subtype', 'required', 'passed', 'reason', 'latency_ms', 'evidence_snippet', 'turn_count', 'selected_subtests_snapshot'],
            'data': [],
            'column_widths': {}
        }
    
    # Define column headers with friendly names
    headers = [
        'Attack ID',
        'Category', 
        'Subtype',
        'Required',
        'Defended',
        'Result Reason',
        'Latency (ms)',
        'Evidence Snippet',
        'Turn Count',
        'Selected Subtests'
    ]
    
    # Convert data to rows
    rows = []
    for item in details_data:
        row = [
            item['id'],
            item['category'].replace('_', ' ').title(),
            item['subtype'].replace('_', ' ').title() if item['subtype'] else '',
            'Yes' if item['required'] else 'No',
            'Yes' if item['passed'] else 'No',
            item['reason'],
            f"{item['latency_ms']:.1f}" if item['latency_ms'] else '0.0',
            item['evidence_snippet'],
            str(item['turn_count']),
            item.get('selected_subtests_snapshot', '')
        ]
        rows.append(row)
    
    # Define column widths for better readability
    column_widths = {
        'A': 25,  # Attack ID
        'B': 18,  # Category
        'C': 15,  # Subtype
        'D': 10,  # Required
        'E': 10,  # Defended
        'F': 40,  # Result Reason
        'G': 12,  # Latency
        'H': 50,  # Evidence Snippet
        'I': 12,  # Turn Count
        'J': 60   # Selected Subtests
    }
    
    return {
        'sheet_name': 'Adversarial_Details',
        'headers': headers,
        'data': rows,
        'column_widths': column_widths
    }


def generate_adversarial_summary_stats(attack_results: List[AttackResult]) -> Dict[str, Any]:
    """
    Generate summary statistics for adversarial testing.
    
    Args:
        attack_results: List of AttackResult objects
        
    Returns:
        Dictionary with summary statistics
    """
    if not attack_results:
        return {}
    
    total_attacks = len(attack_results)
    defended_attacks = sum(1 for r in attack_results if r.passed)
    defense_rate = (defended_attacks / total_attacks) * 100 if total_attacks > 0 else 0
    
    # Category breakdown
    category_stats = {}
    for result in attack_results:
        category = result.category.value
        if category not in category_stats:
            category_stats[category] = {'total': 0, 'defended': 0}
        category_stats[category]['total'] += 1
        if result.passed:
            category_stats[category]['defended'] += 1
    
    # Required attack analysis
    required_attacks = [r for r in attack_results if _is_attack_required(r.id)]
    required_defended = sum(1 for r in required_attacks if r.passed)
    required_defense_rate = (required_defended / len(required_attacks)) * 100 if required_attacks else 100
    
    # Latency analysis
    latencies = [r.latency_ms for r in attack_results if r.latency_ms is not None and r.latency_ms > 0]
    avg_latency = sum(latencies) / len(latencies) if latencies else 0
    max_latency = max(latencies) if latencies else 0
    
    return {
        'total_attacks': total_attacks,
        'defended_attacks': defended_attacks,
        'defense_rate': defense_rate,
        'required_attacks': len(required_attacks),
        'required_defended': required_defended,
        'required_defense_rate': required_defense_rate,
        'avg_latency_ms': avg_latency,
        'max_latency_ms': max_latency,
        'category_breakdown': category_stats,
        'failed_required_attacks': [r.id for r in required_attacks if not r.passed]
    }
