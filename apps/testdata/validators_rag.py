"""RAG-specific data validators."""

import logging
from typing import Dict, List, Set, Tuple, Any
from collections import Counter

logger = logging.getLogger(__name__)


class RAGValidationResult:
    """Results from RAG data validation."""
    
    def __init__(self):
        self.valid_count = 0
        self.invalid_count = 0
        self.duplicate_count = 0
        self.easy_count = 0
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.distribution_stats: Dict[str, Any] = {}


def validate_schema_and_refs(passages: List[Dict[str, Any]], qaset: List[Dict[str, Any]]) -> RAGValidationResult:
    """
    Validate schema and cross-references between passages and QA set.
    
    Args:
        passages: List of passage dictionaries
        qaset: List of QA dictionaries
        
    Returns:
        RAGValidationResult with validation details
    """
    result = RAGValidationResult()
    
    # Build passage ID index
    passage_ids = {p.id if hasattr(p, 'id') else p['id'] for p in passages}
    
    # Validate QA set references
    for qa in qaset:
        is_valid = True
        
        # Check if context IDs exist in passages
        if qa.get('contexts'):
            for context_id in qa['contexts']:
                if context_id not in passage_ids:
                    result.errors.append(f"QA {qa['qid']}: context_id '{context_id}' not found in passages")
                    is_valid = False
        
        # Check for easy cases (question == answer in same passage)
        question_lower = qa['question'].lower().strip()
        answer_lower = qa['expected_answer'].lower().strip()
        
        if question_lower == answer_lower:
            result.easy_count += 1
            result.warnings.append(f"QA {qa['qid']}: question and answer are identical (easy case)")
        
        # Check if answer appears verbatim in any passage
        for passage in passages:
            passage_text = passage.text if hasattr(passage, 'text') else passage['text']
            passage_id = passage.id if hasattr(passage, 'id') else passage['id']
            if answer_lower in passage_text.lower():
                result.easy_count += 1
                result.warnings.append(f"QA {qa['qid']}: answer found verbatim in passage {passage_id} (easy case)")
                break
        
        if is_valid:
            result.valid_count += 1
        else:
            result.invalid_count += 1
    
    return result


def detect_duplicates(qaset: List[Dict[str, Any]]) -> Tuple[int, List[str]]:
    """
    Detect duplicate questions in QA set.
    
    Args:
        qaset: List of QA dictionaries
        
    Returns:
        Tuple of (duplicate_count, duplicate_messages)
    """
    question_counts = Counter()
    qid_counts = Counter()
    duplicates = []
    
    for qa in qaset:
        question_normalized = qa['question'].lower().strip()
        question_counts[question_normalized] += 1
        qid_counts[qa['qid']] += 1
    
    duplicate_count = 0
    
    # Check for duplicate questions
    for question, count in question_counts.items():
        if count > 1:
            duplicate_count += count - 1
            duplicates.append(f"Question appears {count} times: '{question[:50]}...'")
    
    # Check for duplicate QIDs
    for qid, count in qid_counts.items():
        if count > 1:
            duplicates.append(f"QID appears {count} times: '{qid}'")
    
    return duplicate_count, duplicates


def compute_distribution_stats(qaset: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Compute distribution statistics for QA set.
    
    Args:
        qaset: List of QA dictionaries
        
    Returns:
        Dictionary with distribution statistics
    """
    stats = {
        'total_questions': len(qaset),
        'avg_question_length': 0,
        'avg_answer_length': 0,
        'questions_with_contexts': 0,
        'avg_contexts_per_question': 0,
        'difficulty_distribution': {},
        'category_distribution': {}
    }
    
    if not qaset:
        return stats
    
    question_lengths = []
    answer_lengths = []
    context_counts = []
    difficulties = []
    categories = []
    
    for qa in qaset:
        question_lengths.append(len(qa['question']))
        answer_lengths.append(len(qa['expected_answer']))
        
        if qa.get('contexts'):
            stats['questions_with_contexts'] += 1
            context_counts.append(len(qa['contexts']))
        else:
            context_counts.append(0)
        
        # Extract difficulty if available in metadata
        meta = qa.get('meta', {})
        if 'difficulty' in meta:
            difficulties.append(meta['difficulty'])
        
        if 'category' in meta:
            categories.append(meta['category'])
    
    stats['avg_question_length'] = sum(question_lengths) / len(question_lengths)
    stats['avg_answer_length'] = sum(answer_lengths) / len(answer_lengths)
    stats['avg_contexts_per_question'] = sum(context_counts) / len(context_counts)
    
    # Distribution stats
    if difficulties:
        stats['difficulty_distribution'] = dict(Counter(difficulties))
    
    if categories:
        stats['category_distribution'] = dict(Counter(categories))
    
    return stats


def validate_rag_data(passages: List[Dict[str, Any]], qaset: List[Dict[str, Any]]) -> RAGValidationResult:
    """
    Comprehensive RAG data validation.
    
    Args:
        passages: List of passage dictionaries
        qaset: List of QA dictionaries
        
    Returns:
        Complete RAGValidationResult
    """
    logger.info(f"Validating RAG data: {len(passages)} passages, {len(qaset)} QA pairs")
    
    # Schema and reference validation
    result = validate_schema_and_refs(passages, qaset)
    
    # Duplicate detection
    duplicate_count, duplicate_messages = detect_duplicates(qaset)
    result.duplicate_count = duplicate_count
    result.warnings.extend(duplicate_messages)
    
    # Distribution statistics
    result.distribution_stats = compute_distribution_stats(qaset)
    
    logger.info(f"RAG validation complete: {result.valid_count} valid, {result.invalid_count} invalid, {result.duplicate_count} duplicates, {result.easy_count} easy cases")
    
    return result
