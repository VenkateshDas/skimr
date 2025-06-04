"""Video analysis models for the API."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, validator

from ...utils.youtube_utils import validate_youtube_url


class VideoAnalysisRequest(BaseModel):
    """Video analysis request model."""
    
    youtube_url: str = Field(..., description="YouTube video URL")
    analysis_types: List[str] = Field(
        default=["Summary & Classification"], 
        description="Types of analysis to perform"
    )
    model_name: Optional[str] = Field(default=None, description="LLM model to use")
    temperature: Optional[float] = Field(
        default=None, 
        ge=0.0, 
        le=1.0, 
        description="Generation temperature"
    )
    use_cache: bool = Field(default=True, description="Whether to use cached results")
    custom_instruction: Optional[str] = Field(
        default="", 
        description="Custom instruction for analysis"
    )
    
    @validator("youtube_url")
    def validate_youtube_url_format(cls, v):
        """Validate YouTube URL format."""
        if not validate_youtube_url(v):
            raise ValueError("Invalid YouTube URL")
        return v
    
    @validator("analysis_types")
    def validate_analysis_types_list(cls, v):
        """Validate analysis types."""
        valid_types = [
            "Summary & Classification",
            "Action Plan", 
            "Blog Post",
            "LinkedIn Post",
            "X Tweet"
        ]
        for analysis_type in v:
            if analysis_type not in valid_types:
                raise ValueError(f"Invalid analysis type: {analysis_type}")
        return v


class ContentGenerationRequest(BaseModel):
    """Content generation request model."""
    
    video_id: str = Field(..., description="Video ID")
    content_type: str = Field(..., description="Type of content to generate")
    model_name: Optional[str] = Field(default=None, description="LLM model to use")
    temperature: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Generation temperature"
    )
    custom_instruction: Optional[str] = Field(
        default="",
        description="Custom instruction for generation"
    )


class TranscriptRequest(BaseModel):
    """Transcript request model."""
    
    youtube_url: str = Field(..., description="YouTube video URL")
    video_id: str = Field(..., description="Video ID")
    use_cache: bool = Field(default=True, description="Whether to use cached transcript")
    
    @validator("youtube_url")
    def validate_youtube_url_format(cls, v):
        """Validate YouTube URL format."""
        if not validate_youtube_url(v):
            raise ValueError("Invalid YouTube URL")
        return v


class VideoInfo(BaseModel):
    """Video information model."""
    
    video_id: str
    title: str
    description: Optional[str] = None
    duration: Optional[int] = None
    view_count: Optional[int] = None
    channel_name: Optional[str] = None
    thumbnail_url: Optional[str] = None


class TaskOutput(BaseModel):
    """Task output model."""
    
    task_name: str
    content: str
    token_usage: Optional[Dict[str, int]] = None
    execution_time: Optional[float] = None
    status: str = "completed"


class AnalysisResponse(BaseModel):
    """Analysis response model."""
    
    video_id: str
    youtube_url: str
    video_info: Optional[VideoInfo] = None
    task_outputs: Dict[str, TaskOutput] = Field(default_factory=dict)
    total_token_usage: Optional[Dict[str, int]] = None
    analysis_time: Optional[float] = None
    cached: bool = False
    chat_details: Optional[Dict[str, Any]] = None


class ContentGenerationResponse(BaseModel):
    """Content generation response model."""
    
    content: str
    token_usage: Optional[Dict[str, int]] = None
    content_type: str


class TranscriptSegment(BaseModel):
    """Transcript segment model."""
    
    text: str
    start: float
    duration: Optional[float] = None


class TranscriptResponse(BaseModel):
    """Transcript response model."""
    
    video_id: str
    timestamped_transcript: str
    segments: List[TranscriptSegment] = Field(default_factory=list)


class ChatMessage(BaseModel):
    """Chat message model."""
    
    role: str = Field(..., description="Message role (user/assistant)")
    content: str = Field(..., description="Message content")
    timestamp: Optional[str] = None


class ChatRequest(BaseModel):
    """Chat request model."""
    
    video_id: str = Field(..., description="Video ID")
    message: str = Field(..., description="User message")
    chat_history: List[ChatMessage] = Field(default_factory=list)
    model_name: Optional[str] = Field(default=None, description="LLM model to use")
    temperature: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Generation temperature"
    )


class ChatResponse(BaseModel):
    """Chat response model."""
    
    message: str
    token_usage: Optional[Dict[str, int]] = None
    chat_session_id: Optional[str] = None