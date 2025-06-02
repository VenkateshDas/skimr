"""
YouTube Analysis Package

A comprehensive toolkit for analyzing YouTube videos, including transcript analysis,
content summarization, and interactive chat capabilities.
"""

__version__ = "0.1.0"

# Import commonly used modules to make them available when importing the package
from .utils.logging import get_logger
from .services.auth_service import init_auth_state, login, init_supabase, display_auth_ui, get_current_user, logout, require_auth, check_guest_usage
from .ui.helpers import get_category_class, extract_youtube_thumbnail, load_css, get_skimr_logo_base64

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
    
    # UI
    'get_category_class',
    'extract_youtube_thumbnail',
    'load_css',
    'get_skimr_logo_base64',
    
    # Backward compatibility utilities
    'validate_youtube_url',
    'get_cached_transcription',
    'cache_transcription'
]

# Set up package-level logger
logger = get_logger(__name__)
