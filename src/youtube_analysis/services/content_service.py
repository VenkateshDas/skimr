"""Service for content generation operations."""

from typing import Optional, Dict, Any, List, Callable, Tuple
from ..models import AnalysisResult, VideoData, TaskOutput, TokenUsage
from ..repositories import CacheRepository
from ..utils.logging import get_logger
from ..workflows.crew import YouTubeAnalysisCrew
from ..core import LLMManager
from ..core.config import config

logger = get_logger("content_service")


class ContentService:
    """Service for content generation and formatting."""
    
    def __init__(self, cache_repository: CacheRepository):
        self.cache_repo = cache_repository
        self.llm_manager = LLMManager()
        logger.info("Initialized ContentService")
    
    async def generate_single_content(
        self,
        video_id: str,
        youtube_url: str,
        transcript_text: str,
        content_type: str,
        model_name: str = None,
        temperature: float = None,
        progress_callback: Optional[Callable[[int], None]] = None,
        status_callback: Optional[Callable[[str], None]] = None
    ) -> Tuple[Optional[str], Optional[Dict[str, int]]]:
        """
        Generate a single content type for a video.
        
        Args:
            video_id: Video ID
            youtube_url: YouTube URL
            transcript_text: Video transcript text
            content_type: Type of content to generate (task name)
            model_name: LLM model to use (defaults to config)
            temperature: Temperature for generation (defaults to config)
            progress_callback: Progress callback function
            status_callback: Status callback function
            
        Returns:
            Tuple of (generated content string, token usage dict) or (None, None) if failed
        """
        try:
            # Use config defaults if not provided
            if model_name is None:
                model_name = config.llm.default_model
            if temperature is None:
                temperature = config.llm.default_temperature
            
            logger.info(f"Generating {content_type} for video {video_id}")
            
            if status_callback:
                status_callback(f"Generating {content_type}...")
            
            # Create crew instance
            crew = YouTubeAnalysisCrew(
                model_name=model_name,
                temperature=temperature
            )
            
            # Map content type to task creation method
            task_methods = {
                "analyze_and_plan_content": crew.analyze_and_plan_content,
                "write_blog_post": crew.write_blog_post,
                "write_linkedin_post": crew.write_linkedin_post,
                "write_tweet": crew.write_tweet
            }
            
            task_method = task_methods.get(content_type)
            if not task_method:
                logger.error(f"Unknown content type: {content_type}")
                return None, None
            
            # Get existing analysis result for context
            analysis_result = await self.cache_repo.get_analysis_result(video_id)
            
            # Prepare inputs for crew
            from datetime import datetime
            
            # Get video title if available from analysis result
            video_title = f"Video {video_id}"  # Fallback title
            if analysis_result and hasattr(analysis_result, 'video_info') and analysis_result.video_info:
                video_title = analysis_result.video_info.get('title', video_title)
            
            crew_inputs = {
                "youtube_url": youtube_url,
                "transcript": transcript_text,
                "current_datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "video_title": video_title
            }
            
            # Add classification results if available
            if analysis_result and "classify_and_summarize_content" in analysis_result.task_outputs:
                summary_output = analysis_result.task_outputs["classify_and_summarize_content"]
                crew_inputs["summary"] = summary_output.content
                crew_inputs["category"] = analysis_result.category.value
                crew_inputs["context_tag"] = analysis_result.context_tag.value
            
            # Create a mini crew with just the required task
            # First, always include summary task for context
            tasks = [crew.classify_and_summarize_content()]
            
            # Add the specific task we want
            if content_type == "analyze_and_plan_content":
                tasks.append(crew.analyze_and_plan_content())
            elif content_type in ["write_blog_post", "write_linkedin_post", "write_tweet"]:
                # These tasks need context from both summary and action plan
                tasks.append(crew.analyze_and_plan_content())
                tasks.append(task_method())
            
            # Create and execute the crew
            from crewai import Crew, Process
            
            # Extract unique agents from tasks
            agents = []
            seen_agents = set()
            for task in tasks:
                if hasattr(task, 'agent') and task.agent not in seen_agents:
                    agents.append(task.agent)
                    seen_agents.add(task.agent)
            
            mini_crew = Crew(
                agents=agents,
                tasks=tasks,
                process=Process.sequential,
                verbose=True
            )
            
            # Execute the crew
            result = mini_crew.kickoff(inputs=crew_inputs)
            
            if not result:
                logger.error(f"Failed to generate {content_type}")
                return None, None
            
            # Extract content from crew result
            # The result is the final task's output
            if hasattr(result, 'raw'):
                content = result.raw
            elif hasattr(result, 'output'):
                content = result.output
            else:
                content = str(result)
            
            # Extract token usage from crew result
            token_usage_dict = None
            if hasattr(result, 'token_usage') and result.token_usage:
                token_usage = result.token_usage
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
                logger.info(f"Token usage for {content_type}: {token_usage_dict}")
            else:
                logger.warning(f"No token usage found for {content_type}")
                token_usage_dict = {
                    "total_tokens": 0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0
                }
            
            logger.info(f"Successfully generated {content_type}, content length: {len(content) if content else 0}")
            
            # Update analysis result with new content and token usage
            if analysis_result:
                task_token_usage = None
                if token_usage_dict:
                    task_token_usage = TokenUsage(
                        total_tokens=token_usage_dict.get("total_tokens", 0),
                        prompt_tokens=token_usage_dict.get("prompt_tokens", 0),
                        completion_tokens=token_usage_dict.get("completion_tokens", 0)
                    )
                
                task_output = TaskOutput(
                    task_name=content_type,
                    content=content,
                    token_usage=task_token_usage,
                    execution_time=0.0  # Would need to measure
                )
                analysis_result.task_outputs[content_type] = task_output
                await self.cache_repo.save_analysis_result(video_id, analysis_result)
                logger.info(f"Updated cached analysis with {content_type}")
            
            if progress_callback:
                progress_callback(100)
            
            return content, token_usage_dict
            
        except Exception as e:
            logger.error(f"Error generating {content_type}: {str(e)}", exc_info=True)
            return None, None
    
    async def get_formatted_content(
        self, 
        video_id: str, 
        content_type: str
    ) -> Optional[Dict[str, Any]]:
        """Get formatted content for display."""
        analysis_result = await self.cache_repo.get_analysis_result(video_id)
        if not analysis_result:
            return None
        
        task_mapping = {
            "Summary & Classification": "classify_and_summarize_content",
            "Action Plan": "analyze_and_plan_content", 
            "Blog Post": "write_blog_post",
            "LinkedIn Post": "write_linkedin_post",
            "X Tweet": "write_tweet"
        }
        
        task_name = task_mapping.get(content_type)
        if not task_name or task_name not in analysis_result.task_outputs:
            return None
        
        task_output = analysis_result.task_outputs[task_name]
        
        return {
            "content": task_output.content,
            "task_name": task_output.task_name,
            "category": analysis_result.category.value,
            "context_tag": analysis_result.context_tag.value,
            "token_usage": task_output.token_usage.to_dict() if task_output.token_usage else None,
            "execution_time": task_output.execution_time
        }
    
    def format_content_for_export(self, content: str, format_type: str = "markdown") -> str:
        """Format content for export."""
        if format_type == "markdown":
            return content
        elif format_type == "plain":
            # Strip markdown formatting
            import re
            content = re.sub(r'\*\*(.*?)\*\*', r'\1', content)  # Bold
            content = re.sub(r'\*(.*?)\*', r'\1', content)      # Italic
            content = re.sub(r'#{1,6}\s', '', content)          # Headers
            return content
        else:
            return content