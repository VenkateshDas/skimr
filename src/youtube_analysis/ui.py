"""UI helper functions for the YouTube Analyzer Streamlit app."""

import os
import streamlit as st
from typing import Optional, Any, List, Dict

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

def initialize_session_state(model, temperature):
    os.environ["LLM_MODEL"] = model
    os.environ["LLM_TEMPERATURE"] = str(temperature)

def setup_sidebar(version: str):
    """
    Set up the sidebar with configuration options.
    
    Args:
        version: The app version
    """
    with st.sidebar:
        st.title("Configuration")
        
        # Check for OpenAI API key
        openai_api_key = os.environ.get("OPENAI_API_KEY")
        if not openai_api_key:
            st.warning("⚠️ OpenAI API key is not set. Chat functionality will be limited.")
        
        # Model selection
        model = st.selectbox(
            label="Model",
            options=["gpt-4o-mini", "gemini-2.0-flash", "claude-3-7-sonnet-20250219" ],
            index=0
        )
        
        # Temperature setting
        temperature = st.slider(
            label="Temperature",
            min_value=0.0,
            max_value=1.0,
            value=0.7,
            step=0.1
        )
        
        # Cache toggle
        use_cache = st.toggle("Use cached results", value=True)
        
        # Store settings in session state
        if "settings" not in st.session_state:
            st.session_state.settings = {}
        
        st.session_state.settings["model"] = model
        st.session_state.settings["temperature"] = temperature
        st.session_state.settings["use_cache"] = use_cache
        
        # Add a divider
        st.divider()
        
        # Display app version
        st.caption(f"v{version}")
        
        # Add login/signup option
        st.subheader("Account")
        
        # Setup user menu
        setup_user_menu()

def setup_user_menu(user: Optional[Any] = None):
    """
    Set up the user menu in the sidebar.
    
    Args:
        user: Optional user object from Supabase
    """
    with st.sidebar:
        st.markdown("### User")
        if user:
            st.write(f"Logged in as: {user.email}")
            
            # Display user stats if available
            try:
                from .stats import get_summary_count
                summary_count = get_summary_count(user.id)
                if summary_count is not None:
                    st.write(f"Summaries generated: {summary_count}")
            except Exception as e:
                # Silently ignore stats retrieval errors
                pass
                
            if st.button("Logout"):
                from .auth import logout
                if logout():
                    st.rerun()
        else:
            st.session_state.show_auth = True

def create_welcome_message(video_title: Optional[str] = None, has_timestamps: bool = False):
    """
    Create a welcome message for the chat interface.
    
    Args:
        video_title: Optional title of the video being analyzed
        has_timestamps: Whether timestamps are available
    """
    if video_title:
        st.markdown(f"### Analyzing: {video_title}")
        if has_timestamps:
            st.info("This video has timestamps available. You can ask questions about specific parts of the video!")
    else:
        st.markdown("### Welcome to YouTube Video Analyzer!")
        st.write("Enter a YouTube URL to get started.")

def display_video_highlights(video_path: str, highlights: List[Dict[str, Any]]):
    """
    Display video highlights in the UI.
    
    Args:
        video_path: Path to the highlights video
        highlights: List of highlight segments with descriptions
    """
    st.subheader("📽️ Video Highlights")
    
    # Display the video
    video_file = open(video_path, 'rb')
    video_bytes = video_file.read()
    st.video(video_bytes)
    
    # Display highlights information
    st.write("### Key Moments")
    
    for i, highlight in enumerate(highlights, 1):
        start_time = int(highlight.get("start_time", 0))
        end_time = int(highlight.get("end_time", 0))
        
        # Format times as MM:SS
        start_formatted = f"{start_time // 60}:{start_time % 60:02d}"
        end_formatted = f"{end_time // 60}:{end_time % 60:02d}"
        
        # Create expander for each highlight
        with st.expander(f"Highlight {i}: [{start_formatted} - {end_formatted}]"):
            st.markdown(f"**Description:** {highlight.get('description', 'No description available')}")
            st.markdown(f"**Timestamp:** {start_formatted} - {end_formatted}")
            
            # Add a divider between highlights
            if i < len(highlights):
                st.divider() 