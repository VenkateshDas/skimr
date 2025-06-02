"""
Streamlit UI components for displaying analysis results and chat interface.
"""

import streamlit as st
from typing import Dict, Any, List, Callable, Optional
import re
from datetime import datetime

from ..utils.logging import get_logger
from ..utils.youtube_utils import clean_markdown_fences

logger = get_logger("ui_components")


def display_analysis_results(
    analysis_results: Dict[str, Any], 
    session_manager,
    on_demand_handler: Optional[Callable] = None
) -> None:
    """
    Display analysis results in a tabbed interface.
    
    Args:
        analysis_results: Dictionary containing analysis results
        session_manager: StreamlitSessionManager instance
        on_demand_handler: Callback function for generating additional content
    """
    if not analysis_results or "task_outputs" not in analysis_results:
        st.error("No analysis results to display")
        # Debug information
        if analysis_results:
            with st.expander("🔧 Debug - Available Keys"):
                st.json(list(analysis_results.keys()))
        return
    
    task_outputs = analysis_results.get("task_outputs", {})
    

    
    # Define tab configuration
    tab_config = [
        ("📊 Full Report", "classify_and_summarize_content", "summary"),
        ("📋 Action Plan", "analyze_and_plan_content", "action_plan"),
        ("📝 Blog Post", "write_blog_post", "blog"),
        ("💼 LinkedIn Post", "write_linkedin_post", "linkedin"), 
        ("🐦 X Tweet", "write_tweet", "tweet"),
        ("📜 Transcript", "transcript", "transcript"),
        # ("🎬 Highlights", "highlights", "highlights")  # Disabled - keeping code for future use
    ]
    
    # Create tabs
    tabs = st.tabs([tab[0] for tab in tab_config])
    
    # Display content in each tab
    for idx, (tab_name, task_key, content_type) in enumerate(tab_config):
        with tabs[idx]:
            if content_type == "transcript":
                _display_transcript_tab(analysis_results, session_manager)
            elif content_type == "highlights":
                # Highlights disabled - keeping code for future use
                # _display_highlights_tab(analysis_results, session_manager)
                st.info("Video highlights feature is temporarily disabled.")
            else:
                # Regular content tabs
                content = task_outputs.get(task_key)
                if content:
                    # Handle both string content and TaskOutput objects
                    if isinstance(content, dict) and "content" in content:
                        # It's a TaskOutput dictionary
                        actual_content = content["content"]
                    elif isinstance(content, str):
                        # It's raw string content
                        actual_content = content
                    else:
                        # Try to extract content from object
                        actual_content = getattr(content, 'content', str(content))
                    
                    _display_content_with_copy(actual_content, content_type)
                    
                    # Disable regenerate for Full Report tab
                    if task_key != "classify_and_summarize_content":
                        # Add custom instruction field for regeneration
                        st.markdown("---")
                        st.markdown("### Regenerate with Custom Instructions")
                        custom_instruction = st.text_area(
                            f"Add custom instructions for regenerating this {tab_name}",
                            key=f"custom_instruction_{task_key}",
                            placeholder="Example: Focus more on the technical aspects, or Add more actionable steps, etc."
                        )
                        if st.button(f"Regenerate {tab_name}", key=f"regen_tab_{task_key}"):
                            if on_demand_handler:
                                on_demand_handler(task_key)
                    
                else:
                    # Content not yet generated
                    if task_key == "classify_and_summarize_content":
                        # Special handling for summary - it should be the main analysis result
                        st.warning("📊 Analysis summary not available. This might indicate an issue with the analysis process.")
                        st.info("The summary should be automatically generated during video analysis. If you see this message, please try analyzing the video again or contact support.")
                        

                    else:
                        st.info(f"{tab_name} not yet generated.")
                        
                        # Add custom instruction field
                        st.markdown("### Custom Instructions")
                        custom_instruction = st.text_area(
                            f"Add custom instructions for this {tab_name}",
                            key=f"custom_instruction_{task_key}",
                            placeholder="Example: Focus more on the technical aspects, or Add more actionable steps, etc."
                        )
                        
                        if on_demand_handler:
                            # Pass the backend task_key instead of display name
                            if st.button(f"Generate {tab_name}", key=f"gen_tab_{task_key}"):
                                on_demand_handler(task_key)


def _display_content_with_copy(content: str, content_type: str) -> None:
    """Display content with raw markdown expander."""
    # Clean markdown fences if present
    cleaned_content = clean_markdown_fences(content)
    
    # Display the main content
    st.markdown(cleaned_content)
    
    # Add expander with raw markdown at the end
    with st.expander("📄 View Raw Markdown", expanded=False):
        st.code(content, language="markdown")


def _display_transcript_tab(analysis_results: Dict[str, Any], session_manager) -> None:
    """Display transcript with timestamp toggle."""
    st.markdown("### Video Transcript")
    
    # Toggle for timestamps
    show_timestamps = st.checkbox("Show timestamps", value=True, key="transcript_timestamps")
    
    # Get transcript
    transcript_segments = analysis_results.get("transcript_segments", [])
    transcript_text = analysis_results.get("transcript", "")
    
    if transcript_segments and show_timestamps:
        # Display with timestamps
        transcript_with_timestamps = ""
        for segment in transcript_segments:
            start = segment.get('start', 0)
            minutes, seconds = divmod(int(start), 60)
            timestamp = f"[{minutes:02d}:{seconds:02d}]"
            text = segment.get('text', '')
            transcript_with_timestamps += f"{timestamp} {text}\n"
        
        st.text_area(
            "Transcript with timestamps",
            value=transcript_with_timestamps,
            height=400,
            label_visibility="collapsed"
        )
    elif transcript_text:
        # Display plain text
        st.text_area(
            "Transcript",
            value=transcript_text,
            height=400,
            label_visibility="collapsed"
        )
    else:
        st.info("Transcript not available")


def _display_highlights_tab(analysis_results: Dict[str, Any], session_manager) -> None:
    """Display video highlights."""
    highlights = analysis_results.get("highlights")
    
    if highlights:
        st.markdown("### Key Video Moments")
        for idx, highlight in enumerate(highlights):
            with st.expander(f"Highlight {idx + 1}: {highlight.get('title', 'Untitled')}", expanded=True):
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.write(highlight.get('description', ''))
                with col2:
                    timestamp = highlight.get('timestamp', '0:00')
                    st.metric("Timestamp", timestamp)
    else:
        st.info("Video highlights not yet generated.")
        if st.button("Generate Highlights", key="gen_highlights"):
            st.info("Highlight generation is coming soon!")


def display_chat_interface(
    chat_messages: List[Dict[str, str]],
    on_submit: Callable[[str], None],
    is_streaming: bool = False,
    streaming_response_placeholder: str = ""
) -> None:
    """
    Display chat interface with message history and input.
    
    Args:
        chat_messages: List of chat messages
        on_submit: Callback function when user submits a message
        is_streaming: Whether AI is currently streaming a response
        streaming_response_placeholder: Placeholder text for streaming response
    """
    # st.markdown("### 💬 Chat with Video Assistant")
    
    # Create a container for the chat messages with fixed height for scrolling
    chat_container = st.container(height=380)
    
    with chat_container:
        # Display all messages in the chat container
        for i, message in enumerate(chat_messages):
            role = message["role"]
            content = message["content"]
            
            # Skip thinking messages or empty content
            if role == "thinking" or not content:
                continue
                
            # Display user messages
            if role == "user":
                with st.chat_message("user", avatar="👤"):
                    st.markdown(content)
            
            # Display assistant messages
            elif role == "assistant":
                with st.chat_message("assistant", avatar="🤖"):
                    st.markdown(content)
        
        # Handle streaming response
        if is_streaming:
            with st.chat_message("assistant", avatar="🤖"):
                if streaming_response_placeholder:
                    placeholder = st.empty()
                    placeholder.markdown(streaming_response_placeholder + "▌")
                    # Store reference for streaming updates
                    st.session_state["chat_streaming_placeholder_ref"] = placeholder
                else:
                    st.markdown("*Thinking...*")
    
    # Add a user input field outside the message container
    user_input = st.chat_input("Ask a question about the video...", disabled=is_streaming)
    
    # Handle user input
    if user_input and not is_streaming:
        on_submit(user_input.strip())


def display_performance_stats(performance_stats: Dict[str, Any]) -> None:
    """Display Phase 2 architecture performance statistics."""
    st.markdown("### ⚡ Performance Statistics")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        cache_stats = performance_stats.get("cache_stats", {})
        st.metric(
            "Cache Hit Rate",
            f"{cache_stats.get('hit_rate', 0):.1%}",
            delta=f"{cache_stats.get('hits', 0)} hits"
        )
    
    with col2:
        connection_stats = performance_stats.get("connection_stats", {})
        st.metric(
            "Connection Pool",
            f"{connection_stats.get('active', 0)} active",
            delta=f"{connection_stats.get('reused', 0)} reused"
        )
    
    with col3:
        timing_stats = performance_stats.get("timing", {})
        total_time = timing_stats.get("total", 0)
        st.metric(
            "Analysis Time",
            f"{total_time:.1f}s",
            delta=f"-{timing_stats.get('saved', 0):.1f}s saved"
        )
    
    # Detailed breakdown
    with st.expander("Detailed Performance Breakdown", expanded=False):
        if "operation_times" in performance_stats:
            st.markdown("#### Operation Times")
            for operation, time in performance_stats["operation_times"].items():
                st.text(f"{operation}: {time:.2f}s")
        
        if "resource_usage" in performance_stats:
            st.markdown("#### Resource Usage")
            resource = performance_stats["resource_usage"]
            st.text(f"Memory: {resource.get('memory_mb', 0):.1f} MB")
            st.text(f"CPU: {resource.get('cpu_percent', 0):.1f}%")