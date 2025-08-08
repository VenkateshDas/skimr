"""Optimized YouTube client with async support and robust transcript fetching."""

import re
import asyncio
from typing import Dict, Any, Optional, Tuple, List
import requests
from dataclasses import dataclass
import yt_dlp

from .cache_manager import CacheManager
from .transcript_fetcher import RobustTranscriptFetcher, LanguagePreference, TranscriptResult
from ..utils.ssl_config import get_ssl_config
from ..utils.logging import get_logger

logger = get_logger("youtube_client")

@dataclass
class VideoInfo:
    """Video information data class."""
    video_id: str
    title: str
    description: str
    duration: Optional[int] = None
    view_count: Optional[int] = None
    upload_date: Optional[str] = None

class YouTubeClient:
    """Optimized YouTube client with robust transcript fetching and caching."""
    
    def __init__(
        self, 
        cache_manager: Optional[CacheManager] = None,
        language_preferences: Optional[LanguagePreference] = None,
        enable_whisper_fallback: bool = True,
        max_retries: int = 3
    ):
        self.cache = cache_manager or CacheManager()
        self.enable_whisper_fallback = enable_whisper_fallback
        
        # Initialize robust transcript fetcher
        self.transcript_fetcher = RobustTranscriptFetcher(
            cache_manager=self.cache,
            language_preferences=language_preferences,
            max_retries=max_retries
        )
        
        # SSL config for downstream decisions
        self.ssl_config = get_ssl_config()
        
        # Video ID extraction patterns
        self._video_patterns = [
            r'(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})',
            r'(?:https?://)?(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})',
            r'(?:https?://)?(?:www\.)?youtube\.com/v/([a-zA-Z0-9_-]{11})'
        ]
        
        logger.info("Initialized YouTubeClient with robust transcript fetching")
    
    def extract_video_id(self, url: str) -> Optional[str]:
        """Extract video ID from YouTube URL."""
        if not url:
            return None
        
        for pattern in self._video_patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return None
    
    async def get_video_info(self, url: str, use_cache: bool = True) -> Optional[VideoInfo]:
        """Get video information with caching."""
        video_id = self.extract_video_id(url)
        if not video_id:
            logger.error(f"Invalid YouTube URL: {url}")
            return None
        
        cache_key = f"video_info_{video_id}"
        
        if use_cache:
            cached = self.cache.get("analysis", cache_key)
            if cached:
                logger.debug(f"Using cached video info for {video_id}")
                return VideoInfo(**cached)
        
        try:
            # Prefer yt-dlp for rich metadata unless SSL is disabled
            if self.ssl_config.verify_ssl:
                ydl_opts = {
                    'quiet': True,
                    'no_warnings': True,
                    'extract_flat': False,
                }
                ydl_opts = self.ssl_config.configure_yt_dlp_options(ydl_opts)
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    video_info = VideoInfo(
                        video_id=video_id,
                        title=info.get('title', f'YouTube Video {video_id}'),
                        description=info.get('description', '')[:500] + ('...' if len(info.get('description', '')) > 500 else ''),
                        duration=info.get('duration'),
                        view_count=info.get('view_count'),
                        upload_date=info.get('upload_date')
                    )
            else:
                # Dev fallback: use oEmbed endpoint via requests session with SSL verify disabled
                session = requests.Session()
                self.ssl_config.configure_requests_session(session)
                oembed_url = 'https://www.youtube.com/oembed'
                resp = session.get(oembed_url, params={'url': url, 'format': 'json'}, timeout=10)
                title = f'YouTube Video {video_id}'
                description = ''
                if resp.ok:
                    data = resp.json()
                    title = data.get('title', title)
                video_info = VideoInfo(
                    video_id=video_id,
                    title=title,
                    description=description,
                )
            
            # Cache the result
            if use_cache:
                self.cache.set("analysis", cache_key, video_info.__dict__)
            
            logger.info(f"Retrieved video info: {video_info.title}")
            return video_info
                
        except Exception as e:
            logger.error(f"Error getting video info for {video_id}: {e}")
            return None
    
    async def get_transcript(
        self, 
        url: str, 
        use_cache: bool = True,
        preferred_language: Optional[str] = None
    ) -> Optional[str]:
        """
        Get video transcript using robust fetching approach.
        
        Args:
            url: YouTube video URL
            use_cache: Whether to use cached transcripts
            preferred_language: Preferred language code (e.g., 'en', 'de')
            
        Returns:
            Transcript text or None if unavailable
        """
        video_id = self.extract_video_id(url)
        if not video_id:
            logger.error(f"Invalid YouTube URL: {url}")
            return None
        
        try:
            result = await self.transcript_fetcher.fetch_transcript(
                video_id=video_id,
                youtube_url=url,
                use_cache=use_cache,
                preferred_language=preferred_language,
                fallback_to_whisper=self.enable_whisper_fallback
            )
            
            if result.success:
                logger.info(f"Retrieved transcript for {video_id} from {result.source.value} ({len(result.transcript)} chars)")
                return result.transcript
            else:
                logger.warning(f"Failed to get transcript for {video_id}: {result.error}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting transcript for {video_id}: {e}")
            return None
    
    async def get_transcript_with_timestamps(
        self, 
        url: str, 
        use_cache: bool = True,
        preferred_language: Optional[str] = None
    ) -> Tuple[Optional[str], Optional[List[Dict[str, Any]]]]:
        """
        Get transcript with timestamps using robust fetching approach.
        
        Args:
            url: YouTube video URL
            use_cache: Whether to use cached transcripts
            preferred_language: Preferred language code
            
        Returns:
            Tuple of (formatted transcript with timestamps, raw segment list)
        """
        video_id = self.extract_video_id(url)
        if not video_id:
            logger.error(f"Invalid YouTube URL: {url}")
            return None, None
        
        try:
            result = await self.transcript_fetcher.fetch_transcript(
                video_id=video_id,
                youtube_url=url,
                use_cache=use_cache,
                preferred_language=preferred_language,
                fallback_to_whisper=self.enable_whisper_fallback
            )
            
            if result.success and result.segments:
                # Format with timestamps
                formatted_transcript = []
                for segment in result.segments:
                    seconds = int(segment['start'])
                    minutes, seconds = divmod(seconds, 60)
                    timestamp = f"{minutes:02d}:{seconds:02d}"
                    formatted_transcript.append(f"[{timestamp}] {segment['text']}")
                
                formatted_text = "\n".join(formatted_transcript)
                
                logger.info(f"Retrieved timestamped transcript for {video_id} from {result.source.value}")
                return formatted_text, result.segments
            else:
                logger.warning(f"Failed to get timestamped transcript for {video_id}: {result.error}")
                return None, None
                
        except Exception as e:
            logger.error(f"Error getting timestamped transcript for {video_id}: {e}")
            return None, None
    
    async def get_transcript_result(
        self,
        url: str,
        use_cache: bool = True,
        preferred_language: Optional[str] = None
    ) -> TranscriptResult:
        """
        Get detailed transcript result including metadata and source information.
        
        Args:
            url: YouTube video URL
            use_cache: Whether to use cached transcripts
            preferred_language: Preferred language code
            
        Returns:
            TranscriptResult with detailed information about the fetch operation
        """
        video_id = self.extract_video_id(url)
        if not video_id:
            return TranscriptResult(
                success=False,
                error="Invalid YouTube URL"
            )
        
        try:
            result = await self.transcript_fetcher.fetch_transcript(
                video_id=video_id,
                youtube_url=url,
                use_cache=use_cache,
                preferred_language=preferred_language,
                fallback_to_whisper=self.enable_whisper_fallback
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting transcript result for {video_id}: {e}")
            return TranscriptResult(
                success=False,
                error=str(e)
            )
    
    def validate_url(self, url: str) -> bool:
        """Validate YouTube URL."""
        return self.extract_video_id(url) is not None
    
    async def get_video_details(self, url: str, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """
        Get complete video details including info and transcript using robust approach.
        
        Args:
            url: YouTube video URL
            use_cache: Whether to use cached data
            
        Returns:
            Dictionary with video details and transcript information
        """
        video_id = self.extract_video_id(url)
        if not video_id:
            logger.error(f"Invalid YouTube URL: {url}")
            return None
        
        try:
            # Run video info and transcript fetching concurrently
            info_task = self.get_video_info(url, use_cache)
            transcript_result_task = self.get_transcript_result(url, use_cache)
            
            info, transcript_result = await asyncio.gather(
                info_task, transcript_result_task,
                return_exceptions=True
            )
            
            # Handle exceptions
            if isinstance(info, Exception):
                logger.error(f"Error getting video info: {info}")
                info = None
            
            if isinstance(transcript_result, Exception):
                logger.error(f"Error getting transcript: {transcript_result}")
                transcript_result = TranscriptResult(success=False, error=str(transcript_result))
            
            # Format timestamped transcript if available
            timestamped_transcript = None
            if transcript_result.success and transcript_result.segments:
                formatted_lines = []
                for segment in transcript_result.segments:
                    seconds = int(segment['start'])
                    minutes, seconds = divmod(seconds, 60)
                    timestamp = f"{minutes:02d}:{seconds:02d}"
                    formatted_lines.append(f"[{timestamp}] {segment['text']}")
                timestamped_transcript = "\n".join(formatted_lines)
            
            return {
                "video_id": video_id,
                "url": url,
                "info": info,
                "transcript": transcript_result.transcript if transcript_result.success else None,
                "timestamped_transcript": timestamped_transcript,
                "transcript_list": transcript_result.segments if transcript_result.success else None,
                "transcript_source": transcript_result.source.value if transcript_result.source else None,
                "transcript_language": transcript_result.language,
                "transcript_error": transcript_result.error if not transcript_result.success else None,
                "fetch_time_ms": transcript_result.fetch_time_ms
            }
            
        except Exception as e:
            logger.error(f"Error getting video details for {video_id}: {e}")
            return None
    
    def get_transcript_metrics(self) -> Dict[str, Any]:
        """Get transcript fetching performance metrics."""
        return self.transcript_fetcher.get_metrics()
    
    def reset_transcript_circuit_breakers(self):
        """Reset transcript fetching circuit breakers (for admin/testing purposes)."""
        self.transcript_fetcher.reset_circuit_breakers()
        logger.info("Reset all transcript fetching circuit breakers")
    
    def configure_language_preferences(self, language_preferences: LanguagePreference):
        """Update language preferences for transcript fetching."""
        self.transcript_fetcher.language_prefs = language_preferences
        logger.info("Updated transcript language preferences")
    
    def enable_transcript_source(self, source_name: str, enabled: bool):
        """Enable or disable specific transcript sources."""
        # This could be extended to selectively enable/disable sources
        # For now, we handle this through the circuit breaker mechanism
        if not enabled:
            # Force circuit breaker open for this source
            from .transcript_fetcher import TranscriptSource
            try:
                source = TranscriptSource(source_name.lower())
                breaker = self.transcript_fetcher.circuit_breakers[source]
                breaker.state = "open"
                breaker.failures = breaker.failure_threshold
                logger.info(f"Disabled transcript source: {source_name}")
            except ValueError:
                logger.warning(f"Unknown transcript source: {source_name}")
        else:
            # Reset circuit breaker for this source
            from .transcript_fetcher import TranscriptSource
            try:
                source = TranscriptSource(source_name.lower())
                breaker = self.transcript_fetcher.circuit_breakers[source]
                breaker.state = "closed"
                breaker.failures = 0
                logger.info(f"Enabled transcript source: {source_name}")
            except ValueError:
                logger.warning(f"Unknown transcript source: {source_name}")

    # Backward compatibility methods (deprecated)
    def _get_transcript_sync(self, video_id: str) -> Optional[List[Dict[str, Any]]]:
        """
        Deprecated: Use get_transcript_result instead.
        Synchronous transcript fetching with basic retry logic for backward compatibility.
        """
        logger.warning("_get_transcript_sync is deprecated. Use async methods instead.")
        
        try:
            # Convert async call to sync for backward compatibility
            result = asyncio.run(self.transcript_fetcher.fetch_transcript(
                video_id=video_id,
                youtube_url=f"https://youtu.be/{video_id}",
                use_cache=True,
                fallback_to_whisper=self.enable_whisper_fallback
            ))
            
            if result.success and result.segments:
                return result.segments
            else:
                logger.warning(f"Backward compatibility method failed for {video_id}: {result.error}")
                return None
                
        except Exception as e:
            logger.error(f"Error in backward compatibility method for {video_id}: {e}")
            return None