"""
WebApp adapter for integrating the service layer with Streamlit.
Provides a clean interface between Streamlit webapp and the Phase 2 service layer architecture.
"""

import os
import asyncio
from typing import Dict, Any, Optional, Tuple, Callable, List, AsyncGenerator
from datetime import datetime

from ..service_factory import get_service_factory
from ..utils.logging import get_logger
from ..utils.youtube_utils import validate_youtube_url, extract_video_id, get_video_info
from ..utils.cache_utils import clear_analysis_cache
from ..utils.video_highlights import clear_highlights_cache

logger = get_logger("webapp_adapter")


class WebAppAdapter:
    """
    Adapter that provides a clean interface between Streamlit webapp 
    and the Phase 2 service layer architecture.
    """
    
    def __init__(self, progress_callbacks=None):
        self.service_factory = get_service_factory()
        self.callbacks = progress_callbacks  # StreamlitCallbacks instance
        
    def validate_youtube_url(self, url: str) -> bool:
        """Validate YouTube URL."""
        return validate_youtube_url(url)
    
    def get_video_info(self, url: str) -> Optional[Dict[str, Any]]:
        """Get video information for preview."""
        try:
            return get_video_info(url)
        except Exception as e:
            logger.error(f"Error getting video info: {e}")
            return None
    
    async def analyze_video(
        self, 
        youtube_url: str, 
        settings: Dict[str, Any]
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Run video analysis using the Phase 2 architecture.
        
        Args:
            youtube_url: YouTube video URL
            settings: Dictionary containing model, temperature, use_cache, analysis_types
            
        Returns:
            Tuple of (results dict, error message)
        """
        try:
            # Extract settings
            model_name = settings.get("model", "gpt-4o-mini")
            temperature = settings.get("temperature", 0.2)
            use_cache = settings.get("use_cache", True)
            analysis_types = settings.get("analysis_types", ["Summary & Classification"])
            
            # Ensure required analysis type is included
            if "Summary & Classification" not in analysis_types:
                analysis_types = ["Summary & Classification"] + analysis_types
            
            logger.info(f"Starting video analysis: {youtube_url}")
            logger.info(f"Settings: model={model_name}, temperature={temperature}, cache={use_cache}")
            
            # Get video analysis workflow from service factory
            workflow = self.service_factory.get_video_analysis_workflow()
            
            # Update progress callback
            if self.callbacks:
                self.callbacks.update_status("Initializing analysis...")
                self.callbacks.update_progress(5)
            
            # Run analysis through workflow
            result_tuple = await workflow.analyze_video_complete(
                youtube_url=youtube_url,
                analysis_types=analysis_types,
                use_cache=use_cache,
                progress_callback=self.callbacks.update_progress if self.callbacks else None,
                status_callback=self.callbacks.update_status if self.callbacks else None,
                model_name=model_name,
                temperature=temperature
            )
            
            # Handle tuple return from workflow
            if isinstance(result_tuple, tuple) and len(result_tuple) == 2:
                results, workflow_error = result_tuple
                if workflow_error:
                    return None, workflow_error
                if not results:
                    return None, "Analysis failed to produce results"
            else:
                # Fallback for non-tuple return
                results = result_tuple
                if not results:
                    return None, "Analysis failed to produce results"
            
            # Ensure results have proper structure
            if not isinstance(results, dict):
                return None, f"Invalid results type: {type(results)}"
            
            # Add video URL to results for reference
            results["youtube_url"] = youtube_url
            
            # Extract video ID and add to results
            video_id = extract_video_id(youtube_url)
            if video_id:
                results["video_id"] = video_id
            
            # Get video info and add to results
            video_info = self.get_video_info(youtube_url)
            if video_info:
                results["video_info"] = video_info
            
            # Check if chat was setup successfully
            if "chat_details" not in results or not results.get("chat_details"):
                logger.warning("Chat details not included in analysis results")
                # Try to setup chat separately if needed
                try:
                    chat_service = self.service_factory.get_chat_service()
                    if hasattr(chat_service, 'setup_for_video'):
                        chat_details = await chat_service.setup_for_video(
                            video_id=video_id,
                            video_data=results.get("video_data")
                        )
                        if chat_details:
                            results["chat_details"] = chat_details
                except Exception as e:
                    logger.error(f"Failed to setup chat: {e}")
            
            logger.info("Analysis completed successfully")
            return results, None
            
        except Exception as e:
            error_msg = f"Error during video analysis: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return None, error_msg
    
    async def generate_additional_content(
        self,
        youtube_url: str,
        video_id: str,
        transcript_text: str,
        content_type: str,
        settings: Dict[str, Any]
    ) -> Tuple[Optional[str], Optional[str], Optional[Dict[str, int]]]:
        """
        Generate additional content types on demand.
        
        Args:
            youtube_url: YouTube video URL
            video_id: Video ID
            transcript_text: Video transcript text
            content_type: Type of content to generate (e.g., "Action Plan", "Blog Post")
            settings: Dictionary containing model, temperature settings
            
        Returns:
            Tuple of (generated content, error message, token usage dict)
        """
        try:
            # Extract settings
            model_name = settings.get("model", "gpt-4o-mini")
            temperature = settings.get("temperature", 0.2)
            
            logger.info(f"Generating {content_type} for video {video_id}")
            
            # Get content service from factory
            content_service = self.service_factory.get_content_service()
            
            # Map display names to task names
            content_type_mapping = {
                "Action Plan": "analyze_and_plan_content",
                "Blog Post": "write_blog_post",
                "LinkedIn Post": "write_linkedin_post",
                "X Tweet": "write_tweet"
            }
            
            task_name = content_type_mapping.get(content_type, content_type)
            
            # Update progress
            if self.callbacks:
                self.callbacks.update_status(f"Generating {content_type}...")
                self.callbacks.update_progress(10)
            
            # Generate content through service (now returns tuple with token usage)
            content, token_usage = await content_service.generate_single_content(
                video_id=video_id,
                youtube_url=youtube_url,
                transcript_text=transcript_text,
                content_type=task_name,
                model_name=model_name,
                temperature=temperature,
                progress_callback=self.callbacks.update_progress if self.callbacks else None,
                status_callback=self.callbacks.update_status if self.callbacks else None
            )
            
            if not content:
                return None, f"Failed to generate {content_type}", None
            
            # Update cached analysis results if available
            try:
                cache_repo = self.service_factory.get_cache_repository()
                cached_result = await cache_repo.get_analysis_result(video_id)
                if cached_result and cached_result.task_outputs:
                    # Create a proper TaskOutput object
                    from ..models import TaskOutput, TokenUsage
                    task_token_usage = None
                    if token_usage:
                        task_token_usage = TokenUsage(
                            total_tokens=token_usage.get("total_tokens", 0),
                            prompt_tokens=token_usage.get("prompt_tokens", 0),
                            completion_tokens=token_usage.get("completion_tokens", 0)
                        )
                    
                    task_output = TaskOutput(
                        task_name=task_name,
                        content=content,
                        token_usage=task_token_usage,
                        execution_time=0.0  # Would need to measure
                    )
                    cached_result.task_outputs[task_name] = task_output
                    await cache_repo.save_analysis_result(video_id, cached_result)
                    logger.info(f"Updated cached analysis with {content_type}")
            except Exception as e:
                logger.warning(f"Could not update cache with new content: {e}")
            
            # Explicitly save token usage to cache if available
            if token_usage and isinstance(token_usage, dict):
                try:
                    success = await self.save_token_usage_to_cache(
                        video_id, 
                        "additional_content", 
                        token_usage, 
                        task_name
                    )
                    if success:
                        logger.info(f"Saved token usage to cache for {content_type}: {token_usage}")
                    else:
                        logger.warning(f"Failed to save token usage to cache for {content_type}")
                except Exception as e:
                    logger.warning(f"Error saving token usage to cache for {content_type}: {e}")
            
            logger.info(f"{content_type} generated successfully")
            return content, None, token_usage
            
        except Exception as e:
            error_msg = f"Error generating {content_type}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return None, error_msg, None
    
    async def get_chat_response_stream(
        self,
        video_id: str,
        chat_history: List[Dict[str, str]],
        current_question: str,
        settings: Dict[str, Any]
    ) -> AsyncGenerator[Tuple[str, Optional[Dict[str, int]]], None]:
        """
        Stream chat response for a video with token usage tracking.
        
        Args:
            video_id: Video ID
            chat_history: List of previous chat messages
            current_question: Current user question
            settings: Dictionary containing model, temperature settings
            
        Yields:
            Tuple of (response chunks, token usage dict for final response)
        """
        try:
            # Extract settings
            model_name = settings.get("model", "gpt-4o-mini")
            temperature = settings.get("temperature", 0.2)
            
            logger.info(f"Streaming chat response for video {video_id}")
            
            # Get chat service from factory
            chat_service = self.service_factory.get_chat_service()
            
            # Stream response through service (now returns tuples with token usage)
            async for chunk, token_usage in chat_service.stream_response(
                video_id=video_id,
                chat_history=chat_history,
                current_question=current_question,
                model_name=model_name,
                temperature=temperature
            ):
                yield chunk, token_usage
                
        except Exception as e:
            error_msg = f"Error in chat streaming: {str(e)}"
            logger.error(error_msg, exc_info=True)
            yield f"\n\nError: {error_msg}", None

    # Keep the original method for backward compatibility
    async def get_chat_response_stream_original(
        self,
        video_id: str,
        chat_history: List[Dict[str, str]],
        current_question: str,
        settings: Dict[str, Any]
    ) -> AsyncGenerator[str, None]:
        """
        Stream chat response for a video (original method without token tracking).
        """
        async for chunk, token_usage in self.get_chat_response_stream(video_id, chat_history, current_question, settings):
            if chunk:  # Only yield non-empty chunks
                yield chunk
    
    def get_transcript_details(
        self,
        youtube_url: str,
        video_id: str,
        use_cache: bool = True
    ) -> Tuple[Optional[str], Optional[List[Dict]], Optional[str]]:
        """
        Get transcript details for a video.
        
        Returns:
            Tuple of (timestamped transcript string, segment list, error message)
        """
        try:
            logger.info(f"Getting transcript details for video {video_id}")
            
            # Get transcript service
            transcript_service = self.service_factory.get_transcript_service()
            
            # Get formatted transcripts
            timestamped, segments = asyncio.run(
                transcript_service.get_formatted_transcripts(
                    youtube_url=youtube_url,
                    video_id=video_id,
                    use_cache=use_cache
                )
            )
            
            if not timestamped or not segments:
                return None, None, "Could not retrieve transcript"
            
            return timestamped, segments, None
            
        except Exception as e:
            error_msg = f"Error getting transcript: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return None, None, error_msg
    
    async def get_video_highlights(
        self,
        youtube_url: str,
        video_id: str,
        settings: Dict[str, Any]
    ) -> Tuple[Optional[str], Optional[List[Dict]], Optional[str]]:
        """
        Generate video highlights.
        
        Returns:
            Tuple of (video path, highlight segments, error message)
        """
        try:
            logger.info(f"Generating highlights for video {video_id}")
            
            # Extract settings
            max_highlights = settings.get("max_highlights", 3)
            model_name = settings.get("model", "gpt-4o-mini")
            temperature = settings.get("temperature", 0.2)
            
            # Get content service (or dedicated highlights service if available)
            content_service = self.service_factory.get_content_service()
            
            if hasattr(content_service, 'generate_video_highlights'):
                video_path, segments = await content_service.generate_video_highlights(
                    youtube_url=youtube_url,
                    video_id=video_id,
                    max_highlights=max_highlights,
                    model_name=model_name,
                    temperature=temperature,
                    progress_callback=self.callbacks.update_progress if self.callbacks else None,
                    status_callback=self.callbacks.update_status if self.callbacks else None
                )
                
                if video_path and segments:
                    return video_path, segments, None
                else:
                    return None, None, "Failed to generate highlights"
            else:
                return None, None, "Highlights generation not available"
                
        except Exception as e:
            error_msg = f"Error generating highlights: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return None, None, error_msg
    
    def clear_cache_for_video(self, video_id: str) -> bool:
        """Clear all cached data for a specific video."""
        try:
            # Clear analysis cache
            success1 = clear_analysis_cache(video_id)
            
            # Clear highlights cache if available
            try:
                success2 = clear_highlights_cache(video_id)
            except Exception as e:
                logger.warning(f"Could not clear highlights cache: {e}")
                success2 = True  # Don't fail if highlights cache not available
            
            # Clear service layer cache
            success3 = asyncio.run(self._clear_service_cache(video_id))
            
            # Clear token usage cache
            success4 = asyncio.run(self._clear_token_usage_cache(video_id))
            
            if all([success1, success2, success3, success4]):
                logger.info(f"Successfully cleared all cache for video {video_id}")
                return True
            else:
                logger.warning(f"Partial cache clear for video {video_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error clearing cache for video {video_id}: {e}")
            return False
    
    async def _clear_service_cache(self, video_id: str) -> bool:
        """Clear service layer cache for a video."""
        try:
            workflow = self.service_factory.get_video_analysis_workflow()
            # Access cache repository through analysis service
            cache_repo = workflow.analysis_service.cache_repo
            await cache_repo.clear_video_cache(video_id)
            return True
        except Exception as e:
            logger.error(f"Error clearing service cache: {e}")
            return False
    
    async def _clear_token_usage_cache(self, video_id: str) -> bool:
        """Clear token usage cache for a video."""
        try:
            workflow = self.service_factory.get_video_analysis_workflow()
            # Access cache repository through analysis service
            cache_repo = workflow.analysis_service.cache_repo
            await cache_repo.clear_token_usage_cache(video_id)
            return True
        except Exception as e:
            logger.error(f"Error clearing token usage cache: {e}")
            return False

    # Token Usage Caching Methods
    async def get_cached_token_usage(self, video_id: str) -> Optional[Dict[str, Any]]:
        """
        Get cached token usage data for a video.
        
        Args:
            video_id: Video ID
            
        Returns:
            Dictionary with token usage data or None if not found
        """
        try:
            workflow = self.service_factory.get_video_analysis_workflow()
            # Access cache repository through analysis service
            cache_repo = workflow.analysis_service.cache_repo
            return await cache_repo.get_token_usage_for_session_manager(video_id)
        except Exception as e:
            logger.error(f"Error getting cached token usage for {video_id}: {e}")
            return None
    
    async def save_token_usage_to_cache(
        self, 
        video_id: str, 
        operation_type: str,
        token_usage: Dict[str, int],
        operation_name: Optional[str] = None
    ) -> bool:
        """
        Save token usage to cache.
        
        Args:
            video_id: Video ID
            operation_type: Type of operation ('initial_analysis', 'additional_content', 'chat')
            token_usage: Token usage dictionary
            operation_name: Name of the specific operation (for additional_content)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            workflow = self.service_factory.get_video_analysis_workflow()
            # Access cache repository through analysis service
            cache_repo = workflow.analysis_service.cache_repo
            from ..models import TokenUsage
            token_usage_obj = TokenUsage.from_dict(token_usage)
            await cache_repo.update_token_usage_cache(
                video_id, operation_type, token_usage_obj, operation_name
            )
            return True
        except Exception as e:
            logger.error(f"Error saving token usage to cache: {e}")
            return False
    
    async def initialize_token_usage_cache(self, video_id: str) -> Optional[Dict[str, Any]]:
        """
        Initialize token usage cache for a video.
        
        Args:
            video_id: Video ID
            
        Returns:
            Cached token usage data if available, None otherwise
        """
        try:
            return await self.get_cached_token_usage(video_id)
        except Exception as e:
            logger.error(f"Error initializing token usage cache: {e}")
            return None
    
    async def cleanup_resources(self):
        """Cleanup adapter resources."""
        try:
            # Get the workflow to cleanup its resources
            workflow = self.service_factory.get_video_analysis_workflow()
            if hasattr(workflow, 'cleanup'):
                await workflow.cleanup()
            
            # Clear any background tasks in the callbacks
            if self.callbacks and hasattr(self.callbacks, 'cleanup'):
                self.callbacks.cleanup()
                
            logger.info("WebApp adapter cleanup completed")
        except Exception as e:
            logger.error(f"Error during adapter cleanup: {e}")

    # Chat Session Management Methods
    async def get_cached_chat_messages(self, video_id: str) -> List[Dict[str, str]]:
        """
        Get cached chat messages for a video.
        
        Args:
            video_id: Video ID
            
        Returns:
            List of chat messages in Streamlit format
        """
        try:
            chat_service = self.service_factory.get_chat_service()
            return await chat_service.get_cached_chat_messages(video_id)
        except Exception as e:
            logger.error(f"Error getting cached chat messages: {str(e)}")
            return []
    
    async def save_chat_messages_to_cache(
        self, 
        video_id: str, 
        messages: List[Dict[str, str]]
    ) -> bool:
        """
        Save chat messages to cache.
        
        Args:
            video_id: Video ID
            messages: List of chat messages from Streamlit
            
        Returns:
            True if successful, False otherwise
        """
        try:
            chat_service = self.service_factory.get_chat_service()
            return await chat_service.update_chat_session_with_messages(video_id, messages)
        except Exception as e:
            logger.error(f"Error saving chat messages to cache: {str(e)}")
            return False
    
    async def initialize_chat_session_with_welcome(
        self, 
        video_id: str, 
        youtube_url: str, 
        video_title: str,
        agent_details: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, str]]:
        """
        Initialize a chat session with welcome message and return messages.
        
        Args:
            video_id: Video ID
            youtube_url: YouTube URL
            video_title: Video title
            agent_details: Agent details from analysis
            
        Returns:
            List of initial messages including welcome message
        """
        try:
            chat_service = self.service_factory.get_chat_service()
            chat_session = await chat_service.initialize_chat_session_with_welcome(
                video_id, youtube_url, video_title, agent_details
            )
            
            if chat_session:
                # Convert to Streamlit format
                messages = []
                for msg in chat_session.messages:
                    messages.append({
                        "role": msg.role.value,
                        "content": msg.content
                    })
                return messages
            
            return []
            
        except Exception as e:
            logger.error(f"Error initializing chat session with welcome: {str(e)}")
            return []
    
    async def clear_chat_session(self, video_id: str) -> bool:
        """
        Clear chat session for a video.
        
        Args:
            video_id: Video ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            chat_service = self.service_factory.get_chat_service()
            return await chat_service.clear_chat_session(video_id)
        except Exception as e:
            logger.error(f"Error clearing chat session: {str(e)}")
            return False
    
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