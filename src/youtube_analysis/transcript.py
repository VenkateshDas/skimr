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
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        
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

def format_transcript_with_clickable_timestamps(transcript_list, video_id, jump_in_embedded=False):
    """
    Format transcript with clickable timestamps that jump to specific points in the video.
    
    Args:
        transcript_list: List of transcript items with start times and text
        video_id: YouTube video ID
        jump_in_embedded: Whether to jump to timestamp in embedded video or open in new tab
        
    Returns:
        HTML string with clickable timestamps
    """
    html_parts = []
    html_parts.append('<div class="transcript-container" style="height: 400px; overflow-y: auto; font-family: monospace; white-space: pre-wrap; padding: 10px; background-color: #1A1A1A; border-radius: 8px; border: 1px solid #333;">')
    
    for item in transcript_list:
        # Convert seconds to MM:SS format
        seconds = int(item['start'])
        minutes, seconds = divmod(seconds, 60)
        timestamp = f"{minutes:02d}:{seconds:02d}"
        
        # Create clickable timestamp that jumps to that point in the video
        timestamp_seconds = int(item['start'])
        html_parts.append(f'<div class="transcript-line" style="margin-bottom: 8px;">')
        
        if jump_in_embedded:
            # Instead of using JavaScript, use a direct link with a simpler approach
            # YouTube URLs with timestamps can be used in the iframe source
            html_parts.append(f'<a href="https://www.youtube.com/embed/{video_id}?start={timestamp_seconds}&autoplay=1" target="youtube-player" style="color: #FF0000; text-decoration: none; font-weight: bold;" onclick="event.preventDefault(); document.getElementById(\'youtube-player\').src = this.href;">[{timestamp}]</a> {item["text"]}')
        else:
            # Create a link that opens in a new tab
            html_parts.append(f'<a href="https://www.youtube.com/watch?v={video_id}&t={timestamp_seconds}" target="_blank" style="color: #FF0000; text-decoration: none; font-weight: bold;">[{timestamp}]</a> {item["text"]}')
        
        html_parts.append('</div>')
    
    html_parts.append('</div>')
    return ''.join(html_parts) 