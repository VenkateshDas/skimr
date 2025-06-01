"""
Streamlit session state management utilities.
"""

import streamlit as st
from typing import Dict, Any, Optional
from datetime import datetime

from ..utils.logging import get_logger

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
        defaults = {
            "authenticated": False,
            "user": None,
            "auth_initialized": False,
            "show_auth": False,
            "guest_analysis_count": 0
        }
        
        for key, default_value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = default_value
    
    @staticmethod
    def initialize_analysis_state():
        """Initialize analysis-related session state."""
        defaults = {
            "analysis_complete": False,
            "analysis_results": None,
            "analysis_start_time": None,
            "video_id": None,
            "video_url": None,
            "video_info": None,
            "transcript_list": None,
            "transcript_text": None,
            "timestamped_transcript": None
        }
        
        for key, default_value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = default_value
    
    @staticmethod
    def initialize_chat_state():
        """Initialize chat-related session state."""
        defaults = {
            "chat_enabled": False,
            "chat_messages": [],
            "chat_details": None,
            "chat_user_input": "",
            "thinking_message_shown": False,
            "thinking_placeholder": None,
            "user_input_disabled": False
        }
        
        for key, default_value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = default_value
    
    @staticmethod
    def initialize_ui_state():
        """Initialize UI-related session state."""
        defaults = {
            "content_generation_pending": False,
            "content_type_generated": None,
            "highlights_video_path": None,
            "highlights_segments": None
        }
        
        for key, default_value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = default_value
    
    @staticmethod
    def initialize_token_tracking():
        """Initialize comprehensive token usage tracking."""
        defaults = {
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
        
        for key, default_value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = default_value
    
    @staticmethod
    def initialize_settings():
        """Initialize application settings."""
        defaults = {
            "settings": {
                "model": "gpt-4o-mini",
                "temperature": 0.2,
                "use_cache": True,
                "use_optimized": True,
                "analysis_types": ["Summary & Classification"]
            }
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
        return st.session_state.get("settings", {})
    
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
            import asyncio
            
            # Get cached messages
            cached_messages = asyncio.run(webapp_adapter.get_cached_chat_messages(video_id))
            
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
            import asyncio
            
            chat_messages = st.session_state.get("chat_messages", [])
            
            if chat_messages:
                success = asyncio.run(webapp_adapter.save_chat_messages_to_cache(video_id, chat_messages))
                if success:
                    logger.debug(f"Saved {len(chat_messages)} chat messages to cache for video {video_id}")
                return success
            else:
                logger.debug(f"No chat messages to save for video {video_id}")
                return True
                
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
            import asyncio
            
            # First try to load cached messages
            if StreamlitSessionManager.load_cached_chat_messages(webapp_adapter, video_id):
                # Messages loaded from cache
                st.session_state.chat_enabled = True
                st.session_state.chat_details = chat_details
                logger.info(f"Chat initialized from cache for video {video_id}")
                return True
            
            # No cached messages, initialize with welcome
            welcome_messages = asyncio.run(
                webapp_adapter.initialize_chat_session_with_welcome(
                    video_id, youtube_url, video_title, chat_details
                )
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
            import asyncio
            
            success = asyncio.run(webapp_adapter.clear_chat_session(video_id))
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