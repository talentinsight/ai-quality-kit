"""
Test standardized error handling.

Ensures that the common error classes work correctly and provide
proper structured error information.
"""

import pytest
from apps.common.errors import (
    EvaluationError,
    DatasetValidationError,
    SuiteExecutionError,
    ProviderError,
    ReportError,
    ConfigurationError,
    GatingError
)


class TestEvaluationError:
    """Test base EvaluationError class."""
    
    def test_basic_error_creation(self):
        """Test basic error creation."""
        error = EvaluationError("Test error message")
        
        assert str(error) == "Test error message"
        assert error.message == "Test error message"
        assert error.error_code == "EVALUATIONERROR"
        assert error.details == {}
    
    def test_error_with_code_and_details(self):
        """Test error creation with custom code and details."""
        details = {"key": "value", "count": 42}
        error = EvaluationError(
            "Test error", 
            error_code="CUSTOM_ERROR",
            details=details
        )
        
        assert error.error_code == "CUSTOM_ERROR"
        assert error.details == details
    
    def test_error_to_dict(self):
        """Test error serialization to dictionary."""
        error = EvaluationError(
            "Test error",
            error_code="TEST_ERROR",
            details={"field": "value"}
        )
        
        result = error.to_dict()
        
        expected = {
            "error_type": "EvaluationError",
            "error_code": "TEST_ERROR",
            "message": "Test error",
            "details": {"field": "value"}
        }
        
        assert result == expected


class TestSpecificErrors:
    """Test specific error subclasses."""
    
    def test_dataset_validation_error(self):
        """Test DatasetValidationError."""
        validation_errors = [{"field": "id", "message": "required"}]
        error = DatasetValidationError(
            "Validation failed",
            dataset_type="safety",
            validation_errors=validation_errors
        )
        
        assert error.details["dataset_type"] == "safety"
        assert error.details["validation_errors"] == validation_errors
        assert error.error_code == "DATASETVALIDATIONERROR"
    
    def test_suite_execution_error(self):
        """Test SuiteExecutionError."""
        error = SuiteExecutionError(
            "Suite failed",
            suite_name="red_team",
            test_id="test_001"
        )
        
        assert error.details["suite_name"] == "red_team"
        assert error.details["test_id"] == "test_001"
    
    def test_provider_error(self):
        """Test ProviderError."""
        error = ProviderError(
            "Provider timeout",
            provider_name="openai",
            status_code=504
        )
        
        assert error.details["provider_name"] == "openai"
        assert error.details["status_code"] == 504
    
    def test_report_error(self):
        """Test ReportError."""
        error = ReportError(
            "Report generation failed",
            report_format="xlsx"
        )
        
        assert error.details["report_format"] == "xlsx"
    
    def test_configuration_error(self):
        """Test ConfigurationError."""
        error = ConfigurationError(
            "Missing config",
            config_key="API_KEY"
        )
        
        assert error.details["config_key"] == "API_KEY"
    
    def test_gating_error(self):
        """Test GatingError."""
        failed_tests = ["test_001", "test_002"]
        error = GatingError(
            "Gating failed",
            failed_tests=failed_tests
        )
        
        assert error.details["failed_tests"] == failed_tests
    
    def test_error_inheritance(self):
        """Test that all errors inherit from EvaluationError."""
        errors = [
            DatasetValidationError("test"),
            SuiteExecutionError("test"),
            ProviderError("test"),
            ReportError("test"),
            ConfigurationError("test"),
            GatingError("test")
        ]
        
        for error in errors:
            assert isinstance(error, EvaluationError)
            assert hasattr(error, 'to_dict')
            assert callable(error.to_dict)
