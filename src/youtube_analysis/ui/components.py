"""
Streamlit UI components for displaying analysis results and chat interface.
"""

# Re-export the original components to maintain compatibility
from .original_components import (
    display_analysis_results_original as display_analysis_results,
    display_chat_interface_original as display_chat_interface
)

# Import the original handle_chat_input from the webapp functions
def handle_chat_input():
    """Handle processing of chat input."""
    from ..webapp_functions import handle_chat_input as original_handle_chat_input
    original_handle_chat_input()