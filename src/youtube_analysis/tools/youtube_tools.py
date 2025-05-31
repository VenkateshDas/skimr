from crewai.tools import BaseTool
from typing import Dict, Optional, List, Any, Union
import asyncio

from ..utils.logging import get_logger
from ..core import YouTubeClient, CacheManager

logger = get_logger("tools.youtube")

# Initialize core components
cache_manager = CacheManager()
youtube_client = YouTubeClient(cache_manager)

class YouTubeTranscriptionTool(BaseTool):
    name: str = "YouTube Transcription Tool"
    description: str = "Fetches the transcription of a YouTube video given its URL."
    
    def _run(self, youtube_url: str) -> str:
        """
        Fetches the transcription of a YouTube video given its URL.
        
        Args:
            youtube_url: The URL of the YouTube video.

        Returns:
            The full transcription text of the video.
        """
        logger.info(f"Using YouTube Transcription Tool for URL: {youtube_url}")
        try:
            # Use the YouTubeClient to get the transcript
            transcript = asyncio.run(youtube_client.get_transcript(youtube_url))
            return transcript
        except Exception as e:
            error_message = f"Error fetching transcription: {str(e)}"
            logger.error(error_message, exc_info=True)
            return error_message 