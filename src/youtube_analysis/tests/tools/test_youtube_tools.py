#!/usr/bin/env python3
"""
Test script for the YouTube transcription tool.
"""

import sys
import os
import argparse

# Add the src directory to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../')))

from src.youtube_analysis.tools.youtube_tools import YouTubeTranscriptionTool
from src.youtube_analysis.utils.logging import setup_logger

# Set up logger
logger = setup_logger("test_youtube_tools", log_level="DEBUG")

def test_url_extraction(url):
    """Test the URL extraction functionality."""
    tool = YouTubeTranscriptionTool()
    try:
        video_id = tool._extract_video_id(url)
        logger.info(f"Successfully extracted video ID: {video_id}")
        return video_id
    except Exception as e:
        logger.error(f"Failed to extract video ID: {str(e)}")
        return None

def test_transcription_fetch(url):
    """Test the transcription fetching functionality."""
    tool = YouTubeTranscriptionTool()
    try:
        transcription = tool._run(url)
        if "Error fetching transcription" in transcription:
            logger.error(f"Failed to fetch transcription: {transcription}")
            return None
        
        # Print a preview of the transcription
        preview = transcription[:200] + "..." if len(transcription) > 200 else transcription
        logger.info(f"Successfully fetched transcription. Preview: {preview}")
        return transcription
    except Exception as e:
        logger.error(f"Failed to fetch transcription: {str(e)}")
        return None

def main():
    """Main function to run the tests."""
    parser = argparse.ArgumentParser(description="Test YouTube Transcription Tool")
    parser.add_argument("--url", type=str, help="YouTube URL to test")
    parser.add_argument("--extract-only", action="store_true", help="Only test URL extraction, not transcription fetching")
    args = parser.parse_args()
    
    # Test URLs
    test_urls = [
        "https://www.youtube.com/watch?v=TCGXT7ySco8",
        "https://youtu.be/TCGXT7ySco8",
    ]
    
    if args.url:
        test_urls = [args.url]
    
    logger.info(f"Testing {len(test_urls)} URLs")
    
    for url in test_urls:
        logger.info(f"Testing URL: {url}")
        
        # Test URL extraction
        video_id = test_url_extraction(url)
        if not video_id:
            logger.error(f"URL extraction test failed for: {url}")
            continue
        
        # Test transcription fetching if not extract-only
        if not args.extract_only:
            transcription = test_transcription_fetch(url)
            if not transcription:
                logger.error(f"Transcription fetching test failed for: {url}")
                continue
            
            logger.info(f"All tests passed for URL: {url}")
        else:
            logger.info(f"URL extraction test passed for: {url}")
    
    logger.info("Testing completed")

if __name__ == "__main__":
    main()