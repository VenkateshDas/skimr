"""
Streamlit-specific callback adapters for progress and status updates.
"""

from typing import Optional, Callable
import streamlit as st
from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx

from ..utils.logging import get_logger

logger = get_logger("streamlit_callbacks")


class StreamlitCallbacks:
    """
    Manages Streamlit-specific progress and status callbacks.
    Provides thread-safe updates for Streamlit UI components.
    """
    
    def __init__(self):
        self.progress_placeholder = None
        self.status_placeholder = None
        self.progress_bar = None
        
    def setup(self):
        """Setup Streamlit placeholders for progress and status."""
        self.progress_placeholder = st.empty()
        self.status_placeholder = st.empty()
        self.progress_bar = self.progress_placeholder.progress(0)
        
    def create_progress_callback(self) -> Callable[[int], None]:
        """Create a thread-safe progress callback for Streamlit."""
        def update_progress(value: int):
            try:
                # Only update if there's a valid Streamlit context
                if get_script_run_ctx() and self.progress_bar:
                    self.progress_bar.progress(value)
            except Exception as e:
                logger.debug(f"Could not update progress: {e}")
                
        return update_progress
    
    def create_status_callback(self) -> Callable[[str], None]:
        """Create a thread-safe status callback for Streamlit."""
        def update_status(message: str):
            try:
                # Only update if there's a valid Streamlit context
                if get_script_run_ctx() and self.status_placeholder:
                    self.status_placeholder.info(message)
            except Exception as e:
                logger.debug(f"Could not update status: {e}")
                
        return update_status
    
    def clear(self):
        """Clear the progress and status displays."""
        try:
            if self.progress_placeholder:
                self.progress_placeholder.empty()
            if self.status_placeholder:
                self.status_placeholder.empty()
        except Exception as e:
            logger.debug(f"Could not clear displays: {e}")
    
    def show_success(self, message: str):
        """Show a success message."""
        try:
            if self.status_placeholder:
                self.status_placeholder.success(message)
        except Exception as e:
            logger.debug(f"Could not show success: {e}")
    
    def show_error(self, message: str):
        """Show an error message."""
        try:
            if self.status_placeholder:
                self.status_placeholder.error(message)
        except Exception as e:
            logger.debug(f"Could not show error: {e}")
    
    def update_progress(self, value: int):
        """Update progress directly."""
        try:
            if get_script_run_ctx() and self.progress_bar:
                self.progress_bar.progress(value)
        except Exception as e:
            logger.debug(f"Could not update progress: {e}")
    
    def update_status(self, message: str):
        """Update status directly."""
        try:
            if get_script_run_ctx() and self.status_placeholder:
                self.status_placeholder.info(message)
        except Exception as e:
            logger.debug(f"Could not update status: {e}")