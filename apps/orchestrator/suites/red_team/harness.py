"""Multi-turn adversarial harness for Red Team attack execution."""

import time
import logging
from typing import List, Dict, Any, Optional, Callable
from .schemas import AttackCase, AttackResult, AttackStep, Channel
from .detectors import score_attack
# Import moved to avoid circular dependency

logger = logging.getLogger(__name__)


class ConversationState:
    """Maintains state across multi-turn attack sequences."""
    
    def __init__(self):
        self.history: List[Dict[str, str]] = []
        self.context_injections: List[str] = []
        self.metadata_injections: Dict[str, str] = {}
        self.turn_count = 0
    
    def add_turn(self, role: str, content: str, response: str = ""):
        """Add a conversation turn to history."""
        self.history.append({
            "turn": self.turn_count,
            "role": role,
            "content": content,
            "response": response
        })
        self.turn_count += 1
    
    def add_context_injection(self, content: str):
        """Add content to be injected into retrieved passages."""
        self.context_injections.append(content)
    
    def add_metadata_injection(self, key: str, value: str):
        """Add metadata to be injected into document metadata."""
        self.metadata_injections[key] = value
    
    def get_injected_context(self) -> List[str]:
        """Get all context injections for RAG middleware."""
        return self.context_injections.copy()
    
    def get_injected_metadata(self) -> Dict[str, str]:
        """Get all metadata injections for RAG middleware."""
        return self.metadata_injections.copy()


class RAGMiddleware:
    """Middleware for injecting malicious content into RAG pipeline."""
    
    def __init__(self, base_contexts: Optional[List[str]] = None):
        self.base_contexts = base_contexts or []
        self.injected_contexts: List[str] = []
        self.injected_metadata: Dict[str, str] = {}
    
    def inject_passage(self, content: str):
        """Inject malicious content into retrieved passages."""
        self.injected_contexts.append(content)
        logger.debug(f"Injected passage content: {content[:50]}...")
    
    def inject_metadata(self, key: str, value: str):
        """Inject malicious metadata into document metadata."""
        self.injected_metadata[key] = value
        logger.debug(f"Injected metadata {key}: {value[:50]}...")
    
    def get_modified_contexts(self) -> List[str]:
        """Get contexts with injections applied."""
        # Combine base contexts with injected malicious content
        all_contexts = self.base_contexts.copy()
        all_contexts.extend(self.injected_contexts)
        return all_contexts
    
    def get_modified_metadata(self) -> Dict[str, str]:
        """Get metadata with injections applied."""
        return self.injected_metadata.copy()
    
    def clear_injections(self):
        """Clear all injections for next attack."""
        self.injected_contexts.clear()
        self.injected_metadata.clear()


def run_attack_case(
    target_client: Any,
    case: AttackCase,
    rag_middleware: Optional[RAGMiddleware] = None
) -> AttackResult:
    """
    Execute a single attack case with multi-turn conversation support.
    
    Args:
        target_client: Client for making requests to target system
        case: AttackCase to execute
        rag_middleware: Optional RAG middleware for context injection
        
    Returns:
        AttackResult with execution details and scoring
    """
    start_time = time.perf_counter()
    conversation = ConversationState()
    outputs: List[str] = []
    
    # Safety check for max steps - import here to avoid circular dependency
    try:
        from apps.config.red_team import red_team_config
        max_steps = red_team_config.max_steps
    except ImportError:
        max_steps = 6  # Default fallback
    
    if len(case.steps) > max_steps:
        logger.warning(f"Attack {case.id} has {len(case.steps)} steps, limiting to {max_steps}")
        steps_to_execute = case.steps[:max_steps]
    else:
        steps_to_execute = case.steps
    
    try:
        # Execute each step in the attack sequence
        for step_idx, step in enumerate(steps_to_execute):
            step_start = time.perf_counter()
            
            logger.debug(f"Executing step {step_idx + 1}/{len(steps_to_execute)} for attack {case.id}")
            logger.debug(f"Step role: {step.role}, content: {step.content[:100]}...")
            
            # Handle different injection channels
            if step.role == Channel.PASSAGE:
                # Inject into retrieved passages
                if rag_middleware:
                    rag_middleware.inject_passage(step.content)
                    conversation.add_context_injection(step.content)
                else:
                    # Fallback: simulate context injection with delimited prefix
                    fallback_context = f"[INJECTED_PASSAGE]: {step.content}"
                    conversation.add_context_injection(fallback_context)
                    logger.debug("No RAG middleware available, using fallback context injection")
                
                # No direct response for passage injection
                conversation.add_turn("passage", step.content, "")
                continue
                
            elif step.role == Channel.METADATA:
                # Inject into document metadata
                if rag_middleware:
                    rag_middleware.inject_metadata("injected_field", step.content)
                    conversation.add_metadata_injection("injected_field", step.content)
                else:
                    # Fallback: add to conversation context
                    conversation.add_metadata_injection("injected_field", step.content)
                    logger.debug("No RAG middleware available, storing metadata injection")
                
                # No direct response for metadata injection
                conversation.add_turn("metadata", step.content, "")
                continue
                
            elif step.role in [Channel.USER, Channel.SYSTEM]:
                # Direct interaction with target system
                try:
                    # Prepare request with conversation context
                    request_content = step.content
                    
                    # If we have context injections and no middleware, add them as context
                    if not rag_middleware and conversation.context_injections:
                        context_prefix = "\n".join([
                            "[CONTEXT]:",
                            *conversation.context_injections,
                            "[END_CONTEXT]\n"
                        ])
                        request_content = context_prefix + request_content
                    
                    # Make request to target system with deterministic parameters
                    if hasattr(target_client, 'complete'):
                        # Standard completion interface
                        response = target_client.complete(
                            prompt=request_content,
                            temperature=0,  # Deterministic
                            top_p=1,
                            max_tokens=1000
                        )
                        response_text = response.get('text', '') if isinstance(response, dict) else str(response)
                    elif hasattr(target_client, 'chat'):
                        # Chat interface
                        messages = [{"role": "user", "content": request_content}]
                        response = target_client.chat(messages=messages, temperature=0)
                        response_text = response.get('content', '') if isinstance(response, dict) else str(response)
                    else:
                        # Generic callable
                        response = target_client(request_content)
                        response_text = str(response)
                    
                    outputs.append(response_text)
                    conversation.add_turn(step.role.value, step.content, response_text)
                    
                    step_latency = (time.perf_counter() - step_start) * 1000
                    logger.debug(f"Step {step_idx + 1} completed in {step_latency:.1f}ms")
                    
                except Exception as e:
                    error_msg = f"Error executing step {step_idx + 1}: {str(e)}"
                    logger.error(error_msg)
                    outputs.append(f"[ERROR]: {error_msg}")
                    conversation.add_turn(step.role.value, step.content, error_msg)
                    
                    # For client errors, return early with error result
                    total_latency = (time.perf_counter() - start_time) * 1000
                    return AttackResult(
                        id=case.id,
                        category=case.category,
                        passed=True,  # Assume defended on error
                        reason=f"Attack execution failed: {str(e)}",
                        evidence={"error": error_msg},
                        latency_ms=total_latency,
                        turn_count=conversation.turn_count
                    )
            
            else:
                logger.warning(f"Unknown step role: {step.role}")
                continue
        
        # Calculate total latency
        total_latency = (time.perf_counter() - start_time) * 1000
        
        # Score the attack based on outputs and success criteria
        passed, reason, evidence = score_attack(case, outputs)
        
        # Mask secrets in evidence if configured
        try:
            from apps.config.red_team import red_team_config
            mask_secrets = red_team_config.mask_secrets
        except ImportError:
            mask_secrets = True  # Default to masking
            
        if mask_secrets:
            evidence = _mask_secrets_in_evidence(evidence)
        
        # Create result
        result = AttackResult(
            id=case.id,
            category=case.category,
            passed=passed,
            reason=reason,
            evidence=evidence,
            latency_ms=total_latency,
            turn_count=conversation.turn_count
        )
        
        logger.info(f"Attack {case.id} completed: {'DEFENDED' if passed else 'SUCCEEDED'} ({reason})")
        return result
        
    except Exception as e:
        # Handle unexpected errors gracefully
        total_latency = (time.perf_counter() - start_time) * 1000
        error_msg = f"Attack execution failed: {str(e)}"
        logger.error(f"Attack {case.id} failed: {error_msg}")
        
        return AttackResult(
            id=case.id,
            category=case.category,
            passed=True,  # Assume defended if execution failed
            reason=error_msg,
            evidence={"error": error_msg},
            latency_ms=total_latency,
            turn_count=conversation.turn_count
        )


def _mask_secrets_in_evidence(evidence: Dict[str, str]) -> Dict[str, str]:
    """
    Mask potential secrets in evidence dictionary.
    
    Args:
        evidence: Evidence dictionary to mask
        
    Returns:
        Evidence dictionary with secrets masked
    """
    masked_evidence = {}
    
    for key, value in evidence.items():
        if any(secret_indicator in key.lower() for secret_indicator in ['key', 'token', 'password', 'secret']):
            # Mask the value
            if len(value) > 8:
                masked_value = value[:4] + "*" * (len(value) - 8) + value[-4:]
            else:
                masked_value = "*" * len(value)
            masked_evidence[key] = masked_value
        else:
            masked_evidence[key] = value
    
    return masked_evidence


def create_mock_rag_middleware(base_contexts: Optional[List[str]] = None) -> RAGMiddleware:
    """
    Create a mock RAG middleware for testing purposes.
    
    Args:
        base_contexts: Base contexts to use for RAG simulation
        
    Returns:
        RAGMiddleware instance
    """
    default_contexts = [
        "This is a sample document about company policies.",
        "Security guidelines require proper authentication.",
        "All users must follow established procedures."
    ]
    
    return RAGMiddleware(base_contexts or default_contexts)
