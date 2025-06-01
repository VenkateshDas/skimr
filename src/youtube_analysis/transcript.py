"""Utility functions for handling YouTube video transcripts with timestamps."""

import re
import asyncio
from typing import Dict, List, Tuple, Any, Optional

from .utils.logging import get_logger
from .core import YouTubeClient, CacheManager

# Configure logging
logger = get_logger("transcript")

# Initialize core components
cache_manager = CacheManager()
youtube_client = YouTubeClient(cache_manager)

def get_transcript_with_timestamps(youtube_url: str) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Get the transcript of a YouTube video with timestamps (sync wrapper).
    
    Args:
        youtube_url: The URL of the YouTube video
        
    Returns:
        A tuple containing:
        - The formatted transcript as a string with timestamps
        - The raw transcript list for further processing
        
    Raises:
        ValueError: If the transcript cannot be retrieved
    """
    return asyncio.run(get_transcript_with_timestamps_async(youtube_url))

async def get_transcript_with_timestamps_async(youtube_url: str) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Get the transcript of a YouTube video with timestamps (async).
    
    Args:
        youtube_url: The URL of the YouTube video
        
    Returns:
        A tuple containing:
        - The formatted transcript as a string with timestamps
        - The raw transcript list for further processing
        
    Raises:
        ValueError: If the transcript cannot be retrieved
    """
    try:
        # Use the YouTube client to get transcript with timestamps
        logger.info(f"Fetching transcript with timestamps for {youtube_url}")
        result = await youtube_client.get_transcript_with_timestamps(youtube_url)
        
        if result[0] is None or result[1] is None:
            raise ValueError("Could not retrieve transcript with timestamps")
        
        return result
        
    except Exception as e:
        error_msg = f"Error retrieving transcript with timestamps: {str(e)}"
        logger.error(error_msg)
        raise ValueError(error_msg) 