"""Integration tests for WebAppAdapter integration with FastAPI backend."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient

from src.youtube_analysis_api.app import create_app
from src.youtube_analysis_api.dependencies import get_web_app_adapter
from src.youtube_analysis.adapters.webapp_adapter import WebAppAdapter


@pytest.fixture
def app():
    """Create FastAPI app for testing."""
    return create_app()


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Authentication headers for testing."""
    return {"Authorization": "Bearer test-access-token"}


class TestWebAppAdapterIntegration:
    """Test the integration between FastAPI and WebAppAdapter."""
    
    @patch("src.youtube_analysis_api.dependencies.get_user_context")
    @patch("src.youtube_analysis_api.dependencies.get_service_factory")
    def test_dependency_injection(self, mock_get_service_factory, mock_get_user_context, client):
        """Test that WebAppAdapter is correctly injected into the dependency system."""
        # Arrange
        mock_service_factory = MagicMock()
        mock_webapp_adapter = MagicMock()
        mock_service_factory.get_web_app_adapter.return_value = mock_webapp_adapter
        mock_get_service_factory.return_value = mock_service_factory
        
        # Mock authentication
        mock_get_user_context.return_value = {
            "is_guest": False,
            "user_id": "test-user-id",
            "email": "test@example.com"
        }
        
        # Act
        with patch("src.youtube_analysis_api.dependencies.get_web_app_adapter") as patched_get_adapter:
            # Call the dependency directly
            adapter = get_web_app_adapter()
            
            # Assert
            assert adapter is mock_webapp_adapter
            mock_service_factory.get_web_app_adapter.assert_called_once()
    
    @patch("src.youtube_analysis_api.dependencies.get_user_context")
    @patch("src.youtube_analysis.adapters.webapp_adapter.get_service_factory")
    def test_adapter_initialization(self, mock_get_service_factory, mock_get_user_context):
        """Test that WebAppAdapter is initialized with the correct parameters."""
        # Arrange
        mock_service_factory = MagicMock()
        mock_get_service_factory.return_value = mock_service_factory
        
        # Act
        adapter = WebAppAdapter()
        
        # Assert
        assert adapter.service_factory is mock_service_factory
        mock_get_service_factory.assert_called_once()
    
    @patch("src.youtube_analysis_api.dependencies.get_user_context")
    @patch("src.youtube_analysis_api.dependencies.get_web_app_adapter")
    def test_adapter_method_integration(self, mock_get_adapter, mock_get_user_context, client, auth_headers):
        """Test that adapter methods are called with correct parameters."""
        # Arrange
        mock_adapter = MagicMock()
        mock_adapter.validate_youtube_url.return_value = True
        mock_adapter.analyze_video = AsyncMock(return_value=({
            "video_id": "dQw4w9WgXcQ",
            "task_outputs": {},
            "total_token_usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
            "analysis_time": 1.0,
            "cached": False
        }, None))
        mock_get_adapter.return_value = mock_adapter
        
        # Mock authentication
        mock_get_user_context.return_value = {
            "is_guest": False,
            "user_id": "test-user-id",
            "email": "test@example.com"
        }
        
        # Request data
        request_data = {
            "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "analysis_types": ["Summary & Classification"],
            "use_cache": False,
            "model": "gpt-4o-mini",
            "temperature": 0.3
        }
        
        # Act
        response = client.post(
            "/api/v1/video/analyze",
            json=request_data,
            headers=auth_headers
        )
        
        # Assert
        assert response.status_code == 200
        
        # Verify adapter methods are called with correct parameters
        mock_adapter.validate_youtube_url.assert_called_once_with(request_data["youtube_url"])
        mock_adapter.analyze_video.assert_called_once()
        call_kwargs = mock_adapter.analyze_video.call_args[1]
        assert call_kwargs["youtube_url"] == request_data["youtube_url"]
        assert call_kwargs["settings"]["analysis_types"] == request_data["analysis_types"]
        assert call_kwargs["settings"]["use_cache"] == request_data["use_cache"]
        assert call_kwargs["settings"]["model"] == request_data["model"]
        assert call_kwargs["settings"]["temperature"] == request_data["temperature"]
    
    @patch("src.youtube_analysis_api.dependencies.get_user_context")
    @patch("src.youtube_analysis_api.dependencies.get_web_app_adapter")
    def test_result_transformation(self, mock_get_adapter, mock_get_user_context, client, auth_headers):
        """Test that adapter results are correctly transformed to API responses."""
        # Arrange
        mock_adapter = MagicMock()
        mock_adapter.validate_youtube_url.return_value = True
        
        # Mock adapter response structure
        adapter_response = {
            "video_id": "dQw4w9WgXcQ",
            "video_info": {
                "video_id": "dQw4w9WgXcQ",
                "title": "Test Video",
                "description": "Test description",
                "channel_name": "Test Channel"
            },
            "task_outputs": {
                "summary": {
                    "task_name": "summary",
                    "content": "This is a test summary",
                    "token_usage": {"prompt_tokens": 80, "completion_tokens": 40, "total_tokens": 120},
                    "execution_time": 1.2,
                    "status": "completed"
                }
            },
            "total_token_usage": {"prompt_tokens": 80, "completion_tokens": 40, "total_tokens": 120},
            "analysis_time": 1.5,
            "cached": True
        }
        
        mock_adapter.analyze_video = AsyncMock(return_value=(adapter_response, None))
        mock_get_adapter.return_value = mock_adapter
        
        # Mock authentication
        mock_get_user_context.return_value = {
            "is_guest": False,
            "user_id": "test-user-id",
            "email": "test@example.com"
        }
        
        # Act
        response = client.post(
            "/api/v1/video/analyze",
            json={"youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
            headers=auth_headers
        )
        
        # Assert
        assert response.status_code == 200
        response_data = response.json()
        
        # Verify the response structure matches our API model
        assert response_data["success"] is True
        assert response_data["video_id"] == "dQw4w9WgXcQ"
        assert "video_info" in response_data
        assert "analysis_results" in response_data
        assert "summary" in response_data["analysis_results"]
        assert response_data["analysis_results"]["summary"] == "This is a test summary"
        assert response_data["token_usage"]["total_tokens"] == 120
        assert response_data["cached"] is True
        assert response_data["analysis_time_seconds"] == 1.5
    
    @patch("src.youtube_analysis_api.dependencies.get_user_context")
    @patch("src.youtube_analysis_api.dependencies.get_web_app_adapter")
    def test_error_handling(self, mock_get_adapter, mock_get_user_context, client, auth_headers):
        """Test that adapter errors are correctly transformed to API error responses."""
        # Arrange
        mock_adapter = MagicMock()
        mock_adapter.validate_youtube_url.return_value = True
        
        # Mock adapter error response
        mock_adapter.analyze_video = AsyncMock(return_value=(None, "Analysis failed: service unavailable"))
        mock_get_adapter.return_value = mock_adapter
        
        # Mock authentication
        mock_get_user_context.return_value = {
            "is_guest": False,
            "user_id": "test-user-id",
            "email": "test@example.com"
        }
        
        # Act
        response = client.post(
            "/api/v1/video/analyze",
            json={"youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
            headers=auth_headers
        )
        
        # Assert
        assert response.status_code == 400  # Bad request for service errors
        response_data = response.json()
        
        # Verify the error response structure
        assert response_data["success"] is False
        assert "error" in response_data
        assert response_data["error"]["message"] == "Analysis failed: service unavailable"
        assert response_data["error"]["code"] == "ANALYSIS_ERROR" 