import logging
import os
import sys
import colorlog
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Union

# Define log levels
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL
}

# Default log format
DEFAULT_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DEFAULT_COLOR_LOG_FORMAT = "%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Keep track of configured loggers
CONFIGURED_LOGGERS: Dict[str, logging.Logger] = {}

def ensure_log_dir() -> Path:
    """Create logs directory if it doesn't exist and return its path."""
    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir

def setup_logger(name: str, log_level: str = "INFO") -> logging.Logger:
    """
    Set up a logger with colorful console output.
    
    Args:
        name: The name of the logger
        log_level: The log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        
    Returns:
        A configured logger instance
    """
    # Get log level from environment variable if not provided
    log_level = log_level.upper()
    
    # Create logger
    logger = logging.getLogger(name)
    
    # Ensure log_level is valid
    if log_level in LOG_LEVELS:
        logger.setLevel(LOG_LEVELS[log_level])
    else:
        logger.setLevel(logging.INFO)
        logger.warning(f"Invalid log level: {log_level}. Using INFO instead.")
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Create console handler with color formatting
    console_handler = logging.StreamHandler()
    if log_level in LOG_LEVELS:
        console_handler.setLevel(LOG_LEVELS[log_level])
    else:
        console_handler.setLevel(logging.INFO)
    
    # Define color scheme
    colors = {
        'DEBUG': 'cyan',
        'INFO': 'green',
        'WARNING': 'yellow',
        'ERROR': 'red',
        'CRITICAL': 'red,bg_white',
    }
    
    # Create formatter with colors
    formatter = colorlog.ColoredFormatter(
        "%(log_color)s%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        log_colors=colors
    )
    
    # Add formatter to handler
    console_handler.setFormatter(formatter)
    
    # Add handler to logger
    logger.addHandler(console_handler)
    
    return logger

def get_log_level() -> str:
    """Get the log level from environment variable or use default."""
    return os.environ.get("LOG_LEVEL", "INFO").upper()

# Create a default logger for the package
default_logger = setup_logger("youtube_analysis", get_log_level())

def get_logger(name: str, log_level: Optional[str] = None) -> logging.Logger:
    """
    Get a logger with the specified name and log level.
    
    Args:
        name: The name of the logger
        log_level: The log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        
    Returns:
        A configured logger instance
    """
    # Get log level from environment variable if not provided
    if log_level is None:
        log_level = os.environ.get("LOG_LEVEL", "INFO")
    
    return setup_logger(name, log_level) 