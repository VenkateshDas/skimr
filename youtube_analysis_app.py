#!/usr/bin/env python3
"""
YouTube Analysis App - A CrewAI implementation for analyzing YouTube videos
"""

import sys
import os
import argparse
import traceback
from typing import Optional, Dict, Any, Union, NoReturn

# Add the src directory to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from src.youtube_analysis.main import run, train
from src.youtube_analysis.utils.logging import get_logger, setup_logger

# Version information
__version__ = "1.0.0"

# Set up the root logger
logger = setup_logger("youtube_analysis_app")

def parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments.
    
    Returns:
        The parsed arguments.
    """
    parser = argparse.ArgumentParser(
        description="YouTube Analysis App - Analyze YouTube videos using CrewAI",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    # Main operation modes
    mode_group = parser.add_argument_group("Operation Modes")
    mode_group.add_argument(
        "--train", 
        type=int, 
        metavar="N",
        help="Train the crew for N iterations"
    )
    mode_group.add_argument(
        "--url", 
        type=str, 
        metavar="URL",
        help="Directly analyze a specific YouTube URL without prompting"
    )
    
    # Logging options
    log_group = parser.add_argument_group("Logging Options")
    log_group.add_argument(
        "--debug", 
        action="store_true", 
        help="Enable debug logging"
    )
    log_group.add_argument(
        "--log-to-file", 
        action="store_true", 
        help="Enable logging to file"
    )
    
    # Other options
    parser.add_argument(
        "--version", 
        action="version", 
        version=f"YouTube Analysis App v{__version__}"
    )
    
    return parser.parse_args()

def main() -> int:
    """
    Main entry point for the application.
    
    Returns:
        Exit code (0 for success, non-zero for errors).
    """
    logger.info("Starting YouTube Analysis App")
    
    args = parse_arguments()
    
    # Set debug logging if requested
    if args.debug:
        os.environ["LOG_LEVEL"] = "DEBUG"
        logger.info("Debug logging enabled")
    
    # Set file logging if requested
    if args.log_to_file:
        logger.info("File logging enabled")
        # Re-setup the logger with file logging enabled
        setup_logger("youtube_analysis_app", log_to_file=True)
    
    try:
        if args.train:
            if args.train <= 0:
                logger.error("Number of iterations must be positive")
                print("Error: Number of iterations must be positive")
                return 1
                
            logger.info(f"Training mode activated with {args.train} iterations")
            train(args.train)
        elif args.url:
            logger.info(f"Direct URL analysis mode activated for: {args.url}")
            # TODO: Implement direct URL analysis without prompting
            print(f"Analyzing URL: {args.url}")
            print("This feature is not yet implemented. Please run without --url to be prompted for a URL.")
            return 1
        else:
            logger.info("Analysis mode activated")
            run()
    except ValueError as e:
        logger.error(f"Value error: {str(e)}")
        print(f"Error: {str(e)}")
        return 1
    except ConnectionError as e:
        logger.error(f"Connection error: {str(e)}")
        print(f"Connection error: {str(e)}")
        print("Please check your internet connection and try again.")
        return 1
    except Exception as e:
        logger.critical(f"Unhandled exception in main: {str(e)}", exc_info=True)
        print(f"Critical error: {str(e)}")
        print("Check the logs for more details.")
        return 1
    
    logger.info("Application completed successfully")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        logger.warning("Application interrupted by user")
        print("\nApplication interrupted by user. Exiting...")
        sys.exit(130)
    except Exception as e:
        logger.critical(f"Unhandled exception: {str(e)}", exc_info=True)
        print(f"Critical error: {str(e)}")
        print("Check the logs for more details.")
        sys.exit(1)