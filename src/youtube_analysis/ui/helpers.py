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
    """Load custom CSS styles."""
    st.markdown("""
        <style>
        .stButton button {
            width: 100%;
        }
        .sidebar .stButton button {
            width: auto;
        }
        .st-emotion-cache-16idsys p {
            font-size: 14px;
        }
        </style>
    """, unsafe_allow_html=True)


def get_skimr_logo_base64() -> Optional[str]:
    """Returns the base64 encoded Skimr logo for embedding in HTML."""
    # Logo file path
    logo_path = Path("src/youtube_analysis/logo/logo_v2.png")
    
    # Check if the logo file exists
    if not logo_path.exists():
        return None
    
    try:
        with open(logo_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except Exception:
        return None 