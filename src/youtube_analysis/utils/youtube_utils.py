"""Utility functions for working with YouTube videos."""

from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from urllib.parse import urlparse, parse_qs
import re
import time
import os
import logging
import hashlib
from typing import Dict, Optional, Any, List, Tuple
from datetime import datetime, timedelta
import json
from pathlib import Path
import requests
from youtube_transcript_api.formatters import TextFormatter

try:
    from pytube import YouTube
    PYTUBE_AVAILABLE = True
except ImportError:
    PYTUBE_AVAILABLE = False

from .logging import get_logger
from ..config import YOUTUBE_API_KEY, CACHE_EXPIRY_DAYS, CACHE_DIR

# Configure logging
logger = get_logger(__name__)

# Get cache settings from config
cache_dir = Path(CACHE_DIR)
cache_dir.mkdir(parents=True, exist_ok=True)

def get_cache_dir() -> Path:
    """Get the cache directory path and ensure it exists."""
    return cache_dir

def get_cache_key(video_id: str, prefix: str = "") -> str:
    """
    Generate a cache key for a video ID.
    
    Args:
        video_id: The YouTube video ID
        prefix: Optional prefix for the cache key
    
    Returns:
        The cache key string
    """
    key = f"{prefix}_{video_id}" if prefix else video_id
    return hashlib.sha256(key.encode()).hexdigest()

def is_cache_valid(cache_file: Path) -> bool:
    """
    Check if a cache file is still valid based on its age.
    
    Args:
        cache_file: Path to the cache file
    
    Returns:
        True if the cache is still valid, False otherwise
    """
    if not cache_file.exists():
        return False
    
    # Check file age
    file_age = datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)
    return file_age.days < CACHE_EXPIRY_DAYS

def get_cached_transcription(video_id: str) -> Optional[str]:
    """
    Get cached transcription for a video if available.
    
    Args:
        video_id: The YouTube video ID
    
    Returns:
        The cached transcription or None if not found/expired
    """
    try:
        cache_file = get_cache_dir() / f"{get_cache_key(video_id, 'transcript')}.json"
        
        if is_cache_valid(cache_file):
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('transcript')
        
        return None
    except Exception as e:
        logger.warning(f"Error reading cache for video {video_id}: {str(e)}")
        return None

def cache_transcription(video_id: str, transcript: str) -> bool:
    """
    Cache a video transcription.
    
    Args:
        video_id: The YouTube video ID
        transcript: The transcription text
    
    Returns:
        True if caching was successful, False otherwise
    """
    try:
        cache_file = get_cache_dir() / f"{get_cache_key(video_id, 'transcript')}.json"
        
        data = {
            'video_id': video_id,
            'transcript': transcript,
            'timestamp': datetime.now().isoformat()
        }
        
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return True
    except Exception as e:
        logger.warning(f"Error caching transcription for video {video_id}: {str(e)}")
        return False

def extract_video_id(url: str) -> Optional[str]:
    """
    Extract the video ID from a YouTube URL.
    
    Args:
        url: YouTube URL or video ID
    
    Returns:
        Video ID or None if invalid URL
    """
    try:
        # Check if the input is already a video ID (11 characters, alphanumeric with _ and -)
        if re.match(r'^[0-9A-Za-z_-]{11}$', url):
            logger.info(f"Input appears to be a video ID already: {url}")
            return url
            
        # Handle various YouTube URL formats
        patterns = [
            r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',  # Standard and shortened
            r'(?:embed\/)([0-9A-Za-z_-]{11})',  # Embed URLs
            r'(?:watch\?v=)([0-9A-Za-z_-]{11})',  # Standard watch URLs
            r'(?:youtu\.be\/)([0-9A-Za-z_-]{11})'  # youtu.be URLs
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        # If we get here, no pattern matched
        logger.warning(f"Could not extract video ID from URL: {url}")
        return None
    except Exception as e:
        logger.error(f"Error extracting video ID: {str(e)}")
        return None

def validate_youtube_url(url: str) -> bool:
    """
    Validate if a URL is a valid YouTube URL.
    
    Args:
        url: The URL to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not url:
        return False
        
    patterns = [
        r'^https?:\/\/(?:www\.)?youtube\.com\/watch\?v=[0-9A-Za-z_-]{11}.*$',
        r'^https?:\/\/(?:www\.)?youtu\.be\/[0-9A-Za-z_-]{11}.*$',
        r'^https?:\/\/(?:www\.)?youtube\.com\/embed\/[0-9A-Za-z_-]{11}.*$'
    ]
    
    return any(re.match(pattern, url) for pattern in patterns)

def get_transcript(url: str, use_cache: bool = True) -> str:
    """
    Get the transcript of a YouTube video.
    
    Args:
        url: The YouTube URL
        use_cache: Whether to use cached transcripts
    
    Returns:
        The video transcript
    
    Raises:
        ValueError: If the URL is invalid or transcript cannot be retrieved
    """
    try:
        video_id = extract_video_id(url)
        
        # Try to get from cache first
        if use_cache:
            cached_transcript = get_cached_transcription(video_id)
            if cached_transcript:
                logger.info(f"Using cached transcript for video {video_id}")
                return cached_transcript
        
        # Get transcript from YouTube
        try:
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['en', "de", "ta", "hi"])
        except Exception as e:
            raise ValueError(f"Could not get transcript: {str(e)}")
        
        # Format transcript manually instead of using TextFormatter
        transcript_text = "\n".join([item.get('text', '') for item in transcript_list])
        
        # Cache the transcript
        if use_cache:
            cache_transcription(video_id, transcript_text)
        
        return transcript_text
    
    except ValueError as e:
        raise e
    except Exception as e:
        raise ValueError(f"Error getting transcript: {str(e)}")

def get_video_info(url: str) -> Optional[Dict[str, str]]:
    """
    Get basic information about a YouTube video.
    
    Args:
        url: YouTube video URL
    
    Returns:
        Dictionary with video information or None if error
    """
    try:
        video_id = extract_video_id(url)
        if not video_id:
            logger.error(f"Could not extract video ID from URL: {url}")
            return None
        
        # Try using YouTube Data API if API key is available
        api_key = YOUTUBE_API_KEY
        if api_key:
            try:
                # Use YouTube Data API v3
                api_url = f"https://www.googleapis.com/youtube/v3/videos?id={video_id}&key={api_key}&part=snippet"
                response = requests.get(api_url)
                data = response.json()
                
                if response.status_code == 200 and data.get('items'):
                    snippet = data['items'][0]['snippet']
                    return {
                        'video_id': video_id,
                        'title': snippet.get('title', f"YouTube Video ({video_id})"),
                        'description': snippet.get('description', '')[:500] + "..." if len(snippet.get('description', '')) > 500 else snippet.get('description', ''),
                        'thumbnail_url': snippet.get('thumbnails', {}).get('high', {}).get('url', f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"),
                        'youtube_url': url
                    }
                else:
                    logger.warning(f"YouTube API returned no items or error: {data.get('error', {}).get('message', 'Unknown error')}")
            except Exception as e:
                logger.warning(f"Error using YouTube Data API: {str(e)}")
        
        # Try using pytube as fallback
        if PYTUBE_AVAILABLE:
            try:
                from pytube import YouTube
                yt = YouTube(url)
                
                return {
                    'video_id': video_id,
                    'title': yt.title,
                    'description': yt.description[:500] + "..." if len(yt.description) > 500 else yt.description,
                    'thumbnail_url': f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
                    'youtube_url': url
                }
            except Exception as e:
                logger.warning(f"Error using pytube to get video info: {str(e)}")
        
        # Fallback to a simpler approach with just the video ID
        logger.info(f"Using basic video info for {video_id} as fallback")
        return {
            'video_id': video_id,
            'title': f"YouTube Video ({video_id})",
            'description': "Video description unavailable.",
            'thumbnail_url': f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
            'youtube_url': url
        }
            
    except Exception as e:
        logger.error(f"Error fetching video info: {str(e)}")
        return None

def process_transcript_async(youtube_url: str) -> Tuple[Optional[str], Optional[List], Optional[str]]:
    """
    Process a YouTube video transcript asynchronously.
    
    Args:
        youtube_url: The YouTube URL
    
    Returns:
        Tuple of (timestamped_transcript, transcript_list, error_message)
    """
    try:
        # Validate URL
        if not validate_youtube_url(youtube_url):
            return None, None, "Invalid YouTube URL"
        
        # Extract video ID
        video_id = extract_video_id(youtube_url)
        if not video_id:
            return None, None, "Could not extract video ID from URL"
        
        # Get transcript with timestamps
        try:
            timestamped_transcript, transcript_list = get_transcript_with_timestamps(youtube_url)
            return timestamped_transcript, transcript_list, None
        except Exception as e:
            error_msg = f"Error getting transcript with timestamps: {str(e)}"
            logger.error(error_msg)
            
            # Try to get plain transcript as fallback
            try:
                plain_transcript = get_transcript(youtube_url)
                return plain_transcript, None, None
            except Exception as e2:
                error_msg = f"Error getting transcript: {str(e2)}"
                logger.error(error_msg)
                return None, None, error_msg
    
    except Exception as e:
        error_msg = f"Error processing transcript: {str(e)}"
        logger.error(error_msg)
        return None, None, error_msg

def get_transcript_with_timestamps(youtube_url: str) -> Tuple[str, List]:
    """
    Get a transcript with timestamps for a YouTube video.
    
    Args:
        youtube_url: The YouTube URL
    
    Returns:
        Tuple of (formatted_transcript_with_timestamps, transcript_list)
    
    Raises:
        ValueError: If the transcript cannot be retrieved
    """
    try:
        video_id = extract_video_id(youtube_url)
        if not video_id:
            raise ValueError(f"Could not extract video ID from URL: {youtube_url}")
        
        # Get transcript from YouTube
        try:
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['en', "de", "ta", "hi"])
        except Exception as e:
            raise ValueError(f"Could not get transcript: {str(e)}")
        
        # Format transcript with timestamps
        formatted_transcript = ""
        for entry in transcript_list:
            # Convert seconds to MM:SS format
            seconds = int(entry['start'])
            minutes, seconds = divmod(seconds, 60)
            timestamp = f"{minutes:02d}:{seconds:02d}"
            
            # Add timestamp and text
            formatted_transcript += f"[{timestamp}] {entry['text']}\n"
        
        return formatted_transcript, transcript_list
    
    except ValueError as e:
        raise e
    except Exception as e:
        raise ValueError(f"Error getting transcript with timestamps: {str(e)}")

def clear_cache(video_id: Optional[str] = None) -> bool:
    """
    Clear the transcript cache.
    
    Args:
        video_id: Optional specific video ID to clear, or None for all
    
    Returns:
        True if successful, False otherwise
    """
    try:
        cache_dir = get_cache_dir()
        
        if video_id:
            # Clear specific video cache
            cache_file = cache_dir / f"{get_cache_key(video_id, 'transcript')}.json"
            if cache_file.exists():
                cache_file.unlink()
                logger.info(f"Cleared cache for video {video_id}")
        else:
            # Clear all cache files
            for cache_file in cache_dir.glob("*.json"):
                cache_file.unlink()
            logger.info("Cleared all transcript cache files")
        
        return True
    except Exception as e:
        logger.error(f"Error clearing cache: {str(e)}")
        return False 

def clean_markdown_fences(content):
    """Remove markdown code fences from the content."""
    content = re.sub(r'^```markdown\s*|```\s*', '', content)
    content = re.sub(r'^```\s*$', '', content)
    return content