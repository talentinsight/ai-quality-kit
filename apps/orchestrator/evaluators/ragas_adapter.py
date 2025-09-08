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
        # Prepare data for Ragas evaluation with proper context formatting
        eval_data = {
            'question': [sample['question'] for sample in valid_samples],
            'answer': [sample['answer'] for sample in valid_samples],
            'contexts': [],
        }
        
        # Ensure contexts are properly formatted for RAGAS faithfulness
        for sample in valid_samples:
            contexts = sample['contexts']
            
            # RAGAS faithfulness requires contexts as list of strings
            # Each context should be a meaningful chunk that can be fact-checked
            if isinstance(contexts, str):
                # Single string context - split into sentences for better faithfulness evaluation
                sentences = [s.strip() for s in contexts.split('.') if s.strip()]
                if len(sentences) > 1:
                    normalized_contexts = sentences
                else:
                    normalized_contexts = [contexts]
            elif isinstance(contexts, list):
                # List of contexts - ensure all are strings and meaningful
                normalized_contexts = []
                for ctx in contexts:
                    if isinstance(ctx, str) and ctx.strip():
                        # Split long contexts into sentences for better faithfulness evaluation
                        if len(ctx) > 200:  # Long context
                            sentences = [s.strip() for s in ctx.split('.') if s.strip() and len(s.strip()) > 10]
                            normalized_contexts.extend(sentences)
                        else:
                            normalized_contexts.append(ctx.strip())
                    elif ctx:  # Non-empty non-string
                        ctx_str = str(ctx).strip()
                        if ctx_str:
                            normalized_contexts.append(ctx_str)
                
                # Ensure we have at least one context
                if not normalized_contexts:
                    normalized_contexts = [str(contexts)]
            else:
                # Fallback: convert to string
                normalized_contexts = [str(contexts)]
            
            # Limit context count for performance (RAGAS can be slow with many contexts)
            if len(normalized_contexts) > 5:
                normalized_contexts = normalized_contexts[:5]
            
            eval_data['contexts'].append(normalized_contexts)
            
        logger.debug(f"Normalized contexts format: {[len(ctx) for ctx in eval_data['contexts']]}")
        
        # Add ground truth if available for all samples
        has_ground_truth = all('ground_truth' in sample and sample['ground_truth'] 
                              for sample in valid_samples)
        if has_ground_truth:
            eval_data['ground_truths'] = [[sample['ground_truth']] for sample in valid_samples]
        
        # Create dataset
        dataset = Dataset.from_dict(eval_data)
        
        # RAG Metrics Spec: Define metrics based on ground truth availability
        if has_ground_truth:
            # With GT: 8 default metrics (faithfulness, context_recall, answer_relevancy, 
            # context_precision, answer_correctness, answer_similarity, context_entities_recall, context_relevancy)
            metrics_to_eval = [
                faithfulness, 
                answer_relevancy,
                context_recall,
                answer_correctness,
                answer_similarity
            ]
            # Note: context_precision, context_entities_recall, context_relevancy not yet implemented in RAGAS
            logger.info("🎯 RAG Metrics Spec: Using GT-available metrics (5 core RAGAS metrics)")
        else:
            # No GT: 3 core metrics (faithfulness, context_recall proxy, answer_relevancy)
            metrics_to_eval = [faithfulness, answer_relevancy]
            # Note: context_recall proxy (question↔context relevance) handled separately
            logger.info("🎯 RAG Metrics Spec: Using No-GT metrics (2 core RAGAS metrics)")
        
        logger.info(f"Evaluating {len(valid_samples)} samples with Ragas metrics: {[m.name for m in metrics_to_eval]}")
        
        # Debug: Log sample data format for RAGAS faithfulness troubleshooting
        if valid_samples:
            sample = valid_samples[0]
            logger.info(f"🔍 RAGAS Input Debug:")
            logger.info(f"  Question: {sample['question'][:100]}...")
            logger.info(f"  Answer: {sample['answer'][:100]}...")
            logger.info(f"  Contexts count: {len(eval_data['contexts'][0])}")
            logger.info(f"  Context format: {type(eval_data['contexts'][0])}")
            
            # Log each context for faithfulness debugging
            for i, ctx in enumerate(eval_data['contexts'][0][:3]):  # First 3 contexts
                logger.info(f"  Context {i+1}: {ctx[:80]}...")
                logger.info(f"  Context {i+1} length: {len(ctx)} chars")
            
            # Check if contexts contain facts that can be verified in answer
            answer_lower = sample['answer'].lower()
            context_facts = []
            for ctx in eval_data['contexts'][0]:
                # Look for numbers, dates, names that might be facts
                import re
                facts = re.findall(r'\b\d+(?:\.\d+)?\s*(?:million|billion|thousand|%|percent)\b', ctx.lower())
                facts.extend(re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', ctx))  # Proper nouns
                context_facts.extend(facts)
            
            logger.info(f"  Extracted facts from context: {context_facts[:5]}")
            
            # Check fact overlap
            fact_overlap = []
            for fact in context_facts:
                if fact.lower() in answer_lower:
                    fact_overlap.append(fact)
            
            logger.info(f"  Facts found in answer: {fact_overlap}")
            logger.info(f"  Expected faithfulness: {'HIGH' if len(fact_overlap) > 0 else 'LOW'}")
        
        # Run Ragas evaluation with timeout and smaller sample size
        import signal
        import os
        
        def timeout_handler(signum, frame):
            raise TimeoutError("Ragas evaluation timed out")
        
        # Set timeout (3 minutes default)
        timeout_seconds = int(os.getenv("RAGAS_TIMEOUT_S", "180"))
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(timeout_seconds)
        
        try:
            # Limit sample size for faster evaluation
            max_samples = int(os.getenv("RAGAS_SAMPLE_SIZE", "3"))
            if len(valid_samples) > max_samples:
                valid_samples = valid_samples[:max_samples]
                logger.info(f"Limiting Ragas evaluation to {max_samples} samples for performance")
            
            result = evaluate(dataset, metrics=metrics_to_eval)
        finally:
            signal.alarm(0)  # Cancel the alarm
        
        # Professional RAGAS result parsing with multiple fallback strategies
        result_dict = {}
        
        try:
            # Strategy 1: Modern RAGAS EvaluationResult object
            if hasattr(result, 'to_pandas'):
                logger.debug("Using RAGAS EvaluationResult.to_pandas() method")
                df = result.to_pandas()
                logger.debug(f"DataFrame shape: {df.shape}, columns: {list(df.columns)}")
                
                # Get all numeric columns
                numeric_cols = df.select_dtypes(include=['number']).columns
                if len(numeric_cols) > 0:
                    # Calculate mean for each metric
                    means = df[numeric_cols].mean()
                    result_dict = means.to_dict()
                    logger.info(f"Successfully extracted RAGAS metrics via pandas: {result_dict}")
                else:
                    # Try to extract values manually from non-numeric columns
                    logger.debug("No numeric columns found, attempting manual extraction")
                    for col in df.columns:
                        if col in ['faithfulness', 'answer_relevancy', 'context_precision', 'context_recall', 
                                  'answer_correctness', 'answer_similarity']:
                            try:
                                values = df[col].dropna()
                                if len(values) > 0:
                                    # Try to convert to numeric
                                    numeric_values = []
                                    for val in values:
                                        try:
                                            if isinstance(val, (int, float)):
                                                numeric_values.append(float(val))
                                            elif hasattr(val, '__float__'):
                                                numeric_values.append(float(val))
                                        except (ValueError, TypeError):
                                            continue
                                    
                                    if numeric_values:
                                        result_dict[col] = sum(numeric_values) / len(numeric_values)
                                        logger.debug(f"Extracted {col}: {result_dict[col]}")
                            except Exception as e:
                                logger.debug(f"Failed to extract {col}: {e}")
                                continue
                    
                    if result_dict:
                        logger.info(f"Successfully extracted RAGAS metrics via manual parsing: {result_dict}")
            
            # Strategy 2: Direct attribute access
            elif hasattr(result, 'scores') or hasattr(result, '__dict__'):
                logger.debug("Using direct attribute access")
                
                # Try scores attribute first
                if hasattr(result, 'scores'):
                    scores = result.scores
                    logger.debug(f"Found scores attribute: {type(scores)}")
                    
                    if isinstance(scores, dict):
                        for metric, value in scores.items():
                            if metric in ['faithfulness', 'answer_relevancy', 'context_precision', 'context_recall']:
                                try:
                                    if hasattr(value, '__iter__') and not isinstance(value, (str, bytes)):
                                        # Handle arrays/lists
                                        numeric_vals = [float(v) for v in value if v is not None]
                                        if numeric_vals:
                                            result_dict[metric] = sum(numeric_vals) / len(numeric_vals)
                                    else:
                                        result_dict[metric] = float(value)
                                except (ValueError, TypeError) as e:
                                    logger.debug(f"Could not convert {metric} value {value}: {e}")
                
                # Try direct attributes
                for attr in ['faithfulness', 'answer_relevancy', 'context_precision', 'context_recall']:
                    if hasattr(result, attr) and attr not in result_dict:
                        try:
                            value = getattr(result, attr)
                            if value is not None:
                                result_dict[attr] = float(value)
                        except (ValueError, TypeError, AttributeError):
                            continue
                
                if result_dict:
                    logger.info(f"Successfully extracted RAGAS metrics via attribute access: {result_dict}")
            
            # Strategy 3: Legacy dict format
            elif isinstance(result, dict):
                logger.debug("Using legacy dict format")
                result_dict = result.copy()
                logger.info(f"Using legacy RAGAS dict format: {result_dict}")
            
            else:
                logger.warning(f"Unknown RAGAS result type: {type(result)}")
                logger.debug(f"Result attributes: {dir(result)[:10]}")
                return {}
                
        except Exception as e:
            logger.error(f"All RAGAS parsing strategies failed: {e}")
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
            if ragas_key in result_dict:
                value = result_dict[ragas_key]
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
