"""Ragas evaluator adapter for RAG quality assessment.

This module provides a thin adapter that computes common Ragas metrics over RAG samples.
It is designed to be pluggable via environment flags and request options, with graceful
degradation when Ragas is not available or when evaluation fails.
"""

import logging
from typing import Dict, List, Any, Optional, Union

# Configure logging
logger = logging.getLogger(__name__)


def evaluate_ragas(samples: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Evaluate RAG samples using Ragas metrics.
    
    This function provides a thin adapter that computes common Ragas metrics over a list
    of RAG samples. It handles import failures and validation errors gracefully by
    returning an empty dictionary, ensuring that failures do not break the test run.
    
    Args:
        samples: List of evaluation samples, each containing:
            - question: str - The original query
            - answer: str - The generated answer  
            - contexts: List[str] - Retrieved context passages
            - ground_truth: Optional[str] - Expected answer (optional)
            
    Returns:
        Dictionary with Ragas metrics under "ragas" key:
        {
            "ragas": {
                "faithfulness": float,
                "answer_relevancy": float, 
                "context_precision": float,
                "context_recall": float,        # Only with ground truth
                "answer_correctness": float,    # Only with ground truth
                "answer_similarity": float     # Only with ground truth
            }
        }
        
        Without ground truth: 3 metrics (faithfulness, answer_relevancy, context_precision)
        With ground truth: 6 metrics (all above)
        
        Returns empty dict {} if:
        - Ragas import fails
        - Insufficient sample data
        - Evaluation errors occur
        
    Note:
        This function never raises exceptions to the caller. All errors are logged
        and result in an empty dictionary return value for graceful degradation.
    """
    
    # Try to import Ragas - return empty dict if not available
    try:
        from ragas import evaluate
        from ragas.metrics import (
            faithfulness, 
            answer_relevancy, 
            context_precision, 
            context_recall,
            answer_correctness,
            answer_similarity
        )
        from datasets import Dataset
    except ImportError as e:
        logger.debug(f"Ragas not available for evaluation: {e}")
        return {}
    
    # Validate input samples
    if not samples:
        logger.debug("No samples provided for Ragas evaluation")
        return {}
    
    # Validate sample format
    required_fields = ['question', 'answer', 'contexts']
    valid_samples = []
    
    for i, sample in enumerate(samples):
        # Check required fields
        missing_fields = [field for field in required_fields if field not in sample]
        if missing_fields:
            logger.debug(f"Sample {i} missing required fields: {missing_fields}")
            continue
            
        # Validate contexts is a list
        if not isinstance(sample.get('contexts'), list):
            logger.debug(f"Sample {i} contexts field is not a list")
            continue
            
        # Validate non-empty strings
        if not sample.get('question') or not sample.get('answer'):
            logger.debug(f"Sample {i} has empty question or answer")
            continue
            
        valid_samples.append(sample)
    
    # Check if we have sufficient valid samples
    if not valid_samples:
        logger.debug("No valid samples found for Ragas evaluation")
        return {}
    
    try:
        # Prepare data for Ragas evaluation
        eval_data = {
            'question': [sample['question'] for sample in valid_samples],
            'answer': [sample['answer'] for sample in valid_samples],
            'contexts': [sample['contexts'] for sample in valid_samples],
        }
        
        # Add ground truth if available for all samples
        has_ground_truth = all('ground_truth' in sample and sample['ground_truth'] 
                              for sample in valid_samples)
        if has_ground_truth:
            eval_data['ground_truths'] = [[sample['ground_truth']] for sample in valid_samples]
        
        # Create dataset
        dataset = Dataset.from_dict(eval_data)
        
        # Define metrics to evaluate based on available data
        # Without ground truth: faithfulness, answer_relevancy, context_precision (as context relevancy)
        metrics_to_eval = [faithfulness, answer_relevancy, context_precision]
        
        # Add additional metrics that require ground truth
        if has_ground_truth:
            metrics_to_eval.extend([
                context_recall,
                answer_correctness,
                answer_similarity
            ])
        
        logger.info(f"Evaluating {len(valid_samples)} samples with Ragas metrics: {[m.name for m in metrics_to_eval]}")
        
        # Run Ragas evaluation
        result = evaluate(dataset, metrics=metrics_to_eval)
        
        # Ensure result is a dictionary
        if not isinstance(result, dict):
            logger.warning(f"Ragas evaluation returned unexpected type: {type(result)}")
            return {}
        
        # Extract and format results
        ragas_metrics = {}
        
        # Map Ragas result keys to our standardized names
        metric_mapping = {
            'faithfulness': 'faithfulness',
            'answer_relevancy': 'answer_relevancy', 
            'context_precision': 'context_precision',
            'context_recall': 'context_recall',
            'answer_correctness': 'answer_correctness',
            'answer_similarity': 'answer_similarity'
        }
        
        for ragas_key, our_key in metric_mapping.items():
            if ragas_key in result:
                value = result[ragas_key]
                # Convert to float and handle potential NaN values
                try:
                    # Handle case where value might be a numpy array or list (take mean)
                    if hasattr(value, '__iter__') and not isinstance(value, (str, bytes)):
                        # Convert iterable to list of floats first, then take mean
                        try:
                            values_list = [float(x) for x in value]
                            float_value = sum(values_list) / len(values_list) if values_list else 0.0
                        except (ValueError, TypeError):
                            # If conversion fails, try to get the first element
                            first_val = value[0] if len(value) > 0 else 0.0
                            float_value = float(first_val)
                    else:
                        float_value = float(value)  # type: ignore
                    
                    if not (float_value != float_value):  # Check for NaN
                        ragas_metrics[our_key] = float_value
                    else:
                        logger.warning(f"Ragas metric {ragas_key} returned NaN")
                except (ValueError, TypeError, ImportError) as e:
                    logger.warning(f"Could not convert Ragas metric {ragas_key} to float: {value}, error: {e}")
        
        if ragas_metrics:
            logger.info(f"Ragas evaluation completed successfully: {ragas_metrics}")
            return {"ragas": ragas_metrics}
        else:
            logger.warning("Ragas evaluation completed but no valid metrics extracted")
            return {}
            
    except Exception as e:
        # Handle specific known issues
        error_str = str(e).lower()
        if "uvloop" in error_str or "can't patch loop" in error_str:
            logger.warning("Ragas evaluation failed due to uvloop compatibility issue")
        elif "openai" in error_str and "api" in error_str:
            logger.warning("Ragas evaluation failed due to OpenAI API issue - check API key and rate limits")
        else:
            logger.warning(f"Ragas evaluation failed with error: {e}")
        
        # Always return empty dict for graceful degradation
        return {}


def check_ragas_thresholds(
    ragas_metrics: Dict[str, float], 
    thresholds: Dict[str, float]
) -> Dict[str, bool]:
    """
    Check if Ragas metrics meet specified thresholds.
    
    Args:
        ragas_metrics: Dictionary of Ragas metric scores
        thresholds: Dictionary of minimum threshold values with keys like:
            - min_faithfulness
            - min_answer_relevancy  
            - min_context_precision
            - min_context_recall
            
    Returns:
        Dictionary indicating which thresholds were met
    """
    results = {}
    
    # Map threshold keys to metric keys
    threshold_mapping = {
        'min_faithfulness': 'faithfulness',
        'min_answer_relevancy': 'answer_relevancy',
        'min_context_precision': 'context_precision', 
        'min_context_recall': 'context_recall'
    }
    
    for threshold_key, metric_key in threshold_mapping.items():
        if threshold_key in thresholds:
            threshold_value = thresholds[threshold_key]
            metric_value = ragas_metrics.get(metric_key)
            
            if metric_value is not None:
                results[threshold_key] = metric_value >= threshold_value
            else:
                results[threshold_key] = False
                
    return results
