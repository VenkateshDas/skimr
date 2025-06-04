"""Pytest configuration and fixtures for FastAPI backend tests."""

import os
import sys
import pytest
import asyncio
from typing import Dict, Any, Generator
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

# Add the project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Set test environment variables before importing app
os.environ["API_SECRET_KEY"] = "test-secret-key-for-testing-only"
os.environ["SUPABASE_URL"] = "https://test.supabase.co"
os.environ["SUPABASE_ANON_KEY"] = "test-anon-key"
os.environ["API_DEBUG"] = "true"
os.environ["ENVIRONMENT"] = "test"

from src.youtube_analysis_api.app import create_app
from src.youtube_analysis_api.config import get_api_config


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def api_config():
    """Get test API configuration."""
    return get_api_config()


@pytest.fixture
def mock_supabase_client():
    """Mock Supabase client for testing."""
    mock_client = Mock()
    mock_client.verify_token = AsyncMock()
    mock_client.get_user_profile = AsyncMock()
    mock_client.update_user_profile = AsyncMock()
    mock_client.check_user_exists = AsyncMock()
    mock_client.get_user_metadata = AsyncMock()
    return mock_client


@pytest.fixture
def mock_webapp_adapter():
    """Mock WebAppAdapter for testing."""
    mock_adapter = Mock()
    mock_adapter.analyze_video = Mock()
    mock_adapter.generate_content = Mock()
    mock_adapter.get_transcript = Mock()
    mock_adapter.chat_with_video = Mock()
    mock_adapter.validate_youtube_url = Mock()
    mock_adapter.get_video_info = Mock()
    return mock_adapter


@pytest.fixture
def mock_service_factory():
    """Mock ServiceFactory for testing."""
    mock_factory = Mock()
    mock_factory.get_web_app_adapter = Mock()
    return mock_factory


@pytest.fixture
def test_user_data():
    """Test user data for authentication tests."""
    return {
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


@pytest.fixture
def test_jwt_token():
    """Test JWT token for authentication."""
    return "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ0ZXN0LXVzZXItaWQtMTIzIiwiZW1haWwiOiJ0ZXN0QGV4YW1wbGUuY29tIiwiYXVkIjoiYXV0aGVudGljYXRlZCIsInR5cGUiOiJhY2Nlc3MiLCJleHAiOjk5OTk5OTk5OTl9"


@pytest.fixture
def test_refresh_token():
    """Test refresh token for authentication."""
    return "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ0ZXN0LXVzZXItaWQtMTIzIiwidHlwZSI6InJlZnJlc2giLCJleHAiOjk5OTk5OTk5OTl9"


@pytest.fixture
def test_video_data():
    """Test video data for video analysis tests."""
    return {
        "video_id": "dQw4w9WgXcQ",
        "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "video_info": {
            "video_id": "dQw4w9WgXcQ",
            "title": "Test Video Title",
            "description": "Test video description",
            "duration": 212,
            "view_count": 1000000,
            "channel_name": "Test Channel",
            "thumbnail_url": "https://img.youtube.com/vi/dQw4w9WgXcQ/maxresdefault.jpg"
        },
        "task_outputs": {
            "summary": {
                "task_name": "summary",
                "content": "Test video summary",
                "token_usage": {"prompt_tokens": 100, "completion_tokens": 50},
                "execution_time": 2.5,
                "status": "completed"
            }
        },
        "total_token_usage": {"prompt_tokens": 100, "completion_tokens": 50},
        "analysis_time": 5.2,
        "cached": False,
        "chat_details": {"session_id": "test-session-123"}
    }


@pytest.fixture
def auth_headers(test_jwt_token):
    """Authentication headers for testing."""
    return {"Authorization": f"Bearer {test_jwt_token}"}


@pytest.fixture
def guest_user_context():
    """Guest user context for testing."""
    return {
        "is_guest": True,
        "user_id": None,
        "email": None,
        "daily_limit": 1,
        "remaining_requests": 1
    }


@pytest.fixture
def authenticated_user_context():
    """Authenticated user context for testing."""
    return {
        "is_guest": False,
        "user_id": "test-user-id-123",
        "email": "test@example.com",
        "daily_limit": None,
        "remaining_requests": None
    }


@pytest.fixture
def app():
    """Create FastAPI test application."""
    return create_app()


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def async_client(app):
    """Create async test client."""
    from httpx import AsyncClient
    return AsyncClient(app=app, base_url="http://test")


# Mock patches for external dependencies
@pytest.fixture(autouse=True)
def mock_external_dependencies(mock_supabase_client, mock_webapp_adapter, mock_service_factory):
    """Auto-use fixture to mock external dependencies."""
    with patch('src.youtube_analysis_api.auth.supabase_client.get_supabase_client', return_value=mock_supabase_client), \
         patch('src.youtube_analysis_api.dependencies.get_service_factory', return_value=mock_service_factory), \
         patch('src.youtube_analysis_api.dependencies.get_web_app_adapter', return_value=mock_webapp_adapter):
        mock_service_factory.get_web_app_adapter.return_value = mock_webapp_adapter
        yield


# Test data generators
def generate_test_analysis_request(**overrides):
    """Generate test analysis request data."""
    default_data = {
        "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "analysis_types": ["Summary & Classification"],
        "use_cache": True,
        "custom_instruction": ""
    }
    default_data.update(overrides)
    return default_data


def generate_test_login_request(**overrides):
    """Generate test login request data."""
    default_data = {
        "supabase_token": "test-supabase-token"
    }
    default_data.update(overrides)
    return default_data


def generate_test_content_request(**overrides):
    """Generate test content generation request data."""
    default_data = {
        "video_id": "dQw4w9WgXcQ",
        "content_type": "blog_post",
        "custom_instruction": ""
    }
    default_data.update(overrides)
    return default_data


# Mock API config for testing
@pytest.fixture(autouse=True)
def mock_api_config():
    """Mock APIConfig to prevent hardcoded values."""
    with patch('src.youtube_analysis_api.config.APIConfig.secret_key', new_callable=lambda: os.environ.get('API_SECRET_KEY', '')), \
         patch('src.youtube_analysis_api.config.APIConfig.debug', new_callable=lambda: os.environ.get('API_DEBUG', 'false').lower() == 'true'), \
         patch('src.youtube_analysis_api.config.APIConfig.__post_init__') as mock_post_init:
        
        def custom_post_init(self):
            origins_str = os.environ.get('API_CORS_ORIGINS', '')
            if origins_str:
                self.cors_origins = [origin.strip() for origin in origins_str.split(',') if origin.strip()]
            else:
                self.cors_origins = []
        
        mock_post_init.side_effect = custom_post_init
        yield


# Create app fixture for API tests
@pytest.fixture
def test_app():
    """Create a test FastAPI application."""
    from src.youtube_analysis_api.app import create_app
    app = create_app()
    return app


@pytest.fixture
def test_client(test_app):
    """Create a test client for the FastAPI application."""
    from fastapi.testclient import TestClient
    return TestClient(test_app)