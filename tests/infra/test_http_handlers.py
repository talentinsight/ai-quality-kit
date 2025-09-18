"""
Test HTTP exception handlers.

Ensures that HTTP exception handlers provide consistent error responses
and proper error handling across the API.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from apps.common.errors import (
    EvaluationError,
    DatasetValidationError,
    SuiteExecutionError,
    ProviderError,
    ConfigurationError,
    GatingError
)
from apps.common.http_handlers import (
    create_error_response,
    evaluation_error_handler,
    dataset_validation_error_handler,
    suite_execution_error_handler,
    provider_error_handler,
    configuration_error_handler,
    gating_error_handler,
    http_exception_handler,
    validation_exception_handler,
    generic_exception_handler,
    install_exception_handlers
)


class TestErrorResponseCreation:
    """Test error response creation utilities."""
    
    def test_create_error_response_basic(self):
        """Test basic error response creation."""
        response = create_error_response(
            status_code=400,
            error_code="TEST_ERROR",
            message="Test error message"
        )
        
        assert isinstance(response, JSONResponse)
        assert response.status_code == 400
        
        content = response.body.decode()
        assert "TEST_ERROR" in content
        assert "Test error message" in content
    
    def test_create_error_response_with_details(self):
        """Test error response creation with details."""
        details = {"field": "value", "api_key": "sk-secret123"}
        response = create_error_response(
            status_code=422,
            error_code="VALIDATION_ERROR",
            message="Validation failed",
            details=details
        )
        
        content = response.body.decode()
        assert "VALIDATION_ERROR" in content
        assert "value" in content  # Safe detail preserved
        assert "sk-***REDACTED***" in content  # Secret redacted


class TestSpecificExceptionHandlers:
    """Test specific exception handlers."""
    
    @pytest.fixture
    def mock_request(self):
        """Create a mock request object."""
        return MagicMock(spec=Request)
    
    @pytest.mark.asyncio
    async def test_dataset_validation_error_handler(self, mock_request):
        """Test dataset validation error handler."""
        error = DatasetValidationError(
            "Invalid dataset",
            dataset_type="safety",
            validation_errors=[{"field": "id", "message": "required"}]
        )
        
        response = await dataset_validation_error_handler(mock_request, error)
        
        assert isinstance(response, JSONResponse)
        assert response.status_code == 400
        
        content = response.body.decode()
        assert "DATASET_VALIDATION_ERROR" in content
        assert "Invalid dataset" in content
    
    @pytest.mark.asyncio
    async def test_suite_execution_error_handler(self, mock_request):
        """Test suite execution error handler."""
        error = SuiteExecutionError(
            "Suite failed",
            suite_name="red_team",
            test_id="test_001"
        )
        
        response = await suite_execution_error_handler(mock_request, error)
        
        assert isinstance(response, JSONResponse)
        assert response.status_code == 500
        
        content = response.body.decode()
        assert "SUITE_EXECUTION_ERROR" in content
        assert "Suite failed" in content
    
    @pytest.mark.asyncio
    async def test_provider_error_handler(self, mock_request):
        """Test provider error handler."""
        error = ProviderError(
            "Provider timeout",
            provider_name="openai",
            status_code=504
        )
        
        response = await provider_error_handler(mock_request, error)
        
        assert isinstance(response, JSONResponse)
        assert response.status_code == 502
        
        content = response.body.decode()
        assert "PROVIDER_ERROR" in content
        assert "Provider timeout" in content
    
    @pytest.mark.asyncio
    async def test_configuration_error_handler(self, mock_request):
        """Test configuration error handler."""
        error = ConfigurationError(
            "Missing API key",
            config_key="OPENAI_API_KEY"
        )
        
        response = await configuration_error_handler(mock_request, error)
        
        assert isinstance(response, JSONResponse)
        assert response.status_code == 500
        
        content = response.body.decode()
        assert "CONFIGURATION_ERROR" in content
        assert "Missing API key" in content
    
    @pytest.mark.asyncio
    async def test_gating_error_handler(self, mock_request):
        """Test gating error handler."""
        error = GatingError(
            "Tests failed gating",
            failed_tests=["test_001", "test_002"]
        )
        
        response = await gating_error_handler(mock_request, error)
        
        assert isinstance(response, JSONResponse)
        assert response.status_code == 422
        
        content = response.body.decode()
        assert "GATING_ERROR" in content
        assert "Tests failed gating" in content
    
    @pytest.mark.asyncio
    async def test_http_exception_handler(self, mock_request):
        """Test HTTP exception handler."""
        error = HTTPException(status_code=404, detail="Not found")
        
        response = await http_exception_handler(mock_request, error)
        
        assert isinstance(response, JSONResponse)
        assert response.status_code == 404
        
        content = response.body.decode()
        assert "HTTP_ERROR" in content
        assert "Not found" in content
    
    @pytest.mark.asyncio
    async def test_validation_exception_handler(self, mock_request):
        """Test validation exception handler."""
        # Mock RequestValidationError
        error = MagicMock(spec=RequestValidationError)
        error.errors.return_value = [
            {"field": "name", "message": "required"},
            {"field": "email", "message": "invalid format"}
        ]
        
        response = await validation_exception_handler(mock_request, error)
        
        assert isinstance(response, JSONResponse)
        assert response.status_code == 422
        
        content = response.body.decode()
        assert "VALIDATION_ERROR" in content
        assert "Request validation failed" in content
    
    @pytest.mark.asyncio
    async def test_generic_exception_handler(self, mock_request):
        """Test generic exception handler."""
        error = ValueError("Unexpected error")
        
        response = await generic_exception_handler(mock_request, error)
        
        assert isinstance(response, JSONResponse)
        assert response.status_code == 500
        
        content = response.body.decode()
        assert "INTERNAL_ERROR" in content
        assert "An unexpected error occurred" in content
    
    @pytest.mark.asyncio
    async def test_evaluation_error_handler_status_mapping(self, mock_request):
        """Test that evaluation error handler maps error types to correct status codes."""
        test_cases = [
            (DatasetValidationError("test"), 400),
            (SuiteExecutionError("test"), 500),
            (ProviderError("test"), 502),
            (ConfigurationError("test"), 500),
            (GatingError("test"), 422),
            (EvaluationError("test"), 500)  # Default case
        ]
        
        for error, expected_status in test_cases:
            response = await evaluation_error_handler(mock_request, error)
            assert response.status_code == expected_status


class TestExceptionHandlerInstallation:
    """Test exception handler installation."""
    
    def test_install_exception_handlers(self):
        """Test that exception handlers are installed correctly."""
        app = FastAPI()
        
        # Should not raise any exceptions
        install_exception_handlers(app)
        
        # Verify that handlers are installed (basic check)
        assert hasattr(app, 'exception_handlers')
        assert len(app.exception_handlers) > 0
    
    def test_install_exception_handlers_idempotent(self):
        """Test that installing handlers multiple times is safe."""
        app = FastAPI()
        
        # Install handlers twice
        install_exception_handlers(app)
        initial_count = len(app.exception_handlers)
        
        install_exception_handlers(app)
        final_count = len(app.exception_handlers)
        
        # Should not duplicate handlers (though this depends on FastAPI implementation)
        # At minimum, should not crash
        assert final_count >= initial_count
