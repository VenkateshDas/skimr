"""Optimized YouTube client with async support and caching."""

import re
import os
import asyncio
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass
from youtube_transcript_api import YouTubeTranscriptApi
import yt_dlp

from .cache_manager import CacheManager
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
    """Optimized YouTube client with caching and async support."""
    
    def __init__(self, cache_manager: Optional[CacheManager] = None):
        self.cache = cache_manager or CacheManager()
        self._video_patterns = [
            r'(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})',
            r'(?:https?://)?(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})',
            r'(?:https?://)?(?:www\.)?youtube\.com/v/([a-zA-Z0-9_-]{11})'
        ]
    
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
            # Use yt-dlp for reliable video info extraction
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
            }
            
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
                
                # Cache the result
                if use_cache:
                    self.cache.set("analysis", cache_key, video_info.__dict__)
                
                logger.info(f"Retrieved video info: {video_info.title}")
                return video_info
                
        except Exception as e:
            logger.error(f"Error getting video info: {e}")
            return None
    
    async def get_transcript(self, url: str, use_cache: bool = True) -> Optional[str]:
        """Get video transcript with caching."""
        video_id = self.extract_video_id(url)
        if not video_id:
            return None
        
        cache_key = f"transcript_{video_id}"
        
        if use_cache:
            cached = self.cache.get("transcripts", cache_key)
            if cached:
                logger.debug(f"Using cached transcript for {video_id}")
                return cached.get("text")
        
        # Run blocking transcript API call in executor
        loop = asyncio.get_event_loop()
        try:
            transcript_list = await loop.run_in_executor(
                None, self._get_transcript_sync, video_id
            )
            
            if not transcript_list:
                return None
            
            transcript = ' '.join([item['text'] for item in transcript_list])
            
            # Cache the result
            if use_cache:
                self.cache.set("transcripts", cache_key, {"text": transcript})
            
            logger.info(f"Retrieved transcript for {video_id} ({len(transcript)} chars)")
            return transcript
            
        except Exception as e:
            logger.error(f"Error getting transcript for {video_id}: {e}")
            return None
    
    def _get_transcript_sync(self, video_id: str) -> Optional[List[Dict[str, Any]]]:
        """Synchronous transcript fetching with retry logic."""
        languages = ['en', 'de', 'ta', 'es', 'fr', 'hi', 'ar', 'zh', 'ja', 'ko']
        
        for attempt in range(3):  # 3 retry attempts
            try:
                # Try different language combinations
                if attempt == 0:
                    # First attempt: try primary languages
                    transcript_list = YouTubeTranscriptApi.get_transcript(
                        video_id, languages=['en', 'de', 'ta', 'es', 'fr']
                    )
                elif attempt == 1:
                    # Second attempt: try all available languages
                    transcript_list = YouTubeTranscriptApi.get_transcript(
                        video_id, languages=languages
                    )
                else:
                    # Third attempt: let the API decide
                    transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
                
                if transcript_list:
                    return transcript_list
                    
            except Exception as e:
                error_msg = str(e).lower()
                if 'no element found' in error_msg or 'xml' in error_msg:
                    logger.warning(f"XML parsing error for {video_id} on attempt {attempt + 1}: {e}")
                    if attempt < 2:
                        continue  # Retry
                elif 'could not retrieve' in error_msg or 'transcript' in error_msg:
                    logger.warning(f"No transcript available for {video_id}: {e}")
                    break  # Don't retry for missing transcripts
                else:
                    logger.error(f"Unexpected error getting transcript for {video_id} on attempt {attempt + 1}: {e}")
                    if attempt < 2:
                        continue  # Retry for unexpected errors
        
        return None
    
    async def get_transcript_with_timestamps(self, url: str, use_cache: bool = True) -> Tuple[Optional[str], Optional[List[Dict[str, Any]]]]:
        """Get transcript with timestamps."""
        video_id = self.extract_video_id(url)
        if not video_id:
            return None, None
        
        cache_key = f"transcript_ts_{video_id}"
        
        if use_cache:
            cached = self.cache.get("transcripts", cache_key)
            if cached:
                logger.debug(f"Using cached timestamped transcript for {video_id}")
                return cached.get("formatted"), cached.get("raw")
        
        # Run blocking transcript API call in executor
        loop = asyncio.get_event_loop()
        try:
            transcript_list = await loop.run_in_executor(
                None, self._get_transcript_sync, video_id
            )
            
            if not transcript_list:
                return None, None
            
            # Format with timestamps
            formatted_transcript = []
            for item in transcript_list:
                seconds = int(item['start'])
                minutes, seconds = divmod(seconds, 60)
                timestamp = f"{minutes:02d}:{seconds:02d}"
                formatted_transcript.append(f"[{timestamp}] {item['text']}")
            
            formatted_text = "\n".join(formatted_transcript)
            
            # Cache the result
            if use_cache:
                self.cache.set("transcripts", cache_key, {
                    "formatted": formatted_text,
                    "raw": transcript_list
                })
            
            logger.info(f"Retrieved timestamped transcript for {video_id}")
            return formatted_text, transcript_list
            
        except Exception as e:
            logger.error(f"Error getting timestamped transcript for {video_id}: {e}")
            return None, None
    
    def validate_url(self, url: str) -> bool:
        """Validate YouTube URL."""
        return self.extract_video_id(url) is not None
    
    async def get_video_details(self, url: str, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """Get complete video details including info and transcript."""
        video_id = self.extract_video_id(url)
        if not video_id:
            return None
        
        # Run tasks concurrently
        info_task = self.get_video_info(url, use_cache)
        transcript_task = self.get_transcript(url, use_cache)
        ts_transcript_task = self.get_transcript_with_timestamps(url, use_cache)
        
        info, transcript, (ts_transcript, ts_list) = await asyncio.gather(
            info_task, transcript_task, ts_transcript_task,
            return_exceptions=True
        )
        
        # Handle exceptions
        if isinstance(info, Exception):
            logger.error(f"Error getting video info: {info}")
            info = None
        if isinstance(transcript, Exception):
            logger.error(f"Error getting transcript: {transcript}")
            transcript = None
        if isinstance(ts_transcript, Exception):
            logger.error(f"Error getting timestamped transcript: {ts_transcript}")
            ts_transcript, ts_list = None, None
        
        return {
            "video_id": video_id,
            "url": url,
            "info": info,
            "transcript": transcript,
            "timestamped_transcript": ts_transcript,
            "transcript_list": ts_list
        }