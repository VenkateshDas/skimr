"""Unit tests for video analysis Pydantic models."""

import pytest
from pydantic import ValidationError
from src.youtube_analysis_api.api.models.video import (
    VideoAnalysisRequest,
    AnalysisResponse,
    ContentGenerationRequest,
    ContentGenerationResponse,
    TranscriptRequest,
    TranscriptResponse,
    VideoInfo
)


class TestVideoAnalysisRequest:
    """Test VideoAnalysisRequest model validation."""
    
    def test_valid_analysis_request(self):
        """Test creating valid VideoAnalysisRequest."""
        # Arrange & Act
        data = {
            "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "analysis_types": ["Summary & Classification", "Blog Post"],
            "use_cache": True,
            "model_name": "gpt-4o-mini",
            "temperature": 0.2,
            "custom_instruction": "Analyze in depth"
        }
        
        request = VideoAnalysisRequest(**data)
        
        # Assert
        assert request.youtube_url == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        assert "Summary & Classification" in request.analysis_types
        assert "Blog Post" in request.analysis_types
        assert request.use_cache is True
        assert request.model_name == "gpt-4o-mini"
        assert request.temperature == 0.2
        assert request.custom_instruction == "Analyze in depth"
    
    def test_analysis_request_defaults(self):
        """Test VideoAnalysisRequest default values."""
        # Arrange & Act
        data = {
            "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        }
        
        request = VideoAnalysisRequest(**data)
        
        # Assert
        assert request.analysis_types == ["Summary & Classification"]
        assert request.use_cache is True
        assert request.model_name is None
        assert request.temperature is None
        assert request.custom_instruction == ""
    
    def test_analysis_request_invalid_url(self):
        """Test VideoAnalysisRequest with invalid URL."""
        # Arrange
        data = {
            "youtube_url": "invalid-url"
        }
        
        # Act & Assert
        with pytest.raises(ValidationError):
            VideoAnalysisRequest(**data)
    
    def test_analysis_request_invalid_temperature(self):
        """Test VideoAnalysisRequest with invalid temperature."""
        # Arrange
        data = {
            "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "temperature": 1.5  # Should be <= 1.0
        }
        
        # Act & Assert
        with pytest.raises(ValidationError):
            VideoAnalysisRequest(**data)


class TestAnalysisResponse:
    """Test AnalysisResponse model validation."""
    
    def test_valid_analysis_response(self):
        """Test creating valid AnalysisResponse."""
        # Arrange & Act
        data = {
            "video_id": "dQw4w9WgXcQ",
            "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "video_info": {
                "video_id": "dQw4w9WgXcQ",
                "title": "Test Video",
                "description": "Test description",
                "duration": 212,
                "view_count": 1000000,
                "channel_name": "Test Channel",
                "thumbnail_url": "https://img.youtube.com/vi/dQw4w9WgXcQ/maxresdefault.jpg"
            },
            "task_outputs": {
                "summary": {
                    "task_name": "summary",
                    "content": "Test summary",
                    "token_usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
                    "execution_time": 2.5,
                    "status": "completed"
                }
            },
            "total_token_usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150
            },
            "analysis_time": 5.2,
            "cached": False
        }
        
        response = AnalysisResponse(**data)
        
        # Assert
        assert response.video_id == "dQw4w9WgXcQ"
        assert response.youtube_url == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        assert response.video_info.title == "Test Video"
        assert "summary" in response.task_outputs
        assert response.task_outputs["summary"].content == "Test summary"
        assert response.total_token_usage["total_tokens"] == 150
        assert response.analysis_time == 5.2
        assert response.cached is False
    
    def test_analysis_response_minimal(self):
        """Test AnalysisResponse with minimal data."""
        # Arrange & Act
        data = {
            "video_id": "dQw4w9WgXcQ",
            "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        }
        
        response = AnalysisResponse(**data)
        
        # Assert
        assert response.video_id == "dQw4w9WgXcQ"
        assert response.youtube_url == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        assert response.video_info is None
        assert response.task_outputs == {}
        assert response.total_token_usage is None
        assert response.analysis_time is None
        assert response.cached is False


class TestContentGenerationRequest:
    """Test ContentGenerationRequest model validation."""
    
    def test_valid_content_generation_request(self):
        """Test creating valid ContentGenerationRequest."""
        # Arrange & Act
        data = {
            "video_id": "dQw4w9WgXcQ",
            "content_type": "blog_post",
            "model_name": "gpt-4o",
            "temperature": 0.5,
            "custom_instruction": "Write in casual tone"
        }
        
        request = ContentGenerationRequest(**data)
        
        # Assert
        assert request.video_id == "dQw4w9WgXcQ"
        assert request.content_type == "blog_post"
        assert request.model_name == "gpt-4o"
        assert request.temperature == 0.5
        assert request.custom_instruction == "Write in casual tone"
    
    def test_content_request_defaults(self):
        """Test ContentGenerationRequest default values."""
        # Arrange & Act
        data = {
            "video_id": "dQw4w9WgXcQ",
            "content_type": "blog_post"
        }
        
        request = ContentGenerationRequest(**data)
        
        # Assert
        assert request.model_name is None
        assert request.temperature is None
        assert request.custom_instruction == ""


class TestTranscriptRequest:
    """Test TranscriptRequest model validation."""
    
    def test_valid_transcript_request(self):
        """Test creating valid TranscriptRequest."""
        # Arrange & Act
        data = {
            "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "video_id": "dQw4w9WgXcQ",
            "use_cache": True
        }
        
        request = TranscriptRequest(**data)
        
        # Assert
        assert request.youtube_url == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        assert request.video_id == "dQw4w9WgXcQ"
        assert request.use_cache is True
    
    def test_transcript_request_defaults(self):
        """Test TranscriptRequest default values."""
        # Arrange & Act
        data = {
            "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "video_id": "dQw4w9WgXcQ"
        }
        
        request = TranscriptRequest(**data)
        
        # Assert
        assert request.use_cache is True


class TestVideoInfo:
    """Test VideoInfo model validation."""
    
    def test_valid_video_info(self):
        """Test creating valid VideoInfo."""
        # Arrange & Act
        data = {
            "video_id": "dQw4w9WgXcQ",
            "title": "Test Video",
            "description": "Test description",
            "duration": 212,
            "view_count": 1000000,
            "channel_name": "Test Channel",
            "thumbnail_url": "https://img.youtube.com/vi/dQw4w9WgXcQ/maxresdefault.jpg"
        }
        
        video_info = VideoInfo(**data)
        
        # Assert
        assert video_info.video_id == "dQw4w9WgXcQ"
        assert video_info.title == "Test Video"
        assert video_info.description == "Test description"
        assert video_info.duration == 212
        assert video_info.view_count == 1000000
        assert video_info.channel_name == "Test Channel"
        assert video_info.thumbnail_url == "https://img.youtube.com/vi/dQw4w9WgXcQ/maxresdefault.jpg"
    
    def test_video_info_minimal(self):
        """Test creating VideoInfo with minimal data."""
        # Arrange & Act
        data = {
            "video_id": "dQw4w9WgXcQ",
            "title": "Test Video"
        }
        
        video_info = VideoInfo(**data)
        
        # Assert
        assert video_info.video_id == "dQw4w9WgXcQ"
        assert video_info.title == "Test Video"
        assert video_info.description is None
        assert video_info.duration is None
        assert video_info.view_count is None
        assert video_info.channel_name is None 