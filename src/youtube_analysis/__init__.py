"""
YouTube Analysis Package

A comprehensive toolkit for analyzing YouTube videos, including transcript analysis,
content summarization, and interactive chat capabilities.
"""

__version__ = "0.1.0"

# Import commonly used modules to make them available when importing the package
from .utils.logging import get_logger
from .auth import init_auth_state, login, init_supabase, display_auth_ui, get_current_user, logout, require_auth, check_guest_usage
from .analysis import run_analysis, run_direct_analysis, extract_category
from .crew import YouTubeAnalysisCrew
from .chat import setup_chat_for_video
from .transcript import get_transcript_with_timestamps
from .ui import get_category_class, extract_youtube_thumbnail, load_css, setup_sidebar, create_welcome_message, setup_user_menu
from .utils.youtube_utils import (
    extract_video_id, 
    get_transcript, 
    get_video_info, 
    validate_youtube_url,
    get_cached_transcription,
    cache_transcription
)
from .utils.cache_utils import get_cached_analysis, cache_analysis, clear_analysis_cache

# Export these functions and classes
__all__ = [
    # Logging
    'get_logger',
    
    # Auth
    'init_auth_state',
    'login',
    'init_supabase',
    'display_auth_ui',
    'get_current_user',
    'logout',
    'require_auth',
    'check_guest_usage',
    
    # Analysis
    'run_analysis',
    'run_direct_analysis',
    'extract_category',
    'YouTubeAnalysisCrew',
    
    # Chat
    'setup_chat_for_video',
    
    # Transcript
    'get_transcript_with_timestamps',
    
    # UI
    'get_category_class',
    'extract_youtube_thumbnail',
    'load_css',
    'setup_sidebar',
    'create_welcome_message',
    'setup_user_menu',
    
    # YouTube Utilities
    'extract_video_id',
    'get_transcript',
    'get_video_info',
    'validate_youtube_url',
    'get_cached_transcription',
    'cache_transcription',
    
    # Cache Utilities
    'get_cached_analysis',
    'cache_analysis',
    'clear_analysis_cache'
]

# Set up package-level logger
logger = get_logger(__name__)
