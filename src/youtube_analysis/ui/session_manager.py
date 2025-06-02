"""
Streamlit session state management utilities.
"""

import asyncio
import streamlit as st
from typing import Dict, Any, Optional
from datetime import datetime
from ..utils.logging import get_logger
from ..core.config import config, get_default_settings

logger = get_logger("session_manager")


class StreamlitSessionManager:
    """Manages Streamlit session state with proper initialization and cleanup."""
    
    @staticmethod
    def initialize_all():
        """Initialize all session state variables."""
        StreamlitSessionManager.initialize_auth_state()
        StreamlitSessionManager.initialize_analysis_state()
        StreamlitSessionManager.initialize_chat_state()
        StreamlitSessionManager.initialize_ui_state()
        StreamlitSessionManager.initialize_settings()
        StreamlitSessionManager.initialize_token_tracking()
        
        logger.info("All session state variables initialized")
    
    @staticmethod
    def initialize_auth_state():
        """Initialize authentication-related session state."""
        auth_defaults = {
            "authenticated": False,
            "user": None,
            "show_auth": False,
            "guest_analysis_count": 0
        }
        
        for key, default_value in auth_defaults.items():
            if key not in st.session_state:
                st.session_state[key] = default_value
    
    @staticmethod
    def initialize_analysis_state():
        """Initialize analysis-related session state."""
        analysis_defaults = {
            "analysis_complete": False,
            "analysis_results": None,
            "analysis_start_time": None,
            "video_id": None,
            "video_url": None,
            "video_info": None,
            "transcript_list": None,
            "transcript_text": None,
            "timestamped_transcript": None,
            "highlights_video_path": None,
            "highlights_segments": None
        }
        
        for key, default_value in analysis_defaults.items():
            if key not in st.session_state:
                st.session_state[key] = default_value
    
    @staticmethod
    def initialize_chat_state():
        """Initialize chat-related session state."""
        chat_defaults = {
            "chat_enabled": False,
            "chat_messages": [],
            "chat_details": None,
            "chat_user_input": None,
            "thinking_message_shown": False,
            "thinking_placeholder": None,
            "user_input_disabled": False
        }
        
        for key, default_value in chat_defaults.items():
            if key not in st.session_state:
                st.session_state[key] = default_value
    
    @staticmethod
    def initialize_ui_state():
        """Initialize UI-related session state."""
        ui_defaults = {
            "current_youtube_url": "",
            "content_generation_pending": False,
            "content_type_generated": None,
            "is_chat_streaming": False,
            "current_chat_question": None,
            "chat_streaming_placeholder": "",
            "chat_streaming_placeholder_ref": None
        }
        
        for key, default_value in ui_defaults.items():
            if key not in st.session_state:
                st.session_state[key] = default_value
    
    @staticmethod
    def initialize_token_tracking():
        """Initialize comprehensive token usage tracking."""
        token_defaults = {
            "cumulative_token_usage": {
                "total_tokens": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0
            },
            "token_usage_breakdown": {
                "initial_analysis": None,
                "additional_content": {},
                "chat": {
                    "total_tokens": 0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "message_count": 0
                }
            }
        }
        
        for key, default_value in token_defaults.items():
            if key not in st.session_state:
                st.session_state[key] = default_value
    
    @staticmethod
    def initialize_settings():
        """Initialize application settings."""
        defaults = {
            "settings": get_default_settings()
        }
        
        for key, default_value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = default_value
    
    @staticmethod
    def reset_analysis_state():
        """Reset analysis-related state for new analysis."""
        analysis_keys = [
            "analysis_complete",
            "analysis_results", 
            "analysis_start_time",
            "video_id",
            "video_url",
            "video_info",
            "transcript_list",
            "transcript_text",
            "timestamped_transcript",
            "chat_enabled",
            "chat_messages",
            "chat_details",
            "highlights_video_path",
            "highlights_segments"
        ]
        
        for key in analysis_keys:
            if key in st.session_state:
                if key == "chat_messages":
                    st.session_state[key] = []
                elif key in ["chat_enabled", "analysis_complete"]:
                    st.session_state[key] = False
                else:
                    st.session_state[key] = None
        
        # Reset token tracking for new analysis
        StreamlitSessionManager.reset_token_tracking()
        
        logger.info("Analysis state reset for new analysis")
    
    @staticmethod
    def reset_token_tracking():
        """Reset token usage tracking for new analysis."""
        # Ensure token tracking is initialized first
        if "cumulative_token_usage" not in st.session_state or "token_usage_breakdown" not in st.session_state:
            StreamlitSessionManager.initialize_token_tracking()
        
        st.session_state.cumulative_token_usage = {
            "total_tokens": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0
        }
        st.session_state.token_usage_breakdown = {
            "initial_analysis": None,
            "additional_content": {},
            "chat": {
                "total_tokens": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "message_count": 0
            }
        }
        logger.info("Token tracking reset for new analysis")
    
    @staticmethod
    def reset_chat_state():
        """Reset chat-related state."""
        chat_keys = [
            "chat_messages",
            "chat_user_input", 
            "thinking_message_shown",
            "thinking_placeholder",
            "user_input_disabled"
        ]
        
        for key in chat_keys:
            if key in st.session_state:
                if key == "chat_messages":
                    st.session_state[key] = []
                elif key in ["thinking_message_shown", "user_input_disabled"]:
                    st.session_state[key] = False
                else:
                    st.session_state[key] = None

        # Reset chat token usage
        if "token_usage_breakdown" in st.session_state:
            st.session_state.token_usage_breakdown["chat"] = {
                "total_tokens": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "message_count": 0
            }
            # Recalculate cumulative usage without chat
            StreamlitSessionManager._recalculate_cumulative_usage()
        else:
            # Ensure token tracking is initialized
            StreamlitSessionManager.initialize_token_tracking()
        
        logger.info("Chat state reset")
    
    @staticmethod
    def add_token_usage(operation_type: str, token_usage: Dict[str, int], operation_name: Optional[str] = None):
        """
        Add token usage for an operation and update cumulative totals.
        Also saves to cache if video_id is available.
        
        Args:
            operation_type: Type of operation ('initial_analysis', 'additional_content', 'chat')
            token_usage: Dict with 'total_tokens', 'prompt_tokens', 'completion_tokens'
            operation_name: Name of the specific operation (for additional_content)
        """
        if "token_usage_breakdown" not in st.session_state:
            StreamlitSessionManager.initialize_token_tracking()
        
        breakdown = st.session_state.token_usage_breakdown
        
        if operation_type == "initial_analysis":
            breakdown["initial_analysis"] = token_usage.copy()
        elif operation_type == "additional_content" and operation_name:
            breakdown["additional_content"][operation_name] = token_usage.copy()
        elif operation_type == "chat":
            # Add to chat totals
            chat_usage = breakdown["chat"]
            chat_usage["total_tokens"] += token_usage.get("total_tokens", 0)
            chat_usage["prompt_tokens"] += token_usage.get("prompt_tokens", 0)
            chat_usage["completion_tokens"] += token_usage.get("completion_tokens", 0)
            chat_usage["message_count"] += 1
        
        # Update breakdown in session state
        st.session_state.token_usage_breakdown = breakdown
        
        # Recalculate cumulative usage
        StreamlitSessionManager._recalculate_cumulative_usage()
        
        logger.info(f"Added token usage for {operation_type}: {token_usage}")
        
        # Auto-save to cache if video_id is available
        video_id = st.session_state.get("video_id")
        webapp_adapter = st.session_state.get("webapp_adapter")
        
        if video_id and webapp_adapter:
            try:
                # Save token usage to cache immediately
                StreamlitSessionManager.auto_save_token_usage(webapp_adapter, video_id)
                logger.debug(f"Auto-saved token usage to cache for video {video_id}")
            except Exception as e:
                logger.warning(f"Auto-save token usage failed (non-critical): {str(e)}")
        elif video_id and not webapp_adapter:
            logger.debug(f"Video ID available ({video_id}) but webapp_adapter not found in session state")
        else:
            logger.debug("Video ID or webapp_adapter not available for auto-save")

    @staticmethod
    def _recalculate_cumulative_usage():
        """Recalculate cumulative token usage from all sources."""
        breakdown = st.session_state.token_usage_breakdown
        cumulative = {
            "total_tokens": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0
        }
        
        # Add initial analysis
        if breakdown.get("initial_analysis"):
            for key in cumulative:
                cumulative[key] += breakdown["initial_analysis"].get(key, 0)
        
        # Add additional content
        for content_usage in breakdown.get("additional_content", {}).values():
            for key in cumulative:
                cumulative[key] += content_usage.get(key, 0)
        
        # Add chat
        chat_usage = breakdown.get("chat", {})
        for key in cumulative:
            cumulative[key] += chat_usage.get(key, 0)
        
        st.session_state.cumulative_token_usage = cumulative

    @staticmethod
    def get_cumulative_token_usage() -> Dict[str, int]:
        """Get cumulative token usage across all operations."""
        if "cumulative_token_usage" not in st.session_state:
            StreamlitSessionManager.initialize_token_tracking()
        return st.session_state.cumulative_token_usage.copy()

    @staticmethod
    def get_token_usage_breakdown() -> Dict[str, Any]:
        """Get detailed token usage breakdown by operation."""
        if "token_usage_breakdown" not in st.session_state:
            StreamlitSessionManager.initialize_token_tracking()
        return st.session_state.token_usage_breakdown.copy()
    
    @staticmethod
    def get_settings() -> Dict[str, Any]:
        """Get current settings from session state."""
        if "settings" not in st.session_state:
            StreamlitSessionManager.initialize_settings()
        return st.session_state.settings
    
    @staticmethod
    def update_settings(new_settings: Dict[str, Any]):
        """Update settings in session state."""
        current_settings = StreamlitSessionManager.get_settings()
        current_settings.update(new_settings)
        st.session_state.settings = current_settings
        
        logger.debug(f"Settings updated: {new_settings}")
    
    @staticmethod
    def is_analysis_complete() -> bool:
        """Check if analysis is complete."""
        return st.session_state.get("analysis_complete", False)
    
    @staticmethod
    def is_chat_enabled() -> bool:
        """Check if chat is enabled."""
        return st.session_state.get("chat_enabled", False)
    
    @staticmethod
    def get_analysis_results() -> Optional[Dict[str, Any]]:
        """Get analysis results from session state."""
        return st.session_state.get("analysis_results")
    
    @staticmethod
    def store_analysis_results(results: Dict[str, Any]):
        """Store analysis results in session state."""
        st.session_state.analysis_results = results
        st.session_state.analysis_complete = True
        
        # Add initial analysis token usage if available
        if "token_usage" in results and results["token_usage"]:
            StreamlitSessionManager.add_token_usage("initial_analysis", results["token_usage"])
        
        logger.info("Analysis results stored in session state")
    
    @staticmethod
    def store_analysis_results_without_token_override(results: Dict[str, Any]):
        """
        Store analysis results in session state WITHOUT overwriting token usage.
        Used when token usage has been restored from cache.
        """
        st.session_state.analysis_results = results
        st.session_state.analysis_complete = True
        
        # Do NOT add initial analysis token usage here - it should already be loaded from cache
        # Only add if no token usage exists at all (fallback scenario)
        if "token_usage_breakdown" not in st.session_state or not st.session_state.token_usage_breakdown.get("initial_analysis"):
            if "token_usage" in results and results["token_usage"]:
                StreamlitSessionManager.add_token_usage("initial_analysis", results["token_usage"])
                logger.info("Added initial analysis token usage as fallback (no cached data found)")
        
        logger.info("Analysis results stored in session state (preserving cached token usage)")
    
    @staticmethod
    def initialize_all_states():
        """Initialize all session state variables (alias for initialize_all)."""
        StreamlitSessionManager.initialize_all()
    
    @staticmethod
    def reset_for_new_analysis():
        """Reset state for starting a new analysis."""
        StreamlitSessionManager.reset_analysis_state()
        # Also reset any pending UI flags
        st.session_state.content_generation_pending = False
        st.session_state.content_type_generated = None
        # Clear webapp_adapter reference
        if hasattr(st.session_state, 'webapp_adapter'):
            delattr(st.session_state, 'webapp_adapter')
        logger.info("Session state reset for new analysis")
    
    @staticmethod
    def get_state(key: str, default: Any = None) -> Any:
        """Get a specific state value."""
        return st.session_state.get(key, default)
    
    @staticmethod
    def set_state(key: str, value: Any):
        """Set a specific state value."""
        st.session_state[key] = value
    
    @staticmethod
    def get_video_id() -> Optional[str]:
        """Get the current video ID."""
        return st.session_state.get("video_id")
    
    @staticmethod
    def set_video_id(video_id: str):
        """Set the current video ID."""
        st.session_state.video_id = video_id
    
    @staticmethod
    def set_analysis_results(results: Dict[str, Any]):
        """Set analysis results (alias for store_analysis_results)."""
        StreamlitSessionManager.store_analysis_results(results)
    
    @staticmethod
    def get_chat_messages() -> list:
        """Get chat messages."""
        return st.session_state.get("chat_messages", [])
    
    @staticmethod
    def add_chat_message(message: Dict[str, str]):
        """Add a chat message."""
        if "chat_messages" not in st.session_state:
            st.session_state.chat_messages = []
        st.session_state.chat_messages.append(message)
    
    @staticmethod
    def initialize_chat_messages(messages: list):
        """Initialize chat messages with a list."""
        st.session_state.chat_messages = messages
    
    @staticmethod
    def set_chat_details(chat_details: Dict[str, Any]):
        """Set chat details."""
        st.session_state.chat_details = chat_details
    
    @staticmethod
    def update_task_output(task_key: str, content: str):
        """Update task output in analysis results."""
        if "analysis_results" in st.session_state and st.session_state.analysis_results:
            if "task_outputs" not in st.session_state.analysis_results:
                st.session_state.analysis_results["task_outputs"] = {}
            st.session_state.analysis_results["task_outputs"][task_key] = content

    # Chat History Caching Methods
    @staticmethod
    def load_cached_chat_messages(webapp_adapter, video_id: str) -> bool:
        """
        Load chat messages from cache and update session state.
        
        Args:
            webapp_adapter: WebAppAdapter instance
            video_id: Video ID
            
        Returns:
            True if messages were loaded, False otherwise
        """
        try:
            # Use asyncio to run the async cache operation
            async def load_chat_messages():
                return await webapp_adapter.get_cached_chat_messages(video_id)
            
            # Run the async operation - handle existing event loop
            cached_messages = None
            try:
                cached_messages = asyncio.run(load_chat_messages())
            except RuntimeError:
                # Event loop already running, need to use different approach
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Create a task and run it
                    task = loop.create_task(load_chat_messages())
                    # This is tricky - we need to wait for completion but can't use await in sync function
                    # For now, log warning and return False
                    logger.warning("Event loop already running, cannot load chat messages synchronously")
                    return False
                else:
                    cached_messages = loop.run_until_complete(load_chat_messages())
            
            if cached_messages:
                st.session_state.chat_messages = cached_messages
                logger.info(f"Loaded {len(cached_messages)} cached chat messages for video {video_id}")
                return True
            else:
                logger.debug(f"No cached chat messages found for video {video_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error loading cached chat messages: {str(e)}")
            return False
    
    @staticmethod
    def save_chat_messages_to_cache(webapp_adapter, video_id: str) -> bool:
        """
        Save current chat messages to cache.
        
        Args:
            webapp_adapter: WebAppAdapter instance
            video_id: Video ID
            
        Returns:
            True if messages were saved, False otherwise
        """
        try:
            chat_messages = st.session_state.get("chat_messages", [])
            
            if not chat_messages:
                logger.debug(f"No chat messages to save for video {video_id}")
                return True
            
            # Use asyncio to run the async cache operation
            async def save_chat_messages():
                return await webapp_adapter.save_chat_messages_to_cache(video_id, chat_messages)
            
            # Run the async operation - handle existing event loop
            try:
                success = asyncio.run(save_chat_messages())
            except RuntimeError:
                # Event loop already running, need to use different approach
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Create a task and run it
                    task = loop.create_task(save_chat_messages())
                    # This is tricky - we need to wait for completion but can't use await in sync function
                    # For now, log warning and return False
                    logger.warning("Event loop already running, cannot save chat messages synchronously")
                    return False
                else:
                    success = loop.run_until_complete(save_chat_messages())
            
            if success:
                logger.debug(f"Saved {len(chat_messages)} chat messages to cache for video {video_id}")
            return success
                
        except Exception as e:
            logger.error(f"Error saving chat messages to cache: {str(e)}")
            return False
    
    @staticmethod
    def initialize_chat_with_cache(webapp_adapter, video_id: str, youtube_url: str, video_title: str, chat_details: Optional[Dict[str, Any]] = None) -> bool:
        """
        Initialize chat by loading from cache or creating with welcome message.
        
        Args:
            webapp_adapter: WebAppAdapter instance
            video_id: Video ID
            youtube_url: YouTube URL
            video_title: Video title
            chat_details: Chat details from analysis
            
        Returns:
            True if chat was initialized successfully, False otherwise
        """
        try:
            # First try to load cached messages
            if StreamlitSessionManager.load_cached_chat_messages(webapp_adapter, video_id):
                # Messages loaded from cache
                st.session_state.chat_enabled = True
                st.session_state.chat_details = chat_details
                logger.info(f"Chat initialized from cache for video {video_id}")
                return True
            
            # No cached messages, initialize with welcome
            async def initialize_welcome():
                return await webapp_adapter.initialize_chat_session_with_welcome(
                    video_id, youtube_url, video_title, chat_details
                )
            
            # Run the async operation - handle existing event loop
            welcome_messages = None
            try:
                welcome_messages = asyncio.run(initialize_welcome())
            except RuntimeError:
                # Event loop already running, need to use different approach
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Create a task and run it
                    task = loop.create_task(initialize_welcome())
                    # This is tricky - we need to wait for completion but can't use await in sync function
                    # For now, log warning and return False
                    logger.warning("Event loop already running, cannot initialize chat with welcome synchronously")
                    return False
                else:
                    welcome_messages = loop.run_until_complete(initialize_welcome())
            
            if welcome_messages:
                st.session_state.chat_messages = welcome_messages
                st.session_state.chat_enabled = True
                st.session_state.chat_details = chat_details
                logger.info(f"Chat initialized with welcome message for video {video_id}")
                return True
            else:
                logger.warning(f"Failed to initialize chat session for video {video_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error initializing chat with cache: {str(e)}")
            return False
    
    @staticmethod
    def clear_cached_chat_session(webapp_adapter, video_id: str) -> bool:
        """
        Clear cached chat session for a video.
        
        Args:
            webapp_adapter: WebAppAdapter instance
            video_id: Video ID
            
        Returns:
            True if cleared successfully, False otherwise
        """
        try:
            # Use asyncio to run the async cache operation
            async def clear_chat_session():
                return await webapp_adapter.clear_chat_session(video_id)
            
            # Run the async operation - handle existing event loop
            try:
                success = asyncio.run(clear_chat_session())
            except RuntimeError:
                # Event loop already running, need to use different approach
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Create a task and run it
                    task = loop.create_task(clear_chat_session())
                    # This is tricky - we need to wait for completion but can't use await in sync function
                    # For now, log warning and return False
                    logger.warning("Event loop already running, cannot clear chat session synchronously")
                    return False
                else:
                    success = loop.run_until_complete(clear_chat_session())
            
            if success:
                logger.info(f"Cleared cached chat session for video {video_id}")
            return success
            
        except Exception as e:
            logger.error(f"Error clearing cached chat session: {str(e)}")
            return False
    
    @staticmethod
    def auto_save_chat_messages(webapp_adapter, video_id: str):
        """
        Automatically save chat messages when they are updated.
        Call this after adding new messages to session state.
        
        Args:
            webapp_adapter: WebAppAdapter instance
            video_id: Video ID
        """
        try:
            # Save in background, don't block UI
            StreamlitSessionManager.save_chat_messages_to_cache(webapp_adapter, video_id)
        except Exception as e:
            logger.warning(f"Auto-save of chat messages failed: {str(e)}")
    
    @staticmethod
    async def auto_save_chat_messages_async(webapp_adapter, video_id: str):
        """
        Automatically save chat messages when they are updated (async version).
        Call this after adding new messages to session state.
        
        Args:
            webapp_adapter: WebAppAdapter instance
            video_id: Video ID
        """
        try:
            # Save in background, don't block UI
            await StreamlitSessionManager.save_chat_messages_to_cache_async(webapp_adapter, video_id)
        except Exception as e:
            logger.warning(f"Auto-save of chat messages failed: {str(e)}")

    # Token Usage Caching Methods
    @staticmethod
    def load_cached_token_usage(webapp_adapter, video_id: str) -> bool:
        """
        Load token usage data from cache and update session state.
        
        Args:
            webapp_adapter: WebAppAdapter instance for cache access
            video_id: Video ID
            
        Returns:
            True if token usage was loaded, False otherwise
        """
        try:
            # Use asyncio to run the async cache operation
            async def load_token_usage():
                # Use the webapp adapter's method to get cached token usage
                return await webapp_adapter.get_cached_token_usage(video_id)
            
            # Run the async operation - handle existing event loop
            cached_data = None
            try:
                cached_data = asyncio.run(load_token_usage())
            except RuntimeError:
                # Event loop already running, need to use different approach
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Create a task and run it
                    task = loop.create_task(load_token_usage())
                    # This is tricky - we need to wait for completion but can't use await in sync function
                    # For now, log warning and return False
                    logger.warning("Event loop already running, cannot load token usage synchronously")
                    return False
                else:
                    cached_data = loop.run_until_complete(load_token_usage())
            
            if cached_data and isinstance(cached_data, dict):
                # Restore token usage data to session state
                if "cumulative_usage" in cached_data:
                    st.session_state.cumulative_token_usage = cached_data["cumulative_usage"]
                
                if "breakdown" in cached_data:
                    st.session_state.token_usage_breakdown = cached_data["breakdown"]
                
                logger.info(f"Loaded cached token usage for video {video_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error loading cached token usage for video {video_id}: {str(e)}")
            return False
    
    @staticmethod
    def save_token_usage_to_cache(webapp_adapter, video_id: str) -> bool:
        """
        Save current token usage data to cache.
        
        Args:
            webapp_adapter: WebAppAdapter instance for cache access
            video_id: Video ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get current token usage from session state
            if "token_usage_breakdown" not in st.session_state or "cumulative_token_usage" not in st.session_state:
                logger.warning(f"No token usage data to save for video {video_id}")
                return False
            
            breakdown = st.session_state.token_usage_breakdown
            cumulative = st.session_state.cumulative_token_usage
            
            # Use asyncio to run the async cache operation
            async def save_token_usage():
                # Get cache repository through service factory
                cache_repo = webapp_adapter.service_factory.get_cache_repository()
                from ..models import TokenUsageCache, TokenUsage
                
                # Create TokenUsageCache object from session state data
                token_cache = TokenUsageCache(video_id=video_id)
                
                # Set cumulative usage
                if cumulative:
                    token_cache.cumulative_usage = TokenUsage.from_dict(cumulative)
                
                # Set initial analysis
                if breakdown.get("initial_analysis"):
                    token_cache.initial_analysis = TokenUsage.from_dict(breakdown["initial_analysis"])
                
                # Set additional content
                if breakdown.get("additional_content"):
                    for content_type, usage_data in breakdown["additional_content"].items():
                        token_cache.additional_content[content_type] = TokenUsage.from_dict(usage_data)
                
                # Set chat usage
                chat_data = breakdown.get("chat", {})
                if chat_data and any(chat_data.get(key, 0) > 0 for key in ["total_tokens", "prompt_tokens", "completion_tokens"]):
                    # Extract message count and create TokenUsage without it
                    chat_usage_dict = {k: v for k, v in chat_data.items() if k != "message_count"}
                    token_cache.chat_usage = TokenUsage.from_dict(chat_usage_dict)
                    token_cache.chat_message_count = chat_data.get("message_count", 0)
                
                # Store in cache
                await cache_repo.store_token_usage_cache(token_cache)
                return True
            
            # Run the async operation - handle existing event loop
            try:
                success = asyncio.run(save_token_usage())
            except RuntimeError:
                # Event loop already running, need to use different approach
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Create a task and run it
                    task = loop.create_task(save_token_usage())
                    # This is tricky - we need to wait for completion but can't use await in sync function
                    # For now, log warning and return False
                    logger.warning("Event loop already running, cannot save token usage synchronously")
                    return False
                else:
                    success = loop.run_until_complete(save_token_usage())
            
            if success:
                logger.info(f"Saved token usage to cache for video {video_id}")
            return success
            
        except Exception as e:
            logger.error(f"Error saving token usage to cache for video {video_id}: {str(e)}")
            return False
    
    @staticmethod
    def auto_save_token_usage(webapp_adapter, video_id: str):
        """
        Automatically save token usage to cache (non-blocking).
        
        Args:
            webapp_adapter: WebAppAdapter instance
            video_id: Video ID
        """
        try:
            StreamlitSessionManager.save_token_usage_to_cache(webapp_adapter, video_id)
        except Exception as e:
            logger.debug(f"Auto-save token usage failed (non-critical): {str(e)}")
    
    @staticmethod
    async def initialize_token_usage_with_cache_async(webapp_adapter, video_id: str) -> bool:
        """
        Initialize token usage tracking with cached data if available (async version).
        
        Args:
            webapp_adapter: WebAppAdapter instance
            video_id: Video ID
            
        Returns:
            True if loaded from cache, False if initialized fresh
        """
        # First initialize empty token tracking
        StreamlitSessionManager.initialize_token_tracking()
        
        try:
            # Get cached token usage directly
            cached_data = await webapp_adapter.get_cached_token_usage(video_id)
            
            if cached_data and isinstance(cached_data, dict):
                # Restore token usage data to session state
                if "cumulative_usage" in cached_data:
                    st.session_state.cumulative_token_usage = cached_data["cumulative_usage"]
                
                if "breakdown" in cached_data:
                    st.session_state.token_usage_breakdown = cached_data["breakdown"]
                
                logger.info(f"Initialized token usage from cache for video {video_id}")
                return True
            else:
                logger.info(f"Initialized fresh token usage tracking for video {video_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error initializing token usage with cache: {str(e)}")
            return False
    
    @staticmethod
    def initialize_token_usage_with_cache(webapp_adapter, video_id: str) -> bool:
        """
        Initialize token usage tracking with cached data if available.
        
        Args:
            webapp_adapter: WebAppAdapter instance
            video_id: Video ID
            
        Returns:
            True if loaded from cache, False if initialized fresh
        """
        # First initialize empty token tracking
        StreamlitSessionManager.initialize_token_tracking()
        
        # Try to load from cache - use simpler approach that works in sync context
        try:
            # Check if we're already in an async context
            import asyncio
            loop = None
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                # No running loop, we can use asyncio.run
                pass
            
            if loop and loop.is_running():
                # We're in an async context, cannot use sync method reliably
                logger.warning("Cannot load token usage synchronously from async context. Use async version.")
                return False
            else:
                # Not in async context, can use asyncio.run
                async def load_cached_data():
                    return await webapp_adapter.get_cached_token_usage(video_id)
                
                cached_data = asyncio.run(load_cached_data())
                
                if cached_data and isinstance(cached_data, dict):
                    # Restore token usage data to session state
                    if "cumulative_usage" in cached_data:
                        st.session_state.cumulative_token_usage = cached_data["cumulative_usage"]
                    
                    if "breakdown" in cached_data:
                        st.session_state.token_usage_breakdown = cached_data["breakdown"]
                    
                    logger.info(f"Initialized token usage from cache for video {video_id}")
                    return True
                else:
                    logger.info(f"Initialized fresh token usage tracking for video {video_id}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error initializing token usage with cache: {str(e)}")
            return False

    # Async Chat Caching Methods
    @staticmethod
    async def load_cached_chat_messages_async(webapp_adapter, video_id: str) -> bool:
        """
        Load chat messages from cache and update session state (async version).
        
        Args:
            webapp_adapter: WebAppAdapter instance
            video_id: Video ID
            
        Returns:
            True if messages were loaded, False otherwise
        """
        try:
            cached_messages = await webapp_adapter.get_cached_chat_messages(video_id)
            
            if cached_messages:
                st.session_state.chat_messages = cached_messages
                logger.info(f"Loaded {len(cached_messages)} cached chat messages for video {video_id}")
                return True
            else:
                logger.debug(f"No cached chat messages found for video {video_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error loading cached chat messages: {str(e)}")
            return False
    
    @staticmethod
    async def save_chat_messages_to_cache_async(webapp_adapter, video_id: str) -> bool:
        """
        Save current chat messages to cache (async version).
        
        Args:
            webapp_adapter: WebAppAdapter instance
            video_id: Video ID
            
        Returns:
            True if messages were saved, False otherwise
        """
        try:
            chat_messages = st.session_state.get("chat_messages", [])
            
            if not chat_messages:
                logger.debug(f"No chat messages to save for video {video_id}")
                return True
            
            success = await webapp_adapter.save_chat_messages_to_cache(video_id, chat_messages)
            
            if success:
                logger.debug(f"Saved {len(chat_messages)} chat messages to cache for video {video_id}")
            return success
                
        except Exception as e:
            logger.error(f"Error saving chat messages to cache: {str(e)}")
            return False
    
    @staticmethod
    async def initialize_chat_with_cache_async(webapp_adapter, video_id: str, youtube_url: str, video_title: str, chat_details: Optional[Dict[str, Any]] = None) -> bool:
        """
        Initialize chat by loading from cache or creating with welcome message (async version).
        
        Args:
            webapp_adapter: WebAppAdapter instance
            video_id: Video ID
            youtube_url: YouTube URL
            video_title: Video title
            chat_details: Chat details from analysis
            
        Returns:
            True if chat was initialized successfully, False otherwise
        """
        try:
            # First try to load cached messages
            if await StreamlitSessionManager.load_cached_chat_messages_async(webapp_adapter, video_id):
                # Messages loaded from cache
                st.session_state.chat_enabled = True
                st.session_state.chat_details = chat_details
                logger.info(f"Chat initialized from cache for video {video_id}")
                return True
            
            # No cached messages, initialize with welcome
            welcome_messages = await webapp_adapter.initialize_chat_session_with_welcome(
                video_id, youtube_url, video_title, chat_details
            )
            
            if welcome_messages:
                st.session_state.chat_messages = welcome_messages
                st.session_state.chat_enabled = True
                st.session_state.chat_details = chat_details
                logger.info(f"Chat initialized with welcome message for video {video_id}")
                return True
            else:
                logger.warning(f"Failed to initialize chat session for video {video_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error initializing chat with cache: {str(e)}")
            return False