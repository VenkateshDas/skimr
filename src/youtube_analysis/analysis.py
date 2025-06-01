"""Analysis functionality for YouTube videos."""

import re
import copy
import asyncio
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime
import os

from .utils.logging import get_logger
from .utils.video_highlights import generate_highlights_video, get_cached_highlights_video, cache_highlights_video
from .core import CacheManager, YouTubeClient
from .crew import YouTubeAnalysisCrew
from .transcript import get_transcript_with_timestamps, get_transcript_with_timestamps_async
from .chat import setup_chat_for_video, setup_chat_for_video_async

# Configure logging
logger = get_logger("analysis")

# Initialize core components
cache_manager = CacheManager()
youtube_client = YouTubeClient(cache_manager)

async def _fetch_video_data(youtube_url: str) -> Tuple[str, str, Optional[str], Optional[List[Dict[str, Any]]], Dict[str, Any]]:
    """
    Fetch all video-related data concurrently.
    
    Returns:
        Tuple of (video_id, transcript, timestamped_transcript, transcript_list, video_info)
    """
    video_id = youtube_client.extract_video_id(youtube_url)
    logger.info(f"Extracted video ID: {video_id} from URL: {youtube_url}")
    
    # Fetch all data concurrently for maximum performance
    transcript_task = youtube_client.get_transcript(youtube_url)
    video_info_task = youtube_client.get_video_info(youtube_url)
    timestamped_transcript_task = get_transcript_with_timestamps_async(youtube_url)
    
    try:
        # Run all three operations concurrently
        results = await asyncio.gather(
            transcript_task,
            video_info_task, 
            timestamped_transcript_task,
            return_exceptions=True  # Don't fail if one fails
        )
        
        transcript = results[0] if not isinstance(results[0], Exception) else None
        video_info_obj = results[1] if not isinstance(results[1], Exception) else None
        
        # Handle timestamped transcript result
        if isinstance(results[2], Exception):
            logger.warning(f"Could not get transcript with timestamps: {str(results[2])}")
            timestamped_transcript, transcript_list = None, None
        else:
            timestamped_transcript, transcript_list = results[2]
        
        # Validate that we at least got the basic transcript
        if transcript is None:
            logger.error(f"Failed to fetch basic transcript for video {video_id}")
            raise ValueError("Failed to fetch basic transcript")
        
        # Convert video info object to dict
        video_info = {
            "title": video_info_obj.title if video_info_obj else "Unknown Video",
            "description": video_info_obj.description if video_info_obj else "No description available"
        }
        
        return video_id, transcript, timestamped_transcript, transcript_list, video_info
        
    except Exception as e:
        logger.error(f"Error fetching video data: {str(e)}")
        raise

async def _check_and_validate_cache(video_id: str, use_cache: bool) -> Optional[Dict[str, Any]]:
    """
    Check cache and validate cached results.
    
    Returns:
        Valid cached results or None
    """
    if not use_cache:
        logger.info(f"Cache usage disabled, forcing new analysis for video {video_id}")
        return None
    
    logger.info(f"Checking for cached analysis for video ID: {video_id}")
    cached_results = cache_manager.get("analysis", f"analysis_{video_id}")
    
    if not cached_results:
        return None
    
    logger.info(f"Using cached analysis for video {video_id}")
    logger.debug(f"Cached results keys: {cached_results.keys()}")
    
    # Check for placeholder content
    if "task_outputs" in cached_results and cached_results["task_outputs"]:
        for key, value in cached_results["task_outputs"].items():
            if isinstance(value, str) and "placeholder" in value.lower():
                logger.warning(f"Found placeholder content in cached task output '{key}', forcing new analysis")
                return None
    
    return cached_results

async def _setup_chat_for_cached_results(youtube_url: str, video_id: str, cached_results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Set up chat functionality for cached results.
    """
    try:
        # Fetch data needed for chat
        video_id, transcript, timestamped_transcript, transcript_list, _ = await _fetch_video_data(youtube_url)
        
        # Set up chat functionality
        if transcript is None:
            logger.error(f"Cannot set up chat: transcript is None for video {video_id}")
            chat_details = None
        else:
            chat_details = await setup_chat_for_video_async(youtube_url, transcript, transcript_list)
        
        # Update cached results
        cached_results["chat_details"] = chat_details
        return cached_results
        
    except Exception as e:
        logger.warning(f"Error recreating chat agent for cached analysis: {str(e)}")
        return cached_results

async def _execute_crew_analysis(youtube_url: str, video_data: Tuple, analysis_types: List[str], 
                                progress_callback=None, status_callback=None) -> Tuple[Dict[str, Any], Optional[str]]:
    """
    Execute the CrewAI analysis workflow.
    
    Args:
        youtube_url: Video URL
        video_data: Tuple from _fetch_video_data
        analysis_types: Types of analysis to perform
        progress_callback: Progress callback function
        status_callback: Status callback function
        
    Returns:
        Tuple of (results_dict, error_message)
    """
    video_id, transcript, timestamped_transcript, transcript_list, video_info = video_data
    
    if progress_callback:
        progress_callback(30)
    if status_callback:
        status_callback("Creating analysis crew...")
    
    # Set up chat functionality
    if transcript is None:
        logger.error(f"Cannot set up chat: transcript is None for video {video_id}")
        chat_details = None
    else:
        chat_details = await setup_chat_for_video_async(youtube_url, transcript, transcript_list)
    
    if progress_callback:
        progress_callback(40)
    if status_callback:
        status_callback("Analyzing video content...")
    
    # Create and run the crew
    logger.info("Creating YouTubeAnalysisCrew")
    crew_instance = YouTubeAnalysisCrew()
    
    try:
        crew = crew_instance.crew(analysis_types=analysis_types)
        logger.info(f"Successfully set up crew with {len(crew.tasks)} tasks")
        
        # Prepare inputs
        current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        video_title = video_info["title"]
        
        inputs = {
            "youtube_url": youtube_url,
            "transcript": transcript,
            "current_datetime": current_datetime,
            "video_title": video_title
        }
        
        logger.info(f"Starting crew execution with inputs: youtube_url={youtube_url}, transcript length={len(transcript) if transcript else 0}")
        
        # Execute crew
        crew_output = crew.kickoff(inputs=inputs)
        logger.info(f"Crew execution completed, output type: {type(crew_output)}")
        
        # Extract task outputs
        task_outputs = {}
        for task in crew.tasks:
            task_name = task.name if hasattr(task, 'name') else task.__class__.__name__
            logger.info(f"Processing task: {task_name}, has output: {hasattr(task, 'output')}")
            
            if hasattr(task, 'output') and task.output:
                task_outputs[task_name] = task.output.raw
                logger.info(f"Added output for task {task_name}, length: {len(str(task.output.raw))}")
                
                # Update progress based on task completion
                if task_name == "classify_and_summarize_content":
                    if progress_callback:
                        progress_callback(70)
                    if status_callback:
                        status_callback("Analyzing video content and creating action plan...")
                elif task_name == "analyze_and_plan_content":
                    if progress_callback:
                        progress_callback(95)
                    if status_callback:
                        status_callback("Generating final report...")
        
        # Validate outputs
        if not task_outputs:
            logger.warning("No task outputs were generated")
            return None, "Analysis produced no results. Please try again."
        
        # Check for placeholder content
        for key, value in task_outputs.items():
            if isinstance(value, str) and "placeholder" in value.lower():
                logger.warning(f"Detected placeholder text in task output '{key}'")
                return None, "Analysis produced placeholder results. Please try again with cache disabled or a different model."
        
        if progress_callback:
            progress_callback(100)
        if status_callback:
            status_callback("Analysis completed successfully!")
        
        # Get token usage
        token_usage = crew_output.token_usage if hasattr(crew_output, 'token_usage') else None
        token_usage_dict = None
        if token_usage:
            if hasattr(token_usage, 'get'):
                token_usage_dict = token_usage
            else:
                token_usage_dict = {
                    "total_tokens": getattr(token_usage, 'total_tokens', 0),
                    "prompt_tokens": getattr(token_usage, 'prompt_tokens', 0),
                    "completion_tokens": getattr(token_usage, 'completion_tokens', 0)
                }
        
        # Extract category and context
        category = "Uncategorized"
        context_tag = "General"
        if "classify_and_summarize_content" in task_outputs:
            category = extract_category(task_outputs["classify_and_summarize_content"])
            context_tag = extract_context_tag(task_outputs["classify_and_summarize_content"])
        
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
            "context_tag": context_tag,
            "token_usage": token_usage_dict,
            "cached": False,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "chat_details": chat_details
        }
        
        return results, None
        
    except Exception as e:
        logger.error(f"Error in crew execution: {str(e)}", exc_info=True)
        return None, f"Failed to run analysis crew: {str(e)}"

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

def extract_context_tag(output: str) -> str:
    """
    Extract the context tag from the classification output.
    
    Args:
        output: The classification output
        
    Returns:
        The extracted context tag
    """
    # Look for context tag names in the output
    context_tags = [
        "Tutorial", "News", "Review", "Case Study", 
        "Interview", "Opinion Piece", "How-To Guide"
    ]
    
    for tag in context_tags:
        if tag in output:
            return tag
    
    return "General"

def run_analysis(youtube_url: str, progress_callback=None, status_callback=None, use_cache: bool = True, 
                analysis_types: List[str] = None) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Run the YouTube Analysis Crew with the provided YouTube URL.
    
    Args:
        youtube_url: The URL of the YouTube video to analyze
        progress_callback: Optional callback function to update progress (0-100)
        status_callback: Optional callback function to update status messages
        use_cache: Whether to use cached analysis results if available
        analysis_types: List of analysis types to generate (default: all types)
    """
    # Convert to async and run
    return asyncio.run(_run_analysis_async(
        youtube_url, progress_callback, status_callback, use_cache, analysis_types
    ))

async def _run_analysis_async(youtube_url: str, progress_callback=None, status_callback=None, 
                            use_cache: bool = True, analysis_types: List[str] = None) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Async implementation of run_analysis with improved performance and structure.
    """
    start_time = datetime.now()
    
    # Default to all analysis types if none specified
    if analysis_types is None:
        analysis_types = ["Summary & Classification", "Action Plan", "Blog Post", "LinkedIn Post", "X Tweet"]
    
    try:
        if analysis_types is not None and isinstance(analysis_types, list):
            analysis_types = tuple(analysis_types)
        
        # Extract video ID first
        video_id = youtube_client.extract_video_id(youtube_url)
        logger.info(f"Extracted video ID: {video_id} from URL: {youtube_url}")
        
        # Check cache first
        cached_results = await _check_and_validate_cache(video_id, use_cache)
        
        if cached_results:
            if status_callback:
                status_callback("Using cached analysis results...")
            if progress_callback:
                progress_callback(100)
            
            # Calculate analysis time for cached results
            end_time = datetime.now()
            analysis_time = (end_time - start_time).total_seconds()
            cached_results["analysis_time"] = analysis_time
            cached_results["cached"] = True
            
            # Set up chat for cached results
            cached_results = await _setup_chat_for_cached_results(youtube_url, video_id, cached_results)
            return cached_results, None
        
        # Proceed with new analysis
        logger.info(f"No cached analysis found for video {video_id}, proceeding with new analysis")
        
        if progress_callback:
            progress_callback(0)
        if status_callback:
            status_callback("Fetching video data...")
        
        # Fetch all video data concurrently
        try:
            video_data = await _fetch_video_data(youtube_url)
            video_id, transcript, timestamped_transcript, transcript_list, video_info = video_data
        except Exception as e:
            logger.error(f"Error fetching video data: {str(e)}")
            return None, f"Error fetching video data: {str(e)}"
        
        if progress_callback:
            progress_callback(20)
        if status_callback:
            status_callback("Running analysis...")
        
        # Execute crew analysis
        results, error = await _execute_crew_analysis(
            youtube_url, video_data, analysis_types, progress_callback, status_callback
        )
        
        if error:
            return None, error
        
        if not results:
            return None, "Analysis failed to produce results"
        
        # Calculate total analysis time
        end_time = datetime.now()
        analysis_time = (end_time - start_time).total_seconds()
        results["analysis_time"] = analysis_time
        
        # Cache the results
        try:
            results_to_cache = copy.deepcopy(results)
            logger.info(f"Caching analysis results for video {video_id}")
            cache_manager.set("analysis", f"analysis_{video_id}", results_to_cache)
            logger.info("Successfully cached analysis results")
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
        video_id = youtube_client.extract_video_id(youtube_url)
        
        # Update progress
        if progress_callback:
            progress_callback(40)
        if status_callback:
            status_callback("Analyzing video content...")
        
        # Get video info
        video_info_obj = asyncio.run(youtube_client.get_video_info(youtube_url))
        video_info = {"title": video_info_obj.title if video_info_obj else "Unknown Video"}
        
        # Create and run the crew
        import os
        
        # Get model and temperature from environment variables
        model = os.environ.get("LLM_MODEL", "gpt-4o-mini")
        temperature = float(os.environ.get("LLM_TEMPERATURE", "0.7"))
        
        crew_instance = YouTubeAnalysisCrew(model_name=model, temperature=temperature)
        crew = crew_instance.crew()

        # Get current date and time
        current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        video_title = video_info["title"]
        
        # Start the crew execution
        inputs = {"youtube_url": youtube_url, "transcript": plain_transcript, "current_datetime": current_datetime, "video_title": video_title}
        crew_output = crew.kickoff(inputs=inputs)
        
        # Extract task outputs
        task_outputs = {}
        for task in crew.tasks:
            if hasattr(task, 'output') and task.output:
                task_name = task.name if hasattr(task, 'name') else task.__class__.__name__
                task_outputs[task_name] = task.output.raw
                
                # Update progress based on task completion
                if task_name == "classify_and_summarize_content":
                    if progress_callback:
                        progress_callback(70)
                    if status_callback:
                        status_callback("Analyzing video content and creating action plan...")
                elif task_name == "analyze_and_plan_content":
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
        
        # Convert UsageMetrics object to dictionary if needed
        token_usage_dict = None
        if token_usage:
            if hasattr(token_usage, 'get'):
                # Already a dictionary
                token_usage_dict = token_usage
            else:
                # Convert UsageMetrics object to dictionary
                token_usage_dict = {
                    "total_tokens": getattr(token_usage, 'total_tokens', 0),
                    "prompt_tokens": getattr(token_usage, 'prompt_tokens', 0),
                    "completion_tokens": getattr(token_usage, 'completion_tokens', 0)
                }
        
        # Extract category from classification output
        category = "Uncategorized"
        context_tag = "General"
        if "classify_and_summarize_content" in task_outputs:
            category = extract_category(task_outputs["classify_and_summarize_content"])
            context_tag = extract_context_tag(task_outputs["classify_and_summarize_content"])
        
        # Prepare results
        results = {
            "video_id": video_id,
            "youtube_url": youtube_url,
            "transcript": plain_transcript,
            "output": str(crew_output),
            "task_outputs": task_outputs,
            "category": category,
            "context_tag": context_tag,
            "token_usage": token_usage_dict,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "chat_details": None
        }
        
        # Cache the analysis results for future use
        try:
            # Create a deep copy to avoid modifying the original results
            results_to_cache = copy.deepcopy(results)
            cache_manager.set("analysis", f"analysis_{video_id}", results_to_cache)
        except Exception as e:
            logger.warning(f"Error caching analysis results: {str(e)}")
        
        # If task outputs are not created properly, create default ones
        if not task_outputs or len(task_outputs) == 0:
            logger.warning("Direct analysis produced no task outputs. Creating defaults.")
            task_outputs = {
                "classify_and_summarize_content": "Direct analysis results were not generated properly. Please try again with different settings.",
                "analyze_and_plan_content": "Analysis and action plan could not be created in direct analysis mode.",
                "write_report": "Report generation failed in direct analysis mode."
            }
        
        return results, None
        
    except Exception as e:
        logger.error(f"Error in direct analysis: {str(e)}", exc_info=True)
        return None, str(e)

def generate_video_highlights(youtube_url: str, max_highlights: int = 5, progress_callback=None, status_callback=None) -> Tuple[Optional[str], Optional[List[Dict[str, Any]]], Optional[str]]:
    """
    Generate video highlights from a YouTube video.
    
    Args:
        youtube_url: The URL of the YouTube video
        max_highlights: Maximum number of highlights to extract
        progress_callback: Optional callback function to update progress (0-100)
        status_callback: Optional callback function to update status messages
        
    Returns:
        A tuple containing:
        - Path to the highlights video or None if failed
        - List of highlight segments used or None if failed
        - Error message or None if successful
    """
    try:
        # Extract video ID
        video_id = youtube_client.extract_video_id(youtube_url)
        if not video_id:
            error_msg = f"Invalid YouTube URL: {youtube_url}"
            logger.error(error_msg)
            return None, None, error_msg
        
        if status_callback:
            status_callback("Checking for cached highlights video...")
        
        # Check if we have a cached highlights video
        cached_highlights = get_cached_highlights_video(video_id)
        if cached_highlights:
            logger.info(f"Using cached highlights video for {video_id}")
            
            # Verify the cached video path still exists
            video_path = cached_highlights.get("video_path")
            if video_path and not os.path.exists(video_path):
                logger.warning(f"Cached video path {video_path} no longer exists, generating a new one")
            else:
                if progress_callback:
                    progress_callback(100)
                    
                if status_callback:
                    status_callback("Using cached highlights video...")
                
                return video_path, cached_highlights.get("highlights"), None
        
        # Get transcript with timestamps
        if status_callback:
            status_callback("Fetching video transcript with timestamps...")
            
        if progress_callback:
            progress_callback(10)
        
        try:
            timestamped_transcript, transcript_list = get_transcript_with_timestamps(youtube_url)
        except Exception as e:
            error_msg = f"Error getting transcript with timestamps: {str(e)}"
            logger.error(error_msg)
            return None, None, error_msg
        
        if not timestamped_transcript:
            error_msg = "No transcript available for this video."
            logger.error(error_msg)
            return None, None, error_msg
        
        if status_callback:
            status_callback("Downloading video and analyzing key moments...")
            
        if progress_callback:
            progress_callback(30)
        
        # Generate highlights video
        try:
            highlights_path, highlights = generate_highlights_video(
                youtube_url=youtube_url,
                video_id=video_id,
                transcript_text=timestamped_transcript,
                max_highlights=max_highlights
            )
            
            if not highlights_path:
                if highlights:
                    # We have highlights but no video - likely a download issue
                    error_msg = "Failed to download the video. YouTube may have restricted this content or changed their API."
                    logger.error(error_msg)
                    return None, highlights, error_msg
                else:
                    error_msg = "Failed to generate highlights video. The AI couldn't identify key moments."
                    logger.error(error_msg)
                    return None, None, error_msg
                    
        except Exception as highlight_error:
            error_msg = f"Error in highlights generation: {str(highlight_error)}"
            logger.error(error_msg)
            return None, None, error_msg
        
        if progress_callback:
            progress_callback(90)
        
        # Cache the highlights video info
        cache_highlights_video(video_id, highlights_path, highlights)
        
        if progress_callback:
            progress_callback(100)
            
        if status_callback:
            status_callback("Highlights video generated successfully!")
        
        return highlights_path, highlights, None
        
    except Exception as e:
        error_msg = f"Error generating highlights video: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return None, None, error_msg 
