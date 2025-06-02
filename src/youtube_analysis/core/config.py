"""
Comprehensive Configuration System for YouTube Analysis Application.
All hardcoded values are centralized here and can be overridden via environment variables.
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass, field
from dotenv import load_dotenv
import logging

# Load environment variables from .env file
env_path = Path('.env')
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

# =============================================================================
# CORE APPLICATION SETTINGS
# =============================================================================

@dataclass
class AppConfig:
    """Core application configuration."""
    version: str = field(default_factory=lambda: os.getenv('APP_VERSION', '0.1.0'))
    debug: bool = field(default_factory=lambda: os.getenv('DEBUG', 'false').lower() == 'true')
    environment: str = field(default_factory=lambda: os.getenv('ENVIRONMENT', 'development'))

@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str = field(default_factory=lambda: os.getenv('LOG_LEVEL', 'INFO'))
    format: str = field(default_factory=lambda: os.getenv('LOG_FORMAT', '%(asctime)s [%(name)s] %(levelname)s: %(message)s'))
    date_format: str = field(default_factory=lambda: os.getenv('LOG_DATE_FORMAT', '%Y-%m-%d %H:%M:%S'))

# =============================================================================
# LLM CONFIGURATION
# =============================================================================

@dataclass
class LLMConfig:
    """LLM configuration settings."""
    # Default model settings
    default_model: str = field(default_factory=lambda: os.getenv('LLM_DEFAULT_MODEL', 'gpt-4.1-mini'))
    default_temperature: float = field(default_factory=lambda: float(os.getenv('LLM_DEFAULT_TEMPERATURE', '0.2')))
    default_max_tokens: Optional[int] = field(default_factory=lambda: int(os.getenv('LLM_DEFAULT_MAX_TOKENS', '0')) or None)
    default_timeout: int = field(default_factory=lambda: int(os.getenv('LLM_DEFAULT_TIMEOUT', '60')))
    
    # Available models for UI selection
    available_models: List[str] = field(default_factory=lambda: _parse_list_env('LLM_AVAILABLE_MODELS', [
        'gpt-4o-mini', 'gpt-4o', 'gpt-4-turbo', 'gpt-3.5-turbo',
        'gemini-2.0-flash', 'gemini-2.0-flash-lite', 'gemini-1.5-pro',
        'claude-3-5-sonnet', 'claude-3-haiku'
    ]))
    
    # Model cost estimates (per 1K tokens)
    model_costs: Dict[str, float] = field(default_factory=lambda: _parse_json_env('LLM_MODEL_COSTS', {
        'gpt-4o-mini': 0.00015,
        'gpt-4o': 0.005,
        'gpt-4-turbo': 0.003,
        'gpt-3.5-turbo': 0.0005,
        'gemini-2.0-flash': 0.0001,
        'gemini-2.0-flash-lite': 0.00005,
        'gemini-1.5-pro': 0.0025,
        'claude-3-5-sonnet': 0.003,
        'claude-3-haiku': 0.00025
    }))
    
    # Model descriptions for UI
    model_descriptions: Dict[str, str] = field(default_factory=lambda: _parse_json_env('LLM_MODEL_DESCRIPTIONS', {
        'gpt-4o-mini': 'Fast, cost-effective for most analyses',
        'gpt-4o': 'Most capable OpenAI model',
        'gpt-4-turbo': 'High performance with large context',
        'gpt-3.5-turbo': 'Fast and economical',
        'gemini-2.0-flash': 'Balanced performance and quality',
        'gemini-2.0-flash-lite': 'Ultra-fast responses',
        'gemini-1.5-pro': 'Advanced reasoning capabilities',
        'claude-3-5-sonnet': 'Excellent for analysis and writing',
        'claude-3-haiku': 'Fast and efficient'
    }))

# =============================================================================
# CACHE CONFIGURATION
# =============================================================================

@dataclass
class CacheConfig:
    """Cache configuration settings."""
    # Cache directories
    cache_dir: str = field(default_factory=lambda: os.getenv('CACHE_DIR', str(Path(__file__).parent.parent.parent.parent / 'transcript_cache')))
    analysis_cache_dir: str = field(default_factory=lambda: os.getenv('ANALYSIS_CACHE_DIR', str(Path(__file__).parent.parent.parent.parent / 'analysis_cache')))
    
    # Cache expiry settings
    expiry_days: int = field(default_factory=lambda: int(os.getenv('CACHE_EXPIRY_DAYS', '7')))
    max_cache_size_mb: int = field(default_factory=lambda: int(os.getenv('CACHE_MAX_SIZE_MB', '1000')))
    
    # Cache behavior
    enable_cache: bool = field(default_factory=lambda: os.getenv('ENABLE_CACHE', 'true').lower() == 'true')
    auto_cleanup: bool = field(default_factory=lambda: os.getenv('CACHE_AUTO_CLEANUP', 'true').lower() == 'true')

# =============================================================================
# NETWORK CONFIGURATION
# =============================================================================

@dataclass
class NetworkConfig:
    """Network and timeout configuration."""
    # HTTP timeouts
    http_timeout_total: int = field(default_factory=lambda: int(os.getenv('HTTP_TIMEOUT_TOTAL', '30')))
    http_timeout_connect: int = field(default_factory=lambda: int(os.getenv('HTTP_TIMEOUT_CONNECT', '10')))
    http_keepalive_timeout: int = field(default_factory=lambda: int(os.getenv('HTTP_KEEPALIVE_TIMEOUT', '30')))
    
    # Video download timeouts
    video_download_timeout: int = field(default_factory=lambda: int(os.getenv('VIDEO_DOWNLOAD_TIMEOUT', '300')))
    
    # Server settings
    server_port: int = field(default_factory=lambda: int(os.getenv('STREAMLIT_SERVER_PORT', '8501')))
    server_address: str = field(default_factory=lambda: os.getenv('STREAMLIT_SERVER_ADDRESS', '0.0.0.0'))

# =============================================================================
# USER AND AUTH CONFIGURATION
# =============================================================================

@dataclass
class AuthConfig:
    """Authentication and user configuration."""
    # Guest user limits
    max_guest_analyses: int = field(default_factory=lambda: int(os.getenv('MAX_GUEST_ANALYSES', '1')))
    
    # Authentication settings
    enable_auth: bool = field(default_factory=lambda: os.getenv('ENABLE_AUTH', 'true').lower() == 'true')
    session_timeout_hours: int = field(default_factory=lambda: int(os.getenv('SESSION_TIMEOUT_HOURS', '24')))
    
    # Supabase settings
    supabase_url: Optional[str] = field(default_factory=lambda: os.getenv('SUPABASE_URL'))
    supabase_key: Optional[str] = field(default_factory=lambda: os.getenv('SUPABASE_KEY'))

# =============================================================================
# API CONFIGURATION
# =============================================================================

@dataclass
class APIConfig:
    """External API configuration."""
    # YouTube API
    youtube_api_key: Optional[str] = field(default_factory=lambda: os.getenv('YOUTUBE_API_KEY'))
    enable_youtube_api: bool = field(default_factory=lambda: os.getenv('ENABLE_YOUTUBE_API', 'true').lower() == 'true')
    
    # OpenAI API
    openai_api_key: Optional[str] = field(default_factory=lambda: os.getenv('OPENAI_API_KEY'))
    
    # Anthropic API
    anthropic_api_key: Optional[str] = field(default_factory=lambda: os.getenv('ANTHROPIC_API_KEY'))
    
    # Google API
    google_api_key: Optional[str] = field(default_factory=lambda: os.getenv('GOOGLE_API_KEY'))
    gemini_api_key: Optional[str] = field(default_factory=lambda: os.getenv('GEMINI_API_KEY'))
    
    # Tavily API (for web search)
    tavily_api_key: Optional[str] = field(default_factory=lambda: os.getenv('TAVILY_API_KEY'))
    
    # Glama.ai API (for cost calculation)
    glama_api_key: Optional[str] = field(default_factory=lambda: os.getenv('GLAMA_API_KEY'))
    enable_dynamic_costs: bool = field(default_factory=lambda: os.getenv('ENABLE_DYNAMIC_COSTS', 'true').lower() == 'true')

# =============================================================================
# UI CONFIGURATION
# =============================================================================

@dataclass
class UIConfig:
    """User interface configuration."""
    # Default UI settings
    default_use_cache: bool = field(default_factory=lambda: os.getenv('UI_DEFAULT_USE_CACHE', 'true').lower() == 'true')
    default_use_optimized: bool = field(default_factory=lambda: os.getenv('UI_DEFAULT_USE_OPTIMIZED', 'true').lower() == 'true')
    default_analysis_types: List[str] = field(default_factory=lambda: _parse_list_env('UI_DEFAULT_ANALYSIS_TYPES', ['Summary & Classification']))
    
    # Temperature slider settings
    temperature_min: float = field(default_factory=lambda: float(os.getenv('UI_TEMPERATURE_MIN', '0.0')))
    temperature_max: float = field(default_factory=lambda: float(os.getenv('UI_TEMPERATURE_MAX', '1.0')))
    temperature_step: float = field(default_factory=lambda: float(os.getenv('UI_TEMPERATURE_STEP', '0.1')))
    
    # Page configuration
    page_title: str = field(default_factory=lambda: os.getenv('UI_PAGE_TITLE', 'Skimr Summarizer'))
    page_icon: str = field(default_factory=lambda: os.getenv('UI_PAGE_ICON', ':material/movie:'))
    layout: str = field(default_factory=lambda: os.getenv('UI_LAYOUT', 'wide'))
    sidebar_state: str = field(default_factory=lambda: os.getenv('UI_SIDEBAR_STATE', 'expanded'))

# =============================================================================
# CHAT CONFIGURATION
# =============================================================================

@dataclass
class ChatConfig:
    """Chat system configuration."""
    # Chat prompt templates
    chat_prompt_template: str = field(default_factory=lambda: os.getenv('CHAT_PROMPT_TEMPLATE', '''You are an AI assistant that helps users understand YouTube video content.
You have access to the transcript of a YouTube video titled "{video_title}" with the following description:

DESCRIPTION:
{video_description}

You can answer questions about this video and also handle general questions not related to the video.

For questions about the video content, use the YouTube_Video_Search tool to find relevant information in the transcript.
For questions about the video itself (URL, ID, title, description), use the YouTube_Video_Info tool.
If the user asks about a concept that is not clearly explained in the video, use the Tavily_Search tool to find relevant information online.
Also, if the question is not related to the video but if it is a valid question that can be answered by the internet, use the Tavily_Search tool to find relevant information online.
For general questions not related to the video, use your own knowledge to answer or use the Tavily_Search tool to find relevant information online.

Always be helpful, accurate, and concise in your responses.
If you don't know the answer to a question about the video, say so rather than making up information.
If you are searching the internet for information, then use clever search queries to get the most relevant information.

IMPORTANT: When answering questions about the video content, always include the timestamp citations from the transcript in your response. 
These timestamps indicate when in the video the information was mentioned. Format citations like [MM:SS] in your answers.

IMPORTANT: Use the chat history to maintain context of the conversation. Refer back to previous questions and answers when relevant.'''))
    
    welcome_template: str = field(default_factory=lambda: os.getenv('CHAT_WELCOME_TEMPLATE', '''Hello! I'm your AI assistant for the video "{video_title}". Ask me any questions about the content, and I'll do my best to answer based on the transcript. I'll include timestamps in my answers to help you locate information in the video.'''))
    
    # Chat behavior settings
    max_chat_history: int = field(default_factory=lambda: int(os.getenv('CHAT_MAX_HISTORY', '50')))
    enable_streaming: bool = field(default_factory=lambda: os.getenv('CHAT_ENABLE_STREAMING', 'true').lower() == 'true')

# =============================================================================
# ANALYSIS CONFIGURATION
# =============================================================================

@dataclass
class AnalysisConfig:
    """Analysis workflow configuration."""
    # Available analysis types
    available_analysis_types: List[str] = field(default_factory=lambda: _parse_list_env('ANALYSIS_AVAILABLE_TYPES', [
        'Summary & Classification',
        'Action Plan',
        'Blog Post',
        'LinkedIn Post',
        'X Tweet'
    ]))
    
    # Content generation settings
    enable_concurrent_generation: bool = field(default_factory=lambda: os.getenv('ANALYSIS_ENABLE_CONCURRENT', 'true').lower() == 'true')
    max_concurrent_tasks: int = field(default_factory=lambda: int(os.getenv('ANALYSIS_MAX_CONCURRENT_TASKS', '3')))
    
    # Progress tracking
    enable_progress_tracking: bool = field(default_factory=lambda: os.getenv('ANALYSIS_ENABLE_PROGRESS', 'true').lower() == 'true')

# =============================================================================
# MAIN CONFIGURATION CLASS
# =============================================================================

@dataclass
class Config:
    """Main configuration class that aggregates all configuration sections."""
    app: AppConfig = field(default_factory=AppConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    network: NetworkConfig = field(default_factory=NetworkConfig)
    auth: AuthConfig = field(default_factory=AuthConfig)
    api: APIConfig = field(default_factory=APIConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    chat: ChatConfig = field(default_factory=ChatConfig)
    analysis: AnalysisConfig = field(default_factory=AnalysisConfig)

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def _parse_list_env(env_var: str, default: List[str]) -> List[str]:
    """Parse a comma-separated environment variable into a list."""
    value = os.getenv(env_var)
    if value:
        return [item.strip() for item in value.split(',') if item.strip()]
    return default

def _parse_json_env(env_var: str, default: Dict[str, Any]) -> Dict[str, Any]:
    """Parse a JSON environment variable into a dictionary."""
    value = os.getenv(env_var)
    if value:
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            logging.warning(f"Invalid JSON in environment variable {env_var}, using default")
    return default

# =============================================================================
# GLOBAL CONFIGURATION INSTANCE
# =============================================================================

# Create global configuration instance
config = Config()

# =============================================================================
# BACKWARD COMPATIBILITY EXPORTS
# =============================================================================

# Export commonly used values for backward compatibility
APP_VERSION = config.app.version
YOUTUBE_API_KEY = config.api.youtube_api_key
SUPABASE_URL = config.auth.supabase_url
SUPABASE_KEY = config.auth.supabase_key
MAX_GUEST_ANALYSES = config.auth.max_guest_analyses
CACHE_EXPIRY_DAYS = config.cache.expiry_days
CACHE_DIR = config.cache.cache_dir
LOG_LEVEL = config.logging.level
CHAT_PROMPT_TEMPLATE = config.chat.chat_prompt_template
CHAT_WELCOME_TEMPLATE = config.chat.welcome_template

# =============================================================================
# CONFIGURATION VALIDATION
# =============================================================================

def validate_config() -> Tuple[bool, List[str]]:
    """
    Validate that required configuration variables are set.
    
    Returns:
        Tuple of (is_valid, missing_vars)
    """
    required_vars = []
    missing_vars = []
    
    # Check for YouTube API key if analysis is enabled
    if config.api.enable_youtube_api and not config.api.youtube_api_key:
        missing_vars.append('YOUTUBE_API_KEY')
    
    # Check for Supabase credentials if auth is enabled
    if config.auth.enable_auth:
        if not config.auth.supabase_url:
            missing_vars.append('SUPABASE_URL')
        if not config.auth.supabase_key:
            missing_vars.append('SUPABASE_KEY')
    
    # Check for at least one LLM API key
    llm_keys = [
        config.api.openai_api_key,
        config.api.anthropic_api_key,
        config.api.google_api_key or config.api.gemini_api_key
    ]
    if not any(llm_keys):
        missing_vars.append('At least one LLM API key (OPENAI_API_KEY, ANTHROPIC_API_KEY, or GOOGLE_API_KEY/GEMINI_API_KEY)')
    
    return len(missing_vars) == 0, missing_vars

def setup_logging():
    """Configure logging for the application."""
    logging.basicConfig(
        level=getattr(logging, config.logging.level),
        format=config.logging.format,
        datefmt=config.logging.date_format
    )

def get_model_cost(model_name: str) -> float:
    """Get the cost per 1K tokens for a model."""
    # Check if dynamic costs are enabled and we have an API key
    if config.api.enable_dynamic_costs and config.api.glama_api_key:
        try:
            # Import here to avoid circular imports
            from ..services.cost_service import get_model_cost_per_1k
            return get_model_cost_per_1k(model_name)
        except ImportError:
            # Fall back to static costs if cost service isn't available
            pass
    
    return config.llm.model_costs.get(model_name, 0.0001)  # Default fallback cost

def get_model_description(model_name: str) -> str:
    """Get the description for a model."""
    return config.llm.model_descriptions.get(model_name, "AI Language Model")

def is_model_available(model_name: str) -> bool:
    """Check if a model is in the available models list."""
    return model_name in config.llm.available_models

def get_default_settings() -> Dict[str, Any]:
    """Get default settings for the application."""
    return {
        "model": config.llm.default_model,
        "temperature": config.llm.default_temperature,
        "use_cache": config.ui.default_use_cache,
        "use_optimized": config.ui.default_use_optimized,
        "analysis_types": config.ui.default_analysis_types.copy()
    }

# =============================================================================
# ENVIRONMENT CONFIGURATION HELPERS
# =============================================================================

def create_env_template() -> str:
    """Create a template .env file with all available configuration options."""
    template = """# YouTube Analysis Application Configuration
# Copy this file to .env and configure your settings

# =============================================================================
# CORE APPLICATION SETTINGS
# =============================================================================
APP_VERSION=0.1.0
DEBUG=false
ENVIRONMENT=development

# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================
LOG_LEVEL=INFO
LOG_FORMAT=%(asctime)s [%(name)s] %(levelname)s: %(message)s
LOG_DATE_FORMAT=%Y-%m-%d %H:%M:%S

# =============================================================================
# LLM CONFIGURATION
# =============================================================================
LLM_DEFAULT_MODEL=gpt-4o-mini
LLM_DEFAULT_TEMPERATURE=0.2
LLM_DEFAULT_MAX_TOKENS=0
LLM_DEFAULT_TIMEOUT=60

# Available models (comma-separated)
LLM_AVAILABLE_MODELS=gpt-4o-mini,gpt-4o,gpt-4-turbo,gpt-3.5-turbo,gemini-2.0-flash,gemini-2.0-flash-lite,gemini-1.5-pro,claude-3-5-sonnet,claude-3-haiku

# Model costs (JSON format, per 1K tokens)
# LLM_MODEL_COSTS={"gpt-4o-mini": 0.00015, "gpt-4o": 0.005, "gemini-2.0-flash": 0.0001}

# =============================================================================
# CACHE CONFIGURATION
# =============================================================================
CACHE_EXPIRY_DAYS=7
CACHE_MAX_SIZE_MB=1000
ENABLE_CACHE=true
CACHE_AUTO_CLEANUP=true
# CACHE_DIR=./transcript_cache
# ANALYSIS_CACHE_DIR=./analysis_cache

# =============================================================================
# NETWORK CONFIGURATION
# =============================================================================
HTTP_TIMEOUT_TOTAL=30
HTTP_TIMEOUT_CONNECT=10
HTTP_KEEPALIVE_TIMEOUT=30
VIDEO_DOWNLOAD_TIMEOUT=300
STREAMLIT_SERVER_PORT=8501
STREAMLIT_SERVER_ADDRESS=0.0.0.0

# =============================================================================
# USER AND AUTH CONFIGURATION
# =============================================================================
MAX_GUEST_ANALYSES=1
ENABLE_AUTH=true
SESSION_TIMEOUT_HOURS=24

# Supabase settings (required if ENABLE_AUTH=true)
SUPABASE_URL=your_supabase_url_here
SUPABASE_KEY=your_supabase_key_here

# =============================================================================
# API KEYS
# =============================================================================
# YouTube API (required if ENABLE_YOUTUBE_API=true)
YOUTUBE_API_KEY=your_youtube_api_key_here
ENABLE_YOUTUBE_API=true

# LLM API Keys (at least one required)
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
GOOGLE_API_KEY=your_google_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here

# Web search API
TAVILY_API_KEY=your_tavily_api_key_here

# Cost calculation API
GLAMA_API_KEY=your_glama_api_key_here
ENABLE_DYNAMIC_COSTS=true

# =============================================================================
# UI CONFIGURATION
# =============================================================================
UI_DEFAULT_USE_CACHE=true
UI_DEFAULT_USE_OPTIMIZED=true
UI_DEFAULT_ANALYSIS_TYPES=Summary & Classification
UI_TEMPERATURE_MIN=0.0
UI_TEMPERATURE_MAX=1.0
UI_TEMPERATURE_STEP=0.1
UI_PAGE_TITLE=Skimr Summarizer
UI_PAGE_ICON=:material/movie:
UI_LAYOUT=wide
UI_SIDEBAR_STATE=expanded

# =============================================================================
# CHAT CONFIGURATION
# =============================================================================
CHAT_MAX_HISTORY=50
CHAT_ENABLE_STREAMING=true

# =============================================================================
# ANALYSIS CONFIGURATION
# =============================================================================
ANALYSIS_AVAILABLE_TYPES=Summary & Classification,Action Plan,Blog Post,LinkedIn Post,X Tweet
ANALYSIS_ENABLE_CONCURRENT=true
ANALYSIS_MAX_CONCURRENT_TASKS=3
ANALYSIS_ENABLE_PROGRESS=true
"""
    return template

def print_config_summary():
    """Print a summary of the current configuration."""
    print("=== YouTube Analysis Application Configuration ===")
    print(f"App Version: {config.app.version}")
    print(f"Environment: {config.app.environment}")
    print(f"Debug Mode: {config.app.debug}")
    print(f"Default Model: {config.llm.default_model}")
    print(f"Available Models: {len(config.llm.available_models)}")
    print(f"Cache Enabled: {config.cache.enable_cache}")
    print(f"Auth Enabled: {config.auth.enable_auth}")
    print(f"Max Guest Analyses: {config.auth.max_guest_analyses}")
    print("=" * 50) 