"""
Standardized logging utilities with PII/secret redaction.

Provides consistent logging patterns across all modules with automatic
redaction of sensitive information.
"""

import re
import logging
from typing import Any, Dict, Optional


# Patterns for sensitive information that should be redacted
REDACTION_PATTERNS = [
    # API Keys and tokens
    (re.compile(r'sk-[a-zA-Z0-9]{20,}', re.IGNORECASE), 'sk-***REDACTED***'),
    (re.compile(r'xoxb-[a-zA-Z0-9-]{20,}', re.IGNORECASE), 'xoxb-***REDACTED***'),
    (re.compile(r'ghp_[a-zA-Z0-9]{20,}', re.IGNORECASE), 'ghp_***REDACTED***'),
    (re.compile(r'AKIA[0-9A-Z]{16}', re.IGNORECASE), 'AKIA***REDACTED***'),
    
    # Generic secrets (key=value patterns)
    (re.compile(r'(api_?key|token|secret|password|pwd)\s*[=:]\s*["\']?([a-zA-Z0-9+/=]{8,})["\']?', re.IGNORECASE), 
     r'\1=***REDACTED***'),
    
    # Email addresses
    (re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'), '***EMAIL_REDACTED***'),
    
    # Phone numbers (basic patterns)
    (re.compile(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'), '***PHONE_REDACTED***'),
    
    # Credit card numbers (basic pattern)
    (re.compile(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b'), '***CARD_REDACTED***'),
    
    # Social Security Numbers
    (re.compile(r'\b\d{3}-\d{2}-\d{4}\b'), '***SSN_REDACTED***'),
    
    # Harmful content markers (for safety logs)
    (re.compile(r'\b(kill|murder|suicide|bomb|terrorist|nazi|hitler)\b', re.IGNORECASE), '***HARMFUL_CONTENT***'),
]


def redact(text: str) -> str:
    """
    Redact sensitive information from text.
    
    Args:
        text: Input text that may contain sensitive information
        
    Returns:
        Text with sensitive information redacted
    """
    if not isinstance(text, str):
        text = str(text)
    
    redacted_text = text
    
    for pattern, replacement in REDACTION_PATTERNS:
        redacted_text = pattern.sub(replacement, redacted_text)
    
    return redacted_text


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with consistent configuration.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    # Only configure if not already configured
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    
    return logger


class RedactingLogger:
    """
    Logger wrapper that automatically redacts sensitive information.
    """
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
    
    def _log_with_redaction(self, level: int, msg: Any, *args, **kwargs):
        """Log message with automatic redaction."""
        if args:
            # Handle format string with args
            try:
                formatted_msg = msg % args
            except (TypeError, ValueError):
                formatted_msg = f"{msg} {args}"
        else:
            formatted_msg = str(msg)
        
        redacted_msg = redact(formatted_msg)
        self.logger.log(level, redacted_msg, **kwargs)
    
    def debug(self, msg: Any, *args, **kwargs):
        """Log debug message with redaction."""
        self._log_with_redaction(logging.DEBUG, msg, *args, **kwargs)
    
    def info(self, msg: Any, *args, **kwargs):
        """Log info message with redaction."""
        self._log_with_redaction(logging.INFO, msg, *args, **kwargs)
    
    def warning(self, msg: Any, *args, **kwargs):
        """Log warning message with redaction."""
        self._log_with_redaction(logging.WARNING, msg, *args, **kwargs)
    
    def error(self, msg: Any, *args, **kwargs):
        """Log error message with redaction."""
        self._log_with_redaction(logging.ERROR, msg, *args, **kwargs)
    
    def critical(self, msg: Any, *args, **kwargs):
        """Log critical message with redaction."""
        self._log_with_redaction(logging.CRITICAL, msg, *args, **kwargs)


def get_redacting_logger(name: str) -> RedactingLogger:
    """
    Get a logger that automatically redacts sensitive information.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        RedactingLogger instance
    """
    base_logger = get_logger(name)
    return RedactingLogger(base_logger)


def log_structured(
    logger: logging.Logger, 
    level: int, 
    message: str, 
    extra_data: Optional[Dict[str, Any]] = None
):
    """
    Log structured data with redaction.
    
    Args:
        logger: Logger instance
        level: Log level
        message: Log message
        extra_data: Additional structured data to log
    """
    if extra_data:
        # Redact the entire extra data structure
        redacted_data = {k: redact(str(v)) for k, v in extra_data.items()}
        full_message = f"{message} | Data: {redacted_data}"
    else:
        full_message = message
    
    logger.log(level, redact(full_message))
