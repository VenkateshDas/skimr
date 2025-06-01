"""Service for transcript operations."""

from typing import Optional, Tuple, List, Dict, Any
import asyncio
from ..models import VideoData, TranscriptSegment
from ..repositories import CacheRepository, YouTubeRepository
from ..utils.logging import get_logger

logger = get_logger("transcript_service")


class TranscriptService:
    """Service for transcript-related operations."""
    
    def __init__(self, cache_repository: CacheRepository, youtube_repository: YouTubeRepository):
        self.cache_repo = cache_repository
        self.youtube_repo = youtube_repository
        logger.info("Initialized TranscriptService")
    
    async def get_transcript(self, youtube_url: str, use_cache: bool = True) -> Optional[str]:
        """Get plain transcript for a video."""
        video_data = await self._get_video_data(youtube_url, use_cache)
        return video_data.transcript if video_data else None
    
    async def get_timestamped_transcript(
        self, 
        youtube_url: str, 
        use_cache: bool = True
    ) -> Tuple[Optional[str], Optional[List[Dict[str, Any]]]]:
        """Get timestamped transcript and segment list."""
        video_data = await self._get_video_data(youtube_url, use_cache)
        if not video_data:
            return None, None
        
        transcript_list = None
        if video_data.transcript_segments:
            transcript_list = [
                {
                    "text": seg.text,
                    "start": seg.start,
                    "duration": seg.duration
                }
                for seg in video_data.transcript_segments
            ]
        
        return video_data.timestamped_transcript, transcript_list
    
    def get_transcript_sync(self, youtube_url: str, use_cache: bool = True) -> Optional[List[Dict[str, Any]]]:
        """
        Synchronous method to get transcript, used as a fallback for the webapp.
        
        Args:
            youtube_url: The YouTube video URL
            use_cache: Whether to use cached data
            
        Returns:
            List of transcript segments or None if error
        """
        try:
            # Get video data synchronously
            video_data = self.get_video_data_sync(youtube_url, use_cache)
            
            # If we have valid video data with transcript segments, use it
            if video_data and video_data.transcript_segments:
                # Convert transcript segments to dictionary format
                transcript_list = [
                    {
                        "text": seg.text,
                        "start": seg.start,
                        "duration": seg.duration
                    }
                    for seg in video_data.transcript_segments
                ]
                logger.info(f"Successfully retrieved transcript segments from video data for {youtube_url}")
                return transcript_list
            
            # If no segments in video data, try direct YouTube API call
            video_id = self.youtube_repo.extract_video_id(youtube_url)
            if not video_id:
                logger.error(f"Could not extract video ID from URL: {youtube_url}")
                return None
            
            # Try using YouTubeTranscriptApi directly
            try:
                from youtube_transcript_api import YouTubeTranscriptApi
                transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['en', 'de', 'ta', 'es', 'fr'])
                logger.info(f"Retrieved transcript directly using YouTubeTranscriptApi for {video_id}")
                return transcript_list
            except Exception as yt_api_error:
                logger.error(f"Error using YouTubeTranscriptApi directly: {str(yt_api_error)}")
                
                # Try to get transcript asynchronously as a last resort
                try:
                    transcript_text = asyncio.run(self.get_transcript(youtube_url, use_cache))
                    if transcript_text:
                        # Create a simple transcript segment with the full text
                        logger.info(f"Created simple transcript segment from plain text for {video_id}")
                        return [{"text": transcript_text, "start": 0.0, "duration": 0.0}]
                    else:
                        logger.error(f"Could not retrieve transcript text for {video_id}")
                        return None
                except Exception as async_error:
                    logger.error(f"Error in async transcript retrieval fallback: {str(async_error)}")
                    return None
        except Exception as e:
            logger.error(f"Error in get_transcript_sync: {str(e)}")
            return None
    
    def get_video_data_sync(self, youtube_url: str, use_cache: bool = True) -> Optional[VideoData]:
        """
        Synchronous wrapper for _get_video_data.
        
        Args:
            youtube_url: The YouTube video URL
            use_cache: Whether to use cached data
            
        Returns:
            VideoData object or None if error
        """
        try:
            # Use asyncio.run to execute the async method
            video_data = asyncio.run(self._get_video_data(youtube_url, use_cache))
            
            # Verify that video_data is not a coroutine
            if asyncio.iscoroutine(video_data):
                logger.warning(f"get_video_data_sync received a coroutine, attempting to resolve it")
                try:
                    # Run the coroutine
                    video_data = asyncio.run(video_data)
                except Exception as coroutine_error:
                    logger.error(f"Error resolving coroutine in get_video_data_sync: {str(coroutine_error)}")
                    return None
            
            # Ensure video_data is a proper VideoData object
            from ..models import VideoData as VideoDataModel
            if not isinstance(video_data, VideoDataModel):
                logger.warning(f"get_video_data_sync got unexpected type: {type(video_data)}, expected VideoData")
                # If it's a dict, try to convert it to VideoData
                if isinstance(video_data, dict):
                    try:
                        return VideoDataModel.from_dict(video_data)
                    except Exception as convert_error:
                        logger.error(f"Error converting dict to VideoData: {str(convert_error)}")
                        return None
                return None
            
            return video_data
        except Exception as e:
            logger.error(f"Error in get_video_data_sync: {str(e)}")
            return None
    
    async def _get_video_data(self, youtube_url: str, use_cache: bool = True) -> Optional[VideoData]:
        """Get video data from cache or fetch fresh."""
        video_id = self.youtube_repo.extract_video_id(youtube_url)
        if not video_id:
            return None
        
        if use_cache:
            video_data = await self.cache_repo.get_video_data(video_id)
            if video_data:
                return video_data
        
        # Fetch fresh data
        video_data = await self.youtube_repo.get_video_data(youtube_url)
        if video_data:
            await self.cache_repo.store_video_data(video_data)
        
        return video_data