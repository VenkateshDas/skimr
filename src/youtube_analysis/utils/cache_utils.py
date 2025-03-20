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
        cache_dir = Path(os.path.expanduser(cache_dir))
    
    # Create directory if it doesn't exist
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    return cache_dir

def get_cache_key(video_id: str) -> str:
    """
    Generate a cache key for a video ID.
    
    Args:
        video_id: The YouTube video ID
        
    Returns:
        The cache key string
    """
    # Create an MD5 hash of the video ID
    return hashlib.md5(video_id.encode()).hexdigest()

def get_cached_analysis(video_id: str, force_bypass: bool = False) -> Optional[Dict[str, Any]]:
    """
    Get cached analysis results if available and not expired.
    
    Args:
        video_id: The YouTube video ID
        force_bypass: If True, always return None to force a new analysis
        
    Returns:
        The cached analysis results or None if not available
    """
    # If force_bypass is True, always return None to force a new analysis
    if force_bypass:
        logger.info(f"Forced bypass of cache for video {video_id}")
        return None
        
    try:
        cache_dir = get_cache_dir()
        cache_key = get_cache_key(video_id)
        cache_file = cache_dir / f"{cache_key}_analysis.json"
        
        logger.info(f"Looking for cached analysis for video {video_id}")
        logger.info(f"Cache key: {cache_key}")
        logger.info(f"Cache file path: {cache_file}")
        
        # Check if cache file exists
        if not cache_file.exists():
            logger.info(f"No cached analysis found for video {video_id} - cache file does not exist")
            return None
        
        # Read cache file
        try:
            with open(cache_file, 'r') as f:
                cache_data = json.load(f)
            logger.info(f"Successfully loaded cache file for video {video_id}")
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON in cache file for video {video_id}: {str(e)}")
            return None
        except Exception as e:
            logger.warning(f"Error reading cache file for video {video_id}: {str(e)}")
            return None
        
        # Check if cache is expired (default: 168 hours / 7 days)
        cache_expiration_hours = int(os.environ.get("ANALYSIS_CACHE_EXPIRATION_HOURS", 168))
        timestamp = datetime.fromisoformat(cache_data['timestamp'])
        if datetime.now() - timestamp > timedelta(hours=cache_expiration_hours):
            logger.info(f"Analysis cache expired for video {video_id}")
            return None
        
        # Extra validation to make sure we have actual analysis data
        if 'analysis_results' not in cache_data or not cache_data['analysis_results']:
            logger.warning(f"Cache file found but contains no analysis results for video {video_id}")
            return None
            
        logger.info(f"Using valid cached analysis for video {video_id} from {timestamp}")
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
        if ('chat_details' in cache_data['analysis_results'] and 
            cache_data['analysis_results']['chat_details'] is not None and 
            'agent' in cache_data['analysis_results']['chat_details']):
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

def create_test_cache_file(video_id: str, analysis_results: Dict[str, Any]) -> None:
    """
    Create a test cache file for a specific video ID.
    This is a helper function for debugging cache issues.
    
    Args:
        video_id: The YouTube video ID
        analysis_results: The analysis results to cache
    """
    try:
        cache_dir = get_cache_dir()
        cache_key = get_cache_key(video_id)
        cache_file = cache_dir / f"{cache_key}_analysis.json"
        
        logger.info(f"Creating test cache file for video {video_id}")
        logger.info(f"Cache key: {cache_key}")
        logger.info(f"Cache file path: {cache_file}")
        
        # Create a copy of the results to modify
        cache_data = {
            'video_id': video_id,
            'analysis_results': analysis_results,
            'timestamp': datetime.now().isoformat()
        }
        
        # Write cache file
        with open(cache_file, 'w') as f:
            json.dump(cache_data, f, default=str)  # Use default=str to handle non-serializable objects
        
        logger.info(f"Created test cache file for video {video_id}")
        
    except Exception as e:
        logger.warning(f"Error creating test cache file for video {video_id}: {str(e)}", exc_info=True) 