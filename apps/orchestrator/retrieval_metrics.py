"""Retrieval metrics computation for RAG systems."""

import json
import logging
import math
from typing import Dict, List, Any, Optional, Tuple
from jsonpath_ng import parse
from jsonpath_ng.exceptions import JSONPathError

logger = logging.getLogger(__name__)


def extract_contexts_from_response(response_data: Dict[str, Any], jsonpath: str) -> List[str]:
    """
    Extract retrieved contexts from response using JSONPath.
    
    Args:
        response_data: Response data from LLM
        jsonpath: JSONPath expression (e.g., "$.contexts" or "$.retrieved")
        
    Returns:
        List of context strings, empty if not found or error
    """
    try:
        jsonpath_expr = parse(jsonpath)
        matches = jsonpath_expr.find(response_data)
        
        if not matches:
            return []
        
        # Get the first match (should be a list)
        contexts = matches[0].value
        
        if not isinstance(contexts, list):
            logger.warning(f"JSONPath {jsonpath} did not return a list, got {type(contexts)}")
            return []
        
        # Convert all items to strings
        return [str(ctx) for ctx in contexts if ctx is not None]
        
    except JSONPathError as e:
        logger.warning(f"Invalid JSONPath expression '{jsonpath}': {e}")
        return []
    except Exception as e:
        logger.warning(f"Error extracting contexts with JSONPath '{jsonpath}': {e}")
        return []


def compute_recall_at_k(retrieved_contexts: List[str], relevant_contexts: List[str], k: Optional[int] = None) -> float:
    """
    Compute Recall@K metric.
    
    Args:
        retrieved_contexts: List of retrieved context strings
        relevant_contexts: List of relevant/ground truth context strings
        k: Number of top results to consider (None = use all retrieved)
        
    Returns:
        Recall@K score (0.0 to 1.0)
    """
    if not relevant_contexts:
        return 0.0
    
    if not retrieved_contexts:
        return 0.0
    
    # Use top-k retrieved contexts
    top_k_retrieved = retrieved_contexts[:k] if k else retrieved_contexts
    
    # Count how many relevant contexts are in top-k retrieved
    relevant_found = 0
    for relevant_ctx in relevant_contexts:
        if any(relevant_ctx.lower() in retrieved_ctx.lower() for retrieved_ctx in top_k_retrieved):
            relevant_found += 1
    
    return relevant_found / len(relevant_contexts)


def compute_mrr_at_k(retrieved_contexts: List[str], relevant_contexts: List[str], k: Optional[int] = None) -> float:
    """
    Compute Mean Reciprocal Rank@K metric.
    
    Args:
        retrieved_contexts: List of retrieved context strings
        relevant_contexts: List of relevant/ground truth context strings
        k: Number of top results to consider (None = use all retrieved)
        
    Returns:
        MRR@K score (0.0 to 1.0)
    """
    if not relevant_contexts or not retrieved_contexts:
        return 0.0
    
    # Use top-k retrieved contexts
    top_k_retrieved = retrieved_contexts[:k] if k else retrieved_contexts
    
    # Find the rank of the first relevant context
    for rank, retrieved_ctx in enumerate(top_k_retrieved, 1):
        if any(relevant_ctx.lower() in retrieved_ctx.lower() for relevant_ctx in relevant_contexts):
            return 1.0 / rank
    
    return 0.0


def compute_ndcg_at_k(retrieved_contexts: List[str], relevant_contexts: List[str], k: Optional[int] = None) -> float:
    """
    Compute Normalized Discounted Cumulative Gain@K metric.
    
    Args:
        retrieved_contexts: List of retrieved context strings
        relevant_contexts: List of relevant/ground truth context strings
        k: Number of top results to consider (None = use all retrieved)
        
    Returns:
        NDCG@K score (0.0 to 1.0)
    """
    if not relevant_contexts or not retrieved_contexts:
        return 0.0
    
    # Use top-k retrieved contexts
    top_k_retrieved = retrieved_contexts[:k] if k else retrieved_contexts
    k_actual = len(top_k_retrieved)
    
    # Compute DCG
    dcg = 0.0
    for rank, retrieved_ctx in enumerate(top_k_retrieved, 1):
        # Binary relevance: 1 if relevant, 0 if not
        relevance = 1.0 if any(relevant_ctx.lower() in retrieved_ctx.lower() for relevant_ctx in relevant_contexts) else 0.0
        dcg += relevance / math.log2(rank + 1)
    
    # Compute IDCG (ideal DCG)
    # Assume all relevant contexts would be ranked first
    num_relevant = min(len(relevant_contexts), k_actual)
    idcg = 0.0
    for rank in range(1, num_relevant + 1):
        idcg += 1.0 / math.log2(rank + 1)
    
    if idcg == 0.0:
        return 0.0
    
    return dcg / idcg


def compute_retrieval_metrics(
    retrieved_contexts: List[str], 
    relevant_contexts: List[str], 
    k: Optional[int] = None
) -> Dict[str, float]:
    """
    Compute all retrieval metrics.
    
    Args:
        retrieved_contexts: List of retrieved context strings
        relevant_contexts: List of relevant/ground truth context strings
        k: Number of top results to consider (None = use all retrieved)
        
    Returns:
        Dictionary with recall@k, mrr@k, ndcg@k metrics
    """
    if k is None and retrieved_contexts:
        k = len(retrieved_contexts)
    
    return {
        "recall_at_k": compute_recall_at_k(retrieved_contexts, relevant_contexts, k),
        "mrr_at_k": compute_mrr_at_k(retrieved_contexts, relevant_contexts, k),
        "ndcg_at_k": compute_ndcg_at_k(retrieved_contexts, relevant_contexts, k),
        "retrieved_count": len(retrieved_contexts) if retrieved_contexts else 0,
        "k_value": k or 0
    }


def evaluate_retrieval_for_case(
    response_data: Dict[str, Any],
    expected_contexts: List[str],
    retrieval_config: Dict[str, Any]
) -> Tuple[Dict[str, float], str]:
    """
    Evaluate retrieval metrics for a single test case.
    
    Args:
        response_data: Response from LLM/RAG system
        expected_contexts: Expected/relevant contexts for this case
        retrieval_config: Configuration with contexts_jsonpath, top_k, etc.
        
    Returns:
        Tuple of (metrics_dict, status_message)
    """
    contexts_jsonpath = retrieval_config.get("contexts_jsonpath")
    top_k = retrieval_config.get("top_k")
    
    if not contexts_jsonpath:
        return {}, "N/A (no JSONPath configured)"
    
    # Extract contexts from response
    retrieved_contexts = extract_contexts_from_response(response_data, contexts_jsonpath)
    
    if not retrieved_contexts:
        return {}, "N/A (no contexts surfaced)"
    
    # Compute metrics
    metrics = compute_retrieval_metrics(retrieved_contexts, expected_contexts, top_k)
    
    return metrics, "computed"
