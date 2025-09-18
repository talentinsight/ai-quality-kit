"""RAG Embedding Robustness Configuration."""

import os


# Master switch for Embedding Robustness subtest
RAG_ER_ENABLED = os.getenv("RAG_ER_ENABLED", "true").lower() == "true"

# Retrieval and evaluation parameters
RAG_ER_K = int(os.getenv("RAG_ER_K", "20"))  # top-k for recall/overlap
RAG_ER_RECALL_MIN = float(os.getenv("RAG_ER_RECALL_MIN", "0.90"))  # gating threshold
RAG_ER_OVERLAP_MIN = float(os.getenv("RAG_ER_OVERLAP_MIN", "0.60"))
RAG_ER_ANS_STABILITY_MIN = float(os.getenv("RAG_ER_ANS_STABILITY_MIN", "0.75"))

# Query rewriting and paraphrase generation
RAG_ER_QUERY_REWRITES = int(os.getenv("RAG_ER_QUERY_REWRITES", "3"))  # number of paraphrases if not provided

# Hybrid retrieval settings
RAG_ER_HYBRID_ENABLED = os.getenv("RAG_ER_HYBRID_ENABLED", "true").lower() == "true"  # dense + BM25 fusion
RAG_ER_RRF_K = int(os.getenv("RAG_ER_RRF_K", "60"))  # RRF constant

# Optional reranker
RAG_ER_RERANKER_ENABLED = os.getenv("RAG_ER_RERANKER_ENABLED", "false").lower() == "true"

# MMR diversification
RAG_ER_MMR_ENABLED = os.getenv("RAG_ER_MMR_ENABLED", "true").lower() == "true"
RAG_ER_MMR_LAMBDA = float(os.getenv("RAG_ER_MMR_LAMBDA", "0.4"))

# Model settings
RAG_ER_EMBED_MODEL = os.getenv("RAG_ER_EMBED_MODEL", "default")  # use existing embed provider
RAG_ER_LLM_REWRITE_MODEL = os.getenv("RAG_ER_LLM_REWRITE_MODEL", "default")  # for paraphrase generation

# Low agreement detection
RAG_ER_LOW_AGR_STD_MIN = float(os.getenv("RAG_ER_LOW_AGR_STD_MIN", "0.08"))  # min std to flag low-agreement

# Gating behavior
RAG_ER_FAIL_FAST = os.getenv("RAG_ER_FAIL_FAST", "true").lower() == "true"  # if required ER case fails → gate

# Validation
assert 1 <= RAG_ER_K <= 100, "RAG_ER_K must be between 1 and 100"
assert 0.0 <= RAG_ER_RECALL_MIN <= 1.0, "RAG_ER_RECALL_MIN must be between 0.0 and 1.0"
assert 0.0 <= RAG_ER_OVERLAP_MIN <= 1.0, "RAG_ER_OVERLAP_MIN must be between 0.0 and 1.0"
assert 0.0 <= RAG_ER_ANS_STABILITY_MIN <= 1.0, "RAG_ER_ANS_STABILITY_MIN must be between 0.0 and 1.0"
assert 1 <= RAG_ER_QUERY_REWRITES <= 10, "RAG_ER_QUERY_REWRITES must be between 1 and 10"
assert 1 <= RAG_ER_RRF_K <= 1000, "RAG_ER_RRF_K must be between 1 and 1000"
assert 0.0 <= RAG_ER_MMR_LAMBDA <= 1.0, "RAG_ER_MMR_LAMBDA must be between 0.0 and 1.0"
assert 0.0 <= RAG_ER_LOW_AGR_STD_MIN <= 1.0, "RAG_ER_LOW_AGR_STD_MIN must be between 0.0 and 1.0"


def get_rag_er_config() -> dict:
    """Get current RAG Embedding Robustness configuration."""
    return {
        "enabled": RAG_ER_ENABLED,
        "k": RAG_ER_K,
        "recall_min": RAG_ER_RECALL_MIN,
        "overlap_min": RAG_ER_OVERLAP_MIN,
        "ans_stability_min": RAG_ER_ANS_STABILITY_MIN,
        "query_rewrites": RAG_ER_QUERY_REWRITES,
        "hybrid_enabled": RAG_ER_HYBRID_ENABLED,
        "rrf_k": RAG_ER_RRF_K,
        "reranker_enabled": RAG_ER_RERANKER_ENABLED,
        "mmr_enabled": RAG_ER_MMR_ENABLED,
        "mmr_lambda": RAG_ER_MMR_LAMBDA,
        "embed_model": RAG_ER_EMBED_MODEL,
        "llm_rewrite_model": RAG_ER_LLM_REWRITE_MODEL,
        "low_agr_std_min": RAG_ER_LOW_AGR_STD_MIN,
        "fail_fast": RAG_ER_FAIL_FAST
    }
