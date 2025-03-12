from crewai.tools import BaseTool
from typing import Dict, Optional, List, Any, Union

from ..utils.logging import get_logger
from ..utils.youtube_utils import get_transcript

logger = get_logger("tools.youtube")

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
            # Use the utility function to get the transcript
            transcript = get_transcript(youtube_url)
            return transcript
        except Exception as e:
            error_message = f"Error fetching transcription: {str(e)}"
            logger.error(error_message, exc_info=True)
            return error_message 