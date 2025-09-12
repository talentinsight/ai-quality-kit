"""Hybrid Search Module for RAG Embedding Robustness.

Implements pure functions for dense, BM25, RRF fusion, MMR diversification, and optional reranking.
No vendor lock-in - all functions are pure and testable.
"""

import math
from typing import List, Dict, Set, Optional, Tuple, Any
from dataclasses import dataclass
from collections import defaultdict

try:
    import numpy as np
except ImportError:
    # Mock numpy for basic operations
    class MockNumpy:
        @staticmethod
        def dot(a, b):
            return sum(x * y for x, y in zip(a, b))
        
        @staticmethod
        def linalg_norm(v):
            return math.sqrt(sum(x * x for x in v))
        
        @staticmethod
        def zeros_like(v):
            return [0.0] * len(v)
    
    class np:
        dot = MockNumpy.dot
        class linalg:
            norm = MockNumpy.linalg_norm
        zeros_like = MockNumpy.zeros_like


@dataclass
class DocHit:
    """Document hit with score and metadata."""
    doc_id: str
    score: float
    text: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None


def dense_search(query: str, passages: List[Dict[str, Any]], k: int, 
                embed_fn: callable) -> List[DocHit]:
    """
    Dense semantic search using embeddings.
    
    Args:
        query: Search query
        passages: List of passage dicts with 'id', 'text', 'meta'
        k: Number of top results to return
        embed_fn: Function to embed text -> vector
    
    Returns:
        List of DocHit sorted by similarity score (descending)
    """
    if not passages or k <= 0:
        return []
    
    # Embed query
    query_emb = embed_fn(query)
    
    # Embed all passages and compute similarities
    hits = []
    for passage in passages:
        passage_emb = embed_fn(passage['text'])
        
        # Cosine similarity
        similarity = np.dot(query_emb, passage_emb) / (
            np.linalg.norm(query_emb) * np.linalg.norm(passage_emb)
        )
        
        hits.append(DocHit(
            doc_id=passage['id'],
            score=float(similarity),
            text=passage['text'],
            meta=passage.get('meta')
        ))
    
    # Sort by score descending and return top-k
    hits.sort(key=lambda x: x.score, reverse=True)
    return hits[:k]


def bm25_search(query: str, passages: List[Dict[str, Any]], k: int,
               synonyms: Optional[List[str]] = None) -> List[DocHit]:
    """
    BM25 lexical search with optional synonym expansion.
    
    Args:
        query: Search query
        passages: List of passage dicts with 'id', 'text', 'meta'
        k: Number of top results to return
        synonyms: Optional list of synonyms to expand query
    
    Returns:
        List of DocHit sorted by BM25 score (descending)
    """
    if not passages or k <= 0:
        return []
    
    # Simple BM25 implementation
    # Parameters
    k1 = 1.2
    b = 0.75
    
    # Tokenize query (simple whitespace + lowercase)
    query_terms = set(query.lower().split())
    
    # Add synonyms if provided
    if synonyms:
        for synonym in synonyms:
            query_terms.add(synonym.lower())
    
    # Tokenize all passages and compute stats
    passage_tokens = []
    doc_lengths = []
    term_freqs = []
    doc_freqs = defaultdict(int)
    
    for passage in passages:
        tokens = passage['text'].lower().split()
        passage_tokens.append(tokens)
        doc_lengths.append(len(tokens))
        
        # Term frequencies in this document
        tf = defaultdict(int)
        unique_terms = set()
        for token in tokens:
            tf[token] += 1
            unique_terms.add(token)
        
        term_freqs.append(tf)
        
        # Document frequencies
        for term in unique_terms:
            doc_freqs[term] += 1
    
    if not passage_tokens:
        return []
    
    avg_doc_length = sum(doc_lengths) / len(doc_lengths)
    num_docs = len(passages)
    
    # Compute BM25 scores
    hits = []
    for i, passage in enumerate(passages):
        score = 0.0
        tf = term_freqs[i]
        doc_len = doc_lengths[i]
        
        for term in query_terms:
            if term in tf:
                # Term frequency component
                tf_component = tf[term] * (k1 + 1) / (
                    tf[term] + k1 * (1 - b + b * doc_len / avg_doc_length)
                )
                
                # Inverse document frequency component
                df = doc_freqs[term]
                idf_component = math.log((num_docs - df + 0.5) / (df + 0.5))
                
                score += tf_component * idf_component
        
        hits.append(DocHit(
            doc_id=passage['id'],
            score=score,
            text=passage['text'],
            meta=passage.get('meta')
        ))
    
    # Sort by score descending and return top-k
    hits.sort(key=lambda x: x.score, reverse=True)
    return hits[:k]


def rrf_fuse(dense_hits: List[DocHit], bm25_hits: List[DocHit], 
            k_rrf: int = 60) -> List[DocHit]:
    """
    Reciprocal Rank Fusion (RRF) to combine dense and BM25 results.
    
    Args:
        dense_hits: Results from dense search
        bm25_hits: Results from BM25 search
        k_rrf: RRF constant (default: 60)
    
    Returns:
        Fused results sorted by RRF score (descending)
    """
    # Create rank maps
    dense_ranks = {hit.doc_id: i + 1 for i, hit in enumerate(dense_hits)}
    bm25_ranks = {hit.doc_id: i + 1 for i, hit in enumerate(bm25_hits)}
    
    # Collect all unique documents
    all_doc_ids = set(dense_ranks.keys()) | set(bm25_ranks.keys())
    
    # Create doc_id to hit mapping for metadata
    doc_to_hit = {}
    for hit in dense_hits + bm25_hits:
        if hit.doc_id not in doc_to_hit:
            doc_to_hit[hit.doc_id] = hit
    
    # Compute RRF scores
    fused_hits = []
    for doc_id in all_doc_ids:
        rrf_score = 0.0
        
        # Add dense contribution
        if doc_id in dense_ranks:
            rrf_score += 1.0 / (k_rrf + dense_ranks[doc_id])
        
        # Add BM25 contribution
        if doc_id in bm25_ranks:
            rrf_score += 1.0 / (k_rrf + bm25_ranks[doc_id])
        
        # Use existing hit metadata
        base_hit = doc_to_hit[doc_id]
        fused_hits.append(DocHit(
            doc_id=doc_id,
            score=rrf_score,
            text=base_hit.text,
            meta=base_hit.meta
        ))
    
    # Sort by RRF score descending
    fused_hits.sort(key=lambda x: x.score, reverse=True)
    return fused_hits


def mmr_diversify(query_emb: Any, candidates: List[DocHit], 
                 top_k: int, lambda_param: float = 0.4,
                 embed_fn: callable = None) -> List[DocHit]:
    """
    Maximal Marginal Relevance (MMR) diversification.
    
    Args:
        query_emb: Query embedding vector
        candidates: Candidate documents to diversify
        top_k: Number of diverse results to return
        lambda_param: Trade-off between relevance and diversity (0..1)
        embed_fn: Function to embed text -> vector (required for diversity computation)
    
    Returns:
        Diversified results
    """
    if not candidates or top_k <= 0 or embed_fn is None:
        return candidates[:top_k]
    
    # Embed all candidate documents
    candidate_embs = []
    for hit in candidates:
        if hit.text:
            emb = embed_fn(hit.text)
            candidate_embs.append(emb)
        else:
            # Fallback: use zero vector
            candidate_embs.append(np.zeros_like(query_emb))
    
    selected = []
    remaining_indices = list(range(len(candidates)))
    
    while len(selected) < top_k and remaining_indices:
        best_score = -float('inf')
        best_idx = None
        
        for i in remaining_indices:
            # Relevance score (similarity to query)
            relevance = np.dot(query_emb, candidate_embs[i]) / (
                np.linalg.norm(query_emb) * np.linalg.norm(candidate_embs[i])
            )
            
            # Diversity score (max similarity to already selected)
            max_similarity = 0.0
            if selected:
                for j in [candidates.index(s) for s in selected]:
                    similarity = np.dot(candidate_embs[i], candidate_embs[j]) / (
                        np.linalg.norm(candidate_embs[i]) * np.linalg.norm(candidate_embs[j])
                    )
                    max_similarity = max(max_similarity, similarity)
            
            # MMR score
            mmr_score = lambda_param * relevance - (1 - lambda_param) * max_similarity
            
            if mmr_score > best_score:
                best_score = mmr_score
                best_idx = i
        
        if best_idx is not None:
            selected.append(candidates[best_idx])
            remaining_indices.remove(best_idx)
    
    return selected


def rerank(query: str, candidates: List[DocHit], reranker_fn: callable,
          top_k: Optional[int] = None) -> List[DocHit]:
    """
    Optional cross-encoder reranking.
    
    Args:
        query: Search query
        candidates: Candidate documents to rerank
        reranker_fn: Function that takes (query, doc_text) -> relevance_score
        top_k: Optional limit on results
    
    Returns:
        Reranked results
    """
    if not candidates or reranker_fn is None:
        return candidates[:top_k] if top_k else candidates
    
    # Rerank all candidates
    reranked_hits = []
    for hit in candidates:
        if hit.text:
            relevance_score = reranker_fn(query, hit.text)
            reranked_hits.append(DocHit(
                doc_id=hit.doc_id,
                score=float(relevance_score),
                text=hit.text,
                meta=hit.meta
            ))
        else:
            # Keep original score if no text
            reranked_hits.append(hit)
    
    # Sort by reranker score descending
    reranked_hits.sort(key=lambda x: x.score, reverse=True)
    
    return reranked_hits[:top_k] if top_k else reranked_hits


def hybrid_search_pipeline(query: str, passages: List[Dict[str, Any]], 
                          k: int, embed_fn: callable,
                          synonyms: Optional[List[str]] = None,
                          rrf_k: int = 60,
                          mmr_enabled: bool = True,
                          mmr_lambda: float = 0.4,
                          reranker_fn: Optional[callable] = None) -> Tuple[List[DocHit], List[DocHit]]:
    """
    Complete hybrid search pipeline: dense + BM25 + RRF + MMR + optional reranking.
    
    Args:
        query: Search query
        passages: List of passage dicts
        k: Number of final results
        embed_fn: Embedding function
        synonyms: Optional synonyms for BM25 expansion
        rrf_k: RRF constant
        mmr_enabled: Whether to apply MMR diversification
        mmr_lambda: MMR lambda parameter
        reranker_fn: Optional reranker function
    
    Returns:
        Tuple of (dense_only_results, hybrid_results)
    """
    # Dense search
    dense_results = dense_search(query, passages, k * 2, embed_fn)  # Get more for fusion
    
    # BM25 search
    bm25_results = bm25_search(query, passages, k * 2, synonyms)
    
    # RRF fusion
    hybrid_results = rrf_fuse(dense_results, bm25_results, rrf_k)
    
    # Optional reranking
    if reranker_fn:
        hybrid_results = rerank(query, hybrid_results[:k * 3], reranker_fn, k * 2)
    
    # MMR diversification
    if mmr_enabled and embed_fn:
        query_emb = embed_fn(query)
        hybrid_results = mmr_diversify(query_emb, hybrid_results, k, mmr_lambda, embed_fn)
    
    # Trim to final k
    dense_final = dense_results[:k]
    hybrid_final = hybrid_results[:k]
    
    return dense_final, hybrid_final
