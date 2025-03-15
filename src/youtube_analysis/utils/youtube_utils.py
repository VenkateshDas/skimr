"""Utility functions for YouTube video analysis."""

from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from urllib.parse import urlparse, parse_qs
import re
import time
import os
import logging
import hashlib
from typing import Dict, Optional, Any, List
from datetime import datetime, timedelta
import json
from pathlib import Path
import requests

try:
    from pytube import YouTube
    PYTUBE_AVAILABLE = True
except ImportError:
    PYTUBE_AVAILABLE = False

from .logging import get_logger

# Configure logging
logger = logging.getLogger(__name__)

# Simple cache for transcriptions to avoid redundant API calls
# Key: video_id, Value: (timestamp, transcript_text)
TRANSCRIPTION_CACHE: Dict[str, tuple] = {}
CACHE_EXPIRY = 3600  # Cache expiry in seconds (1 hour)

def extract_video_id(url: str) -> str:
    """
    Extract the video ID from a YouTube URL.
    
    Args:
        url: The YouTube URL
        
    Returns:
        The extracted video ID
        
    Raises:
        ValueError: If the URL is not a valid YouTube URL
    """
    # Regular expression patterns for different YouTube URL formats
    patterns = [
        r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/watch\?v=([a-zA-Z0-9_-]{11})',
        r'(?:https?:\/\/)?(?:www\.)?youtu\.be\/([a-zA-Z0-9_-]{11})',
        r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/embed\/([a-zA-Z0-9_-]{11})',
        r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/v\/([a-zA-Z0-9_-]{11})',
    ]
    
    # Try each pattern
    for pattern in patterns:
        match = re.match(pattern, url)
        if match:
            return match.group(1)
    
    # If no pattern matches, raise an error
    raise ValueError(f"Could not extract video ID from URL: {url}")

def get_transcript(youtube_url: str) -> str:
    """
    Get the transcript of a YouTube video.
    
    Args:
        youtube_url: The URL of the YouTube video
        
    Returns:
        The transcript as a string
        
    Raises:
        ValueError: If the transcript cannot be retrieved
    """
    try:
        # Extract video ID
        video_id = extract_video_id(youtube_url)
        
        # Check if transcript is cached
        cached_transcript = get_cached_transcription(video_id)
        if cached_transcript:
            logger.info(f"Using cached transcript for video {video_id}")
            return cached_transcript
        
        # Fetch transcript
        logger.info(f"Fetching transcript for video {video_id}")
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=["en", "de", "ta"])
        
        # Combine transcript segments
        transcript_text = " ".join([item['text'] for item in transcript_list])
        
        # Cache the transcript
        cache_transcription(video_id, transcript_text)
        
        return transcript_text
        
    except (TranscriptsDisabled, NoTranscriptFound) as e:
        error_msg = f"No transcript available for this video: {str(e)}"
        logger.error(error_msg)
        raise ValueError(error_msg)
    except Exception as e:
        error_msg = f"Error retrieving transcript: {str(e)}"
        logger.error(error_msg)
        raise ValueError(error_msg)

def get_cache_dir() -> Path:
    """
    Get the cache directory for transcriptions.
    
    Returns:
        Path to the cache directory
    """
    # Get cache directory from environment variable or use default
    cache_dir = os.environ.get("TRANSCRIPT_CACHE_DIR", None)
    
    if not cache_dir:
        # Use default cache directory in user's home directory
        home_dir = Path.home()
        cache_dir = home_dir / ".youtube_analysis" / "cache"
    else:
        cache_dir = Path(cache_dir)
    
    # Create directory if it doesn't exist
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    return cache_dir

def get_cache_key(video_id: str) -> str:
    """
    Generate a cache key for a video ID.
    
    Args:
        video_id: The YouTube video ID
        
    Returns:
        A cache key as an MD5 hash
    """
    # Create an MD5 hash of the video ID
    return hashlib.md5(video_id.encode()).hexdigest()

def get_cached_transcription(video_id: str) -> Optional[str]:
    """
    Get a cached transcription if available and not expired.
    
    Args:
        video_id: The YouTube video ID
        
    Returns:
        The cached transcription or None if not available
    """
    try:
        cache_dir = get_cache_dir()
        cache_key = get_cache_key(video_id)
        cache_file = cache_dir / f"{cache_key}.json"
        
        # Check if cache file exists
        if not cache_file.exists():
            return None
        
        # Read cache file
        with open(cache_file, 'r') as f:
            cache_data = json.load(f)
        
        # Check if cache is expired (default: 24 hours)
        cache_expiration_hours = int(os.environ.get("CACHE_EXPIRATION_HOURS", 24))
        timestamp = datetime.fromisoformat(cache_data['timestamp'])
        if datetime.now() - timestamp > timedelta(hours=cache_expiration_hours):
            logger.info(f"Cache expired for video {video_id}")
            return None
        
        return cache_data['transcript']
        
    except Exception as e:
        logger.warning(f"Error reading cache for video {video_id}: {str(e)}")
        return None

def cache_transcription(video_id: str, transcript: str) -> None:
    """
    Cache a transcription for future use.
    
    Args:
        video_id: The YouTube video ID
        transcript: The transcription to cache
    """
    try:
        cache_dir = get_cache_dir()
        cache_key = get_cache_key(video_id)
        cache_file = cache_dir / f"{cache_key}.json"
        
        # Create cache data
        cache_data = {
            'video_id': video_id,
            'transcript': transcript,
            'timestamp': datetime.now().isoformat()
        }
        
        # Write cache file
        with open(cache_file, 'w') as f:
            json.dump(cache_data, f)
        
        logger.info(f"Cached transcript for video {video_id}")
        
    except Exception as e:
        logger.warning(f"Error caching transcript for video {video_id}: {str(e)}")

def get_transcript_from_url(youtube_url: str) -> str:
    """
    Fetches the transcription of a YouTube video given its URL.
    
    Args:
        youtube_url: The URL of the YouTube video.

    Returns:
        The full transcription text of the video.
    """
    logger.info(f"Fetching transcription for URL: {youtube_url}")
    try:
        # Extract video ID from the YouTube URL
        video_id = extract_video_id(youtube_url)
        logger.debug(f"Extracted video ID: {video_id}")
        
        # Check if we have a cached transcription
        current_time = time.time()
        if video_id in TRANSCRIPTION_CACHE:
            timestamp, transcript_text = TRANSCRIPTION_CACHE[video_id]
            if current_time - timestamp < CACHE_EXPIRY:
                logger.info(f"Using cached transcription for video ID: {video_id}")
                return transcript_text
        
        # Fetch the transcript directly using get_transcript
        logger.debug(f"Fetching transcript for video ID: {video_id}")
        transcript_data = YouTubeTranscriptApi.get_transcript(video_id)
        
        # Manual extraction and formatting of transcript text
        transcript_lines = []
        for item in transcript_data:
            if 'text' in item:
                transcript_lines.append(item['text'])
        
        # Join all transcript lines with line breaks
        transcript_text = '\n'.join(transcript_lines)
        
        logger.info(f"Successfully fetched transcription with {len(transcript_text)} characters")
        
        # Cache the transcription
        TRANSCRIPTION_CACHE[video_id] = (current_time, transcript_text)
        
        return transcript_text
    
    except Exception as e:
        error_message = f"Error fetching transcription: {str(e)}"
        logger.error(error_message, exc_info=True)
        raise ValueError(error_message)

def get_video_info(video_id: str) -> Dict[str, Any]:
    """
    Get information about a YouTube video (title, description, etc.).
    
    Args:
        video_id: The YouTube video ID
        
    Returns:
        A dictionary containing video information
    """
    video_info = {
        "title": f"YouTube Video ({video_id})",
        "description": "No description available"
    }
    
    try:
        # Try YouTube Data API first if available
        api_key = os.environ.get("YOUTUBE_API_KEY")
        if api_key:
            url = f"https://www.googleapis.com/youtube/v3/videos?id={video_id}&key={api_key}&part=snippet"
            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("items") and len(data["items"]) > 0:
                        snippet = data["items"][0]["snippet"]
                        video_info["title"] = snippet.get("title", f"YouTube Video ({video_id})")
                        video_info["description"] = snippet.get("description", "No description available")
                        logger.info(f"Retrieved video info for {video_id} using YouTube Data API")
                        return video_info
                    else:
                        logger.warning(f"No video data found for {video_id} using YouTube Data API")
                else:
                    logger.warning(f"Failed to retrieve video info from YouTube Data API: {response.status_code}")
            except Exception as e:
                logger.warning(f"Error using YouTube Data API: {str(e)}")
        
        # Fallback to pytube if API key not available or API request failed
        if PYTUBE_AVAILABLE:
            try:
                # Use pytube to get video info with error handling
                yt = YouTube(f"https://www.youtube.com/watch?v={video_id}")
                
                # Safely get title
                try:
                    if hasattr(yt, 'title') and yt.title:
                        video_info["title"] = yt.title
                except Exception as e:
                    logger.warning(f"Error retrieving title with pytube: {str(e)}")
                
                # Safely get description
                try:
                    if hasattr(yt, 'description') and yt.description:
                        video_info["description"] = yt.description
                except Exception as e:
                    logger.warning(f"Error retrieving description with pytube: {str(e)}")
                
                logger.info(f"Retrieved video info for {video_id} using pytube")
            except Exception as e:
                logger.warning(f"Error retrieving video info with pytube: {str(e)}")
                
    except Exception as e:
        logger.error(f"Error retrieving video info for {video_id}: {str(e)}", exc_info=True)
    
    return video_info

def validate_youtube_url(url: str) -> bool:
    """
    Validate if the provided URL is a valid YouTube URL.
    
    Args:
        url: The URL to validate
        
    Returns:
        True if the URL is valid, False otherwise
    """
    if not url:
        return False
    
    youtube_pattern = r'(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/)[a-zA-Z0-9_-]+'
    return bool(re.match(youtube_pattern, url)) 