"""Data models for analysis results."""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from datetime import datetime
from enum import Enum


class AnalysisStatus(Enum):
    """Analysis status enumeration."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CACHED = "cached"


class ContentCategory(Enum):
    """Content category enumeration."""
    TECHNOLOGY = "Technology"
    BUSINESS = "Business"
    EDUCATION = "Education"
    HEALTH_WELLNESS = "Health & Wellness"
    SCIENCE = "Science"
    FINANCE = "Finance"
    PERSONAL_DEVELOPMENT = "Personal Development"
    ENTERTAINMENT = "Entertainment"
    OTHER = "Other"
    UNCATEGORIZED = "Uncategorized"


class ContextTag(Enum):
    """Context tag enumeration."""
    TUTORIAL = "Tutorial"
    NEWS = "News"
    REVIEW = "Review"
    CASE_STUDY = "Case Study"
    INTERVIEW = "Interview"
    OPINION_PIECE = "Opinion Piece"
    HOW_TO_GUIDE = "How-To Guide"
    GENERAL = "General"


@dataclass
class TokenUsage:
    """Token usage tracking."""
    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    
    def add(self, other: "TokenUsage") -> "TokenUsage":
        """Add another token usage."""
        return TokenUsage(
            total_tokens=self.total_tokens + other.total_tokens,
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens
        )
    
    def to_dict(self) -> Dict[str, int]:
        """Convert to dictionary."""
        return {
            "total_tokens": self.total_tokens,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TokenUsage":
        """Create from dictionary."""
        return cls(
            total_tokens=data.get("total_tokens", 0),
            prompt_tokens=data.get("prompt_tokens", 0),
            completion_tokens=data.get("completion_tokens", 0)
        )


@dataclass
class TokenUsageCache:
    """
    Comprehensive token usage tracking for caching.
    
    This stores all token usage breakdowns for a video analysis session,
    allowing for complete restoration of token usage statistics when
    loading cached results.
    """
    video_id: str
    cumulative_usage: TokenUsage = field(default_factory=TokenUsage)
    initial_analysis: Optional[TokenUsage] = None
    additional_content: Dict[str, TokenUsage] = field(default_factory=dict)
    chat_usage: Optional[TokenUsage] = None
    chat_message_count: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)
    
    def add_initial_analysis(self, token_usage: TokenUsage) -> None:
        """Add initial analysis token usage."""
        self.initial_analysis = token_usage
        self._recalculate_cumulative()
        self.last_updated = datetime.now()
    
    def add_additional_content(self, content_type: str, token_usage: TokenUsage) -> None:
        """Add additional content generation token usage."""
        self.additional_content[content_type] = token_usage
        self._recalculate_cumulative()
        self.last_updated = datetime.now()
    
    def add_chat_usage(self, token_usage: TokenUsage) -> None:
        """Add chat token usage (cumulative)."""
        if self.chat_usage is None:
            self.chat_usage = token_usage
        else:
            self.chat_usage = self.chat_usage.add(token_usage)
        self.chat_message_count += 1
        self._recalculate_cumulative()
        self.last_updated = datetime.now()
    
    def _recalculate_cumulative(self) -> None:
        """Recalculate cumulative token usage from all sources."""
        self.cumulative_usage = TokenUsage()
        
        # Add initial analysis
        if self.initial_analysis:
            self.cumulative_usage = self.cumulative_usage.add(self.initial_analysis)
        
        # Add additional content
        for content_usage in self.additional_content.values():
            self.cumulative_usage = self.cumulative_usage.add(content_usage)
        
        # Add chat
        if self.chat_usage:
            self.cumulative_usage = self.cumulative_usage.add(self.chat_usage)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "video_id": self.video_id,
            "cumulative_usage": self.cumulative_usage.to_dict(),
            "initial_analysis": self.initial_analysis.to_dict() if self.initial_analysis else None,
            "additional_content": {
                key: usage.to_dict() 
                for key, usage in self.additional_content.items()
            },
            "chat_usage": self.chat_usage.to_dict() if self.chat_usage else None,
            "chat_message_count": self.chat_message_count,
            "created_at": self.created_at.isoformat(),
            "last_updated": self.last_updated.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TokenUsageCache":
        """Create from dictionary."""
        # Parse cumulative usage
        cumulative_usage = TokenUsage()
        if data.get("cumulative_usage"):
            cumulative_usage = TokenUsage.from_dict(data["cumulative_usage"])
        
        # Parse initial analysis
        initial_analysis = None
        if data.get("initial_analysis"):
            initial_analysis = TokenUsage.from_dict(data["initial_analysis"])
        
        # Parse additional content
        additional_content = {}
        if data.get("additional_content"):
            for key, usage_data in data["additional_content"].items():
                additional_content[key] = TokenUsage.from_dict(usage_data)
        
        # Parse chat usage
        chat_usage = None
        if data.get("chat_usage"):
            chat_usage = TokenUsage.from_dict(data["chat_usage"])
        
        # Parse timestamps
        created_at = datetime.now()
        if data.get("created_at"):
            try:
                created_at = datetime.fromisoformat(data["created_at"])
            except (ValueError, TypeError):
                pass
        
        last_updated = datetime.now()
        if data.get("last_updated"):
            try:
                last_updated = datetime.fromisoformat(data["last_updated"])
            except (ValueError, TypeError):
                pass
        
        return cls(
            video_id=data["video_id"],
            cumulative_usage=cumulative_usage,
            initial_analysis=initial_analysis,
            additional_content=additional_content,
            chat_usage=chat_usage,
            chat_message_count=data.get("chat_message_count", 0),
            created_at=created_at,
            last_updated=last_updated
        )
    
    def to_session_manager_format(self) -> Dict[str, Any]:
        """
        Convert to the format expected by StreamlitSessionManager.
        
        Returns:
            Dictionary with 'cumulative_usage' and 'breakdown' keys
        """
        breakdown = {
            "initial_analysis": self.initial_analysis.to_dict() if self.initial_analysis else {},
            "additional_content": {
                key: usage.to_dict() 
                for key, usage in self.additional_content.items()
            },
            "chat": {
                **(self.chat_usage.to_dict() if self.chat_usage else {"total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0}),
                "message_count": self.chat_message_count
            }
        }
        
        return {
            "cumulative_usage": self.cumulative_usage.to_dict(),
            "breakdown": breakdown
        }


@dataclass
class TaskOutput:
    """Represents output from a single analysis task."""
    task_name: str
    content: str
    token_usage: Optional[TokenUsage] = None
    execution_time: Optional[float] = None
    status: AnalysisStatus = AnalysisStatus.COMPLETED
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "task_name": self.task_name,
            "content": self.content,
            "token_usage": self.token_usage.to_dict() if self.token_usage else None,
            "execution_time": self.execution_time,
            "status": self.status.value
        }


@dataclass
class AnalysisResult:
    """Complete analysis result."""
    video_id: str
    youtube_url: str
    status: AnalysisStatus
    task_outputs: Dict[str, TaskOutput] = field(default_factory=dict)
    category: ContentCategory = ContentCategory.UNCATEGORIZED
    context_tag: ContextTag = ContextTag.GENERAL
    total_token_usage: Optional[TokenUsage] = None
    analysis_time: Optional[float] = None
    created_at: datetime = field(default_factory=datetime.now)
    cached: bool = False
    chat_details: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    
    @property
    def is_successful(self) -> bool:
        """Check if analysis was successful."""
        return self.status in [AnalysisStatus.COMPLETED, AnalysisStatus.CACHED]
    
    @property
    def has_content(self) -> bool:
        """Check if analysis has content."""
        return len(self.task_outputs) > 0
    
    def add_task_output(self, task_output: TaskOutput) -> None:
        """Add a task output."""
        self.task_outputs[task_output.task_name] = task_output
        
        # Update total token usage
        if task_output.token_usage:
            if self.total_token_usage is None:
                self.total_token_usage = TokenUsage()
            self.total_token_usage = self.total_token_usage.add(task_output.token_usage)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "video_id": self.video_id,
            "youtube_url": self.youtube_url,
            "status": self.status.value,
            "task_outputs": {
                name: output.to_dict() 
                for name, output in self.task_outputs.items()
            },
            "category": self.category.value,
            "context_tag": self.context_tag.value,
            "total_token_usage": (
                self.total_token_usage.to_dict() 
                if self.total_token_usage else None
            ),
            "analysis_time": self.analysis_time,
            "created_at": self.created_at.isoformat(),
            "cached": self.cached,
            "chat_details": self.chat_details,
            "error_message": self.error_message
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AnalysisResult":
        """Create from dictionary."""
        if not isinstance(data, dict):
            raise TypeError(f"Expected dictionary, got {type(data)}")
            
        # Validate required fields
        for field in ["video_id", "youtube_url", "status"]:
            if field not in data:
                raise ValueError(f"Missing required field '{field}' in data")
        
        # Parse task outputs with error handling
        task_outputs = {}
        if "task_outputs" in data and isinstance(data["task_outputs"], dict):
            for name, output_data in data["task_outputs"].items():
                try:
                    if not isinstance(output_data, dict):
                        continue
                        
                    # Make sure required fields exist
                    if "task_name" not in output_data or "content" not in output_data:
                        continue
                        
                    token_usage = None
                    if output_data.get("token_usage") and isinstance(output_data["token_usage"], dict):
                        try:
                            token_usage = TokenUsage.from_dict(output_data["token_usage"])
                        except Exception:
                            # If token usage parsing fails, continue without it
                            pass
                            
                    status = AnalysisStatus.COMPLETED
                    try:
                        if "status" in output_data and output_data["status"]:
                            status = AnalysisStatus(output_data["status"])
                    except ValueError:
                        # Use default if invalid status value
                        pass
                        
                    task_outputs[name] = TaskOutput(
                        task_name=output_data["task_name"],
                        content=output_data["content"],
                        token_usage=token_usage,
                        execution_time=output_data.get("execution_time"),
                        status=status
                    )
                except Exception as e:
                    # Skip this task output if there's an error
                    continue
        
        # Parse status with fallback
        try:
            status = AnalysisStatus(data["status"])
        except ValueError:
            # Default to COMPLETED if invalid status
            status = AnalysisStatus.COMPLETED
            
        # Parse category with fallback
        try:
            category = ContentCategory(data.get("category", "Uncategorized"))
        except ValueError:
            category = ContentCategory.UNCATEGORIZED
            
        # Parse context tag with fallback
        try:
            context_tag = ContextTag(data.get("context_tag", "General"))
        except ValueError:
            context_tag = ContextTag.GENERAL
        
        # Parse token usage
        total_token_usage = None
        if data.get("total_token_usage") and isinstance(data["total_token_usage"], dict):
            try:
                total_token_usage = TokenUsage.from_dict(data["total_token_usage"])
            except Exception:
                # Continue without token usage if parsing fails
                pass
                
        # Parse created_at with fallback
        created_at = datetime.now()
        if "created_at" in data and data["created_at"]:
            try:
                created_at = datetime.fromisoformat(data["created_at"])
            except (ValueError, TypeError):
                # Use current time if parsing fails
                pass
        
        return cls(
            video_id=data["video_id"],
            youtube_url=data["youtube_url"],
            status=status,
            task_outputs=task_outputs,
            category=category,
            context_tag=context_tag,
            total_token_usage=total_token_usage,
            analysis_time=data.get("analysis_time"),
            created_at=created_at,
            cached=data.get("cached", False),
            chat_details=data.get("chat_details"),
            error_message=data.get("error_message")
        )