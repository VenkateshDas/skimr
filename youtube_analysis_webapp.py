import os
import sys
import re
import time
import streamlit as st
from typing import Optional, Dict, Any, Tuple, List, Sequence, TypedDict, Annotated
import pandas as pd
from datetime import datetime

# Add the src directory to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

# Import the YouTube Analysis modules
from src.youtube_analysis import (
    run_analysis, 
    extract_category,
    setup_chat_for_video,
    get_transcript_with_timestamps,
    format_transcript_with_clickable_timestamps,
    get_category_class,
    extract_youtube_thumbnail,
    load_css,
    get_cached_analysis,
    cache_analysis,
    clear_analysis_cache
)
from src.youtube_analysis.utils.youtube_utils import get_transcript, extract_video_id, get_video_info, validate_youtube_url
from src.youtube_analysis.utils.logging import setup_logger

# LangGraph and LangChain imports for chat functionality
from langchain_core.messages import AIMessage, HumanMessage, BaseMessage

# Configure logging
logger = setup_logger("streamlit_app", log_level="INFO")

# App version
__version__ = "1.0.0"

# Define the state for our chat agent
class AgentState(TypedDict):
    """State for the agent."""
    messages: Annotated[Sequence[BaseMessage], "The messages in the conversation"]
    video_id: Annotated[str, "The YouTube video ID"]
    youtube_url: Annotated[str, "The YouTube video URL"]
    title: Annotated[str, "The title of the video"]
    description: Annotated[str, "The description of the video"]

# Set page configuration
st.set_page_config(
    page_title="YouTube Video Analyzer",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

def display_chat_interface(chat_details: Dict[str, Any]):
    """
    Display the chat interface for interacting with the video content.
    
    Args:
        chat_details: The chat setup details
    """
    # Initialize chat messages if not exists
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
    
    # Create a container for the chat interface
    chat_container = st.container()
    
    # Create a container for the input at the bottom
    input_container = st.container()
    
    # Chat input (at the bottom)
    with input_container:
        prompt = st.chat_input("Ask a question about the video...", key="chat_input")
    
    # Display chat messages in the chat container
    with chat_container:
        # Display existing messages
        for message in st.session_state.chat_messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
        
        # Handle new message
        if prompt:
            # Add user message to chat history
            st.session_state.chat_messages.append({"role": "user", "content": prompt})
            
            # Display user message
            with st.chat_message("user"):
                st.markdown(prompt)
            
            # Get AI response
            with st.chat_message("assistant"):
                message_placeholder = st.empty()
                
                try:
                    # Get the agent and thread ID
                    agent = chat_details["agent"]
                    thread_id = chat_details["thread_id"]
                    
                    # Convert previous messages to the format expected by LangGraph
                    messages = []
                    for msg in st.session_state.chat_messages:
                        if msg["role"] == "user":
                            messages.append(HumanMessage(content=msg["content"]))
                        elif msg["role"] == "assistant":
                            messages.append(AIMessage(content=msg["content"]))
                    
                    # Add the current user message if not already added
                    if not messages or messages[-1].type != "human":
                        messages.append(HumanMessage(content=prompt))
                    
                    # Invoke the agent with the thread ID for memory persistence
                    response = agent.invoke(
                        {"messages": messages},
                        config={"configurable": {"thread_id": thread_id}},
                    )
                    
                    # Extract the final answer
                    final_message = response["messages"][-1]
                    answer = final_message.content
                    
                    # Display response
                    message_placeholder.markdown(answer)
                    
                    # Add AI response to chat history
                    st.session_state.chat_messages.append({"role": "assistant", "content": answer})
                except Exception as e:
                    logger.error(f"Error getting chat response: {str(e)}")
                    message_placeholder.markdown("Sorry, I encountered an error while processing your question. Please try again.") 

def display_analysis_results(results: Dict[str, Any]):
    """
    Display the analysis results for a YouTube video.
    
    Args:
        results: The analysis results dictionary
    """
    video_id = results["video_id"]
    category = results["category"]
    token_usage = results.get("token_usage", None)
    
    # Create a container for video and chat
    st.markdown("<h2 class='sub-header'>Video & Chat</h2>", unsafe_allow_html=True)
    video_chat_container = st.container()
    
    with video_chat_container:
        # Create columns for video and chat
        col1, col2 = st.columns([1, 1])
        
        with col1:
            # Display embedded YouTube video with name to target it directly
            st.markdown(f'<iframe id="youtube-player" name="youtube-player" width="100%" height="315" src="https://www.youtube.com/embed/{video_id}" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>', unsafe_allow_html=True)

        
        with col2:
            # Display chat interface
            st.markdown("<h3>Chat with this Video</h3>", unsafe_allow_html=True)
            st.markdown("<p>Ask questions about the video content and get detailed answers based on the transcript.</p>", unsafe_allow_html=True)
            
            # Create a container with fixed height for the chat interface
            chat_area = st.container()
            
            with chat_area:
                if st.session_state.chat_enabled and st.session_state.chat_details:
                    display_chat_interface(st.session_state.chat_details)
                else:
                    st.warning("Chat functionality could not be enabled for this video. Please try again.")
    
    # Create a container for analysis content
    st.markdown("<h2 class='sub-header'>Analysis Results</h2>", unsafe_allow_html=True)
    analysis_container = st.container()
    
    with analysis_container:
        # Analysis tabs
        tabs = st.tabs(["Summary", "Analysis", "Action Plan", "Full Report", "Transcript"])
        
        task_outputs = results["task_outputs"]
        
        # Display content in tabs
        with tabs[0]:
            if "summarize_content" in task_outputs:
                st.markdown(task_outputs["summarize_content"])
            else:
                st.info("Summary not available.")
        
        with tabs[1]:
            if "analyze_content" in task_outputs:
                st.markdown(task_outputs["analyze_content"])
            else:
                st.info("Analysis not available.")
        
        with tabs[2]:
            if "create_action_plan" in task_outputs:
                st.markdown(task_outputs["create_action_plan"])
            else:
                st.info("Action plan not available.")
        
        with tabs[3]:
            if "write_report" in task_outputs:
                st.markdown(task_outputs["write_report"])
            else:
                st.info("Full report not available.")
        
        with tabs[4]:
            st.markdown("### Video Transcript")
            
            # Add toggles for timestamps
            col_a, col_b, col_c = st.columns([1, 1, 1])
            with col_a:
                show_timestamps = st.checkbox("Show timestamps", value=True)
            with col_b:
                clickable_timestamps = st.checkbox("Enable clickable timestamps", value=True)
            with col_c:
                jump_in_embedded = st.checkbox("Jump in embedded video", value=True, 
                                              help="When enabled, clicking timestamps will jump to that point in the embedded video instead of opening a new tab. Clicking a timestamp will reload the video at that specific time, which will reset the video player.")
            # Add JavaScript to enable communication with the YouTube iframe
            if jump_in_embedded:
                # No custom JavaScript needed with the new approach
                pass
            
            if show_timestamps:
                # Check if we have a timestamped transcript in session state
                if "timestamped_transcript" in st.session_state and st.session_state.timestamped_transcript:
                    if clickable_timestamps and "transcript_list" in st.session_state:
                        # Display transcript with clickable timestamps
                        html = format_transcript_with_clickable_timestamps(st.session_state.transcript_list, video_id, jump_in_embedded)
                        st.markdown(html, unsafe_allow_html=True)
                    else:
                        # Display plain text transcript with timestamps
                        st.text_area("Transcript with timestamps", st.session_state.timestamped_transcript, height=400, label_visibility="collapsed")
                else:
                    # Try to get transcript with timestamps
                    try:
                        timestamped_transcript, transcript_list = get_transcript_with_timestamps(results["youtube_url"])
                        st.session_state.timestamped_transcript = timestamped_transcript
                        st.session_state.transcript_list = transcript_list
                        
                        if clickable_timestamps:
                            # Display transcript with clickable timestamps
                            html = format_transcript_with_clickable_timestamps(transcript_list, video_id, jump_in_embedded)
                            st.markdown(html, unsafe_allow_html=True)
                        else:
                            # Display plain text transcript with timestamps
                            st.text_area("Transcript with timestamps", timestamped_transcript, height=400, label_visibility="collapsed")
                    except Exception as e:
                        st.error(f"Error retrieving transcript with timestamps: {str(e)}")
                        st.text_area("Transcript", results["transcript"], height=400, label_visibility="collapsed")
            else:
                # Show regular transcript
                st.text_area("Transcript", results["transcript"], height=400, label_visibility="collapsed")
    
    # Display token usage if available
    if token_usage:
        st.markdown("<h2 class='sub-header'>Token Usage</h2>", unsafe_allow_html=True)
        token_container = st.container()
        
        with token_container:
            # Create a nice looking token usage display
            st.markdown("<div class='card' style='padding: 1rem;'>", unsafe_allow_html=True)
            
            if isinstance(token_usage, dict):
                # If token_usage is a dictionary with detailed information
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Prompt Tokens", token_usage.get("prompt_tokens", "N/A"))
                
                with col2:
                    st.metric("Completion Tokens", token_usage.get("completion_tokens", "N/A"))
                
                with col3:
                    st.metric("Total Tokens", token_usage.get("total_tokens", "N/A"))
                
                # If there's a cost estimate
                if "cost" in token_usage:
                    st.markdown(f"**Estimated Cost:** ${token_usage['cost']:.4f}")
            else:
                # If token_usage is a simple value or string
                st.markdown(f"**Total Tokens Used:** {token_usage}")
            
            st.markdown("</div>", unsafe_allow_html=True)
            
            # Add timestamp of analysis
            if "timestamp" in results:
                st.markdown(f"<div class='metadata'>Analysis completed on {results['timestamp']}</div>", unsafe_allow_html=True)

def main():
    """
    Main function to run the Streamlit app.
    """
    # Load custom CSS
    st.markdown(load_css(), unsafe_allow_html=True)
    
    # Initialize session state variables if they don't exist
    if "chat_enabled" not in st.session_state:
        st.session_state.chat_enabled = False
    
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
    
    if "chat_details" not in st.session_state:
        st.session_state.chat_details = None
    
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
    
    # Sidebar
    with st.sidebar:
        st.image("https://upload.wikimedia.org/wikipedia/commons/e/ef/Youtube_logo.png", width=180)
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
        
        # Cache toggle
        use_cache = st.checkbox(
            "Use cached analysis",
            value=True,
            help="Use cached analysis results if available to save costs"
        )
        
        # Set environment variables based on settings
        os.environ["LLM_MODEL"] = model
        os.environ["LLM_TEMPERATURE"] = str(temperature)
        
        # Reset chat button (if chat is enabled)
        if st.session_state.chat_enabled:
            if st.button("Reset Chat", key="reset_chat"):
                st.session_state.chat_messages = []
                # Re-initialize welcome message
                if st.session_state.chat_details and "title" in st.session_state.chat_details:
                    has_timestamps = st.session_state.chat_details.get("has_timestamps", False)
                    video_title = st.session_state.chat_details.get("title", "this YouTube video")
                    
                    welcome_message = f"Hello! I'm your AI assistant for the video \"{video_title}\". Ask me any questions about the content, and I'll do my best to answer based on the transcript."
                    if has_timestamps:
                        welcome_message += " I'll include timestamps [MM:SS] in my answers to help you locate information in the video."
                    
                    st.session_state.chat_messages = [
                        {
                            "role": "assistant", 
                            "content": welcome_message
                        }
                    ]
                st.rerun()
        
        # Reset analysis button (if analysis is complete)
        if st.session_state.analysis_complete:
            if st.button("New Analysis", key="new_analysis"):
                # Reset all relevant state
                st.session_state.chat_enabled = False
                st.session_state.chat_messages = []
                st.session_state.chat_details = None
                st.session_state.analysis_complete = False
                st.session_state.analysis_results = None
                st.session_state.timestamped_transcript = None
                st.session_state.transcript_list = None
                st.session_state.video_id = None
                st.rerun()
                
            # Clear cache button (only shown if a video has been analyzed)
            if "video_id" in st.session_state and st.session_state.video_id:
                if st.button("Clear Cache for This Video", key="clear_cache"):
                    video_id = st.session_state.video_id
                    if clear_analysis_cache(video_id):
                        st.success(f"Cache cleared for video {video_id}")
                        # Reset analysis state to force a fresh analysis
                        st.session_state.analysis_complete = False
                        st.session_state.analysis_results = None
                        st.session_state.video_id = None
                        st.experimental_rerun()
                    else:
                        st.info("No cached analysis found for this video")
        
        st.markdown("---")
        st.markdown(f"**App Version:** {__version__}")
        st.markdown("Made with ❤️ using CrewAI & LangGraph")

    # Main content
    st.markdown("<h1 class='main-header'>YouTube Video Analyzer & Chat</h1>", unsafe_allow_html=True)
    
    # Only show welcome text and input fields if analysis is not complete
    if not st.session_state.analysis_complete:
        st.markdown("<p class='info-text'>Extract insights, summaries, and action plans from any YouTube video. Chat with the video content to learn more!</p>", unsafe_allow_html=True)
        
        # URL input and analysis button
        youtube_url = st.text_input("YouTube URL", placeholder="Enter YouTube URL (e.g., https://youtu.be/...)", label_visibility="collapsed")
        analyze_button = st.button("Analyze Video", use_container_width=True)
        
        # Run analysis when button is clicked
        if analyze_button:
            if not youtube_url:
                st.error("Please enter a YouTube URL.")
            elif not validate_youtube_url(youtube_url):
                st.error("Please enter a valid YouTube URL.")
            else:
                with st.spinner("Analyzing video..."):
                    try:
                        # Get transcript with timestamps
                        try:
                            timestamped_transcript, transcript_list = get_transcript_with_timestamps(youtube_url)
                            st.session_state.timestamped_transcript = timestamped_transcript
                            st.session_state.transcript_list = transcript_list
                        except Exception as e:
                            logger.warning(f"Could not get transcript with timestamps: {str(e)}")
                            st.session_state.timestamped_transcript = None
                            st.session_state.transcript_list = None
                            
                        # Create progress placeholder
                        progress_placeholder = st.empty()
                        status_placeholder = st.empty()
                        
                        # Initialize progress bar
                        progress_bar = progress_placeholder.progress(0)
                        status_placeholder.info("Fetching video transcript...")
                        
                        # Define progress callback
                        def update_progress(value):
                            progress_bar.progress(value)
                        
                        # Define status callback
                        def update_status(message):
                            status_placeholder.info(message)
                        
                        # Run the analysis
                        results, error = run_analysis(
                            youtube_url, 
                            progress_callback=update_progress,
                            status_callback=update_status,
                            use_cache=use_cache
                        )
                        
                        if error:
                            st.markdown(f"<div class='error-box'>Error: {error}</div>", unsafe_allow_html=True)
                        elif results:
                            # Store results in session state to persist across reruns
                            st.session_state.analysis_results = results
                            st.session_state.analysis_complete = True
                            st.session_state.video_id = results["video_id"]  # Store the video ID for cache clearing
                            
                            # Store chat details in session state
                            if "chat_details" in results:
                                st.session_state.chat_details = results["chat_details"]
                                st.session_state.chat_enabled = True
                                
                                # Add a welcome message with information about timestamps if available
                                has_timestamps = results["chat_details"].get("has_timestamps", False)
                                video_title = results["chat_details"].get("title", "this YouTube video")
                                
                                welcome_message = f"Hello! I'm your AI assistant for the video \"{video_title}\". Ask me any questions about the content, and I'll do my best to answer based on the transcript."
                                if has_timestamps:
                                    welcome_message += " I'll include timestamps [MM:SS] in my answers to help you locate information in the video."
                                
                                st.session_state.chat_messages = [
                                    {
                                        "role": "assistant", 
                                        "content": welcome_message
                                    }
                                ]
                            
                            # Clear the progress and status placeholders
                            progress_placeholder.empty()
                            status_placeholder.empty()
                            
                            # Force a rerun to update the UI
                            st.rerun()
                    except Exception as e:
                        st.error(f"Error analyzing video: {str(e)}")
                        logger.error(f"Error in analysis: {str(e)}", exc_info=True)
                
        # Display information about the app when no analysis is running or complete
        else:
            # Display features in cards
            st.markdown("<h2 class='sub-header'>Features</h2>", unsafe_allow_html=True)
            
            # Feature cards with improved styling
            st.markdown("""
            <div class="feature-grid">
                <div class="card">
                    <span class="card-icon">🔎</span>
                    <h3>Video Classification</h3>
                    <p>Automatically categorize videos into topics like Technology, Business, Education, and more.</p>
                </div>
                <div class="card">
                    <span class="card-icon">📋</span>
                    <h3>Comprehensive Summary</h3>
                    <p>Get a TL;DR and key points to quickly understand the video's content without watching it entirely.</p>
                </div>
                <div class="card">
                    <span class="card-icon">💬</span>
                    <h3>Chat Interface</h3>
                    <p>Ask questions about the video content and get answers based on the transcript in real-time.</p>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # How it works section
            st.markdown("<h2 class='sub-header'>How It Works</h2>", unsafe_allow_html=True)
            
            # Steps with improved styling
            st.markdown("""
            <div class="step-grid">
                <div class="card">
                    <h3>Step 1</h3>
                    <p>Paste any YouTube URL in the input field above.</p>
                </div>
                <div class="card">
                    <h3>Step 2</h3>
                    <p>Our AI extracts and processes the video transcript.</p>
                </div>
                <div class="card">
                    <h3>Step 3</h3>
                    <p>Multiple specialized AI agents analyze the content.</p>
                </div>
                <div class="card">
                    <h3>Step 4</h3>
                    <p>Chat with the video and explore the insights and summary.</p>
                </div>
            </div>
            """, unsafe_allow_html=True)
    
    # Check if analysis is complete (retained from session state)
    if st.session_state.analysis_complete and st.session_state.analysis_results:
        # Display results from session state
        display_analysis_results(st.session_state.analysis_results)

if __name__ == "__main__":
    main() 