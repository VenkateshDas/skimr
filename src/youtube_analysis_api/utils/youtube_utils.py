"""YouTube utility functions."""

import re
from typing import Optional


def validate_youtube_url(url: str) -> bool:
    """
    Validate if a URL is a valid YouTube URL.
    
    Args:
        url: The URL to validate
        
    Returns:
        True if valid YouTube URL, False otherwise
    """
    if not url or not isinstance(url, str):
        return False
    
    # YouTube URL patterns
    patterns = [
        r'^https?://(?:www\.)?youtube\.com/watch\?v=[\w-]+',
        r'^https?://(?:www\.)?youtu\.be/[\w-]+',
        r'^https?://(?:www\.)?youtube\.com/embed/[\w-]+',
        r'^https?://(?:www\.)?youtube\.com/v/[\w-]+',
        r'^https?://(?:m\.)?youtube\.com/watch\?v=[\w-]+',
    ]
    
    return any(re.match(pattern, url.strip()) for pattern in patterns)


def extract_video_id(url: str) -> Optional[str]:
    """
    Extract video ID from YouTube URL.
    
    Args:
        url: YouTube URL
        
    Returns:
        Video ID if found, None otherwise
    """
    if not validate_youtube_url(url):
        return None
    
    # Patterns to extract video ID
    patterns = [
        r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/|youtube\.com/v/)([^&\n?#]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None


def normalize_youtube_url(url: str) -> Optional[str]:
    """
    Normalize YouTube URL to standard format.
    
    Args:
        url: YouTube URL
        
    Returns:
        Normalized URL if valid, None otherwise
    """
    video_id = extract_video_id(url)
    if not video_id:
        return None
    
    return f"https://www.youtube.com/watch?v={video_id}"