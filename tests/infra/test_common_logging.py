"""
Test standardized logging with redaction.

Ensures that logging utilities properly redact sensitive information
and provide consistent logging patterns.
"""

import pytest
import logging
from unittest.mock import patch, MagicMock
from apps.common.logging import (
    redact,
    get_logger,
    RedactingLogger,
    get_redacting_logger,
    log_structured
)


class TestRedactionFunction:
    """Test the redact function."""
    
    def test_redact_api_keys(self):
        """Test redaction of API keys."""
        test_cases = [
            ("sk-1234567890abcdef1234567890abcdef", "sk-***REDACTED***"),
            ("xoxb-1234567890-1234567890-abcdefghijklmnopqrstuvwx", "xoxb-***REDACTED***"),
            ("ghp_1234567890abcdef1234567890abcdef123456", "ghp_***REDACTED***"),
            ("AKIA1234567890ABCDEF", "AKIA***REDACTED***")
        ]
        
        for original, expected in test_cases:
            result = redact(original)
            assert result == expected, f"Failed to redact {original}"
    
    def test_redact_key_value_patterns(self):
        """Test redaction of key=value patterns."""
        test_cases = [
            ("api_key=secret123456", "api_key=***REDACTED***"),
            ("token: bearer_token_here", "token=***REDACTED***"),
            ("password='mypassword123'", "password=***REDACTED***"),
            ('secret="topsecret456"', "secret=***REDACTED***")
        ]
        
        for original, expected in test_cases:
            result = redact(original)
            assert "***REDACTED***" in result, f"Failed to redact {original}"
    
    def test_redact_email_addresses(self):
        """Test redaction of email addresses."""
        text = "Contact user@example.com for support"
        result = redact(text)
        assert "***EMAIL_REDACTED***" in result
        assert "user@example.com" not in result
    
    def test_redact_phone_numbers(self):
        """Test redaction of phone numbers."""
        test_cases = [
            "Call 555-123-4567",
            "Phone: 555.123.4567",
            "Contact 5551234567"
        ]
        
        for text in test_cases:
            result = redact(text)
            assert "***PHONE_REDACTED***" in result
    
    def test_redact_harmful_content(self):
        """Test redaction of harmful content markers."""
        text = "I want to kill the process"
        result = redact(text)
        assert "***HARMFUL_CONTENT***" in result
        assert "kill" not in result
    
    def test_redact_preserves_safe_content(self):
        """Test that safe content is preserved."""
        safe_text = "This is a normal log message with no secrets"
        result = redact(safe_text)
        assert result == safe_text
    
    def test_redact_non_string_input(self):
        """Test redaction with non-string input."""
        result = redact(12345)
        assert result == "12345"
        
        result = redact(None)
        assert result == "None"


class TestLoggerFunctions:
    """Test logger creation functions."""
    
    def test_get_logger(self):
        """Test get_logger function."""
        logger = get_logger("test_logger")
        
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_logger"
    
    def test_get_redacting_logger(self):
        """Test get_redacting_logger function."""
        logger = get_redacting_logger("test_redacting_logger")
        
        assert isinstance(logger, RedactingLogger)
        assert isinstance(logger.logger, logging.Logger)


class TestRedactingLogger:
    """Test RedactingLogger class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_logger = MagicMock()
        self.redacting_logger = RedactingLogger(self.mock_logger)
    
    def test_debug_with_redaction(self):
        """Test debug logging with redaction."""
        self.redacting_logger.debug("API key: sk-1234567890abcdef1234567890abcdef")
        
        self.mock_logger.log.assert_called_once()
        args, kwargs = self.mock_logger.log.call_args
        assert args[0] == logging.DEBUG
        assert "sk-***REDACTED***" in args[1]
    
    def test_info_with_redaction(self):
        """Test info logging with redaction."""
        self.redacting_logger.info("User email: user@example.com")
        
        self.mock_logger.log.assert_called_once()
        args, kwargs = self.mock_logger.log.call_args
        assert args[0] == logging.INFO
        assert "***EMAIL_REDACTED***" in args[1]
    
    def test_error_with_redaction(self):
        """Test error logging with redaction."""
        self.redacting_logger.error("Failed with token: xoxb-secret-token")
        
        self.mock_logger.log.assert_called_once()
        args, kwargs = self.mock_logger.log.call_args
        assert args[0] == logging.ERROR
        assert "xoxb-***REDACTED***" in args[1]
    
    def test_format_string_with_args(self):
        """Test logging with format string and arguments."""
        self.redacting_logger.info("User %s has token %s", "john", "sk-secret123456")
        
        self.mock_logger.log.assert_called_once()
        args, kwargs = self.mock_logger.log.call_args
        logged_message = args[1]
        assert "john" in logged_message
        assert "sk-***REDACTED***" in logged_message


class TestStructuredLogging:
    """Test structured logging function."""
    
    def test_log_structured_with_extra_data(self):
        """Test structured logging with extra data."""
        mock_logger = MagicMock()
        extra_data = {
            "user_id": "12345",
            "api_key": "sk-secret123456",
            "email": "user@example.com"
        }
        
        log_structured(mock_logger, logging.INFO, "Test message", extra_data)
        
        mock_logger.log.assert_called_once()
        args, kwargs = mock_logger.log.call_args
        logged_message = args[1]
        
        assert "Test message" in logged_message
        assert "12345" in logged_message  # Safe data preserved
        assert "sk-***REDACTED***" in logged_message  # API key redacted
        assert "***EMAIL_REDACTED***" in logged_message  # Email redacted
    
    def test_log_structured_without_extra_data(self):
        """Test structured logging without extra data."""
        mock_logger = MagicMock()
        
        log_structured(mock_logger, logging.INFO, "Simple message")
        
        mock_logger.log.assert_called_once()
        args, kwargs = mock_logger.log.call_args
        assert args[1] == "Simple message"
