"""Unit tests for utility functions."""

import pytest
import os
from unittest.mock import patch, MagicMock

from src.youtube_analysis_api.utils.youtube_utils import (
    validate_youtube_url, 
    extract_video_id,
    normalize_youtube_url
)


class TestYouTubeUrlUtils:
    """Tests for YouTube URL utility functions."""
    
    @pytest.mark.parametrize("url,expected", [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", True),
        ("https://youtu.be/dQw4w9WgXcQ", True),
        ("https://youtube.com/watch?v=dQw4w9WgXcQ", True),
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&feature=youtu.be", True),
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42s", True),
        ("https://www.youtube.com/embed/dQw4w9WgXcQ", True),
        ("https://m.youtube.com/watch?v=dQw4w9WgXcQ", True),
        ("https://example.com", False),
        ("https://vimeo.com/12345", False),
        ("invalid-url", False),
        ("", False),
        (None, False),
    ])
    def test_validate_youtube_url(self, url, expected):
        """Test YouTube URL validation with various inputs."""
        # Act
        result = validate_youtube_url(url)
        
        # Assert
        assert result == expected
    
    @pytest.mark.parametrize("url,expected", [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&feature=youtu.be", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42s", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://m.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://example.com", None),
        ("invalid-url", None),
        ("", None),
        (None, None),
    ])
    def test_extract_video_id(self, url, expected):
        """Test YouTube video ID extraction with various inputs."""
        # Act
        result = extract_video_id(url)
        
        # Assert
        assert result == expected
    
    @pytest.mark.parametrize("url,expected", [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ", "https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
        ("https://youtube.com/watch?v=dQw4w9WgXcQ", "https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
        ("https://m.youtube.com/watch?v=dQw4w9WgXcQ", "https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
        ("https://example.com", None),
        ("invalid-url", None),
        ("", None),
        (None, None),
    ])
    def test_normalize_youtube_url(self, url, expected):
        """Test YouTube URL normalization."""
        # Act
        result = normalize_youtube_url(url)
        
        # Assert
        assert result == expected 