"""UI components and utilities for Streamlit integration."""

from .streamlit_callbacks import StreamlitCallbacks
from .session_manager import StreamlitSessionManager
from .components import display_analysis_results, display_chat_interface, display_performance_stats

__all__ = [
    "StreamlitCallbacks", 
    "StreamlitSessionManager",
    "display_analysis_results",
    "display_chat_interface",
    "display_performance_stats"
]

# Lazy import functions to avoid circular imports
def get_skimr_logo_base64():
    """Lazy import to get logo function."""
    from ..ui_legacy import get_skimr_logo_base64 as _get_logo
    return _get_logo()

def load_css():
    """Lazy import to get load_css function.""" 
    from ..ui_legacy import load_css as _load_css
    return _load_css()