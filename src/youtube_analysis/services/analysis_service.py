"""Service for video analysis operations."""

import asyncio
from typing import List, Optional, Dict, Any, Callable, Tuple
from datetime import datetime

from ..models import VideoData, AnalysisResult, AnalysisStatus, ContentCategory, ContextTag, TaskOutput, TokenUsage
from ..repositories import CacheRepository, YouTubeRepository
from ..workflows.crew import YouTubeAnalysisCrew
from ..core import LLMManager
from ..utils.logging import get_logger
from ..core.config import config

logger = get_logger("analysis_service")


class AnalysisService:
    """
    Service for handling video analysis with improved architecture.
    
    Features:
    - Clean separation of concerns
    - Better error handling
    - Performance monitoring
    - Resource management
    """
    
    def __init__(
        self,
        cache_repository: CacheRepository,
        youtube_repository: YouTubeRepository,
        llm_manager: LLMManager
    ):
        self.cache_repo = cache_repository
        self.youtube_repo = youtube_repository
        self.llm_manager = llm_manager
        logger.info("Initialized AnalysisService")
    
    async def analyze_video(
        self,
        youtube_url: str,
        analysis_types: Optional[List[str]] = None,
        use_cache: bool = True,
        progress_callback: Optional[Callable[[int], None]] = None,
        status_callback: Optional[Callable[[str], None]] = None,
        model_name: str = None,
        temperature: float = None
    ) -> Tuple[Optional[AnalysisResult], Optional[str]]:
        """
        Analyze a YouTube video with comprehensive error handling.
        
        Args:
            youtube_url: YouTube video URL
            analysis_types: Types of analysis to perform
            use_cache: Whether to use cached results
            progress_callback: Progress update callback
            status_callback: Status update callback
            model_name: LLM model to use (defaults to config)
            temperature: LLM temperature setting (defaults to config)
            
        Returns:
            Tuple of (AnalysisResult, error_message)
        """
        start_time = datetime.now()
        
        # Use config defaults if not provided
        if model_name is None:
            model_name = config.llm.default_model
        if temperature is None:
            temperature = config.llm.default_temperature
        
        # Default analysis types from config
        if analysis_types is None:
            analysis_types = config.analysis.available_analysis_types.copy()
        
        try:
            # Extract video ID
            video_id = self.youtube_repo.extract_video_id(youtube_url)
            if not video_id:
                return None, f"Invalid YouTube URL: {youtube_url}"
            
            logger.info(f"Starting analysis for video {video_id}")
            
            if progress_callback:
                progress_callback(0)
            if status_callback:
                status_callback("Checking cache...")
            
            # Check cache first
            if use_cache and config.cache.enable_cache:
                try:
                    cached_result = await self.cache_repo.get_analysis_result(video_id)
                    if cached_result and cached_result.is_successful:
                        logger.info(f"Using cached analysis for video {video_id}")
                        
                        # Update timing
                        end_time = datetime.now()
                        cached_result.analysis_time = (end_time - start_time).total_seconds()
                        cached_result.cached = True
                        
                        if progress_callback:
                            progress_callback(100)
                        if status_callback:
                            status_callback("Using cached results...")
                        
                        return cached_result, None
                except Exception as cache_error:
                    # Log but continue with fresh analysis
                    logger.warning(f"Error retrieving from cache: {str(cache_error)}")
            
            if progress_callback:
                progress_callback(10)
            if status_callback:
                status_callback("Fetching video data...")
            
            # Fetch video data
            video_data = await self.youtube_repo.get_video_data(youtube_url)
            if not video_data:
                return None, "Failed to fetch video data"
            
            # Ensure video_data has the required attributes
            if not hasattr(video_data, 'has_transcript'):
                # Try to check if transcript exists in another way
                has_transcript = (
                    (hasattr(video_data, 'transcript') and video_data.transcript is not None) or
                    (hasattr(video_data, 'transcript_segments') and video_data.transcript_segments)
                )
            else:
                has_transcript = video_data.has_transcript
                
            if not has_transcript:
                return None, "No transcript available for this video"
            
            if progress_callback:
                progress_callback(30)
            if status_callback:
                status_callback("Running analysis...")
            
            # Run analysis
            analysis_result = await self._execute_analysis(
                video_data,
                analysis_types,
                model_name,
                temperature,
                progress_callback,
                status_callback
            )
            
            if not analysis_result:
                return None, "Analysis execution failed"
            
            # Calculate total time
            end_time = datetime.now()
            analysis_result.analysis_time = (end_time - start_time).total_seconds()
            
            if progress_callback:
                progress_callback(95)
            if status_callback:
                status_callback("Caching results...")
            
            # Cache the results
            if use_cache and config.cache.enable_cache:
                try:
                    await self.cache_repo.store_analysis_result(analysis_result)
                except Exception as cache_error:
                    logger.warning(f"Error storing analysis in cache: {str(cache_error)}")
                    # Continue without failing the whole operation
            
            if progress_callback:
                progress_callback(100)
            if status_callback:
                status_callback("Analysis completed!")
            
            logger.info(f"Analysis completed for video {video_id} in {analysis_result.analysis_time:.2f}s")
            return analysis_result, None
            
        except Exception as e:
            error_msg = f"Error analyzing video {youtube_url}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return None, error_msg
    
    async def _execute_analysis(
        self,
        video_data: VideoData,
        analysis_types: List[str],
        model_name: str,
        temperature: float,
        progress_callback: Optional[Callable[[int], None]] = None,
        status_callback: Optional[Callable[[str], None]] = None
    ) -> Optional[AnalysisResult]:
        """Execute the actual analysis using CrewAI."""
        try:
            # Create analysis result
            result = AnalysisResult(
                video_id=video_data.video_id,
                youtube_url=video_data.youtube_url,
                status=AnalysisStatus.IN_PROGRESS
            )
            
            # Create CrewAI instance
            crew_instance = YouTubeAnalysisCrew(model_name=model_name, temperature=temperature)
            # Convert analysis_types to tuple to satisfy memoization requirements
            analysis_types_tuple = tuple(analysis_types)
            crew = crew_instance.crew(analysis_types=analysis_types_tuple)
            
            # Prepare inputs
            inputs = {
                "youtube_url": video_data.youtube_url,
                "transcript": video_data.transcript,
                "current_datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "video_title": video_data.video_info.title,
                # Always provide this so task templates with {custom_instruction} don't fail
                "custom_instruction": ""
            }
            
            logger.info(f"Executing crew with {len(crew.tasks)} tasks")
            
            # Execute crew
            crew_output = crew.kickoff(inputs=inputs)
            
            # Process task outputs
            for task in crew.tasks:
                if hasattr(task, 'output') and task.output:
                    task_name = task.name if hasattr(task, 'name') else task.__class__.__name__
                    
                    task_output = TaskOutput(
                        task_name=task_name,
                        content=task.output.raw,
                        status=AnalysisStatus.COMPLETED
                    )
                    
                    result.add_task_output(task_output)
                    
                    # Update progress
                    if progress_callback and task_name == "classify_and_summarize_content":
                        progress_callback(70)
                    elif progress_callback and task_name == "analyze_and_plan_content":
                        progress_callback(85)
            
            # Validate results
            if not result.has_content:
                logger.error("No task outputs generated")
                result.status = AnalysisStatus.FAILED
                result.error_message = "No task outputs generated"
                return result
            
            # Extract category and context
            classification_output = result.task_outputs.get("classify_and_summarize_content")
            if classification_output:
                result.category = self._extract_category(classification_output.content)
                result.context_tag = self._extract_context_tag(classification_output.content)
            
            # Get token usage
            if hasattr(crew_output, 'token_usage') and crew_output.token_usage:
                token_usage = crew_output.token_usage
                if hasattr(token_usage, 'get'):
                    result.total_token_usage = TokenUsage.from_dict(token_usage)
                else:
                    result.total_token_usage = TokenUsage(
                        total_tokens=getattr(token_usage, 'total_tokens', 0),
                        prompt_tokens=getattr(token_usage, 'prompt_tokens', 0),
                        completion_tokens=getattr(token_usage, 'completion_tokens', 0)
                    )
            
            result.status = AnalysisStatus.COMPLETED
            logger.info(f"Analysis completed successfully with {len(result.task_outputs)} task outputs")
            return result
            
        except Exception as e:
            logger.error(f"Error executing analysis: {str(e)}", exc_info=True)
            return None
    
    def _extract_category(self, output: str) -> ContentCategory:
        """Extract category from classification output."""
        categories = {
            "Technology": ContentCategory.TECHNOLOGY,
            "Business": ContentCategory.BUSINESS,
            "Education": ContentCategory.EDUCATION,
            "Health & Wellness": ContentCategory.HEALTH_WELLNESS,
            "Science": ContentCategory.SCIENCE,
            "Finance": ContentCategory.FINANCE,
            "Personal Development": ContentCategory.PERSONAL_DEVELOPMENT,
            "Entertainment": ContentCategory.ENTERTAINMENT
        }
        
        for category_name, category_enum in categories.items():
            if category_name in output:
                return category_enum
        
        if "Other" in output:
            return ContentCategory.OTHER
        
        return ContentCategory.UNCATEGORIZED
    
    def _extract_context_tag(self, output: str) -> ContextTag:
        """Extract context tag from classification output."""
        context_tags = {
            "Tutorial": ContextTag.TUTORIAL,
            "News": ContextTag.NEWS,
            "Review": ContextTag.REVIEW,
            "Case Study": ContextTag.CASE_STUDY,
            "Interview": ContextTag.INTERVIEW,
            "Opinion Piece": ContextTag.OPINION_PIECE,
            "How-To Guide": ContextTag.HOW_TO_GUIDE
        }
        
        for tag_name, tag_enum in context_tags.items():
            if tag_name in output:
                return tag_enum
        
        return ContextTag.GENERAL
    
    async def get_analysis_status(self, video_id: str) -> Optional[AnalysisResult]:
        """Get analysis status for a video."""
        return await self.cache_repo.get_analysis_result(video_id)
    
    async def invalidate_cache(self, video_id: str) -> bool:
        """Invalidate cache for a specific video."""
        try:
            # This would need implementation in the cache repository
            # For now, we'll just log the action
            logger.info(f"Cache invalidation requested for video {video_id}")
            return True
        except Exception as e:
            logger.error(f"Error invalidating cache for {video_id}: {str(e)}")
            return False
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics."""
        return {
            "cache_stats": self.cache_repo.get_cache_stats(),
            "connection_stats": self.youtube_repo.get_connection_stats(),
            "llm_cache_info": self.llm_manager.get_cache_info()
        }