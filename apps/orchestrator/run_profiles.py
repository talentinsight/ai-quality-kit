"""Run profiles and rate-limit safety for RAG testing."""

import asyncio
import logging
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RunProfile:
    """Run profile configuration."""
    name: str
    qa_sample_size: Optional[int]
    description: str
    concurrency_limit: int = 2


# Pre-defined run profiles
RUN_PROFILES = {
    "smoke": RunProfile(
        name="smoke",
        qa_sample_size=20,
        description="Quick smoke test with limited samples",
        concurrency_limit=2
    ),
    "full": RunProfile(
        name="full", 
        qa_sample_size=None,
        description="Full evaluation with all available samples",
        concurrency_limit=4
    )
}


class RateLimitSafetyManager:
    """Manages rate limiting and backoff for API calls."""
    
    def __init__(self, concurrency_limit: int = 2, base_delay: float = 1.0):
        """
        Initialize rate limit manager.
        
        Args:
            concurrency_limit: Maximum concurrent requests
            base_delay: Base delay for exponential backoff
        """
        self.concurrency_limit = concurrency_limit
        self.base_delay = base_delay
        self.semaphore = asyncio.Semaphore(concurrency_limit)
        self.retry_counts = {}
        
    async def execute_with_backoff(self, coro_func, case_id: str = None):
        """
        Execute coroutine function with rate limiting and backoff.
        
        Args:
            coro_func: Coroutine function to execute (or coroutine if single-use)
            case_id: Identifier for tracking retries
            
        Returns:
            Result of coroutine execution
        """
        async with self.semaphore:
            max_retries = 3
            retry_count = 0
            
            while retry_count <= max_retries:
                try:
                    # If it's a coroutine function, call it; if it's already a coroutine, use it directly
                    if callable(coro_func):
                        result = await coro_func()
                    else:
                        result = await coro_func
                    
                    # Reset retry count on success
                    if case_id and case_id in self.retry_counts:
                        del self.retry_counts[case_id]
                    
                    return result
                    
                except Exception as e:
                    # Check if it's a rate limit error
                    if self._is_rate_limit_error(e):
                        retry_count += 1
                        if case_id:
                            self.retry_counts[case_id] = retry_count
                        
                        if retry_count <= max_retries:
                            # Exponential backoff with jitter
                            delay = self.base_delay * (2 ** (retry_count - 1))
                            jitter = delay * 0.1 * (hash(case_id or "") % 100) / 100
                            total_delay = delay + jitter
                            
                            logger.warning(f"Rate limit hit for {case_id}, retrying in {total_delay:.2f}s (attempt {retry_count})")
                            await asyncio.sleep(total_delay)
                            continue
                        else:
                            logger.error(f"Max retries exceeded for {case_id}")
                            raise
                    else:
                        # Non-rate-limit error, re-raise immediately
                        raise
    
    def _is_rate_limit_error(self, error: Exception) -> bool:
        """Check if error is a rate limit error."""
        error_str = str(error).lower()
        
        # Common rate limit indicators
        rate_limit_indicators = [
            "429",  # HTTP 429 Too Many Requests
            "503",  # HTTP 503 Service Unavailable
            "rate limit",
            "too many requests",
            "quota exceeded",
            "throttled"
        ]
        
        return any(indicator in error_str for indicator in rate_limit_indicators)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get rate limiting statistics."""
        return {
            "concurrency_limit": self.concurrency_limit,
            "active_requests": self.concurrency_limit - self.semaphore._value,
            "total_retries": sum(self.retry_counts.values()),
            "cases_with_retries": len(self.retry_counts)
        }


def resolve_run_profile(request) -> RunProfile:
    """
    Resolve run profile from request.
    
    Args:
        request: OrchestratorRequest
        
    Returns:
        RunProfile instance
    """
    # Check if profile is specified in options
    profile_name = None
    
    if request.options and "profile" in request.options:
        profile_name = request.options["profile"]
    elif request.volume and "profile" in request.volume:
        profile_name = request.volume["profile"]
    
    # Default to smoke if not specified
    if not profile_name:
        profile_name = "smoke"
    
    # Get profile or default to smoke
    profile = RUN_PROFILES.get(profile_name, RUN_PROFILES["smoke"])
    
    # Override qa_sample_size if explicitly set in request
    if request.options and "qa_sample_size" in request.options:
        profile = RunProfile(
            name=profile.name,
            qa_sample_size=request.options["qa_sample_size"],
            description=f"{profile.description} (custom sample size)",
            concurrency_limit=profile.concurrency_limit
        )
    
    # Adjust concurrency if perf_repeats is set
    if request.options and "perf_repeats" in request.options:
        perf_repeats = request.options["perf_repeats"]
        if perf_repeats and perf_repeats > 1:
            # Cap concurrency for performance testing
            profile = RunProfile(
                name=profile.name,
                qa_sample_size=profile.qa_sample_size,
                description=f"{profile.description} (perf testing)",
                concurrency_limit=min(profile.concurrency_limit, 2)
            )
    
    return profile


def apply_profile_to_qa_cases(qa_cases: list, profile: RunProfile) -> list:
    """
    Apply profile sampling to QA cases.
    
    Args:
        qa_cases: List of QA case dictionaries
        profile: RunProfile to apply
        
    Returns:
        Filtered list of QA cases
    """
    if not qa_cases:
        return []
    
    if profile.qa_sample_size is None:
        # Full profile - return all cases
        return qa_cases
    
    # Sample cases deterministically
    import random
    rng = random.Random(42)  # Deterministic sampling
    
    if len(qa_cases) <= profile.qa_sample_size:
        return qa_cases
    
    return rng.sample(qa_cases, profile.qa_sample_size)


def get_profile_metadata(profile: RunProfile, rate_limit_stats: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Get profile metadata for reporting.
    
    Args:
        profile: RunProfile instance
        rate_limit_stats: Optional rate limiting statistics
        
    Returns:
        Dictionary with profile metadata
    """
    metadata = {
        "profile": profile.name,
        "qa_sample_size": profile.qa_sample_size,
        "concurrency_limit": profile.concurrency_limit,
        "description": profile.description
    }
    
    if rate_limit_stats:
        metadata.update({
            "rate_limit_retries": rate_limit_stats.get("total_retries", 0),
            "cases_with_retries": rate_limit_stats.get("cases_with_retries", 0)
        })
    
    return metadata
