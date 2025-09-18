"""LLM Profiling System for Adaptive Test Generation."""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Optional, Any
from enum import Enum


class ModelSize(Enum):
    SMALL = "small"      # <7B parameters
    MEDIUM = "medium"    # 7B-30B parameters  
    LARGE = "large"      # 30B-100B parameters
    XLARGE = "xlarge"    # >100B parameters


class SafetyTraining(Enum):
    CONSTITUTIONAL_AI = "constitutional_ai"
    RLHF = "rlhf"
    DPO = "dpo"
    NONE = "none"


@dataclass
class LLMProfile:
    """Profile of an LLM for adaptive test generation."""
    
    # Basic model info
    model_name: str
    provider: str  # "openai", "anthropic", "custom"
    model_size: ModelSize
    parameter_count: Optional[str] = None  # "7B", "70B", etc.
    
    # Training info
    training_cutoff: Optional[datetime] = None
    safety_training: List[SafetyTraining] = None
    
    # Capabilities
    language_support: List[str] = None  # ["en", "tr", "de"]
    domain_expertise: List[str] = None  # ["medical", "legal", "finance"]
    context_length: Optional[int] = None
    
    # Known issues
    known_vulnerabilities: List[str] = None
    known_biases: List[str] = None
    
    # Performance characteristics
    reasoning_capability: str = "medium"  # "low", "medium", "high"
    instruction_following: str = "medium"
    
    def __post_init__(self):
        if self.safety_training is None:
            self.safety_training = []
        if self.language_support is None:
            self.language_support = ["en"]
        if self.domain_expertise is None:
            self.domain_expertise = []
        if self.known_vulnerabilities is None:
            self.known_vulnerabilities = []
        if self.known_biases is None:
            self.known_biases = []


class LLMProfiler:
    """Factory for creating LLM profiles."""
    
    @staticmethod
    def create_profile(model_name: str, provider: str) -> LLMProfile:
        """Create LLM profile based on model name and provider."""
        
        # OpenAI models
        if provider.lower() == "openai":
            if "gpt-4" in model_name.lower():
                return LLMProfile(
                    model_name=model_name,
                    provider=provider,
                    model_size=ModelSize.XLARGE,
                    parameter_count="1.7T",
                    training_cutoff=datetime(2024, 4, 1),
                    safety_training=[SafetyTraining.RLHF, SafetyTraining.CONSTITUTIONAL_AI],
                    language_support=["en", "es", "fr", "de", "it", "pt", "ru", "ja", "ko", "zh"],
                    domain_expertise=["general", "coding", "analysis", "creative"],
                    context_length=128000,
                    known_vulnerabilities=["prompt_injection", "jailbreak_dan"],
                    known_biases=["western_bias", "english_bias"],
                    reasoning_capability="high",
                    instruction_following="high"
                )
            elif "gpt-3.5" in model_name.lower():
                return LLMProfile(
                    model_name=model_name,
                    provider=provider,
                    model_size=ModelSize.MEDIUM,
                    parameter_count="20B",
                    training_cutoff=datetime(2021, 9, 1),
                    safety_training=[SafetyTraining.RLHF],
                    language_support=["en", "es", "fr", "de"],
                    context_length=4096,
                    reasoning_capability="medium",
                    instruction_following="medium"
                )
        
        # Anthropic models
        elif provider.lower() == "anthropic":
            if "claude-3" in model_name.lower():
                return LLMProfile(
                    model_name=model_name,
                    provider=provider,
                    model_size=ModelSize.XLARGE,
                    training_cutoff=datetime(2024, 2, 1),
                    safety_training=[SafetyTraining.CONSTITUTIONAL_AI],
                    language_support=["en", "es", "fr", "de", "it", "pt", "ja"],
                    domain_expertise=["analysis", "reasoning", "coding"],
                    context_length=200000,
                    known_vulnerabilities=["context_stuffing"],
                    known_biases=["western_bias", "academic_bias"],
                    reasoning_capability="high",
                    instruction_following="high"
                )
        
        # Default/Unknown model
        return LLMProfile(
            model_name=model_name,
            provider=provider,
            model_size=ModelSize.MEDIUM,
            reasoning_capability="medium",
            instruction_following="medium"
        )
    
    @staticmethod
    def detect_from_response(model_name: str, provider: str, sample_response: str) -> LLMProfile:
        """Detect LLM capabilities from a sample response."""
        profile = LLMProfiler.create_profile(model_name, provider)
        
        # Analyze response characteristics
        response_length = len(sample_response)
        
        # Detect language capabilities
        if any(char in sample_response for char in "çğıöşü"):
            if "tr" not in profile.language_support:
                profile.language_support.append("tr")
        
        # Detect reasoning capability
        if "step by step" in sample_response.lower() or "first," in sample_response.lower():
            profile.reasoning_capability = "high"
        
        return profile
