"""
Original UI components extracted from the main webapp to preserve exact functionality.
This maintains the exact layout and behavior while allowing backend service integration.
"""

import streamlit as st
import re
import html
import time
import traceback
from typing import Dict, Any, List, Optional

from ..utils.logging import get_logger
from ..utils.youtube_utils import clean_markdown_fences
from ..utils.cache_utils import clear_analysis_cache
from ..utils.video_highlights import clear_highlights_cache, generate_highlights_video, get_cached_highlights_video
from langchain_core.messages import AIMessage, HumanMessage

logger = get_logger("original_components")


def display_analysis_results_original(results: Dict[str, Any]):
    """
    Display the analysis results exactly as in the original webapp.
    
    Args:
        results: The analysis results dictionary
    """
    def sanitize_html_content(content):
        """Clean up and sanitize HTML content for proper rendering."""
        if not content:
            return ""
        
        # Fix common HTML issues
        content = html.unescape(content)
        
        # Fix broken or incomplete HTML tags
        content = re.sub(r'<h##([^>]*)>', r'<h3\1>', content)
        content = re.sub(r'</h##>', r'</h3>', content)
        content = re.sub(r'<h(\d{2,})([^>]*)>', r'<h3\2>', content)
        content = re.sub(r'</h\d{2,}>', r'</h3>', content)
        
        # Fix specific malformed pattern
        content = re.sub(
            r'<h##\s+style="([^"]*)">([^<]+)</h##>',
            r'<h3 style="\1">\2</h3>',
            content
        )
        
        # Fix nested list handling
        content = re.sub(
            r'(?m)^(\s{2,})- (.+)$',
            r'<li class="nested-item" style="margin-left: 1.5rem; margin-bottom: 0.5rem;">\2</li>',
            content
        )
        
        # Fix common unclosed tags
        for tag in ['p', 'div', 'span', 'strong', 'em', 'ul', 'ol', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            open_count = len(re.findall(f'<{tag}[^>]*>', content))
            close_count = len(re.findall(f'</{tag}>', content))
            
            if open_count > close_count:
                diff = open_count - close_count
                content += f'\n{"</" + tag + ">" * diff}'
        
        # Fix lists
        if '<li' in content and '</li>' not in content:
            content = re.sub(r'<li([^>]*)>([^<]+)', r'<li\1>\2</li>', content)
        
        if '<ul' in content and '</ul>' not in content:
            content += '\n</ul>'
        
        # Fix attributes
        content = re.sub(r'class=([^\s>]+)', r'class="\1"', content)
        content = re.sub(r'style="([^"]*?)(?=[^"]*>)', r'style="\1"', content)
        
        return content

    logger.info(f"Displaying analysis results with keys: {list(results.keys())}")
    if "task_outputs" in results:
        logger.info(f"Task outputs available: {list(results['task_outputs'].keys())}")
    
    # Get video information
    video_id = results.get("video_id", "")
    youtube_url = results.get("youtube_url", "")
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
        chat_enabled = st.session_state.get("chat_enabled", False)
        chat_details = st.session_state.get("chat_details")
        
        logger.info(f"Chat status - enabled: {chat_enabled}, details available: {chat_details is not None}")
        
        if chat_enabled and chat_details and isinstance(chat_details, dict):
            try:
                # Create a unique session ID for this display context
                display_context_id = f"display_analysis_{id(results)}"
                st.session_state.chat_session_id = display_context_id
                display_chat_interface_original()
            except Exception as e:
                logger.error(f"Error displaying chat interface: {str(e)}")
                st.markdown("""
                <div style="background: rgba(255, 177, 66, 0.2); border-left: 4px solid #ffb142; padding: 1.5rem; border-radius: 4px; margin-bottom: 1rem; height: 380px; display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center;">
                    <h3 style="margin-top: 0; color: #ffb142;">Chat Error</h3>
                    <p style="color: #e0e0e0;">An error occurred while displaying the chat interface. Please try analyzing the video again.</p>
                </div>
                """, unsafe_allow_html=True)
        elif chat_enabled and not chat_details:
            st.markdown("""
            <div style="background: rgba(255, 177, 66, 0.2); border-left: 4px solid #ffb142; padding: 1.5rem; border-radius: 4px; margin-bottom: 1rem; height: 380px; display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center;">
                <h3 style="margin-top: 0; color: #ffb142;">Chat Setup Issue</h3>
                <p style="color: #e0e0e0;">Chat is enabled but setup details are missing. This may be due to cache compatibility issues. Please try clearing the cache and analyzing again.</p>
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
        
        context_tag_colors = {
            "Tutorial": "#4a69bd",
            "News": "#f6b93b",
            "Review": "#78e08f",
            "Case Study": "#fa983a",
            "Interview": "#b71540",
            "Opinion Piece": "#8c7ae6",
            "How-To Guide": "#e58e26",
            "General": "#95a5a6"
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
    
    # Add section for generating additional analysis types
    task_outputs = results.get("task_outputs", {})
    
    # Create an expander for the on-demand generation options
    with st.expander("🔄 Generate Additional Content Types", expanded=True):
        st.write("Generate additional content types on demand based on this video.")
        
        # Create a row of buttons for different analysis types
        additional_col1, additional_col2, additional_col3, additional_col4 = st.columns(4)
        
        # Button for generating Action Plan
        with additional_col1:
            action_plan_disabled = "analyze_and_plan_content" in task_outputs
            action_plan_btn_text = "📋 Action Plan" if not action_plan_disabled else "✅ Action Plan (Available in Full report)"
            
            if st.button(action_plan_btn_text, disabled=action_plan_disabled, key="generate_action_plan"):
                generate_additional_content("Action Plan", youtube_url, video_id, results.get("transcript", ""))
        
        # Button for generating Blog Post
        with additional_col2:
            blog_disabled = "write_blog_post" in task_outputs
            blog_btn_text = "📝 Blog Post" if not blog_disabled else "✅ Blog Post (Available)"
            
            if st.button(blog_btn_text, disabled=blog_disabled, key="generate_blog_post"):
                generate_additional_content("Blog Post", youtube_url, video_id, results.get("transcript", ""))
        
        # Button for generating LinkedIn Post
        with additional_col3:
            linkedin_disabled = "write_linkedin_post" in task_outputs
            linkedin_btn_text = "💼 LinkedIn Post" if not linkedin_disabled else "✅ LinkedIn Post (Available)"
            
            if st.button(linkedin_btn_text, disabled=linkedin_disabled, key="generate_linkedin_post"):
                generate_additional_content("LinkedIn Post", youtube_url, video_id, results.get("transcript", ""))
        
        # Button for generating X Tweet
        with additional_col4:
            tweet_disabled = "write_tweet" in task_outputs
            tweet_btn_text = "🐦 X Tweet" if not tweet_disabled else "✅ X Tweet (Available)"
            
            if st.button(tweet_btn_text, disabled=tweet_disabled, key="generate_tweet"):
                generate_additional_content("X Tweet", youtube_url, video_id, results.get("transcript", ""))
    
    # Create tabs for analysis content
    analysis_container = st.container()
    
    with analysis_container:
        # Determine which tabs to show
        tab_options = ["📄 Full Report"]
        tab_index = 1
        
        blog_tab_index = None
        linkedin_tab_index = None
        tweet_tab_index = None
        transcript_tab_index = None
        highlights_tab_index = None
        
        # Show tabs for all available content
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
        
        # Display content in tabs
        with tabs[0]:  # Full Report
            # Display token usage and analysis time
            if "token_usage" in results and results["token_usage"]:
                token_info = results["token_usage"]
                if hasattr(token_info, 'get'):
                    tokens_display = f"**Token Usage (Initial Analysis):** {token_info.get('total_tokens', 'N/A')} total tokens"
                    if "prompt_tokens" in token_info and "completion_tokens" in token_info:
                        tokens_display += f" ({token_info.get('prompt_tokens', 'N/A')} prompt, {token_info.get('completion_tokens', 'N/A')} completion)"
                else:
                    total = getattr(token_info, 'total_tokens', 'N/A')
                    prompt = getattr(token_info, 'prompt_tokens', 'N/A')
                    completion = getattr(token_info, 'completion_tokens', 'N/A')
                    tokens_display = f"**Token Usage (Initial Analysis):** {total} total tokens ({prompt} prompt, {completion} completion)"
                st.markdown(tokens_display)
            
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
            
            # Show Action Plan if available
            if "analyze_and_plan_content" in task_outputs:
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
                report_content = clean_markdown_fences(report_content)
                st.markdown(report_content)
            else:
                st.info("Full report not available.")
        
        # Blog Post tab
        if blog_tab_index is not None:
            with tabs[blog_tab_index]:
                if "write_blog_post" in task_outputs:
                    content = sanitize_html_content(task_outputs["write_blog_post"])
                    content = clean_markdown_fences(content)
                    st.markdown(content, unsafe_allow_html=True)
                else:
                    st.info("Blog post content not available.")
        
        # LinkedIn Post tab
        if linkedin_tab_index is not None:
            with tabs[linkedin_tab_index]:
                if "write_linkedin_post" in task_outputs:
                    content = sanitize_html_content(task_outputs["write_linkedin_post"])
                    content = clean_markdown_fences(content)
                    st.markdown(content, unsafe_allow_html=True)
                else:
                    st.info("LinkedIn post content not available.")
        
        # X Tweet tab
        if tweet_tab_index is not None:
            with tabs[tweet_tab_index]:
                if "write_tweet" in task_outputs:
                    content = sanitize_html_content(task_outputs["write_tweet"])
                    content = clean_markdown_fences(content)
                    st.markdown(content, unsafe_allow_html=True)
                else:
                    st.info("X Tweet content not available.")
        
        # Transcript tab
        with tabs[transcript_tab_index]:
            if "transcript" in results:
                transcript = results["transcript"]
                st.text_area("Video Transcript", transcript, height=400, label_visibility="collapsed")
            else:
                st.info("Transcript not available.")
        
        # Video Highlights tab
        with tabs[highlights_tab_index]:
            display_video_highlights_tab(video_id)


def display_chat_interface_original():
    """Display a proper chat interface with proper functionality."""
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
    if not hasattr(st.session_state, 'chat_details') or st.session_state.chat_details is None:
        st.markdown("""
        <div style="background: rgba(255, 177, 66, 0.2); border-left: 4px solid #ffb142; padding: 1.5rem; border-radius: 4px; margin-bottom: 1rem; height: 380px; display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center;">
            <h3 style="margin-top: 0; color: #ffb142;">Chat Details Not Found</h3>
            <p style="color: #e0e0e0;">There was an issue setting up the chat. This might be due to problems retrieving the video transcript.</p>
        </div>
        """, unsafe_allow_html=True)
        return
    
    chat_details = st.session_state.chat_details
    
    # Handle errors in chat details
    if not chat_details or not isinstance(chat_details, dict):
        st.markdown("""
        <div style="background: rgba(255, 177, 66, 0.2); border-left: 4px solid #ffb142; padding: 1.5rem; border-radius: 4px; margin-bottom: 1rem; height: 380px; display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center;">
            <h3 style="margin-top: 0; color: #ffb142;">Invalid Chat Details</h3>
            <p style="color: #e0e0e0;">There was an issue with the chat setup. Please try analyzing the video again.</p>
        </div>
        """, unsafe_allow_html=True)
        logger.error(f"Invalid chat_details type: {type(chat_details)}. Expected dictionary.")
        return
    
    # Create a container for the chat messages with a fixed height
    chat_container = st.container(height=380)
    
    # Check if we need to add a welcome message
    if len(st.session_state.chat_messages) == 0:
        video_title = chat_details.get("title", "this video")
        welcome_message = f"Hello! I'm your AI assistant for the video \"{video_title}\". Ask me any questions about the content, and I'll do my best to answer based on the transcript. I'll include timestamps [MM:SS] in my answers to help you locate information in the video."
        st.session_state.chat_messages.append({"role": "assistant", "content": welcome_message})
    
    # Display all messages in the chat container
    with chat_container:
        for i, message in enumerate(st.session_state.chat_messages):
            if message["role"] == "thinking":
                continue
                
            if message["role"] == "user":
                with st.chat_message("user", avatar="👤"):
                    st.markdown(message["content"])
            elif message["role"] == "assistant":
                with st.chat_message("assistant", avatar="🤖"):
                    st.markdown(message["content"])
    
    # Chat input with unique key
    video_id = st.session_state.get('video_id', 'default')
    # Use random suffix to ensure unique key even for the same video
    import uuid
    key_suffix = str(uuid.uuid4())[:8]
    stable_key = f"chat_input_{video_id}_{key_suffix}"
    
    user_input = st.chat_input("Ask a question about the video...", key=stable_key)
    
    if user_input:
        logger.info(f"User question: {user_input}")
        
        # Add user message to chat history
        st.session_state.chat_messages.append({"role": "user", "content": user_input})
        
        # Add thinking message that will be replaced with the actual response
        st.session_state.chat_messages.append({"role": "thinking", "content": "Thinking..."})
        
        # Explicitly process the chat input now
        try:
            from ..webapp_functions import handle_chat_input as process_chat
            process_chat()
        except Exception as e:
            logger.error(f"Error directly processing chat: {str(e)}")
            # We'll rerun anyway to show the thinking indicator
        
        # Rerun to display the user message and thinking indicator
        st.rerun()


def display_video_highlights_tab(video_id: str):
    """Display the video highlights tab."""
    # Check if highlights are already cached
    highlights_video_path = get_cached_highlights_video(video_id)
    
    if highlights_video_path and st.session_state.get("highlights_segments"):
        from ..ui_legacy import display_video_highlights
        display_video_highlights(highlights_video_path, st.session_state.highlights_segments)
    else:
        st.info("Video highlights are not available for this video. This feature requires additional processing.")


def generate_additional_content(content_type: str, youtube_url: str, video_id: str, transcript: str):
    """Generate additional content on demand."""
    # This is a placeholder for the additional content generation
    # In the full implementation, this would call the content service
    with st.spinner(f"Generating {content_type}..."):
        # Simulate progress
        progress_placeholder = st.empty()
        status_placeholder = st.empty()
        progress_bar = progress_placeholder.progress(0)
        
        status_placeholder.write(f"Generating {content_type}...")
        progress_bar.progress(50)
        
        # Simulate completion
        progress_bar.progress(100)
        status_placeholder.write(f"{content_type} generation completed!")
        
        # Clear progress indicators
        progress_placeholder.empty()
        status_placeholder.empty()
        
        # For now, show a message that this feature is being integrated
        st.warning(f"{content_type} generation is being integrated with the new architecture. Please check back soon!")


def format_analysis_time(seconds: float, include_cached: bool = False, cached: bool = False) -> str:
    """Format analysis time for display."""
    if cached:
        return "< 1 second (cached)"
    
    if seconds < 60:
        return f"{seconds:.1f} seconds"
    else:
        minutes = int(seconds // 60)
        remaining_seconds = seconds % 60
        return f"{minutes}m {remaining_seconds:.1f}s"