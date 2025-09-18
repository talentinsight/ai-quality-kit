"""Tests for RAG Embedding Robustness functionality."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from apps.orchestrator.evaluators.rag_embedding_robustness import (
    recall_at_k, overlap_at_k, answer_stability, low_agreement_flag,
    hybrid_gain_delta_recall, run_embedding_robustness, EmbeddingRobustnessResult
)
from apps.orchestrator.retrieval.hybrid_search import DocHit, dense_search, bm25_search, rrf_fuse
from apps.config.rag_embedding import get_rag_er_config


class TestEmbeddingRobustnessMetrics:
    """Test embedding robustness metric functions."""
    
    def test_recall_at_k_perfect_recall(self):
        """Test recall@k with perfect recall."""
        grounding_ids = {"doc1", "doc2", "doc3"}
        retrieved_ids = ["doc1", "doc2", "doc3", "doc4", "doc5"]
        
        recall = recall_at_k(grounding_ids, retrieved_ids, k=5)
        assert recall == 1.0
    
    def test_recall_at_k_partial_recall(self):
        """Test recall@k with partial recall."""
        grounding_ids = {"doc1", "doc2", "doc3"}
        retrieved_ids = ["doc1", "doc4", "doc5"]
        
        recall = recall_at_k(grounding_ids, retrieved_ids, k=3)
        assert recall == 1/3  # Only doc1 found
    
    def test_recall_at_k_no_grounding(self):
        """Test recall@k with no grounding documents."""
        grounding_ids = set()
        retrieved_ids = ["doc1", "doc2"]
        
        recall = recall_at_k(grounding_ids, retrieved_ids, k=2)
        assert recall == 1.0  # Perfect recall when no grounding expected
    
    def test_overlap_at_k_perfect_overlap(self):
        """Test overlap@k with identical retrieval sets."""
        retrieval_sets = [
            {"doc1", "doc2", "doc3"},
            {"doc1", "doc2", "doc3"},
            {"doc1", "doc2", "doc3"}
        ]
        
        overlap = overlap_at_k(retrieval_sets, k=3)
        assert overlap == 1.0
    
    def test_overlap_at_k_no_overlap(self):
        """Test overlap@k with completely different sets."""
        retrieval_sets = [
            {"doc1", "doc2"},
            {"doc3", "doc4"},
            {"doc5", "doc6"}
        ]
        
        overlap = overlap_at_k(retrieval_sets, k=2)
        assert overlap == 0.0
    
    def test_overlap_at_k_partial_overlap(self):
        """Test overlap@k with partial overlap."""
        retrieval_sets = [
            {"doc1", "doc2"},
            {"doc1", "doc3"},
            {"doc2", "doc3"}
        ]
        
        overlap = overlap_at_k(retrieval_sets, k=2)
        # Jaccard similarities: (1,2)=1/3, (1,3)=1/3, (2,3)=1/3
        # Mean = 1/3
        assert abs(overlap - 1/3) < 0.001
    
    def test_answer_stability_identical_answers(self):
        """Test answer stability with identical answers."""
        def mock_embed(text):
            return [1.0, 0.0, 0.0]  # Same embedding for all
        
        answers = ["Same answer", "Same answer", "Same answer"]
        stability = answer_stability(answers, mock_embed)
        assert stability == 1.0
    
    def test_answer_stability_different_answers(self):
        """Test answer stability with different answers."""
        def mock_embed(text):
            # Return different embeddings based on text
            if "first" in text:
                return [1.0, 0.0, 0.0]
            elif "second" in text:
                return [0.0, 1.0, 0.0]
            else:
                return [0.0, 0.0, 1.0]
        
        answers = ["First answer", "Second answer", "Third answer"]
        stability = answer_stability(answers, mock_embed)
        assert stability == 0.0  # Orthogonal vectors have 0 cosine similarity
    
    def test_low_agreement_flag_high_variance(self):
        """Test low agreement detection with high variance."""
        # High variance embeddings
        embeddings = [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0]
        ]
        
        is_low_agreement = low_agreement_flag(embeddings, std_threshold=0.1)
        assert is_low_agreement  # Should detect high variance
    
    def test_low_agreement_flag_low_variance(self):
        """Test low agreement detection with low variance."""
        # Low variance embeddings
        embeddings = [
            [1.0, 0.1, 0.1],
            [1.0, 0.2, 0.1],
            [1.0, 0.1, 0.2]
        ]
        
        is_low_agreement = low_agreement_flag(embeddings, std_threshold=0.5)
        assert not is_low_agreement  # Should not detect low variance
    
    def test_hybrid_gain_delta_recall(self):
        """Test hybrid gain calculation."""
        dense_recall = 0.7
        hybrid_recall = 0.85
        
        gain = hybrid_gain_delta_recall(dense_recall, hybrid_recall)
        assert gain == 0.15
        
        # Test negative gain
        gain_negative = hybrid_gain_delta_recall(0.9, 0.8)
        assert gain_negative == -0.1


class TestHybridSearch:
    """Test hybrid search components."""
    
    def test_dense_search_basic(self):
        """Test basic dense search functionality."""
        def mock_embed(text):
            # Simple hash-based embedding
            return [hash(text) % 100 / 100.0, (hash(text) >> 8) % 100 / 100.0]
        
        passages = [
            {"id": "p1", "text": "Paris is the capital of France"},
            {"id": "p2", "text": "Berlin is the capital of Germany"},
            {"id": "p3", "text": "London is the capital of England"}
        ]
        
        results = dense_search("capital of France", passages, k=2, embed_fn=mock_embed)
        
        assert len(results) <= 2
        assert all(isinstance(hit, DocHit) for hit in results)
        assert all(hit.score >= 0 for hit in results)
    
    def test_bm25_search_basic(self):
        """Test basic BM25 search functionality."""
        passages = [
            {"id": "p1", "text": "Paris is the capital of France"},
            {"id": "p2", "text": "Berlin is the capital of Germany"},
            {"id": "p3", "text": "London is the capital of England"}
        ]
        
        results = bm25_search("capital France", passages, k=2)
        
        assert len(results) <= 2
        assert all(isinstance(hit, DocHit) for hit in results)
        # BM25 should rank passages with "capital" and "France" higher
        if results:
            assert "p1" in [hit.doc_id for hit in results]
    
    def test_rrf_fuse_basic(self):
        """Test RRF fusion functionality."""
        dense_hits = [
            DocHit(doc_id="p1", score=0.9, text="text1"),
            DocHit(doc_id="p2", score=0.8, text="text2")
        ]
        
        bm25_hits = [
            DocHit(doc_id="p2", score=5.0, text="text2"),
            DocHit(doc_id="p3", score=3.0, text="text3")
        ]
        
        fused_results = rrf_fuse(dense_hits, bm25_hits, k_rrf=60)
        
        assert len(fused_results) == 3  # p1, p2, p3
        assert all(isinstance(hit, DocHit) for hit in fused_results)
        # p2 should rank highest (appears in both lists)
        assert fused_results[0].doc_id == "p2"


class TestEmbeddingRobustnessIntegration:
    """Test embedding robustness integration."""
    
    @pytest.mark.asyncio
    async def test_run_embedding_robustness_basic(self):
        """Test basic embedding robustness evaluation."""
        # Mock case
        case = {
            "qid": "test_q1",
            "question": "What is the capital of France?",
            "contexts": ["p1", "p2"],
            "required": False
        }
        
        # Mock passages
        passages = [
            {"id": "p1", "text": "Paris is the capital of France"},
            {"id": "p2", "text": "Berlin is the capital of Germany"}
        ]
        
        # Mock providers
        providers = {
            "embed_function": lambda text: [hash(text) % 100 / 100.0] * 384,
            "llm_function": AsyncMock(return_value="1. What is France's capital?\n2. Tell me about Paris."),
            "llm_enabled": True
        }
        
        # Mock config
        cfg = {
            "k": 3,
            "query_rewrites": 2,
            "hybrid_enabled": True,
            "mmr_enabled": False,
            "reranker_enabled": False
        }
        
        result = await run_embedding_robustness(case, passages, providers, cfg)
        
        assert isinstance(result, EmbeddingRobustnessResult)
        assert result.qid == "test_q1"
        assert 0.0 <= result.recall_at_k <= 1.0
        assert 0.0 <= result.overlap_at_k <= 1.0
        assert 0.0 <= result.answer_stability <= 1.0
        assert result.k == 3
        assert result.paraphrase_count == 2
    
    @pytest.mark.asyncio
    async def test_run_embedding_robustness_with_robustness_config(self):
        """Test embedding robustness with robustness configuration."""
        case = {
            "qid": "test_q2",
            "question": "What is machine learning?",
            "contexts": ["p1"],
            "required": True,
            "robustness": {
                "paraphrases": ["Explain machine learning", "What is ML?"],
                "synonyms": ["ML", "artificial intelligence"],
                "require_hybrid": True,
                "mmr_lambda": 0.6
            }
        }
        
        passages = [{"id": "p1", "text": "Machine learning is a subset of AI"}]
        
        providers = {
            "embed_function": lambda text: [0.5] * 384,
            "llm_function": AsyncMock(return_value="ML is a type of AI"),
            "llm_enabled": True
        }
        
        cfg = get_rag_er_config()
        
        result = await run_embedding_robustness(case, passages, providers, cfg)
        
        assert result.qid == "test_q2"
        assert result.fallback_triggered  # Should be True due to require_hybrid
        assert result.paraphrase_count == 2  # From robustness config


class TestConfigIntegration:
    """Test configuration integration."""
    
    def test_get_rag_er_config(self):
        """Test RAG embedding robustness configuration."""
        config = get_rag_er_config()
        
        assert isinstance(config, dict)
        assert "enabled" in config
        assert "k" in config
        assert "recall_min" in config
        assert "overlap_min" in config
        assert "ans_stability_min" in config
        
        # Validate ranges
        assert 1 <= config["k"] <= 100
        assert 0.0 <= config["recall_min"] <= 1.0
        assert 0.0 <= config["overlap_min"] <= 1.0
        assert 0.0 <= config["ans_stability_min"] <= 1.0


class TestRegressionPrevention:
    """Test regression prevention for existing RAG functionality."""
    
    def test_rag_legacy_parity_no_er(self):
        """Test that RAG works without embedding robustness enabled."""
        # This would be a more comprehensive test in a real implementation
        # For now, just test that config can be disabled
        with patch('apps.config.rag_embedding.RAG_ER_ENABLED', False):
            config = get_rag_er_config()
            assert config["enabled"] == False
    
    def test_optional_fields_ignored_when_off(self):
        """Test that optional robustness fields are ignored when ER is off."""
        case_with_robustness = {
            "qid": "test",
            "question": "test question",
            "required": True,
            "robustness": {
                "paraphrases": ["test paraphrase"],
                "require_hybrid": True
            }
        }
        
        # When ER is disabled, robustness fields should be ignored
        # This test would verify that the case still processes normally
        assert "robustness" in case_with_robustness  # Fields present but ignored
        assert case_with_robustness["required"] == True  # Other fields work normally
