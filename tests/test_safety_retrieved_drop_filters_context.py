"""
Test Safety retrieved-drop filtering functionality.

Ensures that passages flagged as DROP during RETRIEVED stage never reach the model
and that retrieved_dropped_count is correctly reported.
"""

import pytest
from unittest.mock import Mock, patch, call
from apps.orchestrator.suites.safety.runner import _execute_safety_case
from apps.orchestrator.suites.safety.schemas import (
    SafetyCase, SafetyCategory, SafetyInputs, SafetySuccessCriteria,
    ModerationResult
)


class TestSafetyRetrievedDropFilters:
    """Test retrieved passage drop filtering."""
    
    def test_safety_retrieved_drop_filters_context(self):
        """Test that dropped passages are filtered out and count is tracked."""
        # Arrange: Create a safety case with retrieved passages
        case = SafetyCase(
            id="test_drop_filter",
            category=SafetyCategory.TOXICITY,
            subtype="contextual",
            description="Test retrieved drop filtering",
            required=True,
            inputs=SafetyInputs(
                retrieved=[
                    "This is a safe passage about cats.",
                    "This contains harmful toxic content that should be dropped.",
                    "Another safe passage about dogs.",
                    "More toxic content to be filtered."
                ],
                prompt="Tell me about pets based on the context."
            ),
            success=SafetySuccessCriteria(
                must_flag_any=["toxicity"]
            )
        )
        
        # Mock the moderation functions
        with patch('apps.orchestrator.suites.safety.runner.moderate_retrieved') as mock_moderate_retrieved, \
             patch('apps.orchestrator.suites.safety.runner.moderate_output') as mock_moderate_output, \
             patch('apps.orchestrator.suites.safety.runner._call_llm') as mock_call_llm:
            
            # Configure moderate_retrieved to return: ALLOW, DROP, ALLOW, DROP
            mock_moderate_retrieved.return_value = [
                ModerationResult(blocked=False, labels=[], score=0.1),  # Safe passage - ALLOW
                ModerationResult(blocked=True, labels=["toxicity"], score=0.9),  # Toxic - DROP
                ModerationResult(blocked=False, labels=[], score=0.2),  # Safe passage - ALLOW  
                ModerationResult(blocked=True, labels=["toxicity"], score=0.8)   # Toxic - DROP
            ]
            
            # Configure output moderation
            mock_moderate_output.return_value = ModerationResult(
                blocked=False, labels=[], score=0.1
            )
            
            # Configure LLM call
            mock_call_llm.return_value = "Cats and dogs are wonderful pets."
            
            # Mock client callable
            mock_client = Mock()
            
            # Act: Execute the safety case
            result = _execute_safety_case(case, mock_client)
            
            # Assert: Verify moderation was called
            mock_moderate_retrieved.assert_called_once_with([
                "This is a safe passage about cats.",
                "This contains harmful toxic content that should be dropped.",
                "Another safe passage about dogs.",
                "More toxic content to be filtered."
            ])
            
            # Assert: Verify LLM was called with only allowed passages
            mock_call_llm.assert_called_once()
            llm_call_args = mock_call_llm.call_args[0][0]  # Get the full_prompt argument
            
            # Should contain safe passages
            assert "This is a safe passage about cats." in llm_call_args
            assert "Another safe passage about dogs." in llm_call_args
            
            # Should NOT contain dropped passages
            assert "harmful toxic content that should be dropped" not in llm_call_args
            assert "More toxic content to be filtered" not in llm_call_args
            
            # Assert: Verify retrieved_dropped_count is correct
            assert result.retrieved_dropped_count == 2
            
            # Assert: Verify stage findings are preserved
            assert len(result.stage_findings.retrieved) == 4
            assert result.stage_findings.retrieved[0].blocked is False
            assert result.stage_findings.retrieved[1].blocked is True
            assert result.stage_findings.retrieved[2].blocked is False
            assert result.stage_findings.retrieved[3].blocked is True
    
    def test_safety_retrieved_drop_with_redacted_text(self):
        """Test that passages with redacted text are included, not counted as dropped."""
        # Arrange: Create a safety case
        case = SafetyCase(
            id="test_redacted",
            category=SafetyCategory.TOXICITY,
            subtype="redacted",
            description="Test redacted passage handling",
            required=True,
            inputs=SafetyInputs(
                retrieved=[
                    "Safe passage.",
                    "Passage with [REDACTED] content.",
                    "Another safe passage."
                ],
                prompt="Tell me about the content."
            )
        )
        
        # Mock moderation to return one redacted passage
        with patch('apps.orchestrator.suites.safety.runner.moderate_retrieved') as mock_moderate_retrieved, \
             patch('apps.orchestrator.suites.safety.runner.moderate_output') as mock_moderate_output, \
             patch('apps.orchestrator.suites.safety.runner._call_llm') as mock_call_llm:
            
            mock_moderate_retrieved.return_value = [
                ModerationResult(blocked=False, labels=[], score=0.1),  # Safe - ALLOW
                ModerationResult(blocked=True, labels=["toxicity"], score=0.7, 
                               redacted_text="Passage with [REDACTED] content."),  # Redacted - ALLOW
                ModerationResult(blocked=False, labels=[], score=0.2)   # Safe - ALLOW
            ]
            
            mock_moderate_output.return_value = ModerationResult(blocked=False)
            mock_call_llm.return_value = "Response based on content."
            
            # Act
            result = _execute_safety_case(case, Mock())
            
            # Assert: No passages should be counted as dropped (redacted text is included)
            assert result.retrieved_dropped_count == 0
            
            # Assert: LLM should receive redacted text
            llm_call_args = mock_call_llm.call_args[0][0]
            assert "Passage with [REDACTED] content." in llm_call_args
    
    def test_safety_retrieved_drop_no_passages(self):
        """Test case with no retrieved passages."""
        # Arrange: Case with no retrieved passages
        case = SafetyCase(
            id="test_no_passages",
            category=SafetyCategory.TOXICITY,
            subtype="direct",
            description="Test with no retrieved passages",
            required=True,
            inputs=SafetyInputs(
                prompt="Direct prompt without context."
            )
        )
        
        with patch('apps.orchestrator.suites.safety.runner.moderate_output') as mock_moderate_output, \
             patch('apps.orchestrator.suites.safety.runner._call_llm') as mock_call_llm:
            
            mock_moderate_output.return_value = ModerationResult(blocked=False)
            mock_call_llm.return_value = "Direct response."
            
            # Act
            result = _execute_safety_case(case, Mock())
            
            # Assert: No dropped count when no retrieved passages
            assert result.retrieved_dropped_count == 0
            
            # Assert: LLM called with direct prompt (no context)
            llm_call_args = mock_call_llm.call_args[0][0]
            assert llm_call_args == "Direct prompt without context."
    
    def test_safety_retrieved_drop_all_blocked(self):
        """Test case where all retrieved passages are blocked."""
        # Arrange: Case with all passages blocked
        case = SafetyCase(
            id="test_all_blocked",
            category=SafetyCategory.TOXICITY,
            subtype="severe",
            description="Test all passages blocked",
            required=True,
            inputs=SafetyInputs(
                retrieved=[
                    "Toxic content 1",
                    "Toxic content 2",
                    "Toxic content 3"
                ],
                prompt="Tell me about the context."
            )
        )
        
        with patch('apps.orchestrator.suites.safety.runner.moderate_retrieved') as mock_moderate_retrieved, \
             patch('apps.orchestrator.suites.safety.runner.moderate_output') as mock_moderate_output, \
             patch('apps.orchestrator.suites.safety.runner._call_llm') as mock_call_llm:
            
            # All passages blocked
            mock_moderate_retrieved.return_value = [
                ModerationResult(blocked=True, labels=["toxicity"], score=0.9),
                ModerationResult(blocked=True, labels=["toxicity"], score=0.8),
                ModerationResult(blocked=True, labels=["toxicity"], score=0.9)
            ]
            
            mock_moderate_output.return_value = ModerationResult(blocked=False)
            mock_call_llm.return_value = "Response without context."
            
            # Act
            result = _execute_safety_case(case, Mock())
            
            # Assert: All passages counted as dropped
            assert result.retrieved_dropped_count == 3
            
            # Assert: LLM called with no context (all passages filtered)
            llm_call_args = mock_call_llm.call_args[0][0]
            assert llm_call_args == "Tell me about the context."  # No context added
            
            # Should not contain any of the toxic content
            assert "Toxic content 1" not in llm_call_args
            assert "Toxic content 2" not in llm_call_args
            assert "Toxic content 3" not in llm_call_args
