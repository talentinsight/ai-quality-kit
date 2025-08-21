"""Guardrails validation tests."""

import pytest
import json
import re
import os
import sys
from pathlib import Path
from typing import Dict, Any, List
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

import jsonschema
from apps.rag_service.rag_pipeline import RAGPipeline
from evals.dataset_loader import load_qa
from llm.provider import get_chat
from llm.prompts import JSON_OUTPUT_ENFORCING_PROMPT


class TestGuardrails:
    """Test class for guardrails validation."""
    
    @classmethod
    def setup_class(cls):
        """Setup test fixtures."""
        cls.rag_pipeline = None
        cls.qa_data = None
        cls.chat = get_chat()
        
        # Load JSON schema
        schema_path = "guardrails/schema.json"
        with open(schema_path, 'r') as f:
            cls.json_schema = json.load(f)
    
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
    
    def _extract_json_from_response(self, response: str) -> Dict[str, Any]:
        """
        Extract JSON object from LLM response with best-effort parsing.
        
        Args:
            response: Raw LLM response string
            
        Returns:
            Parsed JSON object
            
        Raises:
            ValueError: If no valid JSON can be extracted
        """
        # Try direct JSON parsing first
        try:
            return json.loads(response.strip())
        except json.JSONDecodeError:
            pass
        
        # Try to find JSON object in response using regex
        json_patterns = [
            r'\{[^{}]*\}',  # Simple single-level object
            r'\{.*?\}',     # Any object (greedy)
            r'\{[\s\S]*\}', # Multi-line object
        ]
        
        for pattern in json_patterns:
            matches = re.findall(pattern, response, re.DOTALL)
            for match in matches:
                try:
                    return json.loads(match)
                except json.JSONDecodeError:
                    continue
        
        # Try cleaning the response
        cleaned = response.strip()
        if cleaned.startswith('```json'):
            cleaned = cleaned[7:]
        if cleaned.endswith('```'):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
        
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass
        
        raise ValueError(f"Could not extract valid JSON from response: {response[:200]}...")
    
    def test_json_schema_validation(self):
        """Test that LLM outputs conform to the required JSON schema."""
        validation_failures = []
        
        for qa_item in self.qa_data:
            query = qa_item['query']
            
            # Get retrieved context
            contexts = self.rag_pipeline.retrieve(query)
            context_text = "\n\n".join([f"Passage {i+1}: {text}" for i, text in enumerate(contexts)])
            
            # Create prompt for JSON-structured response
            user_message = f"""Question: {query}

Context:
{context_text}

Analyze the question and context, then respond with the required JSON structure."""
            
            try:
                # Get LLM response
                messages = [JSON_OUTPUT_ENFORCING_PROMPT, user_message]
                response = self.chat(messages)
                
                # Extract JSON from response
                json_response = self._extract_json_from_response(response)
                
                # Validate against schema
                jsonschema.validate(json_response, self.json_schema)
                
                # Additional validation checks
                self._validate_json_content(json_response, contexts)
                
            except jsonschema.ValidationError as e:
                validation_failures.append(f"Query '{query}': Schema validation failed - {e.message}")
            except ValueError as e:
                validation_failures.append(f"Query '{query}': JSON extraction failed - {str(e)}")
            except Exception as e:
                validation_failures.append(f"Query '{query}': Unexpected error - {str(e)}")
        
        if validation_failures:
            failure_msg = "\n".join(validation_failures)
            assert False, (
                f"JSON schema validation failed for {len(validation_failures)} queries:\n{failure_msg}\n"
                f"This indicates the model is not consistently following the JSON output format. "
                f"Review the JSON-output system prompt and consider additional prompt engineering."
            )
    
    def _validate_json_content(self, json_response: Dict[str, Any], contexts: List[str]) -> None:
        """
        Additional validation of JSON content beyond schema.
        
        Args:
            json_response: Parsed JSON response
            contexts: Retrieved context passages
        """
        # Validate verdict values
        valid_verdicts = {"answer", "unknown", "refuse"}
        verdict = json_response.get("verdict")
        if verdict not in valid_verdicts:
            raise ValueError(f"Invalid verdict '{verdict}'. Must be one of: {valid_verdicts}")
        
        # Validate citations are reasonable
        citations = json_response.get("citations", [])
        if not isinstance(citations, list):
            raise ValueError("Citations must be an array")
        
        # If verdict is "answer", should have at least one citation
        if verdict == "answer" and len(citations) == 0:
            raise ValueError("Verdict 'answer' should include citations from context")
        
        # Citations should be reasonable substrings of context (if not empty)
        if citations and contexts:
            context_combined = " ".join(contexts).lower()
            for citation in citations:
                if isinstance(citation, str) and len(citation.strip()) > 0:
                    # Check if citation content relates to context (fuzzy match)
                    citation_words = set(citation.lower().split())
                    context_words = set(context_combined.split())
                    
                    # At least some overlap expected for reasonable citations
                    overlap = len(citation_words.intersection(context_words))
                    if overlap == 0 and len(citation_words) > 2:
                        # Only warn for longer citations with no overlap
                        pass  # Could log warning, but not fail test
    
    def test_pii_detection_heuristic(self):
        """Test deterministic PII/banned-words detection."""
        pii_violations = []
        
        # Define PII patterns (simple heuristics)
        pii_patterns = {
            'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            'ssn': r'\b\d{3}-\d{2}-\d{4}\b|\b\d{9}\b',
            'phone': r'\b\d{3}-\d{3}-\d{4}\b|\b\(\d{3}\)\s*\d{3}-\d{4}\b',
            'credit_card': r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',
        }
        
        # Banned words/phrases
        banned_terms = [
            'password', 'secret', 'token', 'api_key', 'private_key',
            'confidential', 'classified', 'internal_only'
        ]
        
        for qa_item in self.qa_data:
            query = qa_item['query']
            
            # Get RAG response
            result = self.rag_pipeline.query(query)
            answer = result['answer']
            contexts = result['context']
            
            # Check answer for PII patterns
            for pii_type, pattern in pii_patterns.items():
                matches = re.findall(pattern, answer, re.IGNORECASE)
                if matches:
                    pii_violations.append(f"Query '{query}': Found {pii_type} in answer: {matches}")
            
            # Check answer for banned terms
            answer_lower = answer.lower()
            for term in banned_terms:
                if term in answer_lower:
                    pii_violations.append(f"Query '{query}': Found banned term '{term}' in answer")
            
            # Also check contexts (shouldn't contain obvious PII in our test data)
            for i, context in enumerate(contexts):
                for pii_type, pattern in pii_patterns.items():
                    matches = re.findall(pattern, context, re.IGNORECASE)
                    if matches:
                        pii_violations.append(f"Query '{query}': Found {pii_type} in context {i+1}: {matches}")
        
        assert len(pii_violations) == 0, (
            f"PII detection found {len(pii_violations)} violations:\n" + 
            "\n".join(pii_violations) + "\n"
            f"This indicates potential data leakage or inappropriate content in responses. "
            f"Review the training data and implement additional PII filtering."
        )
    
    def test_output_format_consistency(self):
        """Test that all responses follow consistent output formatting."""
        format_issues = []
        
        for qa_item in self.qa_data:
            query = qa_item['query']
            
            # Get retrieved context
            contexts = self.rag_pipeline.retrieve(query)
            context_text = "\n\n".join([f"Passage {i+1}: {text}" for i, text in enumerate(contexts)])
            
            # Create prompt for JSON-structured response
            user_message = f"""Question: {query}

Context:
{context_text}

Analyze the question and context, then respond with the required JSON structure."""
            
            try:
                # Get LLM response
                messages = [JSON_OUTPUT_ENFORCING_PROMPT, user_message]
                response = self.chat(messages)
                
                # Check response characteristics
                if len(response.strip()) == 0:
                    format_issues.append(f"Query '{query}': Empty response")
                    continue
                
                # Try to extract JSON
                json_response = self._extract_json_from_response(response)
                
                # Validate required fields exist
                if 'verdict' not in json_response:
                    format_issues.append(f"Query '{query}': Missing 'verdict' field")
                
                if 'citations' not in json_response:
                    format_issues.append(f"Query '{query}': Missing 'citations' field")
                
                # Check for extra text outside JSON (should be minimal)
                try:
                    # If response is pure JSON, this should work
                    json.loads(response.strip())
                except json.JSONDecodeError:
                    # Response contains extra text - check if it's significant
                    json_str = json.dumps(json_response)
                    extra_text = response.replace(json_str, '').strip()
                    if len(extra_text) > 20:  # Allow some minor extra text
                        format_issues.append(f"Query '{query}': Significant extra text outside JSON: {extra_text[:50]}...")
                
            except Exception as e:
                format_issues.append(f"Query '{query}': Format processing failed - {str(e)}")
        
        assert len(format_issues) == 0, (
            f"Output format consistency issues found:\n" + 
            "\n".join(format_issues) + "\n"
            f"This indicates the model is not consistently following output format instructions. "
            f"Review the system prompts and consider additional format training."
        )


if __name__ == "__main__":
    # Run tests directly
    pytest.main([__file__, "-v"])
