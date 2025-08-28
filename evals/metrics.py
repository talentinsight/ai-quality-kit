"""Evaluation metrics using Ragas framework."""

from typing import List, Dict, Any, Optional
import pandas as pd
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import (
    faithfulness, 
    context_recall, 
    answer_relevancy, 
    context_precision,
    answer_correctness,
    answer_similarity
)
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def eval_batch(samples: List[Dict[str, Any]]) -> Dict[str, float]:
    """
    Evaluate a batch of samples using Ragas metrics.
    
    Args:
        samples: List of evaluation samples, each containing:
            - question: str - The original query
            - answer: str - The generated answer
            - contexts: List[str] - Retrieved context passages
            - ground_truth: str - Expected answer (optional)
            
    Returns:
        Dictionary with metric scores
        
    Raises:
        ValueError: If samples are invalid or evaluation fails
    """
    if not samples:
        raise ValueError("No samples provided for evaluation")
    
    # Validate sample format
    required_fields = ['question', 'answer', 'contexts']
    for i, sample in enumerate(samples):
        for field in required_fields:
            if field not in sample:
                raise ValueError(f"Missing required field '{field}' in sample {i}")
        
        if not isinstance(sample['contexts'], list):
            raise ValueError(f"'contexts' must be a list in sample {i}")
    
    try:
        # Convert to Ragas dataset format
        eval_data = {
            'question': [sample['question'] for sample in samples],
            'answer': [sample['answer'] for sample in samples],
            'contexts': [sample['contexts'] for sample in samples],
        }
        
        # Add ground truth if available (Ragas expects 'ground_truths' as list of lists)
        if all('ground_truth' in sample for sample in samples):
            eval_data['ground_truths'] = [[sample['ground_truth']] for sample in samples]
        
        # Create dataset
        dataset = Dataset.from_dict(eval_data)
        
        # Define metrics to evaluate (always available)
        metrics_to_eval = [faithfulness, answer_relevancy]
        
        # Add metrics that require ground truth
        if 'ground_truths' in eval_data:
            metrics_to_eval.extend([
                context_recall,
                context_precision,
                answer_correctness,
                answer_similarity
            ])
        
        # Run evaluation with error handling for uvloop compatibility
        logger.info(f"Evaluating {len(samples)} samples with Ragas...")
        try:
            result = evaluate(dataset, metrics=metrics_to_eval)
            
            # Debug: Print the raw result
            logger.info(f"Raw Ragas result: {result}")
            
            # Extract scores for all 6 available metrics
            scores = {}
            metric_names = [
                'faithfulness', 'answer_relevancy',
                'context_recall', 'context_precision', 'answer_correctness',
                'answer_similarity'
            ]
            
            for metric_name in metric_names:
                if hasattr(result, metric_name):
                    metric_value = getattr(result, metric_name)
                    if metric_value is not None:
                        scores[metric_name] = float(metric_value)
            
            # Check if all scores are 0 (which might indicate an issue)
            if all(score == 0.0 for score in scores.values()) and scores:
                logger.warning("All evaluation scores are 0.0, this might indicate an evaluation issue")
            
            logger.info(f"Evaluation completed. Scores: {scores}")
            return scores
            
        except Exception as ragas_error:
            # Handle uvloop compatibility issue
            if "Can't patch loop" in str(ragas_error) or "uvloop" in str(ragas_error):
                logger.warning("Ragas evaluation failed due to uvloop compatibility issue. Skipping evaluation.")
                return {}
            # Handle the "0" error case
            elif str(ragas_error).strip() == "0":
                logger.warning("Ragas evaluation returned '0' error, possibly a score issue. Returning empty scores.")
                return {}
            else:
                logger.error(f"Ragas evaluation failed with error: {ragas_error}")
                raise ragas_error
        
    except Exception as e:
        logger.error(f"Evaluation failed: {e}")
        raise ValueError(f"Ragas evaluation failed: {e}")


def create_eval_sample(question: str, answer: str, contexts: List[str], ground_truth: Optional[str] = None) -> Dict[str, Any]:
    """
    Create a properly formatted evaluation sample.
    
    Args:
        question: The original query
        answer: The generated answer
        contexts: List of retrieved context passages
        ground_truth: Expected answer (optional)
        
    Returns:
        Formatted evaluation sample
    """
    sample = {
        'question': question,
        'answer': answer,
        'contexts': contexts
    }
    
    if ground_truth is not None:
        sample['ground_truth'] = ground_truth
    
    return sample


def check_thresholds(scores: Dict[str, float], thresholds: Dict[str, float]) -> Dict[str, bool]:
    """
    Check if scores meet specified thresholds.
    
    Args:
        scores: Dictionary of metric scores
        thresholds: Dictionary of minimum threshold values
        
    Returns:
        Dictionary indicating which thresholds were met
    """
    results = {}
    
    for metric, threshold in thresholds.items():
        if metric in scores:
            results[metric] = scores[metric] >= threshold
        else:
            results[metric] = False
    
    return results
