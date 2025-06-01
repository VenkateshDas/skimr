"""Service for content generation operations."""

from typing import Optional, Dict, Any, List
from ..models import AnalysisResult, VideoData
from ..repositories import CacheRepository
from ..utils.logging import get_logger

logger = get_logger("content_service")


class ContentService:
    """Service for content generation and formatting."""
    
    def __init__(self, cache_repository: CacheRepository):
        self.cache_repo = cache_repository
        logger.info("Initialized ContentService")
    
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