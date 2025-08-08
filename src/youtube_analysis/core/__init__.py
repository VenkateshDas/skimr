"""Core modules for YouTube analysis."""

from .cache_manager import CacheManager
from .config import config
from .llm_manager import LLMManager
from .youtube_client import YouTubeClient, VideoInfo
from .transcript_fetcher import (
    RobustTranscriptFetcher, 
    TranscriptResult, 
    TranscriptSource,
    LanguagePreference,
    TranscriptError,
    TranscriptUnavailableError,
    TranscriptTemporaryError,
    TranscriptRateLimitError
)
from ..utils.ssl_config import get_ssl_config, configure_ssl_for_development, reset_ssl_config

__all__ = [
    'CacheManager',
    'config', 
    'LLMManager',
    'YouTubeClient',
    'VideoInfo',
    'RobustTranscriptFetcher',
    'TranscriptResult',
    'TranscriptSource',
    'LanguagePreference',
    'TranscriptError',
    'TranscriptUnavailableError',
    'TranscriptTemporaryError',
    'TranscriptRateLimitError',
    'get_ssl_config',
    'configure_ssl_for_development',
    'reset_ssl_config'
]