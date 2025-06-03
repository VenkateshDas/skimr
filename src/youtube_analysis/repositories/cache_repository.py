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
from ..models import VideoData, AnalysisResult, ChatSession, TokenUsageCache, TokenUsage
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
            
            # Check if the cached value is a coroutine (corrupted cache)
            if asyncio.iscoroutine(entry.value):
                logger.warning(f"Found corrupted cache entry (coroutine) for {full_key}, removing")
                del self._memory_cache[full_key]
            elif not entry.is_expired:
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
            # Validate cached value is not corrupted
            if asyncio.iscoroutine(cached_value):
                logger.warning(f"Found corrupted persistent cache entry (coroutine) for {full_key}, ignoring")
                cached_value = None
            else:
                # Add to memory cache
                await self._store_in_memory(full_key, cached_value, ttl_hours)
                logger.debug(f"Persistent cache hit for {full_key}")
                return cached_value
        
        # Cache miss - fetch fresh data
        logger.info(f"Cache miss for {full_key}, fetching fresh data")
        try:
            # Check if fetch_fn is a coroutine function
            if asyncio.iscoroutinefunction(fetch_fn):
                fresh_value = await fetch_fn()
            else:
                fresh_value = await self._run_in_executor(fetch_fn)
            
            # Validate that fresh_value is not a coroutine before caching
            if asyncio.iscoroutine(fresh_value):
                logger.error(f"fetch_fn returned a coroutine instead of data for {full_key}, not caching")
                return None
                
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
        
        # Validate value is not a coroutine
        if asyncio.iscoroutine(value):
            logger.error(f"Cannot cache coroutine object for {full_key}")
            return
        
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
            # Validate value is not a coroutine
            if asyncio.iscoroutine(value):
                logger.error(f"Cannot store coroutine in memory cache for {full_key}")
                return
            
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
                # Check if fetch_fn is a coroutine function
                if asyncio.iscoroutinefunction(fetch_fn):
                    fresh_value = await fetch_fn()
                else:
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
    """Repository for caching video analysis data with comprehensive token usage tracking."""
    
    def __init__(self, cache_manager: CacheManager):
        self.smart_cache = SmartCacheRepository(cache_manager)
        self.cache_manager = cache_manager
        logger.info("Initialized CacheRepository")
    
    async def get_video_data(self, video_id: str) -> Optional[VideoData]:
        """Get cached video data."""
        async def fetch_fresh():
            return None  # Will be fetched by service if needed
        
        try:
            cached_data = await self.smart_cache.get_with_fallback(
                "video_data", 
                video_id, 
                fetch_fresh,
                ttl_hours=168  # 1 week
            )
            
            if cached_data and isinstance(cached_data, dict):
                return VideoData.from_dict(cached_data)
            elif cached_data and hasattr(cached_data, 'video_id'):
                # Already a VideoData object
                return cached_data
                
            return None
        except Exception as e:
            logger.error(f"Error getting video data for {video_id}: {str(e)}")
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
    
    async def save_analysis_result(self, video_id: str, result: AnalysisResult) -> None:
        """Store analysis result (alias for store_analysis_result)."""
        await self.store_analysis_result(result)
    
    async def clear_corrupted_cache_entries(self) -> None:
        """Clear any corrupted cache entries (coroutines)."""
        try:
            logger.info("Scanning for corrupted cache entries...")
            
            # Clear corrupted memory cache entries
            keys_to_remove = []
            for key, entry in self.smart_cache._memory_cache.items():
                if asyncio.iscoroutine(entry.value):
                    keys_to_remove.append(key)
                    logger.warning(f"Found corrupted memory cache entry: {key}")
            
            for key in keys_to_remove:
                del self.smart_cache._memory_cache[key]
                logger.info(f"Removed corrupted memory cache entry: {key}")
            
            # Clear corrupted persistent cache entries
            # Note: This is more complex as we'd need to iterate through all cache entries
            # For now, we'll handle this case-by-case during get operations
            
            if keys_to_remove:
                logger.info(f"Cleared {len(keys_to_remove)} corrupted cache entries")
            else:
                logger.debug("No corrupted cache entries found")
                
        except Exception as e:
            logger.error(f"Error clearing corrupted cache entries: {str(e)}")

    async def clear_video_cache(self, video_id: str) -> None:
        """
        Clear all cached data for a specific video.
        
        Args:
            video_id: Video ID to clear cache for
        """
        try:
            logger.info(f"Clearing cache for video {video_id}")
            
            # Clear from memory cache
            keys_to_remove = []
            for key in self.smart_cache._memory_cache.keys():
                if video_id in key:
                    keys_to_remove.append(key)
            
            for key in keys_to_remove:
                del self.smart_cache._memory_cache[key]
                logger.debug(f"Removed from memory cache: {key}")
            
            # Clear from persistent cache using the cache manager
            # Clear video data
            self.smart_cache.cache_manager.delete("video_data", video_id)
            
            # Clear analysis result
            self.smart_cache.cache_manager.delete("analysis", f"analysis_{video_id}")
            
            # Clear any chat sessions (old format)
            self.smart_cache.cache_manager.delete("chat", f"chat_{video_id}")
            
            # Clear new chat sessions
            self.smart_cache.cache_manager.delete("chat_session", f"chat_{video_id}")
            
            # Clear translations
            await self.delete_custom_data("translations", f"translated_transcript_{video_id}_*")
            
            logger.info(f"Successfully cleared cache for video {video_id}")
            
        except Exception as e:
            logger.error(f"Error clearing cache for video {video_id}: {str(e)}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return self.smart_cache.get_cache_stats()
    
    async def cleanup(self) -> None:
        """Cleanup cache repository."""
        await self.smart_cache.cleanup()

    # Chat Session Caching Methods
    async def get_chat_session(self, video_id: str) -> Optional[ChatSession]:
        """Get cached chat session for a video."""
        async def fetch_fresh():
            return None  # Chat sessions are created on-demand
        
        data = await self.smart_cache.get_with_fallback(
            "chat_session", f"chat_{video_id}", fetch_fresh, ttl_hours=168  # 1 week
        )
        
        if data is None:
            return None
            
        # Check if data is a dictionary
        if not isinstance(data, dict):
            logger.error(f"Invalid chat session data type: {type(data)}, expected dict")
            return None
        
        try:
            # Validate required fields are present
            if "session_id" not in data or "video_id" not in data or "youtube_url" not in data:
                logger.error(f"Missing required fields in chat session data for video {video_id}")
                return None
                
            return ChatSession.from_dict(data)
        except Exception as e:
            logger.error(f"Error creating ChatSession from data: {str(e)}")
            logger.error(f"Data type: {type(data)}")
            logger.error(f"Data preview: {str(data)[:200]}...")
            return None
    
    async def store_chat_session(self, chat_session: ChatSession) -> None:
        """Store chat session in cache."""
        try:
            # Convert to dictionary for storage
            chat_data = chat_session.to_dict()
            
            # Validate the dictionary is JSON serializable
            try:
                json.dumps(chat_data, default=str)
            except (TypeError, ValueError) as e:
                logger.error(f"chat_session data is not JSON serializable: {str(e)}")
                # Try to clean the dictionary
                chat_data = self._clean_dict_for_serialization(chat_data)
            
            # Store in cache with TTL (1 week)
            await self.smart_cache.set_with_ttl(
                "chat_session", f"chat_{chat_session.video_id}", chat_data, ttl_hours=168
            )
            logger.info(f"Stored chat session in cache for video {chat_session.video_id} with {len(chat_session.messages)} messages")
            
        except Exception as e:
            logger.error(f"Error storing chat session in cache: {str(e)}")
    
    async def update_chat_session_messages(self, video_id: str, messages: List[Dict[str, Any]]) -> None:
        """Update just the messages in an existing chat session."""
        try:
            # Get existing chat session
            chat_session = await self.get_chat_session(video_id)
            
            if chat_session is None:
                logger.warning(f"No existing chat session found for video {video_id}, cannot update messages")
                return
            
            # Convert messages to ChatMessage objects
            from ..models import ChatMessage, MessageRole
            chat_messages = []
            for msg_data in messages:
                if isinstance(msg_data, dict):
                    # Handle different message formats
                    role_str = msg_data.get("role", "user")
                    content = msg_data.get("content", "")
                    
                    try:
                        role = MessageRole(role_str)
                    except ValueError:
                        # Default to USER if role is invalid
                        role = MessageRole.USER
                    
                    chat_message = ChatMessage(
                        role=role,
                        content=content,
                        metadata=msg_data.get("metadata")
                    )
                    chat_messages.append(chat_message)
            
            # Update the chat session messages
            chat_session.messages = chat_messages
            chat_session.updated_at = datetime.now()
            
            # Store the updated session
            await self.store_chat_session(chat_session)
            logger.info(f"Updated chat session messages for video {video_id} - {len(chat_messages)} messages")
            
        except Exception as e:
            logger.error(f"Error updating chat session messages for video {video_id}: {str(e)}")
    
    async def clear_chat_session(self, video_id: str) -> None:
        """Clear chat session for a specific video."""
        try:
            # Clear from memory cache
            chat_key = f"chat_session:chat_{video_id}"
            if chat_key in self.smart_cache._memory_cache:
                del self.smart_cache._memory_cache[chat_key]
                logger.debug(f"Removed chat session from memory cache: {chat_key}")
            
            # Clear from persistent cache
            self.smart_cache.cache_manager.delete("chat_session", f"chat_{video_id}")
            
            logger.info(f"Successfully cleared chat session for video {video_id}")
            
        except Exception as e:
            logger.error(f"Error clearing chat session for video {video_id}: {str(e)}")

    # Token Usage Caching Methods
    async def get_token_usage_cache(self, video_id: str) -> Optional[TokenUsageCache]:
        """
        Get cached token usage data for a video.
        
        Args:
            video_id: Video ID
            
        Returns:
            TokenUsageCache object or None if not found
        """
        try:
            cached_data = await self.smart_cache.get_with_fallback(
                "token_usage",
                video_id,
                lambda: None,  # No fallback for token usage
                ttl_hours=168  # 1 week
            )
            
            if cached_data and isinstance(cached_data, dict):
                return TokenUsageCache.from_dict(cached_data)
            elif cached_data and hasattr(cached_data, 'video_id'):
                # Already a TokenUsageCache object
                return cached_data
                
            return None
            
        except Exception as e:
            logger.error(f"Error getting token usage cache for {video_id}: {str(e)}")
            return None
    
    async def store_token_usage_cache(self, token_usage_cache: TokenUsageCache) -> None:
        """
        Store token usage cache for a video.
        
        Args:
            token_usage_cache: TokenUsageCache object to store
        """
        try:
            await self.smart_cache.set_with_ttl(
                "token_usage",
                token_usage_cache.video_id,
                token_usage_cache.to_dict(),
                ttl_hours=168  # 1 week
            )
            logger.info(f"Stored token usage cache for video {token_usage_cache.video_id}")
            
        except Exception as e:
            logger.error(f"Error storing token usage cache: {str(e)}")
    
    async def update_token_usage_cache(
        self, 
        video_id: str, 
        operation_type: str, 
        token_usage: TokenUsage,
        operation_name: Optional[str] = None
    ) -> None:
        """
        Update token usage cache for a specific operation.
        
        Args:
            video_id: Video ID
            operation_type: Type of operation ('initial_analysis', 'additional_content', 'chat')
            token_usage: TokenUsage object
            operation_name: Name of the specific operation (for additional_content)
        """
        try:
            # Get existing cache or create new one
            token_cache = await self.get_token_usage_cache(video_id)
            if token_cache is None:
                token_cache = TokenUsageCache(video_id=video_id)
            
            # Update based on operation type
            if operation_type == "initial_analysis":
                token_cache.add_initial_analysis(token_usage)
                logger.info(f"Added initial analysis token usage for {video_id}: {token_usage.to_dict()}")
                
            elif operation_type == "additional_content" and operation_name:
                token_cache.add_additional_content(operation_name, token_usage)
                logger.info(f"Added {operation_name} token usage for {video_id}: {token_usage.to_dict()}")
                
            elif operation_type == "chat":
                token_cache.add_chat_usage(token_usage)
                logger.info(f"Added chat token usage for {video_id}: {token_usage.to_dict()}")
            
            # Store updated cache
            await self.store_token_usage_cache(token_cache)
            
        except Exception as e:
            logger.error(f"Error updating token usage cache for {video_id}: {str(e)}")
    
    async def clear_token_usage_cache(self, video_id: str) -> None:
        """
        Clear token usage cache for a video.
        
        Args:
            video_id: Video ID
        """
        try:
            self.cache_manager.delete("token_usage", video_id)
            logger.info(f"Cleared token usage cache for video {video_id}")
            
        except Exception as e:
            logger.error(f"Error clearing token usage cache for {video_id}: {str(e)}")
    
    async def get_token_usage_for_session_manager(self, video_id: str) -> Optional[Dict[str, Any]]:
        """
        Get token usage data in the format expected by StreamlitSessionManager.
        
        Args:
            video_id: Video ID
            
        Returns:
            Dictionary with 'cumulative_usage' and 'breakdown' keys, or None if not found
        """
        try:
            token_cache = await self.get_token_usage_cache(video_id)
            if token_cache:
                return token_cache.to_session_manager_format()
            return None
            
        except Exception as e:
            logger.error(f"Error getting token usage for session manager: {str(e)}")
            return None

    async def get_custom_data(self, category: str, key: str) -> Optional[Dict[str, Any]]:
        """
        Get custom data from cache by category and key.
        
        Args:
            category: Data category (e.g., 'transcripts', 'whisper')
            key: Unique identifier for the data
            
        Returns:
            Cached data or None if not found/expired
        """
        async def fetch_fresh():
            return None  # Will be handled by service layer
            
        try:
            cache_key = f"{category}_{key}"
            data = await self.smart_cache.get_with_fallback(
                category, cache_key, fetch_fresh, ttl_hours=168  # 1 week
            )
            
            return data
        except Exception as e:
            logger.error(f"Error getting custom data for {category}/{key}: {str(e)}")
            return None
            
    async def store_custom_data(self, category: str, key: str, data: Dict[str, Any], ttl_hours: int = 168) -> None:
        """
        Store custom data in cache.
        
        Args:
            category: Data category (e.g., 'transcripts', 'whisper')
            key: Unique identifier for the data
            data: Data to store
            ttl_hours: Cache TTL in hours (default: 1 week)
        """
        try:
            # Validate data
            if not isinstance(data, dict):
                logger.error(f"Invalid data type for custom data: {type(data)}, expected dict")
                return
                
            # Ensure the dictionary is JSON serializable
            try:
                json.dumps(data, default=str)
            except (TypeError, ValueError) as e:
                logger.error(f"Data is not JSON serializable: {str(e)}")
                # Try to clean the dictionary
                data = self._clean_dict_for_serialization(data)
                
            # Store in cache with TTL
            cache_key = f"{category}_{key}"
            await self.smart_cache.set_with_ttl(
                category, cache_key, data, ttl_hours=ttl_hours
            )
            logger.info(f"Stored custom data in cache for {category}/{key}")
        except Exception as e:
            logger.error(f"Error storing custom data in cache: {str(e)}")
    
    async def clear_custom_data(self, category: str, key: str) -> None:
        """
        Clear custom data from cache.
        
        Args:
            category: Data category (e.g., 'transcripts', 'whisper')
            key: Unique identifier for the data
        """
        try:
            cache_key = f"{category}_{key}"
            
            # Remove from memory cache in smart repository
            memory_key = f"{category}:{cache_key}"
            if hasattr(self.smart_cache, '_memory_cache') and memory_key in self.smart_cache._memory_cache:
                del self.smart_cache._memory_cache[memory_key]
                
            # Remove from persistent cache
            self.cache_manager.delete(category, cache_key)
            
            logger.info(f"Cleared custom data from cache for {category}/{key}")
        except Exception as e:
            logger.error(f"Error clearing custom data from cache: {str(e)}")

    async def delete_custom_data(self, data_type: str, key_pattern: str) -> bool:
        """
        Delete custom data entries matching a pattern.
        
        Args:
            data_type: Type of custom data (e.g., "translations")
            key_pattern: Key pattern with optional wildcard (*) 
                        e.g., "translated_transcript_abc123_*" to match all languages
            
        Returns:
            True if successful, False otherwise
        """
        try:
            is_wildcard = "*" in key_pattern
            if is_wildcard:
                # Handle wildcard pattern
                base_pattern = key_pattern.replace("*", "")
                
                # First clear from memory cache
                keys_to_remove = []
                for cache_key in self.smart_cache._memory_cache.keys():
                    if cache_key.startswith(f"{data_type}:{base_pattern}"):
                        keys_to_remove.append(cache_key)
                
                for key in keys_to_remove:
                    del self.smart_cache._memory_cache[key]
                    logger.debug(f"Removed from memory cache: {key}")
                
                # Then clear from persistent cache
                # Get all keys in the namespace
                all_keys = self.cache_manager.get_all_keys(data_type)
                if all_keys:
                    for key in all_keys:
                        if key.startswith(base_pattern):
                            self.cache_manager.delete(data_type, key)
                            logger.debug(f"Removed from persistent cache: {data_type}:{key}")
            else:
                # Direct key deletion
                cache_key = f"{data_type}:{key_pattern}"
                
                # Clear from memory cache
                if cache_key in self.smart_cache._memory_cache:
                    del self.smart_cache._memory_cache[cache_key]
                    logger.debug(f"Removed from memory cache: {cache_key}")
                
                # Clear from persistent cache
                self.cache_manager.delete(data_type, key_pattern)
                
            logger.info(f"Successfully deleted custom data matching {data_type}:{key_pattern}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting custom data {data_type}:{key_pattern}: {str(e)}")
            return False