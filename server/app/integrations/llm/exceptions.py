"""LLM service domain exceptions."""

from app.exceptions.base import ServiceUnavailableError


class LLMServiceError(ServiceUnavailableError):
    """Base exception for LLM service errors."""

    error_code = "LLM_ERROR"


class LLMRateLimitError(LLMServiceError):
    """Exception raised when LLM rate limit is exceeded."""

    error_code = "LLM_RATE_LIMIT"


class LLMTimeoutError(LLMServiceError):
    """Exception raised when LLM request times out."""

    error_code = "LLM_TIMEOUT"


class LLMStreamingError(LLMServiceError):
    """Exception raised when LLM streaming fails."""

    error_code = "LLM_STREAMING_ERROR"


class LLMAPIError(LLMServiceError):
    """Exception raised for general LLM API errors."""

    error_code = "LLM_API_ERROR"
