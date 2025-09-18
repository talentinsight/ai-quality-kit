"""
HTTP exception handlers for consistent error responses.

Provides standardized JSON error responses for all known exception types
with proper status codes and safe error details.
"""

import logging
from typing import Dict, Any
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from .errors import (
    EvaluationError, 
    DatasetValidationError, 
    SuiteExecutionError,
    ProviderError, 
    ReportError, 
    ConfigurationError,
    GatingError
)
from .logging import get_logger, redact

logger = get_logger(__name__)


def create_error_response(
    status_code: int,
    error_code: str,
    message: str,
    details: Dict[str, Any] = None
) -> JSONResponse:
    """
    Create standardized error response.
    
    Args:
        status_code: HTTP status code
        error_code: Application-specific error code
        message: Human-readable error message
        details: Additional error details (will be redacted)
        
    Returns:
        JSONResponse with standardized error format
    """
    response_data = {
        "error": True,
        "status_code": status_code,
        "error_code": error_code,
        "message": redact(message),
        "details": {}
    }
    
    if details:
        # Redact sensitive information from details
        response_data["details"] = {
            k: redact(str(v)) if isinstance(v, str) else v 
            for k, v in details.items()
        }
    
    return JSONResponse(
        status_code=status_code,
        content=response_data
    )


async def evaluation_error_handler(request: Request, exc: EvaluationError) -> JSONResponse:
    """Handle EvaluationError and its subclasses."""
    logger.error(f"EvaluationError: {exc.message}", extra={"error_code": exc.error_code, "details": exc.details})
    
    # Map specific error types to HTTP status codes
    status_code_map = {
        DatasetValidationError: 400,
        SuiteExecutionError: 500,
        ProviderError: 502,
        ReportError: 500,
        ConfigurationError: 500,
        GatingError: 422,
    }
    
    status_code = status_code_map.get(type(exc), 500)
    
    return create_error_response(
        status_code=status_code,
        error_code=exc.error_code,
        message=exc.message,
        details=exc.details
    )


async def dataset_validation_error_handler(request: Request, exc: DatasetValidationError) -> JSONResponse:
    """Handle dataset validation errors specifically."""
    logger.warning(f"Dataset validation failed: {exc.message}", extra=exc.details)
    
    return create_error_response(
        status_code=400,
        error_code="DATASET_VALIDATION_ERROR",
        message=exc.message,
        details=exc.details
    )


async def suite_execution_error_handler(request: Request, exc: SuiteExecutionError) -> JSONResponse:
    """Handle suite execution errors specifically."""
    logger.error(f"Suite execution failed: {exc.message}", extra=exc.details)
    
    return create_error_response(
        status_code=500,
        error_code="SUITE_EXECUTION_ERROR",
        message=exc.message,
        details=exc.details
    )


async def provider_error_handler(request: Request, exc: ProviderError) -> JSONResponse:
    """Handle LLM provider errors specifically."""
    logger.error(f"Provider error: {exc.message}", extra=exc.details)
    
    return create_error_response(
        status_code=502,
        error_code="PROVIDER_ERROR",
        message=exc.message,
        details=exc.details
    )


async def configuration_error_handler(request: Request, exc: ConfigurationError) -> JSONResponse:
    """Handle configuration errors specifically."""
    logger.error(f"Configuration error: {exc.message}", extra=exc.details)
    
    return create_error_response(
        status_code=500,
        error_code="CONFIGURATION_ERROR",
        message=exc.message,
        details=exc.details
    )


async def gating_error_handler(request: Request, exc: GatingError) -> JSONResponse:
    """Handle gating errors specifically."""
    logger.warning(f"Gating error: {exc.message}", extra=exc.details)
    
    return create_error_response(
        status_code=422,
        error_code="GATING_ERROR",
        message=exc.message,
        details=exc.details
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle FastAPI HTTPExceptions."""
    logger.warning(f"HTTP exception: {exc.detail}", extra={"status_code": exc.status_code})
    
    return create_error_response(
        status_code=exc.status_code,
        error_code="HTTP_ERROR",
        message=str(exc.detail),
        details={"status_code": exc.status_code}
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle request validation errors."""
    logger.warning(f"Request validation error: {exc.errors()}")
    
    return create_error_response(
        status_code=422,
        error_code="VALIDATION_ERROR",
        message="Request validation failed",
        details={"validation_errors": exc.errors()}
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions."""
    logger.error(f"Unexpected error: {str(exc)}", exc_info=True)
    
    return create_error_response(
        status_code=500,
        error_code="INTERNAL_ERROR",
        message="An unexpected error occurred",
        details={"error_type": type(exc).__name__}
    )


def install_exception_handlers(app: FastAPI) -> None:
    """
    Install all exception handlers on the FastAPI app.
    
    Args:
        app: FastAPI application instance
    """
    # Install specific exception handlers
    app.add_exception_handler(DatasetValidationError, dataset_validation_error_handler)
    app.add_exception_handler(SuiteExecutionError, suite_execution_error_handler)
    app.add_exception_handler(ProviderError, provider_error_handler)
    app.add_exception_handler(ConfigurationError, configuration_error_handler)
    app.add_exception_handler(GatingError, gating_error_handler)
    
    # Install base exception handler (catches all EvaluationError subclasses)
    app.add_exception_handler(EvaluationError, evaluation_error_handler)
    
    # Install FastAPI built-in exception handlers
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    
    # Install catch-all handler
    app.add_exception_handler(Exception, generic_exception_handler)
    
    logger.info("Exception handlers installed successfully")
