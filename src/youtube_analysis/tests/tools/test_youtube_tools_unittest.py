#!/usr/bin/env python3
"""
Unit tests for the YouTube transcription tool.
"""

import unittest
import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../')))

from src.youtube_analysis.tools.youtube_tools import YouTubeTranscriptionTool
from src.youtube_analysis.utils.logging import setup_logger

# Set up logger
logger = setup_logger("test_youtube_tools_unittest", log_level="DEBUG")

class TestYouTubeTools(unittest.TestCase):
    """Test cases for the YouTube transcription tool."""
    
    def setUp(self):
        """Set up the test environment."""
        self.tool = YouTubeTranscriptionTool()
        self.test_urls = [
            "https://www.youtube.com/watch?v=TCGXT7ySco8",
            "https://youtu.be/TCGXT7ySco8",
        ]
    
    def test_extract_video_id_standard_url(self):
        """Test extracting video ID from a standard YouTube URL."""
        url = "https://www.youtube.com/watch?v=TCGXT7ySco8"
        video_id = self.tool._extract_video_id(url)
        self.assertEqual(video_id, "TCGXT7ySco8")
    
    def test_extract_video_id_short_url(self):
        """Test extracting video ID from a short YouTube URL."""
        url = "https://youtu.be/TCGXT7ySco8"
        video_id = self.tool._extract_video_id(url)
        self.assertEqual(video_id, "TCGXT7ySco8")
    
    def test_extract_video_id_invalid_url(self):
        """Test extracting video ID from an invalid URL."""
        url = "https://example.com"
        with self.assertRaises(ValueError):
            self.tool._extract_video_id(url)
    
    def test_extract_video_id_malformed_url(self):
        """Test extracting video ID from a malformed YouTube URL."""
        url = "https://www.youtube.com/watch"
        with self.assertRaises(ValueError):
            self.tool._extract_video_id(url)
    
    @unittest.skip("Skipping transcription test to avoid API calls during automated testing")
    def test_fetch_transcription(self):
        """Test fetching transcription from a YouTube video."""
        url = "https://www.youtube.com/watch?v=TCGXT7ySco8"
        transcription = self.tool._run(url)
        self.assertNotIn("Error fetching transcription", transcription)
        self.assertTrue(len(transcription) > 0)

if __name__ == "__main__":
    unittest.main() 