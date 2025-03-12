#!/usr/bin/env python3
"""
YouTube Analysis App - A CrewAI implementation for analyzing YouTube videos
"""

import sys
import os
import argparse
import traceback
import json
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
    
    # Output options
    output_group = parser.add_argument_group("Output Options")
    output_group.add_argument(
        "--output-file",
        type=str,
        help="Save analysis results to a JSON file"
    )
    output_group.add_argument(
        "--pretty-print",
        action="store_true",
        help="Pretty print the analysis results"
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

def analyze_url(url: str) -> int:
    """
    Analyze a specific YouTube URL.
    
    Args:
        url: The YouTube URL to analyze.
        
    Returns:
        Exit code (0 for success, non-zero for errors).
    """
    logger.info(f"Analyzing URL: {url}")
    print(f"Analyzing URL: {url}")
    
    # Monkey patch the input function to return the URL
    import builtins
    original_input = builtins.input
    builtins.input = lambda _: url
    
    try:
        # Run the analysis
        results, error = run()
        
        # Restore original input function
        builtins.input = original_input
        
        if error:
            logger.error(f"Analysis failed: {error}")
            print(f"Analysis failed: {error}")
            return 1
        
        logger.info("Analysis completed successfully")
        return 0
    except Exception as e:
        # Restore original input function
        builtins.input = original_input
        
        logger.error(f"Error analyzing URL: {str(e)}", exc_info=True)
        print(f"Error analyzing URL: {str(e)}")
        return 1
    finally:
        # Ensure original input function is restored
        builtins.input = original_input

def save_results_to_file(results: Dict[str, Any], filename: str, pretty: bool = False) -> bool:
    """
    Save analysis results to a JSON file.
    
    Args:
        results: The analysis results.
        filename: The filename to save to.
        pretty: Whether to pretty-print the JSON.
        
    Returns:
        True if successful, False otherwise.
    """
    try:
        with open(filename, 'w') as f:
            if pretty:
                json.dump(results, f, indent=2)
            else:
                json.dump(results, f)
        logger.info(f"Results saved to {filename}")
        print(f"Results saved to {filename}")
        return True
    except Exception as e:
        logger.error(f"Error saving results to file: {str(e)}", exc_info=True)
        print(f"Error saving results to file: {str(e)}")
        return False

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
            return 0
        elif args.url:
            logger.info(f"Direct URL analysis mode activated for: {args.url}")
            
            # Set the URL in the environment for other components
            os.environ["YOUTUBE_URL"] = args.url
            
            # Analyze the URL
            result_code = analyze_url(args.url)
            
            # If analysis was successful and output file is specified, save results
            if result_code == 0 and args.output_file:
                # We need to run again to get the results
                import builtins
                original_input = builtins.input
                builtins.input = lambda _: args.url
                
                try:
                    results, _ = run()
                    if results:
                        save_results_to_file(results, args.output_file, args.pretty_print)
                finally:
                    builtins.input = original_input
            
            return result_code
        else:
            logger.info("Analysis mode activated")
            results, error = run()
            
            if error:
                logger.error(f"Analysis failed: {error}")
                return 1
                
            # If output file is specified, save results
            if args.output_file and results:
                save_results_to_file(results, args.output_file, args.pretty_print)
                
            return 0
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