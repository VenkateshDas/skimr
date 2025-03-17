# YouTube Analysis Crew
# A CrewAI implementation for analyzing YouTube videos

"""YouTube Analysis module for analyzing YouTube videos."""

import time
from .crew import YouTubeAnalysisCrew
from .analysis import run_analysis, run_direct_analysis, extract_category
from .chat import setup_chat_for_video, create_vectorstore, create_agent_graph
from .transcript import get_transcript_with_timestamps
from .ui import get_category_class, extract_youtube_thumbnail, load_css
from .utils.cache_utils import (
    get_cached_analysis, 
    cache_analysis,
    clear_analysis_cache
)
from .utils.youtube_utils import get_transcript_with_timestamps
from typing import Tuple, Optional, Dict, Any
from .utils.logging import get_logger

# Configure logging
logger = get_logger("youtube_analysis")

__all__ = [
    'YouTubeAnalysisCrew',
    'run_analysis',
    'run_direct_analysis',
    'extract_category',
    'setup_chat_for_video',
    'create_vectorstore',
    'create_agent_graph',
    'get_transcript_with_timestamps',
    'get_category_class',
    'extract_youtube_thumbnail',
    'load_css',
    'get_cached_analysis',
    'cache_analysis',
    'clear_analysis_cache'
]

def extract_category(transcript):
    """
    Extract the category of a video based on its transcript.
    
    Args:
        transcript: The video transcript
    
    Returns:
        Category string
    """
    # This is a placeholder. In a real implementation, this would use
    # an AI model to categorize the content based on the transcript.
    categories = [
        "Technology", "Business", "Education", "Entertainment",
        "Science", "Health", "Politics", "Sports", "Travel"
    ]
    import random
    return random.choice(categories)

def setup_chat_for_video(youtube_url, transcript, transcript_list=None):
    """
    Set up a chat interface for a video.
    
    Args:
        youtube_url: YouTube URL
        transcript: Video transcript
        transcript_list: Optional list of transcript items with timestamps
    
    Returns:
        Chat details dictionary
    """
    # This is a placeholder. In a real implementation, this would
    # initialize a chat agent with the video context.
    from .utils.youtube_utils import extract_video_id, get_video_info
    
    video_id = extract_video_id(youtube_url)
    if not video_id:
        return None
    
    video_info = get_video_info(youtube_url)
    if not video_info:
        video_info = {
            'video_id': video_id,
            'title': f"YouTube Video ({video_id})",
            'description': "Video description unavailable.",
            'url': youtube_url
        }
    
    return {
        "agent": None,
        "thread_id": "thread_" + video_id,
        "video_id": video_id,
        "youtube_url": youtube_url,
        "title": video_info.get('title', f"YouTube Video ({video_id})"),
        "description": video_info.get('description', "No description available"),
        "has_timestamps": transcript_list is not None
    }

def get_cached_analysis(video_id):
    """
    Get cached analysis for a video.
    
    Args:
        video_id: YouTube video ID
    
    Returns:
        Cached analysis or None
    """
    # Use the actual implementation from cache_utils.py
    from .utils.cache_utils import get_cached_analysis as get_cached_analysis_util
    return get_cached_analysis_util(video_id)

def cache_analysis(video_id, analysis):
    """
    Cache analysis for a video.
    
    Args:
        video_id: YouTube video ID
        analysis: Analysis results
    
    Returns:
        Success boolean
    """
    # Use the actual implementation from cache_utils.py
    from .utils.cache_utils import cache_analysis as cache_analysis_util
    return cache_analysis_util(video_id, analysis)

def clear_analysis_cache(video_id=None):
    """
    Clear analysis cache.
    
    Args:
        video_id: YouTube video ID (optional, if None, clear all)
    
    Returns:
        Success boolean
    """
    # Use the actual implementation from cache_utils.py
    from .utils.cache_utils import clear_analysis_cache as clear_analysis_cache_util
    return clear_analysis_cache_util(video_id)

def run_analysis(youtube_url: str, progress_callback=None, status_callback=None, use_cache=True) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Run the YouTube video analysis.
    
    Args:
        youtube_url: The URL of the YouTube video to analyze
        progress_callback: Optional callback function to update progress
        status_callback: Optional callback function to update status
        use_cache: Whether to use cached analysis results if available
        
    Returns:
        A tuple containing:
        - The analysis results (or None if error)
        - An error message (or None if successful)
    """
    from .utils.youtube_utils import extract_video_id, get_transcript, get_video_info
    
    try:
        # Extract video ID
        video_id = extract_video_id(youtube_url)
        if not video_id:
            return None, "Could not extract video ID from URL"
        
        # Check if we have cached analysis results
        if use_cache:
            cached_results = get_cached_analysis(video_id)
            if cached_results:
                # Add is_cached flag to indicate this is from cache
                cached_results["is_cached"] = True
                
                # Try to recreate chat details if they're missing or incomplete
                if "chat_details" not in cached_results or cached_results["chat_details"] is None or "agent" not in cached_results["chat_details"] or cached_results["chat_details"]["agent"] is None:
                    try:
                        # Get transcript - handle potential format issues
                        try:
                            transcript = get_transcript(youtube_url)
                        except Exception as transcript_error:
                            logger.warning(f"Error getting transcript for cached analysis: {str(transcript_error)}")
                            # If there's a transcript in the cached results, use that
                            if "transcript" in cached_results and cached_results["transcript"]:
                                transcript = cached_results["transcript"]
                                logger.info("Using transcript from cached results")
                            else:
                                # If we can't get a transcript, we can't recreate the chat agent
                                logger.error("Cannot recreate chat agent without transcript")
                                return cached_results, None
                        
                        # Get video info
                        video_info = get_video_info(youtube_url)
                        if video_info:
                            # Try to create a basic chat setup without requiring transcript
                            # This avoids the error with transcript formatting
                            chat_details = {
                                "video_id": video_id,
                                "youtube_url": youtube_url,
                                "title": video_info.get("title", f"YouTube Video ({video_id})"),
                                "description": video_info.get("description", "No description available"),
                                "agent": None,  # Will be created by the chat.py module
                                "thread_id": f"thread_{video_id}_{int(time.time())}",
                                "has_timestamps": False,
                                "error": "Chat agent could not be recreated from cache"
                            }
                            
                            # Try to import the chat module and create a proper agent if possible
                            try:
                                from .chat import create_agent_graph, create_vectorstore
                                
                                # Try to get transcript with timestamps
                                try:
                                    from .transcript import get_transcript_with_timestamps
                                    _, transcript_list = get_transcript_with_timestamps(youtube_url)
                                except Exception as ts_error:
                                    logger.warning(f"Error getting transcript with timestamps: {str(ts_error)}")
                                    transcript_list = None
                                
                                # Create vector store and agent
                                vectorstore = create_vectorstore(transcript, transcript_list)
                                
                                # Create video metadata
                                video_metadata = {
                                    "video_id": video_id,
                                    "youtube_url": youtube_url,
                                    "title": video_info.get("title", f"YouTube Video ({video_id})"),
                                    "description": video_info.get("description", "No description available")
                                }
                                
                                # Create agent
                                has_timestamps = transcript_list is not None
                                agent = create_agent_graph(vectorstore, video_metadata, has_timestamps)
                                
                                # Update chat details
                                chat_details["agent"] = agent
                                chat_details["has_timestamps"] = has_timestamps
                                chat_details.pop("error", None)  # Remove error if successful
                                
                                logger.info("Successfully recreated chat agent for cached analysis")
                            except Exception as e:
                                logger.error(f"Error creating agent for cached analysis: {str(e)}")
                                
                            # Add chat details to cached results
                            cached_results["chat_details"] = chat_details
                        else:
                            logger.warning("Could not get video info for recreating chat details")
                    except Exception as e:
                        logger.error(f"Error recreating chat details: {str(e)}")
                
                return cached_results, None
        
        # Get video info
        if progress_callback:
            progress_callback(10)
        if status_callback:
            status_callback("Fetching video information")
        
        video_info = get_video_info(youtube_url)
        if not video_info:
            return None, "Could not fetch video information"
        
        # Get transcript
        if progress_callback:
            progress_callback(30)
        if status_callback:
            status_callback("Fetching video transcript")
        
        try:
            transcript = get_transcript(youtube_url)
        except Exception as e:
            logger.error(f"Error getting transcript: {str(e)}")
            return None, f"Could not fetch transcript: {str(e)}"
        
        # Extract category
        if progress_callback:
            progress_callback(50)
        if status_callback:
            status_callback("Categorizing video content")
        
        category = extract_category(transcript)
        
        # Simulate analysis tasks
        if progress_callback:
            progress_callback(70)
        if status_callback:
            status_callback("Analyzing video content")
        
        # Placeholder for actual analysis
        time.sleep(2)  # Simulate processing time
        
        # Create chat setup
        if progress_callback:
            progress_callback(90)
        if status_callback:
            status_callback("Setting up chat interface")
        
        # Try to get transcript with timestamps
        try:
            from .transcript import get_transcript_with_timestamps
            _, transcript_list = get_transcript_with_timestamps(youtube_url)
        except Exception as e:
            logger.warning(f"Error getting transcript with timestamps: {str(e)}")
            transcript_list = None
        
        # Create chat setup
        chat_details = setup_chat_for_video(
            youtube_url,
            transcript,
            transcript_list
        )
        
        # Prepare results
        results = {
            "video_id": video_id,
            "url": youtube_url,
            "title": video_info.get('title', f"YouTube Video ({video_id})"),
            "description": video_info.get('description', ''),
            "category": category,
            "transcript": transcript,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "chat_details": chat_details,
            "task_outputs": {
                "summarize_content": "This is a placeholder summary of the video content.",
                "analyze_content": "This is a placeholder analysis of the video content.",
                "create_action_plan": "This is a placeholder action plan based on the video content.",
                "write_report": "This is a placeholder full report of the video content."
            },
            "token_usage": {
                "prompt_tokens": 1000,
                "completion_tokens": 500,
                "total_tokens": 1500,
                "cost": 0.02
            }
        }
        
        # Cache results
        if use_cache:
            cache_analysis(video_id, results)
        
        if progress_callback:
            progress_callback(100)
        if status_callback:
            status_callback("Analysis complete")
        
        return results, None
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        logger.error(f"Error in run_analysis: {str(e)}", exc_info=True)
        return None, str(e) 