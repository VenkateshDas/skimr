"""Utility functions for handling YouTube video transcripts with timestamps."""

import re
from typing import Dict, List, Tuple, Any, Optional
from youtube_transcript_api import YouTubeTranscriptApi

from .utils.logging import get_logger
from .utils.youtube_utils import extract_video_id

# Configure logging
logger = get_logger("transcript")

def get_transcript_with_timestamps(youtube_url: str) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Get the transcript of a YouTube video with timestamps.
    
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
        # Extract video ID
        video_id = extract_video_id(youtube_url)
        
        # Fetch transcript with timestamps
        logger.info(f"Fetching transcript with timestamps for video {video_id}")
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['en', "de", "ta"])
        
        # Format transcript with timestamps
        formatted_transcript = []
        for item in transcript_list:
            # Convert seconds to MM:SS format
            seconds = int(item['start'])
            minutes, seconds = divmod(seconds, 60)
            timestamp = f"{minutes:02d}:{seconds:02d}"
            
            # Add timestamp and text
            formatted_transcript.append(f"[{timestamp}] {item['text']}")
        
        # Join transcript segments with newlines
        transcript_text = "\n".join(formatted_transcript)
        
        return transcript_text, transcript_list
        
    except Exception as e:
        error_msg = f"Error retrieving transcript with timestamps: {str(e)}"
        logger.error(error_msg)
        raise ValueError(error_msg) 