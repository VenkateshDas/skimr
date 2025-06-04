"""Mock WebAppAdapter for testing."""

from typing import Dict, Any, Optional
from unittest.mock import Mock


class MockWebAppAdapter:
    """Mock implementation of WebAppAdapter for testing."""
    
    def __init__(self):
        self.analyze_video_calls = []
        self.generate_content_calls = []
        self.get_transcript_calls = []
        self.chat_with_video_calls = []
        
        # Default return values
        self.analyze_video_result = {
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
                    "content": "Test summary content",
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
        
        self.generate_content_result = {
            "content": "Generated test content",
            "token_usage": {"prompt_tokens": 50, "completion_tokens": 25}
        }
        
        self.get_transcript_result = {
            "timestamped_transcript": "Test transcript content",
            "segments": [
                {"text": "Hello world", "start": 0.0, "duration": 2.0},
                {"text": "This is a test", "start": 2.0, "duration": 3.0}
            ]
        }
        
        self.chat_with_video_result = {
            "message": "Test chat response",
            "token_usage": {"prompt_tokens": 30, "completion_tokens": 20},
            "chat_session_id": "test-chat-session-456"
        }
    
    def analyze_video(self, **kwargs) -> Dict[str, Any]:
        """Mock analyze_video method."""
        self.analyze_video_calls.append(kwargs)
        return self.analyze_video_result
    
    def generate_content(self, **kwargs) -> Dict[str, Any]:
        """Mock generate_content method."""
        self.generate_content_calls.append(kwargs)
        return self.generate_content_result
    
    def get_transcript(self, youtube_url: str, use_cache: bool = True) -> Dict[str, Any]:
        """Mock get_transcript method."""
        self.get_transcript_calls.append({"youtube_url": youtube_url, "use_cache": use_cache})
        return self.get_transcript_result
    
    def chat_with_video(self, **kwargs) -> Dict[str, Any]:
        """Mock chat_with_video method."""
        self.chat_with_video_calls.append(kwargs)
        return self.chat_with_video_result
    
    def validate_youtube_url(self, url: str) -> bool:
        """Mock validate_youtube_url method."""
        return "youtube.com" in url or "youtu.be" in url
    
    def get_video_info(self, url: str) -> Optional[Dict[str, Any]]:
        """Mock get_video_info method."""
        if self.validate_youtube_url(url):
            return {
                "video_id": "dQw4w9WgXcQ",
                "title": "Test Video",
                "description": "Test description",
                "duration": 212,
                "view_count": 1000000,
                "channel_name": "Test Channel",
                "thumbnail_url": "https://img.youtube.com/vi/dQw4w9WgXcQ/maxresdefault.jpg"
            }
        return None
    
    def set_analyze_video_result(self, result: Dict[str, Any]):
        """Set the result for analyze_video calls."""
        self.analyze_video_result = result
    
    def set_generate_content_result(self, result: Dict[str, Any]):
        """Set the result for generate_content calls."""
        self.generate_content_result = result
    
    def set_get_transcript_result(self, result: Dict[str, Any]):
        """Set the result for get_transcript calls."""
        self.get_transcript_result = result
    
    def set_chat_with_video_result(self, result: Dict[str, Any]):
        """Set the result for chat_with_video calls."""
        self.chat_with_video_result = result
    
    def reset_calls(self):
        """Reset all call tracking."""
        self.analyze_video_calls = []
        self.generate_content_calls = []
        self.get_transcript_calls = []
        self.chat_with_video_calls = []


def create_mock_webapp_adapter() -> MockWebAppAdapter:
    """Factory function to create a mock WebAppAdapter."""
    return MockWebAppAdapter()