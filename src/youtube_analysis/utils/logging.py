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

def setup_logger(
    name: str, 
    log_level: str = "INFO", 
    log_to_file: bool = False, 
    log_format: Optional[str] = None, 
    color_console: bool = True
) -> logging.Logger:
    """
    Set up a logger with the specified name and configuration.
    
    Args:
        name: The name of the logger.
        log_level: The log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_to_file: Whether to log to a file. Default is False.
        log_format: The log format.
        color_console: Whether to use colored output in the console.
        
    Returns:
        The configured logger.
    """
    # Check if this logger has already been configured
    if name in CONFIGURED_LOGGERS:
        return CONFIGURED_LOGGERS[name]
    
    # Get the log level
    level = LOG_LEVELS.get(log_level.upper(), logging.INFO)
    
    # Create a logger
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Clear any existing handlers
    logger.handlers = []
    
    # Prevent propagation to avoid duplicate logs
    logger.propagate = False
    
    # Set the log format
    file_formatter = logging.Formatter(log_format or DEFAULT_LOG_FORMAT)
    
    # Add console handler with optional color
    console_handler = logging.StreamHandler(sys.stdout)
    if color_console:
        # Color configuration
        color_formatter = colorlog.ColoredFormatter(
            DEFAULT_COLOR_LOG_FORMAT,
            log_colors={
                'DEBUG': 'cyan',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'red,bg_white',
            }
        )
        console_handler.setFormatter(color_formatter)
    else:
        console_handler.setFormatter(file_formatter)
    
    logger.addHandler(console_handler)
    
    # Add file handler if requested
    if log_to_file:
        log_dir = ensure_log_dir()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"{name}_{timestamp}.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    # Store the configured logger
    CONFIGURED_LOGGERS[name] = logger
    
    return logger

def get_log_level() -> str:
    """Get the log level from environment variable or use default."""
    return os.environ.get("LOG_LEVEL", "INFO").upper()

# Create a default logger for the package
default_logger = setup_logger("youtube_analysis", get_log_level())

def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the specified name.
    
    Args:
        name: The name of the logger.
        
    Returns:
        The configured logger.
    """
    full_name = f"youtube_analysis.{name}"
    return setup_logger(full_name, get_log_level()) 