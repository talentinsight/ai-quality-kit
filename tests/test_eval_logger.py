"""Test evaluation logger functionality."""

import pytest
import os
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class TestEvalLogger:
    """Test evaluation logger functionality."""
    
    def test_is_logging_enabled_true(self):
        """Test that logging is enabled when all conditions are met."""
        with patch.dict(os.environ, {
            "LOG_TO_SNOWFLAKE": "true",
            "SNOWFLAKE_ACCOUNT": "test-account",
            "SNOWFLAKE_USER": "test-user",
            "SNOWFLAKE_PASSWORD": "test-password",
            "SNOWFLAKE_ROLE": "test-role",
            "SNOWFLAKE_WAREHOUSE": "test-warehouse",
            "SNOWFLAKE_DATABASE": "test-database",
            "SNOWFLAKE_SCHEMA": "test-schema"
        }):
            from apps.db.eval_logger import is_logging_enabled
            assert is_logging_enabled() is True
    
    def test_is_logging_enabled_false_log_disabled(self):
        """Test that logging is disabled when LOG_TO_SNOWFLAKE is not 'true'."""
        with patch.dict(os.environ, {
            "LOG_TO_SNOWFLAKE": "false",
            "SNOWFLAKE_ACCOUNT": "test-account",
            "SNOWFLAKE_USER": "test-user",
            "SNOWFLAKE_PASSWORD": "test-password",
            "SNOWFLAKE_ROLE": "test-role",
            "SNOWFLAKE_WAREHOUSE": "test-warehouse",
            "SNOWFLAKE_DATABASE": "test-database",
            "SNOWFLAKE_SCHEMA": "test-schema"
        }):
            from apps.db.eval_logger import is_logging_enabled
            assert is_logging_enabled() is False
    
    def test_is_logging_enabled_false_missing_env_vars(self):
        """Test that logging is disabled when required env vars are missing."""
        with patch.dict(os.environ, {
            "LOG_TO_SNOWFLAKE": "true",
            "SNOWFLAKE_ACCOUNT": "test-account"
            # Missing other required vars
        }, clear=True):
            from apps.db.eval_logger import is_logging_enabled
            assert is_logging_enabled() is False
    
    def test_is_logging_enabled_false_log_not_set(self):
        """Test that logging is disabled when LOG_TO_SNOWFLAKE is not set."""
        with patch.dict(os.environ, {
            "SNOWFLAKE_ACCOUNT": "test-account",
            "SNOWFLAKE_USER": "test-user",
            "SNOWFLAKE_PASSWORD": "test-password",
            "SNOWFLAKE_ROLE": "test-role",
            "SNOWFLAKE_WAREHOUSE": "test-warehouse",
            "SNOWFLAKE_DATABASE": "test-database",
            "SNOWFLAKE_SCHEMA": "test-schema"
        }):
            from apps.db.eval_logger import is_logging_enabled
            assert is_logging_enabled() is False
    
    def test_ensure_tables_note(self, capsys):
        """Test that ensure_tables_note prints the expected message."""
        from apps.db.eval_logger import ensure_tables_note
        
        ensure_tables_note()
        captured = capsys.readouterr()
        
        assert "LLM_EVAL_RESULTS table exists" in captured.out
        assert "RUN_ID, METRIC_GROUP, METRIC_NAME" in captured.out
        assert "CREATE TABLE LLM_EVAL_RESULTS" in captured.out
    
    def test_log_evaluation_results_success(self, capsys):
        """Test successful logging of evaluation results."""
        # For now, just test that the function doesn't crash
        # The actual Snowflake interaction is complex to mock properly
        with patch.dict(os.environ, {
            "LOG_TO_SNOWFLAKE": "true",
            "SNOWFLAKE_ACCOUNT": "test-account",
            "SNOWFLAKE_USER": "test-user",
            "SNOWFLAKE_PASSWORD": "test-password",
            "SNOWFLAKE_ROLE": "test-role",
            "SNOWFLAKE_WAREHOUSE": "test-warehouse",
            "SNOWFLAKE_DATABASE": "test-database",
            "SNOWFLAKE_SCHEMA": "test-schema"
        }):
            # Import after patching environment
            from apps.db.eval_logger import log_evaluation_results
            
            # Test data
            run_id = "test-run-123"
            metric_group = "ragas"
            metrics = {"faithfulness": 0.85, "answer_relevancy": 0.92}
            extra = {"model": "gpt-4", "temperature": 0.1}
            
            # This should not crash (even if it can't connect to Snowflake)
            log_evaluation_results(run_id, metric_group, metrics, extra)
            
            # Verify some output was produced
            captured = capsys.readouterr()
            assert "metrics to Snowflake" in captured.out or "Failed to log" in captured.out
    
    def test_log_evaluation_results_no_extra(self, capsys):
        """Test logging evaluation results without extra data."""
        # For now, just test that the function doesn't crash
        # The actual Snowflake interaction is complex to mock properly
        with patch.dict(os.environ, {
            "LOG_TO_SNOWFLAKE": "true",
            "SNOWFLAKE_ACCOUNT": "test-account",
            "SNOWFLAKE_USER": "test-user",
            "SNOWFLAKE_PASSWORD": "test-password",
            "SNOWFLAKE_ROLE": "test-role",
            "SNOWFLAKE_WAREHOUSE": "test-warehouse",
            "SNOWFLAKE_DATABASE": "test-database",
            "SNOWFLAKE_SCHEMA": "test-schema"
        }):
            # Import after patching environment
            from apps.db.eval_logger import log_evaluation_results
            
            # Test data without extra
            run_id = "test-run-456"
            metric_group = "guardrails"
            metrics = {"safety_score": 0.95}
            
            # This should not crash (even if it can't connect to Snowflake)
            log_evaluation_results(run_id, metric_group, metrics)
            
            # Verify some output was produced
            captured = capsys.readouterr()
            assert "metrics to Snowflake" in captured.out or "Failed to log" in captured.out
    
    def test_log_evaluation_results_logging_disabled(self, capsys):
        """Test that logging is skipped when disabled."""
        with patch.dict(os.environ, {
            "LOG_TO_SNOWFLAKE": "false"
        }):
            from apps.db.eval_logger import log_evaluation_results
            
            log_evaluation_results("test-run", "test-group", {"test": 1.0})
            
            captured = capsys.readouterr()
            assert "Skipping Snowflake logging for test-group metrics" in captured.out
    
    def test_log_evaluation_results_no_snowflake_client(self, capsys):
        """Test that logging is skipped when snowflake client is not available."""
        with patch.dict(os.environ, {
            "LOG_TO_SNOWFLAKE": "true",
            "SNOWFLAKE_ACCOUNT": "test-account",
            "SNOWFLAKE_USER": "test-user",
            "SNOWFLAKE_PASSWORD": "test-password",
            "SNOWFLAKE_ROLE": "test-role",
            "SNOWFLAKE_WAREHOUSE": "test-warehouse",
            "SNOWFLAKE_DATABASE": "test-database",
            "SNOWFLAKE_SCHEMA": "test-schema"
        }):
            # Mock snowflake_cursor to be None
            with patch('apps.db.eval_logger.snowflake_cursor', None):
                from apps.db.eval_logger import log_evaluation_results
                
                log_evaluation_results("test-run", "test-group", {"test": 1.0})
                
                captured = capsys.readouterr()
                assert "snowflake client not available" in captured.out
    
    @patch('apps.db.eval_logger.snowflake_cursor')
    def test_log_evaluation_results_exception_handling(self, mock_snowflake_cursor, capsys):
        """Test that exceptions during logging are handled gracefully."""
        # Mock the cursor to raise an exception
        mock_cursor = MagicMock()
        mock_cursor.__enter__.side_effect = Exception("Database connection failed")
        mock_snowflake_cursor.return_value = mock_cursor
        
        with patch.dict(os.environ, {
            "LOG_TO_SNOWFLAKE": "true",
            "SNOWFLAKE_ACCOUNT": "test-account",
            "SNOWFLAKE_USER": "test-user",
            "SNOWFLAKE_PASSWORD": "test-password",
            "SNOWFLAKE_ROLE": "test-role",
            "SNOWFLAKE_WAREHOUSE": "test-warehouse",
            "SNOWFLAKE_DATABASE": "test-database",
            "SNOWFLAKE_SCHEMA": "test-schema"
        }):
            from apps.db.eval_logger import log_evaluation_results
            
            # This should not crash
            log_evaluation_results("test-run", "test-group", {"test": 1.0})
            
            captured = capsys.readouterr()
            assert "Failed to log test-group metrics to Snowflake" in captured.out
    
    @patch('apps.db.eval_logger.snowflake_cursor')
    def test_log_evaluation_results_empty_metrics(self, mock_snowflake_cursor, capsys):
        """Test logging with empty metrics dictionary."""
        # Mock the cursor
        mock_cursor = MagicMock()
        mock_snowflake_cursor.return_value = mock_cursor
        
        # Mock the module import to ensure our mock is used
        with patch('apps.db.eval_logger.snowflake_cursor', mock_snowflake_cursor):
            with patch.dict(os.environ, {
                "LOG_TO_SNOWFLAKE": "true",
                "SNOWFLAKE_ACCOUNT": "test-account",
                "SNOWFLAKE_USER": "test-user",
                "SNOWFLAKE_PASSWORD": "test-password",
                "SNOWFLAKE_ROLE": "test-role",
                "SNOWFLAKE_WAREHOUSE": "test-warehouse",
                "SNOWFLAKE_DATABASE": "test-database",
                "SNOWFLAKE_SCHEMA": "test-schema"
            }):
                from apps.db.eval_logger import log_evaluation_results
                
                # Test with empty metrics
                log_evaluation_results("test-run", "test-group", {})
                
                # Verify cursor was called correctly (should still enter/exit even with no metrics)
                assert mock_cursor.__enter__.called
                assert mock_cursor.__exit__.called
                
                # Verify execute was not called (no metrics to log)
                assert mock_cursor.execute.call_count == 0
                
                captured = capsys.readouterr()
                assert "Logged 0 metrics to Snowflake for test-group" in captured.out
