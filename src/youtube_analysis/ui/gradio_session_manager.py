"""
Gradio session state management utilities.
Replaces Streamlit session management for Gradio UI.
"""

import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
from ..utils.logging import get_logger
from ..core.config import config, get_default_settings
import gc

logger = get_logger("gradio_session_manager")


class GradioSessionManager:
    """Manages Gradio session state with proper initialization and cleanup."""
    
    def __init__(self):
        """Initialize the session manager with default state."""
        self._session_state = {}
        self.initialize_all()
    
    def initialize_all(self):
        """Initialize all session state variables."""
        self.initialize_auth_state()
        self.initialize_analysis_state()
        self.initialize_chat_state()
        self.initialize_ui_state()
        self.initialize_settings()
        self.initialize_token_tracking()
        
        logger.info("All session state variables initialized")
    
    def initialize_auth_state(self):
        """Initialize authentication-related session state."""
        auth_defaults = {
            "authenticated": False,
            "user": None,
            "show_auth": False,
            "guest_analysis_count": 0
        }
        
        for key, default_value in auth_defaults.items():
            if key not in self._session_state:
                self._session_state[key] = default_value
    
    def initialize_analysis_state(self):
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
            if key not in self._session_state:
                self._session_state[key] = default_value
    
    def initialize_chat_state(self):
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
            if key not in self._session_state:
                self._session_state[key] = default_value
    
    def initialize_ui_state(self):
        """Initialize UI-related session state."""
        ui_defaults = {
            "current_youtube_url": "",
            "content_generation_pending": False,
            "content_type_generated": None,
            "is_chat_streaming": False,
            "current_chat_question": None,
            "chat_streaming_placeholder": "",
            "chat_streaming_placeholder_ref": None,
            "show_video_with_subtitles": False,
            "video_id_for_subtitles": None
        }
        
        for key, default_value in ui_defaults.items():
            if key not in self._session_state:
                self._session_state[key] = default_value
    
    def initialize_token_tracking(self):
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
            if key not in self._session_state:
                self._session_state[key] = default_value
    
    def initialize_settings(self):
        """Initialize application settings."""
        defaults = {
            "settings": get_default_settings()
        }
        
        for key, default_value in defaults.items():
            if key not in self._session_state:
                self._session_state[key] = default_value
    
    def reset_analysis_state(self):
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
            if key in self._session_state:
                if key == "chat_messages":
                    self._session_state[key] = []
                elif key in ["chat_enabled", "analysis_complete"]:
                    self._session_state[key] = False
                else:
                    self._session_state[key] = None
        
        # Reset token tracking for new analysis
        self.reset_token_tracking()
        
        logger.info("Analysis state reset for new analysis")
    
    def reset_token_tracking(self):
        """Reset token usage tracking for new analysis."""
        # Ensure token tracking is initialized first
        if "cumulative_token_usage" not in self._session_state or "token_usage_breakdown" not in self._session_state:
            self.initialize_token_tracking()
        
        self._session_state["cumulative_token_usage"] = {
            "total_tokens": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0
        }
        self._session_state["token_usage_breakdown"] = {
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
    
    def reset_chat_state(self):
        """Reset chat-related state."""
        chat_keys = [
            "chat_messages",
            "chat_user_input", 
            "thinking_message_shown",
            "thinking_placeholder",
            "user_input_disabled"
        ]
        
        for key in chat_keys:
            if key in self._session_state:
                if key == "chat_messages":
                    self._session_state[key] = []
                elif key in ["thinking_message_shown", "user_input_disabled"]:
                    self._session_state[key] = False
                else:
                    self._session_state[key] = None

        # Reset chat token usage
        if "token_usage_breakdown" in self._session_state:
            self._session_state["token_usage_breakdown"]["chat"] = {
                "total_tokens": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "message_count": 0
            }
            # Recalculate cumulative usage without chat
            self._recalculate_cumulative_usage()
        else:
            # Ensure token tracking is initialized
            self.initialize_token_tracking()
        
        logger.info("Chat state reset")
    
    def add_token_usage(self, operation_type: str, token_usage: Dict[str, int], operation_name: Optional[str] = None):
        """
        Add token usage for an operation and update cumulative totals.
        
        Args:
            operation_type: Type of operation ('initial_analysis', 'additional_content', 'chat')
            token_usage: Dict with 'total_tokens', 'prompt_tokens', 'completion_tokens'
            operation_name: Name of the specific operation (for additional_content)
        """
        if "token_usage_breakdown" not in self._session_state:
            self.initialize_token_tracking()
        
        breakdown = self._session_state["token_usage_breakdown"]
        
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
        self._session_state["token_usage_breakdown"] = breakdown
        
        # Recalculate cumulative usage
        self._recalculate_cumulative_usage()
        
        logger.info(f"Added token usage for {operation_type}: {token_usage}")
    
    def _recalculate_cumulative_usage(self):
        """Recalculate cumulative token usage from all sources."""
        breakdown = self._session_state["token_usage_breakdown"]
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
        
        self._session_state["cumulative_token_usage"] = cumulative

    def get_cumulative_token_usage(self) -> Dict[str, int]:
        """Get cumulative token usage across all operations."""
        if "cumulative_token_usage" not in self._session_state:
            self.initialize_token_tracking()
        return self._session_state["cumulative_token_usage"].copy()

    def get_token_usage_breakdown(self) -> Dict[str, Any]:
        """Get detailed token usage breakdown by operation."""
        if "token_usage_breakdown" not in self._session_state:
            self.initialize_token_tracking()
        return self._session_state["token_usage_breakdown"].copy()
    
    def get_settings(self) -> Dict[str, Any]:
        """Get current settings from session state."""
        if "settings" not in self._session_state:
            self.initialize_settings()
        return self._session_state["settings"]
    
    def update_settings(self, new_settings: Dict[str, Any]):
        """Update settings in session state."""
        current_settings = self.get_settings()
        current_settings.update(new_settings)
        self._session_state["settings"] = current_settings
        
        logger.debug(f"Settings updated: {new_settings}")
    
    def is_analysis_complete(self) -> bool:
        """Check if analysis is complete."""
        return self._session_state.get("analysis_complete", False)
    
    def is_chat_enabled(self) -> bool:
        """Check if chat is enabled."""
        return self._session_state.get("chat_enabled", False)
    
    def get_analysis_results(self) -> Optional[Dict[str, Any]]:
        """Get analysis results from session state."""
        return self._session_state.get("analysis_results")
    
    def store_analysis_results(self, results: Dict[str, Any]):
        """Store analysis results in session state."""
        self._session_state["analysis_results"] = results
        self._session_state["analysis_complete"] = True
        
        # Add initial analysis token usage if available
        if "token_usage" in results and results["token_usage"]:
            self.add_token_usage("initial_analysis", results["token_usage"])
        
        logger.info("Analysis results stored in session state")
    
    def store_analysis_results_without_token_override(self, results: Dict[str, Any]):
        """
        Store analysis results in session state WITHOUT overwriting token usage.
        Used when token usage has been restored from cache.
        """
        self._session_state["analysis_results"] = results
        self._session_state["analysis_complete"] = True
        
        # Do NOT add initial analysis token usage here - it should already be loaded from cache
        # Only add if no token usage exists at all (fallback scenario)
        if "token_usage_breakdown" not in self._session_state or not self._session_state["token_usage_breakdown"].get("initial_analysis"):
            if "token_usage" in results and results["token_usage"]:
                self.add_token_usage("initial_analysis", results["token_usage"])
                logger.info("Added initial analysis token usage as fallback (no cached data found)")
        
        logger.info("Analysis results stored in session state (preserving cached token usage)")
    
    def reset_for_new_analysis(self):
        """Reset session state for a new analysis."""
        # Keep authentication and guest count state
        authenticated = self.get_state("authenticated", False)
        guest_count = self.get_state("guest_analysis_count", 0)
        
        # Clear all session state
        self._session_state.clear()
        
        # Restore authentication and guest count state
        self.set_state("authenticated", authenticated)
        self.set_state("guest_analysis_count", guest_count)
        
        # Initialize all states
        self.initialize_all()
        
        # Clear subtitle data
        self.clear_subtitle_data()
        
        logger.info("Reset session state for new analysis")
    
    def get_state(self, key: str, default: Any = None) -> Any:
        """Get a specific state value."""
        return self._session_state.get(key, default)
    
    def set_state(self, key: str, value: Any):
        """Set a specific state value."""
        self._session_state[key] = value
    
    def get_video_id(self) -> Optional[str]:
        """Get the current video ID."""
        return self._session_state.get("video_id")
    
    def set_video_id(self, video_id: str):
        """Set the current video ID."""
        self._session_state["video_id"] = video_id
    
    def set_analysis_results(self, results: Dict[str, Any]):
        """Set analysis results (alias for store_analysis_results)."""
        self.store_analysis_results(results)
    
    def get_chat_messages(self) -> list:
        """Get chat messages."""
        return self._session_state.get("chat_messages", [])
    
    def add_chat_message(self, message: Dict[str, str]):
        """Add a chat message."""
        if "chat_messages" not in self._session_state:
            self._session_state["chat_messages"] = []
        self._session_state["chat_messages"].append(message)
    
    def initialize_chat_messages(self, messages: list):
        """Initialize chat messages with a list."""
        self._session_state["chat_messages"] = messages
    
    def set_chat_details(self, chat_details: Dict[str, Any]):
        """Set chat details."""
        self._session_state["chat_details"] = chat_details
    
    def update_task_output(self, task_key: str, content: str):
        """Update task output in analysis results."""
        if "analysis_results" in self._session_state and self._session_state["analysis_results"]:
            if "task_outputs" not in self._session_state["analysis_results"]:
                self._session_state["analysis_results"]["task_outputs"] = {}
            self._session_state["analysis_results"]["task_outputs"][task_key] = content

    def clear_subtitle_data(self):
        """Clear subtitle and translation data from session state."""
        # Clear subtitle-related session states
        video_id = self.get_video_id()
        if video_id:
            # Find and clear all translation-related session states
            keys_to_remove = []
            for key in self._session_state:
                if isinstance(key, str) and key.startswith(f"translated_segments_{video_id}_"):
                    keys_to_remove.append(key)
                elif isinstance(key, str) and key.startswith(f"subtitles_for_player_{video_id}"):
                    keys_to_remove.append(key)
            
            for key in keys_to_remove:
                if key in self._session_state:
                    del self._session_state[key]
        
        # Reset subtitle display flags
        self.set_state("show_video_with_subtitles", False)
        self.set_state("video_id_for_subtitles", None)
        
        logger.info("Cleared subtitle and translation data")
    
    # Async methods for cache integration
    async def initialize_token_usage_with_cache_async(self, webapp_adapter, video_id: str) -> bool:
        """
        Initialize token usage tracking with cached data if available (async version).
        
        Args:
            webapp_adapter: WebAppAdapter instance
            video_id: Video ID
            
        Returns:
            True if loaded from cache, False if initialized fresh
        """
        # First initialize empty token tracking
        self.initialize_token_tracking()
        
        try:
            # Get cached token usage directly
            cached_data = await webapp_adapter.get_cached_token_usage(video_id)
            
            if cached_data and isinstance(cached_data, dict):
                # Restore token usage data to session state
                if "cumulative_usage" in cached_data:
                    self._session_state["cumulative_token_usage"] = cached_data["cumulative_usage"]
                
                if "breakdown" in cached_data:
                    self._session_state["token_usage_breakdown"] = cached_data["breakdown"]
                
                logger.info(f"Initialized token usage from cache for video {video_id}")
                return True
            else:
                logger.info(f"Initialized fresh token usage tracking for video {video_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error initializing token usage with cache: {str(e)}")
            return False
    
    async def initialize_chat_with_cache_async(self, webapp_adapter, video_id: str, youtube_url: str, video_title: str, chat_details: Optional[Dict[str, Any]] = None) -> bool:
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
            cached_messages = await webapp_adapter.get_cached_chat_messages(video_id)
            
            if cached_messages:
                # Messages loaded from cache
                self._session_state["chat_messages"] = cached_messages
                self._session_state["chat_enabled"] = True
                self._session_state["chat_details"] = chat_details
                logger.info(f"Chat initialized from cache for video {video_id}")
                return True
            
            # No cached messages, initialize with welcome
            welcome_messages = await webapp_adapter.initialize_chat_session_with_welcome(
                video_id, youtube_url, video_title, chat_details
            )
            
            if welcome_messages:
                self._session_state["chat_messages"] = welcome_messages
                self._session_state["chat_enabled"] = True
                self._session_state["chat_details"] = chat_details
                logger.info(f"Chat initialized with welcome message for video {video_id}")
                return True
            else:
                logger.warning(f"Failed to initialize chat session for video {video_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error initializing chat with cache: {str(e)}")
            return False
    
    async def auto_save_chat_messages(self, webapp_adapter, video_id: str):
        """
        Automatically save chat messages when they are updated (async version).
        
        Args:
            webapp_adapter: WebAppAdapter instance
            video_id: Video ID
        """
        try:
            chat_messages = self._session_state.get("chat_messages", [])
            
            if not chat_messages:
                logger.debug(f"No chat messages to save for video {video_id}")
                return True
            
            success = await webapp_adapter.save_chat_messages_to_cache(video_id, chat_messages)
            
            if success:
                logger.debug(f"Saved {len(chat_messages)} chat messages to cache for video {video_id}")
            return success
                
        except Exception as e:
            logger.warning(f"Auto-save of chat messages failed: {str(e)}")
            return False
    
    def get_session_dict(self) -> Dict[str, Any]:
        """Get the entire session state as a dictionary for Gradio State."""
        return self._session_state.copy()
    
    def update_session_dict(self, session_dict: Dict[str, Any]):
        """Update the session state from a dictionary from Gradio State."""
        self._session_state.update(session_dict)