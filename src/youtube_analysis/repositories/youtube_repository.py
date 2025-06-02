"""Repository for YouTube data access with connection pooling."""

import asyncio
import aiohttp
from typing import Optional, List, Dict, Any
from urllib.parse import urlparse, parse_qs
import re
from datetime import datetime, timedelta

from ..models import VideoData, VideoInfo, TranscriptSegment
from ..core import YouTubeClient, CacheManager
from ..utils.logging import get_logger
from ..core.config import config

logger = get_logger("youtube_repository")


class YouTubeRepository:
    """
    Repository for YouTube data access with advanced features:
    - Connection pooling
    - Rate limiting
    - Retry logic
    - Concurrent request handling
    """
    
    def __init__(self, youtube_client: YouTubeClient, max_connections: int = None):
        self.youtube_client = youtube_client
        self.max_connections = max_connections or config.network.http_keepalive_timeout
        self._session: Optional[aiohttp.ClientSession] = None
        self._rate_limiter = asyncio.Semaphore(10)  # 10 concurrent requests
        self._request_times: List[datetime] = []
        
        logger.info(f"Initialized YouTubeRepository with max_connections={self.max_connections}")
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session with connection pooling."""
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(
                limit=self.max_connections,
                limit_per_host=20,
                ttl_dns_cache=300,
                use_dns_cache=True,
                keepalive_timeout=config.network.http_keepalive_timeout,
                enable_cleanup_closed=True
            )
            
            timeout = aiohttp.ClientTimeout(
                total=config.network.http_timeout_total, 
                connect=config.network.http_timeout_connect
            )
            
            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers={
                    'User-Agent': 'YouTube-Analysis-Tool/1.0'
                }
            )
            
            logger.info("Created new HTTP session with connection pooling")
        
        return self._session
    
    async def _rate_limit(self) -> None:
        """Apply rate limiting to prevent API overload."""
        now = datetime.now()
        
        # Remove old requests (older than 1 minute)
        self._request_times = [
            req_time for req_time in self._request_times
            if now - req_time < timedelta(minutes=1)
        ]
        
        # If too many requests in the last minute, wait
        if len(self._request_times) >= 50:  # 50 requests per minute limit
            sleep_time = 60 - (now - self._request_times[0]).total_seconds()
            if sleep_time > 0:
                logger.info(f"Rate limiting: sleeping for {sleep_time:.2f} seconds")
                await asyncio.sleep(sleep_time)
        
        self._request_times.append(now)
    
    async def get_video_data(self, youtube_url: str) -> Optional[VideoData]:
        """
        Get complete video data including metadata and transcript.
        
        Args:
            youtube_url: YouTube video URL
            
        Returns:
            VideoData object or None if failed
        """
        async with self._rate_limiter:
            await self._rate_limit()
            
            try:
                video_id = self.extract_video_id(youtube_url)
                if not video_id:
                    logger.error(f"Invalid YouTube URL: {youtube_url}")
                    return None
                
                logger.info(f"Fetching video data for {video_id}")
                
                # Fetch video info and transcript concurrently
                video_info_task = self._get_video_info(youtube_url)
                transcript_task = self._get_transcript_data(youtube_url)
                
                video_info_obj, transcript_data = await asyncio.gather(
                    video_info_task,
                    transcript_task,
                    return_exceptions=True
                )
                
                # Handle video info result
                if isinstance(video_info_obj, Exception):
                    logger.error(f"Error fetching video info: {str(video_info_obj)}")
                    video_info_obj = None
                
                # Handle transcript result
                if isinstance(transcript_data, Exception):
                    logger.error(f"Error fetching transcript: {str(transcript_data)}")
                    transcript_data = (None, None, None)
                
                # Create VideoInfo
                if video_info_obj:
                    video_info = VideoInfo(
                        video_id=video_id,
                        title=video_info_obj.title,
                        description=video_info_obj.description,
                        duration=getattr(video_info_obj, 'duration', None),
                        view_count=getattr(video_info_obj, 'view_count', None),
                        like_count=getattr(video_info_obj, 'like_count', None),
                        channel_name=getattr(video_info_obj, 'channel_name', None),
                        channel_id=getattr(video_info_obj, 'channel_id', None),
                        thumbnail_url=getattr(video_info_obj, 'thumbnail_url', None)
                    )
                else:
                    video_info = VideoInfo(
                        video_id=video_id,
                        title=f"YouTube Video ({video_id})",
                        description="Video information unavailable"
                    )
                
                # Extract transcript data
                transcript, timestamped_transcript, transcript_segments = transcript_data
                
                # Create VideoData
                video_data = VideoData(
                    video_info=video_info,
                    transcript=transcript,
                    timestamped_transcript=timestamped_transcript,
                    transcript_segments=transcript_segments
                )
                
                logger.info(f"Successfully fetched video data for {video_id}")
                return video_data
                
            except Exception as e:
                logger.error(f"Error fetching video data for {youtube_url}: {str(e)}", exc_info=True)
                return None
    
    async def _get_video_info(self, youtube_url: str):
        """Get video info using YouTube client."""
        return await self.youtube_client.get_video_info(youtube_url)
    
    async def _get_transcript_data(self, youtube_url: str) -> tuple:
        """Get transcript data using YouTube client."""
        try:
            # Get basic transcript
            transcript = await self.youtube_client.get_transcript(youtube_url)
            
            # Get transcript with timestamps
            timestamped_result = await self.youtube_client.get_transcript_with_timestamps(youtube_url)
            
            if timestamped_result and len(timestamped_result) == 2:
                timestamped_transcript, transcript_list = timestamped_result
                
                # Convert to TranscriptSegment objects
                transcript_segments = []
                if transcript_list:
                    for item in transcript_list:
                        segment = TranscriptSegment(
                            text=item.get('text', ''),
                            start=item.get('start', 0),
                            duration=item.get('duration')
                        )
                        transcript_segments.append(segment)
                
                return transcript, timestamped_transcript, transcript_segments
            else:
                return transcript, None, None
                
        except Exception as e:
            logger.error(f"Error getting transcript data: {str(e)}")
            return None, None, None
    
    def extract_video_id(self, youtube_url: str) -> Optional[str]:
        """Extract video ID from YouTube URL."""
        return self.youtube_client.extract_video_id(youtube_url)
    
    async def validate_youtube_url(self, youtube_url: str) -> bool:
        """Validate if YouTube URL is accessible."""
        try:
            session = await self._get_session()
            
            async with self._rate_limiter:
                await self._rate_limit()
                
                async with session.head(youtube_url) as response:
                    return response.status == 200
                    
        except Exception as e:
            logger.error(f"Error validating YouTube URL {youtube_url}: {str(e)}")
            return False
    
    async def get_video_metadata_batch(self, video_urls: List[str]) -> List[Optional[VideoInfo]]:
        """
        Get metadata for multiple videos concurrently.
        
        Args:
            video_urls: List of YouTube URLs
            
        Returns:
            List of VideoInfo objects (None for failed requests)
        """
        async def get_single_metadata(url: str) -> Optional[VideoInfo]:
            video_data = await self.get_video_data(url)
            return video_data.video_info if video_data else None
        
        # Process in batches to avoid overwhelming the API
        batch_size = 5
        results = []
        
        for i in range(0, len(video_urls), batch_size):
            batch = video_urls[i:i + batch_size]
            batch_tasks = [get_single_metadata(url) for url in batch]
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            
            # Handle exceptions
            batch_results = [
                result if not isinstance(result, Exception) else None
                for result in batch_results
            ]
            
            results.extend(batch_results)
            
            # Small delay between batches
            if i + batch_size < len(video_urls):
                await asyncio.sleep(1)
        
        logger.info(f"Processed {len(video_urls)} videos, {sum(1 for r in results if r)} successful")
        return results
    
    async def cleanup(self) -> None:
        """Cleanup repository resources."""
        if self._session and not self._session.closed:
            await self._session.close()
            logger.info("Closed HTTP session")
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection statistics."""
        if self._session and hasattr(self._session.connector, '_conns'):
            connector = self._session.connector
            total_connections = sum(len(conns) for conns in connector._conns.values())
            
            return {
                "total_connections": total_connections,
                "max_connections": self.max_connections,
                "session_closed": self._session.closed if self._session else True,
                "recent_requests": len(self._request_times)
            }
        
        return {
            "total_connections": 0,
            "max_connections": self.max_connections,
            "session_closed": True,
            "recent_requests": len(self._request_times)
        }