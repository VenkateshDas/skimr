"""
Gradio-specific callback adapters for progress and status updates.
Replaces StreamlitCallbacks for Gradio UI.
"""

from typing import Optional, Callable, Any
import gradio as gr
from ..utils.logging import get_logger

logger = get_logger("gradio_callbacks")


class GradioCallbacks:
    """
    Manages Gradio-specific progress and status callbacks.
    Provides updates for Gradio UI components.
    """
    
    def __init__(self):
        self.progress_component = None
        self.status_component = None
        self.progress_value = 0
        self.status_message = ""
        
    def setup(self, progress_component=None, status_component=None):
        """Setup Gradio components for progress and status."""
        self.progress_component = progress_component
        self.status_component = status_component
        
    def create_progress_callback(self) -> Callable[[int], None]:
        """Create a progress callback for Gradio."""
        def update_progress(value: int):
            try:
                self.progress_value = max(0, min(100, value))
                logger.debug(f"Progress updated to {self.progress_value}%")
                return self.progress_value
            except Exception as e:
                logger.debug(f"Could not update progress: {e}")
                return self.progress_value
                
        return update_progress
    
    def create_status_callback(self) -> Callable[[str], None]:
        """Create a status callback for Gradio."""
        def update_status(message: str):
            try:
                self.status_message = message
                logger.debug(f"Status updated: {message}")
                return self.status_message
            except Exception as e:
                logger.debug(f"Could not update status: {e}")
                return self.status_message
                
        return update_status
    
    def clear(self):
        """Clear the progress and status displays."""
        try:
            self.progress_value = 0
            self.status_message = ""
            logger.debug("Cleared progress and status displays")
        except Exception as e:
            logger.debug(f"Could not clear displays: {e}")
    
    def show_success(self, message: str):
        """Show a success message."""
        try:
            self.status_message = f"✅ {message}"
            logger.debug(f"Success message: {message}")
            return self.status_message
        except Exception as e:
            logger.debug(f"Could not show success: {e}")
            return self.status_message
    
    def show_error(self, message: str):
        """Show an error message."""
        try:
            self.status_message = f"❌ {message}"
            logger.debug(f"Error message: {message}")
            return self.status_message
        except Exception as e:
            logger.debug(f"Could not show error: {e}")
            return self.status_message
    
    def update_progress(self, value: int):
        """Update progress directly."""
        try:
            self.progress_value = max(0, min(100, value))
            logger.debug(f"Progress directly updated to {self.progress_value}%")
            return self.progress_value
        except Exception as e:
            logger.debug(f"Could not update progress: {e}")
            return self.progress_value
    
    def update_status(self, message: str):
        """Update status directly."""
        try:
            self.status_message = message
            logger.debug(f"Status directly updated: {message}")
            return self.status_message
        except Exception as e:
            logger.debug(f"Could not update status: {e}")
            return self.status_message
    
    def get_progress(self) -> int:
        """Get current progress value."""
        return self.progress_value
    
    def get_status(self) -> str:
        """Get current status message."""
        return self.status_message