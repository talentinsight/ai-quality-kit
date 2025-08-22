"""Unit tests for log service functionality."""

import pytest
from unittest.mock import patch, Mock
import os


class TestLogService:
    """Test logging service operations."""
    
    def test_logging_disabled(self, set_env_defaults):
        """Test that logging is disabled by default."""
        with patch.dict(os.environ, set_env_defaults):
            from apps.observability.log_service import is_logging_enabled
            
            assert is_logging_enabled() is False
    
    def test_logging_enabled(self, set_env_defaults):
        """Test that logging can be enabled."""
        env_enabled = {**set_env_defaults, "ENABLE_API_LOGGING": "true"}
        with patch.dict(os.environ, env_enabled):
            from apps.observability.log_service import is_logging_enabled
            
            assert is_logging_enabled() is True
    
    def test_live_eval_disabled(self, set_env_defaults):
        """Test that live evaluation is disabled by default."""
        with patch.dict(os.environ, set_env_defaults):
            from apps.observability.log_service import is_live_eval_enabled
            
            assert is_live_eval_enabled() is False
    
    def test_live_eval_enabled(self, set_env_defaults):
        """Test that live evaluation can be enabled."""
        env_enabled = {**set_env_defaults, "ENABLE_LIVE_EVAL": "true"}
        with patch.dict(os.environ, env_enabled):
            from apps.observability.log_service import is_live_eval_enabled
            
            assert is_live_eval_enabled() is True
    
    def test_start_log_disabled(self, set_env_defaults):
        """Test start_log when logging is disabled."""
        with patch.dict(os.environ, set_env_defaults):
            from apps.observability.log_service import start_log
            
            # Should return a pseudo-id when logging is disabled
            log_id = start_log("test query", "test_hash", ["context1"], "live")
            
            assert log_id is not None
            assert isinstance(log_id, str)
    
    def test_start_log_enabled(self, fake_snowflake_cursor, set_env_defaults):
        """Test start_log when logging is enabled."""
        env_enabled = {**set_env_defaults, "ENABLE_API_LOGGING": "true"}
        with patch.dict(os.environ, env_enabled):
            from apps.observability.log_service import start_log
            
            log_id = start_log("test query", "test_hash", ["context1"], "live")
            
            # Should return a log ID
            assert log_id is not None
            assert isinstance(log_id, str)
            
            # Should execute SQL when logging is enabled
            fake_snowflake_cursor.execute.assert_called()
    
    def test_finish_log_disabled(self, set_env_defaults):
        """Test finish_log when logging is disabled."""
        with patch.dict(os.environ, set_env_defaults):
            from apps.observability.log_service import finish_log
            
            # Should not crash when logging is disabled
            finish_log("test_id", "test_answer", 100)
    
    def test_finish_log_enabled(self, fake_snowflake_cursor, set_env_defaults):
        """Test finish_log when logging is enabled."""
        env_enabled = {**set_env_defaults, "ENABLE_API_LOGGING": "true"}
        with patch.dict(os.environ, env_enabled):
            from apps.observability.log_service import finish_log
            
            finish_log("test_id", "test_answer", 100)
            
            # Should execute SQL when logging is enabled
            fake_snowflake_cursor.execute.assert_called()
    
    def test_log_eval_metrics_disabled(self, set_env_defaults):
        """Test log_eval_metrics when logging is disabled."""
        with patch.dict(os.environ, set_env_defaults):
            from apps.observability.log_service import log_eval_metrics
            
            # Should not crash when logging is disabled
            log_eval_metrics("test_id", "ragas", {"faithfulness": 0.8, "context_recall": 0.9})
    
    def test_log_eval_metrics_enabled(self, fake_snowflake_cursor, set_env_defaults):
        """Test log_eval_metrics when logging is enabled."""
        env_enabled = {**set_env_defaults, "ENABLE_API_LOGGING": "true"}
        with patch.dict(os.environ, env_enabled):
            from apps.observability.log_service import log_eval_metrics
            
            metrics = {"faithfulness": 0.8, "context_recall": 0.9}
            log_eval_metrics("test_id", "ragas", metrics)
            
            # Should execute SQL when logging is enabled
            fake_snowflake_cursor.execute.assert_called()
    
    def test_provider_info_extraction(self, set_env_defaults):
        """Test provider information extraction."""
        with patch.dict(os.environ, set_env_defaults):
            from apps.observability.log_service import _get_provider_info
            
            provider_info = _get_provider_info()
            
            assert "provider" in provider_info
            assert "model_name" in provider_info
            assert provider_info["provider"] == "openai"
            assert provider_info["model_name"] == "gpt-4o-mini"
    
    def test_logging_with_pii_redaction(self, fake_snowflake_cursor, set_env_defaults):
        """Test that PII is redacted in logs."""
        env_enabled = {**set_env_defaults, "ENABLE_API_LOGGING": "true"}
        with patch.dict(os.environ, env_enabled):
            from apps.observability.log_service import start_log
            
            # Query with potential PII
            query_with_pii = "My email is user@example.com and phone is 555-123-4567"
            log_id = start_log(query_with_pii, "test_hash", ["context"], "live")
            
            # Should execute SQL
            fake_snowflake_cursor.execute.assert_called()
            
            # Check if PII was redacted (this depends on implementation)
            call_args = fake_snowflake_cursor.execute.call_args
            if call_args and call_args[0]:
                sql = call_args[0][0]
                # Should not contain raw PII in SQL
                assert "user@example.com" not in sql
                assert "555-123-4567" not in sql
    
    def test_logging_error_handling(self, fake_snowflake_cursor, set_env_defaults):
        """Test error handling in logging operations."""
        env_enabled = {**set_env_defaults, "ENABLE_API_LOGGING": "true"}
        with patch.dict(os.environ, env_enabled):
            from apps.observability.log_service import start_log
            
            # Mock cursor to raise exception
            fake_snowflake_cursor.execute.side_effect = Exception("Database error")
            
            # Should handle errors gracefully
            log_id = start_log("test query", "test_hash", ["context"], "live")
            
            # Should still return a log ID even on error
            assert log_id is not None
    
    def test_logging_performance_tracking(self, fake_snowflake_cursor, set_env_defaults):
        """Test that performance metrics are tracked."""
        env_enabled = {**set_env_defaults, "ENABLE_API_LOGGING": "true"}
        with patch.dict(os.environ, env_enabled):
            from apps.observability.log_service import start_log, finish_log
            
            # Start logging
            log_id = start_log("test query", "test_hash", ["context"], "live")
            
            # Finish logging with performance metrics
            finish_log(log_id, "test answer", 150)  # 150ms latency
            
            # Should execute SQL for both start and finish
            assert fake_snowflake_cursor.execute.call_count >= 2
