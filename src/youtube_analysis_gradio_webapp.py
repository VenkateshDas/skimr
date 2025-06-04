"""
Gradio-based YouTube Analysis WebApp
Migration from Streamlit to Gradio with Full Feature Parity.
"""

import gradio as gr
import os
import sys
import logging
import asyncio
from typing import List, Dict, Any, Optional, Tuple
import base64
from pathlib import Path
import warnings

# Suppress Streamlit warnings when running Gradio
warnings.filterwarnings("ignore", message=".*ScriptRunContext.*")
warnings.filterwarnings("ignore", message=".*Session state.*")
warnings.filterwarnings("ignore", category=UserWarning, module="streamlit.*")

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

# --- Core Application Imports ---
from youtube_analysis.core.config import APP_VERSION, validate_config, setup_logging, CHAT_WELCOME_TEMPLATE, config
from youtube_analysis.utils.logging import get_logger
from youtube_analysis.ui.gradio_session_manager import GradioSessionManager
from youtube_analysis.ui.gradio_callbacks import GradioCallbacks
from youtube_analysis.adapters.webapp_adapter import WebAppAdapter
from youtube_analysis.services.auth_service import (
    init_auth_state, get_current_user, logout, check_guest_usage
)
from youtube_analysis.services.user_stats_service import get_user_stats, increment_summary_count

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Configure logging
setup_logging()
logger = get_logger("gradio_webapp")


def get_logo_base64() -> Optional[str]:
    """Returns the base64 encoded Skimr logo for embedding in HTML."""
    logo_path = Path("src/youtube_analysis/logo/logo_v2.png")
    
    if not logo_path.exists():
        return None
    
    try:
        with open(logo_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except Exception:
        return None


def create_header():
    """Create the header section with logo and title."""
    logo_base64 = get_logo_base64()
    
    header_html = """
    <div style="background: #ffffff; 
                border-bottom: 1px solid #e5e7eb; 
                padding: 2rem 0; 
                margin-bottom: 2rem;">
        
        <div style="max-width: 1200px; margin: 0 auto; text-align: center; padding: 0 2rem;">
    """
    
    if logo_base64:
        header_html += f'''
            <div style="display: flex; align-items: center; justify-content: center; margin-bottom: 1rem;">
                <img src="data:image/png;base64,{logo_base64}" 
                     width="120" 
                     alt="Skimr Logo" 
                     style="margin-right: 1rem;">
                <div style="text-align: left;">
                    <h1 style="color: #111827; 
                               margin: 0; 
                               font-family: 'Inter', system-ui, -apple-system, sans-serif;
                               font-size: 2.5rem; 
                               font-weight: 800; 
                               letter-spacing: -0.025em;">
                        SKIMR
                    </h1>
                    <p style="color: #6b7280; 
                              margin: 0; 
                              font-family: 'Inter', system-ui, -apple-system, sans-serif;
                              font-size: 1.1rem; 
                              font-weight: 400;">
                        Skim through Youtube. Know what matters fast.
                    </p>
                </div>
            </div>
        '''
    else:
        header_html += """
            <h1 style="color: #111827; 
                       margin: 0 0 0.5rem 0; 
                       font-family: 'Inter', system-ui, -apple-system, sans-serif;
                       font-size: 2.5rem; 
                       font-weight: 800; 
                       letter-spacing: -0.025em;">
                SKIMR
            </h1>
            <p style="color: #6b7280; 
                      margin: 0; 
                      font-family: 'Inter', system-ui, -apple-system, sans-serif;
                      font-size: 1.1rem; 
                      font-weight: 400;">
                Skim through Youtube. Know what matters fast.
            </p>
        """
    
    header_html += """
        </div>
    </div>
    """
    
    return gr.HTML(header_html)


def create_sidebar():
    """Create the sidebar with settings, auth, and controls."""
    with gr.Column(scale=1, min_width=300) as sidebar:
        # Sidebar header
        gr.HTML("""
        <div style="background: #f8f9fa; 
                    border: 1px solid #e9ecef;
                    padding: 1rem; 
                    border-radius: 8px; 
                    text-align: center; 
                    margin-bottom: 1.5rem;">
            <h3 style="color: #495057; 
                       margin: 0; 
                       font-family: 'Inter', system-ui, -apple-system, sans-serif;
                       font-size: 1.1rem; 
                       font-weight: 600;">
                Control Panel
            </h3>
        </div>
        """)
        
        # User Account Section
        with gr.Group():
            gr.HTML("""
            <div style="background: #f8f9fa; 
                        border-left: 4px solid #3b82f6;
                        padding: 0.75rem; 
                        border-radius: 6px; 
                        margin-bottom: 1rem;">
                <h4 style="color: #374151; 
                           margin: 0; 
                           font-family: 'Inter', system-ui, -apple-system, sans-serif;
                           font-size: 0.9rem; 
                           font-weight: 600;
                           display: flex;
                           align-items: center;">
                    <span style="margin-right: 0.5rem;">👤</span> Account
                </h4>
            </div>
            """)
            
            auth_status = gr.Markdown("You are not logged in.", elem_classes=["auth-status"])
            
            # Authentication form (initially hidden)
            with gr.Column(visible=False) as auth_form:
                with gr.Tabs():
                    with gr.Tab("Login"):
                        login_email = gr.Textbox(label="Email", placeholder="your@email.com", scale=1)
                        login_password = gr.Textbox(label="Password", type="password", scale=1)
                        login_button = gr.Button("Login", variant="primary", size="sm")
                        login_message = gr.Markdown("")
                    
                    with gr.Tab("Sign Up"):
                        signup_email = gr.Textbox(label="Email", placeholder="your@email.com", scale=1)
                        signup_password = gr.Textbox(label="Password", type="password", scale=1)
                        signup_confirm = gr.Textbox(label="Confirm Password", type="password", scale=1)
                        signup_button = gr.Button("Sign Up", variant="primary", size="sm")
                        signup_message = gr.Markdown("")
            
            # Control buttons
            with gr.Row():
                auth_button = gr.Button("Login/Sign Up", size="sm", scale=1)
                logout_button = gr.Button("Logout", visible=False, size="sm", scale=1)
                cancel_auth_button = gr.Button("Cancel", visible=False, size="sm", scale=1)
            
            user_stats = gr.Markdown("")
        
        # Settings Section
        with gr.Group():
            gr.HTML("""
            <div style="background: #f8f9fa; 
                        border-left: 4px solid #10b981;
                        padding: 0.75rem; 
                        border-radius: 6px; 
                        margin-bottom: 1rem;">
                <h4 style="color: #374151; 
                           margin: 0; 
                           font-family: 'Inter', system-ui, -apple-system, sans-serif;
                           font-size: 0.9rem; 
                           font-weight: 600;
                           display: flex;
                           align-items: center;">
                    <span style="margin-right: 0.5rem;">⚙️</span> Settings
                </h4>
            </div>
            """)
            
            model_dropdown = gr.Dropdown(
                choices=config.llm.available_models,
                value=config.llm.default_model,
                label="AI Model",
                scale=1
            )
            
            transcription_dropdown = gr.Dropdown(
                choices=[("OpenAI Whisper", "openai"), ("Groq Whisper", "groq")],
                value="openai",
                label="Transcription Model",
                scale=1
            )
            
            temperature_slider = gr.Slider(
                minimum=config.ui.temperature_min,
                maximum=config.ui.temperature_max,
                value=config.llm.default_temperature,
                step=config.ui.temperature_step,
                label="Creativity Level"
            )
            
            use_cache_checkbox = gr.Checkbox(
                label="Use Cache (Faster)",
                value=config.ui.default_use_cache
            )
            
            # Subtitle translation settings
            gr.Markdown("**Subtitle Translation**", elem_classes=["settings-subsection"])
            
            from youtube_analysis.utils.language_utils import get_supported_languages
            supported_languages = get_supported_languages()
            language_options = [f"{name} ({code})" for code, name in supported_languages.items()]
            
            subtitle_language = gr.Dropdown(
                choices=language_options,
                value="English (en)",
                label="Target Language",
                scale=1
            )
        
        # Analysis Controls Section
        with gr.Group():
            gr.HTML("""
            <div style="background: #f8f9fa; 
                        border-left: 4px solid #f59e0b;
                        padding: 0.75rem; 
                        border-radius: 6px; 
                        margin-bottom: 1rem;">
                <h4 style="color: #374151; 
                           margin: 0; 
                           font-family: 'Inter', system-ui, -apple-system, sans-serif;
                           font-size: 0.9rem; 
                           font-weight: 600;
                           display: flex;
                           align-items: center;">
                    <span style="margin-right: 0.5rem;">🔄</span> Analysis Controls
                </h4>
            </div>
            """)
            
            new_analysis_btn = gr.Button("New Analysis", size="sm", scale=1)
            clear_cache_btn = gr.Button("Clear Cache", size="sm", scale=1)
        
        # Token Usage Section
        with gr.Group():
            gr.HTML("""
            <div style="background: #f8f9fa; 
                        border-left: 4px solid #8b5cf6;
                        padding: 0.75rem; 
                        border-radius: 6px; 
                        margin-bottom: 1rem;">
                <h4 style="color: #374151; 
                           margin: 0; 
                           font-family: 'Inter', system-ui, -apple-system, sans-serif;
                           font-size: 0.9rem; 
                           font-weight: 600;
                           display: flex;
                           align-items: center;">
                    <span style="margin-right: 0.5rem;">📈</span> Usage Stats
                </h4>
            </div>
            """)
            
            with gr.Row():
                total_tokens = gr.Number(label="Total", value=0, interactive=False, scale=1)
                estimated_cost = gr.Textbox(label="Cost", value="$0.00", interactive=False, scale=1)
            
            model_info = gr.Markdown("**Model:** Not selected", elem_classes=["model-info"])
            usage_breakdown = gr.Markdown("No usage data available yet.", elem_classes=["usage-breakdown"])
            
            # Hidden detailed stats
            prompt_tokens = gr.Number(label="Prompt Tokens", value=0, interactive=False, visible=False)
            completion_tokens = gr.Number(label="Completion Tokens", value=0, interactive=False, visible=False)
            cost_source = gr.Markdown("**Cost Source:** static", visible=False)
    
    return (sidebar, auth_status, auth_form, login_email, login_password, login_button, 
            login_message, signup_email, signup_password, signup_confirm, 
            signup_button, signup_message, auth_button, logout_button, 
            cancel_auth_button, user_stats, model_dropdown, transcription_dropdown, 
            temperature_slider, use_cache_checkbox, subtitle_language, new_analysis_btn, 
            clear_cache_btn, total_tokens, prompt_tokens, completion_tokens, 
            model_info, estimated_cost, cost_source, usage_breakdown)


def create_main_content():
    """Create the main content area with improved layout."""
    with gr.Column(scale=3) as main_content:
        # Video input section with clean styling
        with gr.Column(visible=True) as video_input_section:
            gr.HTML("""
            <div style="background: #ffffff; 
                        border: 1px solid #e5e7eb;
                        padding: 2rem; 
                        border-radius: 12px; 
                        margin-bottom: 2rem;
                        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);">
                <h2 style="color: #111827; 
                           margin: 0 0 1.5rem 0; 
                           text-align: center; 
                           font-family: 'Inter', system-ui, -apple-system, sans-serif;
                           font-size: 1.5rem;
                           font-weight: 600;">
                    🎯 Paste your YouTube link
                </h2>
                
                <p style="color: #6b7280; 
                          text-align: center; 
                          margin: 0 0 1.5rem 0;
                          font-family: 'Inter', system-ui, -apple-system, sans-serif;
                          font-size: 1rem;">
                    Enter a YouTube URL to get started with AI-powered analysis
                </p>
            </div>
            """)
            
            with gr.Group():
                with gr.Row():
                    youtube_url = gr.Textbox(
                        placeholder="https://www.youtube.com/watch?v=...",
                        label="",
                        show_label=False,
                        scale=4,
                        elem_classes=["url-input"]
                    )
                    analyze_btn = gr.Button(
                        "Analyze", 
                        variant="primary",
                        interactive=False,
                        scale=1,
                        size="lg",
                        elem_classes=["analyze-btn"]
                    )
            
            # Status and progress with better styling
            status_display = gr.Markdown("", elem_classes=["status-display"])
            progress_bar = gr.Slider(
                minimum=0, maximum=100, value=0, 
                label="Analysis Progress", 
                visible=False, interactive=False
            )
            
            # Marketing sections with improved layout
            create_marketing_sections()
        
        # Analysis results section with clean design
        with gr.Column(visible=False) as analysis_results_section:
            # Video and Chat - Side by side with better proportions
            with gr.Row(equal_height=True):
                # Video section
                with gr.Column(scale=3):
                    gr.HTML("""
                    <div style="background: #ffffff; 
                                border: 1px solid #e5e7eb;
                                padding: 1rem; 
                                border-radius: 8px; 
                                margin-bottom: 1rem;">
                        <h3 style="color: #111827; 
                                   margin: 0; 
                                   text-align: center;
                                   font-family: 'Inter', system-ui, -apple-system, sans-serif;
                                   font-size: 1.1rem;
                                   font-weight: 600;">
                            📺 Video Player
                        </h3>
                    </div>
                    """)
                    video_player = gr.HTML("", show_label=False, elem_classes=["video-player"])
                    video_info = gr.Markdown("", elem_classes=["video-info"])
                    video_subtitles_status = gr.Markdown("", elem_classes=["video-status"])
                
                # Chat section with clean design
                with gr.Column(scale=2):
                    gr.HTML("""
                    <div style="background: #ffffff; 
                                border: 1px solid #e5e7eb;
                                padding: 1rem; 
                                border-radius: 8px; 
                                margin-bottom: 1rem;">
                        <h3 style="color: #111827; 
                                   margin: 0; 
                                   text-align: center;
                                   font-family: 'Inter', system-ui, -apple-system, sans-serif;
                                   font-size: 1.1rem;
                                   font-weight: 600;">
                            💬 AI Chat
                        </h3>
                    </div>
                    """)
                    
                    chatbot = gr.Chatbot(
                        height=450,
                        show_label=False,
                        avatar_images=("👤", "🤖"),
                        type="messages",
                        elem_classes=["modern-chatbot"]
                    )
                    
                    with gr.Group():
                        chat_input = gr.Textbox(
                            placeholder="Ask anything about this video...",
                            label="",
                            show_label=False,
                            interactive=True,
                            scale=4,
                            elem_classes=["chat-input"]
                        )
                        with gr.Row():
                            chat_submit = gr.Button("Send", variant="primary", scale=2, size="sm")
                            chat_reset = gr.Button("Reset", scale=1, size="sm")
            
            # Analysis results with clean tabs
            gr.HTML("""
            <div style="background: #ffffff; 
                        border: 1px solid #e5e7eb;
                        padding: 1.5rem; 
                        border-radius: 8px; 
                        margin: 2rem 0 1rem 0;
                        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);">
                <h3 style="color: #111827; 
                           margin: 0; 
                           text-align: center;
                           font-family: 'Inter', system-ui, -apple-system, sans-serif;
                           font-size: 1.25rem;
                           font-weight: 600;">
                    📊 Analysis Results
                </h3>
            </div>
            """)
            
            with gr.Tabs() as results_tabs:
                with gr.Tab("📊 Summary", elem_classes=["modern-tab"]):
                    summary_content = gr.Markdown("", elem_classes=["content-display"])
                    
                with gr.Tab("📋 Action Plan", elem_classes=["modern-tab"]):
                    action_plan_content = gr.Markdown("", elem_classes=["content-display"])
                    with gr.Group():
                        action_plan_instruction = gr.Textbox(
                            placeholder="Add custom instructions for regenerating this Action Plan",
                            label="Custom Instructions",
                            lines=2
                        )
                        action_plan_generate = gr.Button("Generate Action Plan", variant="secondary")
                        
                with gr.Tab("📝 Blog Post", elem_classes=["modern-tab"]):
                    blog_content = gr.Markdown("", elem_classes=["content-display"])
                    with gr.Group():
                        blog_instruction = gr.Textbox(
                            placeholder="Add custom instructions for regenerating this Blog Post",
                            label="Custom Instructions",
                            lines=2
                        )
                        blog_generate = gr.Button("Generate Blog Post", variant="secondary")
                        
                with gr.Tab("💼 LinkedIn Post", elem_classes=["modern-tab"]):
                    linkedin_content = gr.Markdown("", elem_classes=["content-display"])
                    with gr.Group():
                        linkedin_instruction = gr.Textbox(
                            placeholder="Add custom instructions for regenerating this LinkedIn Post",
                            label="Custom Instructions",
                            lines=2
                        )
                        linkedin_generate = gr.Button("Generate LinkedIn Post", variant="secondary")
                        
                with gr.Tab("🐦 X Tweet", elem_classes=["modern-tab"]):
                    tweet_content = gr.Markdown("", elem_classes=["content-display"])
                    with gr.Group():
                        tweet_instruction = gr.Textbox(
                            placeholder="Add custom instructions for regenerating this X Tweet",
                            label="Custom Instructions",
                            lines=2
                        )
                        tweet_generate = gr.Button("Generate X Tweet", variant="secondary")
                        
                with gr.Tab("📜 Transcript", elem_classes=["modern-tab"]):
                    (show_timestamps, translate_btn, apply_subtitles_btn, translation_status,
                     transcript_display, download_srt_btn, download_vtt_btn, 
                     download_srt_file, download_vtt_file) = create_transcript_tab()
    
    return (main_content, video_input_section, analysis_results_section, youtube_url, analyze_btn, 
            status_display, progress_bar, video_player, video_info, video_subtitles_status,
            chatbot, chat_input, chat_submit, chat_reset, summary_content, action_plan_content, 
            blog_content, linkedin_content, tweet_content, action_plan_instruction,
            blog_instruction, linkedin_instruction, tweet_instruction, action_plan_generate,
            blog_generate, linkedin_generate, tweet_generate, show_timestamps, translate_btn, 
            apply_subtitles_btn, translation_status, transcript_display, download_srt_btn, 
            download_vtt_btn, download_srt_file, download_vtt_file)


def create_marketing_sections():
    """Create the marketing sections with clean, professional styling."""
    gr.HTML("""
    <div style="display: grid; 
                grid-template-columns: 1fr 1fr; 
                gap: 2rem; 
                margin: 3rem 0;">
        
        <div style="background: #ffffff; 
                    border: 1px solid #e5e7eb;
                    padding: 2rem; 
                    border-radius: 12px; 
                    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);">
            <h3 style="color: #111827; 
                       margin: 0 0 1.5rem 0; 
                       font-family: 'Inter', system-ui, -apple-system, sans-serif;
                       font-size: 1.25rem;
                       font-weight: 600;">
                🎯 How Skimr Works
            </h3>
            <ul style="color: #374151; 
                       line-height: 1.6; 
                       margin: 0; 
                       padding-left: 1.25rem;
                       font-family: 'Inter', system-ui, -apple-system, sans-serif;">
                <li><strong>Skimr</strong> turns YouTube videos into <em>bite-sized insights</em></li>
                <li>Generates <strong>summaries</strong>, <strong>action plans</strong>, and <strong>ready-to-share content</strong></li>
                <li>Paste the link. <strong>We handle the rest</strong></li>
            </ul>
            <p style="color: #3b82f6; 
                      margin: 1.5rem 0 0 0; 
                      font-weight: 600; 
                      text-align: center;
                      font-family: 'Inter', system-ui, -apple-system, sans-serif;">
                <strong>Spend less time watching. More time discovering.</strong>
            </p>
        </div>
        
        <div style="background: #ffffff; 
                    border: 1px solid #e5e7eb;
                    padding: 2rem; 
                    border-radius: 12px; 
                    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);">
            <h3 style="color: #111827; 
                       margin: 0 0 1.5rem 0; 
                       font-family: 'Inter', system-ui, -apple-system, sans-serif;
                       font-size: 1.25rem;
                       font-weight: 600;">
                🚀 What You'll Get
            </h3>
            <ul style="color: #374151; 
                       line-height: 1.6; 
                       margin: 0; 
                       padding-left: 1.25rem;
                       font-family: 'Inter', system-ui, -apple-system, sans-serif;">
                <li>✅ <strong>TL;DR Magic:</strong> 10x faster than watching</li>
                <li>✅ <strong>Ask & Receive:</strong> Get answers instantly</li>
                <li>✅ <strong>Copy-paste content</strong> for Blogs, LinkedIn, X</li>
                <li>✅ <strong>Actionable plans</strong> from passive watching</li>
            </ul>
        </div>
    </div>
    
    <div style="background: #f8f9fa; 
                border: 1px solid #e5e7eb;
                padding: 3rem 2rem; 
                border-radius: 12px; 
                margin: 3rem 0;
                box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);">
        <h3 style="color: #111827; 
                   margin: 0 0 2rem 0; 
                   text-align: center; 
                   font-family: 'Inter', system-ui, -apple-system, sans-serif;
                   font-size: 1.5rem;
                   font-weight: 600;">
            Who is Skimr For?
        </h3>
        
        <div style="display: grid; 
                    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); 
                    gap: 2rem;">
            
            <div style="background: #ffffff; 
                        border: 1px solid #e5e7eb;
                        padding: 2rem; 
                        border-radius: 8px; 
                        text-align: center;
                        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);">
                <h4 style="color: #111827; 
                           margin: 0 0 1rem 0;
                           font-family: 'Inter', system-ui, -apple-system, sans-serif;
                           font-size: 1.1rem;
                           font-weight: 600;">
                    🎓 Students & Researchers
                </h4>
                <p style="color: #6b7280; 
                          margin: 0; 
                          line-height: 1.5;
                          font-family: 'Inter', system-ui, -apple-system, sans-serif;">
                    Extract key insights from educational content without watching hours of lectures.
                </p>
            </div>
            
            <div style="background: #ffffff; 
                        border: 1px solid #e5e7eb;
                        padding: 2rem; 
                        border-radius: 8px; 
                        text-align: center;
                        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);">
                <h4 style="color: #111827; 
                           margin: 0 0 1rem 0;
                           font-family: 'Inter', system-ui, -apple-system, sans-serif;
                           font-size: 1.1rem;
                           font-weight: 600;">
                    💼 Busy Professionals
                </h4>
                <p style="color: #6b7280; 
                          margin: 0; 
                          line-height: 1.5;
                          font-family: 'Inter', system-ui, -apple-system, sans-serif;">
                    Stay updated with industry trends by quickly digesting conference talks and webinars.
                </p>
            </div>
            
            <div style="background: #ffffff; 
                        border: 1px solid #e5e7eb;
                        padding: 2rem; 
                        border-radius: 8px; 
                        text-align: center;
                        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);">
                <h4 style="color: #111827; 
                           margin: 0 0 1rem 0;
                           font-family: 'Inter', system-ui, -apple-system, sans-serif;
                           font-size: 1.1rem;
                           font-weight: 600;">
                    📱 Content Creators
                </h4>
                <p style="color: #6b7280; 
                          margin: 0; 
                          line-height: 1.5;
                          font-family: 'Inter', system-ui, -apple-system, sans-serif;">
                    Research competitors and trends efficiently. Generate social media content from video insights.
                </p>
            </div>
        </div>
    </div>
    """)


# Old functions removed - functionality moved to create_sidebar() and create_main_content()


def create_transcript_tab():
    """Create the transcript tab content."""
    with gr.Column():
        with gr.Row():
            show_timestamps = gr.Checkbox(label="Show timestamps", value=True)
            translate_btn = gr.Button("Translate to Target Language", variant="secondary")
            apply_subtitles_btn = gr.Button("✔ Apply Subtitles to Video Player", variant="primary")
        
        # Translation status
        translation_status = gr.Markdown("")
        
        transcript_display = gr.Textbox(
            label="Transcript",
            lines=15,
            max_lines=20,
            show_label=False,
            interactive=False,
            placeholder="Transcript will appear here after video analysis..."
        )
        
        # Download section
        with gr.Accordion("📥 Download Options", open=False):
            with gr.Row():
                download_srt_btn = gr.Button("Download SRT", variant="secondary")
                download_vtt_btn = gr.Button("Download VTT", variant="secondary")
            
            # File download components (hidden until files are ready)
            download_srt_file = gr.File(label="SRT File", visible=False)
            download_vtt_file = gr.File(label="VTT File", visible=False)
    
    return (show_timestamps, translate_btn, apply_subtitles_btn, translation_status,
            transcript_display, download_srt_btn, download_vtt_btn, 
            download_srt_file, download_vtt_file)


# Old functions removed - functionality moved to create_sidebar()


class GradioWebApp:
    """Main Gradio Web Application class."""
    
    def __init__(self):
        logger.info("Initializing GradioWebApp...")
        self.session_manager = GradioSessionManager()
        self.callbacks = GradioCallbacks()
        self.webapp_adapter = WebAppAdapter(self.callbacks)
        
        # Initialize authentication
        init_auth_state()
        
    def enable_url_input(self, url):
        """Enable/disable analyze button based on URL input."""
        has_url = bool(url and url.strip())
        return gr.update(interactive=has_url)
    
    def update_auth_display(self, session_state):
        """Update authentication display based on current state."""
        user = get_current_user()
        
        if user:
            auth_status = f"**Email:** {user.email}"
            stats = get_user_stats()
            if stats:
                auth_status += f"\n\n### Your Statistics\n**Summaries Generated:** {stats.get('summary_count', 0)}"
            
            return (
                gr.update(value=auth_status),  # auth_status
                gr.update(visible=False),      # auth_button
                gr.update(visible=True),       # logout_button
                gr.update(value="")            # user_stats
            )
        else:
            guest_count = session_state.get("guest_analysis_count", 0)
            remaining = max(0, config.auth.max_guest_analyses - guest_count)
            
            auth_status = "You are not logged in."
            if remaining > 0:
                auth_status += f"\n\n🎁 {remaining} free analysis remaining"
            else:
                auth_status += "\n\n🚫 Free analyses used up"
            
            return (
                gr.update(value=auth_status),  # auth_status
                gr.update(visible=True),       # auth_button
                gr.update(visible=False),      # logout_button
                gr.update(value="")            # user_stats
            )
    
    def handle_chat_submit(self, message, chat_history, session_state):
        """Handle chat message submission."""
        if not message or not message.strip():
            return "", chat_history, gr.update()
        
        # Add user message to chat history
        chat_history = chat_history or []
        chat_history.append({"role": "user", "content": message.strip()})
        
        # Update session state
        session_state = session_state or {}
        if "chat_messages" not in session_state:
            session_state["chat_messages"] = []
        
        # Add user message to session
        session_state["chat_messages"].append({"role": "user", "content": message.strip()})
        
        # Auto-save chat messages
        video_id = session_state.get("video_id")
        if video_id:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self.session_manager.auto_save_chat_messages(self.webapp_adapter, video_id))
            except RuntimeError:
                # No running event loop, run synchronously (fire and forget)
                try:
                    asyncio.run(self.session_manager.auto_save_chat_messages(self.webapp_adapter, video_id))
                except Exception:
                    pass
        
        # Clear input and disable it during response
        return "", chat_history, gr.update(interactive=False)
    
    def generate_chat_response(self, chat_history, session_state):
        """Generate streaming chat response."""
        if not chat_history or not session_state:
            return chat_history, session_state
        
        try:
            # Get the last user message from chat history
            user_message = None
            for msg in reversed(chat_history):
                if msg["role"] == "user":
                    user_message = msg["content"]
                    break
                    
            if not user_message:
                return chat_history, session_state
                
            video_id = session_state.get("video_id")
            
            if not video_id:
                chat_history.append({"role": "assistant", "content": "Sorry, I need a video to be analyzed first before I can answer questions."})
                return chat_history, session_state
            
            # Get chat messages for context (exclude the current message)
            previous_messages = session_state.get("chat_messages", [])[:-1]
            
            # Generate streaming response
            response = ""
            try:
                # Use asyncio to handle the streaming response
                async def get_streaming_response():
                    nonlocal response
                    settings = self.session_manager.get_settings()
                    async for chunk, token_usage in self.webapp_adapter.get_chat_response_stream(
                        video_id, previous_messages, user_message, settings
                    ):
                        if chunk:
                            response += chunk
                            # Update chat history with current response
                            current_history = chat_history.copy()
                            current_history.append({"role": "assistant", "content": response + "▌"})
                            yield current_history, session_state
                    
                    # Final response without cursor
                    final_history = chat_history.copy()
                    final_history.append({"role": "assistant", "content": response})
                    
                    # Add assistant message to session state
                    session_state["chat_messages"].append({"role": "assistant", "content": response})
                    
                    # Track token usage if available
                    if token_usage and isinstance(token_usage, dict):
                        self.session_manager.add_token_usage("chat", token_usage)
                        logger.info(f"Tracked chat token usage: {token_usage}")
                        
                        # Save token usage to cache
                        if video_id:
                            try:
                                success = await self.webapp_adapter.save_token_usage_to_cache(
                                    video_id, "chat", token_usage
                                )
                                if success:
                                    logger.debug(f"Saved chat token usage to cache for video {video_id}")
                            except Exception as e:
                                logger.warning(f"Error saving chat token usage to cache: {e}")
                    
                    # Auto-save updated chat messages
                    if video_id:
                        await self.session_manager.auto_save_chat_messages(self.webapp_adapter, video_id)
                    
                    yield final_history, session_state
                
                # Run the async generator
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    async_gen = get_streaming_response()
                    while True:
                        try:
                            result = loop.run_until_complete(async_gen.__anext__())
                            yield result
                        except StopAsyncIteration:
                            break
                finally:
                    loop.close()
                
            except Exception as e:
                logger.error(f"Error generating chat response: {e}", exc_info=True)
                error_message = "Sorry, I encountered an error while generating my response. Please try again."
                chat_history.append({"role": "assistant", "content": error_message})
                session_state["chat_messages"].append({"role": "assistant", "content": error_message})
                yield chat_history, session_state
                
        except Exception as e:
            logger.error(f"Error in chat response generation: {e}", exc_info=True)
            if chat_history and len(chat_history) > 0:
                error_message = "Sorry, an error occurred. Please try again."
                chat_history.append({"role": "assistant", "content": error_message})
            return chat_history, session_state
    
    def handle_chat_reset(self, session_state):
        """Handle chat reset."""
        try:
            # Clear chat messages from session state
            if session_state:
                session_state["chat_messages"] = []
                
                # Clear cached chat session
                video_id = session_state.get("video_id")
                if video_id:
                    try:
                        # Clear cache asynchronously
                        async def clear_cache():
                            await self.webapp_adapter.clear_chat_session(video_id)
                        
                        asyncio.create_task(clear_cache())
                        logger.info(f"Cleared chat cache for video {video_id}")
                    except Exception as e:
                        logger.warning(f"Error clearing chat cache: {e}")
                
                # Initialize with welcome message
                analysis_results = session_state.get("analysis_results")
                if analysis_results:
                    video_title = analysis_results.get("video_info", {}).get("title", "this video")
                    welcome = CHAT_WELCOME_TEMPLATE.format(video_title=video_title)
                    session_state["chat_messages"] = [{"role": "assistant", "content": welcome}]
                    
                    # Return updated chat history with welcome message
                    return [{"role": "assistant", "content": welcome}], session_state, gr.update(interactive=True)
            
            # Fallback welcome message
            welcome = "👋 Hi! I'm ready to answer questions about the video. What would you like to know?"
            if session_state:
                session_state["chat_messages"] = [{"role": "assistant", "content": welcome}]
            
            return [{"role": "assistant", "content": welcome}], session_state, gr.update(interactive=True)
            
        except Exception as e:
            logger.error(f"Error resetting chat: {e}", exc_info=True)
            return [], session_state, gr.update(interactive=True)
    
    def analyze_video_wrapper(self, url, session_state, progress=gr.Progress()):
        """Wrapper for analyze_video that handles button states and runs async analysis."""
        return asyncio.run(self.analyze_video(url, session_state, progress))
    
    async def analyze_video(self, url, session_state, progress=gr.Progress()):
        """Analyze a YouTube video."""
        if not url or not url.strip():
            return (session_state, 
                    gr.update(value="❌ Please enter a YouTube URL"),
                    gr.update(visible=True),   # video_input_section
                    gr.update(visible=False),  # analysis_results_section
                    [],                        # empty chat_history
                    gr.update(value=""),       # summary_content
                    gr.update(value=""),       # action_plan_content
                    gr.update(value=""),       # blog_content
                    gr.update(value=""),       # linkedin_content
                    gr.update(value=""),       # tweet_content
                    gr.update(value=""),       # video_player
                    gr.update(value=""),       # video_info
                    gr.update(value=""))       # transcript_display
        
        if not self.webapp_adapter.validate_youtube_url(url):
            return (session_state,
                    gr.update(value="❌ Invalid YouTube URL. Please check the URL and try again."),
                    gr.update(visible=True),
                    gr.update(visible=False),
                    [],
                    gr.update(value=""),
                    gr.update(value=""),
                    gr.update(value=""),
                    gr.update(value=""),
                    gr.update(value=""),
                    gr.update(value=""),
                    gr.update(value=""),
                    gr.update(value=""))
        
        # Check guest usage
        if not session_state.get("authenticated") and not check_guest_usage():
            return (session_state,
                    gr.update(value="❌ Guest analysis limit reached. Please log in."),
                    gr.update(visible=True),
                    gr.update(visible=False),
                    [],
                    gr.update(value=""),
                    gr.update(value=""),
                    gr.update(value=""),
                    gr.update(value=""),
                    gr.update(value=""),
                    gr.update(value=""),
                    gr.update(value=""),
                    gr.update(value=""))
        
        # Reset for new analysis
        self.session_manager.reset_for_new_analysis()
        session_state = self.session_manager.get_session_dict()
        self.session_manager.set_state("current_youtube_url", url)
        
        try:
            progress(0.0, desc="Starting analysis...")
            
            # Create a progress tracking function
            def progress_tracker(value):
                """Update Gradio progress bar"""
                normalized_value = max(0.0, min(1.0, value / 100.0))
                progress(normalized_value, desc=f"Analyzing video... {int(value)}%")
            
            # Set up the callback in the callbacks object
            self.callbacks.progress_tracker = progress_tracker
            self.callbacks.create_progress_callback = lambda: progress_tracker
            
            # Show initial progress steps
            progress(0.1, desc="Validating YouTube URL...")
            await asyncio.sleep(0.1)  # Small delay to show progress
            
            progress(0.2, desc="Downloading video information...")
            await asyncio.sleep(0.1)
            
            # Run analysis with progress tracking
            results, error = await self.webapp_adapter.analyze_video(
                url, self.session_manager.get_settings()
            )
            
            if error:
                error_msg = f"❌ Analysis failed: {error}"
                return (session_state, 
                        gr.update(value=error_msg),
                        gr.update(visible=True),
                        gr.update(visible=False),
                        [],
                        gr.update(value=""),
                        gr.update(value=""),
                        gr.update(value=""),
                        gr.update(value=""),
                        gr.update(value=""),
                        gr.update(value=""),
                        gr.update(value=""),
                        gr.update(value=""))
            
            if results:
                # Handle successful analysis
                await self._handle_successful_analysis(results, url)
                updated_session_state = self.session_manager.get_session_dict()
                
                # Initialize chat for the analysis
                chat_history, updated_session_state = self.initialize_chat_for_analysis(updated_session_state, results)
                
                # Populate analysis results
                (summary_content, action_plan_content, blog_content, linkedin_content, 
                 tweet_content, video_url, video_info_text, transcript_text) = self.populate_analysis_results(updated_session_state)
                
                progress(100, desc="Analysis complete!")
                
                return (updated_session_state,
                        gr.update(value="✅ Analysis completed successfully!"),
                        gr.update(visible=False),  # Hide input section
                        gr.update(visible=True),   # Show results section
                        chat_history,              # Initialize chat
                        summary_content,           # Summary tab
                        action_plan_content,       # Action Plan tab
                        blog_content,              # Blog tab
                        linkedin_content,          # LinkedIn tab
                        tweet_content,             # Tweet tab
                        video_url,                 # Video player
                        video_info_text,           # Video info
                        transcript_text)           # Transcript display
            else:
                return (session_state,
                        gr.update(value="❌ Analysis completed but returned no results."),
                        gr.update(visible=True),
                        gr.update(visible=False),
                        [],
                        gr.update(value=""),
                        gr.update(value=""),
                        gr.update(value=""),
                        gr.update(value=""),
                        gr.update(value=""),
                        gr.update(value=""),
                        gr.update(value=""),
                        gr.update(value=""))
                
        except Exception as e:
            logger.error(f"Exception during video analysis: {e}", exc_info=True)
            return (session_state,
                    gr.update(value=f"❌ An unexpected error occurred: {str(e)}"),
                    gr.update(visible=True),
                    gr.update(visible=False),
                    [],
                    gr.update(value=""),
                    gr.update(value=""),
                    gr.update(value=""),
                    gr.update(value=""),
                    gr.update(value=""),
                    gr.update(value=""),
                    gr.update(value=""),
                    gr.update(value=""))
    
    async def _handle_successful_analysis(self, results, youtube_url: str):
        """Handle successful analysis results."""
        logger.info("Analysis successful.")
        video_id = results.get("video_id")
        self.session_manager.set_video_id(video_id)
        
        # Initialize token usage with cache
        if video_id:
            try:
                token_loaded_from_cache = await self.session_manager.initialize_token_usage_with_cache_async(
                    self.webapp_adapter, video_id
                )
                if token_loaded_from_cache:
                    logger.info(f"Restored token usage from cache for video {video_id}")
                    self.session_manager.store_analysis_results_without_token_override(results)
                else:
                    logger.info(f"No cached token usage found for video {video_id}, using fresh tracking")
                    self.session_manager.set_analysis_results(results)
            except Exception as e:
                logger.warning(f"Failed to initialize token usage cache: {e}")
                self.session_manager.set_analysis_results(results)
        else:
            self.session_manager.set_analysis_results(results)
        
        self.session_manager.set_state("analysis_complete", True)
        
        # Handle chat setup
        if results.get("chat_details") and results["chat_details"].get("agent"):
            video_title = results.get("video_info", {}).get("title", "this video")
            
            chat_initialized = await self.session_manager.initialize_chat_with_cache_async(
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
                
                current_messages = self.session_manager.get_chat_messages()
                if not current_messages:
                    welcome = CHAT_WELCOME_TEMPLATE.format(video_title=video_title)
                    self.session_manager.initialize_chat_messages([{"role": "assistant", "content": welcome}])
        else:
            logger.warning("Chat details not found in analysis results.")
            self.session_manager.set_state("chat_enabled", False)
        
        # Increment summary count if not cached
        if not results.get("cached", False):
            if self.session_manager.get_state("authenticated"):
                user = get_current_user()
                if user and hasattr(user, 'id'):
                    increment_summary_count(user.id)
                    logger.info(f"Incremented summary count for user {user.id}")
            else:
                current_guest_count = self.session_manager.get_state("guest_analysis_count", 0)
                self.session_manager.set_state("guest_analysis_count", current_guest_count + 1)
                logger.info(f"Incremented guest analysis count to {current_guest_count + 1}")
    
    def initialize_chat_for_analysis(self, session_state, analysis_results):
        """Initialize chat interface with welcome message after analysis."""
        try:
            if analysis_results and analysis_results.get("chat_details"):
                video_title = analysis_results.get("video_info", {}).get("title", "this video")
                welcome = CHAT_WELCOME_TEMPLATE.format(video_title=video_title)
                
                # Initialize chat messages in session state
                session_state["chat_messages"] = [{"role": "assistant", "content": welcome}]
                session_state["chat_enabled"] = True
                
                # Return chat history for Gradio chatbot
                return [{"role": "assistant", "content": welcome}], session_state
            else:
                # Fallback welcome message
                welcome = "👋 Hi! I'm ready to answer questions about the video. What would you like to know?"
                session_state["chat_messages"] = [{"role": "assistant", "content": welcome}]
                session_state["chat_enabled"] = True
                return [{"role": "assistant", "content": welcome}], session_state
                
        except Exception as e:
            logger.error(f"Error initializing chat: {e}", exc_info=True)
            return [], session_state
    
    async def generate_content(self, content_type, custom_instruction, session_state):
        """Generate additional content (Action Plan, Blog Post, LinkedIn Post, X Tweet)."""
        try:
            # Get analysis results and required data
            analysis_results = session_state.get("analysis_results")
            if not analysis_results:
                return gr.update(value="❌ No analysis results found. Please analyze a video first."), session_state
            
            # Get required data for content generation
            youtube_url = analysis_results.get("youtube_url")
            video_id = analysis_results.get("video_id")
            transcript_text = analysis_results.get("transcript", "")
            
            # Try alternative transcript sources if main one is empty
            if not transcript_text:
                transcript_segments = analysis_results.get("transcript_segments", [])
                if transcript_segments:
                    transcript_text = " ".join([segment.get("text", "") for segment in transcript_segments if segment.get("text")])
                
                if not transcript_text:
                    video_info = analysis_results.get("video_info", {})
                    if isinstance(video_info, dict):
                        transcript_text = video_info.get("transcript", "")
            
            if not all([youtube_url, video_id, transcript_text]):
                missing_fields = []
                if not youtube_url: missing_fields.append("youtube_url")
                if not video_id: missing_fields.append("video_id")
                if not transcript_text: missing_fields.append("transcript")
                
                error_msg = f"❌ Cannot generate content: Missing {', '.join(missing_fields)} from analysis."
                return gr.update(value=error_msg), session_state
            
            # Content type mapping
            content_types_map = {
                "Action Plan": "analyze_and_plan_content",
                "Blog Post": "write_blog_post", 
                "LinkedIn Post": "write_linkedin_post",
                "X Tweet": "write_tweet"
            }
            
            task_key = content_types_map.get(content_type, content_type)
            
            # Prepare settings with custom instruction
            settings = self.session_manager.get_settings().copy()
            if custom_instruction and custom_instruction.strip():
                settings["custom_instruction"] = custom_instruction.strip()
            
            # Generate content
            content, error, token_usage = await self.webapp_adapter.generate_additional_content(
                youtube_url, video_id, transcript_text, content_type, settings
            )
            
            if error:
                if "Connection" in error or "timeout" in error.lower():
                    return gr.update(value=f"❌ Connection issue while generating {content_type}. Please try again."), session_state
                elif "rate limit" in error.lower() or "quota" in error.lower():
                    return gr.update(value=f"❌ Service temporarily unavailable. Please try again in a few minutes."), session_state
                else:
                    return gr.update(value=f"❌ Failed to generate {content_type}: {error}"), session_state
            
            if content:
                # Update task output in session state
                if "analysis_results" not in session_state:
                    session_state["analysis_results"] = {}
                if "task_outputs" not in session_state["analysis_results"]:
                    session_state["analysis_results"]["task_outputs"] = {}
                
                session_state["analysis_results"]["task_outputs"][task_key] = content
                
                # Track token usage
                if token_usage and isinstance(token_usage, dict):
                    self.session_manager.add_token_usage("additional_content", token_usage, task_key)
                    logger.info(f"Tracked token usage for {content_type}: {token_usage}")
                    
                    # Save token usage to cache
                    if video_id:
                        try:
                            success = await self.webapp_adapter.save_token_usage_to_cache(
                                video_id, "additional_content", token_usage, task_key
                            )
                            if success:
                                logger.debug(f"Saved additional content token usage to cache for video {video_id}")
                        except Exception as e:
                            logger.warning(f"Error saving additional content token usage to cache: {e}")
                
                # Clean content for display
                from youtube_analysis.utils.youtube_utils import clean_markdown_fences
                cleaned_content = clean_markdown_fences(content)
                
                return gr.update(value=cleaned_content), session_state
            else:
                return gr.update(value=f"❌ No content generated for {content_type}, but no error reported."), session_state
                
        except Exception as e:
            logger.error(f"Exception generating {content_type}: {e}", exc_info=True)
            return gr.update(value=f"❌ Error generating {content_type}: {str(e)}"), session_state
    
    def handle_action_plan_generate(self, custom_instruction, session_state):
        """Handle Action Plan generation."""
        return asyncio.run(self.generate_content("Action Plan", custom_instruction, session_state))
    
    def handle_blog_generate(self, custom_instruction, session_state):
        """Handle Blog Post generation.""" 
        return asyncio.run(self.generate_content("Blog Post", custom_instruction, session_state))
    
    def handle_linkedin_generate(self, custom_instruction, session_state):
        """Handle LinkedIn Post generation."""
        return asyncio.run(self.generate_content("LinkedIn Post", custom_instruction, session_state))
    
    def handle_tweet_generate(self, custom_instruction, session_state):
        """Handle X Tweet generation."""
        return asyncio.run(self.generate_content("X Tweet", custom_instruction, session_state))
    
    def handle_new_analysis(self, session_state):
        """Handle new analysis request - reset everything for a fresh start."""
        try:
            # Clear all analysis-related data
            self.session_manager.reset_for_new_analysis()
            
            # Clear session state
            session_state = self.session_manager.get_session_dict()
            
            # Reset URL input
            return (
                session_state,                      # Updated session state
                "",                                 # Clear URL input
                gr.update(visible=True),            # Show input section
                gr.update(visible=False),           # Hide results section
                [],                                 # Clear chat history
                gr.update(value=""),                # Clear summary
                gr.update(value=""),                # Clear action plan
                gr.update(value=""),                # Clear blog
                gr.update(value=""),                # Clear linkedin
                gr.update(value=""),                # Clear tweet
                gr.update(value=""),                # Clear video player
                gr.update(value=""),                # Clear video info
                gr.update(value="Ready for new analysis") # Status message
            )
        except Exception as e:
            logger.error(f"Error handling new analysis: {e}", exc_info=True)
            return (
                session_state,
                "",
                gr.update(visible=True),
                gr.update(visible=False), 
                [],
                gr.update(value=""),
                gr.update(value=""),
                gr.update(value=""),
                gr.update(value=""),
                gr.update(value=""),
                gr.update(value=""),
                gr.update(value=""),
                gr.update(value=f"Error resetting: {str(e)}")
            )
    
    def handle_clear_cache(self, session_state):
        """Handle cache clearing for current video."""
        try:
            video_id = session_state.get("video_id")
            if not video_id:
                return session_state, gr.update(value="❌ No video to clear cache for.")
            
            # Clear cache for the video
            success = self.webapp_adapter.clear_cache_for_video(video_id)
            
            # Clear subtitle data from session state
            self.session_manager.clear_subtitle_data()
            
            if success:
                # Reset for new analysis
                self.session_manager.reset_for_new_analysis()
                session_state = self.session_manager.get_session_dict()
                
                return (
                    session_state,
                    gr.update(value=f"✅ Cache cleared successfully for video {video_id}. Ready for fresh analysis.")
                )
            else:
                return session_state, gr.update(value=f"⚠️ Cache clearing may have failed for video {video_id}.")
                
        except Exception as e:
            logger.error(f"Error clearing cache: {e}", exc_info=True)
            return session_state, gr.update(value=f"❌ Error clearing cache: {str(e)}")
    
    def show_auth_form(self):
        """Show the authentication form."""
        return (
            gr.update(visible=True),   # auth_form
            gr.update(visible=False),  # auth_button
            gr.update(visible=True),   # cancel_auth_button
            gr.update(value=""),       # login_message
            gr.update(value="")        # signup_message
        )
    
    def hide_auth_form(self):
        """Hide the authentication form."""
        return (
            gr.update(visible=False),  # auth_form
            gr.update(visible=True),   # auth_button
            gr.update(visible=False),  # cancel_auth_button
            gr.update(value=""),       # login_email
            gr.update(value=""),       # login_password
            gr.update(value=""),       # signup_email
            gr.update(value=""),       # signup_password
            gr.update(value=""),       # signup_confirm
            gr.update(value=""),       # login_message
            gr.update(value="")        # signup_message
        )
    
    def handle_login(self, email, password, session_state):
        """Handle user login."""
        try:
            if not email or not password:
                return (
                    session_state,
                    gr.update(value="❌ Please enter both email and password."),
                    gr.update(),  # auth_status
                    gr.update(),  # auth_form visibility
                    gr.update(),  # auth_button visibility
                    gr.update(),  # logout_button visibility
                    gr.update(),  # cancel_auth_button visibility
                    gr.update()   # user_stats
                )
            
            # Import auth service function
            from youtube_analysis.services.auth_service import login
            
            success, message = login(email, password)
            
            if success:
                # Update session state
                session_state["authenticated"] = True
                user = get_current_user()
                session_state["user"] = user
                
                # Get user stats
                stats = get_user_stats()
                auth_status = f"**Email:** {user.email}"
                if stats:
                    auth_status += f"\n\n### Your Statistics\n**Summaries Generated:** {stats.get('summary_count', 0)}"
                
                return (
                    session_state,
                    gr.update(value="✅ Login successful!"),
                    gr.update(value=auth_status),
                    gr.update(visible=False),  # Hide auth form
                    gr.update(visible=False),  # Hide auth button
                    gr.update(visible=True),   # Show logout button
                    gr.update(visible=False),  # Hide cancel button
                    gr.update(value="")
                )
            else:
                return (
                    session_state,
                    gr.update(value=f"❌ {message}"),
                    gr.update(),
                    gr.update(),
                    gr.update(),
                    gr.update(),
                    gr.update(),
                    gr.update()
                )
                
        except Exception as e:
            logger.error(f"Error during login: {e}", exc_info=True)
            return (
                session_state,
                gr.update(value=f"❌ Login error: {str(e)}"),
                gr.update(),
                gr.update(),
                gr.update(),
                gr.update(),
                gr.update(),
                gr.update()
            )
    
    def handle_signup(self, email, password, confirm_password, session_state):
        """Handle user signup."""
        try:
            if not email or not password or not confirm_password:
                return (
                    session_state,
                    gr.update(value="❌ Please fill in all fields."),
                    gr.update(),  # auth_status
                    gr.update(),  # auth_form visibility
                    gr.update(),  # auth_button visibility
                    gr.update(),  # logout_button visibility
                    gr.update(),  # cancel_auth_button visibility
                    gr.update()   # user_stats
                )
            
            if password != confirm_password:
                return (
                    session_state,
                    gr.update(value="❌ Passwords do not match."),
                    gr.update(),
                    gr.update(),
                    gr.update(),
                    gr.update(),
                    gr.update(),
                    gr.update()
                )
            
            # Import auth service function
            from youtube_analysis.services.auth_service import signup
            
            success, message = signup(email, password)
            
            if success:
                # Auto-login after successful signup
                from youtube_analysis.services.auth_service import login
                login_success, login_message = login(email, password)
                
                if login_success:
                    # Update session state
                    session_state["authenticated"] = True
                    user = get_current_user()
                    session_state["user"] = user
                    
                    # Get user stats
                    stats = get_user_stats()
                    auth_status = f"**Email:** {user.email}"
                    if stats:
                        auth_status += f"\n\n### Your Statistics\n**Summaries Generated:** {stats.get('summary_count', 0)}"
                    
                    return (
                        session_state,
                        gr.update(value="✅ Account created and logged in successfully!"),
                        gr.update(value=auth_status),
                        gr.update(visible=False),  # Hide auth form
                        gr.update(visible=False),  # Hide auth button
                        gr.update(visible=True),   # Show logout button
                        gr.update(visible=False),  # Hide cancel button
                        gr.update(value="")
                    )
                else:
                    return (
                        session_state,
                        gr.update(value=f"✅ Account created! Please login."),
                        gr.update(),
                        gr.update(),
                        gr.update(),
                        gr.update(),
                        gr.update(),
                        gr.update()
                    )
            else:
                return (
                    session_state,
                    gr.update(value=f"❌ {message}"),
                    gr.update(),
                    gr.update(),
                    gr.update(),
                    gr.update(),
                    gr.update(),
                    gr.update()
                )
                
        except Exception as e:
            logger.error(f"Error during signup: {e}", exc_info=True)
            return (
                session_state,
                gr.update(value=f"❌ Signup error: {str(e)}"),
                gr.update(),
                gr.update(),
                gr.update(),
                gr.update(),
                gr.update(),
                gr.update()
            )
    
    def handle_logout(self, session_state):
        """Handle user logout."""
        try:
            success = logout()
            if success:
                # Update session state
                session_state["authenticated"] = False
                session_state["user"] = None
                
                # Update auth display
                guest_count = session_state.get("guest_analysis_count", 0)
                remaining = max(0, config.auth.max_guest_analyses - guest_count)
                
                auth_status = "You are not logged in."
                if remaining > 0:
                    auth_status += f"\n\n🎁 {remaining} free analysis remaining"
                else:
                    auth_status += "\n\n🚫 Free analyses used up"
                
                return (
                    session_state,
                    gr.update(value=auth_status),   # auth_status
                    gr.update(visible=True),        # auth_button
                    gr.update(visible=False),       # logout_button
                    gr.update(value="")             # user_stats
                )
            else:
                return (
                    session_state,
                    gr.update(),
                    gr.update(),
                    gr.update(),
                    gr.update()
                )
        except Exception as e:
            logger.error(f"Error during logout: {e}", exc_info=True)
            return (
                session_state,
                gr.update(),
                gr.update(),
                gr.update(),
                gr.update()
            )
    
    def populate_analysis_results(self, session_state):
        """Populate analysis result tabs with content from session state."""
        try:
            analysis_results = session_state.get("analysis_results")
            if not analysis_results:
                return (
                    gr.update(value=""), # summary_content
                    gr.update(value=""), # action_plan_content
                    gr.update(value=""), # blog_content
                    gr.update(value=""), # linkedin_content
                    gr.update(value=""), # tweet_content
                    gr.update(value=""), # video_player
                    gr.update(value=""), # video_info
                    gr.update(value="")  # transcript_display
                )
            
            task_outputs = analysis_results.get("task_outputs", {})
            video_info = analysis_results.get("video_info", {})
            video_id = analysis_results.get("video_id")
            transcript_text = analysis_results.get("transcript", "")
            
            # Clean content for display
            from youtube_analysis.utils.youtube_utils import clean_markdown_fences
            
            # Get content for each tab
            summary = task_outputs.get("classify_and_summarize_content", "")
            action_plan = task_outputs.get("analyze_and_plan_content", "")
            blog = task_outputs.get("write_blog_post", "")
            linkedin = task_outputs.get("write_linkedin_post", "")
            tweet = task_outputs.get("write_tweet", "")
            
            # Clean markdown fences
            summary = clean_markdown_fences(summary) if summary else ""
            action_plan = clean_markdown_fences(action_plan) if action_plan else ""
            blog = clean_markdown_fences(blog) if blog else ""
            linkedin = clean_markdown_fences(linkedin) if linkedin else ""
            tweet = clean_markdown_fences(tweet) if tweet else ""
            
            # Video player HTML iframe embed
            video_html = f'<iframe width="100%" height="400" src="https://www.youtube.com/embed/{video_id}" frameborder="0" allowfullscreen></iframe>' if video_id else ""
            
            # Video info display
            video_title = video_info.get("title", "")
            video_duration = video_info.get("duration", "")
            video_info_text = ""
            if video_title:
                video_info_text = f"**{video_title}**"
                if video_duration:
                    video_info_text += f" • Duration: {video_duration}"
            
            return (
                gr.update(value=summary),
                gr.update(value=action_plan if action_plan else "Action Plan not yet generated."),
                gr.update(value=blog if blog else "Blog Post not yet generated."),
                gr.update(value=linkedin if linkedin else "LinkedIn Post not yet generated."),
                gr.update(value=tweet if tweet else "X Tweet not yet generated."),
                gr.update(value=video_html),
                gr.update(value=video_info_text),
                gr.update(value=transcript_text if transcript_text else "Transcript will appear here after analysis...")
            )
            
        except Exception as e:
            logger.error(f"Error populating analysis results: {e}", exc_info=True)
            return (
                gr.update(value="Error loading results"),
                gr.update(value="Error loading results"),
                gr.update(value="Error loading results"),
                gr.update(value="Error loading results"),
                gr.update(value="Error loading results"),
                gr.update(value=""),
                gr.update(value="Error loading video info"),
                gr.update(value="Error loading transcript")
            )
    
    def toggle_transcript_timestamps(self, show_timestamps, session_state):
        """Toggle between transcript with and without timestamps."""
        try:
            analysis_results = session_state.get("analysis_results")
            if not analysis_results:
                return gr.update(value="No transcript available")
            
            transcript_segments = analysis_results.get("transcript_segments", [])
            transcript_text = analysis_results.get("transcript", "")
            
            # Check for translated segments in session state
            video_id = analysis_results.get("video_id")
            settings = self.session_manager.get_settings()
            target_language = settings.get("subtitle_language", "en")
            
            session_translation_key = f"translated_segments_for_display_{video_id}_{target_language}"
            translated_segments = session_state.get(session_translation_key)
            
            # Use translated segments if available and language is different
            if translated_segments and target_language != "en":
                display_segments = translated_segments
                display_text = " ".join([seg.get("text", "") for seg in translated_segments])
            else:
                display_segments = transcript_segments
                display_text = transcript_text
            
            if show_timestamps and display_segments:
                # Format with timestamps
                from youtube_analysis.utils.subtitle_utils import format_srt_time
                formatted_transcript = "\n".join([
                    f"[{format_srt_time(seg.get('start', 0))} --> {format_srt_time(seg.get('start', 0) + (seg.get('duration', 2.0) or 2.0))}] {seg.get('text', '')}"
                    for seg in display_segments
                ])
                return gr.update(value=formatted_transcript)
            else:
                # Plain text
                return gr.update(value=display_text if display_text else "No transcript available")
                
        except Exception as e:
            logger.error(f"Error toggling transcript timestamps: {e}", exc_info=True)
            return gr.update(value="Error formatting transcript")
    
    async def handle_translate_transcript(self, session_state):
        """Handle transcript translation."""
        try:
            analysis_results = session_state.get("analysis_results")
            if not analysis_results:
                return session_state, gr.update(value="❌ No analysis results found.")
            
            video_id = analysis_results.get("video_id")
            transcript_segments = analysis_results.get("transcript_segments", [])
            
            if not transcript_segments:
                return session_state, gr.update(value="❌ No transcript segments available for translation.")
            
            # Get target language from settings
            settings = self.session_manager.get_settings()
            target_language = settings.get("subtitle_language", "en")
            
            # Detect source language
            from youtube_analysis.utils.subtitle_utils import detect_language
            transcript_text = analysis_results.get("transcript", "")
            source_language = analysis_results.get("detected_language")
            
            if not source_language and transcript_text:
                source_language = detect_language(transcript_text)
            
            if not source_language or source_language == "unknown":
                # Check for Hindi characters as fallback
                devanagari_chars = sum(1 for c in transcript_text if '\u0900' <= c <= '\u097F')
                source_language = "hi" if devanagari_chars > 0 else "en"
            
            if target_language == source_language:
                return session_state, gr.update(value="💡 Target language is the same as source language. No translation needed.")
            
            # Check if already translated
            session_translation_key = f"translated_segments_for_display_{video_id}_{target_language}"
            if session_translation_key in session_state:
                from youtube_analysis.utils.language_utils import get_language_name
                lang_name = get_language_name(target_language)
                return session_state, gr.update(value=f"✅ Already translated to {lang_name}")
            
            # Perform translation
            from youtube_analysis.service_factory import get_translation_service
            translation_service = get_translation_service()
            
            translated_text, translated_segments = await translation_service.translate_transcript(
                segments=transcript_segments,
                source_language=source_language,
                target_language=target_language,
                video_id=video_id
            )
            
            if translated_segments:
                # Store translated segments
                session_state[session_translation_key] = translated_segments
                
                # Update subtitles data for video player
                subtitles_player_key = f"subtitles_for_player_{video_id}"
                subtitles_data = session_state.get(subtitles_player_key, {})
                subtitles_data[target_language] = {
                    "segments": translated_segments,
                    "default": True
                }
                # Set other languages as non-default
                for lang in subtitles_data:
                    if lang != target_language:
                        subtitles_data[lang]["default"] = False
                        
                session_state[subtitles_player_key] = subtitles_data
                
                from youtube_analysis.utils.language_utils import get_language_name
                lang_name = get_language_name(target_language)
                return session_state, gr.update(value=f"✅ Successfully translated to {lang_name}")
            else:
                return session_state, gr.update(value="❌ Translation failed. Please try again.")
                
        except Exception as e:
            logger.error(f"Error translating transcript: {e}", exc_info=True)
            return session_state, gr.update(value=f"❌ Translation error: {str(e)}")
    
    def handle_apply_subtitles(self, session_state):
        """Handle applying subtitles to video player."""
        try:
            analysis_results = session_state.get("analysis_results")
            if not analysis_results:
                return session_state, gr.update(value="❌ No analysis results found.")
            
            video_id = analysis_results.get("video_id")
            if not video_id:
                return session_state, gr.update(value="❌ No video ID found.")
            
            # Check for subtitles data
            subtitles_player_key = f"subtitles_for_player_{video_id}"
            subtitles_data = session_state.get(subtitles_player_key, {})
            
            if not subtitles_data or not any(info.get("segments") for info in subtitles_data.values()):
                return session_state, gr.update(value="❌ No subtitle data available.")
            
            # Set flags to show video with custom subtitles
            session_state["show_video_with_subtitles"] = True
            session_state["video_id_for_subtitles"] = video_id
            
            return session_state, gr.update(value="✅ Subtitles applied to video player!")
            
        except Exception as e:
            logger.error(f"Error applying subtitles: {e}", exc_info=True)
            return session_state, gr.update(value=f"❌ Error applying subtitles: {str(e)}")
    
    def handle_download_subtitle_file(self, file_type, session_state):
        """Handle subtitle file download (SRT or VTT)."""
        try:
            analysis_results = session_state.get("analysis_results")
            if not analysis_results:
                return gr.update(value=None, visible=False)
            
            video_id = analysis_results.get("video_id")
            transcript_segments = analysis_results.get("transcript_segments", [])
            
            # Check for translated segments
            settings = self.session_manager.get_settings()
            target_language = settings.get("subtitle_language", "en")
            session_translation_key = f"translated_segments_for_display_{video_id}_{target_language}"
            
            # Use translated segments if available
            if session_translation_key in session_state:
                segments_for_download = session_state[session_translation_key]
                export_language = target_language
            else:
                segments_for_download = transcript_segments
                export_language = "en"  # Default to English
            
            if not segments_for_download:
                return gr.update(value=None, visible=False)
            
            # Generate subtitle files
            from youtube_analysis.utils.subtitle_utils import create_subtitle_files
            subtitle_files = create_subtitle_files(
                segments=segments_for_download,
                video_id=video_id,
                language=export_language
            )
            
            if file_type.lower() in subtitle_files:
                file_path = subtitle_files[file_type.lower()]
                if os.path.exists(file_path):
                    return gr.update(value=file_path, visible=True)
            
            return gr.update(value=None, visible=False)
            
        except Exception as e:
            logger.error(f"Error generating {file_type} file: {e}", exc_info=True)
            return gr.update(value=None, visible=False)
    
    def update_token_usage_display(self, session_state):
        """Update token usage display with current session data."""
        try:
            # Get token usage data from session manager
            cumulative_usage = self.session_manager.get_cumulative_token_usage()
            token_breakdown = self.session_manager.get_token_usage_breakdown()
            settings = self.session_manager.get_settings()
            
            # Update token counts
            total_tokens_value = cumulative_usage.get("total_tokens", 0)
            prompt_tokens_value = cumulative_usage.get("prompt_tokens", 0) 
            completion_tokens_value = cumulative_usage.get("completion_tokens", 0)
            
            # Update model info
            current_model = settings.get("model", "Not selected")
            model_info_text = f"**Model:** {current_model}"
            
            # Calculate estimated cost (simplified format for sidebar)
            from youtube_analysis.services.cost_service import calculate_cost_for_tokens
            try:
                total_cost = calculate_cost_for_tokens(
                    model=current_model,
                    input_tokens=prompt_tokens_value,
                    output_tokens=completion_tokens_value
                )
                if total_cost < 0.01:
                    estimated_cost_text = f"${total_cost:.6f}"
                else:
                    estimated_cost_text = f"${total_cost:.2f}"
                cost_source_text = f"**Cost Source:** dynamic"
            except Exception as e:
                logger.warning(f"Error calculating cost: {e}")
                estimated_cost_text = "$0.00"
                cost_source_text = "**Cost Source:** unavailable"
            
            # Create simplified usage breakdown for sidebar
            if total_tokens_value > 0:
                usage_breakdown_text = f"**Tokens:** {total_tokens_value:,}\n**Cost:** {estimated_cost_text}\n**Model:** {current_model}"
            else:
                usage_breakdown_text = "No usage data available yet."
            
            return (
                gr.update(value=total_tokens_value),
                gr.update(value=prompt_tokens_value),
                gr.update(value=completion_tokens_value),
                gr.update(value=model_info_text),
                gr.update(value=estimated_cost_text),
                gr.update(value=cost_source_text),
                gr.update(value=usage_breakdown_text)
            )
            
        except Exception as e:
            logger.error(f"Error updating token usage display: {e}", exc_info=True)
            return (
                gr.update(value=0),
                gr.update(value=0),
                gr.update(value=0),
                gr.update(value="**Model:** Error"),
                gr.update(value="$0.00"),
                gr.update(value="**Cost Source:** Error"),
                gr.update(value="Error loading usage data")
            )
    
    def handle_model_change(self, model_value, session_state):
        """Handle AI model selection change."""
        try:
            settings = self.session_manager.get_settings()
            settings["model"] = model_value
            self.session_manager.set_settings(settings)
            logger.info(f"Model updated to: {model_value}")
            return session_state
        except Exception as e:
            logger.error(f"Error updating model: {e}", exc_info=True)
            return session_state
    
    def handle_transcription_model_change(self, transcription_model, session_state):
        """Handle transcription model selection change."""
        try:
            settings = self.session_manager.get_settings()
            settings["transcription_model"] = transcription_model
            self.session_manager.set_settings(settings)
            logger.info(f"Transcription model updated to: {transcription_model}")
            return session_state
        except Exception as e:
            logger.error(f"Error updating transcription model: {e}", exc_info=True)
            return session_state
    
    def handle_temperature_change(self, temperature, session_state):
        """Handle temperature slider change."""
        try:
            settings = self.session_manager.get_settings()
            settings["temperature"] = temperature
            self.session_manager.set_settings(settings)
            logger.info(f"Temperature updated to: {temperature}")
            return session_state
        except Exception as e:
            logger.error(f"Error updating temperature: {e}", exc_info=True)
            return session_state
    
    def handle_cache_setting_change(self, use_cache, session_state):
        """Handle cache setting change."""
        try:
            settings = self.session_manager.get_settings()
            settings["use_cache"] = use_cache
            self.session_manager.set_settings(settings)
            logger.info(f"Use cache updated to: {use_cache}")
            return session_state
        except Exception as e:
            logger.error(f"Error updating cache setting: {e}", exc_info=True)
            return session_state
    
    def handle_subtitle_language_change(self, language_option, session_state):
        """Handle subtitle language selection change."""
        try:
            # Extract language code from "Language Name (code)" format
            language_code = language_option.split("(")[-1].rstrip(")")
            settings = self.session_manager.get_settings()
            settings["subtitle_language"] = language_code
            self.session_manager.set_settings(settings)
            logger.info(f"Subtitle language updated to: {language_code}")
            return session_state
        except Exception as e:
            logger.error(f"Error updating subtitle language: {e}", exc_info=True)
            return session_state
    
    def create_interface(self):
        """Create the main Gradio interface."""
        with gr.Blocks(
            theme=gr.themes.Soft(),
            title="SKIMR - YouTube Analysis",
            css="""
            /* Import Inter font */
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
            
            /* Global styles */
            * {
                font-family: 'Inter', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
            }
            
            .gradio-container {
                max-width: 1600px !important;
                margin: 0 auto;
                background: #f9fafb;
                min-height: 100vh;
            }
            
            /* Header styling */
            .gradio-container > .gradio-column > .gradio-row:first-child {
                margin-bottom: 0 !important;
            }
            
            /* Main layout styling */
            .url-input input {
                border-radius: 8px !important;
                border: 1px solid #d1d5db !important;
                font-size: 16px !important;
                padding: 12px 16px !important;
                font-family: 'Inter', system-ui, -apple-system, sans-serif !important;
                transition: all 0.2s ease !important;
            }
            
            .url-input input:focus {
                border-color: #3b82f6 !important;
                box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1) !important;
                outline: none !important;
            }
            
            .modern-chatbot {
                border-radius: 8px !important;
                border: 1px solid #e5e7eb !important;
                box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1) !important;
            }
            
            .chat-input input {
                border-radius: 8px !important;
                border: 1px solid #d1d5db !important;
                padding: 10px 14px !important;
                font-family: 'Inter', system-ui, -apple-system, sans-serif !important;
                transition: all 0.2s ease !important;
            }
            
            .chat-input input:focus {
                border-color: #3b82f6 !important;
                box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1) !important;
                outline: none !important;
            }
            
            .content-display {
                background: #ffffff;
                padding: 2rem;
                border-radius: 8px;
                border: 1px solid #e5e7eb;
                margin: 1rem 0;
                box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
            }
            
            .modern-tab {
                font-weight: 600 !important;
                font-family: 'Inter', system-ui, -apple-system, sans-serif !important;
            }
            
            .auth-status, .model-info, .usage-breakdown {
                font-size: 0.9rem;
                line-height: 1.5;
                font-family: 'Inter', system-ui, -apple-system, sans-serif !important;
                color: #374151;
            }
            
            .settings-subsection {
                font-size: 0.95rem;
                margin: 0.75rem 0 0.5rem 0;
                color: #6b7280;
                font-family: 'Inter', system-ui, -apple-system, sans-serif !important;
            }
            
            .status-display {
                text-align: center;
                font-weight: 500;
                margin: 1.5rem 0;
                font-family: 'Inter', system-ui, -apple-system, sans-serif !important;
                color: #374151;
            }
            
            /* Button styling */
            .gradio-button {
                font-family: 'Inter', system-ui, -apple-system, sans-serif !important;
                font-weight: 500;
                border-radius: 8px !important;
                transition: all 0.2s ease !important;
            }
            
            /* Form elements */
            .gradio-textbox input, .gradio-dropdown select, .gradio-slider input {
                font-family: 'Inter', system-ui, -apple-system, sans-serif !important;
                border-radius: 8px !important;
            }
            
            /* Sidebar styling */
            .gradio-group {
                border: 1px solid #e5e7eb;
                border-radius: 8px;
                padding: 1rem;
                margin-bottom: 1.5rem;
                background: #ffffff;
                box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
            }
            
            /* Responsive design */
            @media (max-width: 1024px) {
                .gradio-container {
                    max-width: 100% !important;
                    margin: 0;
                    padding: 1rem;
                }
            }
            
            @media (max-width: 768px) {
                .gradio-container {
                    padding: 0.5rem;
                }
            }
            
            /* Custom styles for analyze button */
            .analyze-btn button {
                background: #2563eb !important;
                color: #fff !important;
                font-weight: 700 !important;
                font-size: 1.15rem !important;
                border-radius: 8px !important;
                padding: 0.85rem 2.5rem !important;
                min-height: 56px !important;
                box-shadow: 0 2px 8px rgba(37,99,235,0.08);
                border: none !important;
                transition: background 0.2s, box-shadow 0.2s;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            .analyze-btn button:hover, .analyze-btn button:focus {
                background: #1d4ed8 !important;
                box-shadow: 0 4px 16px rgba(37,99,235,0.12);
            }
            .analyze-btn {
                display: flex;
                align-items: center;
                height: 100%;
                margin-left: 1rem;
            }
            """
        ) as interface:
            
            # Global state
            session_state = gr.State(self.session_manager.get_session_dict())
            
            # Header
            create_header()
            
            # Main layout with sidebar and content
            with gr.Row(equal_height=False):
                # Sidebar with all controls
                (sidebar, auth_status, auth_form, login_email, login_password, login_button, 
                 login_message, signup_email, signup_password, signup_confirm, 
                 signup_button, signup_message, auth_button, logout_button, 
                 cancel_auth_button, user_stats, model_dropdown, transcription_dropdown, 
                 temperature_slider, use_cache_checkbox, subtitle_language, new_analysis_btn, 
                 clear_cache_btn, total_tokens, prompt_tokens, completion_tokens, 
                 model_info, estimated_cost, cost_source, usage_breakdown) = create_sidebar()
                
                # Main content area
                (main_content, video_input_section, analysis_results_section, youtube_url, analyze_btn, 
                 status_display, progress_bar, video_player, video_info, video_subtitles_status,
                 chatbot, chat_input, chat_submit, chat_reset, summary_content, action_plan_content, 
                 blog_content, linkedin_content, tweet_content, action_plan_instruction,
                 blog_instruction, linkedin_instruction, tweet_instruction, action_plan_generate,
                 blog_generate, linkedin_generate, tweet_generate, show_timestamps, translate_btn, 
                 apply_subtitles_btn, translation_status, transcript_display, download_srt_btn, 
                 download_vtt_btn, download_srt_file, download_vtt_file) = create_main_content()
            
            # Event handlers
            
            # Enable analyze button when URL is entered
            youtube_url.change(
                fn=self.enable_url_input,
                inputs=[youtube_url],
                outputs=[analyze_btn]
            )
            
            # Analyze video with progress tracking
            def start_analysis(url, session_state):
                """Start analysis and disable button"""
                return (
                    gr.update(interactive=False, value="🔄 Analyzing..."),  # Disable analyze button
                    gr.update(value="🔄 Starting analysis..."),  # Update status
                    session_state
                )
            
            def finish_analysis_ui_update():
                """Re-enable button after analysis"""
                return gr.update(interactive=True, value="🔍 Analyze")
                
            # Click event: disable button and start analysis
            analyze_click = analyze_btn.click(
                fn=start_analysis,
                inputs=[youtube_url, session_state],
                outputs=[analyze_btn, status_display, session_state]
            ).then(
                # Run the actual analysis
                fn=self.analyze_video_wrapper,
                inputs=[youtube_url, session_state],
                outputs=[
                    session_state, status_display, video_input_section, analysis_results_section, 
                    chatbot, summary_content, action_plan_content, blog_content, 
                    linkedin_content, tweet_content, video_player, video_info, transcript_display
                ]
            ).then(
                # Update token usage display after analysis
                fn=self.update_token_usage_display,
                inputs=[session_state],
                outputs=[total_tokens, prompt_tokens, completion_tokens, model_info, 
                        estimated_cost, cost_source, usage_breakdown]
            ).then(
                # Re-enable the analyze button
                fn=finish_analysis_ui_update,
                outputs=[analyze_btn]
            )
            
            # Chat event handlers
            
            # Handle chat input submission
            chat_submit_event = chat_submit.click(
                fn=self.handle_chat_submit,
                inputs=[chat_input, chatbot, session_state],
                outputs=[chat_input, chatbot, chat_input]
            )
            
            # Generate streaming response after submission
            chat_submit_event.then(
                fn=self.generate_chat_response,
                inputs=[chatbot, session_state],
                outputs=[chatbot, session_state]
            ).then(
                # Update token usage display after chat response
                fn=self.update_token_usage_display,
                inputs=[session_state],
                outputs=[total_tokens, prompt_tokens, completion_tokens, model_info, 
                        estimated_cost, cost_source, usage_breakdown]
            ).then(
                # Re-enable chat input after response
                fn=lambda: gr.update(interactive=True),
                outputs=[chat_input]
            )
            
            # Handle Enter key in chat input
            chat_input_event = chat_input.submit(
                fn=self.handle_chat_submit,
                inputs=[chat_input, chatbot, session_state],
                outputs=[chat_input, chatbot, chat_input]
            )
            
            # Generate streaming response after Enter
            chat_input_event.then(
                fn=self.generate_chat_response,
                inputs=[chatbot, session_state],
                outputs=[chatbot, session_state]
            ).then(
                # Update token usage display after chat response
                fn=self.update_token_usage_display,
                inputs=[session_state],
                outputs=[total_tokens, prompt_tokens, completion_tokens, model_info, 
                        estimated_cost, cost_source, usage_breakdown]
            ).then(
                # Re-enable chat input after response
                fn=lambda: gr.update(interactive=True),
                outputs=[chat_input]
            )
            
            # Handle chat reset
            chat_reset.click(
                fn=self.handle_chat_reset,
                inputs=[session_state],
                outputs=[chatbot, session_state, chat_input]
            )
            
            # Content generation event handlers
            
            # Action Plan generation
            action_plan_generate.click(
                fn=self.handle_action_plan_generate,
                inputs=[action_plan_instruction, session_state],
                outputs=[action_plan_content, session_state]
            ).then(
                # Update token usage display after content generation
                fn=self.update_token_usage_display,
                inputs=[session_state],
                outputs=[total_tokens, prompt_tokens, completion_tokens, model_info, 
                        estimated_cost, cost_source, usage_breakdown]
            )
            
            # Blog Post generation
            blog_generate.click(
                fn=self.handle_blog_generate,
                inputs=[blog_instruction, session_state],
                outputs=[blog_content, session_state]
            ).then(
                # Update token usage display after content generation
                fn=self.update_token_usage_display,
                inputs=[session_state],
                outputs=[total_tokens, prompt_tokens, completion_tokens, model_info, 
                        estimated_cost, cost_source, usage_breakdown]
            )
            
            # LinkedIn Post generation
            linkedin_generate.click(
                fn=self.handle_linkedin_generate,
                inputs=[linkedin_instruction, session_state],
                outputs=[linkedin_content, session_state]
            ).then(
                # Update token usage display after content generation
                fn=self.update_token_usage_display,
                inputs=[session_state],
                outputs=[total_tokens, prompt_tokens, completion_tokens, model_info, 
                        estimated_cost, cost_source, usage_breakdown]
            )
            
            # X Tweet generation
            tweet_generate.click(
                fn=self.handle_tweet_generate,
                inputs=[tweet_instruction, session_state],
                outputs=[tweet_content, session_state]
            ).then(
                # Update token usage display after content generation
                fn=self.update_token_usage_display,
                inputs=[session_state],
                outputs=[total_tokens, prompt_tokens, completion_tokens, model_info, 
                        estimated_cost, cost_source, usage_breakdown]
            )
            
            # Analysis control event handlers
            
            # New Analysis button
            new_analysis_btn.click(
                fn=self.handle_new_analysis,
                inputs=[session_state],
                outputs=[
                    session_state, youtube_url, video_input_section, analysis_results_section,
                    chatbot, summary_content, action_plan_content, blog_content,
                    linkedin_content, tweet_content, video_player, video_info, status_display
                ]
            )
            
            # Clear Cache button
            clear_cache_btn.click(
                fn=self.handle_clear_cache,
                inputs=[session_state],
                outputs=[session_state, status_display]
            )
            
            # Authentication event handlers
            
            # Show auth form
            auth_button.click(
                fn=self.show_auth_form,
                outputs=[auth_form, auth_button, cancel_auth_button, login_message, signup_message]
            )
            
            # Cancel auth form
            cancel_auth_button.click(
                fn=self.hide_auth_form,
                outputs=[
                    auth_form, auth_button, cancel_auth_button, login_email, 
                    login_password, signup_email, signup_password, signup_confirm,
                    login_message, signup_message
                ]
            )
            
            # Login
            login_button.click(
                fn=self.handle_login,
                inputs=[login_email, login_password, session_state],
                outputs=[
                    session_state, login_message, auth_status, auth_form, 
                    auth_button, logout_button, cancel_auth_button, user_stats
                ]
            )
            
            # Signup
            signup_button.click(
                fn=self.handle_signup,
                inputs=[signup_email, signup_password, signup_confirm, session_state],
                outputs=[
                    session_state, signup_message, auth_status, auth_form,
                    auth_button, logout_button, cancel_auth_button, user_stats
                ]
            )
            
            # Logout button
            logout_button.click(
                fn=self.handle_logout,
                inputs=[session_state],
                outputs=[session_state, auth_status, auth_button, logout_button, user_stats]
            )
            
            # Settings panel event handlers
            
            # AI Model selection
            model_dropdown.change(
                fn=self.handle_model_change,
                inputs=[model_dropdown, session_state],
                outputs=[session_state]
            ).then(
                # Update token usage display when model changes (for cost calculation)
                fn=self.update_token_usage_display,
                inputs=[session_state],
                outputs=[total_tokens, prompt_tokens, completion_tokens, model_info, 
                        estimated_cost, cost_source, usage_breakdown]
            )
            
            # Transcription model selection
            transcription_dropdown.change(
                fn=self.handle_transcription_model_change,
                inputs=[transcription_dropdown, session_state],
                outputs=[session_state]
            )
            
            # Temperature slider
            temperature_slider.change(
                fn=self.handle_temperature_change,
                inputs=[temperature_slider, session_state],
                outputs=[session_state]
            )
            
            # Cache setting checkbox
            use_cache_checkbox.change(
                fn=self.handle_cache_setting_change,
                inputs=[use_cache_checkbox, session_state],
                outputs=[session_state]
            )
            
            # Subtitle language selection
            subtitle_language.change(
                fn=self.handle_subtitle_language_change,
                inputs=[subtitle_language, session_state],
                outputs=[session_state]
            )
            
            # Transcript tab event handlers
            
            # Toggle transcript timestamps
            show_timestamps.change(
                fn=self.toggle_transcript_timestamps,
                inputs=[show_timestamps, session_state],
                outputs=[transcript_display]
            )
            
            # Translate transcript
            translate_btn.click(
                fn=self.handle_translate_transcript,
                inputs=[session_state],
                outputs=[session_state, translation_status]
            ).then(
                # Update transcript display after translation
                fn=self.toggle_transcript_timestamps,
                inputs=[show_timestamps, session_state],
                outputs=[transcript_display]
            )
            
            # Apply subtitles to video player
            apply_subtitles_btn.click(
                fn=self.handle_apply_subtitles,
                inputs=[session_state],
                outputs=[session_state, translation_status]
            )
            
            # Download SRT file
            download_srt_btn.click(
                fn=lambda session_state: self.handle_download_subtitle_file("srt", session_state),
                inputs=[session_state],
                outputs=[download_srt_file]
            )
            
            # Download VTT file
            download_vtt_btn.click(
                fn=lambda session_state: self.handle_download_subtitle_file("vtt", session_state),
                inputs=[session_state],
                outputs=[download_vtt_file]
            )
            
            # Update auth display and token usage on load
            interface.load(
                fn=self.update_auth_display,
                inputs=[session_state],
                outputs=[auth_status, auth_button, logout_button, user_stats]
            ).then(
                # Initialize token usage display on load
                fn=self.update_token_usage_display,
                inputs=[session_state],
                outputs=[total_tokens, prompt_tokens, completion_tokens, model_info, 
                        estimated_cost, cost_source, usage_breakdown]
            )
        
        return interface
    
    def launch(self, **kwargs):
        """Launch the Gradio application."""
        interface = self.create_interface()
        return interface.launch(**kwargs)


def main():
    """Main function to run the Gradio app."""
    # Configuration Check
    validate_config()
    
    # Services will be initialized when GradioWebApp is created
    
    # Create and run the app
    app = GradioWebApp()
    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        debug=True
    )


if __name__ == "__main__":
    main()