"""Integration tests for video analysis endpoints."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient

from src.youtube_analysis_api.app import create_app
from src.youtube_analysis_api.api.models.video import (
    VideoAnalysisRequest,
    VideoAnalysisResponse,
    ContentGenerationRequest,
    ContentGenerationResponse,
    TranscriptRequest,
    TranscriptResponse
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
def auth_headers():
    """Authentication headers for testing."""
    return {"Authorization": "Bearer test-access-token"}


@pytest.fixture
def mock_webapp_adapter():
    """Mock WebAppAdapter for testing."""
    mock = MagicMock()
    mock.analyze_video = AsyncMock()
    mock.generate_additional_content = AsyncMock()
    mock.get_transcript_details = MagicMock()
    mock.get_video_info = MagicMock()
    mock.validate_youtube_url = MagicMock(return_value=True)
    return mock


@pytest.fixture
def mock_auth_middleware():
    """Mock authentication middleware."""
    return {
        "is_guest": False,
        "user_id": "test-user-id",
        "email": "test@example.com",
        "daily_limit": None,
        "remaining_requests": None
    }


@pytest.fixture
def test_video_data():
    """Test video analysis data."""
    return {
        "video_id": "dQw4w9WgXcQ",
        "video_info": {
            "video_id": "dQw4w9WgXcQ",
            "title": "Test Video",
            "description": "Test description",
            "channel_name": "Test Channel",
            "duration": 212,
            "view_count": 1000000,
            "thumbnail_url": "https://img.youtube.com/vi/dQw4w9WgXcQ/maxresdefault.jpg"
        },
        "task_outputs": {
            "summary": {
                "task_name": "summary",
                "content": "This is a test summary content.",
                "token_usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 50,
                    "total_tokens": 150
                },
                "execution_time": 2.5,
                "status": "completed"
            },
            "topics": {
                "task_name": "topics",
                "content": ["Topic 1", "Topic 2", "Topic 3"],
                "token_usage": {
                    "prompt_tokens": 80,
                    "completion_tokens": 30,
                    "total_tokens": 110
                },
                "execution_time": 1.5,
                "status": "completed"
            }
        },
        "total_token_usage": {
            "prompt_tokens": 180,
            "completion_tokens": 80,
            "total_tokens": 260
        },
        "analysis_time": 4.0,
        "cached": False,
        "chat_details": {
            "session_id": "test-session-123"
        }
    }


class TestVideoAnalysisEndpoints:
    """Integration tests for video analysis endpoints."""
    
    @patch("src.youtube_analysis_api.dependencies.get_user_context")
    @patch("src.youtube_analysis_api.dependencies.get_web_app_adapter")
    def test_analyze_video_success(self, mock_get_adapter, mock_get_user_context, 
                                client, auth_headers, mock_webapp_adapter, 
                                mock_auth_middleware, test_video_data):
        """Test successful video analysis."""
        # Arrange
        mock_get_adapter.return_value = mock_webapp_adapter
        mock_get_user_context.return_value = mock_auth_middleware
        
        # Mock successful analysis
        mock_webapp_adapter.analyze_video.return_value = (test_video_data, None)
        
        request_data = {
            "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "analysis_types": ["Summary & Classification", "Topics"],
            "use_cache": True,
            "model": "gpt-4o-mini",
            "temperature": 0.2
        }
        
        # Act
        response = client.post(
            "/api/v1/video/analyze",
            json=request_data,
            headers=auth_headers
        )
        
        # Assert
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["success"] is True
        assert response_data["video_id"] == test_video_data["video_id"]
        assert response_data["video_info"]["title"] == test_video_data["video_info"]["title"]
        assert "summary" in response_data["analysis_results"]
        assert response_data["token_usage"]["total_tokens"] == 260
        assert response_data["cached"] is False
        
        # Verify adapter call
        mock_webapp_adapter.analyze_video.assert_called_once()
        call_args = mock_webapp_adapter.analyze_video.call_args[1]
        assert call_args["youtube_url"] == request_data["youtube_url"]
        assert call_args["settings"]["analysis_types"] == request_data["analysis_types"]
        assert call_args["settings"]["model"] == request_data["model"]
    
    @patch("src.youtube_analysis_api.dependencies.get_user_context")
    @patch("src.youtube_analysis_api.dependencies.get_web_app_adapter")
    def test_analyze_video_error(self, mock_get_adapter, mock_get_user_context, 
                              client, auth_headers, mock_webapp_adapter, mock_auth_middleware):
        """Test video analysis with error."""
        # Arrange
        mock_get_adapter.return_value = mock_webapp_adapter
        mock_get_user_context.return_value = mock_auth_middleware
        
        # Mock analysis error
        mock_webapp_adapter.analyze_video.return_value = (None, "Failed to analyze video")
        
        request_data = {
            "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "analysis_types": ["Summary & Classification"]
        }
        
        # Act
        response = client.post(
            "/api/v1/video/analyze",
            json=request_data,
            headers=auth_headers
        )
        
        # Assert
        assert response.status_code == 400
        response_data = response.json()
        assert response_data["success"] is False
        assert "error" in response_data
        assert response_data["error"]["message"] == "Failed to analyze video"
    
    @patch("src.youtube_analysis_api.dependencies.get_user_context")
    @patch("src.youtube_analysis_api.dependencies.get_web_app_adapter")
    def test_generate_content_success(self, mock_get_adapter, mock_get_user_context, 
                                   client, auth_headers, mock_webapp_adapter, mock_auth_middleware):
        """Test successful content generation."""
        # Arrange
        mock_get_adapter.return_value = mock_webapp_adapter
        mock_get_user_context.return_value = mock_auth_middleware
        
        # Mock content generation
        mock_webapp_adapter.get_video_info.return_value = {
            "video_id": "dQw4w9WgXcQ",
            "title": "Test Video",
            "channel_name": "Test Channel"
        }
        
        mock_webapp_adapter.get_transcript_details.return_value = (
            "Full transcript text for testing",
            [{"text": "Segment 1", "start": 0.0}],
            None
        )
        
        mock_webapp_adapter.generate_additional_content.return_value = (
            "Generated blog post content",
            None,
            {"prompt_tokens": 200, "completion_tokens": 100, "total_tokens": 300}
        )
        
        request_data = {
            "video_id": "dQw4w9WgXcQ",
            "content_type": "blog_post",
            "model": "gpt-4o",
            "temperature": 0.5,
            "custom_instruction": "Write in a professional tone"
        }
        
        # Act
        response = client.post(
            "/api/v1/video/content",
            json=request_data,
            headers=auth_headers
        )
        
        # Assert
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["success"] is True
        assert response_data["content"] == "Generated blog post content"
        assert response_data["token_usage"]["total_tokens"] == 300
        
        # Verify adapter calls
        mock_webapp_adapter.get_transcript_details.assert_called_once()
        mock_webapp_adapter.generate_additional_content.assert_called_once()
        call_args = mock_webapp_adapter.generate_additional_content.call_args[1]
        assert call_args["content_type"] == "blog_post"
        assert call_args["settings"]["model"] == "gpt-4o"
        assert call_args["settings"]["custom_instruction"] == "Write in a professional tone"
    
    @patch("src.youtube_analysis_api.dependencies.get_user_context")
    @patch("src.youtube_analysis_api.dependencies.get_web_app_adapter")
    def test_generate_content_missing_transcript(self, mock_get_adapter, mock_get_user_context, 
                                             client, auth_headers, mock_webapp_adapter, mock_auth_middleware):
        """Test content generation with missing transcript."""
        # Arrange
        mock_get_adapter.return_value = mock_webapp_adapter
        mock_get_user_context.return_value = mock_auth_middleware
        
        # Mock missing transcript
        mock_webapp_adapter.get_video_info.return_value = {
            "video_id": "dQw4w9WgXcQ",
            "title": "Test Video",
            "channel_name": "Test Channel"
        }
        
        mock_webapp_adapter.get_transcript_details.return_value = (
            None,
            None,
            "Failed to retrieve transcript"
        )
        
        request_data = {
            "video_id": "dQw4w9WgXcQ",
            "content_type": "blog_post"
        }
        
        # Act
        response = client.post(
            "/api/v1/video/content",
            json=request_data,
            headers=auth_headers
        )
        
        # Assert
        assert response.status_code == 400
        response_data = response.json()
        assert response_data["success"] is False
        assert "error" in response_data
        assert "transcript" in response_data["error"]["message"].lower()
    
    @patch("src.youtube_analysis_api.dependencies.get_user_context")
    @patch("src.youtube_analysis_api.dependencies.get_web_app_adapter")
    def test_get_transcript_success(self, mock_get_adapter, mock_get_user_context, 
                                 client, auth_headers, mock_webapp_adapter, mock_auth_middleware):
        """Test successful transcript retrieval."""
        # Arrange
        mock_get_adapter.return_value = mock_webapp_adapter
        mock_get_user_context.return_value = mock_auth_middleware
        
        # Mock transcript retrieval
        mock_webapp_adapter.get_transcript_details.return_value = (
            "Full transcript text for testing",
            [
                {"text": "Segment 1", "start": 0.0, "duration": 2.0},
                {"text": "Segment 2", "start": 2.0, "duration": 3.0}
            ],
            None
        )
        
        request_data = {
            "video_id": "dQw4w9WgXcQ",
            "use_cache": True
        }
        
        # Act
        response = client.post(
            "/api/v1/video/transcript",
            json=request_data,
            headers=auth_headers
        )
        
        # Assert
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["success"] is True
        assert response_data["transcript"] == "Full transcript text for testing"
        assert len(response_data["segments"]) == 2
        
        # Verify adapter call
        mock_webapp_adapter.get_transcript_details.assert_called_once()
        call_args = mock_webapp_adapter.get_transcript_details.call_args[1]
        assert call_args["video_id"] == request_data["video_id"]
        assert call_args["use_cache"] == request_data["use_cache"]
    
    @patch("src.youtube_analysis_api.dependencies.get_user_context")
    def test_guest_user_rate_limit(self, mock_get_user_context, client):
        """Test rate limiting for guest users."""
        # Arrange
        # Mock guest user with no remaining requests
        mock_get_user_context.return_value = {
            "is_guest": True,
            "user_id": None,
            "email": None,
            "daily_limit": 3,
            "remaining_requests": 0
        }
        
        request_data = {
            "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "analysis_types": ["Summary & Classification"]
        }
        
        # Act
        response = client.post(
            "/api/v1/video/analyze",
            json=request_data
        )
        
        # Assert
        assert response.status_code == 429  # Too Many Requests
        response_data = response.json()
        assert response_data["success"] is False
        assert "error" in response_data
        assert "rate limit" in response_data["error"]["message"].lower()
    
    @patch("src.youtube_analysis_api.dependencies.get_user_context")
    def test_authenticated_user_no_rate_limit(self, mock_get_user_context, client, auth_headers):
        """Test authenticated users are not rate limited."""
        # This test verifies that the rate limiting middleware correctly 
        # distinguishes between guest and authenticated users
        
        # Arrange
        # Mock authenticated user (no rate limit)
        mock_get_user_context.return_value = {
            "is_guest": False,
            "user_id": "test-user-id",
            "email": "test@example.com",
            "daily_limit": None,
            "remaining_requests": None
        }
        
        # This test doesn't call the actual endpoint since we're only testing 
        # the middleware behavior - we'll mock a 200 response from the next handler
        
        # We'll verify this by checking that rate limiting doesn't block the request
        # The actual implementation of analyzing the video will be tested elsewhere
        
        with patch("src.youtube_analysis_api.api.routers.video_analysis.get_web_app_adapter") as mock_get_adapter:
            mock_adapter = MagicMock()
            mock_adapter.validate_youtube_url.return_value = True
            mock_adapter.analyze_video.return_value = ({}, None)  # Success
            mock_get_adapter.return_value = mock_adapter
            
            # Act
            response = client.post(
                "/api/v1/video/analyze",
                json={"youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
                headers=auth_headers
            )
            
            # Assert
            # If we get a 200 response, it means rate limiting didn't block the request
            assert response.status_code != 429  # Not rate limited 