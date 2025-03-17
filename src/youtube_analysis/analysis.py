"""Analysis functionality for YouTube videos."""

import re
import copy
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

from .utils.logging import get_logger
from .utils.youtube_utils import extract_video_id, get_transcript, get_video_info
from .utils.cache_utils import get_cached_analysis, cache_analysis
from .crew import YouTubeAnalysisCrew
from .transcript import get_transcript_with_timestamps
from .chat import setup_chat_for_video

# Configure logging
logger = get_logger("analysis")

def extract_category(output: str) -> str:
    """
    Extract the category from the classification output.
    
    Args:
        output: The classification output
        
    Returns:
        The extracted category
    """
    # Look for category names in the output
    categories = [
        "Technology", "Business", "Education", "Health & Wellness", 
        "Science", "Finance", "Personal Development", "Entertainment"
    ]
    
    for category in categories:
        if category in output:
            return category
    
    # If no category is found, check for "Other"
    if "Other" in output:
        # Try to extract the specified category
        match = re.search(r"Other \(([^)]+)\)", output)
        if match:
            return f"Other: {match.group(1)}"
        return "Other"
    
    return "Uncategorized"

def run_analysis(youtube_url: str, progress_callback=None, status_callback=None, use_cache: bool = True) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Run the YouTube Analysis Crew with the provided YouTube URL.
    
    Args:
        youtube_url: The URL of the YouTube video to analyze
        progress_callback: Optional callback function to update progress (0-100)
        status_callback: Optional callback function to update status messages
        use_cache: Whether to use cached analysis results if available
        
    Returns:
        A tuple containing the analysis results and any error message
    """
    try:
        # Extract video ID for thumbnail
        video_id = extract_video_id(youtube_url)
        logger.info(f"Extracted video ID: {video_id} from URL: {youtube_url}")
        logger.debug(f"use_cache setting: {use_cache}")
        
        # Check if we have cached analysis results
        if use_cache:
            logger.info(f"Checking for cached analysis for video ID: {video_id}")
            cached_results = get_cached_analysis(video_id)
            if cached_results:
                logger.info(f"Using cached analysis for video {video_id}")
                logger.debug(f"Cached results keys: {cached_results.keys()}")
                
                if status_callback:
                    status_callback("Using cached analysis results...")
                
                if progress_callback:
                    progress_callback(100)
                
                # We need to recreate the chat agent since it's not serializable
                try:
                    # Get the transcript
                    transcript = get_transcript(youtube_url)
                    
                    # Get transcript with timestamps
                    try:
                        timestamped_transcript, transcript_list = get_transcript_with_timestamps(youtube_url)
                    except Exception as e:
                        logger.warning(f"Could not get transcript with timestamps: {str(e)}")
                        timestamped_transcript = None
                        transcript_list = None
                    
                    # Set up chat functionality
                    chat_details = setup_chat_for_video(youtube_url, transcript, transcript_list)
                    
                    # Update the cached results with the new chat details
                    cached_results["chat_details"] = chat_details
                    
                except Exception as e:
                    logger.warning(f"Error recreating chat agent for cached analysis: {str(e)}")
                
                return cached_results, None
            else:
                logger.info(f"No cached analysis found for video {video_id}, proceeding with new analysis")
        else:
            logger.info(f"Cache usage disabled, proceeding with new analysis for video {video_id}")
        
        # Update progress
        if progress_callback:
            progress_callback(0)
        if status_callback:
            status_callback("Fetching video transcript...")
        
        # Get the transcript
        transcript = get_transcript(youtube_url)
        
        if progress_callback:
            progress_callback(15)
        
        # Get transcript with timestamps
        try:
            timestamped_transcript, transcript_list = get_transcript_with_timestamps(youtube_url)
        except Exception as e:
            logger.warning(f"Could not get transcript with timestamps: {str(e)}")
            timestamped_transcript = None
            transcript_list = None
        
        if progress_callback:
            progress_callback(20)
        if status_callback:
            status_callback("Creating analysis crew...")
        
        # Set up chat functionality
        chat_details = setup_chat_for_video(youtube_url, transcript, transcript_list)
        
        if progress_callback:
            progress_callback(30)
        if status_callback:
            status_callback("Chat functionality enabled!")
        
        # Create and run the crew
        import os
        
        # Get model and temperature from environment variables
        model = os.environ.get("LLM_MODEL", "gpt-4o-mini")
        temperature = float(os.environ.get("LLM_TEMPERATURE", "0.7"))
        
        crew_instance = YouTubeAnalysisCrew(model_name=model, temperature=temperature)
        crew = crew_instance.crew()
        
        # Update progress
        if progress_callback:
            progress_callback(40)
        if status_callback:
            status_callback("Analyzing video content...")
        
        # Start the crew execution
        inputs = {"youtube_url": youtube_url, "transcript": transcript}
        crew_output = crew.kickoff(inputs=inputs)
        
        # Extract task outputs
        task_outputs = {}
        for task in crew.tasks:
            if hasattr(task, 'output') and task.output:
                task_name = task.name if hasattr(task, 'name') else task.__class__.__name__
                task_outputs[task_name] = task.output.raw
                
                # Update progress based on task completion
                if task_name == "classify_video":
                    if progress_callback:
                        progress_callback(50)
                    if status_callback:
                        status_callback("Summarizing video content...")
                elif task_name == "summarize_content":
                    if progress_callback:
                        progress_callback(70)
                    if status_callback:
                        status_callback("Analyzing video content...")
                elif task_name == "analyze_content":
                    if progress_callback:
                        progress_callback(85)
                    if status_callback:
                        status_callback("Creating action plan...")
                elif task_name == "create_action_plan":
                    if progress_callback:
                        progress_callback(95)
                    if status_callback:
                        status_callback("Generating final report...")
        
        # Update progress
        if progress_callback:
            progress_callback(100)
        if status_callback:
            status_callback("Analysis completed successfully!")
        
        # Get token usage
        token_usage = crew_output.token_usage if hasattr(crew_output, 'token_usage') else None
        
        # Extract category from classification output
        category = "Uncategorized"
        if "classify_video" in task_outputs:
            category = extract_category(task_outputs["classify_video"])
        
        # Prepare results
        results = {
            "video_id": video_id,
            "youtube_url": youtube_url,
            "transcript": transcript,
            "timestamped_transcript": timestamped_transcript,
            "transcript_list": transcript_list,
            "output": str(crew_output),
            "task_outputs": task_outputs,
            "category": category,
            "token_usage": token_usage,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "chat_details": chat_details
        }
        
        # Cache the analysis results for future use
        try:
            # Create a deep copy to avoid modifying the original results
            results_to_cache = copy.deepcopy(results)
            cache_analysis(video_id, results_to_cache)
        except Exception as e:
            logger.warning(f"Error caching analysis results: {str(e)}")
        
        return results, None
        
    except Exception as e:
        logger.error(f"Error in analysis: {str(e)}", exc_info=True)
        return None, str(e)

def run_direct_analysis(youtube_url: str, plain_transcript: str, progress_callback=None, status_callback=None) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Run the YouTube Analysis Crew directly with a provided transcript.
    This is used as a fallback when the standard run_analysis function encounters errors.
    
    Args:
        youtube_url: The URL of the YouTube video to analyze
        plain_transcript: The plain text transcript of the video
        progress_callback: Optional callback function to update progress (0-100)
        status_callback: Optional callback function to update status messages
        
    Returns:
        A tuple containing the analysis results and any error message
    """
    try:
        # Extract video ID for thumbnail
        video_id = extract_video_id(youtube_url)
        
        # Update progress
        if progress_callback:
            progress_callback(40)
        if status_callback:
            status_callback("Analyzing video content...")
        
        # Get video info
        video_info = get_video_info(youtube_url)
        
        # Create and run the crew
        import os
        
        # Get model and temperature from environment variables
        model = os.environ.get("LLM_MODEL", "gpt-4o-mini")
        temperature = float(os.environ.get("LLM_TEMPERATURE", "0.7"))
        
        crew_instance = YouTubeAnalysisCrew(model_name=model, temperature=temperature)
        crew = crew_instance.crew()
        
        # Start the crew execution
        inputs = {"youtube_url": youtube_url, "transcript": plain_transcript}
        crew_output = crew.kickoff(inputs=inputs)
        
        # Extract task outputs
        task_outputs = {}
        for task in crew.tasks:
            if hasattr(task, 'output') and task.output:
                task_name = task.name if hasattr(task, 'name') else task.__class__.__name__
                task_outputs[task_name] = task.output.raw
                
                # Update progress based on task completion
                if task_name == "classify_video":
                    if progress_callback:
                        progress_callback(50)
                    if status_callback:
                        status_callback("Summarizing video content...")
                elif task_name == "summarize_content":
                    if progress_callback:
                        progress_callback(70)
                    if status_callback:
                        status_callback("Analyzing video content...")
                elif task_name == "analyze_content":
                    if progress_callback:
                        progress_callback(85)
                    if status_callback:
                        status_callback("Creating action plan...")
                elif task_name == "create_action_plan":
                    if progress_callback:
                        progress_callback(95)
                    if status_callback:
                        status_callback("Generating final report...")
        
        # Update progress
        if progress_callback:
            progress_callback(100)
        if status_callback:
            status_callback("Analysis completed successfully!")
        
        # Get token usage
        token_usage = crew_output.token_usage if hasattr(crew_output, 'token_usage') else None
        
        # Extract category from classification output
        category = "Uncategorized"
        if "classify_video" in task_outputs:
            category = extract_category(task_outputs["classify_video"])
        
        # Prepare results
        results = {
            "video_id": video_id,
            "youtube_url": youtube_url,
            "transcript": plain_transcript,
            "output": str(crew_output),
            "task_outputs": task_outputs,
            "category": category,
            "token_usage": token_usage,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "chat_details": None
        }
        
        # Cache the analysis results for future use
        try:
            # Create a deep copy to avoid modifying the original results
            results_to_cache = copy.deepcopy(results)
            cache_analysis(video_id, results_to_cache)
        except Exception as e:
            logger.warning(f"Error caching analysis results: {str(e)}")
        
        return results, None
        
    except Exception as e:
        logger.error(f"Error in direct analysis: {str(e)}", exc_info=True)
        return None, str(e) 