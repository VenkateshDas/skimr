#!/usr/bin/env python3
"""
YouTube Analysis Streamlit App - A web interface for analyzing YouTube videos using CrewAI
"""

import os
import sys
import time
import re
import streamlit as st
from typing import Optional, Dict, Any, Tuple
import pandas as pd
import plotly.express as px
from datetime import datetime

# Add the src directory to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

# Import the YouTube Analysis modules
from src.youtube_analysis.utils.youtube_utils import get_transcript, extract_video_id
from src.youtube_analysis.crew import YouTubeAnalysisCrew
from src.youtube_analysis.utils.logging import setup_logger

# Configure logging
logger = setup_logger("streamlit_app", log_level="INFO")

# App version
__version__ = "1.0.0"

# Set page configuration
st.set_page_config(
    page_title="YouTube Video Analysis",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 3.5rem;
        color: #FF0000;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 2rem;
        color: #606060;
        margin-bottom: 1rem;
    }
    .info-text {
        font-size: 1.5rem;
        color: #303030;
    }
    .success-box {
        padding: 1rem;
        background-color: #E6F4EA;
        border-radius: 0.5rem;
        border-left: 0.5rem solid #34A853;
        margin: 1rem 0;
    }
    .warning-box {
        padding: 1rem;
        background-color: #FCF3CF;
        border-radius: 0.5rem;
        border-left: 0.5rem solid #F9A825;
        margin: 1rem 0;
    }
    .error-box {
        padding: 1rem;
        background-color: #FADBD8;
        border-radius: 0.5rem;
        border-left: 0.5rem solid #E53935;
        margin: 1rem 0;
    }
    .stProgress > div > div > div > div {
        background-color: #FF0000;
    }
    .output-container {
        border: 1px solid #E0E0E0;
        border-radius: 0.5rem;
        padding: 1.5rem;
        background-color: #F9F9F9;
        margin: 1rem 0;
    }
    .youtube-thumbnail {
        width: 100%;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
    .token-usage {
        font-size: 0.9rem;
        color: #606060;
        text-align: right;
        margin-top: 1rem;
    }
</style>
""", unsafe_allow_html=True)

def extract_youtube_thumbnail(video_id: str) -> str:
    """
    Get the thumbnail URL for a YouTube video.
    
    Args:
        video_id: The YouTube video ID
        
    Returns:
        The URL of the video thumbnail
    """
    return f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"

def validate_youtube_url(url: str) -> bool:
    """
    Validate if the provided URL is a valid YouTube URL.
    
    Args:
        url: The URL to validate
        
    Returns:
        True if the URL is valid, False otherwise
    """
    if not url:
        return False
    
    youtube_pattern = r'(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/)[a-zA-Z0-9_-]+'
    return bool(re.match(youtube_pattern, url))

def run_analysis(youtube_url: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Run the YouTube Analysis Crew with the provided YouTube URL.
    
    Args:
        youtube_url: The URL of the YouTube video to analyze
        
    Returns:
        A tuple containing the analysis results and any error message
    """
    try:
        # Extract video ID for thumbnail
        video_id = extract_video_id(youtube_url)
        
        # Create progress placeholder
        progress_placeholder = st.empty()
        status_placeholder = st.empty()
        
        # Initialize progress bar
        progress_bar = progress_placeholder.progress(0)
        status_placeholder.info("Fetching video transcript...")
        
        # Get the transcript
        transcript = get_transcript(youtube_url)
        progress_bar.progress(25)
        status_placeholder.info("Creating analysis crew...")
        
        # Create and run the crew
        crew_instance = YouTubeAnalysisCrew()
        crew = crew_instance.crew()
        
        # Update progress
        progress_bar.progress(50)
        status_placeholder.info("Analyzing video content...")
        
        # Start the crew execution
        inputs = {"youtube_url": youtube_url, "transcript": transcript}
        crew_output = crew.kickoff(inputs=inputs)

        # Get each task from crew and then get the output
        task_outputs = {}
        for task in crew.tasks:
            task_outputs[task.name] = task.output.raw
        
        # Update progress
        progress_bar.progress(100)
        status_placeholder.success("Analysis completed successfully!")
        
        # Get token usage
        token_usage = crew_output.token_usage if hasattr(crew_output, 'token_usage') else None
        
        # Prepare results
        results = {
            "video_id": video_id,
            "youtube_url": youtube_url,
            "transcript": transcript,
            "output": str(crew_output),
            "task_outputs": task_outputs,
            "token_usage": token_usage,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        return results, None
        
    except Exception as e:
        logger.error(f"Error in analysis: {str(e)}", exc_info=True)
        return None, str(e)

def display_token_usage(token_usage: Dict[str, Any], model: str) -> None:
    """
    Display token usage information in a visually appealing way.
    
    Args:
        token_usage: Dictionary containing token usage information
    """
    if not token_usage:
        st.info("Token usage information not available.")
        return
    
    st.subheader("Token Usage")
    
    st.markdown(f"**Model:** {model}")
    # Display the token usage as Plain Text
    st.text(token_usage)

def main():
    """Main function for the Streamlit app."""
    
    # Sidebar
    with st.sidebar:
        st.image("https://upload.wikimedia.org/wikipedia/commons/e/ef/Youtube_logo.png", width=200)
        st.markdown("## Settings")
        
        # Model selection
        model = st.selectbox(
            "Select LLM Model",
            ["gpt-4o-mini", "gpt-4o"],
            index=0
        )
        
        # Temperature setting
        temperature = st.slider(
            "Temperature",
            min_value=0.0,
            max_value=1.0,
            value=0.2,
            step=0.1,
            help="Higher values make output more random, lower values more deterministic"
        )
        
        # Debug mode
        debug_mode = st.checkbox("Debug Mode", value=False)
        
        # Set environment variables based on settings
        os.environ["LLM_MODEL"] = model
        os.environ["LLM_TEMPERATURE"] = str(temperature)
        os.environ["LOG_LEVEL"] = "DEBUG" if debug_mode else "INFO"
        
        st.markdown("---")
        st.markdown(f"**App Version:** {__version__}")
        st.markdown("Made with ❤️ using CrewAI")

    # Main content
    st.markdown("<h1 class='main-header'>YouTube Video Analysis</h1>", unsafe_allow_html=True)
    st.markdown("<p class='info-text'>This tool analyzes YouTube videos using AI to provide insights, summaries, and action plans.</p>", unsafe_allow_html=True)
    
    # URL input
    youtube_url = st.text_input("Enter YouTube URL", placeholder="https://youtu.be/...")
    
    # Analysis button
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        analyze_button = st.button("Analyze Video", type="primary", use_container_width=True)
    
    # Run analysis when button is clicked
    if analyze_button:
        if not youtube_url:
            st.error("Please enter a YouTube URL.")
        elif not validate_youtube_url(youtube_url):
            st.error("Please enter a valid YouTube URL.")
        else:
            with st.spinner("Analyzing video..."):
                results, error = run_analysis(youtube_url)
                
                if error:
                    st.markdown(f"<div class='error-box'>Error: {error}</div>", unsafe_allow_html=True)
                elif results:
                    # Display video information
                    video_id = results["video_id"]
                    thumbnail_url = extract_youtube_thumbnail(video_id)
                    
                    st.markdown("<h2 class='sub-header'>Analysis Results</h2>", unsafe_allow_html=True)
                    
                    # Display video thumbnail
                    st.markdown(f"<img src='{thumbnail_url}' class='youtube-thumbnail' alt='Video Thumbnail'>", unsafe_allow_html=True)
                    
                    # Create tabs for different sections of the output
                    tabs = st.tabs(["Report","Summary", "Analysis", "Action Plan", "Transcript", "Raw Output"])
                    
                    # Parse the output to extract different sections
                    output = results["output"]
                    task_outputs = results["task_outputs"]
                    
                    # Based on the task outputs, display the content in the tabs
                    with tabs[0]:
                        st.markdown(task_outputs["write_report"])
                    
                    with tabs[1]:
                        st.markdown(task_outputs["summarize_content"])
                    
                    with tabs[2]:
                        st.markdown(task_outputs["analyze_content"])
                    
                    with tabs[3]:
                        st.markdown(task_outputs["create_action_plan"])
                    
                    with tabs[4]:
                        st.markdown(results["transcript"])
                    
                    with tabs[5]:
                        st.markdown(results["output"])
                    
                    # Display token usage
                    if results.get("token_usage"):
                        display_token_usage(results["token_usage"], model)
                    
                    # Add timestamp
                    st.markdown(f"<div class='token-usage'>Analysis completed at {results['timestamp']}</div>", unsafe_allow_html=True)

if __name__ == "__main__":
    main() 