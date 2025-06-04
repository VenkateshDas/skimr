"""Integration tests for authentication endpoints."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient

from src.youtube_analysis_api.app import create_app
from src.youtube_analysis_api.api.models.auth import (
    LoginRequest,
    LoginResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
    UserProfileResponse
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
def mock_supabase_client():
    """Mock Supabase client."""
    mock = MagicMock()
    mock.verify_token = AsyncMock()
    mock.get_user_profile = AsyncMock()
    mock.update_user_profile = AsyncMock()
    return mock


@pytest.fixture
def test_user_data():
    """Test user data."""
    return {
        "id": "test-user-id",
        "email": "test@example.com",
        "user_metadata": {
            "full_name": "Test User",
            "avatar_url": "https://example.com/avatar.jpg"
        },
        "app_metadata": {},
        "created_at": "2023-01-01T00:00:00Z",
        "updated_at": "2023-01-01T00:00:00Z"
    }


@pytest.fixture
def test_tokens():
    """Test JWT tokens."""
    return {
        "access_token": "test-access-token",
        "refresh_token": "test-refresh-token",
        "token_type": "bearer"
    }


class TestAuthEndpoints:
    """Test authentication endpoints."""
    
    @patch("src.youtube_analysis_api.auth.supabase_client.get_supabase_client")
    @patch("src.youtube_analysis_api.api.routers.auth.create_access_token")
    @patch("src.youtube_analysis_api.api.routers.auth.create_refresh_token")
    def test_login_success(self, mock_create_refresh, mock_create_access, mock_get_client, 
                          client, mock_supabase_client, test_user_data, test_tokens):
        """Test successful login endpoint."""
        # Arrange
        mock_get_client.return_value = mock_supabase_client
        mock_supabase_client.verify_token.return_value = test_user_data
        mock_create_access.return_value = test_tokens["access_token"]
        mock_create_refresh.return_value = test_tokens["refresh_token"]
        
        login_request = {
            "supabase_token": "supabase-token-123"
        }
        
        # Act
        response = client.post("/api/v1/auth/login", json=login_request)
        
        # Assert
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["success"] is True
        assert response_data["user"]["id"] == test_user_data["id"]
        assert response_data["user"]["email"] == test_user_data["email"]
        assert response_data["access_token"] == test_tokens["access_token"]
        assert response_data["refresh_token"] == test_tokens["refresh_token"]
        
        # Verify Supabase client was called correctly
        mock_supabase_client.verify_token.assert_called_once_with("supabase-token-123")
    
    @patch("src.youtube_analysis_api.auth.supabase_client.get_supabase_client")
    def test_login_invalid_token(self, mock_get_client, client, mock_supabase_client):
        """Test login with invalid token."""
        # Arrange
        mock_get_client.return_value = mock_supabase_client
        mock_supabase_client.verify_token.return_value = None  # Invalid token
        
        login_request = {
            "supabase_token": "invalid-token"
        }
        
        # Act
        response = client.post("/api/v1/auth/login", json=login_request)
        
        # Assert
        assert response.status_code == 401
        response_data = response.json()
        assert response_data["success"] is False
        assert "error" in response_data
        assert "Invalid token" in response_data["error"]["message"]
    
    @patch("src.youtube_analysis_api.auth.jwt_utils.verify_token")
    @patch("src.youtube_analysis_api.api.routers.auth.create_access_token")
    def test_refresh_token_success(self, mock_create_access, mock_verify_token, 
                                 client, test_user_data, test_tokens):
        """Test successful token refresh."""
        # Arrange
        mock_verify_token.return_value = {"sub": test_user_data["id"], "type": "refresh"}
        mock_create_access.return_value = "new-access-token"
        
        refresh_request = {
            "refresh_token": test_tokens["refresh_token"]
        }
        
        # Act
        response = client.post("/api/v1/auth/refresh", json=refresh_request)
        
        # Assert
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["success"] is True
        assert response_data["access_token"] == "new-access-token"
        assert response_data["token_type"] == "bearer"
        
        # Verify token verification
        mock_verify_token.assert_called_once_with(
            test_tokens["refresh_token"], 
            token_type="refresh"
        )
    
    @patch("src.youtube_analysis_api.auth.jwt_utils.verify_token")
    def test_refresh_token_invalid(self, mock_verify_token, client):
        """Test token refresh with invalid token."""
        # Arrange
        from src.youtube_analysis_api.exceptions import InvalidTokenError
        mock_verify_token.side_effect = InvalidTokenError("Token invalid")
        
        refresh_request = {
            "refresh_token": "invalid-refresh-token"
        }
        
        # Act
        response = client.post("/api/v1/auth/refresh", json=refresh_request)
        
        # Assert
        assert response.status_code == 401
        response_data = response.json()
        assert response_data["success"] is False
        assert "error" in response_data
        assert "Token invalid" in response_data["error"]["message"]
    
    @patch("src.youtube_analysis_api.auth.jwt_utils.verify_token")
    @patch("src.youtube_analysis_api.auth.supabase_client.get_supabase_client")
    def test_get_profile_success(self, mock_get_client, mock_verify_token, 
                              client, mock_supabase_client, test_user_data, test_tokens):
        """Test successful profile retrieval."""
        # Arrange
        mock_verify_token.return_value = {"sub": test_user_data["id"], "type": "access"}
        mock_get_client.return_value = mock_supabase_client
        mock_supabase_client.get_user_profile.return_value = test_user_data
        
        # Act
        response = client.get(
            "/api/v1/auth/profile",
            headers={"Authorization": f"Bearer {test_tokens['access_token']}"}
        )
        
        # Assert
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["success"] is True
        assert response_data["profile"]["id"] == test_user_data["id"]
        assert response_data["profile"]["email"] == test_user_data["email"]
        assert response_data["profile"]["full_name"] == test_user_data["user_metadata"]["full_name"]
    
    def test_get_profile_no_token(self, client):
        """Test profile retrieval without token."""
        # Act
        response = client.get("/api/v1/auth/profile")
        
        # Assert
        assert response.status_code == 401
        response_data = response.json()
        assert response_data["success"] is False
        assert "error" in response_data
        assert "Not authenticated" in response_data["error"]["message"]
    
    @patch("src.youtube_analysis_api.auth.jwt_utils.verify_token")
    @patch("src.youtube_analysis_api.auth.supabase_client.get_supabase_client")
    def test_update_profile_success(self, mock_get_client, mock_verify_token, 
                                 client, mock_supabase_client, test_user_data, test_tokens):
        """Test successful profile update."""
        # Arrange
        mock_verify_token.return_value = {"sub": test_user_data["id"], "type": "access"}
        mock_get_client.return_value = mock_supabase_client
        
        # Updated user data
        updated_user_data = test_user_data.copy()
        updated_user_data["user_metadata"]["full_name"] = "Updated User Name"
        mock_supabase_client.update_user_profile.return_value = updated_user_data
        
        update_request = {
            "full_name": "Updated User Name"
        }
        
        # Act
        response = client.post(
            "/api/v1/auth/profile",
            json=update_request,
            headers={"Authorization": f"Bearer {test_tokens['access_token']}"}
        )
        
        # Assert
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["success"] is True
        assert response_data["profile"]["full_name"] == "Updated User Name"
        
        # Verify Supabase client was called correctly
        mock_supabase_client.update_user_profile.assert_called_once_with(
            test_user_data["id"],
            {"full_name": "Updated User Name"}
        )
    
    def test_guest_login_success(self, client):
        """Test successful guest login."""
        # Act
        response = client.post("/api/v1/auth/guest")
        
        # Assert
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["success"] is True
        assert "access_token" in response_data
        assert "token_type" in response_data
        assert response_data["user"]["is_guest"] is True 