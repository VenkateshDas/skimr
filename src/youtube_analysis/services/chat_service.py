"""Service for chat operations."""

import asyncio
from typing import Optional, Dict, Any, List, Union
from ..models import ChatSession, ChatMessage, VideoData, AnalysisResult
from ..repositories import CacheRepository, YouTubeRepository
from ..chat import setup_chat_for_video_async
from ..utils.logging import get_logger

logger = get_logger("chat_service")


class ChatService:
    """Service for chat-related operations."""
    
    def __init__(self, cache_repository: CacheRepository, youtube_repository: YouTubeRepository):
        self.cache_repo = cache_repository
        self.youtube_repo = youtube_repository
        logger.info("Initialized ChatService")
    
    async def setup_chat(
        self, 
        youtube_url_or_data: Union[str, VideoData], 
        analysis_result: Optional[AnalysisResult] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Set up chat for a video.
        
        Args:
            youtube_url_or_data: Either a YouTube URL string or a VideoData object
            analysis_result: Optional analysis result to use for enhanced context
            
        Returns:
            Dictionary with chat details or None if failed
        """
        try:
            # Handle the case where a coroutine was passed
            if asyncio.iscoroutine(youtube_url_or_data):
                logger.warning("setup_chat received a coroutine for youtube_url_or_data, resolving it")
                youtube_url_or_data = await youtube_url_or_data
                
            # Handle different argument types
            if isinstance(youtube_url_or_data, VideoData):
                # We already have the VideoData object
                video_data = youtube_url_or_data
                youtube_url = video_data.youtube_url
                logger.info(f"Using provided VideoData object for {youtube_url}")
            elif isinstance(youtube_url_or_data, str):
                # We have a URL string, need to get VideoData
                youtube_url = youtube_url_or_data
                
                # Extract video ID
                video_id = self.youtube_repo.extract_video_id(youtube_url)
                if not video_id:
                    logger.error(f"Invalid YouTube URL: {youtube_url}")
                    return None
                
                # Try to get from cache first
                video_data = await self.cache_repo.get_video_data(video_id)
                
                # If not in cache, fetch from YouTube
                if not video_data:
                    logger.info(f"Fetching video data for {video_id}")
                    video_data = await self.youtube_repo.get_video_data(youtube_url)
            else:
                # Unexpected type
                logger.error(f"Unexpected type for youtube_url_or_data: {type(youtube_url_or_data)}")
                return None
            
            # Check if we have a valid VideoData object with transcript
            if not video_data:
                logger.error("Failed to get video data for chat setup")
                return None
            
            if not hasattr(video_data, 'has_transcript'):
                logger.error("VideoData object missing has_transcript attribute")
                return None
                
            if not video_data.has_transcript:
                logger.error("No transcript available for chat setup")
                return None
            
            # Convert transcript segments to list format for the chat setup
            transcript_list = None
            if hasattr(video_data, 'transcript_segments') and video_data.transcript_segments:
                transcript_list = [
                    {
                        "text": seg.text,
                        "start": seg.start,
                        "duration": seg.duration
                    }
                    for seg in video_data.transcript_segments
                ]
                logger.info(f"Prepared {len(transcript_list)} transcript segments for chat")
            
            # Get the transcript text
            transcript = video_data.transcript if hasattr(video_data, 'transcript') else None
            if not transcript:
                logger.error("No transcript text available for chat setup")
                return None
            
            # Set up chat
            logger.info(f"Setting up chat for {youtube_url}")
            chat_details = await setup_chat_for_video_async(
                youtube_url,
                transcript,
                transcript_list
            )
            
            if not chat_details:
                logger.error(f"Failed to set up chat for {youtube_url}")
                return None
                
            logger.info(f"Successfully set up chat for {youtube_url}")
            return chat_details
            
        except Exception as e:
            logger.error(f"Error setting up chat: {str(e)}", exc_info=True)
            return None

    def setup_chat_sync(
        self, 
        youtube_url_or_data: Union[str, VideoData], 
        analysis_result: Optional[AnalysisResult] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Synchronous wrapper for setup_chat.
        
        Args:
            youtube_url_or_data: Either a YouTube URL string or a VideoData object
            analysis_result: Optional analysis result to use for enhanced context
            
        Returns:
            Dictionary with chat details or None if failed
        """
        try:
            import asyncio
            
            # Properly handle coroutines as input
            if asyncio.iscoroutine(youtube_url_or_data):
                logger.warning("setup_chat_sync received a coroutine for youtube_url_or_data")
                try:
                    # Try to resolve it first
                    youtube_url_or_data = asyncio.run(youtube_url_or_data)
                except Exception as coroutine_error:
                    logger.error(f"Error resolving coroutine in setup_chat_sync: {str(coroutine_error)}")
                    return None
            
            # Run the async setup_chat method
            return asyncio.run(self.setup_chat(youtube_url_or_data, analysis_result))
        except Exception as e:
            logger.error(f"Error in setup_chat_sync: {str(e)}", exc_info=True)
            return None