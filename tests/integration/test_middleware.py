"""Integration tests for FastAPI middleware."""

import pytest
import json
import logging
from unittest.mock import patch, MagicMock
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.testclient import TestClient
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from src.youtube_analysis_api.app import create_app
from src.youtube_analysis_api.middleware import (
    setup_middleware,
    LoggingMiddleware,
    AuthenticationMiddleware,
    RateLimitingMiddleware,
    ErrorHandlingMiddleware
)
from src.youtube_analysis_api.exceptions import (
    AuthenticationError, 
    RateLimitExceededError,
    ValidationError
)


@pytest.fixture
def app():
    """Create FastAPI app for testing."""
    return create_app()


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def test_tokens():
    """Test JWT tokens."""
    return {
        "access_token": "test-access-token",
        "refresh_token": "test-refresh-token"
    }


class TestCORSMiddleware:
    """Test CORS middleware configuration."""
    
    def test_cors_headers_allowed_origin(self, client):
        """Test CORS headers for allowed origin."""
        # Act
        response = client.options(
            "/api/v1/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET"
            }
        )
        
        # Assert
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers
        assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
        assert "access-control-allow-credentials" in response.headers
        assert response.headers["access-control-allow-credentials"] == "true"
    
    def test_cors_headers_disallowed_origin(self, client):
        """Test CORS headers for disallowed origin in production."""
        # In test mode, all origins are allowed, so we need to patch the config
        with patch("src.youtube_analysis_api.config.APIConfig.environment", "production"), \
             patch("src.youtube_analysis_api.config.APIConfig.cors_origins", ["http://allowed-origin.com"]):
            
            # Act
            response = client.options(
                "/api/v1/health",
                headers={
                    "Origin": "http://disallowed-origin.com",
                    "Access-Control-Request-Method": "GET"
                }
            )
            
            # Assert
            assert response.status_code == 200
            # In our implementation, FastAPI's CORS middleware still responds with 200
            # but doesn't include the CORS headers for disallowed origins
            assert "access-control-allow-origin" not in response.headers


class TestAuthenticationMiddleware:
    """Test authentication middleware."""
    
    @patch("src.youtube_analysis_api.auth.jwt_utils.verify_token")
    def test_valid_auth_token(self, mock_verify_token, client, test_tokens):
        """Test valid authentication token."""
        # Arrange
        user_id = "test-user-id"
        mock_verify_token.return_value = {
            "sub": user_id,
            "email": "test@example.com",
            "type": "access"
        }
        
        # Act
        response = client.get(
            "/api/v1/auth/profile",
            headers={"Authorization": f"Bearer {test_tokens['access_token']}"}
        )
        
        # Assert
        assert response.status_code != 401  # Not unauthorized
        mock_verify_token.assert_called_once_with(test_tokens["access_token"], token_type="access")
    
    def test_missing_auth_token(self, client):
        """Test missing authentication token."""
        # Act
        response = client.get("/api/v1/auth/profile")
        
        # Assert
        assert response.status_code == 401
        response_data = response.json()
        assert response_data["success"] is False
        assert "error" in response_data
        assert "Not authenticated" in response_data["error"]["message"]
    
    def test_invalid_auth_scheme(self, client):
        """Test invalid authentication scheme."""
        # Act
        response = client.get(
            "/api/v1/auth/profile",
            headers={"Authorization": "InvalidScheme token123"}
        )
        
        # Assert
        assert response.status_code == 401
        response_data = response.json()
        assert response_data["success"] is False
        assert "error" in response_data
        assert "Bearer" in response_data["error"]["message"]
    
    @patch("src.youtube_analysis_api.auth.jwt_utils.verify_token")
    def test_invalid_auth_token(self, mock_verify_token, client, test_tokens):
        """Test invalid authentication token."""
        # Arrange
        from src.youtube_analysis_api.exceptions import InvalidTokenError
        mock_verify_token.side_effect = InvalidTokenError("Invalid token")
        
        # Act
        response = client.get(
            "/api/v1/auth/profile",
            headers={"Authorization": f"Bearer {test_tokens['access_token']}"}
        )
        
        # Assert
        assert response.status_code == 401
        response_data = response.json()
        assert response_data["success"] is False
        assert "error" in response_data
        assert "Invalid token" in response_data["error"]["message"]
    
    @patch("src.youtube_analysis_api.auth.jwt_utils.verify_token")
    def test_expired_auth_token(self, mock_verify_token, client, test_tokens):
        """Test expired authentication token."""
        # Arrange
        from src.youtube_analysis_api.exceptions import TokenExpiredError
        mock_verify_token.side_effect = TokenExpiredError("Token has expired")
        
        # Act
        response = client.get(
            "/api/v1/auth/profile",
            headers={"Authorization": f"Bearer {test_tokens['access_token']}"}
        )
        
        # Assert
        assert response.status_code == 401
        response_data = response.json()
        assert response_data["success"] is False
        assert "error" in response_data
        assert "expired" in response_data["error"]["message"].lower()
    
    def test_public_endpoint_no_auth(self, client):
        """Test public endpoints don't require authentication."""
        # Act
        response = client.get("/health")
        
        # Assert
        assert response.status_code == 200  # Public endpoint should be accessible
        response_data = response.json()
        assert response_data["status"] == "healthy"


class TestRateLimitingMiddleware:
    """Test rate limiting middleware."""
    
    @patch("src.youtube_analysis_api.middleware.get_user_context")
    def test_guest_user_under_limit(self, mock_get_user_context, client):
        """Test guest user under rate limit."""
        # Arrange
        mock_get_user_context.return_value = {
            "is_guest": True,
            "user_id": None,
            "daily_limit": 3,
            "remaining_requests": 2
        }
        
        # Act
        response = client.get("/api/v1/health")
        
        # Assert
        assert response.status_code == 200  # Request should proceed
        assert "X-Rate-Limit-Remaining" in response.headers
        assert response.headers["X-Rate-Limit-Remaining"] == "1"  # Decremented by 1
    
    @patch("src.youtube_analysis_api.middleware.get_user_context")
    def test_guest_user_at_limit(self, mock_get_user_context, client):
        """Test guest user at rate limit."""
        # Arrange
        mock_get_user_context.return_value = {
            "is_guest": True,
            "user_id": None,
            "daily_limit": 3,
            "remaining_requests": 0
        }
        
        # Act
        response = client.post("/api/v1/video/analyze", json={"youtube_url": "https://youtube.com/watch?v=test"})
        
        # Assert
        assert response.status_code == 429  # Too Many Requests
        response_data = response.json()
        assert response_data["success"] is False
        assert "error" in response_data
        assert "rate limit" in response_data["error"]["message"].lower()
    
    @patch("src.youtube_analysis_api.middleware.get_user_context")
    def test_authenticated_user_no_limit(self, mock_get_user_context, client):
        """Test authenticated user has no rate limit."""
        # Arrange
        mock_get_user_context.return_value = {
            "is_guest": False,
            "user_id": "test-user-id",
            "email": "test@example.com",
            "daily_limit": None,
            "remaining_requests": None
        }
        
        # Act
        response = client.get("/api/v1/health")
        
        # Assert
        assert response.status_code == 200  # Request should proceed
        assert "X-Rate-Limit-Remaining" not in response.headers  # No rate limit headers for auth users


class TestErrorHandlingMiddleware:
    """Test error handling middleware."""
    
    @patch("src.youtube_analysis_api.middleware.LoggingMiddleware.dispatch")
    async def test_handle_authentication_error(self, mock_dispatch):
        """Test handling authentication error."""
        # Arrange
        app = FastAPI()
        middleware = ErrorHandlingMiddleware()
        
        # Mock request
        request = Request({"type": "http", "method": "GET", "path": "/test"})
        
        # Mock exception during request processing
        mock_dispatch.side_effect = AuthenticationError("Authentication failed")
        
        # Act
        response = await middleware.dispatch(request, mock_dispatch)
        
        # Assert
        assert response.status_code == 401
        response_data = json.loads(response.body.decode())
        assert response_data["success"] is False
        assert response_data["error"]["message"] == "Authentication failed"
        assert response_data["error"]["code"] == "AUTHENTICATION_ERROR"
    
    @patch("src.youtube_analysis_api.middleware.LoggingMiddleware.dispatch")
    async def test_handle_rate_limit_error(self, mock_dispatch):
        """Test handling rate limit error."""
        # Arrange
        app = FastAPI()
        middleware = ErrorHandlingMiddleware()
        
        # Mock request
        request = Request({"type": "http", "method": "GET", "path": "/test"})
        
        # Mock exception during request processing
        mock_dispatch.side_effect = RateLimitExceededError("Rate limit exceeded")
        
        # Act
        response = await middleware.dispatch(request, mock_dispatch)
        
        # Assert
        assert response.status_code == 429
        response_data = json.loads(response.body.decode())
        assert response_data["success"] is False
        assert response_data["error"]["message"] == "Rate limit exceeded"
        assert response_data["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    
    @patch("src.youtube_analysis_api.middleware.LoggingMiddleware.dispatch")
    async def test_handle_validation_error(self, mock_dispatch):
        """Test handling validation error."""
        # Arrange
        app = FastAPI()
        middleware = ErrorHandlingMiddleware()
        
        # Mock request
        request = Request({"type": "http", "method": "GET", "path": "/test"})
        
        # Mock exception during request processing
        mock_dispatch.side_effect = ValidationError("Invalid input")
        
        # Act
        response = await middleware.dispatch(request, mock_dispatch)
        
        # Assert
        assert response.status_code == 400
        response_data = json.loads(response.body.decode())
        assert response_data["success"] is False
        assert response_data["error"]["message"] == "Invalid input"
        assert response_data["error"]["code"] == "VALIDATION_ERROR"
    
    @patch("src.youtube_analysis_api.middleware.LoggingMiddleware.dispatch")
    async def test_handle_http_exception(self, mock_dispatch):
        """Test handling HTTP exception."""
        # Arrange
        app = FastAPI()
        middleware = ErrorHandlingMiddleware()
        
        # Mock request
        request = Request({"type": "http", "method": "GET", "path": "/test"})
        
        # Mock exception during request processing
        mock_dispatch.side_effect = HTTPException(status_code=404, detail="Not found")
        
        # Act
        response = await middleware.dispatch(request, mock_dispatch)
        
        # Assert
        assert response.status_code == 404
        response_data = json.loads(response.body.decode())
        assert response_data["success"] is False
        assert response_data["error"]["message"] == "Not found"
        assert response_data["error"]["code"] == "HTTP_ERROR"


class TestLoggingMiddleware:
    """Test logging middleware."""
    
    @patch("src.youtube_analysis_api.middleware.logger")
    def test_request_logging(self, mock_logger, client):
        """Test request logging."""
        # Act
        response = client.get(
            "/api/v1/health",
            headers={"X-Request-ID": "test-request-id"}
        )
        
        # Assert
        assert response.status_code == 200
        
        # Verify logger was called for the request
        mock_logger.info.assert_any_call(
            "Incoming request", 
            extra={"request_id": "test-request-id", "path": "/api/v1/health", "method": "GET"}
        )
    
    @patch("src.youtube_analysis_api.middleware.logger")
    def test_response_logging(self, mock_logger, client):
        """Test response logging."""
        # Act
        response = client.get(
            "/api/v1/health",
            headers={"X-Request-ID": "test-request-id"}
        )
        
        # Assert
        assert response.status_code == 200
        
        # Verify logger was called for the response
        mock_logger.info.assert_any_call(
            "Request completed", 
            extra={"request_id": "test-request-id", "status_code": 200}
        )
    
    @patch("src.youtube_analysis_api.middleware.logger")
    def test_error_logging(self, mock_logger, client):
        """Test error logging."""
        # Act
        response = client.get("/non-existent-endpoint")
        
        # Assert
        assert response.status_code == 404
        
        # Verify logger was called for the error
        mock_logger.error.assert_any_call(
            "Request error", 
            extra={"status_code": 404, "path": "/non-existent-endpoint"}
        )
    
    def test_request_id_generation(self, client):
        """Test request ID generation when not provided."""
        # Act
        response = client.get("/api/v1/health")
        
        # Assert
        assert response.status_code == 200
        assert "X-Request-ID" in response.headers
        assert response.headers["X-Request-ID"] is not None
        assert len(response.headers["X-Request-ID"]) > 0
    
    def test_request_id_propagation(self, client):
        """Test request ID propagation when provided."""
        # Arrange
        request_id = "test-request-id-123"
        
        # Act
        response = client.get(
            "/api/v1/health",
            headers={"X-Request-ID": request_id}
        )
        
        # Assert
        assert response.status_code == 200
        assert "X-Request-ID" in response.headers
        assert response.headers["X-Request-ID"] == request_id 