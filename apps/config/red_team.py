"""Red Team configuration management with environment overrides."""

import os
from typing import List
from apps.orchestrator.suites.red_team.schemas import RedTeamConfig


def load_red_team_config() -> RedTeamConfig:
    """Load Red Team configuration from environment variables with defaults."""
    
    # Parse required metrics from comma-separated string
    required_metrics_str = os.getenv("REDTEAM_REQUIRED_METRICS", "prompt_injection,data_extraction")
    required_metrics = [metric.strip() for metric in required_metrics_str.split(",") if metric.strip()]
    
    return RedTeamConfig(
        enabled=os.getenv("REDTEAM_ENABLED", "true").lower() == "true",
        fail_fast=os.getenv("REDTEAM_FAIL_FAST", "true").lower() == "true",
        max_steps=int(os.getenv("REDTEAM_MAX_STEPS", "6")),
        seed=int(os.getenv("REDTEAM_SEED", "0")),
        mask_secrets=os.getenv("REDTEAM_MASK_SECRETS", "true").lower() == "true",
        required_metrics=required_metrics
    )


# Global config instance
red_team_config = load_red_team_config()
