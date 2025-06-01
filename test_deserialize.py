#!/usr/bin/env python3
"""Simple test script to validate the deserialization fixes."""

import logging
import sys
import asyncio
import json
from src.youtube_analysis.models import AnalysisResult, VideoData
from src.youtube_analysis.repositories import CacheRepository
from src.youtube_analysis.service_factory import get_service_factory
from src.youtube_analysis.utils.logging import get_logger

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = get_logger("test_script")

async def test_deserialize_analysis_result():
    """Test deserializing an AnalysisResult."""
    # Create a minimal valid AnalysisResult dict
    data = {
        "video_id": "test123",
        "youtube_url": "https://youtu.be/test123",
        "status": "completed",
        "created_at": "2023-01-01T00:00:00",
        "task_outputs": {
            "summary": {
                "task_name": "summary",
                "content": "Test content",
                "status": "completed"
            }
        }
    }
    
    try:
        # Test deserializing from dict
        result = AnalysisResult.from_dict(data)
        logger.info(f"Successfully deserialized AnalysisResult: {result.video_id}")
        
        # Test with string data (invalid case)
        try:
            string_data = json.dumps(data)
            repository = get_service_factory().get_cache_repository()
            await repository.smart_cache.set_with_ttl("analysis", f"analysis_test123", string_data)
            result = await repository.get_analysis_result("test123")
            if result:
                logger.info(f"Successfully retrieved analysis from string data: {result.video_id}")
            else:
                logger.error("Failed to retrieve analysis from string data")
        except Exception as e:
            logger.error(f"Error testing with string data: {str(e)}")
    
    except Exception as e:
        logger.error(f"Error in test_deserialize_analysis_result: {str(e)}")
        import traceback
        traceback.print_exc()

async def test_deserialize_video_data():
    """Test deserializing a VideoData object."""
    # Create a minimal valid VideoData dict
    data = {
        "video_id": "test123",
        "title": "Test Video",
        "description": "Test description",
        "transcript": "This is a test transcript.",
        "transcript_segments": [
            {"text": "This is a test", "start": 0.0, "duration": 1.0}
        ]
    }
    
    try:
        # Test deserializing directly
        repository = get_service_factory().get_cache_repository()
        await repository.smart_cache.set_with_ttl("video_data", "test123", data)
        result = await repository.get_video_data("test123")
        
        if result:
            logger.info(f"Successfully retrieved video data: {result.video_id if hasattr(result, 'video_id') else 'unknown'}")
        else:
            logger.error("Failed to retrieve video data")
            
    except Exception as e:
        logger.error(f"Error in test_deserialize_video_data: {str(e)}")
        import traceback
        traceback.print_exc()

async def main():
    """Run the tests."""
    logger.info("Starting deserialization tests...")
    await test_deserialize_analysis_result()
    await test_deserialize_video_data()
    logger.info("Tests completed!")

if __name__ == "__main__":
    asyncio.run(main()) 