"""
WebApp adapter for integrating the service layer with Streamlit.
"""

import os
import asyncio
from typing import Dict, Any, Optional, Tuple, Callable
from datetime import datetime

from ..service_factory import get_video_analysis_workflow, get_transcript_service, get_chat_service
from ..analysis_v2 import run_analysis_v2, cleanup_analysis_resources
from ..utils.logging import get_logger
from ..utils.youtube_utils import validate_youtube_url, extract_video_id, get_video_info
from ..utils.cache_utils import clear_analysis_cache

logger = get_logger("webapp_adapter")


class WebAppAdapter:
    """
    Adapter that provides a clean interface between Streamlit webapp 
    and the new service layer architecture.
    """
    
    def __init__(self):
        self.workflow = None
        self.transcript_service = None
        self.chat_service = None
        
    def _get_workflow(self):
        """Get or create the video analysis workflow."""
        if self.workflow is None:
            self.workflow = get_video_analysis_workflow()
        return self.workflow
    
    def _get_transcript_service(self):
        """Get or create the transcript service."""
        if self.transcript_service is None:
            self.transcript_service = get_transcript_service()
        return self.transcript_service
    
    def _get_chat_service(self):
        """Get or create the chat service."""
        if self.chat_service is None:
            self.chat_service = get_chat_service()
        return self.chat_service
    
    def validate_youtube_url(self, url: str) -> bool:
        """Validate YouTube URL."""
        return validate_youtube_url(url)
    
    def get_video_info(self, url: str) -> Optional[Dict[str, Any]]:
        """Get video information."""
        try:
            return get_video_info(url)
        except Exception as e:
            logger.error(f"Error getting video info: {e}")
            return None
    
    def process_transcript(
        self, 
        url: str, 
        use_cache: bool = True
    ) -> Tuple[Optional[str], Optional[list], Optional[str]]:
        """
        Process video transcript using the new service layer.
        
        Returns:
            Tuple of (timestamped_transcript, transcript_list, error_message)
        """
        try:
            video_id = extract_video_id(url)
            if not video_id:
                return None, None, "Could not extract video ID from URL"
            
            transcript_service = self._get_transcript_service()
            
            # Use sync method for now (we'll need to add this to TranscriptService)
            video_data = transcript_service.get_video_data_sync(video_id)
            
            if not video_data or not video_data.transcript_segments:
                return None, None, "Could not retrieve transcript"
            
            # Format transcript with timestamps
            timestamped_transcript = ""
            for item in video_data.transcript_segments:
                start = item.get('start', 0)
                minutes, seconds = divmod(int(start), 60)
                timestamp = f"[{minutes:02d}:{seconds:02d}]"
                text = item.get('text', '')
                timestamped_transcript += f"{timestamp} {text}\n"
            
            return timestamped_transcript, video_data.transcript_segments, None
            
        except Exception as e:
            error_msg = f"Error processing transcript: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return None, None, error_msg
    
    def run_analysis(
        self,
        url: str,
        progress_callback: Optional[Callable[[int], None]] = None,
        status_callback: Optional[Callable[[str], None]] = None,
        use_cache: bool = True,
        model_name: str = "gpt-4o-mini",
        temperature: float = 0.2,
        analysis_types: Optional[list] = None
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Run video analysis using the optimized Phase 2 architecture.
        
        Returns:
            Tuple of (results, error_message)
        """
        try:
            # Set environment variables for the analysis
            os.environ["LLM_MODEL"] = model_name
            os.environ["LLM_TEMPERATURE"] = str(temperature)
            os.environ["USE_OPTIMIZED_ANALYSIS"] = "true"
            
            # Clear cache if requested
            if not use_cache:
                video_id = extract_video_id(url)
                if video_id:
                    clear_analysis_cache(video_id)
                    logger.info(f"Cleared cache for video {video_id}")
            
            # Ensure analysis types include required type
            if not analysis_types:
                analysis_types = ["Summary & Classification"]
            elif "Summary & Classification" not in analysis_types:
                analysis_types = ["Summary & Classification"] + analysis_types
            
            logger.info(f"Starting analysis with settings: model={model_name}, temperature={temperature}, cache={use_cache}")
            
            # Use the Phase 2 analysis function
            results, error = run_analysis_v2(
                url,
                progress_callback=progress_callback,
                status_callback=status_callback,
                use_cache=use_cache,
                analysis_types=analysis_types,
                model_name=model_name,
                temperature=temperature
            )
            
            if error:
                logger.error(f"Analysis failed: {error}")
                return None, error
            
            if not results:
                logger.error("Analysis returned no results")
                return None, "Analysis failed to produce results"
            
            # Validate results structure
            if not isinstance(results, dict) or "task_outputs" not in results:
                logger.error(f"Invalid results structure: {type(results)}")
                return None, "Analysis returned invalid results structure"
            
            logger.info("Analysis completed successfully")
            return results, None
            
        except Exception as e:
            error_msg = f"Error during analysis: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return None, error_msg
    
    def setup_chat(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Set up chat functionality for a video.
        
        Returns:
            Chat details dictionary or None if failed
        """
        try:
            chat_service = self._get_chat_service()
            
            # Use async setup (we'll need to handle this properly)
            chat_details = asyncio.run(chat_service.setup_chat(url))
            
            logger.info(f"Chat setup completed for {url}")
            return chat_details
            
        except Exception as e:
            logger.error(f"Error setting up chat: {e}", exc_info=True)
            return None
    
    def clear_cache(self, video_id: str) -> bool:
        """Clear analysis cache for a video."""
        try:
            success = clear_analysis_cache(video_id)
            if success:
                logger.info(f"Cache cleared for video {video_id}")
            return success
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return False
    
    async def cleanup_resources(self):
        """Clean up all resources."""
        try:
            await cleanup_analysis_resources()
            logger.info("Resources cleaned up successfully")
        except Exception as e:
            logger.warning(f"Error during cleanup: {e}")
    
    def convert_transcript_to_text(self, transcript_list: list) -> str:
        """Convert transcript list to plain text."""
        if not transcript_list:
            return ""
        
        return " ".join([item.get('text', '') for item in transcript_list])
    
    def format_analysis_time(self, seconds: float, cached: bool = False) -> str:
        """Format analysis time for display."""
        if cached:
            return "< 1 second (cached)"
        
        if seconds < 60:
            return f"{seconds:.1f} seconds"
        else:
            minutes = int(seconds // 60)
            remaining_seconds = seconds % 60
            return f"{minutes}m {remaining_seconds:.1f}s"