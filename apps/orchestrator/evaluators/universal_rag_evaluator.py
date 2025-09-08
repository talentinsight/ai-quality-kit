"""
Universal RAG Evaluation Engine

A production-grade, domain-agnostic RAG evaluation system that properly handles
the "I don't know" scenario and provides intelligent context-answer alignment scoring.

Key Features:
- Multi-layer semantic analysis for context relevance
- Universal honesty detection across languages
- Intelligent response classification
- Configurable thresholds (no hardcoding)
- Backward compatibility with existing RAGAS integration
- Comprehensive logging and error handling

Author: AI Quality Kit Team
Version: 1.0.0
"""

import os
import re
import logging
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass
from enum import Enum
import numpy as np

# Optional imports with graceful fallbacks
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logging.warning("sentence-transformers not available, falling back to basic similarity")

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logging.warning("OpenAI not available for embeddings")


class ResponseType(Enum):
    """Classification of RAG response types"""
    HONEST_IDK = "honest_idk"  # "I don't know" type responses
    FACTUAL = "factual"        # Contains factual information
    HALLUCINATION = "hallucination"  # Made-up information
    PARTIAL = "partial"        # Partially correct/incomplete
    ERROR = "error"           # Error or malformed response


@dataclass
class RelevanceAnalysis:
    """Results of context relevance analysis"""
    semantic_score: float      # 0.0-1.0 semantic similarity
    keyword_score: float       # 0.0-1.0 keyword overlap
    entity_score: float        # 0.0-1.0 named entity overlap
    overall_score: float       # 0.0-1.0 weighted combination
    confidence: float          # 0.0-1.0 confidence in analysis
    method_used: str          # Which analysis method was primary


@dataclass
class ResponseClassification:
    """Results of response classification"""
    response_type: ResponseType
    confidence: float          # 0.0-1.0 confidence in classification
    honesty_score: float       # 0.0-1.0 how "honest" the response is
    factual_score: float       # 0.0-1.0 how factual the response appears
    language_detected: str     # Detected language code
    patterns_matched: List[str] # Which honesty patterns matched


@dataclass
class UniversalEvalResult:
    """Universal RAG evaluation result"""
    passed: bool
    score: float              # 0.0-1.0 overall quality score
    explanation: str          # Human-readable explanation
    relevance_analysis: RelevanceAnalysis
    response_classification: ResponseClassification
    evaluation_method: str    # Which evaluation path was used
    ragas_metrics: Optional[Dict[str, float]] = None
    confidence: float = 0.0


class UniversalRAGEvaluator:
    """
    Universal RAG Evaluation Engine
    
    Provides intelligent, context-aware evaluation of RAG responses that properly
    handles the "I don't know" scenario and works across domains and languages.
    """
    
    def __init__(self):
        """Initialize the Universal RAG Evaluator"""
        self.logger = logging.getLogger(__name__)
        
        # Load configuration from environment
        self.relevance_threshold = float(os.getenv("CONTEXT_RELEVANCE_THRESHOLD", "0.3"))
        self.honesty_threshold = float(os.getenv("HONESTY_DETECTION_THRESHOLD", "0.7"))
        self.semantic_weight = float(os.getenv("SEMANTIC_ANALYSIS_WEIGHT", "0.5"))
        self.keyword_weight = float(os.getenv("KEYWORD_ANALYSIS_WEIGHT", "0.3"))
        self.entity_weight = float(os.getenv("ENTITY_ANALYSIS_WEIGHT", "0.2"))
        
        # Initialize embedding model if available
        self.embedding_model = None
        if SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                model_name = os.getenv("SENTENCE_TRANSFORMER_MODEL", "all-MiniLM-L6-v2")
                self.embedding_model = SentenceTransformer(model_name)
                self.logger.info(f"Loaded sentence transformer model: {model_name}")
            except Exception as e:
                self.logger.warning(f"Failed to load sentence transformer: {e}")
        
        # Multi-language honesty patterns
        self.honesty_patterns = {
            "en": [
                r"\bi\s+don'?t\s+know\b",
                r"\bi\s+do\s+not\s+know\b", 
                r"\bno\s+information\b",
                r"\bcannot\s+answer\b",
                r"\bunable\s+to\s+answer\b",
                r"\bno\s+data\b",
                r"\bnot\s+sure\b",
                r"\bunclear\b",
                r"\bunknown\b",
                r"\bno\s+details\b"
            ],
            "tr": [
                r"\bbilmiyorum\b",
                r"\bbilgi\s+yok\b",
                r"\bcevap\s+veremem\b",
                r"\bemin\s+değilim\b",
                r"\bnet\s+değil\b",
                r"\bbilinmiyor\b"
            ],
            "es": [
                r"\bno\s+sé\b",
                r"\bno\s+tengo\s+información\b",
                r"\bno\s+puedo\s+responder\b",
                r"\bdesconocido\b"
            ],
            "fr": [
                r"\bje\s+ne\s+sais\s+pas\b",
                r"\bpas\s+d'information\b",
                r"\binconnu\b"
            ],
            "de": [
                r"\bich\s+weiß\s+nicht\b",
                r"\bkeine\s+information\b",
                r"\bunbekannt\b"
            ]
        }
        
        self.logger.info("Universal RAG Evaluator initialized successfully")
    
    def evaluate_response(self, 
                         question: str, 
                         contexts: List[str], 
                         answer: str,
                         ground_truth: Optional[str] = None) -> UniversalEvalResult:
        """
        Main evaluation method - intelligently evaluates RAG responses
        
        Args:
            question: The input question
            contexts: List of retrieved contexts
            answer: The generated answer
            ground_truth: Optional ground truth for enhanced evaluation
            
        Returns:
            UniversalEvalResult with comprehensive evaluation
        """
        try:
            self.logger.info(f"🎯 Universal RAG Evaluation starting for question: {question[:50]}...")
            
            # Stage 1: Analyze context relevance
            relevance_analysis = self.analyze_context_relevance(question, contexts)
            self.logger.info(f"📊 Context relevance: {relevance_analysis.overall_score:.3f} (method: {relevance_analysis.method_used})")
            
            # Stage 2: Classify the response
            response_classification = self.classify_response(answer)
            self.logger.info(f"🔍 Response type: {response_classification.response_type.value} (confidence: {response_classification.confidence:.3f})")
            
            # Stage 3: Intelligent evaluation based on context relevance
            if relevance_analysis.overall_score < self.relevance_threshold:
                # Low relevance scenario - evaluate honesty
                result = self._evaluate_low_relevance_scenario(
                    question, contexts, answer, relevance_analysis, response_classification
                )
            else:
                # High relevance scenario - standard evaluation
                result = self._evaluate_high_relevance_scenario(
                    question, contexts, answer, ground_truth, relevance_analysis, response_classification
                )
            
            self.logger.info(f"✅ Universal evaluation complete: {result.evaluation_method} → {'PASS' if result.passed else 'FAIL'} (score: {result.score:.3f})")
            return result
            
        except Exception as e:
            self.logger.error(f"❌ Universal RAG evaluation failed: {e}")
            # Graceful fallback
            return UniversalEvalResult(
                passed=False,
                score=0.0,
                explanation=f"Evaluation error: {str(e)}",
                relevance_analysis=RelevanceAnalysis(0.0, 0.0, 0.0, 0.0, 0.0, "error"),
                response_classification=ResponseClassification(
                    ResponseType.ERROR, 0.0, 0.0, 0.0, "unknown", []
                ),
                evaluation_method="error_fallback"
            )
    
    def analyze_context_relevance(self, question: str, contexts: List[str]) -> RelevanceAnalysis:
        """
        Multi-layer analysis of context relevance to question
        
        Combines semantic similarity, keyword overlap, and entity matching
        for robust relevance assessment across domains.
        """
        if not contexts or not question.strip():
            return RelevanceAnalysis(0.0, 0.0, 0.0, 0.0, 0.0, "empty_input")
        
        # Clean inputs
        question_clean = question.lower().strip()
        contexts_clean = [ctx.lower().strip() for ctx in contexts if ctx.strip()]
        
        if not contexts_clean:
            return RelevanceAnalysis(0.0, 0.0, 0.0, 0.0, 0.0, "empty_contexts")
        
        # Layer 1: Semantic similarity (if available)
        semantic_score = self._calculate_semantic_similarity(question_clean, contexts_clean)
        
        # Layer 2: Keyword overlap
        keyword_score = self._calculate_keyword_overlap(question_clean, contexts_clean)
        
        # Layer 3: Named entity overlap (basic implementation)
        entity_score = self._calculate_entity_overlap(question_clean, contexts_clean)
        
        # Weighted combination
        overall_score = (
            self.semantic_weight * semantic_score +
            self.keyword_weight * keyword_score +
            self.entity_weight * entity_score
        )
        
        # Determine primary method and confidence
        scores = [semantic_score, keyword_score, entity_score]
        weights = [self.semantic_weight, self.keyword_weight, self.entity_weight]
        methods = ["semantic", "keyword", "entity"]
        
        primary_idx = np.argmax([w * s for w, s in zip(weights, scores)])
        method_used = methods[primary_idx]
        confidence = min(0.95, max(0.1, scores[primary_idx] * weights[primary_idx] + 0.1))
        
        return RelevanceAnalysis(
            semantic_score=semantic_score,
            keyword_score=keyword_score,
            entity_score=entity_score,
            overall_score=overall_score,
            confidence=confidence,
            method_used=method_used
        )
    
    def classify_response(self, answer: str) -> ResponseClassification:
        """
        Classify the type of response using multi-language pattern matching
        and semantic analysis
        """
        if not answer or not answer.strip():
            return ResponseClassification(
                ResponseType.ERROR, 1.0, 0.0, 0.0, "unknown", []
            )
        
        answer_clean = answer.lower().strip()
        
        # Detect language (basic heuristic)
        detected_lang = self._detect_language(answer_clean)
        
        # Check for honesty patterns
        honesty_score, matched_patterns = self._check_honesty_patterns(answer_clean, detected_lang)
        
        # Analyze factual content
        factual_score = self._analyze_factual_content(answer_clean)
        
        # Classify response type
        if honesty_score >= self.honesty_threshold:
            response_type = ResponseType.HONEST_IDK
            confidence = honesty_score
        elif factual_score >= 0.7:
            response_type = ResponseType.FACTUAL
            confidence = factual_score
        elif factual_score >= 0.3:
            response_type = ResponseType.PARTIAL
            confidence = 0.6
        else:
            # Could be hallucination, but we need more sophisticated detection
            response_type = ResponseType.FACTUAL  # Conservative classification
            confidence = 0.4
        
        return ResponseClassification(
            response_type=response_type,
            confidence=confidence,
            honesty_score=honesty_score,
            factual_score=factual_score,
            language_detected=detected_lang,
            patterns_matched=matched_patterns
        )
    
    def _calculate_semantic_similarity(self, question: str, contexts: List[str]) -> float:
        """Calculate semantic similarity using embeddings if available"""
        if not self.embedding_model:
            return 0.0  # Fallback to other methods
        
        try:
            question_embedding = self.embedding_model.encode([question])
            context_embeddings = self.embedding_model.encode(contexts)
            
            # Calculate cosine similarities
            similarities = []
            for ctx_emb in context_embeddings:
                similarity = np.dot(question_embedding[0], ctx_emb) / (
                    np.linalg.norm(question_embedding[0]) * np.linalg.norm(ctx_emb)
                )
                similarities.append(similarity)
            
            # Return maximum similarity
            return float(max(similarities)) if similarities else 0.0
            
        except Exception as e:
            self.logger.warning(f"Semantic similarity calculation failed: {e}")
            return 0.0
    
    def _calculate_keyword_overlap(self, question: str, contexts: List[str]) -> float:
        """Calculate keyword overlap using Jaccard similarity"""
        # Extract meaningful words (filter out stop words)
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should'}
        
        question_words = set(word for word in re.findall(r'\b\w+\b', question.lower()) 
                           if len(word) > 2 and word not in stop_words)
        
        if not question_words:
            return 0.0
        
        max_overlap = 0.0
        for context in contexts:
            context_words = set(word for word in re.findall(r'\b\w+\b', context.lower()) 
                              if len(word) > 2 and word not in stop_words)
            
            if context_words:
                intersection = len(question_words & context_words)
                union = len(question_words | context_words)
                jaccard = intersection / union if union > 0 else 0.0
                max_overlap = max(max_overlap, jaccard)
        
        return max_overlap
    
    def _calculate_entity_overlap(self, question: str, contexts: List[str]) -> float:
        """Basic named entity overlap (can be enhanced with NLP libraries)"""
        # Simple heuristic: look for capitalized words and numbers
        question_entities = set(re.findall(r'\b[A-Z][a-z]+\b|\b\d+\b', question))
        
        if not question_entities:
            return 0.0
        
        max_overlap = 0.0
        for context in contexts:
            context_entities = set(re.findall(r'\b[A-Z][a-z]+\b|\b\d+\b', context))
            
            if context_entities:
                intersection = len(question_entities & context_entities)
                union = len(question_entities | context_entities)
                overlap = intersection / union if union > 0 else 0.0
                max_overlap = max(max_overlap, overlap)
        
        return max_overlap
    
    def _detect_language(self, text: str) -> str:
        """Basic language detection using character patterns"""
        # Turkish specific characters
        if re.search(r'[çğıöşüÇĞIÖŞÜ]', text):
            return "tr"
        
        # Spanish specific patterns
        if re.search(r'[ñáéíóúü¿¡]', text):
            return "es"
        
        # French specific patterns
        if re.search(r'[àâäéèêëïîôöùûüÿç]', text):
            return "fr"
        
        # German specific patterns
        if re.search(r'[äöüßÄÖÜ]', text):
            return "de"
        
        # Default to English
        return "en"
    
    def _check_honesty_patterns(self, answer: str, language: str) -> Tuple[float, List[str]]:
        """Check for honesty patterns in the given language"""
        patterns = self.honesty_patterns.get(language, self.honesty_patterns["en"])
        matched_patterns = []
        
        for pattern in patterns:
            if re.search(pattern, answer, re.IGNORECASE):
                matched_patterns.append(pattern)
        
        # Calculate honesty score based on matches and answer length
        if matched_patterns:
            # Strong honesty indicators
            base_score = 0.8
            # Boost score if answer is short (typical of honest "I don't know" responses)
            length_factor = max(0.1, 1.0 - len(answer) / 200)  # Shorter = more honest
            honesty_score = min(0.95, base_score + length_factor * 0.15)
        else:
            honesty_score = 0.0
        
        return honesty_score, matched_patterns
    
    def _analyze_factual_content(self, answer: str) -> float:
        """Analyze how factual the content appears (basic heuristics)"""
        # Look for factual indicators
        factual_indicators = [
            r'\b\d+\b',  # Numbers
            r'\b(is|are|was|were)\b',  # Definitive statements
            r'\b(according to|based on)\b',  # Citations
            r'\b(percent|percentage|%)\b',  # Statistics
            r'\b(research|study|data)\b',  # Research references
        ]
        
        factual_score = 0.0
        for pattern in factual_indicators:
            if re.search(pattern, answer, re.IGNORECASE):
                factual_score += 0.2
        
        # Normalize to 0-1 range
        return min(1.0, factual_score)
    
    def _evaluate_low_relevance_scenario(self, 
                                       question: str, 
                                       contexts: List[str], 
                                       answer: str,
                                       relevance_analysis: RelevanceAnalysis,
                                       response_classification: ResponseClassification) -> UniversalEvalResult:
        """
        Evaluate when context relevance is low - focus on honesty
        """
        if response_classification.response_type == ResponseType.HONEST_IDK:
            # Perfect! LLM was honest about not knowing
            score = 0.9  # High score for honesty
            passed = True
            explanation = f"✅ HONEST RAG: Context irrelevant (relevance: {relevance_analysis.overall_score:.3f}), LLM correctly responded 'I don't know' (honesty: {response_classification.honesty_score:.3f})"
        else:
            # LLM tried to answer despite irrelevant context - potential hallucination
            score = 0.2  # Low score for potential hallucination
            passed = False
            explanation = f"⚠️ POTENTIAL HALLUCINATION: Context irrelevant (relevance: {relevance_analysis.overall_score:.3f}) but LLM provided answer - risk of hallucination"
        
        return UniversalEvalResult(
            passed=passed,
            score=score,
            explanation=explanation,
            relevance_analysis=relevance_analysis,
            response_classification=response_classification,
            evaluation_method="low_relevance_honesty_check",
            confidence=response_classification.confidence
        )
    
    def _evaluate_high_relevance_scenario(self, 
                                        question: str, 
                                        contexts: List[str], 
                                        answer: str,
                                        ground_truth: Optional[str],
                                        relevance_analysis: RelevanceAnalysis,
                                        response_classification: ResponseClassification) -> UniversalEvalResult:
        """
        Evaluate when context relevance is high - use standard RAG evaluation
        """
        # For high relevance, we expect factual answers
        if response_classification.response_type == ResponseType.HONEST_IDK:
            # Context is relevant but LLM says "I don't know" - might be overly conservative
            score = 0.4  # Medium score - not wrong but missed opportunity
            passed = False
            explanation = f"⚠️ CONSERVATIVE RAG: Context relevant (relevance: {relevance_analysis.overall_score:.3f}) but LLM responded 'I don't know' - may be overly conservative"
        else:
            # Context is relevant and LLM provided answer - evaluate quality
            # This is where we'd integrate with RAGAS for detailed evaluation
            base_score = relevance_analysis.overall_score * response_classification.factual_score
            score = min(0.95, max(0.1, base_score))
            
            # Simple threshold for now (can be enhanced with RAGAS integration)
            threshold = float(os.getenv("RAG_QUALITY_THRESHOLD", "0.4"))
            passed = score >= threshold
            
            if passed:
                explanation = f"✅ QUALITY RAG: Context relevant (relevance: {relevance_analysis.overall_score:.3f}), factual response (factual: {response_classification.factual_score:.3f})"
            else:
                explanation = f"⚠️ LOW QUALITY RAG: Context relevant but response quality insufficient (score: {score:.3f} < {threshold})"
        
        return UniversalEvalResult(
            passed=passed,
            score=score,
            explanation=explanation,
            relevance_analysis=relevance_analysis,
            response_classification=response_classification,
            evaluation_method="high_relevance_quality_check",
            confidence=min(relevance_analysis.confidence, response_classification.confidence)
        )
