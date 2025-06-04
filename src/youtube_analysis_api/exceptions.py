"""Custom exceptions for the FastAPI backend."""

from datetime import datetime
from typing import Optional


class APIError(Exception):
    """Base API exception class."""
    
    def __init__(
        self,
        detail: str,
        status_code: int = 500,
        error_code: str = "API_ERROR"
    ):
        self.detail = detail
        self.message = detail  # Alias for compatibility
        self.status_code = status_code
        self.error_code = error_code
        super().__init__(detail)
    
    def to_json(self) -> str:
        """Convert error to JSON string."""
        import json
        return json.dumps({
            "success": False,
            "error": {
                "code": self.error_code,
                "message": self.message
            }
        })


class ValidationError(APIError):
    """Validation error exception."""
    
    def __init__(self, detail: str):
        super().__init__(
            detail=detail,
            status_code=422,
            error_code="VALIDATION_ERROR"
        )


class AuthenticationError(APIError):
    """Authentication error exception."""
    
    def __init__(self, detail: str = "Authentication required"):
        super().__init__(
            detail=detail,
            status_code=401,
            error_code="AUTHENTICATION_ERROR"
        )


class AuthorizationError(APIError):
    """Authorization error exception."""
    
    def __init__(self, detail: str = "Insufficient permissions"):
        super().__init__(
            detail=detail,
            status_code=403,
            error_code="AUTHORIZATION_ERROR"
        )


class NotFoundError(APIError):
    """Resource not found exception."""
    
    def __init__(self, detail: str = "Resource not found"):
        super().__init__(
            detail=detail,
            status_code=404,
            error_code="NOT_FOUND"
        )


class ConflictError(APIError):
    """Resource conflict exception."""
    
    def __init__(self, detail: str = "Resource conflict"):
        super().__init__(
            detail=detail,
            status_code=409,
            error_code="CONFLICT_ERROR"
        )


class RateLimitError(APIError):
    """Rate limit exceeded exception."""
    
    def __init__(self, detail: str = "Rate limit exceeded"):
        super().__init__(
            detail=detail,
            status_code=429,
            error_code="RATE_LIMIT_ERROR"
        )


class ServiceUnavailableError(APIError):
    """Service unavailable exception."""
    
    def __init__(self, detail: str = "Service temporarily unavailable"):
        super().__init__(
            detail=detail,
            status_code=503,
            error_code="SERVICE_UNAVAILABLE"
        )


class InternalServerError(APIError):
    """Internal server error exception."""
    
    def __init__(self, detail: str = "Internal server error"):
        super().__init__(
            detail=detail,
            status_code=500,
            error_code="INTERNAL_ERROR"
        )


class ExternalServiceError(APIError):
    """External service error exception."""
    
    def __init__(self, detail: str, service_name: str = "external"):
        super().__init__(
            detail=f"{service_name}: {detail}",
            status_code=502,
            error_code="EXTERNAL_SERVICE_ERROR"
        )


class TokenExpiredError(AuthenticationError):
    """JWT token expired exception."""
    
    def __init__(self, detail: str = "Token has expired"):
        super().__init__(detail)
        self.error_code = "TOKEN_EXPIRED"


class InvalidTokenError(AuthenticationError):
    """Invalid JWT token exception."""
    
    def __init__(self, detail: str = "Invalid token"):
        super().__init__(detail)
        self.error_code = "INVALID_TOKEN"


class GuestLimitExceededError(AuthenticationError):
    """Guest usage limit exceeded exception."""
    
    def __init__(self, detail: str = "Guest analysis limit reached. Please log in to continue."):
        super().__init__(detail)
        self.error_code = "GUEST_LIMIT_EXCEEDED"


class VideoAnalysisError(APIError):
    """Video analysis specific error."""
    
    def __init__(self, detail: str):
        super().__init__(
            detail=detail,
            status_code=422,
            error_code="VIDEO_ANALYSIS_ERROR"
        )


class TranscriptNotFoundError(NotFoundError):
    """Transcript not found exception."""
    
    def __init__(self, detail: str = "Transcript not available for this video"):
        super().__init__(detail)
        self.error_code = "TRANSCRIPT_NOT_FOUND"


class CacheError(APIError):
    """Cache operation error."""
    
    def __init__(self, detail: str):
        super().__init__(
            detail=detail,
            status_code=500,
            error_code="CACHE_ERROR"
        )


class ConfigurationError(APIError):
    """Configuration error exception."""
    
    def __init__(self, detail: str):
        super().__init__(
            detail=detail,
            status_code=500,
            error_code="CONFIGURATION_ERROR"
        )


class SupabaseError(APIError):
    """Supabase service error exception."""
    
    def __init__(self, detail: str = "Supabase service error"):
        super().__init__(
            detail=detail,
            status_code=503,
            error_code="SUPABASE_ERROR"
        )