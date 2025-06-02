"""Service for transcript operations."""

from typing import Optional, Tuple, List, Dict, Any
import asyncio
from ..models import VideoData, TranscriptSegment
from ..transcription import WhisperTranscriber, TranscriptUnavailable
from ..repositories import CacheRepository, YouTubeRepository
from ..utils.logging import get_logger

logger = get_logger("transcript_service")


class TranscriptService:
    """Service for transcript-related operations."""
    
    def __init__(self, cache_repository: CacheRepository, youtube_repository: YouTubeRepository):
        self.cache_repo = cache_repository
        self.youtube_repo = youtube_repository
        self.whisper_transcriber = WhisperTranscriber()
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
    
    async def get_formatted_transcripts(
        self,
        youtube_url: str,
        video_id: str,
        use_cache: bool = True
    ) -> Tuple[Optional[str], Optional[List[Dict[str, Any]]]]:
        """
        Get formatted transcripts for a video.
        
        Args:
            youtube_url: YouTube URL
            video_id: Video ID
            use_cache: Whether to use cached data
            
        Returns:
            Tuple of (timestamped transcript string, segment list)
        """
        video_data = await self._get_video_data(youtube_url, use_cache)
        if not video_data:
            return None, None
        
        # Format transcript with timestamps
        timestamped_transcript = ""
        transcript_segments = []
        
        if video_data.transcript_segments:
            for seg in video_data.transcript_segments:
                # Format timestamp
                start = seg.start
                minutes, seconds = divmod(int(start), 60)
                timestamp = f"[{minutes:02d}:{seconds:02d}]"
                
                # Add to timestamped transcript
                timestamped_transcript += f"{timestamp} {seg.text}\n"
                
                # Add to segments list
                transcript_segments.append({
                    "text": seg.text,
                    "start": seg.start,
                    "duration": seg.duration
                })
        
        return timestamped_transcript, transcript_segments
    
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
                        # Try Whisper transcription as final fallback
                        logger.info(f"Attempting Whisper transcription as final fallback for {video_id}")
                        whisper_result = asyncio.run(self.get_transcript_with_whisper(youtube_url, use_cache=use_cache))
                        if whisper_result and len(whisper_result) == 2:
                            _, segments = whisper_result
                            if segments:
                                logger.info(f"Successfully transcribed {video_id} with Whisper")
                                return segments
                            
                        logger.error(f"Could not retrieve transcript for {video_id}")
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
    
    async def get_transcript_with_whisper(
        self, 
        youtube_url: str, 
        language: str = "en", 
        model_name: str = None,
        use_cache: bool = True
    ) -> Optional[Tuple[str, List[Dict[str, Any]]]]:
        """
        Get transcript using OpenAI Whisper API directly.
        
        Args:
            youtube_url: YouTube URL
            language: ISO-639-1 language code
            model_name: OpenAI Whisper model to use (whisper-1, gpt-4o-transcribe, gpt-4o-mini-transcribe)
            use_cache: Whether to use cached transcript
            
        Returns:
            Tuple of (transcript text, segment list) or None if error
        """
        video_id = self.youtube_repo.extract_video_id(youtube_url)
        if not video_id:
            logger.error(f"Invalid YouTube URL: {youtube_url}")
            return None
        
        cache_key = f"whisper_transcript_{video_id}_{language}_{model_name or 'default'}"
        
        if use_cache:
            cached_data = await self.cache_repo.get_custom_data("transcripts", cache_key)
            if cached_data:
                logger.info(f"Using cached Whisper transcript for {video_id}")
                return cached_data.get("text"), cached_data.get("segments")
        
        try:
            logger.info(f"Transcribing {video_id} with Whisper API")
            transcript_obj = await self.whisper_transcriber.get(
                video_id=video_id, 
                language=language,
                model_name=model_name
            )
            
            if not transcript_obj or not transcript_obj.segments:
                logger.warning(f"Whisper transcription failed for {video_id}")
                return None
            
            # Convert segments to list of dicts for consistency with existing API
            segments_list = [
                {
                    "text": segment.text,
                    "start": segment.start,
                    "duration": segment.duration or 0
                }
                for segment in transcript_obj.segments
            ]
            
            transcript_text = transcript_obj.text
            
            # Store in cache
            if use_cache:
                await self.cache_repo.store_custom_data(
                    "transcripts", 
                    cache_key, 
                    {
                        "text": transcript_text,
                        "segments": segments_list
                    }
                )
            
            logger.info(f"Successfully transcribed {video_id} with Whisper")
            return transcript_text, segments_list
            
        except TranscriptUnavailable as e:
            logger.warning(f"Whisper transcription unavailable for {video_id}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error in Whisper transcription for {video_id}: {str(e)}")
            return None
    
    def get_transcript_with_whisper_sync(
        self, 
        youtube_url: str, 
        language: str = "en", 
        model_name: str = None,
        use_cache: bool = True
    ) -> Optional[Tuple[str, List[Dict[str, Any]]]]:
        """
        Synchronous method to get transcript using Whisper.
        
        Args:
            youtube_url: YouTube URL
            language: ISO-639-1 language code
            model_name: OpenAI Whisper model to use
            use_cache: Whether to use cached transcript
            
        Returns:
            Tuple of (transcript text, segment list) or None if error
        """
        try:
            # Use asyncio.run to execute the async method
            return asyncio.run(self.get_transcript_with_whisper(
                youtube_url=youtube_url, 
                language=language, 
                model_name=model_name, 
                use_cache=use_cache
            ))
        except Exception as e:
            logger.error(f"Error in get_transcript_with_whisper_sync: {str(e)}")
            return None