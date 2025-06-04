"""Unit tests for JWT utilities."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, Mock
from src.youtube_analysis_api.auth.jwt_utils import (
    create_access_token,
    create_refresh_token,
    verify_token,
    extract_user_id,
    extract_user_email,
    is_token_expired,
    get_token_expiry
)
from src.youtube_analysis_api.exceptions import (
    AuthenticationError,
    TokenExpiredError,
    InvalidTokenError
)


class TestJWTTokenCreation:
    """Test JWT token creation functions."""
    
    @patch('src.youtube_analysis_api.auth.jwt_utils.get_jwt_config')
    @patch('src.youtube_analysis_api.auth.jwt_utils.jwt.encode')
    def test_create_access_token_with_default_expiry(self, mock_encode, mock_config):
        """Test creating access token with default expiry."""
        # Arrange
        mock_config.return_value = {
            "secret_key": "test-secret",
            "algorithm": "HS256",
            "access_token_expire_minutes": 30,
            "refresh_token_expire_days": 7
        }
        mock_encode.return_value = "test-access-token"
        
        test_data = {"sub": "user123", "email": "test@example.com"}
        
        # Act
        result = create_access_token(test_data)
        
        # Assert
        assert result == "test-access-token"
        mock_encode.assert_called_once()
        call_args = mock_encode.call_args
        # Check positional and keyword arguments
        assert call_args.args[1] == "test-secret"  # Second positional arg
        assert call_args.kwargs["algorithm"] == "HS256"  # Keyword arg
        
        # Check payload contains required fields
        payload = call_args.args[0]  # First positional argument
        assert payload["sub"] == "user123"
        assert payload["email"] == "test@example.com"
        assert payload["type"] == "access"
        assert "exp" in payload
    
    @patch('src.youtube_analysis_api.auth.jwt_utils.get_jwt_config')
    @patch('src.youtube_analysis_api.auth.jwt_utils.jwt.encode')
    def test_create_access_token_with_custom_expiry(self, mock_encode, mock_config):
        """Test creating access token with custom expiry."""
        # Arrange
        mock_config.return_value = {
            "secret_key": "test-secret",
            "algorithm": "HS256",
            "access_token_expire_minutes": 30,
            "refresh_token_expire_days": 7
        }
        mock_encode.return_value = "test-access-token"
        
        test_data = {"sub": "user123"}
        custom_expiry = timedelta(minutes=60)
        
        # Act
        result = create_access_token(test_data, custom_expiry)
        
        # Assert
        assert result == "test-access-token"
        mock_encode.assert_called_once()
        
        # Check that custom expiry was used
        payload = mock_encode.call_args[0][0]
        assert payload["type"] == "access"
    
    @patch('src.youtube_analysis_api.auth.jwt_utils.get_jwt_config')
    @patch('src.youtube_analysis_api.auth.jwt_utils.jwt.encode')
    def test_create_refresh_token(self, mock_encode, mock_config):
        """Test creating refresh token."""
        # Arrange
        mock_config.return_value = {
            "secret_key": "test-secret",
            "algorithm": "HS256",
            "access_token_expire_minutes": 30,
            "refresh_token_expire_days": 7
        }
        mock_encode.return_value = "test-refresh-token"
        
        test_data = {"sub": "user123"}
        
        # Act
        result = create_refresh_token(test_data)
        
        # Assert
        assert result == "test-refresh-token"
        mock_encode.assert_called_once()
        
        payload = mock_encode.call_args[0][0]
        assert payload["sub"] == "user123"
        assert payload["type"] == "refresh"
        assert "exp" in payload


class TestJWTTokenVerification:
    """Test JWT token verification functions."""
    
    @patch('src.youtube_analysis_api.auth.jwt_utils.get_jwt_config')
    @patch('src.youtube_analysis_api.auth.jwt_utils.jwt.decode')
    def test_verify_token_success(self, mock_decode, mock_config):
        """Test successful token verification."""
        # Arrange
        mock_config.return_value = {
            "secret_key": "test-secret",
            "algorithm": "HS256"
        }
        mock_payload = {
            "sub": "user123",
            "email": "test@example.com",
            "type": "access",
            "exp": 9999999999
        }
        mock_decode.return_value = mock_payload
        
        # Act
        result = verify_token("test-token")
        
        # Assert
        assert result == mock_payload
        mock_decode.assert_called_once_with(
            "test-token",
            "test-secret",
            algorithms=["HS256"]
        )
    
    @patch('src.youtube_analysis_api.auth.jwt_utils.get_jwt_config')
    @patch('src.youtube_analysis_api.auth.jwt_utils.jwt.decode')
    def test_verify_token_wrong_type(self, mock_decode, mock_config):
        """Test token verification with wrong token type."""
        # Arrange
        mock_config.return_value = {
            "secret_key": "test-secret",
            "algorithm": "HS256"
        }
        mock_payload = {
            "sub": "user123",
            "type": "refresh",
            "exp": 9999999999
        }
        mock_decode.return_value = mock_payload
        
        # Act & Assert
        with pytest.raises(AuthenticationError, match="Token verification failed"):
            verify_token("test-token", token_type="access")
    
    @patch('src.youtube_analysis_api.auth.jwt_utils.get_jwt_config')
    @patch('src.youtube_analysis_api.auth.jwt_utils.jwt.decode')
    def test_verify_token_expired(self, mock_decode, mock_config):
        """Test token verification with expired token."""
        # Arrange
        mock_config.return_value = {
            "secret_key": "test-secret",
            "algorithm": "HS256"
        }
        import jwt
        mock_decode.side_effect = jwt.ExpiredSignatureError("Token expired")
        
        # Act & Assert
        with pytest.raises(TokenExpiredError, match="Token has expired"):
            verify_token("expired-token")
    
    @patch('src.youtube_analysis_api.auth.jwt_utils.get_jwt_config')
    @patch('src.youtube_analysis_api.auth.jwt_utils.jwt.decode')
    def test_verify_token_invalid(self, mock_decode, mock_config):
        """Test token verification with invalid token."""
        # Arrange
        mock_config.return_value = {
            "secret_key": "test-secret",
            "algorithm": "HS256"
        }
        import jwt
        mock_decode.side_effect = jwt.InvalidTokenError("Invalid token")
        
        # Act & Assert
        with pytest.raises(InvalidTokenError, match="Invalid token"):
            verify_token("invalid-token")


class TestJWTUtilityFunctions:
    """Test JWT utility functions."""
    
    @patch('src.youtube_analysis_api.auth.jwt_utils.verify_token')
    def test_extract_user_id_success(self, mock_verify):
        """Test successful user ID extraction."""
        # Arrange
        mock_verify.return_value = {"sub": "user123", "email": "test@example.com"}
        
        # Act
        result = extract_user_id("test-token")
        
        # Assert
        assert result == "user123"
        mock_verify.assert_called_once_with("test-token")
    
    @patch('src.youtube_analysis_api.auth.jwt_utils.verify_token')
    def test_extract_user_id_missing(self, mock_verify):
        """Test user ID extraction when user ID is missing."""
        # Arrange
        mock_verify.return_value = {"email": "test@example.com"}
        
        # Act & Assert
        with pytest.raises(AuthenticationError, match="User ID not found in token"):
            extract_user_id("test-token")
    
    @patch('src.youtube_analysis_api.auth.jwt_utils.verify_token')
    def test_extract_user_email_success(self, mock_verify):
        """Test successful user email extraction."""
        # Arrange
        mock_verify.return_value = {"sub": "user123", "email": "test@example.com"}
        
        # Act
        result = extract_user_email("test-token")
        
        # Assert
        assert result == "test@example.com"
    
    @patch('src.youtube_analysis_api.auth.jwt_utils.verify_token')
    def test_extract_user_email_missing(self, mock_verify):
        """Test user email extraction when email is missing."""
        # Arrange
        mock_verify.return_value = {"sub": "user123"}
        
        # Act
        result = extract_user_email("test-token")
        
        # Assert
        assert result is None
    
    @patch('src.youtube_analysis_api.auth.jwt_utils.verify_token')
    def test_extract_user_email_invalid_token(self, mock_verify):
        """Test user email extraction with invalid token."""
        # Arrange
        mock_verify.side_effect = InvalidTokenError("Invalid token")
        
        # Act
        result = extract_user_email("invalid-token")
        
        # Assert
        assert result is None
    
    @patch('src.youtube_analysis_api.auth.jwt_utils.verify_token')
    def test_is_token_expired_false(self, mock_verify):
        """Test token expiry check for valid token."""
        # Arrange
        mock_verify.return_value = {"sub": "user123", "exp": 9999999999}
        
        # Act
        result = is_token_expired("valid-token")
        
        # Assert
        assert result is False
    
    @patch('src.youtube_analysis_api.auth.jwt_utils.verify_token')
    def test_is_token_expired_true(self, mock_verify):
        """Test token expiry check for expired token."""
        # Arrange
        mock_verify.side_effect = TokenExpiredError("Token expired")
        
        # Act
        result = is_token_expired("expired-token")
        
        # Assert
        assert result is True
    
    @patch('src.youtube_analysis_api.auth.jwt_utils.verify_token')
    def test_get_token_expiry_success(self, mock_verify):
        """Test getting token expiry time."""
        # Arrange
        exp_timestamp = 1640995200  # 2022-01-01 00:00:00 UTC
        mock_verify.return_value = {"sub": "user123", "exp": exp_timestamp}
        
        # Act
        result = get_token_expiry("test-token")
        
        # Assert
        assert result == datetime.fromtimestamp(exp_timestamp)
    
    @patch('src.youtube_analysis_api.auth.jwt_utils.verify_token')
    def test_get_token_expiry_missing(self, mock_verify):
        """Test getting token expiry when exp field is missing."""
        # Arrange
        mock_verify.return_value = {"sub": "user123"}
        
        # Act
        result = get_token_expiry("test-token")
        
        # Assert
        assert result is None
    
    @patch('src.youtube_analysis_api.auth.jwt_utils.verify_token')
    def test_get_token_expiry_invalid_token(self, mock_verify):
        """Test getting token expiry for invalid token."""
        # Arrange
        mock_verify.side_effect = InvalidTokenError("Invalid token")
        
        # Act
        result = get_token_expiry("invalid-token")
        
        # Assert
        assert result is None


class TestJWTConfig:
    """Test JWT configuration."""
    
    @patch('src.youtube_analysis_api.auth.jwt_utils.get_api_config')
    def test_get_jwt_config(self, mock_get_api_config):
        """Test JWT configuration retrieval."""
        # Arrange
        mock_config = Mock()
        mock_config.jwt_secret_key = "test-secret"
        mock_config.jwt_algorithm = "HS256"
        mock_config.jwt_access_token_expire_minutes = 30
        mock_config.jwt_refresh_token_expire_days = 7
        mock_get_api_config.return_value = mock_config
        
        # Act
        from src.youtube_analysis_api.auth.jwt_utils import get_jwt_config
        result = get_jwt_config()
        
        # Assert
        expected = {
            "secret_key": "test-secret",
            "algorithm": "HS256",
            "access_token_expire_minutes": 30,
            "refresh_token_expire_days": 7
        }
        assert result == expected