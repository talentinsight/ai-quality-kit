"""Ragas quality evaluation tests."""

import pytest
import os
import sys
import uuid
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from apps.rag_service.rag_pipeline import RAGPipeline
from evals.dataset_loader import load_qa
from evals.metrics import eval_batch, create_eval_sample, check_thresholds
from apps.db.eval_logger import log_evaluation_results
from apps.db.run_context import set_run_id


class TestRagasQuality:
    """Test class for Ragas-based quality evaluation."""
    
    @classmethod
    def setup_class(cls):
        """Setup test fixtures."""
        cls.rag_pipeline = None
        cls.qa_data = None
        
        # Quality thresholds
        cls.thresholds = {
            'faithfulness': 0.75,
            'context_recall': 0.80
        }
        
        # Setup evaluation run ID for logging
        cls.run_id = os.getenv("EVAL_RUN_ID")
        if not cls.run_id:
            cls.run_id = str(uuid.uuid4())
        
        # Set run ID in context for other tests
        set_run_id(cls.run_id)
        
        # Log run start info
        print(f"Starting evaluation run: {cls.run_id}")
    
    def setup_method(self):
        """Setup method run before each test."""
        if self.rag_pipeline is None:
            # Initialize RAG pipeline
            model_name = os.getenv("MODEL_NAME", "gpt-4o-mini")
            top_k = int(os.getenv("RAG_TOP_K", "4"))
            
            self.rag_pipeline = RAGPipeline(model_name=model_name, top_k=top_k)
            
            # Build index from passages
            passages_path = "data/golden/passages.jsonl"
            if not os.path.exists(passages_path):
                pytest.skip(f"Passages file not found: {passages_path}")
            
            self.rag_pipeline.build_index_from_passages(passages_path)
        
        if self.qa_data is None:
            # Load QA dataset
            qa_path = "data/golden/qaset.jsonl"
            if not os.path.exists(qa_path):
                pytest.skip(f"QA dataset not found: {qa_path}")
            
            self.qa_data = load_qa(qa_path)
    
    def test_faithfulness_threshold(self):
        """Test that faithfulness score meets threshold."""
        # Generate answers for all QA pairs
        eval_samples = []
        
        for qa_item in self.qa_data:
            query = qa_item['query']
            expected_answer = qa_item['answer']
            
            # Get RAG response
            result = self.rag_pipeline.query(query)
            generated_answer = result['answer']
            contexts = result['context']
            
            # Create evaluation sample
            sample = create_eval_sample(
                question=query,
                answer=generated_answer,
                contexts=contexts,
                ground_truth=expected_answer
            )
            eval_samples.append(sample)
        
        # Evaluate with Ragas
        scores = eval_batch(eval_samples)
        
        # Check faithfulness threshold
        faithfulness_score = scores.get('faithfulness', 0.0)
        threshold = self.thresholds['faithfulness']
        
        # Log evaluation results to Snowflake if enabled
        log_evaluation_results(
            run_id=self.run_id,
            metric_group="ragas",
            metrics={"faithfulness": faithfulness_score},
            extra={
                "threshold": threshold,
                "test": "faithfulness_threshold",
                "provider": os.getenv("PROVIDER", "unknown"),
                "model": os.getenv("MODEL_NAME", "unknown")
            }
        )
        
        assert faithfulness_score >= threshold, (
            f"Faithfulness score {faithfulness_score:.3f} is below threshold {threshold}. "
            f"This indicates the model is generating answers not well-grounded in the provided context. "
            f"Review the retrieval quality and answer generation prompts."
        )
    
    def test_context_recall_threshold(self):
        """Test that context recall score meets threshold."""
        # Generate answers for all QA pairs
        eval_samples = []
        
        for qa_item in self.qa_data:
            query = qa_item['query']
            expected_answer = qa_item['answer']
            
            # Get RAG response
            result = self.rag_pipeline.query(query)
            generated_answer = result['answer']
            contexts = result['context']
            
            # Create evaluation sample
            sample = create_eval_sample(
                question=query,
                answer=generated_answer,
                contexts=contexts,
                ground_truth=expected_answer
            )
            eval_samples.append(sample)
        
        # Evaluate with Ragas
        scores = eval_batch(eval_samples)
        
        # Check context recall threshold
        context_recall_score = scores.get('context_recall', 0.0)
        threshold = self.thresholds['context_recall']
        
        # Log evaluation results to Snowflake if enabled
        log_evaluation_results(
            run_id=self.run_id,
            metric_group="ragas",
            metrics={"context_recall": context_recall_score},
            extra={
                "threshold": threshold,
                "test": "context_recall_threshold",
                "provider": os.getenv("PROVIDER", "unknown"),
                "model": os.getenv("MODEL_NAME", "unknown")
            }
        )
        
        assert context_recall_score >= threshold, (
            f"Context recall score {context_recall_score:.3f} is below threshold {threshold}. "
            f"This indicates the retrieval system is not finding relevant context for the questions. "
            f"Review the embedding model, indexing strategy, and passage quality."
        )
    
    def test_combined_quality_thresholds(self):
        """Test that all quality metrics meet their thresholds."""
        # Generate answers for all QA pairs
        eval_samples = []
        
        for qa_item in self.qa_data:
            query = qa_item['query']
            expected_answer = qa_item['answer']
            
            # Get RAG response
            result = self.rag_pipeline.query(query)
            generated_answer = result['answer']
            contexts = result['context']
            
            # Create evaluation sample
            sample = create_eval_sample(
                question=query,
                answer=generated_answer,
                contexts=contexts,
                ground_truth=expected_answer
            )
            eval_samples.append(sample)
        
        # Evaluate with Ragas
        scores = eval_batch(eval_samples)
        
        # Check all thresholds
        threshold_results = check_thresholds(scores, self.thresholds)
        
        # Log combined evaluation results to Snowflake if enabled
        log_evaluation_results(
            run_id=self.run_id,
            metric_group="ragas",
            metrics=scores,
            extra={
                "thresholds": self.thresholds,
                "test": "combined_quality_thresholds",
                "provider": os.getenv("PROVIDER", "unknown"),
                "model": os.getenv("MODEL_NAME", "unknown"),
                "threshold_results": threshold_results
            }
        )
        
        failed_metrics = [
            metric for metric, passed in threshold_results.items() 
            if not passed
        ]
        
        if failed_metrics:
            failure_details = []
            for metric in failed_metrics:
                score = scores.get(metric, 0.0)
                threshold = self.thresholds[metric]
                failure_details.append(f"{metric}: {score:.3f} < {threshold}")
            
            assert False, (
                f"Quality thresholds failed for metrics: {', '.join(failed_metrics)}. "
                f"Details: {'; '.join(failure_details)}. "
                f"This indicates the RAG system needs improvement in these areas."
            )
    
    def test_rag_pipeline_basic_functionality(self):
        """Test basic RAG pipeline functionality before quality evaluation."""
        # Test that pipeline can process a simple query
        test_query = "What is data quality?"
        
        try:
            result = self.rag_pipeline.query(test_query)
            
            # Validate response structure
            assert 'answer' in result, "Response missing 'answer' field"
            assert 'context' in result, "Response missing 'context' field"
            assert isinstance(result['answer'], str), "Answer must be a string"
            assert isinstance(result['context'], list), "Context must be a list"
            assert len(result['context']) > 0, "Context list cannot be empty"
            assert result['answer'].strip() != "", "Answer cannot be empty"
            
        except Exception as e:
            pytest.fail(f"RAG pipeline basic functionality failed: {e}")


if __name__ == "__main__":
    # Run tests directly
    pytest.main([__file__, "-v"])
