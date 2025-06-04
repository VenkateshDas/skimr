"""Unit tests for video analysis API endpoints."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import FastAPI
from httpx import AsyncClient

from src.youtube_analysis_api.api.routers.video_analysis import router
from src.youtube_analysis_api.api.models.video import (
    VideoAnalysisRequest,
    VideoAnalysisResponse,
    ContentGenerationRequest,
    ContentGenerationResponse,
    TranscriptRequest,
    TranscriptResponse
)
from src.youtube_analysis_api.exceptions import APIError, ValidationError


@pytest.fixture
def app():
    """Create test FastAPI app with video analysis router."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def mock_webapp_adapter():
    """Create mock WebAppAdapter."""
    mock = MagicMock()
    mock.analyze_video = AsyncMock()
    mock.generate_additional_content = AsyncMock()
    mock.get_transcript_details = MagicMock()
    mock.get_video_info = MagicMock()
    mock.validate_youtube_url = MagicMock()
    return mock


@pytest.fixture
def test_token_usage():
    """Test token usage data."""
    return {
        "prompt_tokens": 100,
        "completion_tokens": 50,
        "total_tokens": 150
    }


class TestVideoAnalysisEndpoints:
    """Test video analysis API endpoints."""
    
    @pytest.mark.asyncio
    @patch("src.youtube_analysis_api.api.routers.video_analysis.get_web_app_adapter")
    async def test_analyze_video_success(self, mock_get_adapter, app, mock_webapp_adapter, test_token_usage):
        """Test successful video analysis endpoint."""
        # Arrange
        mock_get_adapter.return_value = mock_webapp_adapter
        
        # Mock successful analysis response
        mock_webapp_adapter.analyze_video.return_value = ({
            "video_id": "dQw4w9WgXcQ",
            "video_info": {
                "video_id": "dQw4w9WgXcQ",
                "title": "Test Video",
                "description": "Test description",
                "channel_name": "Test Channel",
                "thumbnail_url": "https://img.youtube.com/vi/dQw4w9WgXcQ/maxresdefault.jpg"
            },
            "task_outputs": {
                "summary": {
                    "task_name": "summary",
                    "content": "Test summary content",
                    "token_usage": test_token_usage,
                    "execution_time": 2.5,
                    "status": "completed"
                }
            },
            "total_token_usage": test_token_usage,
            "analysis_time": 5.2,
            "cached": False
        }, None)  # No error
        
        request_data = {
            "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "analysis_types": ["Summary & Classification"],
            "use_cache": True
        }
        
        # Mock user context dependency
        async def mock_get_user_context():
            return {
                "is_guest": False,
                "user_id": "test-user-id",
                "email": "test@example.com"
            }
        
        with patch("src.youtube_analysis_api.api.routers.video_analysis.get_user_context", return_value=mock_get_user_context()):
            # Act
            async with AsyncClient(app=app, base_url="http://test") as client:
                response = await client.post("/analyze", json=request_data)
            
            # Assert
            assert response.status_code == 200
            response_data = response.json()
            assert response_data["success"] is True
            assert response_data["video_id"] == "dQw4w9WgXcQ"
            assert "analysis_results" in response_data
            assert "token_usage" in response_data
            
            # Verify WebAppAdapter was called with correct arguments
            mock_webapp_adapter.analyze_video.assert_called_once()
            call_args = mock_webapp_adapter.analyze_video.call_args
            assert call_args.kwargs["youtube_url"] == request_data["youtube_url"]
            assert call_args.kwargs["settings"]["analysis_types"] == request_data["analysis_types"]
            assert call_args.kwargs["settings"]["use_cache"] == request_data["use_cache"]
    
    @pytest.mark.asyncio
    @patch("src.youtube_analysis_api.api.routers.video_analysis.get_web_app_adapter")
    async def test_analyze_video_error(self, mock_get_adapter, app, mock_webapp_adapter):
        """Test video analysis endpoint with error response."""
        # Arrange
        mock_get_adapter.return_value = mock_webapp_adapter
        
        # Mock error response
        mock_webapp_adapter.analyze_video.return_value = (None, "Failed to analyze video")
        
        request_data = {
            "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "analysis_types": ["Summary & Classification"],
            "use_cache": True
        }
        
        # Mock user context dependency
        async def mock_get_user_context():
            return {
                "is_guest": False,
                "user_id": "test-user-id",
                "email": "test@example.com"
            }
        
        with patch("src.youtube_analysis_api.api.routers.video_analysis.get_user_context", return_value=mock_get_user_context()):
            # Act
            async with AsyncClient(app=app, base_url="http://test") as client:
                response = await client.post("/analyze", json=request_data)
            
            # Assert
            assert response.status_code == 400
            response_data = response.json()
            assert response_data["success"] is False
            assert "error" in response_data
            assert response_data["error"]["message"] == "Failed to analyze video"
    
    @pytest.mark.asyncio
    @patch("src.youtube_analysis_api.api.routers.video_analysis.get_web_app_adapter")
    async def test_analyze_video_invalid_url(self, mock_get_adapter, app, mock_webapp_adapter):
        """Test video analysis endpoint with invalid URL."""
        # Arrange
        mock_get_adapter.return_value = mock_webapp_adapter
        
        # Mock URL validation to fail
        mock_webapp_adapter.validate_youtube_url.return_value = False
        
        request_data = {
            "youtube_url": "invalid-url",
            "analysis_types": ["Summary & Classification"],
            "use_cache": True
        }
        
        # Mock user context dependency
        async def mock_get_user_context():
            return {
                "is_guest": False,
                "user_id": "test-user-id",
                "email": "test@example.com"
            }
        
        with patch("src.youtube_analysis_api.api.routers.video_analysis.get_user_context", return_value=mock_get_user_context()):
            # Act
            async with AsyncClient(app=app, base_url="http://test") as client:
                response = await client.post("/analyze", json=request_data)
            
            # Assert
            assert response.status_code == 400
            response_data = response.json()
            assert response_data["success"] is False
            assert "error" in response_data
            assert "Invalid YouTube URL" in response_data["error"]["message"]
    
    @pytest.mark.asyncio
    @patch("src.youtube_analysis_api.api.routers.video_analysis.get_web_app_adapter")
    async def test_generate_content_success(self, mock_get_adapter, app, mock_webapp_adapter, test_token_usage):
        """Test successful content generation endpoint."""
        # Arrange
        mock_get_adapter.return_value = mock_webapp_adapter
        
        # Mock successful content generation
        mock_webapp_adapter.generate_additional_content.return_value = (
            "Generated content for blog post", 
            None,  # No error
            test_token_usage
        )
        
        request_data = {
            "video_id": "dQw4w9WgXcQ",
            "content_type": "blog_post",
            "model": "gpt-4o",
            "temperature": 0.5,
            "custom_instruction": ""
        }
        
        # Mock transcript retrieval
        mock_webapp_adapter.get_transcript_details.return_value = (
            "Full transcript text", 
            [{"text": "Segment 1", "start": 0.0}],
            None  # No error
        )
        
        # Mock video info retrieval
        mock_webapp_adapter.get_video_info.return_value = {
            "video_id": "dQw4w9WgXcQ",
            "title": "Test Video",
            "channel_name": "Test Channel"
        }
        
        # Mock user context dependency
        async def mock_get_user_context():
            return {
                "is_guest": False,
                "user_id": "test-user-id",
                "email": "test@example.com"
            }
        
        with patch("src.youtube_analysis_api.api.routers.video_analysis.get_user_context", return_value=mock_get_user_context()):
            # Act
            async with AsyncClient(app=app, base_url="http://test") as client:
                response = await client.post("/content", json=request_data)
            
            # Assert
            assert response.status_code == 200
            response_data = response.json()
            assert response_data["success"] is True
            assert response_data["content"] == "Generated content for blog post"
            assert "token_usage" in response_data
            
            # Verify WebAppAdapter was called with correct arguments
            mock_webapp_adapter.generate_additional_content.assert_called_once()
            call_args = mock_webapp_adapter.generate_additional_content.call_args
            assert call_args.kwargs["video_id"] == request_data["video_id"]
            assert call_args.kwargs["content_type"] == request_data["content_type"]
            assert call_args.kwargs["settings"]["model"] == request_data["model"]
            assert call_args.kwargs["settings"]["temperature"] == request_data["temperature"]
    
    @pytest.mark.asyncio
    @patch("src.youtube_analysis_api.api.routers.video_analysis.get_web_app_adapter")
    async def test_get_transcript_success(self, mock_get_adapter, app, mock_webapp_adapter):
        """Test successful transcript retrieval endpoint."""
        # Arrange
        mock_get_adapter.return_value = mock_webapp_adapter
        
        # Mock successful transcript retrieval
        mock_webapp_adapter.get_transcript_details.return_value = (
            "Full transcript text", 
            [
                {"text": "Segment 1", "start": 0.0, "duration": 2.0},
                {"text": "Segment 2", "start": 2.0, "duration": 3.0}
            ],
            None  # No error
        )
        
        request_data = {
            "video_id": "dQw4w9WgXcQ",
            "use_cache": True
        }
        
        # Mock user context dependency
        async def mock_get_user_context():
            return {
                "is_guest": False,
                "user_id": "test-user-id",
                "email": "test@example.com"
            }
        
        with patch("src.youtube_analysis_api.api.routers.video_analysis.get_user_context", return_value=mock_get_user_context()):
            # Act
            async with AsyncClient(app=app, base_url="http://test") as client:
                response = await client.post("/transcript", json=request_data)
            
            # Assert
            assert response.status_code == 200
            response_data = response.json()
            assert response_data["success"] is True
            assert response_data["transcript"] == "Full transcript text"
            assert len(response_data["segments"]) == 2
            
            # Verify WebAppAdapter was called with correct arguments
            mock_webapp_adapter.get_transcript_details.assert_called_once()
            call_args = mock_webapp_adapter.get_transcript_details.call_args
            assert call_args.kwargs["video_id"] == request_data["video_id"]
            assert call_args.kwargs["use_cache"] == request_data["use_cache"]
    
    @pytest.mark.asyncio
    @patch("src.youtube_analysis_api.api.routers.video_analysis.get_web_app_adapter")
    async def test_get_transcript_error(self, mock_get_adapter, app, mock_webapp_adapter):
        """Test transcript retrieval endpoint with error."""
        # Arrange
        mock_get_adapter.return_value = mock_webapp_adapter
        
        # Mock error in transcript retrieval
        mock_webapp_adapter.get_transcript_details.return_value = (
            None,  # No transcript
            None,  # No segments
            "Failed to retrieve transcript"  # Error
        )
        
        request_data = {
            "video_id": "dQw4w9WgXcQ",
            "use_cache": True
        }
        
        # Mock user context dependency
        async def mock_get_user_context():
            return {
                "is_guest": False,
                "user_id": "test-user-id",
                "email": "test@example.com"
            }
        
        with patch("src.youtube_analysis_api.api.routers.video_analysis.get_user_context", return_value=mock_get_user_context()):
            # Act
            async with AsyncClient(app=app, base_url="http://test") as client:
                response = await client.post("/transcript", json=request_data)
            
            # Assert
            assert response.status_code == 400
            response_data = response.json()
            assert response_data["success"] is False
            assert "error" in response_data
            assert "Failed to retrieve transcript" in response_data["error"]["message"]
    
    @pytest.mark.asyncio
    @patch("src.youtube_analysis_api.api.routers.video_analysis.get_web_app_adapter")
    async def test_rate_limit_for_guest(self, mock_get_adapter, app, mock_webapp_adapter):
        """Test rate limiting for guest users."""
        # Arrange
        mock_get_adapter.return_value = mock_webapp_adapter
        
        request_data = {
            "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "analysis_types": ["Summary & Classification"],
            "use_cache": True
        }
        
        # Mock guest user context with no remaining requests
        async def mock_get_user_context():
            return {
                "is_guest": True,
                "user_id": None,
                "email": None,
                "daily_limit": 3,
                "remaining_requests": 0
            }
        
        with patch("src.youtube_analysis_api.api.routers.video_analysis.get_user_context", return_value=mock_get_user_context()):
            # Act
            async with AsyncClient(app=app, base_url="http://test") as client:
                response = await client.post("/analyze", json=request_data)
            
            # Assert
            assert response.status_code == 429  # Too Many Requests
            response_data = response.json()
            assert response_data["success"] is False
            assert "error" in response_data
            assert "rate limit" in response_data["error"]["message"].lower() 