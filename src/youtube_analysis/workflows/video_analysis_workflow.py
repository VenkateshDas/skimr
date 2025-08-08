"""Workflow for complete video analysis process."""

from typing import List, Optional, Dict, Any, Callable, Tuple
from ..models import AnalysisResult, VideoData
from ..services import AnalysisService, TranscriptService, ChatService, ContentService
from ..utils.logging import get_logger
from ..core.config import config

logger = get_logger("video_analysis_workflow")


class VideoAnalysisWorkflow:
    """
    Orchestrates the complete video analysis workflow.
    
    Features:
    - End-to-end video analysis
    - Chat setup integration
    - Error recovery
    - Performance monitoring
    """
    
    def __init__(
        self,
        analysis_service: AnalysisService,
        transcript_service: TranscriptService,
        chat_service: ChatService,
        content_service: ContentService
    ):
        self.analysis_service = analysis_service
        self.transcript_service = transcript_service
        self.chat_service = chat_service
        self.content_service = content_service
        logger.info("Initialized VideoAnalysisWorkflow")
    
    async def analyze_video_complete(
        self,
        youtube_url: str,
        analysis_types: Optional[List[str]] = None,
        use_cache: bool = True,
        progress_callback: Optional[Callable[[int], None]] = None,
        status_callback: Optional[Callable[[str], None]] = None,
        model_name: str = None,
        temperature: float = None
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Complete video analysis workflow including chat setup.
        
        Returns:
            Tuple of (complete_results, error_message)
        """
        try:
            # Use config defaults if not provided
            if model_name is None:
                model_name = config.llm.default_model
            if temperature is None:
                temperature = config.llm.default_temperature
            if analysis_types is None:
                analysis_types = config.analysis.available_analysis_types.copy()
            
            # Step 1: Run analysis
            if status_callback:
                status_callback("Starting video analysis...")
            
            analysis_result, error = await self.analysis_service.analyze_video(
                youtube_url=youtube_url,
                analysis_types=analysis_types,
                use_cache=use_cache,
                progress_callback=self._create_sub_progress_callback(progress_callback, 0, 80),
                status_callback=status_callback,
                model_name=model_name,
                temperature=temperature
            )
            
            if error:
                return None, error
            
            if not analysis_result:
                return None, "Analysis failed to produce results"
            
            # Step 2: Set up chat
            if progress_callback:
                progress_callback(85)
            if status_callback:
                status_callback("Setting up chat functionality...")
            
            chat_details = await self.chat_service.setup_chat(youtube_url)
            
            # Step 3: Prepare complete results
            if progress_callback:
                progress_callback(95)
            if status_callback:
                status_callback("Preparing results...")
            
            complete_results = await self._prepare_complete_results(analysis_result, chat_details)
            
            if progress_callback:
                progress_callback(100)
            if status_callback:
                status_callback("Analysis completed successfully!")
            
            logger.info(f"Complete video analysis workflow finished for {youtube_url}")
            return complete_results, None
            
        except Exception as e:
            error_msg = f"Error in video analysis workflow: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return None, error_msg
    
    def _create_sub_progress_callback(
        self, 
        main_callback: Optional[Callable[[int], None]], 
        start_percent: int, 
        end_percent: int
    ) -> Optional[Callable[[int], None]]:
        """Create a sub-progress callback that maps to a portion of the main progress."""
        if not main_callback:
            return None
        
        def sub_callback(progress: int):
            # Map progress from 0-100 to start_percent-end_percent
            mapped_progress = start_percent + (progress * (end_percent - start_percent) // 100)
            main_callback(mapped_progress)
        
        return sub_callback
    
    async def _prepare_complete_results(
        self, 
        analysis_result: AnalysisResult, 
        chat_details: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Prepare complete results dictionary."""
        # Convert analysis result to dict
        results = analysis_result.to_dict()
        
        # Add legacy format compatibility
        task_outputs = {}
        for task_name, task_output in analysis_result.task_outputs.items():
            task_outputs[task_name] = task_output.content
        
        # Get transcript information using transcript service
        transcript = None
        transcript_segments = None
        
        try:
            # Use the transcript service to get transcript data
            transcript = await self.transcript_service.get_transcript(analysis_result.youtube_url, use_cache=True)
            
            # Get transcript segments using transcript service
            timestamped_transcript, segments_list = await self.transcript_service.get_timestamped_transcript(
                analysis_result.youtube_url, use_cache=True
            )
            
            if segments_list:
                transcript_segments = segments_list
                logger.info(f"Retrieved {len(transcript_segments)} transcript segments")
            
        except Exception as e:
            logger.warning(f"Could not retrieve transcript using transcript service: {str(e)}")
            
            # Fallback: try to get video data from cache
            try:
                from ..repositories import CacheRepository
                from ..core import CacheManager
                cache_manager = CacheManager()
                cache_repo = CacheRepository(cache_manager)
                
                video_data = await cache_repo.get_video_data(analysis_result.video_id)
                
                if video_data:
                    transcript = video_data.transcript if hasattr(video_data, 'transcript') else None
                    
                    if hasattr(video_data, 'transcript_segments') and video_data.transcript_segments:
                        transcript_segments = [
                            {
                                "text": seg.text,
                                "start": seg.start,
                                "duration": seg.duration
                            } for seg in video_data.transcript_segments
                        ]
                        
            except Exception as fallback_error:
                logger.warning(f"Fallback transcript retrieval also failed: {str(fallback_error)}")
                
        # Log the result
        if transcript:
            logger.info(f"Successfully retrieved transcript (length: {len(transcript)})")
        else:
            logger.warning("No transcript retrieved for complete results")
        
        # Try to get video info for complete results
        video_info = None
        try:
            # Use analysis_service's repositories to avoid constructing new, incorrect dependencies
            youtube_repo = getattr(self.analysis_service, "youtube_repo", None)
            if youtube_repo and hasattr(youtube_repo, "_get_video_info"):
                video_info_obj = await youtube_repo._get_video_info(analysis_result.youtube_url)
                if video_info_obj:
                    video_info = {
                        "title": getattr(video_info_obj, 'title', None) or f"YouTube Video ({analysis_result.video_id})",
                        "description": getattr(video_info_obj, 'description', ""),
                        "duration": getattr(video_info_obj, 'duration', None),
                        "view_count": getattr(video_info_obj, 'view_count', None),
                        "channel_name": getattr(video_info_obj, 'channel_name', None),
                    }
            else:
                logger.debug("YouTube repository not available from analysis_service; skipping enhanced video info fetch")
        except Exception as e:
            logger.warning(f"Could not get video info: {str(e)}")
            video_info = {"title": "YouTube Video", "description": ""}

        results.update({
            # Legacy format fields
            "task_outputs": task_outputs,
            "category": analysis_result.category.value,
            "context_tag": analysis_result.context_tag.value,
            "token_usage": analysis_result.total_token_usage.to_dict() if analysis_result.total_token_usage else None,
            "timestamp": analysis_result.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "cached": analysis_result.cached,
            
            # Add transcript information
            "transcript": transcript,
            "transcript_segments": transcript_segments,
            
            # Add video info
            "video_info": video_info,
            
            # Add chat details
            "chat_details": chat_details,
            
            # Additional metadata
            "workflow_version": "2.0",
            "performance_optimized": True
        })
        
        return results
    
    async def get_analysis_status(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Get analysis status for a video."""
        analysis_result = await self.analysis_service.get_analysis_status(video_id)
        if not analysis_result:
            return None
        
        return {
            "video_id": video_id,
            "status": analysis_result.status.value,
            "created_at": analysis_result.created_at.isoformat(),
            "analysis_time": analysis_result.analysis_time,
            "task_count": len(analysis_result.task_outputs),
            "cached": analysis_result.cached,
            "error_message": analysis_result.error_message
        }
    
    async def invalidate_cache(self, video_id: str) -> bool:
        """Invalidate cache for a video."""
        return await self.analysis_service.invalidate_cache(video_id)
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get comprehensive performance statistics."""
        return self.analysis_service.get_performance_stats()