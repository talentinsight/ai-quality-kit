"""
Professional RAG Evaluator for retrieval-augmented generation quality.

This evaluator implements comprehensive RAG evaluation using:
- Faithfulness (answer grounded in context)
- Context relevance (retrieved context quality)
- Answer relevance (response addresses question)
- Context recall (ground truth coverage)
- Semantic similarity scoring
- Citation accuracy assessment
"""

import re
import json
from typing import Dict, Any, List, Set, Tuple, Optional
from dataclasses import dataclass
import logging

from .base_evaluator import BaseEvaluator, EvaluationResult, TestCase, TestResponse
from .simple_ground_truth_evaluator import evaluate_simple_ground_truth

logger = logging.getLogger(__name__)


@dataclass
class RAGMetrics:
    """RAG evaluation metrics."""
    
    # Core RAG metrics
    faithfulness_score: float
    context_relevance_score: float
    answer_relevance_score: float
    context_recall_score: float
    
    # Additional metrics
    citation_accuracy: float
    semantic_similarity: float
    
    # Ground truth evaluation (hybrid)
    ground_truth_ai: Optional[Dict[str, Any]]
    ground_truth_rule_based: Optional[Dict[str, Any]]
    ground_truth_comparison: Optional[Dict[str, Any]]
    
    # Quality assessment
    overall_quality: float
    rag_quality_level: str


class RAGEvaluator(BaseEvaluator):
    """
    Professional RAG evaluator for retrieval-augmented generation quality.
    
    Features:
    - Multi-dimensional RAG quality assessment
    - Faithfulness and hallucination detection
    - Context relevance and recall evaluation
    - Answer relevance scoring
    - Citation accuracy verification
    - Semantic similarity measurement
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        
        # Load RAG evaluation patterns
        self.rag_patterns = self._load_rag_patterns()
        
        # Load evaluation weights from config
        self.weights = self.config.get("weights", {
            "faithfulness": 0.3,
            "context_relevance": 0.25,
            "answer_relevance": 0.25,
            "context_recall": 0.2
        })
        
        # Citation patterns for accuracy checking
        self.citation_patterns = [
            r'\[(\d+)\]',  # [1], [2], etc.
            r'\((\d+)\)',  # (1), (2), etc.
            r'source\s*(\d+)',  # source 1, source2, etc.
            r'reference\s*(\d+)',  # reference 1, etc.
        ]
    
    def evaluate(self, test_case: TestCase, response: TestResponse) -> EvaluationResult:
        """
        Evaluate RAG quality of a single test case response.
        
        Args:
            test_case: RAG test case with query and expected context
            response: LLM response with retrieved context
            
        Returns:
            Detailed RAG evaluation result
        """
        try:
            # Extract RAG-specific information
            query = test_case.query
            answer = response.answer
            context = response.context or []
            expected_context = test_case.metadata.get("expected_context", [])
            ground_truth = test_case.metadata.get("ground_truth", "")
            
            # Calculate RAG metrics
            rag_metrics = self._calculate_rag_metrics(
                query, answer, context, expected_context, ground_truth
            )
            
            # Determine overall RAG quality
            quality_threshold = self.thresholds.get("rag_quality_threshold", 0.7)
            is_high_quality = rag_metrics.overall_quality >= quality_threshold
            
            # Calculate confidence based on metric consistency
            confidence = self._calculate_confidence(rag_metrics)
            
            # Determine quality level
            quality_level = self._determine_quality_level(rag_metrics.overall_quality)
            
            # Generate detailed explanation
            explanation = self._generate_explanation(
                is_high_quality, rag_metrics
            )
            
            # Compile detailed metrics
            metrics = {
                "faithfulness_score": rag_metrics.faithfulness_score,
                "context_relevance_score": rag_metrics.context_relevance_score,
                "answer_relevance_score": rag_metrics.answer_relevance_score,
                "context_recall_score": rag_metrics.context_recall_score,
                "citation_accuracy": rag_metrics.citation_accuracy,
                "semantic_similarity": rag_metrics.semantic_similarity,
                "overall_quality": rag_metrics.overall_quality
            }
            
            # Additional details for debugging/analysis
            details = {
                "quality_level": quality_level,
                "context_count": len(context),
                "expected_context_count": len(expected_context),
                "has_ground_truth": bool(ground_truth),
                "threshold_used": quality_threshold,
                "evaluation_method": "comprehensive_rag_v1"
            }
            
            return EvaluationResult(
                passed=is_high_quality,
                score=rag_metrics.overall_quality,
                confidence=confidence,
                details=details,
                risk_level="LOW" if is_high_quality else "MEDIUM",
                explanation=explanation,
                metrics=metrics
            )
            
        except Exception as e:
            logger.error(f"RAG evaluation error for test {test_case.test_id}: {e}")
            return EvaluationResult(
                passed=False,
                score=0.0,
                confidence=0.0,
                details={"error": str(e)},
                risk_level="HIGH",
                explanation=f"Evaluation failed: {str(e)}",
                metrics={}
            )
    
    def evaluate_batch(self, test_cases: List[TestCase], responses: List[TestResponse]) -> List[EvaluationResult]:
        """
        Evaluate a batch of RAG test cases.
        
        Args:
            test_cases: List of RAG test cases
            responses: List of corresponding responses
            
        Returns:
            List of RAG evaluation results
        """
        if len(test_cases) != len(responses):
            raise ValueError("Number of test cases must match number of responses")
        
        results = []
        for test_case, response in zip(test_cases, responses):
            result = self.evaluate(test_case, response)
            results.append(result)
        
        return results
    
    def _load_default_thresholds(self) -> Dict[str, float]:
        """Load default RAG evaluation thresholds."""
        return {
            "rag_quality_threshold": 0.7,  # Minimum score for high quality RAG
            "faithfulness_threshold": 0.8,  # Minimum faithfulness score
            "relevance_threshold": 0.7,  # Minimum relevance score
            "high_confidence_threshold": 0.85  # High confidence threshold
        }
    
    def _load_rag_patterns(self) -> Dict[str, List[str]]:
        """Load RAG evaluation patterns."""
        return {
            "faithfulness_indicators": [
                "according to", "based on", "the document states", "as mentioned",
                "the context shows", "from the provided information", "the source indicates"
            ],
            "hallucination_indicators": [
                "i believe", "i think", "probably", "might be", "could be",
                "in my opinion", "generally speaking", "typically", "usually"
            ],
            "relevance_indicators": [
                "directly addresses", "answers the question", "relevant to",
                "pertains to", "relates to", "concerning", "regarding"
            ],
            "irrelevance_indicators": [
                "unrelated", "off-topic", "not relevant", "doesn't address",
                "not applicable", "different topic", "unconnected"
            ]
        }
    
    def _calculate_rag_metrics(self, query: str, answer: str, context: List[str],
                             expected_context: List[str], ground_truth: str) -> RAGMetrics:
        """Calculate comprehensive RAG metrics."""
        
        # 1. Faithfulness: How grounded is the answer in the context?
        faithfulness_score = self._calculate_faithfulness(answer, context)
        
        # 2. Context Relevance: How relevant is the retrieved context to the query?
        context_relevance_score = self._calculate_context_relevance(query, context)
        
        # 3. Answer Relevance: How well does the answer address the query?
        answer_relevance_score = self._calculate_answer_relevance(query, answer)
        
        # 4. Context Recall: How much of the expected context was retrieved?
        context_recall_score = self._calculate_context_recall(context, expected_context)
        
        # 5. Citation Accuracy: Are citations properly used?
        citation_accuracy = self._calculate_citation_accuracy(answer, context)
        
        # 6. Semantic Similarity: Overall semantic alignment
        semantic_similarity = self._calculate_semantic_similarity(answer, ground_truth)
        
        # 7. Hybrid Ground Truth Evaluation
        ground_truth_ai = None
        ground_truth_rule_based = None
        ground_truth_comparison = None
        
        if ground_truth:
            # Always run rule-based evaluation (fast, offline)
            ground_truth_rule_based = evaluate_simple_ground_truth(answer, ground_truth)
            
            # Try AI-based evaluation if adapter available
            try:
                ground_truth_ai = self._evaluate_ground_truth_with_ai(answer, ground_truth)
            except Exception as e:
                logger.debug(f"AI-based ground truth evaluation failed: {e}")
                ground_truth_ai = None
            
            # Compare results if both available
            if ground_truth_ai and ground_truth_rule_based:
                ground_truth_comparison = self._compare_ground_truth_results(
                    ground_truth_ai, ground_truth_rule_based
                )
        
        # Calculate overall quality score
        overall_quality = (
            self.weights["faithfulness"] * faithfulness_score +
            self.weights["context_relevance"] * context_relevance_score +
            self.weights["answer_relevance"] * answer_relevance_score +
            self.weights["context_recall"] * context_recall_score
        )
        
        # Determine quality level
        if overall_quality >= 0.8:
            rag_quality_level = "EXCELLENT"
        elif overall_quality >= 0.7:
            rag_quality_level = "GOOD"
        elif overall_quality >= 0.5:
            rag_quality_level = "FAIR"
        else:
            rag_quality_level = "POOR"
        
        return RAGMetrics(
            faithfulness_score=faithfulness_score,
            context_relevance_score=context_relevance_score,
            answer_relevance_score=answer_relevance_score,
            context_recall_score=context_recall_score,
            citation_accuracy=citation_accuracy,
            semantic_similarity=semantic_similarity,
            ground_truth_ai=ground_truth_ai,
            ground_truth_rule_based=ground_truth_rule_based,
            ground_truth_comparison=ground_truth_comparison,
            overall_quality=overall_quality,
            rag_quality_level=rag_quality_level
        )
    
    def _calculate_faithfulness(self, answer: str, context: List[str]) -> float:
        """Calculate faithfulness score (how grounded the answer is in context)."""
        if not context:
            return 0.0
        
        answer_lower = answer.lower()
        context_text = " ".join(context).lower()
        
        # Check for faithfulness indicators
        faithfulness_indicators = sum(
            1 for pattern in self.rag_patterns["faithfulness_indicators"]
            if pattern in answer_lower
        )
        
        # Check for hallucination indicators (negative score)
        hallucination_indicators = sum(
            1 for pattern in self.rag_patterns["hallucination_indicators"]
            if pattern in answer_lower
        )
        
        # Simple overlap calculation (can be enhanced with embeddings)
        answer_words = set(answer_lower.split())
        context_words = set(context_text.split())
        overlap_ratio = len(answer_words.intersection(context_words)) / max(len(answer_words), 1)
        
        # Combine signals
        faithfulness_score = (
            0.4 * overlap_ratio +
            0.3 * min(faithfulness_indicators / 2.0, 1.0) +
            0.3 * max(0, 1.0 - hallucination_indicators / 3.0)
        )
        
        return min(faithfulness_score, 1.0)
    
    def _calculate_context_relevance(self, query: str, context: List[str]) -> float:
        """Calculate context relevance score."""
        if not context:
            return 0.0
        
        query_lower = query.lower()
        query_words = set(query_lower.split())
        
        relevant_contexts = 0
        for ctx in context:
            ctx_lower = ctx.lower()
            ctx_words = set(ctx_lower.split())
            
            # Calculate word overlap
            overlap_ratio = len(query_words.intersection(ctx_words)) / max(len(query_words), 1)
            
            # Check for relevance indicators
            relevance_score = overlap_ratio
            if any(pattern in ctx_lower for pattern in self.rag_patterns["relevance_indicators"]):
                relevance_score += 0.2
            if any(pattern in ctx_lower for pattern in self.rag_patterns["irrelevance_indicators"]):
                relevance_score -= 0.3
            
            if relevance_score > 0.3:  # Threshold for relevance
                relevant_contexts += 1
        
        return relevant_contexts / len(context)
    
    def _calculate_answer_relevance(self, query: str, answer: str) -> float:
        """Calculate answer relevance score."""
        query_lower = query.lower()
        answer_lower = answer.lower()
        
        query_words = set(query_lower.split())
        answer_words = set(answer_lower.split())
        
        # Word overlap
        overlap_ratio = len(query_words.intersection(answer_words)) / max(len(query_words), 1)
        
        # Check for direct question addressing
        question_words = ["what", "how", "why", "when", "where", "who", "which"]
        query_has_question = any(qw in query_lower for qw in question_words)
        
        relevance_score = overlap_ratio
        
        if query_has_question:
            # Boost score if answer seems to address the question type
            if "what" in query_lower and any(word in answer_lower for word in ["is", "are", "means", "refers"]):
                relevance_score += 0.2
            elif "how" in query_lower and any(word in answer_lower for word in ["by", "through", "using", "steps"]):
                relevance_score += 0.2
            elif "why" in query_lower and any(word in answer_lower for word in ["because", "due to", "reason", "since"]):
                relevance_score += 0.2
        
        return min(relevance_score, 1.0)
    
    def _calculate_context_recall(self, retrieved_context: List[str], expected_context: List[str]) -> float:
        """Calculate context recall score."""
        if not expected_context:
            return 1.0  # No ground truth to compare against
        
        if not retrieved_context:
            return 0.0
        
        # Simple word-based recall calculation
        expected_words = set()
        for ctx in expected_context:
            expected_words.update(ctx.lower().split())
        
        retrieved_words = set()
        for ctx in retrieved_context:
            retrieved_words.update(ctx.lower().split())
        
        if not expected_words:
            return 1.0
        
        recall = len(expected_words.intersection(retrieved_words)) / len(expected_words)
        return min(recall, 1.0)
    
    def _calculate_citation_accuracy(self, answer: str, context: List[str]) -> float:
        """Calculate citation accuracy score."""
        if not context:
            return 1.0  # No context to cite
        
        # Find all citations in the answer
        citations = []
        for pattern in self.citation_patterns:
            citations.extend(re.findall(pattern, answer, re.IGNORECASE))
        
        if not citations:
            return 0.8  # No citations used, but not necessarily wrong
        
        # Check if cited sources exist
        valid_citations = 0
        for citation in citations:
            try:
                citation_num = int(citation) - 1  # Convert to 0-based index
                if 0 <= citation_num < len(context):
                    valid_citations += 1
            except ValueError:
                continue
        
        if not citations:
            return 1.0
        
        return valid_citations / len(citations)
    
    def _calculate_semantic_similarity(self, answer: str, ground_truth: str) -> float:
        """Calculate semantic similarity (simplified version)."""
        if not ground_truth:
            return 0.5  # No ground truth available
        
        # Simple word-based similarity (can be enhanced with embeddings)
        answer_words = set(answer.lower().split())
        truth_words = set(ground_truth.lower().split())
        
        if not truth_words:
            return 0.5
        
        intersection = len(answer_words.intersection(truth_words))
        union = len(answer_words.union(truth_words))
        
        if union == 0:
            return 0.0
        
        jaccard_similarity = intersection / union
        return jaccard_similarity
    
    def _calculate_confidence(self, rag_metrics: RAGMetrics) -> float:
        """Calculate confidence in the RAG evaluation result."""
        
        # High confidence when metrics are consistent
        metrics_list = [
            rag_metrics.faithfulness_score,
            rag_metrics.context_relevance_score,
            rag_metrics.answer_relevance_score,
            rag_metrics.context_recall_score
        ]
        
        # Calculate standard deviation (lower = more consistent = higher confidence)
        mean_score = sum(metrics_list) / len(metrics_list)
        variance = sum((x - mean_score) ** 2 for x in metrics_list) / len(metrics_list)
        std_dev = variance ** 0.5
        
        # Convert to confidence (lower std_dev = higher confidence)
        consistency_confidence = max(0, 1.0 - std_dev * 2)
        
        # Boost confidence for high overall quality
        quality_confidence = min(rag_metrics.overall_quality * 1.2, 1.0)
        
        # Combined confidence
        combined_confidence = (consistency_confidence + quality_confidence) / 2
        
        return min(combined_confidence, 1.0)
    
    def _determine_quality_level(self, overall_quality: float) -> str:
        """Determine RAG quality level based on overall score."""
        if overall_quality >= 0.9:
            return "EXCELLENT"
        elif overall_quality >= 0.8:
            return "VERY_GOOD"
        elif overall_quality >= 0.7:
            return "GOOD"
        elif overall_quality >= 0.6:
            return "FAIR"
        elif overall_quality >= 0.4:
            return "POOR"
        else:
            return "VERY_POOR"
    
    def _evaluate_ground_truth_with_ai(self, answer: str, ground_truth: str) -> Optional[Dict[str, Any]]:
        """
        Evaluate ground truth using AI-based methods (Ragas).
        
        This method attempts to use external LLM APIs for semantic evaluation.
        Falls back gracefully if APIs are unavailable.
        """
        try:
            # Try to use Ragas for AI-based evaluation
            from apps.orchestrator.evaluators.ragas_adapter import evaluate_ragas
            
            # Prepare sample for Ragas
            samples = [{
                'question': 'Ground truth evaluation',
                'answer': answer,
                'contexts': [ground_truth],  # Use ground truth as context
                'ground_truth': ground_truth
            }]
            
            ragas_result = evaluate_ragas(samples)
            if ragas_result and 'ragas' in ragas_result:
                return {
                    'method': 'ragas_ai',
                    'answer_correctness': ragas_result['ragas'].get('answer_correctness', 0.0),
                    'answer_similarity': ragas_result['ragas'].get('answer_similarity', 0.0),
                    'overall_score': ragas_result['ragas'].get('answer_correctness', 0.0)
                }
        except Exception as e:
            logger.debug(f"Ragas AI evaluation failed: {e}")
        
        # Fallback: return None to indicate AI evaluation unavailable
        return None
    
    def _compare_ground_truth_results(self, ai_result: Dict[str, Any], 
                                    rule_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compare AI-based and rule-based ground truth evaluation results.
        
        Returns comparison metrics including agreement and confidence.
        """
        ai_score = ai_result.get('overall_score', 0.0)
        rule_score = rule_result.get('overall_score', 0.0)
        
        # Calculate agreement (how close the scores are)
        score_diff = abs(ai_score - rule_score)
        agreement = max(0.0, 1.0 - score_diff)
        
        # Calculate confidence based on agreement
        if agreement >= 0.9:
            confidence = "VERY_HIGH"
            confidence_score = 0.95
        elif agreement >= 0.8:
            confidence = "HIGH"
            confidence_score = 0.85
        elif agreement >= 0.7:
            confidence = "MEDIUM"
            confidence_score = 0.75
        elif agreement >= 0.6:
            confidence = "LOW"
            confidence_score = 0.65
        else:
            confidence = "VERY_LOW"
            confidence_score = 0.5
        
        # Generate recommendation
        if agreement >= 0.8:
            if ai_score >= 0.7 and rule_score >= 0.7:
                recommendation = "Both methods agree - high quality answer"
            elif ai_score <= 0.4 and rule_score <= 0.4:
                recommendation = "Both methods agree - low quality answer"
            else:
                recommendation = "Both methods agree - moderate quality answer"
        else:
            if ai_score > rule_score:
                recommendation = "AI evaluation more positive - semantic quality detected"
            else:
                recommendation = "Rule-based evaluation more positive - structural quality detected"
        
        return {
            'agreement': round(agreement, 3),
            'confidence': confidence,
            'confidence_score': round(confidence_score, 3),
            'ai_score': round(ai_score, 3),
            'rule_score': round(rule_score, 3),
            'score_difference': round(score_diff, 3),
            'recommendation': recommendation
        }
    
    def _generate_explanation(self, is_high_quality: bool, rag_metrics: RAGMetrics) -> str:
        """Generate human-readable explanation of the RAG evaluation."""
        
        if is_high_quality:
            explanation = f"✅ HIGH QUALITY RAG: Overall quality {rag_metrics.overall_quality:.3f}"
            explanation += f" (faithfulness: {rag_metrics.faithfulness_score:.2f}, "
            explanation += f"relevance: {rag_metrics.answer_relevance_score:.2f})"
        else:
            explanation = f"⚠️ LOW QUALITY RAG: Overall quality {rag_metrics.overall_quality:.3f}"
            
            # Identify main issues
            issues = []
            if rag_metrics.faithfulness_score < 0.6:
                issues.append("low faithfulness")
            if rag_metrics.context_relevance_score < 0.6:
                issues.append("poor context relevance")
            if rag_metrics.answer_relevance_score < 0.6:
                issues.append("answer not relevant")
            if rag_metrics.context_recall_score < 0.5:
                issues.append("incomplete context recall")
            
            if issues:
                explanation += f" - Issues: {', '.join(issues)}"
        
        return explanation
    
    def _get_required_config_keys(self) -> List[str]:
        """Get required configuration keys for RAG evaluator."""
        return []  # No required keys, all have defaults
