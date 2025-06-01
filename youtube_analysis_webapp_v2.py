"""
Streamlined YouTube Analysis WebApp using Phase 2 Architecture
"""

import streamlit as st
st.set_page_config(
    page_title="Skimr Summarizer",
    page_icon=":material/movie:",
    layout="wide",
    initial_sidebar_state="expanded",
)
import os
import sys
import logging
import concurrent.futures
import traceback
import re
from typing import Optional, Dict, Any
from datetime import datetime

# Add the src directory to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

# Import configuration and setup
from src.youtube_analysis.config import APP_VERSION, validate_config, setup_logging
from src.youtube_analysis.utils.logging import get_logger

# Import new modular components
from src.youtube_analysis.ui import (
    StreamlitCallbacks, StreamlitSessionManager, 
    display_analysis_results, display_chat_interface, 
    handle_chat_input, get_skimr_logo_base64, load_css
)
from src.youtube_analysis.adapters import WebAppAdapter
from src.youtube_analysis.auth import (
    init_auth_state, display_auth_ui, get_current_user, 
    logout, check_guest_usage
)
from src.youtube_analysis.stats import get_user_stats

# Legacy imports for features not yet migrated
from src.youtube_analysis.utils.youtube_utils import clean_markdown_fences
from src.youtube_analysis.utils.cache_utils import clear_analysis_cache
from src.youtube_analysis.utils.video_highlights import clear_highlights_cache

# Import original functions for exact compatibility
try:
    from youtube_transcript_api import YouTubeTranscriptApi
except ImportError:
    # Logger not available yet at module level
    pass

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Configure logging
setup_logging()
logger = get_logger("webapp_v2")


class StreamlitWebApp:
    """Main Streamlit WebApp class using Phase 2 architecture."""
    
    def __init__(self):
        self.session_manager = StreamlitSessionManager()
        self.webapp_adapter = WebAppAdapter()
        self.callbacks = StreamlitCallbacks()
        
        # Handle content generation rerun
        if st.session_state.get("content_generation_pending"):
            st.session_state.content_generation_pending = False
            content_type = st.session_state.get("content_type_generated")
            st.session_state.content_type_generated = None
            logger.info(f"Performing one-time rerun after generating {content_type}")
            st.rerun()
    
    def initialize(self):
        """Initialize the application."""
        self.session_manager.initialize_all()
        init_auth_state()
        load_css()
        
        # Process chat input if needed
        if (self.session_manager.is_chat_enabled() and 
            st.session_state.chat_messages and 
            st.session_state.chat_messages[-1]["role"] == "thinking"):
            self._handle_chat_input()
    
    def setup_sidebar(self):
        """Setup the sidebar with settings and controls."""
        with st.sidebar:
            self._display_logo()
            self._display_user_account()
            self._display_settings()
            self._display_analysis_controls()
            self._display_version()
    
    def _display_logo(self):
        """Display the Skimr logo."""
        try:
            logo_base64 = get_skimr_logo_base64()
            if logo_base64:
                st.markdown(f"""
                <div style="text-align: center; margin-bottom: 1rem;">
                    <img src="data:image/png;base64,{logo_base64}" width="180" alt="Skimr Logo">
                </div>
                """, unsafe_allow_html=True)
        except Exception as e:
            logger.warning(f"Could not load logo: {e}")
    
    def _display_user_account(self):
        """Display user account section."""
        st.sidebar.markdown("<hr style='margin: 1.5rem 0;'>", unsafe_allow_html=True)
        with st.sidebar.expander("👤 User Account", expanded=False):
            user = get_current_user()
            if user:
                st.write(f"**Email:** {user.email}")
                
                stats = get_user_stats()
                if stats:
                    st.markdown("### Your Statistics")
                    st.metric("Summaries Generated", stats.get("summary_count", 0))
                
                if st.button("Logout", key="sidebar_logout"):
                    if logout():
                        st.rerun()
            else:
                st.info("You are not logged in")
                if st.button("Login/Sign Up", key="sidebar_login"):
                    st.session_state.show_auth = True
    
    def _display_settings(self):
        """Display settings section."""
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
                help="Higher values make output more creative"
            )
            
            # Cache toggle
            st.markdown("<h3 style='margin-top: 1rem; margin-bottom: 0.5rem;'>Performance</h3>", unsafe_allow_html=True)
            use_cache = st.checkbox(
                label="Use Cache (Faster Analysis)",
                value=True,
                help="Enable caching for faster repeated analysis"
            )
            
            # Architecture toggle
            use_optimized = st.checkbox(
                label="Use Phase 2 Optimized Architecture",
                value=True,
                help="Enable the improved service layer architecture"
            )
            
            # Update settings
            settings = {
                "model": model,
                "temperature": temperature,
                "use_cache": use_cache,
                "use_optimized": use_optimized,
                "analysis_types": ["Summary & Classification"]
            }
            self.session_manager.update_settings(settings)
            
            # Set environment variables
            os.environ["USE_OPTIMIZED_ANALYSIS"] = "true" if use_optimized else "false"
            os.environ["LLM_MODEL"] = model
            os.environ["LLM_TEMPERATURE"] = str(temperature)
    
    def _display_analysis_controls(self):
        """Display analysis control buttons."""
        if self.session_manager.is_analysis_complete():
            st.markdown("<hr style='margin: 1.5rem 0;'>", unsafe_allow_html=True)
            st.markdown("<h3 style='margin-bottom: 1rem;'>Analysis Options</h3>", unsafe_allow_html=True)
            
            # Reset chat button
            if self.session_manager.is_chat_enabled():
                if st.button("🔄 Reset Chat", key="reset_chat"):
                    self._reset_chat()
            
            # New analysis button
            if st.button("🔄 New Analysis", key="new_analysis"):
                self._new_analysis()
            
            # Clear cache button
            if st.session_state.get("video_id"):
                if st.button("🧹 Clear Cache", key="clear_cache"):
                    self._clear_cache()
    
    def _display_version(self):
        """Display app version."""
        st.markdown(f"<div style='text-align: center; margin-top: 2rem; opacity: 0.7;'>Skimr v{APP_VERSION}</div>", 
                   unsafe_allow_html=True)
    
    def display_main_content(self):
        """Display the main content area."""
        if st.session_state.get("show_auth"):
            display_auth_ui()
            return
        
        if not self.session_manager.is_analysis_complete():
            self._display_video_input()
        else:
            # Display analysis results
            self._display_analysis_results()

            # Display chat interface if enabled
            # This ensures the chat UI is rendered if chat setup was successful.
            if self.session_manager.is_chat_enabled():
                self._display_chat_interface()
    
    def _display_video_input(self):
        """Display the video input interface."""
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
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        col_left, col_middle, col_right = st.columns([1, 2, 1])
        with col_middle:
            st.markdown("<h3 style='text-align: center; width: 100%;'>Paste your YouTube link</h3>", 
                       unsafe_allow_html=True)
            url = st.text_input("YouTube URL", 
                               placeholder="https://www.youtube.com/watch?v=...", 
                               label_visibility="collapsed")
        
        if url:
            self._handle_video_analysis(url)
    
    def _handle_video_analysis(self, url: str):
        """Handle video analysis workflow."""
        # Validate URL
        if not self.webapp_adapter.validate_youtube_url(url):
            st.error("Please enter a valid YouTube URL")
            return
        
        # Check guest usage limits
        if not st.session_state.authenticated and not check_guest_usage():
            video_info = self.webapp_adapter.get_video_info(url)
            if video_info:
                st.warning("You've reached the limit of free analyses. Please log in to continue.")
                st.session_state.show_auth = True
                if st.button("Login/Sign Up"):
                    st.session_state.show_auth = True
            else:
                st.error("Could not fetch video information. Please check the URL and try again.")
            return
        
        # Run analysis
        with st.spinner("Analyzing video..."):
            self._run_video_analysis(url)
    
    def _run_video_analysis(self, url: str):
        """Run the video analysis process using the original logic."""
        try:
            # Increment guest usage
            if not st.session_state.authenticated:
                st.session_state.guest_analysis_count += 1
            
            # Reset state for new analysis
            self.session_manager.reset_analysis_state()
            st.session_state.analysis_start_time = datetime.now()
            
            # Create progress and status placeholders
            progress_placeholder = st.empty()
            status_placeholder = st.empty()
            progress_bar = progress_placeholder.progress(0)
            status_placeholder.info("Fetching video transcript...")
            
            # Define progress update functions (original implementation)
            def update_progress(value):
                try:
                    from streamlit.runtime.scriptrunner import get_script_run_ctx
                    if get_script_run_ctx():
                        progress_bar.progress(value)
                except Exception:
                    pass
            
            def update_status(message):
                try:
                    from streamlit.runtime.scriptrunner import get_script_run_ctx
                    if get_script_run_ctx():
                        status_placeholder.info(message)
                except Exception:
                    pass
            
            # Get settings
            settings = self.session_manager.get_settings()
            use_cache = settings.get("use_cache", True)
            model = settings.get("model", "gpt-4o-mini")
            temperature = settings.get("temperature", 0.2)
            
            # Set environment variables
            import os
            os.environ["LLM_MODEL"] = model
            os.environ["LLM_TEMPERATURE"] = str(temperature)
            
            logger.info(f"Using settings: model={model}, temperature={temperature}, use_cache={use_cache}")
            
            # Get video transcript using original function
            from src.youtube_analysis.utils.youtube_utils import extract_video_id, get_video_info
            
            timestamped_transcript, transcript_list, error = self._process_transcript_original(url, use_cache)
            
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
            transcript_text = self._convert_transcript_list_to_text(transcript_list)
            
            # Extract video ID
            video_id = extract_video_id(url)
            
            # Store in session state
            st.session_state.video_id = video_id
            st.session_state.video_url = url
            st.session_state.video_info = video_info
            st.session_state.transcript_list = transcript_list
            st.session_state.transcript_text = transcript_text
            
            # Clear cache if requested
            if not use_cache:
                logger.info(f"Forcing new analysis by clearing cache for video {video_id}")
                clear_analysis_cache(video_id)
            
            # Run analysis with timeout using original function
            def run_analysis_with_timeout():
                logger.info(f"Starting analysis with use_cache={use_cache}, url={url}")
                try:
                    analysis_types = ["Summary & Classification"]
                    if "settings" in st.session_state and "analysis_types" in st.session_state.settings:
                        analysis_types = st.session_state.settings["analysis_types"]
                    
                    if "Summary & Classification" not in analysis_types:
                        analysis_types = ["Summary & Classification"] + analysis_types
                    
                    # Use Phase 2 architecture
                    use_optimized = os.environ.get("USE_OPTIMIZED_ANALYSIS", "true").lower() in ("true", "1", "yes")
                    if use_optimized:
                        logger.info("Using optimized Phase 2 architecture for analysis")
                        from src.youtube_analysis import run_analysis_v2
                        analysis_result = run_analysis_v2(
                            url,
                            update_progress,
                            update_status,
                            use_cache=use_cache,
                            analysis_types=tuple(analysis_types)
                        )
                    else:
                        logger.info("Using original analysis architecture")
                        from src.youtube_analysis import run_analysis
                        analysis_result = run_analysis(
                            url,
                            update_progress,
                            update_status,
                            use_cache=use_cache,
                            analysis_types=tuple(analysis_types)
                        )
                    
                    if isinstance(analysis_result, tuple) and len(analysis_result) == 2:
                        results, error = analysis_result
                        return results, error
                    else:
                        return None, "Analysis returned unexpected result format"
                        
                except Exception as e:
                    logger.error(f"Exception in analysis: {str(e)}", exc_info=True)
                    return None, str(e)
            
            # Execute with timeout
            with concurrent.futures.ThreadPoolExecutor() as executor:
                from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx
                ctx = get_script_run_ctx()
                
                future = executor.submit(run_analysis_with_timeout)
                
                if ctx:
                    add_script_run_ctx(future, ctx)
                
                try:
                    results, analysis_error = future.result(timeout=180)
                except concurrent.futures.TimeoutError:
                    st.error("Analysis took too long and timed out. Please try again.")
                    return
                except Exception as e:
                    st.error(f"An unexpected error occurred: {str(e)}")
                    return
            
            # Clear progress indicators
            progress_placeholder.empty()
            status_placeholder.empty()
            
            # Handle results
            if analysis_error:
                st.error(f"Analysis failed: {analysis_error}")
                return
            
            if not results or "task_outputs" not in results or not results["task_outputs"]:
                st.error("Analysis didn't generate proper results. Try turning off the 'Use Cache' option and try again.")
                return
            
            # Store results
            st.session_state.analysis_results = results
            st.session_state.analysis_complete = True
            
            # Setup chat for video
            try:
                # Always try to setup chat using the original method since Phase 2 chat setup may fail for cached results
                from src.youtube_analysis import setup_chat_for_video
                logger.info("Setting up chat using original method for better compatibility")
                
                chat_details = setup_chat_for_video(
                    youtube_url=url,
                    transcript=transcript_text,
                    transcript_list=transcript_list
                )
                
                if chat_details and isinstance(chat_details, dict):
                    st.session_state.chat_details = chat_details
                    st.session_state.chat_enabled = True
                    
                    video_title = video_info.get("title", "this YouTube video")
                    welcome_message = f"Hello! I'm your AI assistant for the video \"{video_title}\". Ask me any questions about the content, and I'll do my best to answer based on the transcript. I'll include timestamps [MM:SS] in my answers to help you locate information in the video."
                    st.session_state.chat_messages = [{"role": "assistant", "content": welcome_message}]
                    logger.info("Chat setup completed successfully")
                else:
                    logger.warning("Could not setup chat functionality - chat_details is None or invalid")
                    st.session_state.chat_enabled = False
                    st.session_state.chat_details = None
                    st.session_state.chat_messages = []
            except Exception as chat_error:
                logger.error(f"Error setting up chat: {str(chat_error)}")
                st.session_state.chat_enabled = False
                st.session_state.chat_details = None
                st.session_state.chat_messages = []
            
            # Success message and rerun
            st.success("Analysis completed successfully!")
            st.rerun()
            
        except Exception as e:
            error_msg = f"An error occurred during analysis: {str(e)}"
            logger.error(error_msg, exc_info=True)
            st.error(error_msg)
    
    def _process_transcript_original(self, url: str, use_cache: bool = True):
        """Process transcript using the exact original logic."""
        # Use the original function directly
        from src.youtube_analysis.utils.youtube_utils import extract_video_id, get_cached_transcription
        from src.youtube_analysis.service_factory import get_service_factory
        from youtube_transcript_api import YouTubeTranscriptApi
        
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
                    
                    # First, check if we're using Phase 2 architecture
                    use_optimized = os.environ.get("USE_OPTIMIZED_ANALYSIS", "true").lower() in ("true", "1", "yes")
                    if use_optimized:
                        try:
                            # Try to use the transcript service from Phase 2 architecture
                            transcript_service = get_service_factory().get_transcript_service()
                            video_data = transcript_service.get_video_data_sync(video_id)
                            if video_data and video_data.transcript_segments:
                                logger.info("Successfully retrieved transcript using Phase 2 architecture")
                                
                                # Format transcript with timestamps
                                timestamped_transcript = ""
                                for item in video_data.transcript_segments:
                                    start = item.get('start', 0)
                                    minutes, seconds = divmod(int(start), 60)
                                    timestamp = f"[{minutes:02d}:{seconds:02d}]"
                                    text = item.get('text', '')
                                    timestamped_transcript += f"{timestamp} {text}\n"
                                
                                return timestamped_transcript, video_data.transcript_segments, None
                        except Exception as e:
                            logger.warning(f"Could not retrieve transcript using Phase 2 architecture: {str(e)}")
                            # Fall back to Phase 1 approach
                    
                    # If Phase 2 approach failed or not enabled, try Phase 1 approach
                    try:
                        # Get transcript list to reconstruct the timestamped version
                        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=["en", "de", "ta", "hi"])
                        
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
                        # If we can't get the transcript list, try to parse the cached transcript
                        logger.warning(f"Could not format cached transcript with timestamps: {str(e)}")
                        
                        # Try to extract timestamps from the cached transcript if it has them
                        if "[" in cached_transcript and "]" in cached_transcript:
                            logger.info("Using cached transcript that appears to have timestamps")
                            
                            # Try to reconstruct transcript_list from the timestamped transcript
                            transcript_list = []
                            lines = cached_transcript.strip().split('\n')
                            for line in lines:
                                # Parse lines like "[MM:SS] Text content"
                                match = re.match(r'\[(\d+):(\d+)\]\s*(.*)', line)
                                if match:
                                    minutes, seconds, text = match.groups()
                                    start_time = int(minutes) * 60 + int(seconds)
                                    transcript_list.append({
                                        'start': start_time,
                                        'duration': 5.0,  # Approximate duration
                                        'text': text
                                    })
                            
                            # If we successfully parsed some segments, return them
                            if transcript_list:
                                return cached_transcript, transcript_list, None
                        
                        # If all else fails, return the cached transcript as-is
                        logger.info("Using cached transcript as plain text fallback")
                        return cached_transcript, [{"text": cached_transcript, "start": 0.0, "duration": 0.0}], None
            
            # Fetch fresh transcript
            try:
                logger.info(f"Fetching fresh transcript for video ID: {video_id}")
                transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=["en", "de", "ta", "hi"])
                
                # Format transcript with timestamps
                timestamped_transcript = ""
                for item in transcript_list:
                    start = item.get('start', 0)
                    minutes, seconds = divmod(int(start), 60)
                    timestamp = f"[{minutes:02d}:{seconds:02d}]"
                    text = item.get('text', '')
                    timestamped_transcript += f"{timestamp} {text}\n"
                
                # Cache the plain transcript text
                if use_cache:
                    from src.youtube_analysis.utils.youtube_utils import cache_transcription
                    plain_transcript = " ".join([item.get('text', '') for item in transcript_list])
                    cache_transcription(video_id, plain_transcript)
                
                return timestamped_transcript, transcript_list, None
                
            except Exception as e:
                error_msg = f"Error fetching fresh transcript: {str(e)}"
                logger.error(error_msg)
                return None, None, error_msg
                
        except Exception as e:
            error_msg = f"Error in transcript processing: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return None, None, error_msg
    
    def _convert_transcript_list_to_text(self, transcript_list):
        """Convert transcript list to plain text."""
        if not transcript_list:
            return ""
        
        return " ".join([item.get('text', '') for item in transcript_list])
    
    def _display_analysis_results(self):
        """Display analysis results."""
        results = self.session_manager.get_analysis_results()
        if not results:
            st.error("No analysis results available")
            return
        
        display_analysis_results(results)
    
    def _display_chat_interface(self):
        """Display chat interface."""
        display_chat_interface()
    
    def _handle_chat_input(self):
        """Handle chat input processing."""
        handle_chat_input()
    
    def _reset_chat(self):
        """Reset chat state."""
        self.session_manager.reset_chat_state()
        
        # Re-initialize welcome message
        if st.session_state.chat_details and "title" in st.session_state.chat_details:
            video_title = st.session_state.chat_details.get("title", "this YouTube video")
            welcome_message = (f"Hello! I'm your AI assistant for the video \"{video_title}\". "
                             f"Ask me any questions about the content.")
            st.session_state.chat_messages = [{"role": "assistant", "content": welcome_message}]
        
        st.rerun()
    
    def _new_analysis(self):
        """Start a new analysis."""
        # Cleanup resources
        try:
            import asyncio
            from src.youtube_analysis.analysis_v2 import cleanup_analysis_resources
            asyncio.run(cleanup_analysis_resources())
            logger.info("Successfully cleaned up Phase 2 resources")
        except Exception as e:
            logger.warning(f"Error cleaning up resources: {e}")
        
        # Reset state
        self.session_manager.reset_analysis_state()
        st.rerun()
    
    def _clear_cache(self):
        """Clear cache for current video."""
        video_id = st.session_state.get("video_id")
        if video_id:
            analysis_cleared = clear_analysis_cache(video_id)
            highlights_cleared = clear_highlights_cache(video_id)
            
            if analysis_cleared or highlights_cleared:
                st.success(f"Cache cleared for video {video_id}")
                self.session_manager.reset_analysis_state()
                st.rerun()
            else:
                st.info("No cached data found for this video")
    
    def run(self):
        """Main application entry point."""
        try:
            # Check configuration
            is_valid, missing_vars = validate_config()
            if not is_valid and 'YOUTUBE_API_KEY' in missing_vars:
                st.sidebar.warning(
                    "YouTube API key is missing. The app will try to use pytube as a fallback. "
                    "See the README for setup instructions."
                )
            
            # Initialize and setup
            self.initialize()
            self.setup_sidebar()
            
            # Display main content
            self.display_main_content()
            
        except Exception as e:
            logger.error(f"Error in main app: {e}", exc_info=True)
            st.error(f"An error occurred: {e}")


def main():
    """Main function to run the web application."""
    app = StreamlitWebApp()
    app.run()


if __name__ == "__main__":
    main()