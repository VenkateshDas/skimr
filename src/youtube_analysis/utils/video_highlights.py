"""Utility functions for generating video highlights from YouTube videos."""

import os
import re
import json
import time
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import tempfile
from langchain_google_genai import ChatGoogleGenerativeAI
import requests
from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.video.compositing.concatenate import concatenate_videoclips
from moviepy.video.fx.fadein import fadein
from moviepy.video.fx.fadeout import fadeout

from .logging import get_logger
from ..core.config import CACHE_DIR, YOUTUBE_API_KEY
from .youtube_utils import extract_video_id, get_cache_key, get_video_info, is_cache_valid, get_cache_dir

# Configure logging
logger = get_logger("video_highlights")

def timestamp_to_seconds(ts: str) -> int:
    """
    Convert a timestamp string to seconds.
    
    Args:
        ts: Timestamp string in format MM:SS or HH:MM:SS
        
    Returns:
        The time in seconds
    """
    parts = ts.split(':')
    parts = [int(p) for p in parts]
    if len(parts) == 3:
        hours, minutes, seconds = parts
    else:
        hours = 0
        minutes, seconds = parts
    return hours * 3600 + minutes * 60 + seconds

def extract_timestamps_from_transcript(transcript_text: str) -> List[Dict[str, Any]]:
    """
    Extract timestamps from transcript text.
    
    Args:
        transcript_text: Transcript text with timestamps
        
    Returns:
        List of transcript segments with start and end times
    """
    # Extract timestamped segments with regex
    pattern = r'\[(\d+:\d+(?::\d+)?)\]\s*(.*?)(?=\[\d+:\d+(?::\d+)?\]|$)'
    matches = re.findall(pattern, transcript_text, re.DOTALL)
    
    segments = []
    for i, (timestamp, text) in enumerate(matches):
        start_time = timestamp_to_seconds(timestamp)
        
        # Set end time based on next timestamp or estimate
        if i < len(matches) - 1:
            end_time = timestamp_to_seconds(matches[i+1][0])
        else:
            # For the last segment, estimate a duration
            end_time = start_time + len(text.split()) * 0.5  # rough estimate
        
        segments.append({
            "start_time": start_time,
            "end_time": end_time,
            "text": text.strip()
        })
    
    return segments

def call_llm_for_highlights(transcript_text: str, max_highlights: int = 10, default_segment_length: int = 15, video_info: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    """
    Use an LLM to extract the most important highlights from a transcript.
    
    Args:
        transcript_text: Transcript text with timestamps
        max_highlights: Maximum number of highlights to extract
        default_segment_length: Default length for highlight segments in seconds
        
    Returns:
        List of highlight segments with start_time, end_time, and description
    """
    from langchain.chat_models import ChatOpenAI
    from langchain.schema import SystemMessage, HumanMessage
    
    # Extract segments with timestamps for better processing
    segments = extract_timestamps_from_transcript(transcript_text)

    if video_info:
        video_title = video_info["title"]
        video_description = video_info["description"]
    
    try:
        # Create a prompt for extracting highlights
        prompt = f"""
You are an expert in video summarization.

You are provided with the transcript of a video with timestamps, the title and description of the video.

Video Title: {video_title}
Video Description: {video_description}

Below will be provided with the transcript of a video with timestamps, extract the most important {max_highlights} highlights that clearly summarizes the video.
These extracted highlights will be used in creating a highlights video that provides the most important information to the viewers.

The highlight moments should be in chronological order and should cover the entire video.
The highlight moments should be from the start of the video, the middle and the end of the video.
Do NOT include any promotional content, repetitive sentences, or other content that does not contribute to the core message of the video.

When creating segments, try to not abruptly cut off the video. Make sure to provide a smooth transition between segments.

For each highlight, identify:
- Start time in seconds
- End time in seconds
- A brief description of the highlight

The highlights should be in chronological order and should cover the entire video.

If two highlights are very close in time, merge them into a single segment.
Return only a valid JSON array containing these highlight objects.

Transcript:
{segments}
"""
        # Setup LLM model
        model_name = os.getenv("LLM_MODEL", "gpt-4o-mini")
        temperature = float(os.getenv("LLM_TEMPERATURE", 0.2))
        if model_name.startswith("gpt-"):
            chat_model = ChatOpenAI(
                model=model_name,
                temperature=temperature,
                streaming=False
            )
        elif model_name.startswith("gemini"):
            chat_model = ChatGoogleGenerativeAI(temperature=temperature, model=model_name, api_key=os.getenv("GEMINI_API_KEY"))

        
        # Call the model
        messages = [
            SystemMessage(content="You are an expert in video summarization."),
            HumanMessage(content=prompt)
        ]
        
        response = chat_model.invoke(messages)
        output_text = response.content.strip()
        
        # Extract JSON from the response
        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', output_text)
        if json_match:
            output_text = json_match.group(1)
        else:
            # Try to find array directly
            json_match = re.search(r'\[\s*{[\s\S]*}\s*\]', output_text)
            if json_match:
                output_text = json_match.group(0)
        
        # Parse and validate the JSON response
        highlights = json.loads(output_text)
        
        # Validate and clean the highlights
        validated_highlights = []
        for highlight in highlights:
            # Ensure required fields
            if "start_time" in highlight and "end_time" in highlight and "description" in highlight:
                validated_highlights.append({
                    "start_time": float(highlight["start_time"]),
                    "end_time": float(highlight["end_time"]),
                    "description": highlight["description"]
                })
        
        return validated_highlights
    except Exception as e:
        logger.error(f"Error calling LLM for highlights: {str(e)}")
        return []

def merge_segments(segments: List[Dict[str, Any]], merge_threshold: int = 2) -> List[Dict[str, Any]]:
    """
    Merge segments that are close in time.
    
    Args:
        segments: List of segment dictionaries with start_time and end_time
        merge_threshold: Threshold in seconds for merging segments
        
    Returns:
        List of merged segments
    """
    if not segments:
        return segments
    
    # Sort segments by start time
    segments.sort(key=lambda seg: seg["start_time"])
    
    # Merge adjacent segments
    merged = [segments[0]]
    for current in segments[1:]:
        last = merged[-1]
        if current["start_time"] - last["end_time"] <= merge_threshold:
            # Merge with previous segment
            last["end_time"] = max(last["end_time"], current["end_time"])
            last["description"] += " | " + current["description"]
        else:
            # Add as new segment
            merged.append(current)
    
    return merged

def try_yt_dlp_download(video_id: str, output_path: str) -> bool:
    """
    Attempt to download a YouTube video using yt-dlp as a fallback method.
    
    Args:
        video_id: YouTube video ID
        output_path: Path where the video should be saved
        
    Returns:
        True if download succeeded, False otherwise
    """
    try:
        # Check if yt-dlp is installed
        import importlib.util
        if importlib.util.find_spec("yt_dlp") is None:
            logger.warning("yt-dlp not installed, skipping this fallback method")
            return False
            
        import yt_dlp
        
        # YouTube URL
        url = f"https://www.youtube.com/watch?v={video_id}"
        
        # yt-dlp options
        ydl_opts = {
            'format': 'best[ext=mp4]',
            'outtmpl': output_path,
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
        }
        
        logger.info(f"Attempting to download with yt-dlp: {url}")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
            
        # Check if file exists and has content
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            logger.info(f"Successfully downloaded video using yt-dlp to {output_path}")
            return True
        else:
            logger.warning("yt-dlp download completed but file is missing or empty")
            return False
            
    except Exception as e:
        logger.error(f"Error using yt-dlp to download: {str(e)}")
        return False

def download_youtube_video(video_id: str) -> Optional[str]:
    """
    Download a YouTube video for processing.
    
    Args:
        video_id: YouTube video ID
        
    Returns:
        Path to the downloaded video file, or None if download failed
    """
    try:
        from pytube import YouTube
        
        # Create a temporary directory for downloaded videos
        temp_dir = Path(tempfile.gettempdir()) / "youtube_highlights"
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Check if we already have this video downloaded
        video_path = temp_dir / f"{video_id}.mp4"
        if video_path.exists():
            logger.info(f"Using previously downloaded video: {video_path}")
            return str(video_path)
        
        # YouTube URL
        youtube_url = f"https://www.youtube.com/watch?v={video_id}"
        logger.info(f"Attempting to download video: {youtube_url}")
        
        # Method 1: Try using pytube
        try:
            # Create YouTube object with additional options to handle common issues
            yt = YouTube(
                youtube_url,
                use_oauth=False,
                allow_oauth_cache=True,
                # Add callback for debugging
                on_progress_callback=lambda stream, chunk, remaining: logger.debug(
                    f"Download progress: {(stream.filesize - remaining)/stream.filesize:.1%}"
                )
            )
            
            # Log video details for debugging
            logger.info(f"Video title: {yt.title}")
            logger.info(f"Video length: {yt.length} seconds")
            logger.info(f"Available streams: {len(yt.streams)}")
            
            # First try: Get the highest resolution progressive stream (with both video and audio)
            stream = yt.streams.filter(progressive=True, file_extension="mp4").order_by("resolution").desc().first()
            
            if not stream:
                logger.warning("No progressive streams found, trying adaptive streams")
                # Second try: Get the highest resolution video stream
                stream = yt.streams.filter(file_extension="mp4").order_by("resolution").desc().first()
            
            if not stream:
                logger.error("No suitable video stream found")
                raise ValueError("No suitable video stream found")
            
            # Log stream details for debugging
            logger.info(f"Selected stream: resolution={stream.resolution}, fps={stream.fps}, codec={stream.codecs}")
            
            # Download the video with timeout
            logger.info(f"Downloading video to {temp_dir}")
            stream.download(output_path=str(temp_dir), filename=f"{video_id}.mp4", timeout=300)
            logger.info(f"Video downloaded successfully to {video_path}")
            
            # Verify the downloaded file
            if video_path.exists() and video_path.stat().st_size > 0:
                logger.info(f"Verified downloaded video: {video_path} ({video_path.stat().st_size} bytes)")
                return str(video_path)
            else:
                raise ValueError("Downloaded file is missing or empty")
                
        except Exception as pytube_error:
            logger.warning(f"pytube download failed: {str(pytube_error)}")
            
            # Method 2: Try using yt-dlp
            logger.info("Attempting download with yt-dlp")
            if try_yt_dlp_download(video_id, str(video_path)):
                return str(video_path)
                
            # Method 3: Try using a different pytube approach
            try:
                logger.info("Trying alternative pytube approach")
                yt = YouTube(youtube_url)
                fallback_stream = yt.streams.get_lowest_resolution()
                fallback_stream.download(output_path=str(temp_dir), filename=f"{video_id}.mp4")
                
                if video_path.exists() and video_path.stat().st_size > 0:
                    logger.info("Alternative pytube approach succeeded")
                    return str(video_path)
                    
            except Exception as alt_error:
                logger.warning(f"Alternative pytube approach failed: {str(alt_error)}")
                
            # If all methods failed
            logger.error("All download methods failed")
            return None
            
    except Exception as e:
        logger.error(f"Error in download process: {str(e)}", exc_info=True)
        return None

def create_highlights_video(video_path: str, segments: List[Dict[str, Any]]) -> Optional[str]:
    """
    Create a highlights video from the original video using the extracted segments.
    
    Args:
        video_path: Path to the input video file
        segments: List of highlight segments with start_time and end_time
        
    Returns:
        Path to the created highlights video, or None if creation failed
    """
    try:
        if not segments:
            logger.error("No valid segments provided for highlights video")
            return None
        
        # Create output path
        output_dir = Path(tempfile.gettempdir()) / "youtube_highlights"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate a unique filename based on input video and timestamp
        video_filename = Path(video_path).stem
        timestamp = int(time.time())
        output_path = output_dir / f"{video_filename}_highlights_{timestamp}.mp4"
        
        # Load the main video clip
        logger.info(f"Loading video from {video_path}")
        main_clip = VideoFileClip(video_path)
        
        # Extract subclips for each highlight segment
        clips = []
        for segment in segments:
            start = segment["start_time"]
            end = segment["end_time"]
            
            # Ensure times are within video duration
            if start >= main_clip.duration:
                logger.warning(f"Segment start time {start} exceeds video duration {main_clip.duration}")
                continue
                
            end = min(end, main_clip.duration)
            
            # Extract subclip
            logger.info(f"Extracting segment {start}-{end}: {segment.get('description', '')}")
            subclip = main_clip.subclip(start, end)
            
            # Add fade effects
            subclip = fadein(subclip, duration=0.5)
            subclip = fadeout(subclip, duration=0.5)
            
            clips.append(subclip)
        
        # Concatenate clips if we have any
        if clips:
            logger.info(f"Concatenating {len(clips)} clips")
            final_clip = concatenate_videoclips(clips, method="compose")
            
            # Write the final video
            logger.info(f"Writing highlights video to {output_path}")
            final_clip.write_videofile(str(output_path), codec="libx264", audio_codec="aac")
            
            # Close the main clip
            main_clip.close()
            
            return str(output_path)
        else:
            logger.error("No valid clips to create highlights video")
            return None
    except Exception as e:
        logger.error(f"Error creating highlights video: {str(e)}")
        return None

def generate_highlights_video(youtube_url: str, video_id: str, transcript_text: str, max_highlights: int = 15) -> Tuple[Optional[str], Optional[List[Dict[str, Any]]]]:
    """
    Generate a highlights video from a YouTube video using transcript analysis.
    
    Args:
        video_id: YouTube video ID
        transcript_text: Transcript text with timestamps
        max_highlights: Maximum number of highlights to extract
        
    Returns:
        Tuple containing:
        - Path to the highlights video (or None if failed)
        - List of highlight segments used
    """
    try:
        # Get the video info
        video_info = get_video_info(youtube_url)
        logger.info(f"Video info: {video_info}")
        # Extract highlights using LLM
        highlights = call_llm_for_highlights(transcript_text, max_highlights, video_info=video_info)
        
        if not highlights:
            logger.error("Failed to extract highlights from transcript")
            return None, None
        
        # Merge segments that are close together
        merged_highlights = merge_segments(highlights)
        logger.info(f"Extracted {len(merged_highlights)} highlight segments")
        
        # Download the video
        video_path = download_youtube_video(video_id)
        if not video_path:
            logger.error("Failed to download video")
            return None, merged_highlights
        
        # Create the highlights video
        highlights_path = create_highlights_video(video_path, merged_highlights)
        
        return highlights_path, merged_highlights
    except Exception as e:
        logger.error(f"Error generating highlights video: {str(e)}")
        return None, None

def get_cached_highlights_video(video_id: str) -> Optional[Dict[str, Any]]:
    """
    Get cached highlights video path and data if available.
    
    Args:
        video_id: YouTube video ID
        
    Returns:
        Dictionary with highlights video data or None if not found/expired
    """
    try:
        cache_file = get_cache_dir() / f"{get_cache_key(video_id, 'highlights')}.json"
        
        if is_cache_valid(cache_file):
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                # Check if the video file still exists
                if "video_path" in data and os.path.exists(data["video_path"]):
                    return data
        
        return None
    except Exception as e:
        logger.warning(f"Error reading highlights cache for video {video_id}: {str(e)}")
        return None

def cache_highlights_video(video_id: str, video_path: str, highlights: List[Dict[str, Any]]) -> bool:
    """
    Cache highlights video data.
    
    Args:
        video_id: YouTube video ID
        video_path: Path to the highlights video
        highlights: List of highlight segments
        
    Returns:
        True if caching was successful, False otherwise
    """
    try:
        cache_file = get_cache_dir() / f"{get_cache_key(video_id, 'highlights')}.json"
        
        data = {
            'video_id': video_id,
            'video_path': video_path,
            'highlights': highlights,
            'timestamp': time.time()
        }
        
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return True
    except Exception as e:
        logger.warning(f"Error caching highlights for video {video_id}: {str(e)}")
        return False

def clear_highlights_cache(video_id: str) -> bool:
    """
    Clear the cached highlights for a specific video.
    
    Args:
        video_id: The YouTube video ID
        
    Returns:
        True if the cache was cleared, False otherwise
    """
    try:
        cache_dir = get_cache_dir()
        cache_file = cache_dir / f"{get_cache_key(video_id, 'highlights')}.json"
        
        # Check if cache file exists
        if not cache_file.exists():
            logger.info(f"No cached highlights found for video {video_id}")
            return False
        
        # Get the cached data to find the video file path
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # Also delete the actual video file if it exists
            if "video_path" in data and os.path.exists(data["video_path"]):
                try:
                    os.remove(data["video_path"])
                    logger.info(f"Deleted highlights video file: {data['video_path']}")
                except Exception as file_error:
                    logger.warning(f"Could not delete highlights video file: {str(file_error)}")
        except Exception as read_error:
            logger.warning(f"Error reading highlights cache before deletion: {str(read_error)}")
        
        # Delete the cache file
        cache_file.unlink()
        logger.info(f"Cleared highlights cache for video {video_id}")
        return True
        
    except Exception as e:
        logger.warning(f"Error clearing highlights cache for video {video_id}: {str(e)}")
        return False 