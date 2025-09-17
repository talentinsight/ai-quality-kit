"""Topics/Compliance detection using zero-shot NLI."""

import logging
from typing import Optional, Dict, Any, List
from ..interfaces import GuardrailProvider, SignalResult, SignalLabel, GuardrailCategory
from ..registry import register_provider

logger = logging.getLogger(__name__)


@register_provider("topics.nli", GuardrailCategory.TOPICS)
class TopicsNLIProvider(GuardrailProvider):
    """Topics/Compliance detection using zero-shot NLI (BART-MNLI)."""
    
    def __init__(self):
        super().__init__("topics.nli", GuardrailCategory.TOPICS)
        self.requires_llm = False  # Can work on input text
        self._pipeline = None
        self._available = None
        self._topics = self._get_topic_hypotheses()
    
    def _get_topic_hypotheses(self) -> List[Dict[str, Any]]:
        """Get topic classification hypotheses."""
        return [
            {
                "label": "politics",
                "hypothesis": "This text discusses political topics, elections, government, or political figures.",
                "weight": 0.7
            },
            {
                "label": "weapons",
                "hypothesis": "This text discusses weapons, firearms, explosives, or military equipment.",
                "weight": 0.9
            },
            {
                "label": "terrorism",
                "hypothesis": "This text discusses terrorism, terrorist activities, or extremist content.",
                "weight": 1.0
            },
            {
                "label": "financial_fraud",
                "hypothesis": "This text discusses financial fraud, scams, money laundering, or illegal financial activities.",
                "weight": 0.8
            },
            {
                "label": "social_engineering",
                "hypothesis": "This text discusses social engineering, manipulation tactics, or deceptive practices.",
                "weight": 0.7
            },
            {
                "label": "illegal_activities",
                "hypothesis": "This text discusses illegal activities, criminal behavior, or law breaking.",
                "weight": 0.8
            }
        ]
    
    def is_available(self) -> bool:
        """Check if transformers and BART-MNLI are available."""
        if self._available is not None:
            return self._available
        
        try:
            from transformers import pipeline
            self._pipeline = pipeline(
                "zero-shot-classification",
                model="facebook/bart-large-mnli",
                device=-1  # CPU only for now
            )
            self._available = True
            logger.info("Topics NLI provider initialized successfully")
        except ImportError as e:
            logger.warning(f"transformers not available: {e}")
            self._available = False
        except Exception as e:
            logger.warning(f"Topics NLI initialization failed: {e}")
            self._available = False
        
        return self._available
    
    async def check(self, input_text: str, output_text: Optional[str] = None) -> SignalResult:
        """Check for sensitive topics using NLI."""
        if not self.is_available():
            return SignalResult(
                id=self.provider_id,
                category=self.category,
                score=0.0,
                label=SignalLabel.UNAVAILABLE,
                confidence=0.0,
                details={"missing_dep": True}
            )
        
        # Check both input and output, prioritize input
        text_to_check = input_text or output_text or ""
        if not text_to_check.strip():
            return SignalResult(
                id=self.provider_id,
                category=self.category,
                score=0.0,
                label=SignalLabel.CLEAN,
                confidence=1.0,
                details={"no_text": True}
            )
        
        try:
            # Prepare hypotheses
            hypotheses = [topic["hypothesis"] for topic in self._topics]
            
            # Run zero-shot classification
            result = self._pipeline(text_to_check, hypotheses)
            
            # Process results
            topic_scores = {}
            max_score = 0.0
            detected_topics = []
            
            for i, (label_hyp, score) in enumerate(zip(result['labels'], result['scores'])):
                # Map back to our topic labels
                topic_info = self._topics[hypotheses.index(label_hyp)]
                topic_label = topic_info["label"]
                weight = topic_info["weight"]
                
                # Weighted score
                weighted_score = score * weight
                topic_scores[topic_label] = {
                    "raw_score": float(score),
                    "weighted_score": float(weighted_score),
                    "weight": weight
                }
                
                # Track high-confidence detections
                if score > 0.5:  # Threshold for "detected"
                    detected_topics.append(topic_label)
                    max_score = max(max_score, weighted_score)
            
            # Overall risk score (max weighted score)
            score = min(1.0, max_score)
            confidence = max(result['scores'][:3])  # Confidence from top 3 predictions
            
            # Determine label
            if score > 0.8:
                label = SignalLabel.VIOLATION
            elif score > 0.4:
                label = SignalLabel.HIT
            else:
                label = SignalLabel.CLEAN
            
            return SignalResult(
                id=self.provider_id,
                category=self.category,
                score=score,
                label=label,
                confidence=float(confidence),
                details={
                    "detected_topics": detected_topics,
                    "topic_scores": topic_scores,
                    "max_score": max_score,
                    "text_length": len(text_to_check)
                }
            )
            
        except Exception as e:
            logger.error(f"Topics NLI classification failed: {e}")
            return SignalResult(
                id=self.provider_id,
                category=self.category,
                score=0.0,
                label=SignalLabel.UNAVAILABLE,
                confidence=0.0,
                details={"error": str(e)}
            )
