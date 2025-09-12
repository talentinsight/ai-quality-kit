"""
Standardized exception hierarchy for AI Quality Kit.

Provides consistent error handling across all modules with proper
categorization and structured error information.
"""

from typing import Dict, Any, Optional


class EvaluationError(Exception):
    """Base exception for all AI Quality Kit evaluation errors."""
    
    def __init__(
        self, 
        message: str, 
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__.upper()
        self.details = details or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for structured logging/responses."""
        return {
            "error_type": self.__class__.__name__,
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details
        }


class DatasetValidationError(EvaluationError):
    """Raised when dataset validation fails."""
    
    def __init__(
        self, 
        message: str, 
        dataset_type: Optional[str] = None,
        validation_errors: Optional[list] = None,
        **kwargs
    ):
        details = kwargs.get('details', {})
        if dataset_type:
            details['dataset_type'] = dataset_type
        if validation_errors:
            details['validation_errors'] = validation_errors
        
        super().__init__(message, details=details, **kwargs)


class SuiteExecutionError(EvaluationError):
    """Raised when test suite execution fails."""
    
    def __init__(
        self, 
        message: str, 
        suite_name: Optional[str] = None,
        test_id: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.get('details', {})
        if suite_name:
            details['suite_name'] = suite_name
        if test_id:
            details['test_id'] = test_id
        
        super().__init__(message, details=details, **kwargs)


class ProviderError(EvaluationError):
    """Raised when LLM provider interactions fail."""
    
    def __init__(
        self, 
        message: str, 
        provider_name: Optional[str] = None,
        status_code: Optional[int] = None,
        **kwargs
    ):
        details = kwargs.get('details', {})
        if provider_name:
            details['provider_name'] = provider_name
        if status_code:
            details['status_code'] = status_code
        
        super().__init__(message, details=details, **kwargs)


class ReportError(EvaluationError):
    """Raised when report generation fails."""
    
    def __init__(
        self, 
        message: str, 
        report_format: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.get('details', {})
        if report_format:
            details['report_format'] = report_format
        
        super().__init__(message, details=details, **kwargs)


class ConfigurationError(EvaluationError):
    """Raised when configuration is invalid or missing."""
    
    def __init__(
        self, 
        message: str, 
        config_key: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.get('details', {})
        if config_key:
            details['config_key'] = config_key
        
        super().__init__(message, details=details, **kwargs)


class GatingError(EvaluationError):
    """Raised when test gating logic fails."""
    
    def __init__(
        self, 
        message: str, 
        failed_tests: Optional[list] = None,
        **kwargs
    ):
        details = kwargs.get('details', {})
        if failed_tests:
            details['failed_tests'] = failed_tests
        
        super().__init__(message, details=details, **kwargs)
