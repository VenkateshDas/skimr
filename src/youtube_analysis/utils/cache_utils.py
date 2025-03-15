"""Utility functions for caching analysis results."""

import os
import json
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from .logging import get_logger

# Configure logging
logger = get_logger("cache_utils")

def get_cache_dir() -> Path:
    """
    Get the cache directory for analysis results.
    
    Returns:
        Path to the cache directory
    """
    # Get cache directory from environment variable or use default
    cache_dir = os.environ.get("ANALYSIS_CACHE_DIR", None)
    
    if not cache_dir:
        # Use default cache directory in user's home directory
        home_dir = Path.home()
        cache_dir = home_dir / ".youtube_analysis" / "analysis_cache"
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

def get_cached_analysis(video_id: str) -> Optional[Dict[str, Any]]:
    """
    Get cached analysis results if available and not expired.
    
    Args:
        video_id: The YouTube video ID
        
    Returns:
        The cached analysis results or None if not available
    """
    try:
        cache_dir = get_cache_dir()
        cache_key = get_cache_key(video_id)
        cache_file = cache_dir / f"{cache_key}_analysis.json"
        
        # Check if cache file exists
        if not cache_file.exists():
            logger.info(f"No cached analysis found for video {video_id}")
            return None
        
        # Read cache file
        with open(cache_file, 'r') as f:
            cache_data = json.load(f)
        
        # Check if cache is expired (default: 168 hours / 7 days)
        cache_expiration_hours = int(os.environ.get("ANALYSIS_CACHE_EXPIRATION_HOURS", 168))
        timestamp = datetime.fromisoformat(cache_data['timestamp'])
        if datetime.now() - timestamp > timedelta(hours=cache_expiration_hours):
            logger.info(f"Analysis cache expired for video {video_id}")
            return None
        
        logger.info(f"Using cached analysis for video {video_id} from {timestamp}")
        return cache_data['analysis_results']
        
    except Exception as e:
        logger.warning(f"Error reading analysis cache for video {video_id}: {str(e)}")
        return None

def cache_analysis(video_id: str, analysis_results: Dict[str, Any]) -> None:
    """
    Cache analysis results for future use.
    
    Args:
        video_id: The YouTube video ID
        analysis_results: The analysis results to cache
    """
    try:
        cache_dir = get_cache_dir()
        cache_key = get_cache_key(video_id)
        cache_file = cache_dir / f"{cache_key}_analysis.json"
        
        # Create a copy of the results to modify
        cache_data = {
            'video_id': video_id,
            'analysis_results': analysis_results,
            'timestamp': datetime.now().isoformat()
        }
        
        # Remove non-serializable objects from the analysis results
        # The agent object from chat_details is not serializable
        if 'chat_details' in cache_data['analysis_results'] and 'agent' in cache_data['analysis_results']['chat_details']:
            cache_data['analysis_results']['chat_details'].pop('agent', None)
        
        # Write cache file
        with open(cache_file, 'w') as f:
            json.dump(cache_data, f, default=str)  # Use default=str to handle non-serializable objects
        
        logger.info(f"Cached analysis results for video {video_id}")
        
    except Exception as e:
        logger.warning(f"Error caching analysis for video {video_id}: {str(e)}", exc_info=True)

def clear_analysis_cache(video_id: str) -> bool:
    """
    Clear the cached analysis for a specific video.
    
    Args:
        video_id: The YouTube video ID
        
    Returns:
        True if the cache was cleared, False otherwise
    """
    try:
        cache_dir = get_cache_dir()
        cache_key = get_cache_key(video_id)
        cache_file = cache_dir / f"{cache_key}_analysis.json"
        
        # Check if cache file exists
        if not cache_file.exists():
            logger.info(f"No cached analysis found for video {video_id}")
            return False
        
        # Delete the cache file
        cache_file.unlink()
        logger.info(f"Cleared analysis cache for video {video_id}")
        return True
        
    except Exception as e:
        logger.warning(f"Error clearing analysis cache for video {video_id}: {str(e)}")
        return False 