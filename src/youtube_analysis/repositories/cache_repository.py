"""Repository for cache operations with advanced features."""

import asyncio
import weakref
from typing import Dict, Any, Optional, List, Callable, TypeVar, Generic
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor
import logging
import json
import hashlib

from ..core import CacheManager
from ..models import VideoData, AnalysisResult, ChatSession
from ..utils.logging import get_logger

logger = get_logger("cache_repository")

T = TypeVar('T')


@dataclass
class CacheEntry(Generic[T]):
    """Represents a cache entry with metadata."""
    key: str
    value: T
    created_at: datetime
    expires_at: Optional[datetime] = None
    access_count: int = 0
    last_accessed: datetime = field(default_factory=datetime.now)
    size_bytes: Optional[int] = None
    
    @property
    def is_expired(self) -> bool:
        """Check if entry is expired."""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at
    
    @property
    def age_seconds(self) -> float:
        """Get age in seconds."""
        return (datetime.now() - self.created_at).total_seconds()
    
    @property
    def ttl_seconds(self) -> Optional[float]:
        """Get time to live in seconds."""
        if self.expires_at is None:
            return None
        return max(0, (self.expires_at - datetime.now()).total_seconds())


class SmartCacheRepository:
    """
    Advanced cache repository with smart features:
    - Background refresh for near-expiry items
    - Memory monitoring and cleanup
    - Access pattern tracking
    - Compressed storage for large objects
    """
    
    def __init__(self, cache_manager: CacheManager, max_memory_mb: int = 500):
        self.cache_manager = cache_manager
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self._memory_cache: Dict[str, CacheEntry] = {}
        self._weak_refs: weakref.WeakValueDictionary = weakref.WeakValueDictionary()
        self._background_tasks: Dict[str, asyncio.Task] = {}
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="cache")
        self._refresh_callbacks: Dict[str, Callable] = {}
        
        # Initialize cleanup task as None, will be started when needed
        self._cleanup_task = None
        logger.info(f"Initialized SmartCacheRepository with {max_memory_mb}MB memory limit")
    
    def _ensure_cleanup_task(self):
        """Ensure cleanup task is running."""
        if self._cleanup_task is None or self._cleanup_task.done():
            try:
                self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
            except RuntimeError:
                # No event loop running, cleanup will be started later
                pass
    
    async def get_with_fallback(
        self, 
        cache_type: str, 
        key: str, 
        fetch_fn: Callable[[], Any],
        ttl_hours: int = 24,
        refresh_threshold: float = 0.8
    ) -> Optional[Any]:
        """
        Get value with automatic fallback and background refresh.
        
        Args:
            cache_type: Type of cache (e.g., 'analysis', 'transcript')
            key: Cache key
            fetch_fn: Function to fetch fresh data
            ttl_hours: Time to live in hours
            refresh_threshold: When to trigger background refresh (0.8 = 80% of TTL)
        """
        # Ensure cleanup task is running
        self._ensure_cleanup_task()
        
        full_key = f"{cache_type}:{key}"
        
        # Check memory cache first
        if full_key in self._memory_cache:
            entry = self._memory_cache[full_key]
            entry.access_count += 1
            entry.last_accessed = datetime.now()
            
            if not entry.is_expired:
                # Check if needs background refresh
                if entry.ttl_seconds and entry.ttl_seconds < (ttl_hours * 3600 * (1 - refresh_threshold)):
                    await self._schedule_background_refresh(full_key, fetch_fn, ttl_hours)
                
                logger.debug(f"Memory cache hit for {full_key}")
                return entry.value
            else:
                # Remove expired entry
                del self._memory_cache[full_key]
        
        # Check persistent cache
        cached_value = self.cache_manager.get(cache_type, key)
        if cached_value:
            # Add to memory cache
            await self._store_in_memory(full_key, cached_value, ttl_hours)
            logger.debug(f"Persistent cache hit for {full_key}")
            return cached_value
        
        # Cache miss - fetch fresh data
        logger.info(f"Cache miss for {full_key}, fetching fresh data")
        try:
            fresh_value = await self._run_in_executor(fetch_fn)
            if fresh_value:
                await self.set_with_ttl(cache_type, key, fresh_value, ttl_hours)
            return fresh_value
        except Exception as e:
            logger.error(f"Error fetching fresh data for {full_key}: {str(e)}")
            return None
    
    async def set_with_ttl(
        self, 
        cache_type: str, 
        key: str, 
        value: Any, 
        ttl_hours: int = 24
    ) -> None:
        """Set value with TTL in both memory and persistent cache."""
        full_key = f"{cache_type}:{key}"
        
        # Store in persistent cache
        try:
            self.cache_manager.set(cache_type, key, value)
            logger.debug(f"Stored in persistent cache: {full_key}")
        except Exception as e:
            logger.error(f"Error storing in persistent cache {full_key}: {str(e)}")
        
        # Store in memory cache
        await self._store_in_memory(full_key, value, ttl_hours)
    
    async def _store_in_memory(self, full_key: str, value: Any, ttl_hours: int) -> None:
        """Store value in memory cache with size tracking."""
        try:
            # Calculate size
            size_bytes = len(json.dumps(value, default=str).encode('utf-8'))
            
            # Check memory limit
            await self._ensure_memory_limit(size_bytes)
            
            # Create cache entry
            expires_at = datetime.now() + timedelta(hours=ttl_hours)
            entry = CacheEntry(
                key=full_key,
                value=value,
                created_at=datetime.now(),
                expires_at=expires_at,
                size_bytes=size_bytes
            )
            
            self._memory_cache[full_key] = entry
            logger.debug(f"Stored in memory cache: {full_key} ({size_bytes} bytes)")
            
        except Exception as e:
            logger.error(f"Error storing in memory cache {full_key}: {str(e)}")
    
    async def _ensure_memory_limit(self, new_size: int) -> None:
        """Ensure memory usage stays within limits."""
        current_size = sum(
            entry.size_bytes or 0 
            for entry in self._memory_cache.values()
        )
        
        if current_size + new_size > self.max_memory_bytes:
            logger.info(f"Memory limit exceeded, cleaning up cache")
            await self._cleanup_memory_cache(target_size=self.max_memory_bytes * 0.7)
    
    async def _cleanup_memory_cache(self, target_size: float) -> None:
        """Clean up memory cache to target size."""
        entries = list(self._memory_cache.items())
        
        # Sort by access pattern (LRU + access count)
        entries.sort(key=lambda x: (
            x[1].last_accessed.timestamp(),
            x[1].access_count
        ))
        
        current_size = sum(entry.size_bytes or 0 for _, entry in entries)
        
        # Remove entries until we reach target size
        for key, entry in entries:
            if current_size <= target_size:
                break
            
            current_size -= (entry.size_bytes or 0)
            del self._memory_cache[key]
            logger.debug(f"Evicted from memory cache: {key}")
    
    async def _schedule_background_refresh(
        self, 
        full_key: str, 
        fetch_fn: Callable, 
        ttl_hours: int
    ) -> None:
        """Schedule background refresh for near-expiry items."""
        if full_key in self._background_tasks:
            return  # Already scheduled
        
        async def refresh_task():
            try:
                logger.info(f"Background refresh for {full_key}")
                fresh_value = await self._run_in_executor(fetch_fn)
                if fresh_value:
                    cache_type, key = full_key.split(':', 1)
                    await self.set_with_ttl(cache_type, key, fresh_value, ttl_hours)
                    logger.info(f"Background refresh completed for {full_key}")
            except Exception as e:
                logger.error(f"Background refresh failed for {full_key}: {str(e)}")
            finally:
                # Clean up task reference
                if full_key in self._background_tasks:
                    del self._background_tasks[full_key]
        
        task = asyncio.create_task(refresh_task())
        self._background_tasks[full_key] = task
    
    async def _run_in_executor(self, func: Callable) -> Any:
        """Run blocking function in executor."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, func)
    
    async def _periodic_cleanup(self) -> None:
        """Periodic cleanup of expired entries."""
        while True:
            try:
                await asyncio.sleep(300)  # Run every 5 minutes
                
                # Clean expired memory cache entries
                expired_keys = [
                    key for key, entry in self._memory_cache.items()
                    if entry.is_expired
                ]
                
                for key in expired_keys:
                    del self._memory_cache[key]
                    logger.debug(f"Cleaned expired entry: {key}")
                
                if expired_keys:
                    logger.info(f"Cleaned {len(expired_keys)} expired cache entries")
                
            except Exception as e:
                logger.error(f"Error in periodic cleanup: {str(e)}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_size = sum(
            entry.size_bytes or 0 
            for entry in self._memory_cache.values()
        )
        
        total_accesses = sum(
            entry.access_count 
            for entry in self._memory_cache.values()
        )
        
        return {
            "memory_entries": len(self._memory_cache),
            "memory_size_mb": total_size / (1024 * 1024),
            "memory_limit_mb": self.max_memory_bytes / (1024 * 1024),
            "memory_utilization": total_size / self.max_memory_bytes,
            "total_accesses": total_accesses,
            "background_tasks": len(self._background_tasks),
            "avg_entry_size_kb": (total_size / len(self._memory_cache) / 1024) if self._memory_cache else 0
        }
    
    async def cleanup(self) -> None:
        """Cleanup resources."""
        # Cancel background tasks
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
        
        for task in self._background_tasks.values():
            task.cancel()
        
        # Shutdown executor
        self._executor.shutdown(wait=True)
        
        logger.info("SmartCacheRepository cleanup completed")


class CacheRepository:
    """Main cache repository using SmartCacheRepository."""
    
    def __init__(self, cache_manager: CacheManager):
        self.smart_cache = SmartCacheRepository(cache_manager)
        logger.info("Initialized CacheRepository")
    
    async def get_video_data(self, video_id: str) -> Optional[VideoData]:
        """Get cached video data."""
        async def fetch_fresh():
            return None  # Will be handled by service layer
        
        data = await self.smart_cache.get_with_fallback(
            "video_data", video_id, fetch_fresh, ttl_hours=24
        )
        
        # Defensive: Only try to parse if the structure is correct
        if data and isinstance(data, dict) and "video_id" in data and "transcript" in data:
            try:
                return VideoData.from_dict(data)
            except Exception as e:
                logger.error(f"Failed to parse VideoData from cache for {video_id}: {e}")
                return None
        else:
            logger.warning(f"Cached video data for {video_id} is missing required fields or is not a dict: {data}")
            return None
    
    async def store_video_data(self, video_data: VideoData) -> None:
        """
        Store video data in cache.
        
        Args:
            video_data: VideoData object to store
        """
        try:
            # Handle coroutine input
            if asyncio.iscoroutine(video_data):
                logger.warning("store_video_data received a coroutine, resolving it")
                try:
                    video_data = await video_data
                except Exception as e:
                    logger.error(f"Failed to resolve video_data coroutine: {str(e)}")
                    return
            
            # Validate video_data is not None
            if video_data is None:
                logger.error("Cannot store None video_data")
                return
                
            # Get video_id from the object
            if not hasattr(video_data, 'video_id') and hasattr(video_data, 'video_info'):
                # Try to get video_id from video_info
                if hasattr(video_data.video_info, 'video_id'):
                    video_id = video_data.video_info.video_id
                else:
                    logger.error("Cannot store video data: no video_id attribute found")
                    return
            elif hasattr(video_data, 'video_id'):
                video_id = video_data.video_id
            else:
                logger.error("Cannot store video data: no video_id attribute found")
                return
            
            # Convert to dictionary
            try:
                # Convert to dictionary for storage if it has a to_dict method
                if hasattr(video_data, 'to_dict') and callable(getattr(video_data, 'to_dict')):
                    video_data_dict = video_data.to_dict()
                    logger.debug(f"Converted VideoData object to dictionary for {video_id}")
                else:
                    # Try to convert to dict using __dict__
                    if hasattr(video_data, '__dict__'):
                        video_data_dict = {
                            "video_id": video_id,
                            # Add other fields you can extract
                            "transcript": getattr(video_data, 'transcript', None),
                            "transcript_segments": getattr(video_data, 'transcript_segments', None),
                        }
                        logger.warning(f"VideoData object has no to_dict method, using __dict__ for {video_id}")
                    else:
                        logger.error(f"Cannot convert VideoData to dictionary for {video_id}")
                        return
            except Exception as e:
                logger.error(f"Error converting VideoData to dictionary: {str(e)}")
                return
                
            # Validate the dictionary
            if not isinstance(video_data_dict, dict):
                logger.error(f"Conversion failed: video_data_dict is not a dictionary: {type(video_data_dict)}")
                return
                
            # Ensure the dictionary is JSON serializable
            try:
                json.dumps(video_data_dict, default=str)
            except (TypeError, ValueError) as e:
                logger.error(f"video_data_dict is not JSON serializable: {str(e)}")
                # Try to clean the dictionary
                video_data_dict = self._clean_dict_for_serialization(video_data_dict)
                
            # Store in cache with TTL
            await self.smart_cache.set_with_ttl(
                "video_data", video_id, video_data_dict, ttl_hours=24
            )
            logger.info(f"Stored video data in cache for {video_id}")
            
        except Exception as e:
            logger.error(f"Error storing video data in cache: {str(e)}")
            # Log the type of video_data for debugging
            logger.error(f"video_data type: {type(video_data)}")
            if hasattr(video_data, '__dict__'):
                logger.error(f"video_data attributes: {list(video_data.__dict__.keys())}")
                
    def _clean_dict_for_serialization(self, data_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Clean dictionary to make it JSON serializable."""
        clean_dict = {}
        for key, value in data_dict.items():
            if isinstance(value, dict):
                clean_dict[key] = self._clean_dict_for_serialization(value)
            elif isinstance(value, (list, tuple)):
                clean_dict[key] = [
                    self._clean_dict_for_serialization(item) if isinstance(item, dict) else str(item)
                    if not isinstance(item, (str, int, float, bool, type(None))) else item
                    for item in value
                ]
            elif isinstance(value, (str, int, float, bool, type(None))):
                clean_dict[key] = value
            else:
                # Convert other types to string
                try:
                    clean_dict[key] = str(value)
                except:
                    clean_dict[key] = f"<non-serializable: {type(value).__name__}>"
        return clean_dict
    
    async def get_analysis_result(self, video_id: str) -> Optional[AnalysisResult]:
        """Get cached analysis result."""
        async def fetch_fresh():
            return None  # Will be handled by service layer
        
        data = await self.smart_cache.get_with_fallback(
            "analysis", f"analysis_{video_id}", fetch_fresh, ttl_hours=168  # 1 week
        )
        
        if data is None:
            return None
            
        # Check if data is a dictionary
        if not isinstance(data, dict):
            logger.error(f"Invalid analysis result data type: {type(data)}, expected dict")
            if isinstance(data, str):
                try:
                    # Try to parse string as JSON
                    data = json.loads(data)
                    logger.info(f"Successfully parsed string data as JSON for video {video_id}")
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse string data as JSON for video {video_id}")
                    return None
            else:
                return None
        
        try:
            # Validate required fields are present
            if "video_id" not in data or "youtube_url" not in data or "status" not in data:
                logger.error(f"Missing required fields in analysis result data for video {video_id}")
                return None
                
            return AnalysisResult.from_dict(data)
        except Exception as e:
            logger.error(f"Error creating AnalysisResult from data: {str(e)}")
            logger.error(f"Data type: {type(data)}")
            logger.error(f"Data preview: {str(data)[:200]}...")
            return None
    
    async def store_analysis_result(self, result: AnalysisResult) -> None:
        """Store analysis result."""
        await self.smart_cache.set_with_ttl(
            "analysis", f"analysis_{result.video_id}", result.to_dict(), ttl_hours=168
        )
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return self.smart_cache.get_cache_stats()
    
    async def cleanup(self) -> None:
        """Cleanup cache repository."""
        await self.smart_cache.cleanup()