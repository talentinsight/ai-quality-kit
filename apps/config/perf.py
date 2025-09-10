"""
Performance Testing Configuration.

Environment variables for performance testing parameters and thresholds.
"""

import os

# Core performance testing settings
PERF_ENABLED = os.getenv("PERF_ENABLED", "true").lower() == "true"
PERF_FAIL_FAST = os.getenv("PERF_FAIL_FAST", "true").lower() == "true"

# Default load settings
PERF_CLIENT_MODE = os.getenv("PERF_CLIENT_MODE", "closed_loop")  # default if scenario omits
PERF_TIMEOUT_MS = int(os.getenv("PERF_TIMEOUT_MS", "60000"))
PERF_DEFAULT_CONCURRENCY = int(os.getenv("PERF_DEFAULT_CONCURRENCY", "4"))
PERF_DEFAULT_RATE_RPS = float(os.getenv("PERF_DEFAULT_RATE_RPS", "8"))
PERF_DEFAULT_DURATION_SEC = int(os.getenv("PERF_DEFAULT_DURATION_SEC", "30"))

# Performance thresholds
PERF_P95_MS_MAX = float(os.getenv("PERF_P95_MS_MAX", "2500"))
PERF_ERROR_RATE_MAX = float(os.getenv("PERF_ERROR_RATE_MAX", "0.02"))
PERF_TIMEOUT_RATE_MAX = float(os.getenv("PERF_TIMEOUT_RATE_MAX", "0.01"))
PERF_THROUGHPUT_MIN_RPS = float(os.getenv("PERF_THROUGHPUT_MIN_RPS", "5"))
PERF_TOKENS_PER_SEC_MIN = float(os.getenv("PERF_TOKENS_PER_SEC_MIN", "0.0"))
PERF_MEMORY_PEAK_MB_MAX = float(os.getenv("PERF_MEMORY_PEAK_MB_MAX", "1024"))

# Observability settings
PERF_OBSERVABILITY_HEADERS = os.getenv("PERF_OBSERVABILITY_HEADERS", "true").lower() == "true"

# UI template settings
SHOW_PERF_JSONL_TEMPLATE = os.getenv("SHOW_PERF_JSONL_TEMPLATE", "false").lower() == "true"

# Validation
assert PERF_TIMEOUT_MS > 0, "PERF_TIMEOUT_MS must be positive"
assert PERF_DEFAULT_CONCURRENCY > 0, "PERF_DEFAULT_CONCURRENCY must be positive"
assert PERF_DEFAULT_RATE_RPS > 0, "PERF_DEFAULT_RATE_RPS must be positive"
assert PERF_DEFAULT_DURATION_SEC > 0, "PERF_DEFAULT_DURATION_SEC must be positive"
assert 0 <= PERF_ERROR_RATE_MAX <= 1, "PERF_ERROR_RATE_MAX must be between 0 and 1"
assert 0 <= PERF_TIMEOUT_RATE_MAX <= 1, "PERF_TIMEOUT_RATE_MAX must be between 0 and 1"
assert PERF_CLIENT_MODE in ["closed_loop", "open_loop"], "PERF_CLIENT_MODE must be 'closed_loop' or 'open_loop'"
