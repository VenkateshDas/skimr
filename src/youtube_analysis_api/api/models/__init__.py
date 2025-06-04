"""API models package."""

from .base import BaseResponse, SuccessResponse, ErrorResponse, HealthResponse
from .auth import (
    LoginRequest,
    LoginResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
    UserProfileResponse,
    UpdateProfileRequest
)
from .video import (
    VideoAnalysisRequest,
    AnalysisResponse,
    ContentGenerationRequest,
    ContentGenerationResponse,
    TranscriptRequest,
    TranscriptResponse,
    ChatRequest,
    ChatResponse,
    VideoInfo,
    TaskOutput
)

__all__ = [
    # Base models
    "BaseResponse",
    "SuccessResponse", 
    "ErrorResponse",
    "HealthResponse",
    
    # Auth models
    "LoginRequest",
    "LoginResponse",
    "RefreshTokenRequest",
    "RefreshTokenResponse",
    "UserProfileResponse",
    "UpdateProfileRequest",
    
    # Video models
    "VideoAnalysisRequest",
    "AnalysisResponse",
    "ContentGenerationRequest",
    "ContentGenerationResponse",
    "TranscriptRequest",
    "TranscriptResponse",
    "ChatRequest",
    "ChatResponse",
    "VideoInfo",
    "TaskOutput"
]