from crewai.tools import BaseTool
from youtube_transcript_api import YouTubeTranscriptApi
from urllib.parse import urlparse, parse_qs
from typing import Dict, Optional, List, Any, Union
import re
import functools
import time

from ..utils.logging import get_logger

logger = get_logger("tools.youtube")

# Simple cache for transcriptions to avoid redundant API calls
# Key: video_id, Value: (timestamp, transcript_text)
TRANSCRIPTION_CACHE: Dict[str, tuple] = {}
CACHE_EXPIRY = 3600  # Cache expiry in seconds (1 hour)

class YouTubeTranscriptionTool(BaseTool):
    name: str = "YouTube Transcription Tool"
    description: str = "Fetches the transcription of a YouTube video given its URL."
    
    def _run(self, youtube_url: str, extract_only: bool = False) -> str:
        """
        Fetches the transcription of a YouTube video given its URL.
        
        Args:
            youtube_url: The URL of the YouTube video.
            extract_only: If True, only extract and return the video ID without fetching the transcription.
            
        Returns:
            The full transcription text of the video or the video ID if extract_only is True.
        """
        logger.info(f"Fetching transcription for URL: {youtube_url}")
        try:
            # Extract video ID from the YouTube URL
            video_id = self._extract_video_id(youtube_url)
            logger.debug(f"Extracted video ID: {video_id}")
            
            # If extract_only is True, just return the video ID
            if extract_only:
                return f"Video ID: {video_id}"
            
            # Check if we have a cached transcription
            current_time = time.time()
            if video_id in TRANSCRIPTION_CACHE:
                timestamp, transcript_text = TRANSCRIPTION_CACHE[video_id]
                if current_time - timestamp < CACHE_EXPIRY:
                    logger.info(f"Using cached transcription for video ID: {video_id}")
                    return transcript_text
            
            # Fetch the transcript using the newer fetch method
            logger.debug(f"Fetching transcript for video ID: {video_id}")
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            
            # Try to get the transcript in the default language first
            try:
                transcript = transcript_list.find_transcript(['en'])
                transcript_data = transcript.fetch()
            except Exception:
                # If that fails, get the first available transcript
                transcript = transcript_list.find_generated_transcript()
                transcript_data = transcript.fetch()
            
            logger.debug(f"Fetched {len(transcript_data)} transcript segments")
            
            # Combine all transcript parts into a single text
            transcript_text = ' '.join([part['text'] for part in transcript_data])
            logger.info(f"Successfully fetched transcription with {len(transcript_text)} characters")
            
            # Cache the transcription
            TRANSCRIPTION_CACHE[video_id] = (current_time, transcript_text)
            
            return transcript_text
        
        except Exception as e:
            error_message = f"Error fetching transcription: {str(e)}"
            logger.error(error_message, exc_info=True)
            return error_message
    
    def _extract_video_id(self, youtube_url: str) -> str:
        """
        Extracts the video ID from a YouTube URL.
        
        Args:
            youtube_url: The URL of the YouTube video.
            
        Returns:
            The video ID.
            
        Raises:
            ValueError: If the URL is invalid or the video ID cannot be extracted.
        """
        logger.debug(f"Extracting video ID from URL: {youtube_url}")
        
        # Improved regex pattern to extract video ID from various YouTube URL formats
        youtube_regex = r'(?:https?:\/\/)?(?:www\.|m\.)?(?:youtube\.com\/(?:watch\?.*v=|embed\/|v\/)|youtu\.be\/)([a-zA-Z0-9_-]{11})'
        
        match = re.search(youtube_regex, youtube_url)
        if match:
            video_id = match.group(1)
            logger.debug(f"Extracted video ID using regex: {video_id}")
            return video_id
        
        # If regex fails, fall back to the URL parsing method
        logger.debug("Regex extraction failed, falling back to URL parsing method")
        parsed_url = urlparse(youtube_url)
        
        # Handle different URL formats
        if parsed_url.netloc == 'youtu.be':
            # Short URL format: https://youtu.be/VIDEO_ID
            video_id = parsed_url.path.lstrip('/')
            logger.debug(f"Extracted video ID from youtu.be URL: {video_id}")
        elif parsed_url.netloc in ('www.youtube.com', 'youtube.com', 'm.youtube.com'):
            # Standard URL format: https://www.youtube.com/watch?v=VIDEO_ID
            if parsed_url.path == '/watch':
                query_params = parse_qs(parsed_url.query)
                if 'v' in query_params:
                    video_id = query_params['v'][0]
                    logger.debug(f"Extracted video ID from youtube.com/watch URL: {video_id}")
                else:
                    logger.error("Could not extract video ID from URL: Missing 'v' parameter")
                    raise ValueError("Could not extract video ID from URL: Missing 'v' parameter")
            # Shared URL format: https://www.youtube.com/v/VIDEO_ID
            elif parsed_url.path.startswith('/v/'):
                video_id = parsed_url.path.split('/v/')[1]
                logger.debug(f"Extracted video ID from youtube.com/v/ URL: {video_id}")
            # Embed URL format: https://www.youtube.com/embed/VIDEO_ID
            elif parsed_url.path.startswith('/embed/'):
                video_id = parsed_url.path.split('/embed/')[1]
                logger.debug(f"Extracted video ID from youtube.com/embed/ URL: {video_id}")
            else:
                logger.error(f"Unsupported YouTube URL format: {youtube_url}")
                raise ValueError(f"Unsupported YouTube URL format: {youtube_url}")
        else:
            logger.error(f"Not a valid YouTube URL: {youtube_url}")
            raise ValueError(f"Not a valid YouTube URL: {youtube_url}")
        
        # Validate video ID format (should be 11 characters)
        if not video_id or len(video_id) != 11:
            logger.error(f"Invalid video ID format: {video_id}")
            raise ValueError(f"Invalid video ID format: {video_id}")
            
        return video_id 