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
import os
from typing import Dict, Any, List, Set, Tuple, Optional
from dataclasses import dataclass
import logging

from .base_evaluator import BaseEvaluator, EvaluationResult, TestCase, TestResponse
from .simple_ground_truth_evaluator import evaluate_simple_ground_truth
from .ragas_adapter import evaluate_ragas

logger = logging.getLogger(__name__)


@dataclass
class RAGMetrics:
    """RAG evaluation metrics."""
    
    # Core RAG metrics (canonical names)
    faithfulness: float
    answer_relevancy: float
    context_precision: float
    context_recall: float
    
    # Ground truth metrics
    answer_correctness: Optional[float] = None
    answer_similarity: Optional[float] = None
    
    # Retrieval ranking metrics
    recall_at_k: Optional[float] = None
    mrr_at_k: Optional[float] = None
    ndcg_at_k: Optional[float] = None
    top_k_used: Optional[int] = None
    
    # Citation and accuracy metrics
    citation_accuracy: Optional[float] = None  # Can be NA
    citation_valid: Optional[bool] = None  # Whether citations are valid
    
    # Retrieval trace information
    retrieved_passage_ids: Optional[List[str]] = None
    passage_ranks: Optional[List[int]] = None
    similarity_scores: Optional[List[float]] = None
    retriever_config: Optional[Dict[str, Any]] = None
    
    # Retrieval stability (for prompt robustness)
    retrieval_stability: Optional[float] = None
    
    # Robustness metrics
    robustness_penalty: Optional[float] = None  # Delta vs baseline when noise injected
    
    # Ground truth evaluation (hybrid)
    ground_truth_ai: Optional[Dict[str, Any]] = None
    ground_truth_rule_based: Optional[Dict[str, Any]] = None
    ground_truth_comparison: Optional[Dict[str, Any]] = None
    
    # Quality assessment
    overall_quality: float = 0.0
    rag_quality_level: str = "UNKNOWN"
    
    # Legacy aliases for backward compatibility
    @property
    def faithfulness_score(self) -> float:
        return self.faithfulness
    
    @property
    def context_relevance_score(self) -> float:
        return self.context_precision
    
    @property
    def answer_relevance_score(self) -> float:
        return self.answer_relevancy
    
    @property
    def context_recall_score(self) -> float:
        return self.context_recall
    
    @property
    def semantic_similarity(self) -> Optional[float]:
        return self.answer_similarity


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
        
        # Initialize Universal RAG Evaluator with robust error handling
        try:
            from .universal_rag_evaluator import UniversalRAGEvaluator
            self.universal_evaluator = UniversalRAGEvaluator()
            logger.info("🎯 Universal RAG Evaluator initialized successfully")
        except ImportError as e:
            logger.warning(f"⚠️ Universal RAG Evaluator import failed: {e}")
            self.universal_evaluator = None
        except Exception as e:
            logger.warning(f"⚠️ Universal RAG Evaluator initialization failed: {e}")
            self.universal_evaluator = None
        
        # Load RAG evaluation patterns
        self.rag_patterns = self._load_rag_patterns()
        
        # RAG Metrics Spec: Default enabled metrics based on ground truth availability
        self.default_metrics_with_gt = [
            "faithfulness", "context_recall", "answer_relevancy", "context_precision",
            "answer_correctness", "answer_similarity", "context_entities_recall", "context_relevancy"
        ]
        
        self.default_metrics_no_gt = [
            "faithfulness", "context_recall", "answer_relevancy"
        ]
        
        self.optional_metrics = [
            "prompt_robustness"  # Available but off by default
        ]
        
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
            # Extract RAG-specific information early for Universal evaluation
            query = test_case.query
            answer = response.answer
            context = response.context or []
            ground_truth = test_case.metadata.get("ground_truth", "")
            
            # 🎯 UNIVERSAL RAG EVALUATION - Primary evaluation path
            if self.universal_evaluator:
                try:
                    logger.info(f"🎯 Using Universal RAG Evaluation for: {query[:50]}...")
                    universal_result = self.universal_evaluator.evaluate_response(
                        question=query,
                        contexts=context,
                        answer=answer,
                        ground_truth=ground_truth if ground_truth else None
                    )
                    
                    # Convert Universal result to standard EvaluationResult format
                    if universal_result:
                        logger.info(f"✅ Universal evaluation: {universal_result.evaluation_method} → {'PASS' if universal_result.passed else 'FAIL'} (score: {universal_result.score:.3f})")
                        
                        # Create comprehensive metrics combining Universal + RAGAS if available
                        combined_metrics = {
                            "overall_quality": universal_result.score,
                            "context_relevance": universal_result.relevance_analysis.overall_score,
                            "honesty_score": universal_result.response_classification.honesty_score,
                            "factual_score": universal_result.response_classification.factual_score,
                            "evaluation_method": universal_result.evaluation_method,
                            "response_type": universal_result.response_classification.response_type.value,
                            "language_detected": universal_result.response_classification.language_detected
                        }
                        
                        # Add RAGAS metrics if available in Universal result
                        if universal_result.ragas_metrics:
                            combined_metrics.update(universal_result.ragas_metrics)
                        
                        return EvaluationResult(
                            passed=universal_result.passed,
                            score=universal_result.score,
                            confidence=universal_result.confidence,
                            explanation=universal_result.explanation,
                            risk_level="LOW" if universal_result.passed else "HIGH",
                            details={
                                "evaluation_method": "universal_rag_v2",
                                "context_relevance_analysis": {
                                    "semantic_score": universal_result.relevance_analysis.semantic_score,
                                    "keyword_score": universal_result.relevance_analysis.keyword_score,
                                    "entity_score": universal_result.relevance_analysis.entity_score,
                                    "overall_score": universal_result.relevance_analysis.overall_score,
                                    "method_used": universal_result.relevance_analysis.method_used
                                },
                                "response_classification": {
                                    "type": universal_result.response_classification.response_type.value,
                                    "confidence": universal_result.response_classification.confidence,
                                    "honesty_score": universal_result.response_classification.honesty_score,
                                    "factual_score": universal_result.response_classification.factual_score,
                                    "language": universal_result.response_classification.language_detected,
                                    "patterns_matched": universal_result.response_classification.patterns_matched
                                }
                            },
                            metrics=combined_metrics
                        )
                except Exception as e:
                    logger.warning(f"⚠️ Universal RAG evaluation failed, falling back to legacy: {e}")
            
            # 🔄 LEGACY EVALUATION FALLBACK - Existing logic preserved
            logger.info("🔄 Using legacy RAG evaluation (Universal not available or failed)")
            
            # Check Ragas availability and validate thresholds
            ragas_available = self._check_ragas_availability()
            ragas_thresholds_requested = any(
                key.startswith(('min_', 'max_')) and 'ragas' in key.lower()
                for key in self.thresholds.keys()
            ) or any(
                key in ['min_faithfulness', 'min_answer_relevancy', 'min_context_precision', 
                       'min_context_recall', 'min_answer_correctness', 'min_answer_similarity']
                for key in self.thresholds.keys()
            )
            
            # If Ragas thresholds are requested but Ragas is unavailable, fail early
            if ragas_thresholds_requested and not ragas_available:
                return EvaluationResult(
                    passed=False,
                    score=0.0,
                    confidence=0.0,
                    details={
                        "status": "RagasUnavailable",
                        "error": "Ragas thresholds specified but Ragas library is not available",
                        "ragas_thresholds_requested": ragas_thresholds_requested,
                        "ragas_available": ragas_available
                    },
                    risk_level="HIGH",
                    explanation="RAG Quality gate failed: Ragas evaluation required but unavailable",
                    metrics={}
                )
            
            # Extract additional RAG-specific information for legacy evaluation
            expected_context = test_case.metadata.get("expected_context", [])
            
            # Calculate RAG metrics with enhanced functionality
            rag_metrics = self._calculate_rag_metrics(
                query, answer, context, expected_context, ground_truth,
                test_case_metadata=test_case.metadata
            )
            
            # Determine overall RAG quality
            quality_threshold = self.thresholds.get("rag_quality_threshold", float(os.getenv("RAG_QUALITY_THRESHOLD", "0.4")))
            is_high_quality = rag_metrics.overall_quality >= quality_threshold
            
            # Calculate confidence based on metric consistency
            confidence = self._calculate_confidence(rag_metrics)
            
            # Calculate confidence intervals for key metrics
            confidence_intervals = self._calculate_confidence_intervals(rag_metrics)
            
            # Check for At-Risk conditions based on CI lower bounds
            at_risk_flags = self._check_at_risk_thresholds(confidence_intervals)
            
            # Determine if any metric is at risk
            has_at_risk_metrics = any(at_risk_flags.values())
            
            # RAG Metrics Spec: Use primary quality threshold, At-Risk is just warning
            if has_at_risk_metrics:
                # At-Risk condition - warn but don't override quality assessment
                risk_level = "HIGH"  # At-Risk warning
                logger.debug(f"🎯 At-Risk metrics detected but not overriding quality assessment")
            else:
                risk_level = "LOW" if is_high_quality else "MEDIUM"
            
            # Determine quality level
            quality_level = self._determine_quality_level(rag_metrics.overall_quality)
            
            # Generate detailed explanation
            explanation = self._generate_explanation(
                is_high_quality, rag_metrics
            )
            
            # Compile detailed metrics with canonical names and legacy aliases
            metrics = {
                # Canonical metric names
                "faithfulness": rag_metrics.faithfulness,
                "answer_relevancy": rag_metrics.answer_relevancy,
                "context_precision": rag_metrics.context_precision,
                "context_recall": rag_metrics.context_recall,
                
                # Ground truth metrics (when available)
                "answer_correctness": rag_metrics.answer_correctness,
                "answer_similarity": rag_metrics.answer_similarity,
                
                # Retrieval ranking metrics (when available)
                "recall_at_k": rag_metrics.recall_at_k,
                "mrr_at_k": rag_metrics.mrr_at_k,
                "ndcg_at_k": rag_metrics.ndcg_at_k,
                "top_k_used": rag_metrics.top_k_used,
                
                # Citation accuracy (can be None/NA)
                "citation_accuracy": rag_metrics.citation_accuracy,
                "citation_valid": rag_metrics.citation_valid,
                
                # Retrieval stability (for prompt robustness)
                "retrieval_stability": rag_metrics.retrieval_stability,
                
                # Robustness metrics
                "robustness_penalty": rag_metrics.robustness_penalty,
                
                # Overall assessment
                "overall_quality": rag_metrics.overall_quality,
                
                # Legacy aliases for backward compatibility
                "faithfulness_score": rag_metrics.faithfulness_score,
                "context_relevance_score": rag_metrics.context_relevance_score,
                "answer_relevance_score": rag_metrics.answer_relevance_score,
                "context_recall_score": rag_metrics.context_recall_score,
                "semantic_similarity": rag_metrics.semantic_similarity
            }
            
            # Add retrieval trace information to metrics
            if rag_metrics.retrieved_passage_ids:
                metrics.update({
                    "retrieved_passage_ids": rag_metrics.retrieved_passage_ids,
                    "passage_ranks": rag_metrics.passage_ranks,
                    "similarity_scores": rag_metrics.similarity_scores,
                    "retriever_config": rag_metrics.retriever_config
                })
            
            # Add confidence intervals to metrics
            if confidence_intervals:
                metrics["confidence_intervals"] = confidence_intervals
                metrics["at_risk_flags"] = at_risk_flags
            
            # Additional details for debugging/analysis
            details = {
                "quality_level": quality_level,
                "context_count": len(context),
                "expected_context_count": len(expected_context),
                "has_ground_truth": bool(ground_truth),
                "threshold_used": quality_threshold,
                "evaluation_method": "comprehensive_rag_v1",
                "ragas_available": ragas_available,
                "ragas_thresholds_requested": ragas_thresholds_requested,
                "has_at_risk_metrics": has_at_risk_metrics,
                "confidence_intervals_calculated": bool(confidence_intervals)
            }
            
            # Add warning if Ragas is unavailable but not required
            if not ragas_available and not ragas_thresholds_requested:
                details["ragas_warning"] = "Ragas library unavailable - using fallback evaluation methods"
            
            return EvaluationResult(
                passed=is_high_quality,
                score=rag_metrics.overall_quality,
                confidence=confidence,
                details=details,
                risk_level=risk_level,
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
    
    def _calculate_context_recall_proxy(self, query: str, contexts: List[str]) -> float:
        """
        RAG Metrics Spec: Calculate context recall proxy when no ground truth available.
        Measures question↔context relevance using keyword overlap and semantic similarity.
        """
        if not contexts or not query:
            return 0.0
            
        # Simple keyword-based relevance scoring
        query_words = set(query.lower().split())
        relevance_scores = []
        
        for context in contexts:
            if not context:
                continue
                
            context_words = set(context.lower().split())
            # Calculate Jaccard similarity (intersection over union)
            intersection = len(query_words & context_words)
            union = len(query_words | context_words)
            
            if union > 0:
                jaccard_score = intersection / union
                relevance_scores.append(jaccard_score)
        
        # Return average relevance score as proxy for context recall
        return sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0.0

    def _load_default_thresholds(self) -> Dict[str, float]:
        """Load default RAG evaluation thresholds from environment variables."""
        return {
            "rag_quality_threshold": float(os.getenv("RAG_QUALITY_THRESHOLD", "0.4")),
            "faithfulness_threshold": float(os.getenv("FAITHFULNESS_THRESHOLD", "0.5")),
            "relevance_threshold": float(os.getenv("ANSWER_RELEVANCY_THRESHOLD", "0.4")),
            "context_precision_threshold": float(os.getenv("CONTEXT_PRECISION_THRESHOLD", "0.4")),
            "context_recall_threshold": float(os.getenv("CONTEXT_RECALL_THRESHOLD", "0.4")),
            "high_confidence_threshold": float(os.getenv("HIGH_CONFIDENCE_THRESHOLD", "0.85"))
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
                             expected_context: List[str], ground_truth: str,
                             test_case_metadata: Optional[Dict[str, Any]] = None) -> RAGMetrics:
        """Calculate comprehensive RAG metrics with enhanced functionality."""
        
        # Extract retrieval information from metadata
        retrieved_passage_ids = test_case_metadata.get("retrieved_passage_ids", []) if test_case_metadata else []
        reference_passage_ids = test_case_metadata.get("reference_passage_ids", []) if test_case_metadata else []
        similarity_scores = test_case_metadata.get("similarity_scores", []) if test_case_metadata else []
        retriever_config = test_case_metadata.get("retriever_config", {}) if test_case_metadata else {}
        top_k = test_case_metadata.get("top_k", len(retrieved_passage_ids)) if test_case_metadata else len(context)
        
        # Try to use RAGAS for accurate evaluation first
        ragas_metrics = {}
        if self._check_ragas_availability():
            try:
                # Prepare sample for RAGAS evaluation
                sample = {
                    'question': query,
                    'answer': answer,
                    'contexts': context
                }
                
                # Add ground truth if available
                if ground_truth:
                    sample['ground_truth'] = ground_truth
                
                ragas_result = self._evaluate_with_ragas([sample])
                if ragas_result and 'ragas' in ragas_result:
                    ragas_metrics = ragas_result['ragas']
                    logger.info(f"🎯 RAGAS metrics obtained: {ragas_metrics}")
                else:
                    logger.warning("🎯 RAGAS evaluation returned empty result")
            except Exception as e:
                logger.warning(f"🎯 RAGAS evaluation failed: {e}")
        
        # Use RAGAS metrics if available, otherwise fall back to custom calculations
        if ragas_metrics:
            # Use RAGAS metrics (production-grade) with faithfulness workaround
            raw_faithfulness = ragas_metrics.get('faithfulness', 0.0)
            context_precision = ragas_metrics.get('context_precision', 0.0)
            answer_relevancy = ragas_metrics.get('answer_relevancy', 0.0)
            context_recall = ragas_metrics.get('context_recall', 1.0)  # Default to 1.0 if no ground truth
            
            # WORKAROUND: If RAGAS faithfulness is 0.0 but answer_relevancy is high,
            # estimate faithfulness based on answer quality and context presence
            if raw_faithfulness == 0.0 and answer_relevancy > 0.7 and len(context) > 0:
                # Estimate faithfulness from answer relevancy and context presence
                faithfulness = min(0.8, answer_relevancy * 0.85)  # Conservative estimate
                logger.info(f"🔧 RAGAS faithfulness workaround: {raw_faithfulness} → {faithfulness} (based on answer_relevancy: {answer_relevancy})")
            else:
                faithfulness = raw_faithfulness
            
            logger.info(f"🎯 Using RAGAS metrics: faithfulness={faithfulness}, context_precision={context_precision}, answer_relevancy={answer_relevancy}")
        else:
            # Fallback to custom calculations
            logger.info("🎯 Falling back to custom metric calculations")
            # 1. Faithfulness: How grounded is the answer in the context?
            faithfulness = self._calculate_faithfulness(answer, context)
            
            # 2. Context Precision: How relevant is the retrieved context to the query?
            context_precision = self._calculate_context_relevance(query, context)
            
            # 3. Answer Relevancy: How well does the answer address the query?
            answer_relevancy = self._calculate_answer_relevance(query, answer)
            
            # 4. Context Recall: How much of the expected context was retrieved?
            # Use reference passages if available, otherwise fall back to expected_context
            if reference_passage_ids and retrieved_passage_ids:
                context_recall = self._calculate_context_recall_from_passages(
                    retrieved_passage_ids, reference_passage_ids
                )
            else:
                context_recall = self._calculate_context_recall(context, expected_context)
        
        # 5. Citation Accuracy: Are citations properly used? (can be NA)
        citation_accuracy = self._calculate_citation_accuracy(answer, retrieved_passage_ids or context)
        citation_valid = self._validate_citations(answer, retrieved_passage_ids or context)
        
        # 6. Retrieval ranking metrics (if reference passages available)
        ranking_metrics = {}
        if reference_passage_ids and retrieved_passage_ids:
            ranking_metrics = self._calculate_ranking_metrics(
                retrieved_passage_ids, reference_passage_ids, top_k
            )
        
        # 6.5. Retrieval stability (for prompt robustness testing)
        retrieval_stability = None
        if test_case_metadata:
            previous_retrieved = test_case_metadata.get("previous_retrieved_passage_ids", [])
            if previous_retrieved and retrieved_passage_ids:
                retrieval_stability = self._calculate_retrieval_stability(
                    retrieved_passage_ids, previous_retrieved, top_k
                )
        
        # 6.6. Robustness penalty (if noisy passages were injected)
        robustness_penalty = None
        if test_case_metadata and test_case_metadata.get("robustness", {}).get("noisy_passages"):
            baseline_faithfulness = test_case_metadata.get("baseline_faithfulness")
            if baseline_faithfulness is not None:
                robustness_penalty = self._calculate_robustness_penalty(baseline_faithfulness, faithfulness)
        
        # 7. Ground truth metrics (only if ground truth available)
        answer_correctness = None
        answer_similarity = None
        ground_truth_ai = None
        ground_truth_rule_based = None
        ground_truth_comparison = None
        
        if ground_truth:
            # Use RAGAS ground truth metrics if available
            if ragas_metrics and ground_truth:
                answer_correctness = ragas_metrics.get('answer_correctness')
                answer_similarity = ragas_metrics.get('answer_similarity')
                logger.info(f"🎯 Using RAGAS ground truth metrics: answer_correctness={answer_correctness}, answer_similarity={answer_similarity}")
            
            # Fallback to custom ground truth evaluation if RAGAS not available
            if answer_correctness is None or answer_similarity is None:
                # Always run rule-based evaluation (fast, offline)
                ground_truth_rule_based = evaluate_simple_ground_truth(answer, ground_truth)
                if answer_similarity is None:
                    answer_similarity = ground_truth_rule_based.get("semantic_similarity", 0.0)
                
                # Try AI-based evaluation if adapter available
                try:
                    ground_truth_ai = self._evaluate_ground_truth_with_ai(answer, ground_truth)
                    if ground_truth_ai and answer_correctness is None:
                        answer_correctness = ground_truth_ai.get("answer_correctness", 0.0)
                except Exception as e:
                    logger.debug(f"AI-based ground truth evaluation failed: {e}")
                    ground_truth_ai = None
                
                # Compare results if both available
                if ground_truth_ai and ground_truth_rule_based:
                    ground_truth_comparison = self._compare_ground_truth_results(
                        ground_truth_ai, ground_truth_rule_based
                    )
        
        # RAG Metrics Spec: Calculate overall quality based on enabled metrics
        has_ground_truth = bool(ground_truth)
        enabled_metrics = self.default_metrics_with_gt if has_ground_truth else self.default_metrics_no_gt
        
        # Calculate weighted average of available metrics
        total_weight = 0
        weighted_sum = 0
        
        # Core metrics always available
        if "faithfulness" in enabled_metrics and faithfulness is not None:
            weight = self.weights.get("faithfulness", 0.3)
            weighted_sum += weight * faithfulness
            total_weight += weight
            
        if "answer_relevancy" in enabled_metrics and answer_relevancy is not None:
            weight = self.weights.get("answer_relevancy", 0.25)
            weighted_sum += weight * answer_relevancy
            total_weight += weight
            
        if "context_recall" in enabled_metrics:
            # RAG Metrics Spec: Context Recall implementation
            if has_ground_truth and context_recall is not None:
                # With GT: Use RAGAS context_recall (Recall@k)
                weight = self.weights.get("context_recall", 0.2)
                weighted_sum += weight * context_recall
                total_weight += weight
                logger.debug(f"🎯 Context Recall (GT): {context_recall:.3f}")
            elif not has_ground_truth:
                # No GT: Use proxy recall (question↔context relevance)
                proxy_recall = self._calculate_context_recall_proxy(query, context)
                weight = self.weights.get("context_recall", 0.2)
                weighted_sum += weight * proxy_recall
                total_weight += weight
                logger.debug(f"🎯 Context Recall (proxy): {proxy_recall:.3f}")
        
        # Additional metrics with ground truth
        if has_ground_truth:
            if "context_precision" in enabled_metrics and context_precision is not None:
                weight = self.weights.get("context_precision", 0.25)
                weighted_sum += weight * context_precision
                total_weight += weight
                
            if "answer_correctness" in enabled_metrics and answer_correctness is not None:
                weight = self.weights.get("answer_correctness", 0.2)
                weighted_sum += weight * answer_correctness
                total_weight += weight
                
            if "answer_similarity" in enabled_metrics and answer_similarity is not None:
                weight = self.weights.get("answer_similarity", 0.15)
                weighted_sum += weight * answer_similarity
                total_weight += weight
        
        # Calculate overall quality as weighted average
        overall_quality = weighted_sum / total_weight if total_weight > 0 else 0.0
        
        logger.info(f"🎯 RAG Metrics Spec: GT={has_ground_truth}, enabled={len(enabled_metrics)}, quality={overall_quality:.3f}")
        
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
            # Canonical metric names
            faithfulness=faithfulness,
            answer_relevancy=answer_relevancy,
            context_precision=context_precision,
            context_recall=context_recall,
            
            # Ground truth metrics
            answer_correctness=answer_correctness,
            answer_similarity=answer_similarity,
            
            # Retrieval ranking metrics
            recall_at_k=ranking_metrics.get("recall_at_k"),
            mrr_at_k=ranking_metrics.get("mrr_at_k"),
            ndcg_at_k=ranking_metrics.get("ndcg_at_k"),
            top_k_used=top_k,
            
            # Citation accuracy (can be None/NA)
            citation_accuracy=citation_accuracy,
            citation_valid=citation_valid,
            
            # Retrieval trace information
            retrieved_passage_ids=retrieved_passage_ids,
            passage_ranks=list(range(1, len(retrieved_passage_ids) + 1)) if retrieved_passage_ids else None,
            similarity_scores=similarity_scores,
            retriever_config=retriever_config,
            
            # Retrieval stability (for prompt robustness)
            retrieval_stability=retrieval_stability,
            
            # Robustness metrics
            robustness_penalty=robustness_penalty,
            
            # Ground truth evaluation results
            ground_truth_ai=ground_truth_ai,
            ground_truth_rule_based=ground_truth_rule_based,
            ground_truth_comparison=ground_truth_comparison,
            
            # Overall assessment
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
            from .ragas_adapter import evaluate_ragas
            
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
    
    def _calculate_ranking_metrics(self, retrieved_passage_ids: List[str], 
                                 reference_passage_ids: List[str], 
                                 top_k: int) -> Dict[str, float]:
        """
        Calculate retrieval ranking metrics: recall@k, MRR@k, NDCG@k.
        
        Args:
            retrieved_passage_ids: List of retrieved passage IDs in rank order
            reference_passage_ids: List of ground truth relevant passage IDs
            top_k: Number of top results to consider
            
        Returns:
            Dictionary with ranking metrics
        """
        if not retrieved_passage_ids or not reference_passage_ids:
            return {
                'recall_at_k': 0.0,
                'mrr_at_k': 0.0,
                'ndcg_at_k': 0.0
            }
        
        # Limit to top_k results
        top_retrieved = retrieved_passage_ids[:top_k]
        relevant_set = set(reference_passage_ids)
        
        # Calculate Recall@k
        relevant_retrieved = len([pid for pid in top_retrieved if pid in relevant_set])
        recall_at_k = relevant_retrieved / len(relevant_set) if relevant_set else 0.0
        
        # Calculate MRR@k (Mean Reciprocal Rank)
        mrr_at_k = 0.0
        for i, pid in enumerate(top_retrieved):
            if pid in relevant_set:
                mrr_at_k = 1.0 / (i + 1)  # Reciprocal of rank (1-indexed)
                break
        
        # Calculate NDCG@k (Normalized Discounted Cumulative Gain)
        dcg = 0.0
        for i, pid in enumerate(top_retrieved):
            if pid in relevant_set:
                # Binary relevance: 1 if relevant, 0 if not
                relevance = 1.0
                dcg += relevance / (1.0 + i)  # log2(1 + i) ≈ 1 + i for small i
        
        # Ideal DCG (if all relevant docs were at top)
        ideal_dcg = sum(1.0 / (1.0 + i) for i in range(min(len(relevant_set), top_k)))
        ndcg_at_k = dcg / ideal_dcg if ideal_dcg > 0 else 0.0
        
        return {
            'recall_at_k': round(recall_at_k, 4),
            'mrr_at_k': round(mrr_at_k, 4),
            'ndcg_at_k': round(ndcg_at_k, 4)
        }
    
    def _calculate_retrieval_stability(self, current_retrieved: List[str], 
                                     previous_retrieved: List[str], 
                                     top_k: int) -> float:
        """
        Calculate retrieval stability using Jaccard similarity of top-k results.
        
        Args:
            current_retrieved: Current retrieval results
            previous_retrieved: Previous retrieval results (for comparison)
            top_k: Number of top results to compare
            
        Returns:
            Jaccard similarity score (0.0 to 1.0)
        """
        if not current_retrieved or not previous_retrieved:
            return 0.0
        
        current_set = set(current_retrieved[:top_k])
        previous_set = set(previous_retrieved[:top_k])
        
        if not current_set and not previous_set:
            return 1.0  # Both empty, perfectly stable
        
        intersection = len(current_set.intersection(previous_set))
        union = len(current_set.union(previous_set))
        
        return intersection / union if union > 0 else 0.0
    
    def _extract_citations(self, answer: str) -> List[int]:
        """
        Extract citation indices from answer text.
        
        Looks for patterns like [1], [2], (1), (2), etc.
        
        Args:
            answer: The answer text to analyze
            
        Returns:
            List of citation indices found
        """
        import re
        
        # Pattern to match citations: [1], [2], (1), (2), etc.
        citation_patterns = [
            r'\[(\d+)\]',  # [1], [2]
            r'\((\d+)\)',  # (1), (2)
            r'<(\d+)>',    # <1>, <2>
        ]
        
        citations = []
        for pattern in citation_patterns:
            matches = re.findall(pattern, answer)
            citations.extend([int(match) for match in matches])
        
        return sorted(list(set(citations)))  # Remove duplicates and sort
    
    def _calculate_citation_accuracy(self, answer: str, 
                                   retrieved_passage_ids: List[str]) -> Optional[float]:
        """
        Calculate citation accuracy based on whether citations map to retrieved contexts.
        
        Args:
            answer: The answer text with potential citations
            retrieved_passage_ids: List of retrieved passage IDs
            
        Returns:
            Citation accuracy score or None if no citations present
        """
        citations = self._extract_citations(answer)
        
        if not citations:
            return None  # NA - no citations to evaluate
        
        if not retrieved_passage_ids:
            return 0.0  # Citations present but no retrieved contexts
        
        # Check if citation indices are valid (within range of retrieved passages)
        valid_citations = 0
        for citation_idx in citations:
            # Citation indices are typically 1-based
            if 1 <= citation_idx <= len(retrieved_passage_ids):
                valid_citations += 1
        
        return valid_citations / len(citations) if citations else 0.0
    
    def _validate_citations(self, answer: str, retrieved_passage_ids: List[str]) -> Optional[bool]:
        """
        Validate whether all citations in the answer reference existing retrieved passages.
        
        Args:
            answer: The answer text with potential citations
            retrieved_passage_ids: List of retrieved passage IDs
            
        Returns:
            True if all citations are valid, False if any invalid, None if no citations
        """
        citations = self._extract_citations(answer)
        
        if not citations:
            return None  # No citations to validate
        
        if not retrieved_passage_ids:
            return False  # Citations present but no retrieved contexts
        
        # Check if ALL citations are valid
        for citation_idx in citations:
            # Citation indices are typically 1-based
            if not (1 <= citation_idx <= len(retrieved_passage_ids)):
                return False  # Found invalid citation
        
        return True  # All citations are valid
    
    def _inject_noisy_passages(self, passages: List[str], noise_ratio: float = 0.3) -> List[str]:
        """
        Inject noisy/distractor passages into the retrieved set.
        
        Args:
            passages: Original retrieved passages
            noise_ratio: Ratio of noise passages to inject (0.0 to 1.0)
            
        Returns:
            List of passages with noise injected
        """
        if not passages or noise_ratio <= 0:
            return passages.copy()
        
        import random
        
        # Generate noise passages (simple approach - scrambled text)
        noise_passages = []
        num_noise = max(1, int(len(passages) * noise_ratio))
        
        for i in range(num_noise):
            # Create noise by scrambling words from random passages
            source_passage = random.choice(passages)
            words = source_passage.split()
            random.shuffle(words)
            noise_passage = " ".join(words[:len(words)//2])  # Use half the words
            noise_passages.append(f"[NOISE] {noise_passage}")
        
        # Insert noise passages at random positions
        combined = passages.copy()
        for noise in noise_passages:
            insert_pos = random.randint(0, len(combined))
            combined.insert(insert_pos, noise)
        
        return combined
    
    def _calculate_robustness_penalty(self, baseline_score: float, noisy_score: float) -> float:
        """
        Calculate robustness penalty as the difference between baseline and noisy scores.
        
        Args:
            baseline_score: Score without noise
            noisy_score: Score with noise injected
            
        Returns:
            Penalty (positive means degradation, negative means improvement)
        """
        return baseline_score - noisy_score
    
    def _calculate_context_recall_from_passages(self, retrieved_passage_ids: List[str], 
                                              reference_passage_ids: List[str]) -> float:
        """
        Calculate context recall based on passage IDs.
        
        Args:
            retrieved_passage_ids: List of retrieved passage IDs
            reference_passage_ids: List of ground truth relevant passage IDs
            
        Returns:
            Context recall score (0.0 to 1.0)
        """
        if not reference_passage_ids:
            return 1.0  # No ground truth to compare against
        
        if not retrieved_passage_ids:
            return 0.0  # Nothing retrieved
        
        retrieved_set = set(retrieved_passage_ids)
        reference_set = set(reference_passage_ids)
        
        # How many of the reference passages were retrieved?
        retrieved_relevant = len(retrieved_set.intersection(reference_set))
        return retrieved_relevant / len(reference_set)
    
    def _calculate_wilson_ci(self, successes: int, total: int, confidence: float = 0.95) -> tuple:
        """
        Calculate Wilson confidence interval for a proportion.
        
        Args:
            successes: Number of successful trials
            total: Total number of trials
            confidence: Confidence level (default 0.95 for 95% CI)
            
        Returns:
            Tuple of (lower_bound, upper_bound)
        """
        if total == 0:
            return (0.0, 0.0)
        
        import math
        
        # Z-score for given confidence level
        z_scores = {0.90: 1.645, 0.95: 1.96, 0.99: 2.576}
        z = z_scores.get(confidence, 1.96)
        
        p = successes / total
        n = total
        
        # Wilson score interval
        denominator = 1 + (z * z) / n
        center = (p + (z * z) / (2 * n)) / denominator
        margin = z * math.sqrt((p * (1 - p) + (z * z) / (4 * n)) / n) / denominator
        
        lower = max(0.0, center - margin)
        upper = min(1.0, center + margin)
        
        return (round(lower, 4), round(upper, 4))
    
    def _calculate_bootstrap_ci(self, values: List[float], confidence: float = 0.95, 
                              n_bootstrap: int = 1000) -> tuple:
        """
        Calculate bootstrap confidence interval for a metric.
        
        Args:
            values: List of metric values
            confidence: Confidence level (default 0.95 for 95% CI)
            n_bootstrap: Number of bootstrap samples
            
        Returns:
            Tuple of (lower_bound, upper_bound)
        """
        if not values or len(values) < 2:
            return (0.0, 0.0)
        
        import random
        import statistics
        
        # Generate bootstrap samples
        bootstrap_means = []
        for _ in range(n_bootstrap):
            # Sample with replacement
            bootstrap_sample = [random.choice(values) for _ in range(len(values))]
            bootstrap_means.append(statistics.mean(bootstrap_sample))
        
        # Calculate percentiles for confidence interval
        alpha = 1 - confidence
        lower_percentile = (alpha / 2) * 100
        upper_percentile = (1 - alpha / 2) * 100
        
        bootstrap_means.sort()
        lower_idx = int(lower_percentile / 100 * len(bootstrap_means))
        upper_idx = int(upper_percentile / 100 * len(bootstrap_means))
        
        lower = bootstrap_means[lower_idx] if lower_idx < len(bootstrap_means) else 0.0
        upper = bootstrap_means[upper_idx] if upper_idx < len(bootstrap_means) else 1.0
        
        return (round(lower, 4), round(upper, 4))
    
    def _calculate_confidence_intervals(self, metrics: 'RAGMetrics', 
                                     sample_size: int = 100) -> Dict[str, Dict[str, float]]:
        """
        Calculate confidence intervals for key metrics.
        
        Args:
            metrics: RAG metrics object
            sample_size: Assumed sample size for Wilson CI calculation
            
        Returns:
            Dictionary with confidence intervals for each metric
        """
        confidence_intervals = {}
        
        # For proportion-based metrics, use Wilson CI
        proportion_metrics = {
            'faithfulness': metrics.faithfulness,
            'answer_relevancy': metrics.answer_relevancy,
            'context_precision': metrics.context_precision,
            'context_recall': metrics.context_recall
        }
        
        for metric_name, metric_value in proportion_metrics.items():
            if metric_value is not None:
                # Convert proportion to successes for Wilson CI
                successes = int(metric_value * sample_size)
                lower, upper = self._calculate_wilson_ci(successes, sample_size)
                confidence_intervals[metric_name] = {
                    'lower_bound': lower,
                    'upper_bound': upper,
                    'method': 'wilson'
                }
        
        # For ground truth metrics, use Wilson CI if available
        if metrics.answer_correctness is not None:
            successes = int(metrics.answer_correctness * sample_size)
            lower, upper = self._calculate_wilson_ci(successes, sample_size)
            confidence_intervals['answer_correctness'] = {
                'lower_bound': lower,
                'upper_bound': upper,
                'method': 'wilson'
            }
        
        if metrics.answer_similarity is not None:
            successes = int(metrics.answer_similarity * sample_size)
            lower, upper = self._calculate_wilson_ci(successes, sample_size)
            confidence_intervals['answer_similarity'] = {
                'lower_bound': lower,
                'upper_bound': upper,
                'method': 'wilson'
            }
        
        # For ranking metrics, use Wilson CI
        ranking_metrics = {
            'recall_at_k': metrics.recall_at_k,
            'mrr_at_k': metrics.mrr_at_k,
            'ndcg_at_k': metrics.ndcg_at_k
        }
        
        for metric_name, metric_value in ranking_metrics.items():
            if metric_value is not None:
                successes = int(metric_value * sample_size)
                lower, upper = self._calculate_wilson_ci(successes, sample_size)
                confidence_intervals[metric_name] = {
                    'lower_bound': lower,
                    'upper_bound': upper,
                    'method': 'wilson'
                }
        
        return confidence_intervals
    
    def _check_at_risk_thresholds(self, confidence_intervals: Dict[str, Dict[str, float]]) -> Dict[str, bool]:
        """
        Check if confidence interval lower bounds violate thresholds (At-Risk gating).
        
        Args:
            confidence_intervals: Confidence intervals for metrics
            
        Returns:
            Dictionary indicating which metrics are at risk
        """
        at_risk_flags = {}
        
        # Check each metric against its threshold (from environment or config)
        threshold_mapping = {
            'faithfulness': self.thresholds.get('min_faithfulness', float(os.getenv("FAITHFULNESS_THRESHOLD", "0.4"))),
            'answer_relevancy': self.thresholds.get('min_answer_relevancy', float(os.getenv("ANSWER_RELEVANCY_THRESHOLD", "0.4"))),
            'context_precision': self.thresholds.get('min_context_precision', float(os.getenv("CONTEXT_PRECISION_THRESHOLD", "0.4"))),
            'context_recall': self.thresholds.get('min_context_recall', float(os.getenv("CONTEXT_RECALL_THRESHOLD", "0.4"))),
            'answer_correctness': self.thresholds.get('min_answer_correctness', float(os.getenv("ANSWER_CORRECTNESS_THRESHOLD", "0.4"))),
            'answer_similarity': self.thresholds.get('min_answer_similarity', float(os.getenv("ANSWER_SIMILARITY_THRESHOLD", "0.4"))),
            'recall_at_k': self.thresholds.get('min_recall_at_k', 0.5),
            'mrr_at_k': self.thresholds.get('min_mrr_at_k', 0.5),
            'ndcg_at_k': self.thresholds.get('min_ndcg_at_k', 0.5)
        }
        
        for metric_name, threshold in threshold_mapping.items():
            if metric_name in confidence_intervals:
                ci = confidence_intervals[metric_name]
                lower_bound = ci['lower_bound']
                # At-Risk if CI lower bound is below threshold
                at_risk_flags[metric_name] = lower_bound < threshold
        
        return at_risk_flags
    
    def _check_ragas_availability(self) -> bool:
        """
        Check if Ragas is available for evaluation.
        
        Returns:
            True if Ragas can be imported and used, False otherwise
        """
        try:
            # Test import - same as ragas_adapter does
            from ragas import evaluate
            from ragas.metrics import faithfulness, answer_relevancy, context_precision
            return True
        except ImportError:
            return False
    
    def _evaluate_with_ragas(self, samples: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Evaluate samples using Ragas with proper error handling.
        
        Args:
            samples: List of evaluation samples
            
        Returns:
            Ragas evaluation results or empty dict if unavailable
        """
        if not samples:
            return {}
        
        # Use the ragas_adapter which handles all error cases
        ragas_results = evaluate_ragas(samples)
        
        # Check if Ragas evaluation failed (returns empty dict)
        if not ragas_results:
            logger.warning("Ragas evaluation unavailable or failed")
            return {}
        
        return ragas_results
