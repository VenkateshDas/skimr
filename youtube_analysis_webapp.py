import streamlit as st
import os
import sys
import re
import time
import json
import logging
import io  # Add explicit import for io module
from typing import Optional, Dict, Any, Tuple, List, Sequence, TypedDict, Annotated, Callable, Generator, Union
import pandas as pd
from datetime import datetime, timedelta
import traceback
import html
import uuid
import concurrent.futures
import threading
import markdown
import base64
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListItem, ListFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib import colors
from html.parser import HTMLParser
from html import unescape
import tempfile
import numpy as np
from urllib.parse import urlparse, parse_qs
import requests

# Add the src directory to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

# Import configuration
from src.youtube_analysis.config import APP_VERSION, validate_config, setup_logging

# Import the YouTube Analysis modules
from src.youtube_analysis import run_analysis
from src.youtube_analysis.utils.youtube_utils import (
    get_transcript, 
    extract_video_id, 
    get_video_info, 
    validate_youtube_url,
    get_cached_transcription,
    cache_transcription,
    clean_markdown_fences
)
from src.youtube_analysis.utils.cache_utils import get_cached_analysis, cache_analysis, clear_analysis_cache
from src.youtube_analysis.utils.logging import get_logger
from src.youtube_analysis.auth import init_auth_state, display_auth_ui, get_current_user, logout, require_auth
from src.youtube_analysis.ui import load_css, setup_sidebar, create_welcome_message, setup_user_menu, display_video_highlights
from src.youtube_analysis.analysis import generate_video_highlights
from src.youtube_analysis.stats import increment_summary_count, get_summary_count, get_user_stats

# LangGraph and LangChain imports for chat functionality
from langchain_core.messages import AIMessage, HumanMessage, BaseMessage
from langchain_openai import ChatOpenAI

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Configure logging
setup_logging()
logger = get_logger("__main__")

# Check for OpenAI API key
openai_api_key = os.environ.get("OPENAI_API_KEY")
if not openai_api_key:
    print("WARNING: OPENAI_API_KEY is not set in the environment. Chat functionality will be limited.")
    logger.warning("OPENAI_API_KEY is not set in the environment. Chat functionality will be limited.")

# Set page configuration (must be the first Streamlit command)
st.set_page_config(
    page_title="Skimr Summarizer",
    page_icon=":material/movie:",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize session state variables for content generation to fix circular rerun bug
if "content_generation_pending" not in st.session_state:
    st.session_state.content_generation_pending = False
if "content_type_generated" not in st.session_state:
    st.session_state.content_type_generated = None

# Check if we need to rerun after content generation
if st.session_state.content_generation_pending:
    # Reset the flags to prevent infinite loops
    st.session_state.content_generation_pending = False
    content_type = st.session_state.content_type_generated
    st.session_state.content_type_generated = None
    # Log that we're doing a one-time rerun
    logger.info(f"Performing one-time rerun after generating {content_type}")
    st.rerun()

# App version
VERSION = APP_VERSION

# Helper functions for response processing
def split_into_sentences(text: str) -> List[str]:
    """Split text into sentences for better streaming."""
    # Basic sentence splitting - handles periods, question marks, and exclamation points
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    # Handle cases where the split didn't work well (too long sentences)
    result = []
    for sentence in sentences:
        if len(sentence) > 100:  # If sentence is too long, split by commas
            comma_parts = re.split(r'(?<=,)\s+', sentence)
            result.extend(comma_parts)
        else:
            result.append(sentence)
    
    return result

def self_clean_response(text: str) -> str:
    """Clean up response text to remove repetitive patterns and improve formatting."""
    if not text:
        return ""
    
    # Remove repetitive "How can I assist you today?" and similar phrases
    text = re.sub(r'(How can I assist you today\??)\s*\1', r'\1', text, flags=re.IGNORECASE)
    text = re.sub(r'(How can I help you today\??)\s*\1', r'\1', text, flags=re.IGNORECASE)
    text = re.sub(r'(How may I assist you\??)\s*\1', r'\1', text, flags=re.IGNORECASE)
    
    # Remove any repeated sentences (common in some LLM outputs)
    sentences = split_into_sentences(text)
    unique_sentences = []
    for sentence in sentences:
        if not unique_sentences or sentence.strip() != unique_sentences[-1].strip():
            unique_sentences.append(sentence)
    
    # Rejoin the unique sentences
    cleaned_text = ' '.join(unique_sentences)
    
    # Fix any double spaces
    cleaned_text = re.sub(r'\s{2,}', ' ', cleaned_text)
    
    # Remove any "AI:" or "Assistant:" prefixes that might appear
    cleaned_text = re.sub(r'^(AI:|Assistant:)\s*', '', cleaned_text)
    
    return cleaned_text

def process_transcript_async(url: str, use_cache: bool = True) -> Tuple[Optional[str], Optional[List[Dict[str, Any]]], Optional[str]]:
    """
    Process a YouTube video transcript asynchronously.
    
    Args:
        url: The YouTube video URL
        use_cache: Whether to use cached transcripts (default: True)
        
    Returns:
        A tuple containing:
        - The formatted transcript with timestamps (or None if error)
        - The list of transcript segments (or None if error)
        - An error message (or None if successful)
    """
    try:
        # Validate URL parameter
        if not url:
            logger.error("Empty URL provided to process_transcript_async")
            return None, None, "No URL provided"
            
        logger.info(f"Fetching transcript for video: {url}")
        video_id = extract_video_id(url)
        
        if not video_id:
            # Check if the URL itself might be a video ID
            if re.match(r'^[0-9A-Za-z_-]{11}$', url):
                logger.info(f"URL appears to be a direct video ID: {url}")
                video_id = url
            else:
                logger.error(f"Failed to extract video ID from URL: {url}")
                return None, None, "Could not extract video ID from URL"
        
        logger.info(f"Using video ID: {video_id}")
        
        # Check cache first if enabled
        if use_cache:
            cached_transcript = get_cached_transcription(video_id)
            if cached_transcript:
                logger.info(f"Using cached transcript for video ID: {video_id}")
                
                # Format the cached transcript with timestamps
                try:
                    # Get transcript list to reconstruct the timestamped version
                    from youtube_transcript_api import YouTubeTranscriptApi
                    transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=["en", "de", "ta"])
                    
                    # Format transcript with timestamps
                    timestamped_transcript = ""
                    for item in transcript_list:
                        start = item.get('start', 0)
                        minutes, seconds = divmod(int(start), 60)
                        timestamp = f"[{minutes:02d}:{seconds:02d}]"
                        text = item.get('text', '')
                        timestamped_transcript += f"{timestamp} {text}\n"
                    
                    return timestamped_transcript, transcript_list, None
                except Exception as e:
                    # If we can't get the transcript list, just use the cached transcript
                    logger.warning(f"Could not format cached transcript with timestamps: {str(e)}")
                    return cached_transcript, None, None
        
        # Try to get transcript with timestamps
        try:
            # Use the YouTubeTranscriptApi directly to avoid issues with get_transcript function
            from youtube_transcript_api import YouTubeTranscriptApi
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['en','de','ta'])
            
            if not transcript_list:
                logger.error(f"No transcript available for video ID: {video_id}")
                return None, None, "No transcript available for this video"
            
            # Format transcript with timestamps
            timestamped_transcript = ""
            for item in transcript_list:
                start = item.get('start', 0)
                minutes, seconds = divmod(int(start), 60)
                timestamp = f"[{minutes:02d}:{seconds:02d}]"
                text = item.get('text', '')
                timestamped_transcript += f"{timestamp} {text}\n"
            
            # Cache the transcript if caching is enabled
            if use_cache:
                cache_transcription(video_id, timestamped_transcript)
            
            logger.info(f"Successfully retrieved transcript for video ID: {video_id}")
            return timestamped_transcript, transcript_list, None
            
        except Exception as e:
            error_msg = str(e)
            logger.exception(f"Error getting transcript for video ID {video_id}: {error_msg}")
            
            # Check for specific error messages
            if "Subtitles are disabled for this video" in error_msg:
                return None, None, "Subtitles are disabled for this video"
            elif "Could not retrieve a transcript for this video" in error_msg:
                return None, None, "No transcript available for this video"
            elif "'dict' object has no attribute 'text'" in error_msg:
                return None, None, "Error parsing transcript: Unexpected transcript format"
            else:
                return None, None, f"Error retrieving transcript: {error_msg}"
    
    except Exception as e:
        error_msg = str(e)
        logger.exception(f"Unexpected error processing transcript: {error_msg}")
        return None, None, f"Unexpected error: {error_msg}"

def load_css():
    """Load custom CSS for the app."""
    st.markdown("""
    <style>
        /* Global styling */
        [data-testid="stAppViewContainer"] {
            background: #121212;
            background-attachment: fixed;
        }
        
        /* Main content area */
        [data-testid="stVerticalBlock"] {
            padding: 0 1rem;
        }
        
        /* Headers */
        h1, h2, h3, h4, h5 {
            color: #e0e0e0;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            font-weight: 600;
        }
        
        h1 {
            font-size: 2.5rem;
            margin-bottom: 1.5rem;
            color: #4dabf7;
            display: inline-block;
        }
        
        /* Subheaders */
        .sub-header {
            font-size: 1.8rem;
            margin-top: 1.5rem;
            margin-bottom: 1.2rem;
            color: #e0e0e0;
            font-weight: 600;
            border-bottom: none;
            padding-bottom: 0.5rem;
        }
        
        /* Cards */
        .card {
            padding: 1.8rem;
            border-radius: 12px;
            background: #232323;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            margin-bottom: 1.5rem;
            border: 1px solid #333333;
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }
        
        .card:hover {
            transform: translateY(-5px);
            box-shadow: 0 8px 20px rgba(0, 0, 0, 0.25);
        }
        
        /* Markdown formatting for analysis content */
        .card h1, .card h2, .card h3, .card h4, .card h5, .card h6 {
            color: #4dabf7;
            margin-top: 1.5rem;
            margin-bottom: 1rem;
            font-weight: 600;
        }
        
        .card h1 {
            font-size: 1.8rem;
            border-bottom: 1px solid #333;
            padding-bottom: 0.5rem;
        }
        
        .card h2 {
            font-size: 1.6rem;
        }
        
        .card h3 {
            font-size: 1.4rem;
        }
        
        .card h4 {
            font-size: 1.2rem;
        }
        
        .card p {
            margin-bottom: 1rem;
            line-height: 1.6;
        }
        
        .card ul, .card ol {
            margin-left: 1.5rem;
            margin-bottom: 1.5rem;
            line-height: 1.6;
        }
        
        .card li {
            margin-bottom: 0.5rem;
        }
        
        .card li::marker {
            color: #4dabf7;
        }
        
        .card code {
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            background-color: #2a2a2a;
            color: #4dabf7;
            padding: 0.2rem 0.4rem;
            border-radius: 4px;
            font-size: 0.9rem;
        }
        
        .card pre {
            background-color: #1a1a1a;
            border: 1px solid #333;
            border-radius: 6px;
            padding: 1rem;
            overflow-x: auto;
            margin-bottom: 1.5rem;
        }
        
        .card pre code {
            background-color: transparent;
            padding: 0;
            color: #e0e0e0;
            font-size: 0.9rem;
            line-height: 1.5;
        }
        
        .card blockquote {
            border-left: 3px solid #4dabf7;
            padding-left: 1rem;
            margin-left: 0;
            margin-bottom: 1.5rem;
            color: #aaaaaa;
            font-style: italic;
        }
        
        .card table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 1.5rem;
        }
        
        .card th, .card td {
            padding: 0.75rem;
            border: 1px solid #333;
            text-align: left;
        }
        
        .card th {
            background-color: #2a2a2a;
            color: #4dabf7;
            font-weight: 600;
        }
        
        .card tr:nth-child(even) {
            background-color: #1e1e1e;
        }
        
        .card tr:hover {
            background-color: #2c2c2c;
        }
        
        /* Key points styling */
        .card strong {
            color: #4dabf7;
            font-weight: 600;
        }
        
        /* Metadata */
        .metadata {
            text-align: center;
            margin-top: 15px;
            font-style: italic;
            color: #a0a0a0;
        }
        
        /* Transcript container */
        .transcript-container {
            max-height: 400px;
            overflow-y: auto;
            padding: 15px;
            background: #232323;
            border-radius: 10px;
            border: 1px solid #333333;
        }
        
        /* Make video larger */
        iframe#youtube-player {
            height: 450px !important;
            border-radius: 12px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.20);
        }
        
        /* Fix chat container scrolling */
        [data-testid="stVerticalBlock"] > div:has([data-testid="chatMessageContainer"]) {
            overflow-y: auto;
            max-height: 380px;
            padding-right: 10px;
        }
        
        /* Ensure chat input stays at bottom */
        [data-testid="stChatInput"] {
            position: sticky;
            bottom: 0;
            background: rgba(18, 18, 18, 0.9);
            backdrop-filter: blur(10px);
            padding: 15px 0;
            z-index: 100;
            border-top: 1px solid #333333;
        }
        
        /* Custom chat container */
        .custom-chat-container {
            display: flex;
            flex-direction: column;
            height: 450px;
            border: 1px solid #333333;
            border-radius: 12px;
            background: #232323;
            overflow: hidden;
            margin-top: 0;
            position: relative;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.20);
        }
        
        /* Chat message area */
        .chat-messages-area {
            flex: 1;
            overflow-y: auto;
            padding: 15px;
            margin-bottom: 60px; /* Space for input */
        }
        
        /* Chat input container - fixed at bottom */
        .chat-input-container {
            position: absolute;
            bottom: 0;
            left: 0;
            right: 0;
            background: rgba(18, 18, 18, 0.9);
            backdrop-filter: blur(10px);
            border-top: 1px solid #333333;
            padding: 15px;
            z-index: 10;
        }
        
        /* Message styling */
        .chat-message {
            margin-bottom: 15px;
            padding: 12px 16px;
            border-radius: 12px;
            max-width: 85%;
            word-wrap: break-word;
            display: flex;
            align-items: flex-start;
        }
        
        .message-avatar {
            margin-right: 12px;
            font-size: 24px;
            min-width: 30px;
        }
        
        .message-content {
            flex: 1;
        }
        
        .user-message {
            background: #4dabf7;
            color: white;
            margin-left: auto;
            box-shadow: 0 2px 8px rgba(77, 171, 247, 0.15);
        }
        
        .assistant-message {
            background: #2d2d2d;
            color: #e0e0e0;
            margin-right: auto;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
            border: 1px solid #333333;
        }
        
        .thinking {
            background: rgba(45, 45, 45, 0.7);
            color: #e0e0e0;
            margin-right: auto;
            opacity: 0.7;
        }
        
        /* Style Streamlit form components in the chat */
        .chat-input-container .stTextInput input {
            background: #2d2d2d;
            border: 1px solid #333333;
            color: #e0e0e0;
            border-radius: 8px;
            padding: 12px 16px;
        }
        
        .chat-input-container .stButton > button {
            background: #4dabf7;
            color: white;
            border: none;
            border-radius: 8px;
            padding: 0.5rem 1rem;
            font-weight: 600;
            transition: all 0.3s ease;
        }
        
        .chat-input-container .stButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(77, 171, 247, 0.3);
        }
        
        /* Fix Streamlit form styling */
        .chat-input-container [data-testid="stForm"] {
            background-color: transparent;
            border: none;
            padding: 0;
        }
        
        /* Remove form padding */
        .chat-input-container div[data-testid="stVerticalBlock"] {
            gap: 0 !important;
            padding: 0 !important;
        }
        
        /* Transcript styling */
        .transcript-line {
            margin-bottom: 10px;
            line-height: 1.6;
            word-wrap: break-word;
            overflow-wrap: break-word;
            white-space: pre-wrap;
        }
        
        .transcript-container a {
            color: #4dabf7 !important;
            text-decoration: none;
            font-weight: bold;
            display: inline-block;
            margin-right: 8px;
        }
        
        .transcript-container p {
            margin-bottom: 10px;
            line-height: 1.6;
            word-wrap: break-word;
            overflow-wrap: break-word;
            white-space: pre-wrap;
            color: #e0e0e0;
        }
        
        /* Sidebar styling */
        [data-testid="stSidebar"] {
            background: #1a1a1a;
            border-right: 1px solid #333333;
        }
        
        [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
            padding: 2rem 1rem;
        }
        
        /* Button styling */
        .stButton > button {
            background: #4dabf7;
            color: white;
            border: none;
            border-radius: 8px;
            padding: 0.5rem 1rem;
            font-weight: 600;
            transition: all 0.3s ease;
        }
        
        .stButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(77, 171, 247, 0.3);
        }
        
        /* Input field styling */
        [data-testid="stTextInput"] input {
            background: #2d2d2d;
            border: 1px solid #333333;
            color: #e0e0e0;
            border-radius: 8px;
            padding: 12px 16px;
        }
        
        /* Feature cards */
        .feature-card {
            background: #232323;
            border-radius: 12px;
            padding: 1.5rem;
            height: 100%;
            border: 1px solid #333333;
            transition: transform 0.3s ease, box-shadow 0.3s ease;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        }
        
        .feature-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 8px 20px rgba(0, 0, 0, 0.25);
        }
        
        .feature-card h3 {
            margin-top: 0;
            margin-bottom: 1rem;
            color: #4dabf7;
        }
        
        /* Step cards */
        .step-card {
            background: #232323;
            border-radius: 12px;
            padding: 1.5rem;
            height: 100%;
            border: 1px solid #333333;
            transition: transform 0.3s ease, box-shadow 0.3s ease;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        }
        
        .step-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 8px 20px rgba(0, 0, 0, 0.25);
        }
        
        .step-card h3 {
            margin-top: 0;
            margin-bottom: 1rem;
            color: #4dabf7;
        }
        
        /* Tab styling */
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
        }
        
        .stTabs [data-baseweb="tab"] {
            background-color: #2d2d2d;
            border-radius: 8px 8px 0 0;
            padding: 10px 20px;
            border: 1px solid #333333;
            border-bottom: none;
            color: #e0e0e0;
        }
        
        .stTabs [data-baseweb="tab-panel"] {
            background-color: #232323;
            border-radius: 0 0 8px 8px;
            padding: 20px;
            border: 1px solid #333333;
            border-top: none;
            color: #e0e0e0;
        }
        
        /* Progress bar */
        [data-testid="stProgressBar"] {
            background-color: rgba(255, 255, 255, 0.1);
            height: 10px;
            border-radius: 10px;
        }
        
        [data-testid="stProgressBar"] > div {
            background: #4dabf7;
            border-radius: 10px;
        }
        
        /* Additional dark mode elements */
        div.stMarkdown p {
            color: #e0e0e0;
        }
        
        .stTextInput > div > div > input {
            color: #e0e0e0;
        }
        
        .stSelectbox > div > div > div {
            background-color: #2d2d2d;
            color: #e0e0e0;
        }
        
        .stSelectbox > div > div > div:hover {
            background-color: #333333;
        }
        
        /* Slider styling */
        .stSlider > div > div > div > div {
            background-color: #4dabf7;
        }
        
        /* Checkbox styling */
        .stCheckbox > div > div > label {
            color: #e0e0e0;
        }
        
        /* Warning/error message styling */
        div[data-baseweb="notification"] {
            background-color: #2d2d2d;
            border-color: #4dabf7;
        }
        
        /* Info box styling */
        div[data-testid="stInfo"] {
            background-color: #2d2d2d;
            color: #e0e0e0;
        }
        
        /* Card strong element styling */
        .card strong {
            color: #4dabf7;
            font-weight: 600;
        }
        
        /* Tab styling - improve appearance of tabs */
        button[data-baseweb="tab"] {
            background-color: #1a1a1a;
            border: 1px solid #333;
            border-bottom: none;
            border-radius: 8px 8px 0 0;
            color: #e0e0e0;
            padding: 0.75rem 1.25rem;
            font-weight: 500;
            transition: background-color 0.2s, color 0.2s;
        }

        button[data-baseweb="tab"]:hover {
            background-color: #2a2a2a;
            color: #4dabf7;
        }

        button[data-baseweb="tab"][aria-selected="true"] {
            background-color: #2a2a2a;
            border-bottom: 2px solid #4dabf7;
            color: #4dabf7;
            font-weight: 600;
        }

        /* Tab content container styling */
        [data-testid="stTabContent"] {
            background-color: #1a1a1a;
            border: 1px solid #333;
            border-radius: 0 8px 8px 8px;
            padding: 1.5rem;
            margin-top: -1px;
        }
    </style>
    """, unsafe_allow_html=True)

# Define the state for our chat agent
class AgentState(TypedDict):
    """State for the agent."""
    messages: Annotated[Sequence[BaseMessage], "The messages in the conversation"]
    video_id: Annotated[str, "The YouTube video ID"]
    youtube_url: Annotated[str, "The YouTube video URL"]
    title: Annotated[str, "The title of the video"]
    description: Annotated[str, "The description of the video"]

def display_chat_interface():
    """Display the chat interface for interacting with the video analysis agent."""
    # Check if chat is enabled
    if not st.session_state.chat_enabled:
        st.markdown("""
        <div style="background: rgba(255, 177, 66, 0.2); border-left: 4px solid #ffb142; padding: 1.5rem; border-radius: 4px; margin-bottom: 1rem; height: 380px; display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center;">
            <h3 style="margin-top: 0; color: #ffb142;">Chat Not Available</h3>
            <p style="color: #e0e0e0;">Please analyze a video first to enable the chat functionality.</p>
        </div>
        """, unsafe_allow_html=True)
        return
    
    # Get chat details from session state
    chat_details = st.session_state.chat_details
    
    # Handle errors in chat details
    if not chat_details:
        st.markdown("""
        <div style="background: rgba(255, 177, 66, 0.2); border-left: 4px solid #ffb142; padding: 1.5rem; border-radius: 4px; margin-bottom: 1rem; height: 380px; display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center;">
            <h3 style="margin-top: 0; color: #ffb142;">Chat Details Not Found</h3>
            <p style="color: #e0e0e0;">Please analyze a video first to enable the chat functionality.</p>
        </div>
        """, unsafe_allow_html=True)
        return
    
    # Create a container for the chat messages with a fixed height
    chat_container = st.container(height=380)
    
    # Check if we need to add a welcome message (only if chat_messages is empty)
    if len(st.session_state.chat_messages) == 0:
        # Add a welcome message
        video_title = chat_details.get("title", "this video")
        welcome_message = f"Hello! I'm your AI assistant for the video \"{video_title}\". Ask me any questions about the content, and I'll do my best to answer based on the transcript. I'll include timestamps [MM:SS] in my answers to help you locate information in the video."
        st.session_state.chat_messages.append({"role": "assistant", "content": welcome_message})
    
    # Display all messages in the chat container
    with chat_container:
        # Display previous messages
        for i, message in enumerate(st.session_state.chat_messages):
            # Skip thinking messages
            if message["role"] == "thinking":
                continue
                
            # Display user messages
            if message["role"] == "user":
                with st.chat_message("user", avatar="👤"):
                    st.markdown(message["content"])
            
            # Display assistant messages
            elif message["role"] == "assistant":
                with st.chat_message("assistant", avatar="🤖"):
                    st.markdown(message["content"])
        
        # Handle streaming response if needed
        if st.session_state.streaming:
            # Get chat details from session state
            chat_details = st.session_state.chat_details
            agent = chat_details.get("agent")
            
            if agent is None:
                logger.error("Chat agent is not available for streaming")
                with st.chat_message("assistant", avatar="🤖"):
                    st.markdown("Sorry, the chat agent is not available. Please try analyzing the video again.")
                st.session_state.chat_messages.append({"role": "assistant", "content": "Sorry, the chat agent is not available. Please try analyzing the video again."})
                st.session_state.streaming = False
            else:
                thread_id = chat_details.get("thread_id", f"thread_{st.session_state.video_id}_{int(time.time())}")
                logger.info(f"Using thread ID for streaming: {thread_id}")
                
                # Get the user's question
                user_input = st.session_state.current_question
                logger.info(f"Processing streaming response for question: {user_input}")
                
                # Convert previous messages to the format expected by LangGraph
                messages = []
                for msg in st.session_state.chat_messages:
                    if msg["role"] == "user":
                        messages.append(HumanMessage(content=msg["content"]))
                    elif msg["role"] == "assistant" and msg["role"] != "thinking" and msg["content"]:
                        messages.append(AIMessage(content=msg["content"]))
                
                # Make sure the last message is the user's input
                if not messages or messages[-1].type != "human":
                    messages.append(HumanMessage(content=user_input))
                
                logger.info(f"Invoking chat agent with {len(messages)} messages for streaming")
                
                # Check if we have streaming support information
                supports_streaming = st.session_state.supports_streaming
                logger.info(f"Using streaming support: {supports_streaming}")
                
                # Get agent type
                agent_type = type(agent).__name__
                logger.info(f"Agent type in display_chat_interface: {agent_type}")
                
                # Display streaming response
                with st.chat_message("assistant", avatar="🤖"):
                    try:
                        # For CompiledStateGraph agents, use direct streaming
                        if agent_type == "CompiledStateGraph":
                            logger.info("Using direct streaming for CompiledStateGraph agent")
                            response = st.write_stream(streaming_generator(agent, messages, thread_id))
                            logger.info(f"Streaming completed, final response length: {len(response) if response else 0}")
                            
                            # Clean the response before storing
                            if response:
                                response = self_clean_response(response)
                            
                            # Add to chat history
                            st.session_state.chat_messages.append({
                                "role": "assistant",
                                "content": response
                            })
                        # For other agent types, use simulated streaming
                        else:
                            logger.info(f"Using simulated streaming for {agent_type} agent")
                            placeholder = st.empty()
                            
                            try:
                                # Use a placeholder for streaming simulation
                                current_response = ""
                                for chunk in streaming_generator(agent, messages, thread_id):
                                    current_response += chunk
                                    placeholder.markdown(current_response + "▌")
                                
                                # Set the final response
                                response = current_response.strip()
                                logger.info("Simulated streaming completed")
                                
                                # Add to chat history
                                st.session_state.chat_messages.append({
                                    "role": "assistant",
                                    "content": response
                                })
                            except Exception as e:
                                logger.error(f"Error in simulated streaming: {str(e)}")
                                logger.error(f"Traceback: {traceback.format_exc()}")
                                response = f"Sorry, I encountered an error while processing your question. Error: {str(e)}"
                                placeholder.markdown(response)
                                
                                # Add to chat history
                                st.session_state.chat_messages.append({
                                    "role": "assistant",
                                    "content": response
                                })
                    except Exception as stream_error:
                        logger.error(f"Error during streaming display: {str(stream_error)}")
                        logger.error(f"Traceback: {traceback.format_exc()}")
                        error_msg = "Sorry, I encountered an error while displaying the response. Please try again."
                        st.markdown(error_msg)
                        
                        # Add to chat history
                        st.session_state.chat_messages.append({
                            "role": "assistant",
                            "content": error_msg
                        })
                
                # Reset streaming state
                st.session_state.streaming = False
                st.session_state.current_question = None
                st.session_state.supports_streaming = False
                st.session_state.is_processing_message = False
                logger.info("Streaming state reset")
    
    # Add a user input field outside the message container
    user_input = st.chat_input("Ask a question about the video...")
    
    # Handle user input
    if user_input:
        # Log the question
        logger.info(f"User question: {user_input}")
        
        # Add user message to chat history
        st.session_state.chat_messages.append({"role": "user", "content": user_input})
        
        # Get the agent from chat details
        agent = chat_details.get("agent")
        
        # Check agent type
        agent_type = type(agent).__name__
        logger.info(f"Agent type in display_chat_interface: {agent_type}")
        
        # For CompiledStateGraph agents, set supports_streaming to False and use our custom approach
        if agent_type == "CompiledStateGraph":
            st.session_state.supports_streaming = False
            logger.info("Using custom streaming for CompiledStateGraph agent")
        else:
            # Check if the agent supports streaming
            supports_streaming = check_agent_streaming_support(agent)
            logger.info(f"Agent streaming support: {supports_streaming}")
            st.session_state.supports_streaming = supports_streaming
        
        # Set up streaming state
        st.session_state.streaming = True
        st.session_state.current_question = user_input
        
        # Rerun to display the user message first
        st.rerun()

def streaming_generator(agent, messages, thread_id=None):
    """
    Generate streaming responses from the agent and yield text chunks.
    This version is simplified for use in a Streamlit app.
    """
    
    def extract_final_answer(response):
        """Extracts the final answer from various response formats."""
        if isinstance(response, dict):
            if response.get("messages"):
                final_message = response["messages"][-1]
                return getattr(final_message, "content", str(final_message))
            elif response.get("response"):
                return response["response"]
            elif hasattr(response, "values") and hasattr(response, "get") and response.get("messages"):
                final_message = response.get("messages")[-1]
                return getattr(final_message, "content", str(final_message))
        return getattr(response, "content", response) if hasattr(response, "content") else response

    try:
        final_answer = ""
        agent_type = type(agent).__name__
        
        # Branch 1: CompiledStateGraph agent
        if agent_type == "CompiledStateGraph":
            response = agent.invoke(
                {"messages": messages},
                config={"configurable": {"thread_id": thread_id}},
            )
            final_answer = extract_final_answer(response)
            # If answer is empty or too generic, try to use tool outputs
            if not final_answer or "I can only answer questions about the content" in final_answer:
                if isinstance(response, dict) and response.get("intermediate_steps"):
                    tool_outputs = [
                        f"Found information: {step[1]}" 
                        for step in response["intermediate_steps"] 
                        if isinstance(step, tuple) and len(step) >= 2
                    ]
                    if tool_outputs:
                        final_answer = "Based on the video content:\n\n" + "\n\n".join(tool_outputs)
        
        # Branch 2: Agent with native streaming support
        elif hasattr(agent, "stream") and callable(agent.stream):
            stream = agent.stream(
                {"messages": messages},
                config={"configurable": {"thread_id": thread_id}},
            )
            current_response = ""
            for chunk in stream:
                content = getattr(chunk, "content", chunk.get("content", ""))
                if content:
                    current_response += content
                    yield content
            return current_response
        
        # Branch 3: LLM with streaming via agent.llm.stream
        elif hasattr(agent, "llm") and hasattr(agent.llm, "stream") and callable(agent.llm.stream):
            # Convert messages to the LLM expected format
            llm_messages = []
            for msg in messages:
                if msg.type == "human":
                    llm_messages.append({"role": "user", "content": msg.content})
                elif msg.type == "ai":
                    llm_messages.append({"role": "assistant", "content": msg.content})
            
            stream = agent.llm.stream(llm_messages)
            current_response = ""
            for chunk in stream:
                content = getattr(chunk, "content", chunk.get("content", ""))
                if content:
                    current_response += content
                    yield content
            return current_response
        
        # Branch 4: Fallback simulated streaming
        else:
            response = agent.invoke(
                {"messages": messages},
                config={"configurable": {"thread_id": thread_id}},
            )
            final_answer = extract_final_answer(response)
        
        # Clean up and prepare the final answer for streaming.
        # Assume these helper functions are defined elsewhere:
        #   self_clean_response(text) and split_into_sentences(text)
        final_answer = self_clean_response(final_answer)
        sentences = split_into_sentences(final_answer)
        
        # Yield each sentence with a small delay for streaming effect.
        for i, sentence in enumerate(sentences):
            yield sentence + " "
            time.sleep(0.2 if i < 5 else 0.1)
        return final_answer

    except Exception as e:
        error_msg = f"Sorry, I encountered an error while processing your question. Error: {str(e)}"
        yield error_msg
        return error_msg

def handle_chat_input():
    """Handle chat input and generate responses separately from display function."""
    # Check if there is already an active chat message processing
    if st.session_state.is_processing_message:
        return

    # Check if we're in streaming mode
    if st.session_state.streaming:
        # Mark as processing to prevent duplicate processing
        st.session_state.is_processing_message = True
        
        try:
            # Get chat details from session state
            chat_details = st.session_state.chat_details
            agent = chat_details.get("agent")
            
            if agent is None:
                logger.error("Chat agent is not available for streaming")
                # Add error message to chat history
                st.session_state.chat_messages.append({
                    "role": "assistant",
                    "content": "Sorry, the chat agent is not available. Please try analyzing the video again."
                })
                st.session_state.streaming = False
                st.session_state.is_processing_message = False
                return
            
            thread_id = chat_details.get("thread_id", f"thread_{st.session_state.video_id}_{int(time.time())}")
            logger.info(f"Using thread ID for streaming: {thread_id}")
            
            # Get the user's question
            user_input = st.session_state.current_question
            if not user_input:
                logger.error("No current question found in session state")
                st.session_state.streaming = False
                st.session_state.is_processing_message = False
                return
                
            logger.info(f"Processing streaming response for question: {user_input}")
            
            # Convert previous messages to the format expected by LangGraph
            messages = []
            for msg in st.session_state.chat_messages:
                if msg["role"] == "user":
                    messages.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "assistant" and msg["role"] != "thinking" and msg["content"]:
                    messages.append(AIMessage(content=msg["content"]))
            
            # Make sure the last message is the user's input
            if not messages or messages[-1].type != "human":
                messages.append(HumanMessage(content=user_input))
            
            logger.info(f"Invoking chat agent with {len(messages)} messages for streaming")
            
            # Check if we have streaming support information
            supports_streaming = st.session_state.supports_streaming
            logger.info(f"Using streaming support: {supports_streaming}")
            
            # Get agent type
            agent_type = type(agent).__name__
            logger.info(f"Agent type in handle_chat_input: {agent_type}")
            
            # Display streaming response
            with st.chat_message("assistant", avatar="🤖"):
                try:
                    # For CompiledStateGraph agents, use direct streaming
                    if agent_type == "CompiledStateGraph":
                        try:
                            logger.info("Using direct streaming for CompiledStateGraph agent")
                            response = st.write_stream(streaming_generator(agent, messages, thread_id))
                            logger.info(f"Streaming completed, final response length: {len(response) if response else 0}")
                            
                            # Clean the response before storing
                            if response:
                                response = self_clean_response(response)
                            
                            # Add to chat history
                            st.session_state.chat_messages.append({
                                "role": "assistant",
                                "content": response
                            })
                        except Exception as direct_error:
                            logger.error(f"Error in direct streaming: {str(direct_error)}")
                            logger.error(f"Traceback: {traceback.format_exc()}")
                            error_msg = f"Sorry, I encountered an error while processing your question. Error: {str(direct_error)}"
                            st.markdown(error_msg)
                            
                            # Add to chat history
                            st.session_state.chat_messages.append({
                                "role": "assistant",
                                "content": error_msg
                            })
                    # For other agent types, use simulated streaming
                    else:
                        logger.info(f"Using simulated streaming for {agent_type} agent")
                        placeholder = st.empty()
                        
                        try:
                            # Use a placeholder for streaming simulation
                            current_response = ""
                            for chunk in streaming_generator(agent, messages, thread_id):
                                current_response += chunk
                                placeholder.markdown(current_response + "▌")
                            
                            # Set the final response
                            response = current_response.strip()
                            logger.info("Simulated streaming completed")
                            
                            # Add to chat history
                            st.session_state.chat_messages.append({
                                "role": "assistant",
                                "content": response
                            })
                        except Exception as e:
                            logger.error(f"Error in simulated streaming: {str(e)}")
                            logger.error(f"Traceback: {traceback.format_exc()}")
                            response = f"Sorry, I encountered an error while processing your question. Error: {str(e)}"
                            placeholder.markdown(response)
                            
                            # Add to chat history
                            st.session_state.chat_messages.append({
                                "role": "assistant",
                                "content": response
                            })
                except Exception as stream_error:
                    logger.error(f"Error during streaming display: {str(stream_error)}")
                    logger.error(f"Traceback: {traceback.format_exc()}")
                    error_msg = "Sorry, I encountered an error while displaying the response. Please try again."
                    st.markdown(error_msg)
                    
                    # Add to chat history
                    st.session_state.chat_messages.append({
                        "role": "assistant",
                        "content": error_msg
                    })
                
                # Reset streaming state
                st.session_state.streaming = False
                st.session_state.current_question = None
                st.session_state.supports_streaming = False
                st.session_state.is_processing_message = False
                logger.info("Streaming state reset")
        
        except Exception as e:
            logger.error(f"Error in streaming chat: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            error_msg = f"Sorry, I encountered an error while processing your question. Please try again. Error: {str(e)}"
            
            # Add error message to chat history
            st.session_state.chat_messages.append({
                "role": "assistant",
                "content": error_msg
            })
            
            # Reset streaming state
            st.session_state.streaming = False
            st.session_state.current_question = None
            st.session_state.supports_streaming = False
            st.session_state.is_processing_message = False
        
        # Force a rerun to update the UI with the new message
        st.rerun()
    
    # Original non-streaming handling for fallback
    # Check if there's a thinking message that needs to be processed
    if (st.session_state.chat_messages and 
        st.session_state.chat_messages[-1]["role"] == "thinking"):
        
        # Mark as processing
        st.session_state.is_processing_message = True
        
        logger.info("Processing non-streaming response (fallback path)")
        
        try:
            # Get chat details from session state
            chat_details = st.session_state.chat_details
            agent = chat_details.get("agent")
            
            # Check if agent is None
            if agent is None:
                logger.error("Chat agent is not available")
                
                # Try to recreate the agent
                try:
                    from src.youtube_analysis.chat import setup_chat_for_video
                    
                    # Get necessary information
                    video_id = chat_details.get("video_id")
                    youtube_url = chat_details.get("youtube_url")
                    
                    if "analysis_results" in st.session_state and st.session_state.analysis_results:
                        results = st.session_state.analysis_results
                        
                        if "transcript" in results and results["transcript"]:
                            # Get transcript list if available
                            transcript_list = st.session_state.transcript_list if "transcript_list" in st.session_state else None
                            
                            # Create a new chat
                            new_chat_details = setup_chat_for_video(youtube_url, results["transcript"], transcript_list)
                            
                            if new_chat_details and "agent" in new_chat_details and new_chat_details["agent"] is not None:
                                # Update session state
                                st.session_state.chat_details = new_chat_details
                                
                                # Use the new agent
                                agent = new_chat_details["agent"]
                                logger.info("Successfully recreated chat agent")
                except Exception as agent_error:
                    logger.error(f"Error recreating agent: {str(agent_error)}")
            
            # If agent is still None after recreation attempt
            if agent is None:
                # Get video info from chat details
                video_title = chat_details.get("title", "this video")
                video_id = chat_details.get("video_id", "")
                
                # Create a fallback response
                fallback_response = (
                    f"I'm sorry, but the interactive chat functionality is not available for \"{video_title}\". "
                    f"This could be due to one of the following reasons:\n\n"
                    f"1. The OpenAI API key may not be configured correctly\n"
                    f"2. There might have been an issue processing the transcript\n"
                    f"3. The cached analysis might not include the chat agent\n\n"
                    f"You can still view the video analysis results and transcript. "
                    f"If you'd like to use the chat feature, please try analyzing the video again or check your API key configuration."
                )
                
                # Remove the thinking message
                st.session_state.chat_messages.pop()
                
                # Add fallback response to chat history
                st.session_state.chat_messages.append({
                    "role": "assistant",
                    "content": fallback_response
                })
                
                # Release the processing flag
                st.session_state.is_processing_message = False
                return
            
            thread_id = chat_details.get("thread_id", f"thread_{st.session_state.video_id}_{int(time.time())}")
            logger.info(f"Using thread ID: {thread_id}")
            
            # Get the user's question (the message before the thinking message)
            user_input = ""
            for i in range(len(st.session_state.chat_messages) - 1, -1, -1):
                if st.session_state.chat_messages[i]["role"] == "user":
                    user_input = st.session_state.chat_messages[i]["content"]
                    break
            
            if not user_input:
                logger.error("Could not find user message")
                # Remove the thinking message
                st.session_state.chat_messages.pop()
                # Add error message
                st.session_state.chat_messages.append({
                    "role": "assistant",
                    "content": "Sorry, I couldn't process your question. Please try again."
                })
                
                # Release the processing flag
                st.session_state.is_processing_message = False
                return
            
            logger.info(f"Processing non-streaming response for question: {user_input}")
            
            # Convert previous messages to the format expected by LangGraph (excluding the thinking message)
            messages = []
            for msg in st.session_state.chat_messages:
                if msg["role"] == "user":
                    messages.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "assistant" and msg["role"] != "thinking" and msg["content"]:
                    messages.append(AIMessage(content=msg["content"]))
            
            # Make sure the last message is the user's input
            if not messages or messages[-1].type != "human":
                messages.append(HumanMessage(content=user_input))
            
            logger.info(f"Invoking chat agent with {len(messages)} messages (non-streaming)")
            
            try:
                # Invoke the agent with the thread ID for memory persistence
                response = agent.invoke(
                    {"messages": messages},
                    config={"configurable": {"thread_id": thread_id}},
                    
                )
                
                # Extract the final answer
                final_message = response["messages"][-1]
                answer = final_message.content
                
                logger.info(f"Received response from chat agent: {answer[:100]}...")
                
                # Remove the thinking message
                st.session_state.chat_messages.pop()
                
                # Add AI response to chat history
                st.session_state.chat_messages.append({
                    "role": "assistant",
                    "content": answer
                })
            except Exception as e:
                logger.error(f"Error invoking chat agent: {str(e)}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                
                # Remove the thinking message
                st.session_state.chat_messages.pop()
                
                # Add error message to chat history
                error_message = f"Sorry, I encountered an error while processing your question. Please try again. Error: {str(e)}"
                st.session_state.chat_messages.append({
                    "role": "assistant",
                    "content": error_message
                })
        except Exception as e:
            logger.error(f"Error getting chat response: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            # Remove the thinking message if it exists
            if st.session_state.chat_messages and st.session_state.chat_messages[-1]["role"] == "thinking":
                st.session_state.chat_messages.pop()
            
            # Add error message to chat history
            error_message = "Sorry, I encountered an error while processing your question. Please try again."
            st.session_state.chat_messages.append({
                "role": "assistant",
                "content": error_message
            })
        
        # Release the processing flag
        st.session_state.is_processing_message = False
        
        # Force a rerun to update the UI with the new message
        st.rerun()
    
    return

def format_analysis_time(seconds, include_cached=False, cached=False):
    """Format analysis time in a user-friendly way and optionally show cached status"""
    if seconds < 60:
        time_str = f"{seconds:.1f} seconds"
    elif seconds < 3600:
        minutes = seconds / 60
        time_str = f"{minutes:.1f} minutes"
    else:
        hours = seconds / 3600
        time_str = f"{hours:.1f} hours"
    
    if include_cached and cached:
        return f"{time_str} (cached)"
    return time_str

def display_analysis_results(results: Dict[str, Any]):
    """
    Display the analysis results for a YouTube video.
    
    Args:
        results: The analysis results dictionary
    """
    # Import modules needed in this function
    import re
    import html
    
    # Get analysis types from session state
    analysis_types = st.session_state.settings.get("analysis_types", ["Summary & Classification"])
    logger.info(f"Displaying results for selected analysis types: {analysis_types}")
    
    # Helper function to sanitize HTML content
    def sanitize_html_content(content):
        """Clean up and sanitize HTML content for proper rendering."""
        if not content:
            return ""
        
        # Fix common HTML issues
        # First decode any HTML entities
        content = html.unescape(content)
        
        # Fix broken or incomplete HTML tags
        # Replace malformed header tags that start with <h## with proper <h3 tags
        content = re.sub(r'<h##([^>]*)>', r'<h3\1>', content)
        content = re.sub(r'</h##>', r'</h3>', content)
        
        # Replace any instances of <h with invalid numbers with <h3
        content = re.sub(r'<h(\d{2,})([^>]*)>', r'<h3\2>', content)
        content = re.sub(r'</h\d{2,}>', r'</h3>', content)
        
        # Fix specific malformed pattern from the user's example
        # <h## style="color: #4dabf7; margin-top: 1.5rem; margin-bottom: 1rem;">Classification</h##>
        content = re.sub(
            r'<h##\s+style="([^"]*)">([^<]+)</h##>',
            r'<h3 style="\1">\2</h3>',
            content
        )
        
        # Fix any other HTML header tags that might have incorrectly nested attributes
        content = re.sub(
            r'<(h\d)([^>]*?)style="([^"]*)"([^>]*?)>',
            r'<\1 style="\3"\2\4>',
            content
        )
        
        # Improve nested list handling
        # First replace any double indented items (e.g., "  - Item") with proper nesting
        content = re.sub(
            r'(?m)^(\s{2,})- (.+)$',
            r'<li class="nested-item" style="margin-left: 1.5rem; margin-bottom: 0.5rem;">\2</li>',
            content
        )
        
        # Fix common unclosed or improperly closed tags
        for tag in ['p', 'div', 'span', 'strong', 'em', 'ul', 'ol', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            # Count opening and closing tags
            open_count = len(re.findall(f'<{tag}[^>]*>', content))
            close_count = len(re.findall(f'</{tag}>', content))
            
            # Add missing closing tags
            if open_count > close_count:
                diff = open_count - close_count
                content += f'\n{"</" + tag + ">" * diff}'
        
        # Fix any unclosed or improperly nested HTML lists
        if '<li' in content and '</li>' not in content:
            content = re.sub(r'<li([^>]*)>([^<]+)', r'<li\1>\2</li>', content)
        
        # Ensure all <ul> tags have matching closing tags
        if '<ul' in content and '</ul>' not in content:
            content += '\n</ul>'
        
        # Fix improper class attributes
        content = re.sub(r'class=([^\s>]+)', r'class="\1"', content)
        
        # Fix unclosed style attributes
        content = re.sub(r'style="([^"]*?)(?=[^"]*>)', r'style="\1"', content)
        
        return content

    # Log what we're displaying
    logger.info(f"Displaying analysis results with keys: {list(results.keys())}")
    if "task_outputs" in results:
        logger.info(f"Task outputs available: {list(results['task_outputs'].keys())}")
    
    # Get video information from results
    video_id = results.get("video_id", "")
    youtube_url = results.get("youtube_url", "")
    transcript = results.get("transcript", "")
    category = results.get("category", "Unknown")
    context_tag = results.get("context_tag", "General")
    token_usage = results.get("token_usage", None)
    
    if not video_id:
        logger.error("Missing video_id in results")
        st.error("Analysis results are incomplete. Missing video ID.")
        return
    
    # Create a container for video and chat
    st.markdown("<h2 class='sub-header'>🎬 Video & Chat</h2>", unsafe_allow_html=True)
    
    # Create columns for video and chat
    video_chat_cols = st.columns([1, 1])
    
    with video_chat_cols[0]:
        # Display embedded YouTube video with API enabled
        st.markdown(f'''
        <div style="border-radius: 12px; overflow: hidden; box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);">
            <iframe id="youtube-player" 
                    width="100%" 
                    height="380" 
                    src="https://www.youtube.com/embed/{video_id}?rel=0&modestbranding=1" 
                    frameborder="0" 
                    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" 
                    allowfullscreen>
            </iframe>
        </div>
        ''', unsafe_allow_html=True)
    
    with video_chat_cols[1]:
        # Display chat interface
        if "chat_enabled" in st.session_state and st.session_state.chat_enabled:
            if "chat_details" in st.session_state and st.session_state.chat_details:
                display_chat_interface()
            else:
                st.markdown("""
                <div style="background: rgba(255, 177, 66, 0.2); border-left: 4px solid #ffb142; padding: 1.5rem; border-radius: 4px; margin-bottom: 1rem; height: 380px; display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center;">
                    <h3 style="margin-top: 0; color: #ffb142;">Chat Details Not Found</h3>
                    <p style="color: #e0e0e0;">The chat functionality could not be initialized properly. Please try analyzing the video again.</p>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="background: rgba(225, 77, 77, 0.2); border-left: 4px solid #e14d4d; padding: 1.5rem; border-radius: 4px; margin-bottom: 1rem; height: 380px; display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center;">
                <h3 style="margin-top: 0; color: #ff6b6b;">Chat Unavailable</h3>
                <p style="color: #e0e0e0;">Chat functionality could not be enabled for this video. This could be due to missing API keys or issues with the transcript. Please check your configuration and try again.</p>
            </div>
            """, unsafe_allow_html=True)
    
    # Create a container for analysis content
    if category and category != "Unknown":
        category_colors = {
            "Technology": "#3498db",
            "Business": "#2ecc71",
            "Education": "#9b59b6",
            "Entertainment": "#e74c3c",
            "Science": "#1abc9c",
            "Health & Wellness": "#e67e22",
            "News": "#f1c40f",
            "Sports": "#d35400",
            "Gaming": "#8e44ad",
            "Music": "#c0392b",
            "Travel": "#16a085",
            "Food": "#f39c12",
            "Fashion": "#e84393",
            "Lifestyle": "#6c5ce7"
        }
        
        # Context tag colors using a complementary color scheme
        context_tag_colors = {
            "Tutorial": "#4a69bd",      # Blue
            "News": "#f6b93b",          # Yellow
            "Review": "#78e08f",        # Green
            "Case Study": "#fa983a",    # Orange
            "Interview": "#b71540",     # Red
            "Opinion Piece": "#8c7ae6", # Purple
            "How-To Guide": "#e58e26",  # Amber
            "General": "#95a5a6"        # Gray
        }
        
        color = category_colors.get(category, "#95a5a6")
        context_color = context_tag_colors.get(context_tag, "#95a5a6")
        
        st.markdown(f"""
        <div style="display: flex; align-items: center; margin-bottom: 1rem;">
            <h2 class='sub-header' style="margin-bottom: 0; margin-right: 1rem;">📊 Analysis Results</h2>
            <span style="background-color: {color}; color: white; padding: 0.3rem 0.8rem; border-radius: 20px; font-weight: 600; font-size: 0.9rem; margin-right: 0.5rem;">
                {category}
            </span>
            <span style="background-color: {context_color}; color: white; padding: 0.3rem 0.8rem; border-radius: 20px; font-weight: 600; font-size: 0.9rem;">
                {context_tag}
            </span>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("<h2 class='sub-header'>📊 Analysis Results</h2>", unsafe_allow_html=True)
    
    # Add section for generating additional analysis types on demand
    video_id = results.get("video_id", "")
    youtube_url = results.get("youtube_url", "")
    transcript = results.get("transcript", "")
    task_outputs = results.get("task_outputs", {})
    
    # Create an expander for the on-demand generation options
    with st.expander("🔄 Generate Additional Content Types", expanded=True):
        st.write("Generate additional content types on demand based on this video.")
        
        # Create a row of buttons for different analysis types
        additional_col1, additional_col2, additional_col3, additional_col4 = st.columns(4)
        
        # Button for generating Action Plan
        with additional_col1:
            action_plan_disabled = "analyze_and_plan_content" in task_outputs
            action_plan_btn_text = "📋 Action Plan" if not action_plan_disabled else "✅ Action Plan (Available in Full report) "
            
            if st.button(action_plan_btn_text, disabled=action_plan_disabled, key="generate_action_plan"):
                with st.spinner("Generating Action Plan..."):
                    # Create progress and status placeholders
                    progress_placeholder = st.empty()
                    status_placeholder = st.empty()
                    progress_bar = progress_placeholder.progress(0)
                    
                    # Define update callbacks
                    def update_progress(value):
                        progress_bar.progress(value / 100)
                    
                    def update_status(message):
                        status_placeholder.write(message)
                    
                    # Generate the action plan
                    action_plan_content, result = generate_additional_analysis(
                        youtube_url=youtube_url,
                        video_id=video_id,
                        transcript=transcript,
                        analysis_type="Action Plan",
                        progress_callback=update_progress,
                        status_callback=update_status
                    )
                    
                    # Clear progress indicators
                    progress_placeholder.empty()
                    status_placeholder.empty()
                    
                    if action_plan_content is None:
                        # Result contains the error message
                        st.error(f"Failed to generate Action Plan: {result}")
                    else:
                        # Result contains metadata
                        # Update the results in session state
                        if "task_outputs" not in st.session_state.analysis_results:
                            st.session_state.analysis_results["task_outputs"] = {}
                        
                        st.session_state.analysis_results["task_outputs"]["analyze_and_plan_content"] = action_plan_content
                        
                        # Store token usage information if available
                        if isinstance(result, dict) and "token_usage" in result:
                            if "token_usage_by_task" not in st.session_state.analysis_results:
                                st.session_state.analysis_results["token_usage_by_task"] = {}
                            
                            # Handle UsageMetrics object from CrewAI
                            token_usage = result["token_usage"]
                            if hasattr(token_usage, 'get'):
                                # Already a dictionary
                                token_info = token_usage
                            else:
                                # Convert UsageMetrics object to dictionary
                                token_info = {
                                    "total_tokens": getattr(token_usage, 'total_tokens', 0),
                                    "prompt_tokens": getattr(token_usage, 'prompt_tokens', 0),
                                    "completion_tokens": getattr(token_usage, 'completion_tokens', 0)
                                }
                            
                            st.session_state.analysis_results["token_usage_by_task"]["analyze_and_plan_content"] = token_info
                        
                        # Store analysis time information if available
                        if isinstance(result, dict) and "analysis_time" in result:
                            if "analysis_time_by_task" not in st.session_state.analysis_results:
                                st.session_state.analysis_results["analysis_time_by_task"] = {}
                            st.session_state.analysis_results["analysis_time_by_task"]["analyze_and_plan_content"] = {
                                "time": result["analysis_time"],
                                "cached": result.get("cached", False)
                            }
                        
                        st.success("Action Plan generated successfully! Available in full report.")
                        # Set flag to trigger a single rerun to show new content
                        st.session_state.content_generation_pending = True
                        st.session_state.content_type_generated = "Action Plan"
        
        # Button for generating Blog Post
        with additional_col2:
            blog_disabled = "write_blog_post" in task_outputs
            blog_btn_text = "📝 Blog Post" if not blog_disabled else "✅ Blog Post (Available)"
            
            if st.button(blog_btn_text, disabled=blog_disabled, key="generate_blog_post"):
                with st.spinner("Generating Blog Post..."):
                    # Create progress and status placeholders
                    progress_placeholder = st.empty()
                    status_placeholder = st.empty()
                    progress_bar = progress_placeholder.progress(0)
                    
                    # Define update callbacks
                    def update_progress(value):
                        progress_bar.progress(value / 100)
                    
                    def update_status(message):
                        status_placeholder.write(message)
                    
                    # Generate the blog post
                    blog_content, result = generate_additional_analysis(
                        youtube_url=youtube_url,
                        video_id=video_id,
                        transcript=transcript,
                        analysis_type="Blog Post",
                        progress_callback=update_progress,
                        status_callback=update_status
                    )
                    
                    # Clear progress indicators
                    progress_placeholder.empty()
                    status_placeholder.empty()
                    
                    if blog_content is None:
                        # Result contains the error message
                        st.error(f"Failed to generate Blog Post: {result}")
                    else:
                        # Result contains metadata
                        # Update the results in session state
                        if "task_outputs" not in st.session_state.analysis_results:
                            st.session_state.analysis_results["task_outputs"] = {}
                        
                        st.session_state.analysis_results["task_outputs"]["write_blog_post"] = blog_content
                        
                        # Store token usage information if available
                        if isinstance(result, dict) and "token_usage" in result:
                            if "token_usage_by_task" not in st.session_state.analysis_results:
                                st.session_state.analysis_results["token_usage_by_task"] = {}
                            
                            # Handle UsageMetrics object from CrewAI
                            token_usage = result["token_usage"]
                            if hasattr(token_usage, 'get'):
                                # Already a dictionary
                                token_info = token_usage
                            else:
                                # Convert UsageMetrics object to dictionary
                                token_info = {
                                    "total_tokens": getattr(token_usage, 'total_tokens', 0),
                                    "prompt_tokens": getattr(token_usage, 'prompt_tokens', 0),
                                    "completion_tokens": getattr(token_usage, 'completion_tokens', 0)
                                }
                            
                            st.session_state.analysis_results["token_usage_by_task"]["write_blog_post"] = token_info
                        
                        # Store analysis time information if available
                        if isinstance(result, dict) and "analysis_time" in result:
                            if "analysis_time_by_task" not in st.session_state.analysis_results:
                                st.session_state.analysis_results["analysis_time_by_task"] = {}
                            st.session_state.analysis_results["analysis_time_by_task"]["write_blog_post"] = {
                                "time": result["analysis_time"],
                                "cached": result.get("cached", False)
                            }
                        
                        st.success("Blog Post generated successfully!")
                        # Set flag to trigger a single rerun to show new content
                        st.session_state.content_generation_pending = True
                        st.session_state.content_type_generated = "Blog Post"
        
        # Button for generating LinkedIn Post
        with additional_col3:
            linkedin_disabled = "write_linkedin_post" in task_outputs
            linkedin_btn_text = "💼 LinkedIn Post" if not linkedin_disabled else "✅ LinkedIn Post (Available)"
            
            if st.button(linkedin_btn_text, disabled=linkedin_disabled, key="generate_linkedin_post"):
                with st.spinner("Generating LinkedIn Post..."):
                    # Create progress and status placeholders
                    progress_placeholder = st.empty()
                    status_placeholder = st.empty()
                    progress_bar = progress_placeholder.progress(0)
                    
                    # Define update callbacks
                    def update_progress(value):
                        progress_bar.progress(value / 100)
                    
                    def update_status(message):
                        status_placeholder.write(message)
                    
                    # Generate the LinkedIn post
                    linkedin_content, result = generate_additional_analysis(
                        youtube_url=youtube_url,
                        video_id=video_id,
                        transcript=transcript,
                        analysis_type="LinkedIn Post",
                        progress_callback=update_progress,
                        status_callback=update_status
                    )
                    
                    # Clear progress indicators
                    progress_placeholder.empty()
                    status_placeholder.empty()
                    
                    if linkedin_content is None:
                        # Result contains the error message
                        st.error(f"Failed to generate LinkedIn Post: {result}")
                    else:
                        # Result contains metadata
                        # Update the results in session state
                        if "task_outputs" not in st.session_state.analysis_results:
                            st.session_state.analysis_results["task_outputs"] = {}
                        
                        st.session_state.analysis_results["task_outputs"]["write_linkedin_post"] = linkedin_content
                        
                        # Store token usage information if available
                        if isinstance(result, dict) and "token_usage" in result:
                            if "token_usage_by_task" not in st.session_state.analysis_results:
                                st.session_state.analysis_results["token_usage_by_task"] = {}
                            
                            # Handle UsageMetrics object from CrewAI
                            token_usage = result["token_usage"]
                            if hasattr(token_usage, 'get'):
                                # Already a dictionary
                                token_info = token_usage
                            else:
                                # Convert UsageMetrics object to dictionary
                                token_info = {
                                    "total_tokens": getattr(token_usage, 'total_tokens', 0),
                                    "prompt_tokens": getattr(token_usage, 'prompt_tokens', 0),
                                    "completion_tokens": getattr(token_usage, 'completion_tokens', 0)
                                }
                            
                            st.session_state.analysis_results["token_usage_by_task"]["write_linkedin_post"] = token_info
                        
                        # Store analysis time information if available
                        if isinstance(result, dict) and "analysis_time" in result:
                            if "analysis_time_by_task" not in st.session_state.analysis_results:
                                st.session_state.analysis_results["analysis_time_by_task"] = {}
                            st.session_state.analysis_results["analysis_time_by_task"]["write_linkedin_post"] = {
                                "time": result["analysis_time"],
                                "cached": result.get("cached", False)
                            }
                        
                        st.success("LinkedIn Post generated successfully!")
                        # Set flag to trigger a single rerun to show new content
                        st.session_state.content_generation_pending = True
                        st.session_state.content_type_generated = "LinkedIn Post"
        
        # Button for generating X Tweet
        with additional_col4:
            tweet_disabled = "write_tweet" in task_outputs
            tweet_btn_text = "🐦 X Tweet" if not tweet_disabled else "✅ X Tweet (Available)"
            
            if st.button(tweet_btn_text, disabled=tweet_disabled, key="generate_tweet"):
                with st.spinner("Generating X Tweet..."):
                    # Create progress and status placeholders
                    progress_placeholder = st.empty()
                    status_placeholder = st.empty()
                    progress_bar = progress_placeholder.progress(0)
                    
                    # Define update callbacks
                    def update_progress(value):
                        progress_bar.progress(value / 100)
                    
                    def update_status(message):
                        status_placeholder.write(message)
                    
                    # Generate the tweet
                    tweet_content, result = generate_additional_analysis(
                        youtube_url=youtube_url,
                        video_id=video_id,
                        transcript=transcript,
                        analysis_type="X Tweet",
                        progress_callback=update_progress,
                        status_callback=update_status
                    )
                    
                    # Clear progress indicators
                    progress_placeholder.empty()
                    status_placeholder.empty()
                    
                    if tweet_content is None:
                        # Result contains the error message
                        st.error(f"Failed to generate X Tweet: {result}")
                    else:
                        # Result contains metadata
                        # Update the results in session state
                        if "task_outputs" not in st.session_state.analysis_results:
                            st.session_state.analysis_results["task_outputs"] = {}
                        
                        st.session_state.analysis_results["task_outputs"]["write_tweet"] = tweet_content
                        
                        # Store token usage information if available
                        if isinstance(result, dict) and "token_usage" in result:
                            if "token_usage_by_task" not in st.session_state.analysis_results:
                                st.session_state.analysis_results["token_usage_by_task"] = {}
                            
                            # Handle UsageMetrics object from CrewAI
                            token_usage = result["token_usage"]
                            if hasattr(token_usage, 'get'):
                                # Already a dictionary
                                token_info = token_usage
                            else:
                                # Convert UsageMetrics object to dictionary
                                token_info = {
                                    "total_tokens": getattr(token_usage, 'total_tokens', 0),
                                    "prompt_tokens": getattr(token_usage, 'prompt_tokens', 0),
                                    "completion_tokens": getattr(token_usage, 'completion_tokens', 0)
                                }
                            
                            st.session_state.analysis_results["token_usage_by_task"]["write_tweet"] = token_info
                        
                        # Store analysis time information if available
                        if isinstance(result, dict) and "analysis_time" in result:
                            if "analysis_time_by_task" not in st.session_state.analysis_results:
                                st.session_state.analysis_results["analysis_time_by_task"] = {}
                            st.session_state.analysis_results["analysis_time_by_task"]["write_tweet"] = {
                                "time": result["analysis_time"],
                                "cached": result.get("cached", False)
                            }
                        
                        st.success("X Tweet generated successfully!")
                        # Set flag to trigger a single rerun to show new content
                        st.session_state.content_generation_pending = True
                        st.session_state.content_type_generated = "X Tweet"
    
    analysis_container = st.container()
    
    with analysis_container:
        # Safely get analysis types from session state
        default_types = ["Summary & Classification", "Action Plan", "Blog Post", "LinkedIn Post", "X Tweet"]
        analysis_types = default_types
        if "settings" in st.session_state and "analysis_types" in st.session_state.settings:
            analysis_types = st.session_state.settings["analysis_types"]
        
        # Get task outputs to determine what content is available
        task_outputs = results.get("task_outputs", {})
        
        # Determine which tabs to show
        tab_options = ["📄 Full Report"]
        tab_index = 1  # Keep track of tab index for accessing tabs later
        
        # Store the indices for each tab to access them correctly later
        blog_tab_index = None
        linkedin_tab_index = None
        tweet_tab_index = None
        transcript_tab_index = None
        highlights_tab_index = None
        
        # Show tabs for all available content, regardless of initial selection
        # This ensures that if a user generates content on demand, they will see it
        if "write_blog_post" in task_outputs:
            tab_options.append("📝 Blog Post")
            blog_tab_index = tab_index
            tab_index += 1
            
        if "write_linkedin_post" in task_outputs:
            tab_options.append("💼 LinkedIn Post")
            linkedin_tab_index = tab_index
            tab_index += 1
            
        if "write_tweet" in task_outputs:
            tab_options.append("🐦 X Tweet")
            tweet_tab_index = tab_index
            tab_index += 1
        
        # Always include transcript and video highlights
        tab_options.append("🎙️ Transcript")
        transcript_tab_index = tab_index
        tab_index += 1
        
        tab_options.append("🎬 Video Highlights")
        highlights_tab_index = tab_index
        
        # Create tabs
        tabs = st.tabs(tab_options)
        
        task_outputs = results.get("task_outputs", {})
        
        # Display content in tabs
        with tabs[0]:
            # Get selected analysis types
            selected_analysis_types = st.session_state.settings.get("analysis_types", ["Summary & Classification"])
            
            # Display token usage and analysis time if available for the overall analysis
            if "token_usage" in results and results["token_usage"]:
                token_info = results["token_usage"]
                # Handle both dictionary type (cached) and UsageMetrics object type
                if hasattr(token_info, 'get'):
                    # It's a dictionary
                    tokens_display = f"**Token Usage (Initial Analysis):** {token_info.get('total_tokens', 'N/A')} total tokens"
                    if "prompt_tokens" in token_info and "completion_tokens" in token_info:
                        tokens_display += f" ({token_info.get('prompt_tokens', 'N/A')} prompt, {token_info.get('completion_tokens', 'N/A')} completion)"
                else:
                    # It's a UsageMetrics object
                    total = getattr(token_info, 'total_tokens', 'N/A')
                    prompt = getattr(token_info, 'prompt_tokens', 'N/A')
                    completion = getattr(token_info, 'completion_tokens', 'N/A')
                    tokens_display = f"**Token Usage (Initial Analysis):** {total} total tokens"
                    tokens_display += f" ({prompt} prompt, {completion} completion)"
                st.markdown(tokens_display)
            
            # Display analysis time if available
            if "analysis_time" in results:
                analysis_time = results["analysis_time"]
                time_display = f"**Analysis Time:** {format_analysis_time(analysis_time)}"
                st.markdown(time_display)
            
            # Always show Summary & Classification if available
            report_sections = []
            if "classify_and_summarize_content" in task_outputs:
                report_sections.append(f"""
## Classification and Summary

{task_outputs["classify_and_summarize_content"]}
""")
            
            # Show Action Plan if selected or if it was generated on-demand
            if ("Action Plan" in selected_analysis_types or "analyze_and_plan_content" in task_outputs) and "analyze_and_plan_content" in task_outputs:
                report_sections.append(f"""
## Analysis and Action Plan

{task_outputs["analyze_and_plan_content"]}
""")
            
            if report_sections:
                report_content = "\n".join(report_sections)
                
                # Create an expander for copying the report
                with st.expander("Copy Full Report"):
                    st.code(report_content, language="markdown")
                
                # Display using Streamlit's native markdown support
                # if the report content is within fenced code blocks, then remove the top and bottom fences
                report_content = clean_markdown_fences(report_content)
                st.markdown(report_content)
            else:
                st.info("Full report not available.")
                
        # Blog Post Tab - only display if it was selected and available
        if blog_tab_index is not None:
            with tabs[blog_tab_index]:
                # Use native Streamlit markdown for better rendering
                st.markdown("### Blog Post")
                
                # Get the blog content
                blog_content = task_outputs["write_blog_post"]
                
                # Display token usage and analysis time if available
                metrics_col1, metrics_col2 = st.columns(2)
                
                with metrics_col1:
                    if "token_usage_by_task" in results and "write_blog_post" in results["token_usage_by_task"]:
                        token_info = results["token_usage_by_task"]["write_blog_post"]
                        # Handle both dictionary type (cached) and UsageMetrics object type
                        if hasattr(token_info, 'get'):
                            # It's a dictionary
                            tokens_display = f"**Token Usage:** {token_info.get('total_tokens', 'N/A')} total tokens"
                            if "prompt_tokens" in token_info and "completion_tokens" in token_info:
                                tokens_display += f" ({token_info.get('prompt_tokens', 'N/A')} prompt, {token_info.get('completion_tokens', 'N/A')} completion)"
                        else:
                            # It's a UsageMetrics object
                            total = getattr(token_info, 'total_tokens', 'N/A')
                            prompt = getattr(token_info, 'prompt_tokens', 'N/A')
                            completion = getattr(token_info, 'completion_tokens', 'N/A')
                            tokens_display = f"**Token Usage:** {total} total tokens"
                            tokens_display += f" ({prompt} prompt, {completion} completion)"
                        st.markdown(tokens_display)
                
                with metrics_col2:
                    if "analysis_time_by_task" in results and "write_blog_post" in results["analysis_time_by_task"]:
                        analysis_info = results["analysis_time_by_task"]["write_blog_post"]
                        analysis_time = analysis_info.get("time", 0)
                        cached = analysis_info.get("cached", False)
                        time_display = f"**Analysis Time:** {format_analysis_time(analysis_time, True, cached)}"
                        st.markdown(time_display)
                
                # Create an expander for copying the blog post
                with st.expander("Copy Blog Post"):
                    st.code(blog_content, language="markdown")
                    
                # Display using Streamlit's native markdown support
                # if the blog content is within fenced code blocks, then remove the top and bottom fences
                blog_content = clean_markdown_fences(blog_content)
                st.markdown(blog_content)
        
        # LinkedIn Post Tab - only display if it was selected and available
        if linkedin_tab_index is not None:
            with tabs[linkedin_tab_index]:
                # Display LinkedIn header
                st.markdown("""
                <div style="display: flex; align-items: center; margin-bottom: 1rem;">
                    <div style="width: 60px; height: 60px; border-radius: 50%; background-color: #0A66C2; display: flex; justify-content: center; align-items: center; margin-right: 1rem;">
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="32" height="32" fill="#FFFFFF">
                            <path d="M20.5 2h-17A1.5 1.5 0 002 3.5v17A1.5 1.5 0 003.5 22h17a1.5 1.5 0 001.5-1.5v-17A1.5 1.5 0 0020.5 2zM8 19H5v-9h3zM6.5 8.25A1.75 1.75 0 118.3 6.5a1.78 1.78 0 01-1.8 1.75zM19 19h-3v-4.74c0-1.42-.6-1.93-1.38-1.93A1.74 1.74 0 0013 14.19a.66.66 0 000 .14V19h-3v-9h2.9v1.3a3.11 3.11 0 012.7-1.4c1.55 0 3.36.86 3.36 3.66z"></path>
                        </svg>
                    </div>
                    <div>
                        <div style="font-weight: bold; color: #e0e0e0;">LinkedIn Post</div>
                        <div style="color: #a0a0a0; font-size: 0.9rem;">Professional Network</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # Display token usage and analysis time if available
                metrics_col1, metrics_col2 = st.columns(2)
                
                with metrics_col1:
                    if "token_usage_by_task" in results and "write_linkedin_post" in results["token_usage_by_task"]:
                        token_info = results["token_usage_by_task"]["write_linkedin_post"]
                        # Handle both dictionary type (cached) and UsageMetrics object type
                        if hasattr(token_info, 'get'):
                            # It's a dictionary
                            tokens_display = f"**Token Usage:** {token_info.get('total_tokens', 'N/A')} total tokens"
                            if "prompt_tokens" in token_info and "completion_tokens" in token_info:
                                tokens_display += f" ({token_info.get('prompt_tokens', 'N/A')} prompt, {token_info.get('completion_tokens', 'N/A')} completion)"
                        else:
                            # It's a UsageMetrics object
                            total = getattr(token_info, 'total_tokens', 'N/A')
                            prompt = getattr(token_info, 'prompt_tokens', 'N/A')
                            completion = getattr(token_info, 'completion_tokens', 'N/A')
                            tokens_display = f"**Token Usage:** {total} total tokens"
                            tokens_display += f" ({prompt} prompt, {completion} completion)"
                        st.markdown(tokens_display)
                
                with metrics_col2:
                    if "analysis_time_by_task" in results and "write_linkedin_post" in results["analysis_time_by_task"]:
                        analysis_info = results["analysis_time_by_task"]["write_linkedin_post"]
                        analysis_time = analysis_info.get("time", 0)
                        cached = analysis_info.get("cached", False)
                        time_display = f"**Analysis Time:** {format_analysis_time(analysis_time, True, cached)}"
                        st.markdown(time_display)
                
                # Get the LinkedIn content
                linkedin_content = task_outputs["write_linkedin_post"]
                
                # Create an expander for copying the LinkedIn post
                with st.expander("Copy LinkedIn Post"):
                    st.code(linkedin_content, language="text")
                
                # Format hashtags for display (not for copy)
                display_content = re.sub(r'(#\w+)', r'**\1**', linkedin_content)
                
                # Display using Streamlit's native markdown support
                st.markdown(display_content)
        
        # X/Twitter Post Tab - only display if it was selected and available
        if tweet_tab_index is not None:
            with tabs[tweet_tab_index]:
                # Display X/Twitter header
                st.markdown("""
                <div style="display: flex; align-items: center; margin-bottom: 1rem;">
                    <div style="width: 60px; height: 60px; border-radius: 50%; background-color: #1DA1F2; display: flex; justify-content: center; align-items: center; margin-right: 1rem;">
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="32" height="32" fill="#FFFFFF">
                            <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"></path>
                        </svg>
                    </div>
                    <div>
                        <div style="font-weight: bold; color: #e0e0e0;">X (Twitter) Post</div>
                        <div style="color: #a0a0a0; font-size: 0.9rem;">Social Media</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # Display token usage and analysis time if available
                metrics_col1, metrics_col2 = st.columns(2)
                
                with metrics_col1:
                    if "token_usage_by_task" in results and "write_tweet" in results["token_usage_by_task"]:
                        token_info = results["token_usage_by_task"]["write_tweet"]
                        # Handle both dictionary type (cached) and UsageMetrics object type
                        if hasattr(token_info, 'get'):
                            # It's a dictionary
                            tokens_display = f"**Token Usage:** {token_info.get('total_tokens', 'N/A')} total tokens"
                            if "prompt_tokens" in token_info and "completion_tokens" in token_info:
                                tokens_display += f" ({token_info.get('prompt_tokens', 'N/A')} prompt, {token_info.get('completion_tokens', 'N/A')} completion)"
                        else:
                            # It's a UsageMetrics object
                            total = getattr(token_info, 'total_tokens', 'N/A')
                            prompt = getattr(token_info, 'prompt_tokens', 'N/A')
                            completion = getattr(token_info, 'completion_tokens', 'N/A')
                            tokens_display = f"**Token Usage:** {total} total tokens"
                            tokens_display += f" ({prompt} prompt, {completion} completion)"
                        st.markdown(tokens_display)
                
                with metrics_col2:
                    if "analysis_time_by_task" in results and "write_tweet" in results["analysis_time_by_task"]:
                        analysis_info = results["analysis_time_by_task"]["write_tweet"]
                        analysis_time = analysis_info.get("time", 0)
                        cached = analysis_info.get("cached", False)
                        time_display = f"**Analysis Time:** {format_analysis_time(analysis_time, True, cached)}"
                        st.markdown(time_display)
                
                # Get the tweet content
                tweet_content = task_outputs["write_tweet"]
                
                # Create an expander for copying the tweet
                with st.expander("Copy Tweet"):
                    st.code(tweet_content, language="text")
                
                # Format hashtags and mentions for display (not for copy)
                display_tweet = re.sub(r'(#\w+)', r'**\1**', tweet_content)
                display_tweet = re.sub(r'(@\w+)', r'**\1**', display_tweet)
                
                # Display using Streamlit's native markdown support
                st.markdown(display_tweet)
        
        # Transcript Tab
        with tabs[transcript_tab_index]:
            st.markdown("<h3 style='margin-bottom: 1rem;'>Video Transcript</h3>", unsafe_allow_html=True)
            
            # Add toggles for timestamps
            col_a, col_b, col_c = st.columns([1, 1, 1])
            with col_a:
                show_timestamps = st.checkbox("Show timestamps", value=True)
            
            if show_timestamps:
                # Check if we have a timestamped transcript in session state
                if "timestamped_transcript" in st.session_state and st.session_state.timestamped_transcript:
                    # Display plain text transcript with timestamps
                    st.text_area("Transcript with timestamps", st.session_state.timestamped_transcript, height=400, label_visibility="collapsed")
                else:
                    # Try to get transcript with timestamps
                    try:
                        # Check if URL is available in results, otherwise use video_id
                        if "url" in results and results["url"]:
                            youtube_url = results["url"]
                        elif "youtube_url" in results and results["youtube_url"]:
                            youtube_url = results["youtube_url"]
                        else:
                            # Construct a URL from the video_id
                            youtube_url = f"https://youtu.be/{video_id}"
                            
                        logger.info(f"Retrieving transcript for URL: {youtube_url}")
                        
                        # Get cache setting safely
                        use_cache = True  # Default value
                        if "settings" in st.session_state and isinstance(st.session_state.settings, dict):
                            use_cache = st.session_state.settings.get("use_cache", True)
                        
                        timestamped_transcript, transcript_list, error = process_transcript_async(
                            youtube_url, 
                            use_cache=use_cache
                        )
                        
                        if error:
                            raise ValueError(error)
                            
                        st.session_state.timestamped_transcript = timestamped_transcript
                        st.session_state.transcript_list = transcript_list
                        
                        # Display plain text transcript with timestamps
                        st.text_area("Transcript with timestamps", timestamped_transcript, height=400, label_visibility="collapsed")
                    except Exception as e:
                        st.error(f"Error retrieving transcript with timestamps: {str(e)}")
                        if "transcript" in results:
                            st.text_area("Transcript", results["transcript"], height=400, label_visibility="collapsed")
                        else:
                            st.error("No transcript available.")
            else:
                # Show regular transcript
                if "transcript" in results:
                    st.text_area("Transcript", results["transcript"], height=400, label_visibility="collapsed")
        
        # Video Highlights Tab
        with tabs[highlights_tab_index]:
            try:
                # Check if highlights were previously generated
                if "highlights_video_path" in st.session_state and "highlights_segments" in st.session_state and st.session_state.highlights_video_path and st.session_state.highlights_segments:
                    # Display the highlights video that was already generated
                    display_video_highlights(
                        st.session_state.highlights_video_path,
                        st.session_state.highlights_segments
                    )
                else:
                    # Show button to generate highlights
                    st.write("### Video Highlights")
                    st.write("Generate a highlights video that captures the key moments of this content.")
                    
                    if st.button("🎬 Generate Video Highlights", key="generate_highlights"):
                        with st.spinner("Generating video highlights..."):
                            # Progress tracking
                            progress_placeholder = st.empty()
                            status_placeholder = st.empty()
                            progress_bar = progress_placeholder.progress(0)
                            
                            # Define progress update functions
                            def update_progress(value):
                                try:
                                    progress_bar.progress(value)
                                except Exception:
                                    pass
                            
                            def update_status(message):
                                try:
                                    status_placeholder.info(message)
                                except Exception:
                                    pass
                            
                            # Get the YouTube URL from results
                            youtube_url = results.get("youtube_url", "")
                            if not youtube_url:
                                st.error("YouTube URL not found in results.")
                                return
                            
                            # Generate highlights
                            video_path, highlights_segments, error = generate_video_highlights(
                                youtube_url=youtube_url,
                                max_highlights=5,
                                progress_callback=update_progress,
                                status_callback=update_status
                            )
                            
                            if error:
                                st.error(f"Error generating highlights: {error}")
                                if "download" in error.lower() or "HTTP Error" in error:
                                    st.info("""
                                    ℹ️ **Video Download Issue**
                                    
                                    YouTube frequently updates their API which can cause download issues. You can try:
                                    1. Refresh the page and try again
                                    2. Try a different video
                                    3. Check if the video has any restrictions (age-restricted, private, etc.)
                                    
                                    We've implemented several fallback methods, but some videos may still be unavailable.
                                    """)
                            elif video_path and highlights_segments:
                                # Store in session state
                                st.session_state.highlights_video_path = video_path
                                st.session_state.highlights_segments = highlights_segments
                                
                                # Display the highlights
                                display_video_highlights(video_path, highlights_segments)
                            else:
                                st.error("Failed to generate video highlights. Please try again.")
                    
                    # Show information about the highlights feature
                    st.markdown("---")
                    st.markdown("#### What are Video Highlights?")
                    st.markdown("""
                    The video highlights feature uses AI to:
                    1. Identify the most important moments in the video
                    2. Extract these segments from the original video
                    3. Combine them into a concise highlights video
                    
                    This allows you to quickly get the main points without watching the entire video.
                    """)
            except Exception as e:
                st.error(f"Error displaying highlights tab: {str(e)}")
                logger.error(f"Error in highlights tab: {str(e)}", exc_info=True)
    
    # Display token usage if available
    if token_usage:
        st.markdown("<h2 class='sub-header'>📈 Token Usage</h2>", unsafe_allow_html=True)
        token_container = st.container()
        
        with token_container:
            if isinstance(token_usage, dict):
                # If token_usage is a dictionary with detailed information
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Prompt Tokens", token_usage.get("prompt_tokens", "N/A"), delta=None, delta_color="normal")
                
                with col2:
                    st.metric("Completion Tokens", token_usage.get("completion_tokens", "N/A"), delta=None, delta_color="normal")
                
                with col3:
                    st.metric("Total Tokens", token_usage.get("total_tokens", "N/A"), delta=None, delta_color="normal")
                
            else:
                # If token_usage is a string, try to parse it
                try:
                    # Check if it's a string that contains token information
                    token_text = str(token_usage)
                    
                    # Try to extract token counts
                    total_match = re.search(r'total_tokens=(\d+)', token_text)
                    prompt_match = re.search(r'prompt_tokens=(\d+)', token_text)
                    completion_match = re.search(r'completion_tokens=(\d+)', token_text)
                    
                    if total_match or prompt_match or completion_match:
                        # Create 3 columns for metrics
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            prompt_tokens = int(prompt_match.group(1)) if prompt_match else "N/A"
                            st.metric("Prompt Tokens", prompt_tokens, delta=None, delta_color="normal")
                        
                        with col2:
                            completion_tokens = int(completion_match.group(1)) if completion_match else "N/A"
                            st.metric("Completion Tokens", completion_tokens, delta=None, delta_color="normal")
                        
                        with col3:
                            total_tokens = int(total_match.group(1)) if total_match else "N/A"
                            st.metric("Total Tokens", total_tokens, delta=None, delta_color="normal")

                    else:
                        # Just display the raw token information
                        st.text(f"Token Usage: {token_usage}")
                except Exception as e:
                    # If any error occurs, just display the raw token information
                    st.text(f"Token Usage: {token_usage}")


# Add this function to convert transcript list to text format
def convert_transcript_list_to_text(transcript_list):
    """
    Convert a transcript list to plain text.
    
    Args:
        transcript_list: A list of transcript segments with 'text' keys
        
    Returns:
        Plain text transcript
    """
    # Check if already a string
    if isinstance(transcript_list, str):
        return transcript_list
        
    # Check if None or empty
    if not transcript_list:
        logger.warning("No transcript list to convert")
        return ""
    
    try:
        # Convert list to text
        plain_text = ""
        for item in transcript_list:
            if isinstance(item, dict) and 'text' in item:
                plain_text += item.get('text', '') + " "
            elif isinstance(item, str):
                plain_text += item + " "
        
        return plain_text.strip()
    
    except Exception as e:
        logger.exception(f"Error converting transcript list to text: {str(e)}")
        return ""

def check_agent_streaming_support(agent):
    """
    Check if the agent supports streaming responses.
    
    Args:
        agent: The agent to check
        
    Returns:
        A tuple of (supports_streaming, llm) where supports_streaming is a boolean
        indicating if the agent supports streaming and llm is the language model
    """
    if agent is None:
        logger.info("Agent is None, streaming not supported")
        return False, None
    
    # Try to access the LLM from the agent
    llm = None
    
    # Log agent structure for debugging
    agent_type = type(agent).__name__
    logger.info(f"Agent type: {agent_type}")
    
    # Get all attributes of the agent
    agent_attrs = dir(agent)
    logger.info(f"Agent attributes: {agent_attrs[:15]}...")
    
    # For CompiledStateGraph agents (LangGraph), we need to inspect the nodes
    if agent_type == "CompiledStateGraph":
        logger.info("Detected CompiledStateGraph agent from LangGraph")
        
        # Try to access the graph's nodes
        if hasattr(agent, "_graph") and hasattr(agent._graph, "nodes"):
            logger.info("Found _graph.nodes attribute")
            nodes = agent._graph.nodes
            logger.info(f"Graph nodes: {list(nodes.keys())}")
            
            # Look for LLM in nodes
            for node_name, node in nodes.items():
                logger.info(f"Inspecting node: {node_name}, type: {type(node).__name__}")
                
                # Check if the node itself is an LLM
                if hasattr(node, "model_name") and hasattr(node, "client"):
                    llm = node
                    logger.info(f"Found LLM in node {node_name}")
                    break
                
                # Check if the node has an LLM attribute
                if hasattr(node, "llm"):
                    llm = node.llm
                    logger.info(f"Found llm attribute in node {node_name}")
                    break
        
        # Try to access the state
        if not llm and hasattr(agent, "state"):
            logger.info("Checking agent.state")
            state = agent.state
            if hasattr(state, "llm"):
                llm = state.llm
                logger.info("Found llm in agent.state")
    
    # Standard checks for other agent types
    if not llm:
        if hasattr(agent, "llm"):
            llm = agent.llm
            logger.info("Found llm attribute directly on agent")
        elif hasattr(agent, "agent") and hasattr(agent.agent, "llm"):
            llm = agent.agent.llm
            logger.info("Found llm attribute on agent.agent")
        elif hasattr(agent, "_graph") and hasattr(agent._graph, "llm"):
            llm = agent._graph.llm
            logger.info("Found llm attribute on agent._graph")
        elif hasattr(agent, "runnable") and hasattr(agent.runnable, "llm"):
            llm = agent.runnable.llm
            logger.info("Found llm attribute on agent.runnable")
        elif hasattr(agent, "executor") and hasattr(agent.executor, "llm"):
            llm = agent.executor.llm
            logger.info("Found llm attribute on agent.executor")
    
    # If we found an LLM, log its type
    if llm:
        logger.info(f"LLM type: {type(llm).__name__}")
        llm_attrs = dir(llm)
        logger.info(f"LLM attributes: {llm_attrs[:15]}...")
        
        # Check if we have an OpenAI LLM that supports streaming
        if hasattr(llm, "client") and hasattr(llm.client, "chat") and hasattr(llm.client.chat, "completions"):
            # Check if the model supports streaming
            if hasattr(llm, "model_name"):
                logger.info(f"Found OpenAI LLM with model: {llm.model_name}")
                if any(model in llm.model_name for model in ["gpt-3.5", "gpt-4", "gpt-4o"]):
                    logger.info("Model supports streaming")
                    return True, llm
                else:
                    logger.info(f"Model {llm.model_name} not in streaming supported list")
            else:
                logger.info("OpenAI LLM found but no model_name attribute")
        
        # Check for other LLM types that might support streaming
        if hasattr(llm, "streaming"):
            logger.info(f"LLM has streaming attribute: {llm.streaming}")
            if llm.streaming:
                return True, llm
    else:
        logger.info("Could not find LLM in agent structure")
    
    # Since we couldn't find a streaming-capable LLM, always return False
    logger.info("No streaming support detected, using fallback approach")
    return False, None

def initialize_session_state():
    """Initialize all session state variables to prevent KeyError exceptions."""
    # Authentication-related variables
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    
    if "show_auth" not in st.session_state:
        st.session_state.show_auth = False
    
    # Chat-related variables
    if "chat_enabled" not in st.session_state:
        st.session_state.chat_enabled = False
        
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
        
    if "chat_details" not in st.session_state:
        st.session_state.chat_details = None
    
    if "is_processing_message" not in st.session_state:
        st.session_state.is_processing_message = False
    
    # Analysis-related variables
    if "analysis_complete" not in st.session_state:
        st.session_state.analysis_complete = False
        
    if "analysis_results" not in st.session_state:
        st.session_state.analysis_results = None
    
    if "timestamped_transcript" not in st.session_state:
        st.session_state.timestamped_transcript = None
    
    if "transcript_list" not in st.session_state:
        st.session_state.transcript_list = None
    
    if "video_id" not in st.session_state:
        st.session_state.video_id = None
    
    # Highlights-related variables
    if "highlights_video_path" not in st.session_state:
        st.session_state.highlights_video_path = None
        
    if "highlights_segments" not in st.session_state:
        st.session_state.highlights_segments = None
    
    # Streaming-related variables
    if "streaming" not in st.session_state:
        st.session_state.streaming = False
    
    if "streaming_response" not in st.session_state:
        st.session_state.streaming_response = ""
    
    if "current_question" not in st.session_state:
        st.session_state.current_question = None
    
    if "supports_streaming" not in st.session_state:
        st.session_state.supports_streaming = False
    
    # Settings variables
    if "settings" not in st.session_state:
        st.session_state.settings = {
            "model": "gpt-4o-mini",
            "temperature": 0.7,
            "use_cache": True,
            "analysis_types": ["Summary & Classification"]  # Default analysis types
        }
        logger.info("Initialized default settings in session state")

def get_skimr_logo_base64():
    """Returns the base64 encoded Skimr logo for embedding in HTML."""
    import base64
    from pathlib import Path
    
    # Logo file path
    logo_path = Path("src/youtube_analysis/logo/original.png")
    
    # Check if the logo file exists
    if not logo_path.exists():
        # Use a rocket emoji as fallback
        return None
    
    with open(logo_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode()

def main():
    """Main function to run the web application."""
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    # Initialize ALL session state variables at the start
    initialize_session_state()
    
    # Initialize authentication state
    init_auth_state()
    
    # Setup CSS and UI components
    load_css()
    
    # Process chat input if there's a thinking message
    if st.session_state.chat_enabled and st.session_state.chat_messages and st.session_state.chat_messages[-1]["role"] == "thinking":
        handle_chat_input()
    
    # Check configuration
    is_valid, missing_vars = validate_config()
    if not is_valid:
        if 'YOUTUBE_API_KEY' in missing_vars:
            st.sidebar.warning(
                "YouTube API key is missing. The app will try to use pytube as a fallback, "
                "but it may not work reliably due to YouTube API changes. "
                "See the README for instructions on setting up a YouTube API key."
            )
    
    # Setup sidebar with configuration
    with st.sidebar:
        # Display Skimr logo at the top of the sidebar
        logo_base64 = get_skimr_logo_base64()
        if logo_base64:
            st.markdown(f"""
            <div style="text-align: center; margin-bottom: 1rem;">
                <img src="data:image/png;base64,{logo_base64}" width="180" alt="Skimr Logo">
            </div>
            """, unsafe_allow_html=True)
        
        # User account section - moved to bottom
        st.sidebar.markdown("<hr style='margin: 1.5rem 0;'>", unsafe_allow_html=True)
        with st.sidebar.expander("👤 User Account", expanded=False):
            user = get_current_user()
            if user:
                st.write(f"**Email:** {user.email}")
                
                # Display user statistics
                stats = get_user_stats()
                if stats:
                    st.markdown("### Your Statistics")
                    st.metric("Summaries Generated", stats.get("summary_count", 0))
                    
                    # Add more stats here as they become available
                    
                if st.button("Logout", key="sidebar_logout"):
                    from src.youtube_analysis.auth import logout
                    if logout():
                        st.rerun()
            else:
                st.info("You are not logged in")
                if st.button("Login/Sign Up", key="sidebar_login"):
                    st.session_state.show_auth = True
        
        with st.expander("⚙️ Settings", expanded=False):
            # Model selection
            st.markdown("<h3 style='margin-bottom: 0.5rem;'>AI Model</h3>", unsafe_allow_html=True)
            model = st.selectbox(
                label="AI Model",
                options=["gpt-4o-mini", "gemini-2.0-flash", "gemini-2.0-flash-lite"],
                index=0,
                label_visibility="collapsed"
            )
            
            # Temperature setting
            st.markdown("<h3 style='margin-top: 1rem; margin-bottom: 0.5rem;'>Creativity Level</h3>", unsafe_allow_html=True)
            temperature = st.slider(
                label="Temperature Value",
                min_value=0.0,
                max_value=1.0,
                value=0.2,
                step=0.1,
                label_visibility="collapsed",
                help="Higher values make output more creative, lower values make it more deterministic"
            )
            
            # Cache toggle
            st.markdown("<h3 style='margin-top: 1rem; margin-bottom: 0.5rem;'>Performance</h3>", unsafe_allow_html=True)
            use_cache = st.checkbox(
                label="Use Cache (Faster Analysis)",
                value=True,
                help="Enable caching for faster repeated analysis of the same videos"
            )
        analysis_types = ["Summary & Classification"]

        # Update settings in session state
        st.session_state.settings.update({
            "model": model,
            "temperature": temperature,
            "use_cache": use_cache,
            "analysis_types": analysis_types
        })
        
        # For debugging
        logger.info(f"Settings updated in sidebar: model={model}, temperature={temperature}, use_cache={use_cache}")
        
        # Set environment variables based on settings
        os.environ["LLM_MODEL"] = model
        os.environ["LLM_TEMPERATURE"] = str(temperature)
        
        
        # Reset analysis button (if analysis is complete)
        if st.session_state.analysis_complete:
            # Analysis settings section
            st.markdown("<hr style='margin: 1.5rem 0;'>", unsafe_allow_html=True)
            st.markdown("<h3 style='margin-bottom: 1rem;'>Analysis Options</h3>", unsafe_allow_html=True)
            # Reset chat button (if chat is enabled)
            if st.session_state.chat_enabled:
                if st.button("🔄 Reset Chat", key="reset_chat"):
                    st.session_state.chat_messages = []
                    # Re-initialize welcome message
                    if st.session_state.chat_details and "title" in st.session_state.chat_details:
                        video_title = st.session_state.chat_details.get("title", "this YouTube video")
                        welcome_message = f"Hello! I'm your AI assistant for the video \"{video_title}\". Ask me any questions about the content, and I'll do my best to answer based on the transcript. I'll include timestamps [MM:SS] in my answers to help you locate information in the video."
                        
                        st.session_state.chat_messages = [
                            {
                                "role": "assistant", 
                                "content": welcome_message
                            }
                        ]
                    st.rerun()
        
            if st.button("🔄 New Analysis", key="new_analysis"):
                # Reset all relevant state
                st.session_state.chat_enabled = False
                st.session_state.chat_messages = []
                st.session_state.chat_details = None
                st.session_state.analysis_complete = False
                st.session_state.analysis_results = None
                st.session_state.timestamped_transcript = None
                st.session_state.transcript_list = None
                st.session_state.video_id = None
                # Clear highlights-related session state
                if "highlights_video_path" in st.session_state:
                    del st.session_state.highlights_video_path
                if "highlights_segments" in st.session_state:
                    del st.session_state.highlights_segments
                st.rerun()
                
            # Clear cache button (only shown if a video has been analyzed)
            if "video_id" in st.session_state and st.session_state.video_id:
                if st.button("🧹 Clear Cache", key="clear_cache"):
                    video_id = st.session_state.video_id
                    # Import highlights cache clearing function
                    from src.youtube_analysis.utils.video_highlights import clear_highlights_cache
                    
                    analysis_cleared = clear_analysis_cache(video_id)
                    highlights_cleared = clear_highlights_cache(video_id)
                    
                    if analysis_cleared or highlights_cleared:
                        st.success(f"Cache cleared for video {video_id}")
                        # Reset analysis state to force a fresh analysis
                        st.session_state.analysis_complete = False
                        st.session_state.analysis_results = None
                        st.session_state.video_id = None
                        st.session_state.chat_enabled = False
                        # Clear highlights-related session state
                        if "highlights_video_path" in st.session_state:
                            del st.session_state.highlights_video_path
                        if "highlights_segments" in st.session_state:
                            del st.session_state.highlights_segments
                        st.rerun()
                    else:
                        st.info("No cached data found for this video")
        
        # Display version
        st.markdown(f"<div style='text-align: center; margin-top: 2rem; opacity: 0.7;'>Skimr v{VERSION}</div>", unsafe_allow_html=True)
    
    # Display auth UI if needed
    if st.session_state.show_auth:
        display_auth_ui()
        return
    
    # Main app content
    # Only show welcome text and input fields if analysis is not complete
    if not st.session_state.analysis_complete:
        # Title
        st.markdown("""
            <div style="background: linear-gradient(45deg, #1a1a1a, #232323); padding: 1.5rem 2rem; border-radius: 12px; text-align: center; margin-top: 3rem; position: relative; overflow: hidden;">
                <div style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; background: radial-gradient(circle at 70% 30%, rgba(77, 171, 247, 0.1), transparent 70%); z-index: 1;"></div>
                <div style="position: relative; z-index: 2;">
                    <h1 style="color: #ffffff;">SKIMR</h1>
                    <h2 style="color: #4dabf7; ">Skim through Youtube. Know what matters fast.</h2>
                </div>
            </div>
            """, unsafe_allow_html=True)
        # provide a space between the title and the input field
        st.markdown("<br>", unsafe_allow_html=True)
        col_left, col_middle, col_right = st.columns([1, 2, 1])
        with col_middle:
           st.markdown("<h3 style='text-align: center; width: 100%;'>Paste your YouTube link</h3>", unsafe_allow_html=True)
           url = st.text_input("YouTube URL", placeholder="https://www.youtube.com/watch?v=...", label_visibility="collapsed") 
        
        # Handle form submission
        if url:
            if not validate_youtube_url(url):
                st.error("Please enter a valid YouTube URL")
            elif not st.session_state.authenticated:
                # Instead of showing the warning immediately, start the analysis process
                # and then prompt for login before completing the analysis
                with st.spinner("Preparing to analyze video..."):
                    # Get video info to show the user what they're about to analyze
                    video_info = get_video_info(url)
                    if video_info:
                        # Show login prompt
                        st.warning("Please log in to analyze this video")
                        st.session_state.show_auth = True
                        
                        # Add a button to show auth UI in case they closed it
                        if st.button("Login/Sign Up"):
                            st.session_state.show_auth = True
                    else:
                        st.error("Could not fetch video information. Please check the URL and try again.")
            else:
                # Rest of the analysis code...
                with st.spinner("Analyzing video..."):
                    try:
                        # Reset chat state for new analysis
                        st.session_state.chat_enabled = False
                        st.session_state.chat_messages = []
                        st.session_state.chat_details = None
                        
                        # Clear highlights-related session state
                        if "highlights_video_path" in st.session_state:
                            del st.session_state.highlights_video_path
                        if "highlights_segments" in st.session_state:
                            del st.session_state.highlights_segments
                        
                        # Store the analysis start time
                        st.session_state.analysis_start_time = datetime.now()
                        
                        # Create progress placeholder
                        progress_placeholder = st.empty()
                        status_placeholder = st.empty()
                        
                        # Initialize progress bar
                        progress_bar = progress_placeholder.progress(0)
                        status_placeholder.info("Fetching video transcript...")
                        
                        # Define progress update functions
                        def update_progress(value):
                            try:
                                # Use thread-safe approach for Streamlit updates
                                import streamlit as st
                                from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx
                                
                                # Only update if there's a valid context
                                if get_script_run_ctx():
                                    progress_bar.progress(value)
                            except Exception as e:
                                # Silently fail if we can't update the progress bar
                                pass
                        
                        def update_status(message):
                            try:
                                # Use thread-safe approach for Streamlit updates
                                import streamlit as st
                                from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx
                                
                                # Only update if there's a valid context
                                if get_script_run_ctx():
                                    status_placeholder.info(message)
                            except Exception as e:
                                # Silently fail if we can't update the status
                                pass
                        
                        # Run the analysis
                        try:
                            # Get cache setting from session state
                            use_cache = st.session_state.settings.get("use_cache", True)
                            
                            # Get video transcript
                            timestamped_transcript, transcript_list, error = process_transcript_async(
                                url, 
                                use_cache=use_cache
                            )
                            
                            if error:
                                st.error(f"Error: {error}")
                                return
                            
                            if not timestamped_transcript or not transcript_list:
                                st.error("Could not process video transcript. Please try another video.")
                                return
                            
                            # Get video info
                            video_info = get_video_info(url)
                            if not video_info:
                                st.warning("Could not fetch complete video information. Continuing with limited data.")
                                video_info = {
                                    "title": "Unknown Title",
                                    "description": "No description available",
                                    "channel": "Unknown Channel",
                                    "views": "Unknown",
                                    "likes": "Unknown",
                                    "published": "Unknown"
                                }
                            
                            # Update progress
                            update_progress(10)
                            update_status("Analyzing transcript...")
                            
                            # Convert transcript to text
                            transcript_text = convert_transcript_list_to_text(transcript_list)
                            
                            # Extract video ID
                            video_id = extract_video_id(url)
                            
                            # Store in session state
                            st.session_state.video_id = video_id
                            st.session_state.video_url = url
                            st.session_state.video_info = video_info
                            st.session_state.transcript_list = transcript_list
                            st.session_state.transcript_text = transcript_text
                            
                            # Run analysis with timeout
                            try:
                                # Get settings from session state BEFORE creating the thread
                                use_cache = st.session_state.settings.get("use_cache", True)
                                model = st.session_state.settings.get("model", "gpt-4o-mini")
                                temperature = st.session_state.settings.get("temperature", 0.7)
                                
                                # Set environment variables based on settings
                                os.environ["LLM_MODEL"] = model
                                os.environ["LLM_TEMPERATURE"] = str(temperature)
                                
                                logger.info(f"Using settings from UI: model={model}, temperature={temperature}, use_cache={use_cache}")
                                
                                # Force new analysis if checkbox is unchecked
                                if not use_cache:
                                    # Clear the analysis cache for this video
                                    logger.info(f"Forcing new analysis by clearing cache for video {video_id}")
                                    clear_analysis_cache(video_id)
                                
                                # Define function to run analysis
                                def run_analysis_with_timeout():
                                    logger.info(f"Starting analysis with use_cache={use_cache}, url={url}")
                                    try:
                                        # Safely get analysis types from session state
                                        analysis_types = ["Summary & Classification"]  # Default fallback
                                        if "settings" in st.session_state and "analysis_types" in st.session_state.settings:
                                            analysis_types = st.session_state.settings["analysis_types"]
                                            logger.info(f"Using analysis types from settings: {analysis_types}")
                                        else:
                                            logger.warning("Using default analysis types as settings not found in session state")
                                        
                                        # Ensure Summary & Classification is always included
                                        if "Summary & Classification" not in analysis_types:
                                            analysis_types = ["Summary & Classification"] + analysis_types
                                            logger.info(f"Added required Summary & Classification to analysis types: {analysis_types}")
                                        
                                        analysis_result = run_analysis(
                                            url,  
                                            update_progress,
                                            update_status,
                                            use_cache=use_cache,
                                            analysis_types=tuple(analysis_types)
                                        )
                                        # Handle the returned value properly
                                        if isinstance(analysis_result, tuple) and len(analysis_result) == 2:
                                            results, error = analysis_result
                                            logger.info(f"Analysis complete, got result: {type(results)}, {results is not None}")
                                            return results, error
                                        else:
                                            logger.error(f"Unexpected result format from run_analysis: {type(analysis_result)}")
                                            return None, "Analysis returned unexpected result format"
                                    except Exception as e:
                                        logger.error(f"Exception in run_analysis_with_timeout: {str(e)}", exc_info=True)
                                        return None, str(e)
                                
                                # Use ThreadPoolExecutor to run with timeout
                                with concurrent.futures.ThreadPoolExecutor() as executor:
                                    # Get current Streamlit run context before submitting to the thread
                                    from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx
                                    ctx = get_script_run_ctx()
                                    
                                    # Submit the task to the executor
                                    future = executor.submit(run_analysis_with_timeout)
                                    
                                    # Add the context to the thread
                                    if ctx:
                                        add_script_run_ctx(future, ctx)
                                        
                                    try:
                                        # Wait for up to 3 minutes
                                        results, analysis_error = future.result(timeout=180)
                                        logger.info(f"Analysis completed with results: {results is not None}, error: {analysis_error}")
                                    except concurrent.futures.TimeoutError:
                                        logger.error("Analysis timed out after 3 minutes")
                                        st.error("Analysis took too long and timed out. Please try again later or try a different video.")
                                        return
                                    except Exception as e:
                                        logger.error(f"Unexpected error during analysis: {str(e)}", exc_info=True)
                                        st.error(f"An unexpected error occurred: {str(e)}")
                                        return
                                
                                # Check for errors
                                if analysis_error:
                                    logger.error(f"Analysis error: {analysis_error}")
                                    st.error(f"Analysis failed: {analysis_error}")
                                    return
                                
                                if not results:
                                    logger.error("Analysis returned no results")
                                    st.error("Analysis failed to return results. Try turning off the 'Use Cache' option in settings and try again.")
                                    return
                                
                                # Validate that task_outputs exists and has content
                                if not isinstance(results, dict) or "task_outputs" not in results or not results["task_outputs"]:
                                    logger.error(f"Analysis results missing task_outputs: {results}")
                                    st.error("Analysis didn't generate proper results. Try turning off the 'Use Cache' option in settings and try again.")
                                    return
                                    
                                # Log task outputs for debugging
                                logger.info(f"Task outputs from analysis: {list(results['task_outputs'].keys())}")
                                    
                                # Store results in session state
                                logger.info("Storing analysis results in session state")
                                st.session_state.analysis_results = results
                                st.session_state.analysis_complete = True
                            
                            except Exception as timeout_error:
                                logger.exception(f"Error during analysis with timeout: {str(timeout_error)}")
                                st.error(f"An error occurred during analysis: {str(timeout_error)}")
                                return
                            
                            # Setup chat for video - this is needed for both cached and non-cached results
                            try:
                                # Import the chat setup function
                                from src.youtube_analysis.chat import setup_chat_for_video
                                
                                # Get transcript from results or session state
                                transcript = results.get("transcript", st.session_state.transcript_text)
                                
                                # Set up chat with the transcript and list
                                chat_details = setup_chat_for_video(url, transcript, transcript_list)
                                
                                if chat_details:
                                    st.session_state.chat_details = chat_details
                                    st.session_state.chat_enabled = True
                                    
                                    # Create welcome message
                                    video_title = video_info.get('title', 'this video')
                                    welcome_message = f"Hello! I'm your AI assistant for the video \"{video_title}\". Ask me any questions about the content, and I'll do my best to answer based on the transcript. I'll include timestamps [MM:SS] in my answers to help you locate information in the video."
                                    
                                    # Initialize chat messages
                                    st.session_state.chat_messages = [
                                        {
                                            "role": "assistant", 
                                            "content": welcome_message
                                        }
                                    ]
                                else:
                                    logger.error("Failed to set up chat for video")
                                    st.session_state.chat_enabled = False
                            except Exception as chat_setup_error:
                                logger.exception(f"Error setting up chat: {str(chat_setup_error)}")
                                st.session_state.chat_enabled = False
                            
                            # Clear progress
                            progress_placeholder.progress(100)
                            time.sleep(0.5)
                            progress_placeholder.empty()
                            status_placeholder.empty()
                            
                            # Show success message
                            st.success("Analysis complete!")
                            logger.info(f"Analysis completed successfully for video: {url}")
                            
                            # Track analysis completion time
                            st.session_state.analysis_complete = True
                            
                            if not st.session_state.analysis_results.get("cached", False):
                                # Increment the user's summary count
                                logger.info("About to increment user summary count")
                                user = get_current_user()
                                logger.info(f"Current user: {user if user else 'None'}")
                                
                                if user and hasattr(user, 'id'):
                                    logger.info(f"Current user found: {user.id}, {user.email}")
                                    try:
                                        success = increment_summary_count(user.id)
                                        if success:
                                            logger.info(f"Incremented summary count for user {user.id}")
                                        else:
                                            logger.warning(f"Failed to increment summary count for user {user.id}")
                                    except Exception as count_error:
                                        logger.error(f"Exception incrementing summary count: {str(count_error)}")
                                else:
                                    logger.warning("Cannot increment summary count: No valid user is logged in")

                            else:
                                logger.warning("Using cached analysis - not incrementing summary count")

                            # Rerun the app to update UI with results
                            st.rerun()
                        except Exception as analysis_error:
                            logger.exception(f"Exception during analysis: {str(analysis_error)}")
                            st.error(f"Analysis failed: {str(analysis_error)}")
                            return
                    except Exception as e:
                        logger.exception(f"General error processing video: {str(e)}")
                        st.error(f"An error occurred: {str(e)}")
                        return
        

        # If URL is provided, show video info
        if url and validate_youtube_url(url):
            try:
                # Get video info
                video_info = get_video_info(url)
                if not video_info:
                    st.error("Could not fetch video information. YouTube API may have changed.")
                    
                    # Try to continue with just the video ID
                    video_id = extract_video_id(url)
                    if video_id:
                        st.info(f"Continuing with limited information for video ID: {video_id}")
                        video_info = {
                            'video_id': video_id,
                            'title': f"YouTube Video ({video_id})",
                            'description': "Video description unavailable.",
                            'thumbnail_url': f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
                            'url': url
                        }
                    else:
                        st.error("Could not extract video ID from URL")
                        return
                
                # Display video info with improved styling
                st.markdown("""
                <h3 style="color: #4dabf7;">Video Details</h3>
                """, unsafe_allow_html=True)
                
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.markdown(f"### {video_info['title']}")
                    st.write(video_info.get('description', 'No description available'))
                with col2:
                    st.image(video_info['thumbnail_url'], use_container_width=True)
            
            except Exception as e:
                logger.exception(f"Error fetching video info: {str(e)}")
                st.error(f"An error occurred: {str(e)}")
                return
        
        # Display features and how it works sections
        if not url:
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("""
                <div style="text-align: center;">
                <h2>🎯 How Skimr Works</h2>
                
                <ul style="list-style-type: none; text-align: justify;">
                    <li><strong>Skimr</strong> turns YouTube videos into <em>bite-sized insights</em>.</li>
                    <li>Generates <strong>summaries</strong>, <strong>action plans</strong>, and <strong>ready-to-share content</strong>.</li>
                    <li>Paste the link. <strong>We handle the rest</strong>.</li>
                </ul>

                <p><strong>Spend less time watching. More time discovering.</strong></p>
                </div>
                """, unsafe_allow_html=True)

            with col2:
                st.markdown("""
                <div style="text-align: center;">
                <h2>🚀 What You'll Get</h2>
                <ul style="list-style-type: none; text-align: justify;">
                    <li>✅ <strong>TL;DR Magic:</strong> 10x faster than watching the video</li>
                    <li>✅ <strong>Ask & Receive:</strong> Get answers instantly</li>
                    <li>✅ <strong>Copy-paste content</strong> for Blogs, LinkedIn, X</li>
                    <li>✅ <strong>Actionable plans</strong> from passive watching</li>
                </ul>
                </div>
                """, unsafe_allow_html=True)
    
                
            # Use cases section with improved styling
            st.markdown("""
            <h3 style="color: #4dabf7; margin: 3rem 0 1.5rem 0; text-align: center;">Who is Skimr For?</h3>
            <div style="width: 100px; height: 3px; background: #4dabf7; margin: 0 auto 2rem auto; border-radius: 2px; opacity: 0.5;"></div>
            """, unsafe_allow_html=True)
            
            use_case_cols = st.columns(3)
            
            with use_case_cols[0]:
                st.markdown("""
                <div>
                    <div style="font-size: 2rem; margin-bottom: 1rem; text-align: center;">🎓</div>
                    <h3 style="text-align: center;">Academics</h3>
                    <p>Quickly extract key information from educational videos, lectures, and research presentations.</p>
                </div>
                """, unsafe_allow_html=True)
                
            with use_case_cols[1]:
                st.markdown("""
                <div>
                    <div style="font-size: 2rem; margin-bottom: 1rem; text-align: center;">💼</div>
                    <h3 style="text-align: center;">Professionals</h3>
                    <p>Stay updated with industry trends by efficiently processing webinars, and thought leadership videos.</p>
                </div>
                """, unsafe_allow_html=True)
                
            with use_case_cols[2]:
                st.markdown("""
                <div>
                    <div style="font-size: 2rem; margin-bottom: 1rem; text-align: center;">🧠</div>
                    <h3 style="text-align: center;">Lifelong Learners</h3>
                    <p>Maximize learning from tutorials, courses, and educational content with AI-powered summaries and insights.</p>
                </div>
                """, unsafe_allow_html=True)
            
            # Call to action section
            st.markdown("""
            <div style="background: linear-gradient(45deg, #1a1a1a, #232323); padding: 1.5rem 2rem; border-radius: 12px; text-align: center; margin-top: 3rem; position: relative; overflow: hidden;">
                <div style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; background: radial-gradient(circle at 70% 30%, rgba(77, 171, 247, 0.1), transparent 70%); z-index: 1;"></div>
                <div style="position: relative; z-index: 2;">
                    <h2 style="color: #ffffff; margin-bottom: 1rem;">Ready to Try Skimr?</h2>
                    <p style="color: #e0e0e0; margin-bottom: 2rem; font-size: 1.1rem;">Paste a YouTube URL above and discover insights in seconds!</p>
                </div>
            </div>
            """, unsafe_allow_html=True)
    
    # Check if analysis is complete (retained from session state)
    if st.session_state.analysis_complete and st.session_state.analysis_results:
        # Verify the analysis results have the required fields
        results = st.session_state.analysis_results
        logger.info(f"Found analysis results in session state with keys: {list(results.keys()) if isinstance(results, dict) else 'not a dict'}")
        
        if isinstance(results, dict) and "task_outputs" in results and results["task_outputs"]:
            # Log the tasks that are available
            logger.info(f"Displaying analysis results with tasks: {list(results['task_outputs'].keys())}")
            # Display results from session state
            display_analysis_results(results)
        else:
            logger.error(f"Invalid analysis results structure: {type(results)}")
            st.error("Analysis results are not in the expected format. Please try again.")
            
            # Attempt to fix the results if possible
            if isinstance(results, dict) and "video_id" in results:
                logger.info("Attempting to create fallback task outputs")
                # Create minimal task outputs to display something
                results["task_outputs"] = {
                    "classify_and_summarize_content": "Classification and summary results were not properly generated. Please try again with a different model or settings.",
                    "analyze_and_plan_content": "Analysis and action plan could not be created. Please try again with cache disabled.",
                    "write_report": "Report generation failed."
                }
                
                # Make sure context_tag is set
                if "context_tag" not in results:
                    results["context_tag"] = "General"
                    
                logger.info("Displaying fallback analysis results")
                display_analysis_results(results)

def generate_additional_analysis(youtube_url: str, video_id: str, transcript: str, analysis_type: str, progress_callback=None, status_callback=None):
    """
    Generate a specific additional analysis type on demand after the initial analysis is complete.
    
    Args:
        youtube_url: The URL of the YouTube video
        video_id: The YouTube video ID
        transcript: The video transcript
        analysis_type: The specific analysis type to generate (e.g., "Blog Post", "LinkedIn Post", "X Tweet")
        progress_callback: Optional callback function to update progress
        status_callback: Optional callback function to update status messages
        
    Returns:
        A tuple containing the generated content (or None if error) and either an error message or metadata dict
    """
    logger.info(f"Generating additional analysis type: {analysis_type} for video {video_id}")
    
    try:
        # Start timing the analysis
        start_time = datetime.now()
        
        # Get model settings from session state
        model = st.session_state.settings.get("model", "gpt-4o-mini")
        temperature = st.session_state.settings.get("temperature", 0.7)
        
        # Update status
        if status_callback:
            status_callback(f"Generating {analysis_type}...")
        
        if progress_callback:
            progress_callback(10)
        
        # Create a crew instance with just the necessary agent and task
        from src.youtube_analysis.crew import YouTubeAnalysisCrew
        crew_instance = YouTubeAnalysisCrew(model_name=model, temperature=temperature)
        
        # Create a list with just Summary & Classification and the requested analysis type
        selected_types = ["Summary & Classification", analysis_type]
        
        # Check if we have cached results for this analysis type
        cached_results = get_cached_analysis(video_id)
        if cached_results and "task_outputs" in cached_results:
            task_outputs = cached_results["task_outputs"]
            
            # If the analysis type already exists in the cached results, return it
            if analysis_type == "Action Plan" and "analyze_and_plan_content" in task_outputs:
                logger.info(f"Using cached Action Plan for video {video_id}")
                end_time = datetime.now()
                analysis_time = (end_time - start_time).total_seconds()
                return task_outputs["analyze_and_plan_content"], {"analysis_time": analysis_time, "cached": True}
            elif analysis_type == "Blog Post" and "write_blog_post" in task_outputs:
                logger.info(f"Using cached Blog Post for video {video_id}")
                end_time = datetime.now()
                analysis_time = (end_time - start_time).total_seconds()
                return task_outputs["write_blog_post"], {"analysis_time": analysis_time, "cached": True}
            elif analysis_type == "LinkedIn Post" and "write_linkedin_post" in task_outputs:
                logger.info(f"Using cached LinkedIn Post for video {video_id}")
                end_time = datetime.now()
                analysis_time = (end_time - start_time).total_seconds()
                return task_outputs["write_linkedin_post"], {"analysis_time": analysis_time, "cached": True}
            elif analysis_type == "X Tweet" and "write_tweet" in task_outputs:
                logger.info(f"Using cached X Tweet for video {video_id}")
                end_time = datetime.now()
                analysis_time = (end_time - start_time).total_seconds()
                return task_outputs["write_tweet"], {"analysis_time": analysis_time, "cached": True}
        
        if progress_callback:
            progress_callback(30)
            
        # Create a crew with only the necessary tasks
        # Convert to tuple since lists are unhashable (required for CrewAI's caching mechanism)
        crew = crew_instance.crew(analysis_types=tuple(selected_types))
        
        # Get current date and time
        current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Get video title
        video_info = get_video_info(youtube_url)
        video_title = video_info.get("title", "YouTube Video")
        
        # Start the crew execution with the inputs
        inputs = {
            "youtube_url": youtube_url, 
            "transcript": transcript, 
            "current_datetime": current_datetime, 
            "video_title": video_title
        }
        
        if progress_callback:
            progress_callback(50)
            
        # Execute with crew
        crew_output = crew.kickoff(inputs=inputs)
        
        if progress_callback:
            progress_callback(90)
            
        # Extract the requested content
        task_outputs = {}
        for task in crew.tasks:
            if hasattr(task, 'output') and task.output:
                task_name = task.name if hasattr(task, 'name') else task.__class__.__name__
                task_outputs[task_name] = task.output.raw
        
        if progress_callback:
            progress_callback(100)
            
        # Calculate analysis time
        end_time = datetime.now()
        analysis_time = (end_time - start_time).total_seconds()
            
        # Extract token usage
        token_usage = {}
        if hasattr(crew_output, 'token_usage'):
            token_info = crew_output.token_usage
            if hasattr(token_info, 'get'):
                # Already a dictionary
                token_usage = token_info
            else:
                # Convert UsageMetrics object to dictionary
                token_usage = {
                    "total_tokens": getattr(token_info, 'total_tokens', 0),
                    "prompt_tokens": getattr(token_info, 'prompt_tokens', 0),
                    "completion_tokens": getattr(token_info, 'completion_tokens', 0)
                }
        
        # Determine which output to return based on the requested analysis type
        result = None
        if analysis_type == "Action Plan" and "analyze_and_plan_content" in task_outputs:
            result = task_outputs["analyze_and_plan_content"]
        elif analysis_type == "Blog Post" and "write_blog_post" in task_outputs:
            result = task_outputs["write_blog_post"]
        elif analysis_type == "LinkedIn Post" and "write_linkedin_post" in task_outputs:
            result = task_outputs["write_linkedin_post"]
        elif analysis_type == "X Tweet" and "write_tweet" in task_outputs:
            result = task_outputs["write_tweet"]
        else:
            logger.error(f"Failed to generate {analysis_type}, task output not found in results")
            return None, f"Failed to generate {analysis_type}"
        
        # Cache the newly created content
        if result and cached_results:
            if "task_outputs" not in cached_results:
                cached_results["task_outputs"] = {}
                
            # Add the new analysis to the cached task outputs
            if analysis_type == "Action Plan":
                cached_results["task_outputs"]["analyze_and_plan_content"] = result
            elif analysis_type == "Blog Post":
                cached_results["task_outputs"]["write_blog_post"] = result
            elif analysis_type == "LinkedIn Post":
                cached_results["task_outputs"]["write_linkedin_post"] = result
            elif analysis_type == "X Tweet":
                cached_results["task_outputs"]["write_tweet"] = result
                
            # Cache the updated results
            cache_analysis(video_id, cached_results)
            logger.info(f"Updated cached results with new {analysis_type} for video {video_id}")
            
        logger.info(f"Successfully generated {analysis_type} for video {video_id}")
        return result, {"token_usage": token_usage, "analysis_time": analysis_time, "cached": False}
        
    except Exception as e:
        error_msg = f"Error generating {analysis_type}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return None, error_msg

if __name__ == "__main__":
    main() 
