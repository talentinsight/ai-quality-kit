"""
Simple Ground Truth Evaluator for rule-based text similarity.

This evaluator provides fast, offline ground truth evaluation without requiring
external LLM APIs. It uses multiple text similarity metrics to assess answer quality.
"""

import re
import math
from typing import Dict, List, Tuple, Set
from collections import Counter
import logging

logger = logging.getLogger(__name__)


class SimpleGroundTruthEvaluator:
    """
    Rule-based ground truth evaluator using text similarity metrics.
    
    Features:
    - Keyword overlap analysis
    - BLEU score calculation
    - Exact phrase matching
    - Number/entity extraction
    - Semantic pattern matching
    - No external API dependencies
    """
    
    def __init__(self):
        """Initialize the evaluator with default patterns."""
        self.number_pattern = re.compile(r'\b\d+(?:\.\d+)?(?:%|ms|MB|GB|TB)?\b')
        self.entity_patterns = {
            'dates': re.compile(r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b\d{4}-\d{2}-\d{2}\b'),
            'times': re.compile(r'\b\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM)?\b', re.IGNORECASE),
            'percentages': re.compile(r'\b\d+(?:\.\d+)?%\b'),
            'currencies': re.compile(r'\$\d+(?:,\d{3})*(?:\.\d{2})?|\b\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:USD|EUR|GBP)\b'),
            'urls': re.compile(r'https?://[^\s]+'),
            'emails': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
        }
    
    def evaluate(self, answer: str, ground_truth: str) -> Dict[str, float]:
        """
        Evaluate answer against ground truth using multiple metrics.
        
        Args:
            answer: Generated answer text
            ground_truth: Expected answer text
            
        Returns:
            Dictionary with evaluation metrics:
            {
                'overall_score': float,
                'keyword_overlap': float,
                'bleu_score': float,
                'exact_match': float,
                'entity_match': float,
                'semantic_similarity': float
            }
        """
        if not answer or not ground_truth:
            return self._empty_result()
        
        # Normalize texts
        answer_norm = self._normalize_text(answer)
        ground_truth_norm = self._normalize_text(ground_truth)
        
        # Calculate individual metrics
        keyword_overlap = self._calculate_keyword_overlap(answer_norm, ground_truth_norm)
        bleu_score = self._calculate_bleu_score(answer_norm, ground_truth_norm)
        exact_match = self._calculate_exact_match(answer_norm, ground_truth_norm)
        entity_match = self._calculate_entity_match(answer, ground_truth)
        semantic_similarity = self._calculate_semantic_similarity(answer_norm, ground_truth_norm)
        
        # Calculate weighted overall score
        overall_score = (
            0.25 * keyword_overlap +
            0.20 * bleu_score +
            0.15 * exact_match +
            0.25 * entity_match +
            0.15 * semantic_similarity
        )
        
        return {
            'overall_score': round(overall_score, 3),
            'keyword_overlap': round(keyword_overlap, 3),
            'bleu_score': round(bleu_score, 3),
            'exact_match': round(exact_match, 3),
            'entity_match': round(entity_match, 3),
            'semantic_similarity': round(semantic_similarity, 3)
        }
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison."""
        # Convert to lowercase
        text = text.lower()
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        # Remove punctuation except important ones
        text = re.sub(r'[^\w\s\-\.\%\$]', '', text)
        return text
    
    def _calculate_keyword_overlap(self, answer: str, ground_truth: str) -> float:
        """Calculate keyword overlap ratio."""
        answer_words = set(answer.split())
        ground_truth_words = set(ground_truth.split())
        
        if not ground_truth_words:
            return 0.0
        
        intersection = answer_words.intersection(ground_truth_words)
        return len(intersection) / len(ground_truth_words)
    
    def _calculate_bleu_score(self, answer: str, ground_truth: str, n: int = 2) -> float:
        """Calculate simplified BLEU score for n-grams."""
        answer_tokens = answer.split()
        ground_truth_tokens = ground_truth.split()
        
        if not answer_tokens or not ground_truth_tokens:
            return 0.0
        
        # Calculate n-gram precision
        total_score = 0.0
        for i in range(1, n + 1):
            answer_ngrams = self._get_ngrams(answer_tokens, i)
            ground_truth_ngrams = self._get_ngrams(ground_truth_tokens, i)
            
            if not answer_ngrams:
                continue
            
            matches = 0
            for ngram in answer_ngrams:
                if ngram in ground_truth_ngrams:
                    matches += min(answer_ngrams[ngram], ground_truth_ngrams[ngram])
            
            precision = matches / sum(answer_ngrams.values()) if answer_ngrams else 0
            total_score += precision
        
        # Brevity penalty
        bp = min(1.0, len(answer_tokens) / max(len(ground_truth_tokens), 1))
        
        return bp * (total_score / n) if n > 0 else 0.0
    
    def _get_ngrams(self, tokens: List[str], n: int) -> Counter:
        """Get n-grams from token list."""
        ngrams = []
        for i in range(len(tokens) - n + 1):
            ngrams.append(' '.join(tokens[i:i + n]))
        return Counter(ngrams)
    
    def _calculate_exact_match(self, answer: str, ground_truth: str) -> float:
        """Calculate exact phrase matching score."""
        # Split into phrases (by punctuation)
        answer_phrases = re.split(r'[.!?;,]', answer)
        ground_truth_phrases = re.split(r'[.!?;,]', ground_truth)
        
        answer_phrases = [p.strip() for p in answer_phrases if p.strip()]
        ground_truth_phrases = [p.strip() for p in ground_truth_phrases if p.strip()]
        
        if not ground_truth_phrases:
            return 0.0
        
        matches = 0
        for gt_phrase in ground_truth_phrases:
            for ans_phrase in answer_phrases:
                if gt_phrase in ans_phrase or ans_phrase in gt_phrase:
                    matches += 1
                    break
        
        return matches / len(ground_truth_phrases)
    
    def _calculate_entity_match(self, answer: str, ground_truth: str) -> float:
        """Calculate entity matching score (numbers, dates, etc.)."""
        total_score = 0.0
        entity_count = 0
        
        for entity_type, pattern in self.entity_patterns.items():
            answer_entities = set(pattern.findall(answer))
            ground_truth_entities = set(pattern.findall(ground_truth))
            
            if ground_truth_entities:
                entity_count += 1
                intersection = answer_entities.intersection(ground_truth_entities)
                score = len(intersection) / len(ground_truth_entities)
                total_score += score
        
        return total_score / entity_count if entity_count > 0 else 0.0
    
    def _calculate_semantic_similarity(self, answer: str, ground_truth: str) -> float:
        """Calculate semantic similarity using simple heuristics."""
        # Check for semantic patterns
        semantic_patterns = [
            (r'\b(?:yes|no|true|false)\b', 0.3),  # Boolean answers
            (r'\b\d+(?:\.\d+)?\s*(?:ms|seconds?|minutes?|hours?)\b', 0.2),  # Time units
            (r'\b\d+(?:\.\d+)?%\b', 0.2),  # Percentages
            (r'\b(?:api|endpoint|url|http)\b', 0.1),  # Technical terms
            (r'\b(?:sla|service|level|agreement)\b', 0.1),  # Business terms
            (r'\b(?:uptime|availability|response)\b', 0.1),  # Performance terms
        ]
        
        similarity_score = 0.0
        for pattern, weight in semantic_patterns:
            answer_matches = len(re.findall(pattern, answer, re.IGNORECASE))
            ground_truth_matches = len(re.findall(pattern, ground_truth, re.IGNORECASE))
            
            if ground_truth_matches > 0:
                pattern_score = min(answer_matches / ground_truth_matches, 1.0)
                similarity_score += weight * pattern_score
        
        # Add basic cosine similarity for remaining content
        answer_words = set(answer.split())
        ground_truth_words = set(ground_truth.split())
        
        if answer_words and ground_truth_words:
            intersection = answer_words.intersection(ground_truth_words)
            union = answer_words.union(ground_truth_words)
            jaccard_similarity = len(intersection) / len(union) if union else 0
            similarity_score += 0.1 * jaccard_similarity
        
        return min(similarity_score, 1.0)
    
    def _empty_result(self) -> Dict[str, float]:
        """Return empty result for invalid inputs."""
        return {
            'overall_score': 0.0,
            'keyword_overlap': 0.0,
            'bleu_score': 0.0,
            'exact_match': 0.0,
            'entity_match': 0.0,
            'semantic_similarity': 0.0
        }


def evaluate_simple_ground_truth(answer: str, ground_truth: str) -> Dict[str, float]:
    """
    Convenience function for simple ground truth evaluation.
    
    Args:
        answer: Generated answer text
        ground_truth: Expected answer text
        
    Returns:
        Dictionary with evaluation metrics
    """
    evaluator = SimpleGroundTruthEvaluator()
    return evaluator.evaluate(answer, ground_truth)


# Test the evaluator with sample data
if __name__ == "__main__":
    # Test with sample from rag_comprehensive_sample.jsonl
    answer = "Our API response time SLA is 200ms for 95% of requests and 500ms for 99% of requests, with 99.9% uptime guarantee."
    ground_truth = "API SLA: 200ms (95%), 500ms (99%), 99.9% uptime"
    
    result = evaluate_simple_ground_truth(answer, ground_truth)
    print("Simple Ground Truth Evaluation Result:")
    for metric, score in result.items():
        print(f"  {metric}: {score}")
