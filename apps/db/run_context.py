"""Run context management for evaluation runs."""

# Simple in-memory module variable to share RUN_ID across tests in one session
_run_id: str | None = None


def set_run_id(run_id: str) -> None:
    """Set the current run ID for this session."""
    global _run_id
    _run_id = run_id


def get_run_id() -> str | None:
    """Get the current run ID for this session."""
    return _run_id


def has_run_id() -> bool:
    """Check if a run ID is set for this session."""
    return _run_id is not None


def clear_run_id() -> None:
    """Clear the current run ID."""
    global _run_id
    _run_id = None
