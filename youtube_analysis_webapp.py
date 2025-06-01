"""
Streamlined YouTube Analysis WebApp
Leveraging Phase 2 Architecture with Full Feature Parity.
"""
import streamlit as st
# Ensure page config is the first Streamlit command
st.set_page_config(
    page_title="Skimr Summarizer",
    page_icon=":material/movie:",
    layout="wide",
    initial_sidebar_state="expanded",
)

import os
import sys
import logging
import asyncio
from typing import List, Dict, Any, Optional, Tuple

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

# --- Core Application Imports ---
from src.youtube_analysis.config import APP_VERSION, validate_config, setup_logging
from src.youtube_analysis.utils.logging import get_logger
from src.youtube_analysis.ui import (
    StreamlitCallbacks, StreamlitSessionManager,
    display_analysis_results, display_chat_interface,
    load_css, get_skimr_logo_base64
)
from src.youtube_analysis.adapters.webapp_adapter import WebAppAdapter
from src.youtube_analysis.auth import (
    init_auth_state, display_auth_ui, get_current_user,
    logout, check_guest_usage
)
from src.youtube_analysis.stats import get_user_stats, increment_summary_count

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Configure logging
setup_logging()
logger = get_logger("webapp")


class StreamlitWebApp:
    def __init__(self):
        logger.info("Initializing StreamlitWebApp...")
        self.session_manager = StreamlitSessionManager()
        self.callbacks = StreamlitCallbacks()
        self.webapp_adapter = WebAppAdapter(self.callbacks)
        self._handle_rerun_flags()
        self._clear_corrupted_cache_on_startup()

    def _handle_rerun_flags(self):
        if self.session_manager.get_state("content_generation_pending", False):
            self.session_manager.set_state("content_generation_pending", False)
            content_type = self.session_manager.get_state("content_type_generated")
            self.session_manager.set_state("content_type_generated", None)
            logger.info(f"Performing one-time rerun after generating {content_type}")
            st.rerun()

    def _clear_corrupted_cache_on_startup(self):
        """Clear any corrupted cache entries on webapp startup."""
        try:
            # Run the cleanup asynchronously
            async def cleanup_cache():
                # Access the cache repository through the webapp adapter
                if hasattr(self.webapp_adapter, 'workflow') and hasattr(self.webapp_adapter.workflow, 'cache_repo'):
                    await self.webapp_adapter.workflow.cache_repo.clear_corrupted_cache_entries()
                    logger.info("Completed corrupted cache cleanup on startup")
            
            # Only run if we're not already in an event loop
            try:
                asyncio.run(cleanup_cache())
            except RuntimeError:
                # Event loop already running, schedule the task
                logger.info("Event loop already running, cache cleanup will happen during normal operations")
        except Exception as e:
            logger.warning(f"Could not clear corrupted cache on startup: {e}")

    def initialize_app(self):
        logger.debug("Initializing app: CSS, session, auth.")
        load_css()
        self.session_manager.initialize_all_states()
        init_auth_state()

    def display_sidebar(self):
        with st.sidebar:
            self._display_sidebar_logo()
            self._display_sidebar_auth_status()
            self._display_sidebar_settings()
            self._display_sidebar_analysis_controls()
            self._display_sidebar_phase2_info()
            self._display_sidebar_version()

    def _display_sidebar_logo(self):
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

    def _display_sidebar_auth_status(self):
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
                        self.session_manager.set_state("authenticated", False)
                        st.rerun()
            else:
                st.info("You are not logged in.")
                
                # Show guest analysis information
                from src.youtube_analysis.config import MAX_GUEST_ANALYSES
                guest_count = self.session_manager.get_state("guest_analysis_count", 0)
                remaining = max(0, MAX_GUEST_ANALYSES - guest_count)
                
                if remaining > 0:
                    st.success(f"🎁 {remaining} free analysis remaining")
                else:
                    st.warning("🚫 Free analyses used up")
                
                if st.button("Login/Sign Up", key="sidebar_login"):
                    self.session_manager.set_state("show_auth", True)
                    st.rerun()

    def _display_sidebar_settings(self):
        with st.expander("⚙️ Settings", expanded=False):
            settings = self.session_manager.get_settings()
            model = st.selectbox(
                "AI Model",
                options=["gpt-4o-mini", "gemini-2.0-flash", "gemini-2.0-flash-lite"],
                index=["gpt-4o-mini", "gemini-2.0-flash", "gemini-2.0-flash-lite"].index(settings.get("model", "gpt-4o-mini")),
                key="model_select"
            )
            temperature = st.slider(
                "Creativity Level (Temperature)",
                min_value=0.0, max_value=1.0, value=settings.get("temperature", 0.2), step=0.1,
                key="temp_slider"
            )
            use_cache = st.checkbox(
                "Use Cache (Faster Analysis)", value=settings.get("use_cache", True),
                key="cache_checkbox"
            )
            use_optimized_arch = st.checkbox(
                "Use Phase 2 Optimized Architecture", value=settings.get("use_optimized", True),
                key="optimized_arch_checkbox",
                help="Enables advanced caching, connection pooling, and concurrent processing."
            )

            updated_settings = {
                "model": model, "temperature": temperature, "use_cache": use_cache,
                "use_optimized": use_optimized_arch,
                "analysis_types": ["Summary & Classification"]
            }
            self.session_manager.update_settings(updated_settings)
            os.environ["LLM_MODEL"] = model
            os.environ["LLM_TEMPERATURE"] = str(temperature)
            os.environ["USE_OPTIMIZED_ANALYSIS"] = "true" if use_optimized_arch else "false"

    def _display_sidebar_analysis_controls(self):
        if self.session_manager.is_analysis_complete():
            st.sidebar.markdown("<hr style='margin: 1.5rem 0;'>", unsafe_allow_html=True)
            st.markdown("<h3 style='margin-bottom: 1rem;'>Analysis Options</h3>", unsafe_allow_html=True)

            if self.session_manager.is_chat_enabled():
                if st.button("🔄 Reset Chat", key="reset_chat", use_container_width=True):
                    self._handle_reset_chat_button()

            if st.button("🔄 New Analysis", key="new_analysis", use_container_width=True):
                self._handle_new_analysis_button()

            if self.session_manager.get_video_id():
                if st.button("🧹 Clear Cache", key="clear_cache", use_container_width=True):
                    self._handle_clear_cache_button()

    def _display_sidebar_phase2_info(self):
        if self.session_manager.get_settings().get("use_optimized", True):
            with st.sidebar.expander("⚡ Architecture Info", expanded=False):
                st.markdown("""
                **Active Optimizations:**
                - Service Layer Design
                - Smart Caching (TTL, Memory Limits)
                - HTTP Connection Pooling
                - Concurrent Data Fetching
                - Background Task Management
                """)
                
                # Add system status check
                try:
                    # Quick health check
                    config_valid, missing_vars = validate_config()
                    if config_valid:
                        st.success("🟢 System Status: Healthy")
                    else:
                        st.warning(f"🟡 System Status: Configuration incomplete ({len(missing_vars)} missing vars)")
                except Exception as e:
                    st.error("🔴 System Status: Issues detected")
                    logger.warning(f"System status check failed: {e}")

    def _display_sidebar_version(self):
        st.sidebar.markdown(f"<div style='text-align: center; margin-top: 2rem; opacity: 0.7;'>Skimr v{APP_VERSION}</div>",
                           unsafe_allow_html=True)

    def display_main_content(self):
        if self.session_manager.get_state("show_auth", False):
            display_auth_ui()
            return

        if not self.session_manager.is_analysis_complete():
            self._display_video_input_section()
        else:
            self._display_analysis_section()

    def _display_video_input_section(self):
        # Title and marketing text
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
            st.markdown("<h3 style='text-align: center; width: 100%;'>Paste your YouTube link</h3>", unsafe_allow_html=True)
            
            # Create columns for input and button
            input_col, button_col = st.columns([3, 1])
            
            with input_col:
                youtube_url = st.text_input(
                    "YouTube URL",
                    placeholder="https://www.youtube.com/watch?v=...",
                    label_visibility="collapsed",
                    key="youtube_url_input",
                    value=self.session_manager.get_state("current_youtube_url","")
                )
                self.session_manager.set_state("current_youtube_url", youtube_url)
            
            with button_col:
                # Button is always visible, but disabled when no URL
                analyze_button = st.button(
                    "🔍 Analyze", 
                    key="analyze_video_button", 
                    use_container_width=True, 
                    type="primary",
                    disabled=not youtube_url
                )
                
            # Show guest analysis status if not authenticated
            if not self.session_manager.get_state("authenticated"):
                from src.youtube_analysis.config import MAX_GUEST_ANALYSES
                guest_count = self.session_manager.get_state("guest_analysis_count", 0)
                remaining = max(0, MAX_GUEST_ANALYSES - guest_count)
                
                if remaining == 0:
                    st.warning("🚫 You've used your free analysis. Please log in to continue analyzing videos.")
                elif remaining == 1:
                    st.info("🎁 This is your free analysis! Sign up for unlimited access.")
            
            # Handle button click
            if analyze_button and youtube_url:
                self._handle_analyze_video_button(youtube_url)

        # Always show marketing sections (whether URL is entered or not)
        self._display_marketing_sections()

    def _display_marketing_sections(self):
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

        st.markdown("""
        <h3 style="color: #4dabf7; margin: 3rem 0 1.5rem 0; text-align: center;">Who is Skimr For?</h3>
        <div style="width: 100px; height: 3px; background: #4dabf7; margin: 0 auto 2rem auto; border-radius: 2px; opacity: 0.5;"></div>
        """, unsafe_allow_html=True)
        
        use_case_cols = st.columns(3)
        with use_case_cols[0]:
            st.markdown("""
            <div style="text-align: center;">
            <h4>🎓 Students & Researchers</h4>
            <p>Extract key insights from educational content without watching hours of lectures.</p>
            </div>
            """, unsafe_allow_html=True)
            
        with use_case_cols[1]:
            st.markdown("""
            <div style="text-align: center;">
            <h4>💼 Busy Professionals</h4>
            <p>Stay updated with industry trends by quickly digesting conference talks and webinars.</p>
            </div>
            """, unsafe_allow_html=True)
            
        with use_case_cols[2]:
            st.markdown("""
            <div style="text-align: center;">
            <h4>📱 Content Creators</h4>
            <p>Research competitors and trends efficiently. Generate social media content from video insights.</p>
            </div>
            """, unsafe_allow_html=True)

    def _display_analysis_section(self):
        logger.debug("Displaying analysis section.")
        analysis_results = self.session_manager.get_analysis_results()
        if not analysis_results:
            st.error("Analysis results are missing. Please try analyzing again.")
            if st.button("Start New Analysis"):
                self._handle_new_analysis_button()
            return

        self._display_video_player_and_chat_columns(analysis_results)
        display_analysis_results(analysis_results, self.session_manager, self._handle_generate_additional_content)
        self._display_token_usage_and_performance(analysis_results)

    def _display_video_player_and_chat_columns(self, analysis_results: Dict[str, Any]):
        st.markdown("<h2 class='sub-header'>🎬 Video & Interactive Chat</h2>", unsafe_allow_html=True)
        video_id = analysis_results.get("video_id")
        video_col, chat_col = st.columns([6, 4])

        with video_col:
            if video_id:
                st.video(f"https://www.youtube.com/watch?v={video_id}")
            else:
                st.warning("Video ID not found, cannot display player.")

        with chat_col:
            if self.session_manager.is_chat_enabled():
                display_chat_interface(
                    chat_messages=self.session_manager.get_chat_messages(),
                    on_submit=self._handle_chat_message_submission,
                    is_streaming=self.session_manager.get_state("is_chat_streaming", False),
                    streaming_response_placeholder=self.session_manager.get_state("chat_streaming_placeholder", "")
                )
            else:
                # Display a styled message when chat is not available
                st.markdown("""
                <div style="background: rgba(255, 177, 66, 0.2); border-left: 4px solid #ffb142; padding: 1.5rem; border-radius: 8px; margin-bottom: 1rem; height: 380px; display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center;">
                    <h3 style="margin-top: 0; color: #ffb142;">💬 Chat Not Available</h3>
                    <p style="color: #666; margin-bottom: 0;">Chat functionality requires video analysis to be completed successfully. If you just analyzed a video, please wait a moment for chat to initialize.</p>
                </div>
                """, unsafe_allow_html=True)

    def _display_token_usage_and_performance(self, analysis_results: Dict[str, Any]):
        # Get cumulative and breakdown token usage from session manager
        cumulative_usage = self.session_manager.get_cumulative_token_usage()
        usage_breakdown = self.session_manager.get_token_usage_breakdown()
        
        # Display overall token usage
        st.markdown("<h2 class='sub-header'>📈 Overall Token Usage</h2>", unsafe_allow_html=True)
        cols = st.columns(3)
        with cols[0]:
            st.metric("Total Tokens", f"{cumulative_usage.get('total_tokens', 0):,}")
        with cols[1]:
            st.metric("Prompt Tokens", f"{cumulative_usage.get('prompt_tokens', 0):,}")
        with cols[2]:
            st.metric("Completion Tokens", f"{cumulative_usage.get('completion_tokens', 0):,}")
        
        # Display detailed breakdown in an expander
        with st.expander("🔍 Token Usage Breakdown", expanded=False):
            # Initial Analysis
            if usage_breakdown.get("initial_analysis"):
                st.markdown("### 📊 Initial Analysis")
                initial = usage_breakdown["initial_analysis"]
                cols = st.columns(3)
                with cols[0]:
                    st.metric("Total", f"{initial.get('total_tokens', 0):,}")
                with cols[1]:
                    st.metric("Prompt", f"{initial.get('prompt_tokens', 0):,}")
                with cols[2]:
                    st.metric("Completion", f"{initial.get('completion_tokens', 0):,}")
            
            # Additional Content Generation
            additional_content = usage_breakdown.get("additional_content", {})
            if additional_content:
                st.markdown("### 🎯 Additional Content Generation")
                
                # Map task names to display names
                display_names = {
                    "analyze_and_plan_content": "Action Plan",
                    "write_blog_post": "Blog Post",
                    "write_linkedin_post": "LinkedIn Post",
                    "write_tweet": "X Tweet"
                }
                
                for task_name, usage in additional_content.items():
                    display_name = display_names.get(task_name, task_name)
                    st.markdown(f"**{display_name}:**")
                    cols = st.columns(3)
                    with cols[0]:
                        st.metric("Total", f"{usage.get('total_tokens', 0):,}")
                    with cols[1]:
                        st.metric("Prompt", f"{usage.get('prompt_tokens', 0):,}")
                    with cols[2]:
                        st.metric("Completion", f"{usage.get('completion_tokens', 0):,}")
            
            # Chat Usage
            chat_usage = usage_breakdown.get("chat", {})
            if chat_usage and chat_usage.get("total_tokens", 0) > 0:
                st.markdown("### 💬 Chat Interactions")
                cols = st.columns(4)
                with cols[0]:
                    st.metric("Total Tokens", f"{chat_usage.get('total_tokens', 0):,}")
                with cols[1]:
                    st.metric("Prompt Tokens", f"{chat_usage.get('prompt_tokens', 0):,}")
                with cols[2]:
                    st.metric("Completion Tokens", f"{chat_usage.get('completion_tokens', 0):,}")
                with cols[3]:
                    st.metric("Messages", f"{chat_usage.get('message_count', 0):,}")
            
            # Show usage summary
            if cumulative_usage.get('total_tokens', 0) > 0:
                st.markdown("---")
                st.markdown("### 📈 Usage Summary")
                
                # Calculate cost estimation (rough estimate)
                total_tokens = cumulative_usage.get('total_tokens', 0)
                
                # Rough cost estimates for popular models (per 1K tokens)
                cost_estimates = {
                    "gpt-4o-mini": 0.00015,  # $0.15 per 1M tokens
                    "gemini-2.0-flash": 0.0001,  # Estimated cost
                    "gemini-2.0-flash-lite": 0.00005,  # Estimated cost
                }
                
                current_model = self.session_manager.get_settings().get("model", "gpt-4o-mini")
                cost_per_1k = cost_estimates.get(current_model, 0.0001)
                estimated_cost = (total_tokens / 1000) * cost_per_1k
                
                col1, col2 = st.columns(2)
                with col1:
                    st.info(f"**Model:** {current_model}")
                with col2:
                    st.info(f"**Estimated Cost:** ${estimated_cost:.4f}")

        # Display performance stats if available
        perf_stats = analysis_results.get("performance_stats")
        if perf_stats and self.session_manager.get_settings().get("use_optimized", True):
            from src.youtube_analysis.ui.components import display_performance_stats
            display_performance_stats(perf_stats)

    # --- Event Handlers ---
    def _handle_analyze_video_button(self, youtube_url: str):
        logger.info(f"Analyze button clicked for URL: {youtube_url}")
        if not self.webapp_adapter.validate_youtube_url(youtube_url):
            st.error("❌ Invalid YouTube URL. Please check the URL and try again.")
            return

        if not self.session_manager.get_state("authenticated") and not check_guest_usage():
            st.warning("Guest analysis limit reached. Please log in.")
            self.session_manager.set_state("show_auth", True)
            st.rerun()
            return

        self.session_manager.reset_for_new_analysis()
        self.session_manager.set_state("current_youtube_url", youtube_url)

        with st.spinner("🧙‍♂️ Skimr is working its magic... Fetching transcript and analyzing..."):
            try:
                results, error = asyncio.run(
                    self.webapp_adapter.analyze_video(youtube_url, self.session_manager.get_settings())
                )

                if error:
                    # Show more specific error message based on error type
                    if "Invalid YouTube URL" in error:
                        st.error("❌ Invalid YouTube URL. Please check the URL and try again.")
                    elif "No transcript available" in error:
                        st.error("❌ This video doesn't have captions/transcripts available. Please try a different video.")
                    elif "Analysis execution failed" in error:
                        st.error("❌ Analysis failed. This might be due to video content or processing issues. Please try again.")
                    elif "Connection" in error or "timeout" in error.lower():
                        st.error("❌ Connection issue. Please check your internet connection and try again.")
                    elif "rate limit" in error.lower() or "quota" in error.lower():
                        st.error("❌ Service temporarily unavailable due to high demand. Please try again in a few minutes.")
                    else:
                        st.error(f"❌ Analysis failed: {error}")
                    
                    logger.error(f"Analysis error for {youtube_url}: {error}")
                    self.session_manager.set_state("analysis_complete", False)
                    
                    # Show troubleshooting tips
                    with st.expander("🔧 Troubleshooting Tips"):
                        st.markdown("""
                        **Common solutions:**
                        - Ensure the YouTube video is public and has captions/transcripts
                        - Try refreshing the page and analyzing again
                        - Check if the video URL is correct and complete
                        - Try a different video if the issue persists
                        
                        **If problems continue:**
                        - The video might not have automatic captions enabled
                        - The video content might be too short or have limited speech
                        - There might be temporary service issues
                        """)
                elif results:
                    logger.info(f"Analysis successful for {youtube_url}.")
                    self.session_manager.set_analysis_results(results)
                    self.session_manager.set_state("analysis_complete", True)
                    self.session_manager.set_video_id(results.get("video_id"))

                    # Handle chat setup from results with caching
                    if results.get("chat_details") and results["chat_details"].get("agent"):
                        video_title = results.get("video_info", {}).get("title", "this video")
                        video_id = results.get("video_id")  # Extract video_id from results
                        
                        # Use the new cached chat initialization
                        chat_initialized = self.session_manager.initialize_chat_with_cache(
                            self.webapp_adapter, 
                            video_id, 
                            youtube_url, 
                            video_title, 
                            results["chat_details"]
                        )
                        
                        if not chat_initialized:
                            logger.warning("Failed to initialize chat with cache, falling back to manual setup")
                            self.session_manager.set_chat_details(results["chat_details"])
                            self.session_manager.set_state("chat_enabled", True)
                            
                            # Initialize welcome message only if chat_messages is empty
                            current_messages = self.session_manager.get_chat_messages()
                            if not current_messages:
                                welcome = f"Hello! I'm your AI assistant for the video \"{video_title}\". Ask me any questions about the content, and I'll do my best to answer based on the transcript. I'll include timestamps in my answers to help you locate information in the video."
                                self.session_manager.initialize_chat_messages([{"role": "assistant", "content": welcome}])
                    else:
                        logger.warning("Chat details not found in analysis results.")
                        self.session_manager.set_state("chat_enabled", False)

                    # Increment summary count if not cached
                    if not results.get("cached", False):
                        if self.session_manager.get_state("authenticated"):
                            # Increment summary count for authenticated users
                            user = get_current_user()
                            if user and hasattr(user, 'id'):
                               increment_summary_count(user.id)
                               logger.info(f"Incremented summary count for user {user.id}")
                        else:
                            # Increment guest analysis count for guest users
                            current_guest_count = self.session_manager.get_state("guest_analysis_count", 0)
                            self.session_manager.set_state("guest_analysis_count", current_guest_count + 1)
                            logger.info(f"Incremented guest analysis count to {current_guest_count + 1}")
                else:
                    st.error("Analysis completed but returned no results.")
                    logger.error(f"No results from analysis for {youtube_url}")
                    self.session_manager.set_state("analysis_complete", False)

            except Exception as e:
                logger.error(f"Exception during video analysis: {e}", exc_info=True)
                st.error(f"An unexpected error occurred: {str(e)}")
                self.session_manager.set_state("analysis_complete", False)
        st.rerun()

    def _handle_generate_additional_content(self, content_type_key: str):
        logger.info(f"Generating additional content: {content_type_key}")

        analysis_results = self.session_manager.get_analysis_results()
        if not analysis_results:
            st.error("Cannot generate content: Initial analysis results not found.")
            return

        # Debug: Log available keys
        logger.info(f"Analysis results keys: {list(analysis_results.keys())}")
        
        youtube_url = analysis_results.get("youtube_url")
        video_id = analysis_results.get("video_id")
        transcript_text = analysis_results.get("transcript")
        
        # Try alternative transcript sources if main one is empty
        if not transcript_text:
            # Try transcript_segments
            transcript_segments = analysis_results.get("transcript_segments", [])
            if transcript_segments:
                # Reconstruct transcript from segments
                transcript_text = " ".join([segment.get("text", "") for segment in transcript_segments if segment.get("text")])
                logger.info(f"Reconstructed transcript from {len(transcript_segments)} segments")
            
            # Try video_info transcript
            if not transcript_text:
                video_info = analysis_results.get("video_info", {})
                if isinstance(video_info, dict):
                    transcript_text = video_info.get("transcript")
                    logger.info(f"Found transcript in video_info: {transcript_text is not None}")

        # More detailed debugging
        logger.info(f"Content generation debug - URL: {youtube_url is not None}, Video ID: {video_id is not None}, Transcript: {transcript_text is not None}")
        if transcript_text:
            logger.info(f"Transcript length: {len(transcript_text)}")
        else:
            logger.warning("No transcript found in any location")
        
        if not all([youtube_url, video_id, transcript_text]):
            # Show detailed error with what's missing
            missing_fields = []
            if not youtube_url:
                missing_fields.append("youtube_url")
            if not video_id:
                missing_fields.append("video_id")
            if not transcript_text:
                missing_fields.append("transcript")
            
            error_msg = f"Cannot generate content: Missing {', '.join(missing_fields)} from initial analysis."
            st.error(error_msg)
            return

        with st.spinner(f"Generating {content_type_key}... This may take a moment."):
            try:
                content, error, token_usage = asyncio.run(
                    self.webapp_adapter.generate_additional_content(
                        youtube_url, video_id, transcript_text, content_type_key, self.session_manager.get_settings()
                    )
                )
                if error:
                    # Show more specific error message based on error type
                    if "Connection" in error or "timeout" in error.lower():
                        st.error(f"❌ Connection issue while generating {content_type_key}. Please try again.")
                    elif "rate limit" in error.lower() or "quota" in error.lower():
                        st.error(f"❌ Service temporarily unavailable. Please try generating {content_type_key} again in a few minutes.")
                    elif "model" in error.lower() or "token" in error.lower():
                        st.error(f"❌ AI model issue while generating {content_type_key}. Please try again.")
                    else:
                        st.error(f"❌ Failed to generate {content_type_key}: {error}")
                    
                    # Show retry suggestion
                    st.info("💡 You can try generating this content again by clicking the button above.")
                elif content:
                    st.success(f"{content_type_key} generated successfully! View it in the tabs.")
                    content_types_map_to_task_key = {
                        "Action Plan": "analyze_and_plan_content",
                        "Blog Post": "write_blog_post",
                        "LinkedIn Post": "write_linkedin_post",
                        "X Tweet": "write_tweet"
                    }
                    task_key = content_types_map_to_task_key.get(content_type_key, content_type_key)

                    self.session_manager.update_task_output(task_key, content)
                    
                    # Track token usage if available
                    if token_usage and isinstance(token_usage, dict):
                        self.session_manager.add_token_usage("additional_content", token_usage, task_key)
                        logger.info(f"Tracked token usage for {content_type_key}: {token_usage}")
                    
                    self.session_manager.set_state("content_generation_pending", True)
                    self.session_manager.set_state("content_type_generated", content_type_key)
                else:
                    st.warning(f"No content generated for {content_type_key}, but no error reported.")
            except Exception as e:
                logger.error(f"Exception generating {content_type_key}: {e}", exc_info=True)
                st.error(f"Error generating {content_type_key}: {str(e)}")
        st.rerun()

    def _handle_chat_message_submission(self, user_input: str):
        logger.debug(f"User submitted chat: {user_input}")
        if not user_input.strip():
            return

        self.session_manager.add_chat_message({"role": "user", "content": user_input})
        
        # Auto-save chat messages to cache
        video_id = self.session_manager.get_video_id()
        if video_id:
            self.session_manager.auto_save_chat_messages(self.webapp_adapter, video_id)
        
        self.session_manager.set_state("is_chat_streaming", True)
        self.session_manager.set_state("current_chat_question", user_input)
        st.rerun()

    def _process_chat_ai_response(self):
        if not self.session_manager.get_state("is_chat_streaming", False):
            return

        logger.info("Processing AI chat response...")
        video_id = self.session_manager.get_video_id()
        chat_history = self.session_manager.get_chat_messages()[:-1]
        current_question = self.session_manager.get_state("current_chat_question")

        if not all([video_id, current_question]):
            logger.error("Missing video_id or current_question for chat.")
            self.session_manager.add_chat_message({"role": "assistant", "content": "Sorry, I can't process that right now."})
            self.session_manager.set_state("is_chat_streaming", False)
            return

        full_response = ""
        chat_token_usage = None
        try:
            async def stream_to_ui():
                nonlocal full_response, chat_token_usage
                message_placeholder = self.session_manager.get_state("chat_streaming_placeholder_ref")
                
                if message_placeholder is None:
                    # If no placeholder is set, just get the full response
                    async for chunk, token_usage in self.webapp_adapter.get_chat_response_stream(
                        video_id, chat_history, current_question, self.session_manager.get_settings()
                    ):
                        if chunk:
                            full_response += chunk
                        if token_usage:
                            chat_token_usage = token_usage
                else:
                    # Stream to the placeholder
                    async for chunk, token_usage in self.webapp_adapter.get_chat_response_stream(
                        video_id, chat_history, current_question, self.session_manager.get_settings()
                    ):
                        if chunk:
                            full_response += chunk
                            try:
                                message_placeholder.markdown(full_response + "▌")
                            except Exception as placeholder_error:
                                logger.warning(f"Could not update placeholder: {placeholder_error}")
                        if token_usage:
                            chat_token_usage = token_usage
                    
                    # Final update without cursor
                    try:
                        message_placeholder.markdown(full_response)
                    except Exception as placeholder_error:
                        logger.warning(f"Could not do final placeholder update: {placeholder_error}")

            asyncio.run(stream_to_ui())

        except Exception as e:
            logger.error(f"Error streaming chat response: {e}", exc_info=True)
            full_response = "Sorry, an error occurred while generating my response."
        finally:
            self.session_manager.add_chat_message({"role": "assistant", "content": full_response})
            
            # Auto-save chat messages to cache
            video_id = self.session_manager.get_video_id()
            if video_id:
                self.session_manager.auto_save_chat_messages(self.webapp_adapter, video_id)
            
            # Track chat token usage if available
            if chat_token_usage and isinstance(chat_token_usage, dict):
                self.session_manager.add_token_usage("chat", chat_token_usage)
                logger.info(f"Tracked chat token usage: {chat_token_usage}")
            
            self.session_manager.set_state("is_chat_streaming", False)
            self.session_manager.set_state("current_chat_question", None)
            # Clear the placeholder reference
            self.session_manager.set_state("chat_streaming_placeholder_ref", None)
            st.rerun()

    def _handle_reset_chat_button(self):
        logger.info("Reset chat button clicked.")
        
        # Clear cached chat session
        video_id = self.session_manager.get_video_id()
        if video_id:
            self.session_manager.clear_cached_chat_session(self.webapp_adapter, video_id)
        
        # Reset session state
        self.session_manager.reset_chat_state()
        
        # Reinitialize with welcome message
        analysis_results = self.session_manager.get_analysis_results()
        if analysis_results and analysis_results.get("chat_details"):
            video_title = analysis_results.get("video_info", {}).get("title", "this video")
            youtube_url = analysis_results.get("youtube_url", "")
            
            # Use cached initialization to create new session with welcome message
            if video_id and youtube_url:
                chat_initialized = self.session_manager.initialize_chat_with_cache(
                    self.webapp_adapter, 
                    video_id, 
                    youtube_url, 
                    video_title, 
                    analysis_results["chat_details"]
                )
                
                if not chat_initialized:
                    # Fallback to manual welcome message
                    welcome = f"Hello! I'm your AI assistant for the video \"{video_title}\". Ask me any questions about the content, and I'll do my best to answer based on the transcript. I'll include timestamps in my answers to help you locate information in the video."
                    self.session_manager.initialize_chat_messages([{"role": "assistant", "content": welcome}])
        st.rerun()

    def _handle_new_analysis_button(self):
        logger.info("New analysis button clicked.")
        asyncio.run(self.webapp_adapter.cleanup_resources())
        self.session_manager.reset_for_new_analysis()
        self.session_manager.set_state("current_youtube_url", "")
        st.rerun()

    def _handle_clear_cache_button(self):
        video_id = self.session_manager.get_video_id()
        logger.info(f"Clear cache button clicked for video_id: {video_id}")
        if video_id:
            # Clear all cache including chat sessions
            self.webapp_adapter.clear_cache_for_video(video_id)
            st.success(f"Cache (including chat history) cleared for video {video_id}.")
            self.session_manager.reset_for_new_analysis()
            self.session_manager.set_state("current_youtube_url", "")
            st.rerun()
        else:
            st.warning("No video ID found to clear cache for.")

    def run(self):
        self.initialize_app()
        self.display_sidebar()
        self.display_main_content()

        # Handle chat streaming if needed
        if self.session_manager.get_state("is_chat_streaming", False) and \
           not st.session_state.get("chat_input"):
            self._process_chat_ai_response()


def main():
    # Configuration Check
    is_config_valid, missing_vars = validate_config()
    if not is_config_valid:
        logger.warning(f"Configuration incomplete. Missing: {', '.join(missing_vars)}")

    app = StreamlitWebApp()
    app.run()

if __name__ == "__main__":
    main()