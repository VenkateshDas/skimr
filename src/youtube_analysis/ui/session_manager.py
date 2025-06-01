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
        
        logger.info("Analysis state reset for new analysis")
    
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
        
        logger.info("Chat state reset")
    
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
        
        logger.info("Analysis results stored in session state")