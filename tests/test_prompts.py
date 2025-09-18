"""Unit tests for prompt templates."""

import pytest


class TestPrompts:
    """Test prompt template functionality."""
    
    def test_context_only_answering_prompt_exists(self):
        """Test that CONTEXT_ONLY_ANSWERING_PROMPT exists and contains key directives."""
        from llm.prompts import CONTEXT_ONLY_ANSWERING_PROMPT
        
        assert CONTEXT_ONLY_ANSWERING_PROMPT is not None
        assert isinstance(CONTEXT_ONLY_ANSWERING_PROMPT, str)
        assert len(CONTEXT_ONLY_ANSWERING_PROMPT) > 0
        
        # Should contain key directives
        prompt_lower = CONTEXT_ONLY_ANSWERING_PROMPT.lower()
        assert "only use information from the provided context" in prompt_lower
        assert "i don't know" in prompt_lower
        assert "context" in prompt_lower
    
    def test_json_output_enforcing_prompt_exists(self):
        """Test that JSON_OUTPUT_ENFORCING_PROMPT exists and contains key directives."""
        from llm.prompts import JSON_OUTPUT_ENFORCING_PROMPT
        
        assert JSON_OUTPUT_ENFORCING_PROMPT is not None
        assert isinstance(JSON_OUTPUT_ENFORCING_PROMPT, str)
        assert len(JSON_OUTPUT_ENFORCING_PROMPT) > 0
        
        # Should contain key directives
        prompt_lower = JSON_OUTPUT_ENFORCING_PROMPT.lower()
        assert "json" in prompt_lower
        assert "verdict" in prompt_lower
        assert "citations" in prompt_lower
    
    def test_prompt_structure(self):
        """Test that prompts have proper structure."""
        from llm.prompts import CONTEXT_ONLY_ANSWERING_PROMPT, JSON_OUTPUT_ENFORCING_PROMPT
        
        for prompt_name, prompt in [("CONTEXT_ONLY_ANSWERING_PROMPT", CONTEXT_ONLY_ANSWERING_PROMPT), 
                                   ("JSON_OUTPUT_ENFORCING_PROMPT", JSON_OUTPUT_ENFORCING_PROMPT)]:
            # Should be a string
            assert isinstance(prompt, str), f"{prompt_name} should be a string"
            
            # Should not be empty
            assert len(prompt.strip()) > 0, f"{prompt_name} should not be empty"
            
            # Should contain assistant role indicator
            assert "assistant" in prompt.lower(), f"{prompt_name} should contain assistant role"
            
            # Should contain context instruction
            assert "context" in prompt.lower(), f"{prompt_name} should mention context"
    
    def test_prompt_content_quality(self):
        """Test that prompts have good content quality."""
        from llm.prompts import CONTEXT_ONLY_ANSWERING_PROMPT, JSON_OUTPUT_ENFORCING_PROMPT
        
        for prompt_name, prompt in [("CONTEXT_ONLY_ANSWERING_PROMPT", CONTEXT_ONLY_ANSWERING_PROMPT), 
                                   ("JSON_OUTPUT_ENFORCING_PROMPT", JSON_OUTPUT_ENFORCING_PROMPT)]:
            # Should not contain placeholder text
            assert "{{" not in prompt, f"{prompt_name} should not contain template placeholders"
            assert "}}" not in prompt, f"{prompt_name} should not contain template placeholders"
            
            # Should not contain TODO or FIXME
            assert "todo" not in prompt.lower(), f"{prompt_name} should not contain TODO"
            assert "fixme" not in prompt.lower(), f"{prompt_name} should not contain FIXME"
            
            # Should be properly formatted (no excessive whitespace)
            lines = prompt.split('\n')
            for line in lines:
                if line.strip():  # Non-empty lines
                    assert len(line) < 200, f"{prompt_name} has excessively long line: {line[:50]}..."
    
    def test_prompt_differences(self):
        """Test that different prompts are actually different."""
        from llm.prompts import CONTEXT_ONLY_ANSWERING_PROMPT, JSON_OUTPUT_ENFORCING_PROMPT
        
        # The two prompts should be different
        assert CONTEXT_ONLY_ANSWERING_PROMPT != JSON_OUTPUT_ENFORCING_PROMPT, "Prompts should be different"
        
        # They should have different lengths (JSON one might be longer)
        assert abs(len(CONTEXT_ONLY_ANSWERING_PROMPT) - len(JSON_OUTPUT_ENFORCING_PROMPT)) > 10, \
            "Prompts should have significantly different lengths"
    
    def test_prompt_instructions(self):
        """Test that prompts contain clear instructions."""
        from llm.prompts import CONTEXT_ONLY_ANSWERING_PROMPT, JSON_OUTPUT_ENFORCING_PROMPT
        
        for prompt_name, prompt in [("CONTEXT_ONLY_ANSWERING_PROMPT", CONTEXT_ONLY_ANSWERING_PROMPT), 
                                   ("JSON_OUTPUT_ENFORCING_PROMPT", JSON_OUTPUT_ENFORCING_PROMPT)]:
            # Should contain clear instructions
            prompt_lower = prompt.lower()
            
            # Should mention what to do
            assert any(word in prompt_lower for word in ["answer", "respond", "provide"]), \
                f"{prompt_name} should contain action instructions"
            
            # Should mention what not to do (JSON prompt has different structure)
            if prompt_name == "JSON_OUTPUT_ENFORCING_PROMPT":
                assert "only" in prompt_lower or "must" in prompt_lower, \
                    f"{prompt_name} should contain restriction instructions"
            else:
                assert any(word in prompt_lower for word in ["don't", "do not", "avoid", "never"]), \
                    f"{prompt_name} should contain restriction instructions"
    
    def test_prompt_context_handling(self):
        """Test that prompts properly handle context instructions."""
        from llm.prompts import CONTEXT_ONLY_ANSWERING_PROMPT, JSON_OUTPUT_ENFORCING_PROMPT
        
        for prompt_name, prompt in [("CONTEXT_ONLY_ANSWERING_PROMPT", CONTEXT_ONLY_ANSWERING_PROMPT), 
                                   ("JSON_OUTPUT_ENFORCING_PROMPT", JSON_OUTPUT_ENFORCING_PROMPT)]:
            prompt_lower = prompt.lower()
            
            # Should mention context usage
            assert "context" in prompt_lower, f"{prompt_name} should mention context"
            
            # Should mention when to say "I don't know" (JSON prompt has different structure)
            if prompt_name == "JSON_OUTPUT_ENFORCING_PROMPT":
                assert "unknown" in prompt_lower, \
                    f"{prompt_name} should mention unknown verdict"
            else:
                assert any(phrase in prompt_lower for phrase in ["i don't know", "don't know", "cannot answer"]), \
                    f"{prompt_name} should mention when to say I don't know"
    
    def test_prompt_format_requirements(self):
        """Test that prompts specify format requirements."""
        from llm.prompts import JSON_OUTPUT_ENFORCING_PROMPT
        
        prompt_lower = JSON_OUTPUT_ENFORCING_PROMPT.lower()
        
        # JSON enforced prompt should mention JSON format
        assert "json" in prompt_lower, "JSON_OUTPUT_ENFORCING_PROMPT should mention JSON format"
        assert any(word in prompt_lower for word in ["format", "structure", "schema"]), \
            "JSON_OUTPUT_ENFORCING_PROMPT should mention format requirements"
    
    def test_prompt_length_reasonableness(self):
        """Test that prompts are reasonable length."""
        from llm.prompts import CONTEXT_ONLY_ANSWERING_PROMPT, JSON_OUTPUT_ENFORCING_PROMPT
        
        for prompt_name, prompt in [("CONTEXT_ONLY_ANSWERING_PROMPT", CONTEXT_ONLY_ANSWERING_PROMPT), 
                                   ("JSON_OUTPUT_ENFORCING_PROMPT", JSON_OUTPUT_ENFORCING_PROMPT)]:
            # Should not be too short (missing instructions)
            assert len(prompt) > 100, f"{prompt_name} is too short for comprehensive instructions"
            
            # Should not be too long (unwieldy)
            assert len(prompt) < 2000, f"{prompt_name} is too long and unwieldy"
    
    def test_prompt_no_hardcoded_values(self):
        """Test that prompts don't contain hardcoded test values."""
        from llm.prompts import CONTEXT_ONLY_ANSWERING_PROMPT, JSON_OUTPUT_ENFORCING_PROMPT
        
        for prompt_name, prompt in [("CONTEXT_ONLY_ANSWERING_PROMPT", CONTEXT_ONLY_ANSWERING_PROMPT), 
                                   ("JSON_OUTPUT_ENFORCING_PROMPT", JSON_OUTPUT_ENFORCING_PROMPT)]:
            # Should not contain hardcoded test values
            assert "test" not in prompt.lower(), f"{prompt_name} should not contain test values"
            assert "example" not in prompt.lower(), f"{prompt_name} should not contain example values"
            assert "sample" not in prompt.lower(), f"{prompt_name} should not contain sample values"
