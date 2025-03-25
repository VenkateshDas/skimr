"""Configuration settings for the YouTube Analyzer app."""

import os
from pathlib import Path
from dotenv import load_dotenv
import logging

# Load environment variables from .env file
env_path = Path('.env')
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

# YouTube API settings
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')

# Supabase settings
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

# Cache settings
CACHE_EXPIRY_DAYS = int(os.getenv('CACHE_EXPIRY_DAYS', '7'))
CACHE_DIR = os.getenv('CACHE_DIR', os.path.join(os.getcwd(), 'transcript_cache'))

# Logging settings
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# App settings
APP_VERSION = os.getenv('APP_VERSION', '0.1.0')

def validate_config():
    """
    Validate that required configuration variables are set.
    
    Returns:
        Tuple of (is_valid, missing_vars)
    """
    required_vars = []
    missing_vars = []
    
    # Check for YouTube API key if analysis is enabled
    if os.getenv('ENABLE_YOUTUBE_API', 'true').lower() == 'true':
        required_vars.append('YOUTUBE_API_KEY')
    
    # Check for Supabase credentials if auth is enabled
    if os.getenv('ENABLE_AUTH', 'true').lower() == 'true':
        required_vars.extend(['SUPABASE_URL', 'SUPABASE_KEY'])
    
    # Check which required variables are missing
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    return len(missing_vars) == 0, missing_vars

def setup_logging():
    """Configure logging for the application."""
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL),
        format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ) 