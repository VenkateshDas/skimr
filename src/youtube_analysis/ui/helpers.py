"""UI helper functions for YouTube Analyzer."""

import base64
import streamlit as st
from pathlib import Path
from typing import Optional


def get_category_class(category: str) -> str:
    """
    Get the CSS class for a category badge.
    
    Args:
        category: The category name
        
    Returns:
        The CSS class for the category badge
    """
    category = category.lower()
    if "technology" in category:
        return "category-technology"
    elif "business" in category:
        return "category-business"
    elif "education" in category:
        return "category-education"
    elif "health" in category:
        return "category-health"
    elif "science" in category:
        return "category-science"
    elif "finance" in category:
        return "category-finance"
    elif "personal" in category:
        return "category-personal"
    elif "entertainment" in category:
        return "category-entertainment"
    else:
        return "category-other"


def extract_youtube_thumbnail(video_id: str) -> str:
    """
    Get the thumbnail URL for a YouTube video.
    
    Args:
        video_id: The YouTube video ID
        
    Returns:
        The URL of the video thumbnail
    """
    return f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"


def load_css():
    """Load custom CSS styles once per session."""
    if st.session_state.get("_css_loaded", False):
        return
    st.markdown(
        """
        <style>
        .stButton button { width: 100%; }
        .sidebar .stButton button { width: auto; }
        .st-emotion-cache-16idsys p { font-size: 14px; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.session_state["_css_loaded"] = True


@st.cache_data(show_spinner=False)
def get_skimr_logo_base64() -> Optional[str]:
    """Return the base64-encoded Skimr logo for embedding in HTML.

    This helper now builds the file path relative to the *module* location
    instead of relying on the current working directory. This makes the logo
    resolution robust whether the application is executed from the project
    root, installed as a package, or invoked by a process manager.
    """

    # Build logo path relative to the current file:
    # helpers.py -> ui/ -> (parents[1]) youtube_analysis/ -> logo/logo_v2.png
    logo_path = Path(__file__).resolve().parents[1] / "logo" / "logo_v2.png"

    if not logo_path.exists():
        return None

    try:
        with open(logo_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except Exception:
        return None 