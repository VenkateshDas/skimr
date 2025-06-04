"""Mock services for testing external dependencies."""

from typing import Dict, Any, Optional
from unittest.mock import AsyncMock, Mock


class MockSupabaseClient:
    """Mock Supabase client for testing."""
    
    def __init__(self):
        self.verify_token_calls = []
        self.get_user_profile_calls = []
        self.update_user_profile_calls = []
        self.check_user_exists_calls = []
        self.get_user_metadata_calls = []
        
        # Default return values
        self.user_data = {
            "id": "test-user-id-123",
            "email": "test@example.com",
            "user_metadata": {
                "full_name": "Test User",
                "avatar_url": "https://example.com/avatar.jpg"
            },
            "app_metadata": {},
            "created_at": "2023-01-01T00:00:00Z",
            "updated_at": "2023-01-01T00:00:00Z",
            "aud": "authenticated"
        }
        
        self.profile_data = {
            "id": "test-user-id-123",
            "email": "test@example.com",
            "metadata": {
                "full_name": "Test User",
                "avatar_url": "https://example.com/avatar.jpg"
            }
        }
    
    async def verify_token(self, token: str) -> Dict[str, Any]:
        """Mock verify_token method."""
        self.verify_token_calls.append(token)
        if token == "invalid-token":
            from src.youtube_analysis_api.exceptions import AuthenticationError
            raise AuthenticationError("Invalid token")
        if token == "expired-token":
            from src.youtube_analysis_api.exceptions import TokenExpiredError
            raise TokenExpiredError("Token expired")
        return self.user_data
    
    async def get_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Mock get_user_profile method."""
        self.get_user_profile_calls.append(user_id)
        if user_id == "nonexistent-user":
            return None
        return self.profile_data
    
    async def update_user_profile(self, user_id: str, profile_data: Dict[str, Any]) -> bool:
        """Mock update_user_profile method."""
        self.update_user_profile_calls.append({"user_id": user_id, "profile_data": profile_data})
        return user_id != "update-fail-user"
    
    async def check_user_exists(self, user_id: str) -> bool:
        """Mock check_user_exists method."""
        self.check_user_exists_calls.append(user_id)
        return user_id != "nonexistent-user"
    
    async def get_user_metadata(self, user_id: str) -> Dict[str, Any]:
        """Mock get_user_metadata method."""
        self.get_user_metadata_calls.append(user_id)
        if user_id == "nonexistent-user":
            return {}
        return self.profile_data.get("metadata", {})
    
    def set_user_data(self, user_data: Dict[str, Any]):
        """Set user data for testing."""
        self.user_data = user_data
    
    def set_profile_data(self, profile_data: Dict[str, Any]):
        """Set profile data for testing."""
        self.profile_data = profile_data
    
    def reset_calls(self):
        """Reset all call tracking."""
        self.verify_token_calls = []
        self.get_user_profile_calls = []
        self.update_user_profile_calls = []
        self.check_user_exists_calls = []
        self.get_user_metadata_calls = []


class MockServiceFactory:
    """Mock ServiceFactory for testing."""
    
    def __init__(self, webapp_adapter=None):
        self.webapp_adapter = webapp_adapter or Mock()
        self.get_web_app_adapter_calls = []
    
    def get_web_app_adapter(self):
        """Mock get_web_app_adapter method."""
        self.get_web_app_adapter_calls.append(True)
        return self.webapp_adapter
    
    def set_webapp_adapter(self, adapter):
        """Set the webapp adapter for testing."""
        self.webapp_adapter = adapter
    
    def reset_calls(self):
        """Reset call tracking."""
        self.get_web_app_adapter_calls = []


class MockJWTUtils:
    """Mock JWT utilities for testing."""
    
    def __init__(self):
        self.create_access_token_calls = []
        self.create_refresh_token_calls = []
        self.verify_token_calls = []
        self.extract_user_id_calls = []
        
        # Default token values
        self.access_token = "mock-access-token"
        self.refresh_token = "mock-refresh-token"
        self.token_payload = {
            "sub": "test-user-id-123",
            "email": "test@example.com",
            "aud": "authenticated",
            "type": "access",
            "exp": 9999999999
        }
    
    def create_access_token(self, data: Dict[str, Any], expires_delta=None) -> str:
        """Mock create_access_token."""
        self.create_access_token_calls.append({"data": data, "expires_delta": expires_delta})
        return self.access_token
    
    def create_refresh_token(self, data: Dict[str, Any]) -> str:
        """Mock create_refresh_token."""
        self.create_refresh_token_calls.append(data)
        return self.refresh_token
    
    def verify_token(self, token: str, token_type: str = "access") -> Dict[str, Any]:
        """Mock verify_token."""
        self.verify_token_calls.append({"token": token, "token_type": token_type})
        if token == "invalid-token":
            from src.youtube_analysis_api.exceptions import InvalidTokenError
            raise InvalidTokenError("Invalid token")
        if token == "expired-token":
            from src.youtube_analysis_api.exceptions import TokenExpiredError
            raise TokenExpiredError("Token expired")
        
        payload = self.token_payload.copy()
        payload["type"] = token_type
        return payload
    
    def extract_user_id(self, token: str) -> str:
        """Mock extract_user_id."""
        self.extract_user_id_calls.append(token)
        if token == "invalid-token":
            from src.youtube_analysis_api.exceptions import AuthenticationError
            raise AuthenticationError("Invalid token")
        return self.token_payload["sub"]
    
    def set_token_payload(self, payload: Dict[str, Any]):
        """Set token payload for testing."""
        self.token_payload = payload
    
    def reset_calls(self):
        """Reset all call tracking."""
        self.create_access_token_calls = []
        self.create_refresh_token_calls = []
        self.verify_token_calls = []
        self.extract_user_id_calls = []


def create_mock_supabase_client() -> MockSupabaseClient:
    """Factory function to create a mock Supabase client."""
    return MockSupabaseClient()


def create_mock_service_factory(webapp_adapter=None) -> MockServiceFactory:
    """Factory function to create a mock ServiceFactory."""
    return MockServiceFactory(webapp_adapter)


def create_mock_jwt_utils() -> MockJWTUtils:
    """Factory function to create mock JWT utilities."""
    return MockJWTUtils()