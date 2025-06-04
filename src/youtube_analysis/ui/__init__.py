"""UI components and utilities for both Streamlit and Gradio integration."""

# Streamlit components (legacy)
from .streamlit_callbacks import StreamlitCallbacks
from .session_manager import StreamlitSessionManager
from .components import display_analysis_results, display_chat_interface, display_performance_stats
from .helpers import get_skimr_logo_base64, load_css

# Gradio components (new)
from .gradio_callbacks import GradioCallbacks
from .gradio_session_manager import GradioSessionManager

__all__ = [
    # Streamlit components
    "StreamlitCallbacks", 
    "StreamlitSessionManager",
    "display_analysis_results",
    "display_chat_interface",
    "display_performance_stats",
    "get_skimr_logo_base64",
    "load_css",
    # Gradio components
    "GradioCallbacks",
    "GradioSessionManager",
]