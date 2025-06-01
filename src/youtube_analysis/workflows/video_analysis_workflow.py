"""Workflow for complete video analysis process."""

from typing import List, Optional, Dict, Any, Callable, Tuple
from ..models import AnalysisResult, VideoData
from ..services import AnalysisService, TranscriptService, ChatService, ContentService
from ..utils.logging import get_logger

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
        model_name: str = "gpt-4o-mini",
        temperature: float = 0.2
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Complete video analysis workflow including chat setup.
        
        Returns:
            Tuple of (complete_results, error_message)
        """
        try:
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
            
            complete_results = self._prepare_complete_results(analysis_result, chat_details)
            
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
    
    def _prepare_complete_results(
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
        
        results.update({
            # Legacy format fields
            "task_outputs": task_outputs,
            "category": analysis_result.category.value,
            "context_tag": analysis_result.context_tag.value,
            "token_usage": analysis_result.total_token_usage.to_dict() if analysis_result.total_token_usage else None,
            "timestamp": analysis_result.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "cached": analysis_result.cached,
            
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