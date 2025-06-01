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