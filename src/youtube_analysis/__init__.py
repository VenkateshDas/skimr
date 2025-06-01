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
from .analysis_v2 import run_analysis_v2, get_performance_stats
from .crew import YouTubeAnalysisCrew
from .chat import setup_chat_for_video
from .transcript import get_transcript_with_timestamps
from .ui_legacy import get_category_class, extract_youtube_thumbnail, load_css, setup_sidebar, create_welcome_message, setup_user_menu
from .core import CacheManager, LLMManager, YouTubeClient

# For backward compatibility, still export some utils
from .utils.youtube_utils import validate_youtube_url, get_cached_transcription, cache_transcription

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
    'run_analysis_v2',
    'run_direct_analysis',
    'extract_category',
    'get_performance_stats',
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
    
    # Core Components
    'CacheManager',
    'LLMManager', 
    'YouTubeClient',
    
    # Backward compatibility utilities
    'validate_youtube_url',
    'get_cached_transcription',
    'cache_transcription'
]

# Set up package-level logger
logger = get_logger(__name__)
