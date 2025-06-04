"""Video analysis router."""

import asyncio
import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.responses import StreamingResponse

from ...api.models.video import (
    VideoAnalysisRequest,
    AnalysisResponse,
    ContentGenerationRequest,
    ContentGenerationResponse,
    TranscriptRequest,
    TranscriptResponse,
    ChatRequest,
    ChatResponse
)
from ...api.models.base import SuccessResponse
from ...dependencies import (
    check_guest_limits,
    get_web_app_adapter,
    get_optional_user
)
from ...exceptions import (
    VideoAnalysisError,
    GuestLimitExceededError,
    ValidationError
)
from ...utils.youtube_utils import validate_youtube_url, extract_video_id

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_video(
    request: VideoAnalysisRequest,
    background_tasks: BackgroundTasks,
    user_context: Dict[str, Any] = Depends(check_guest_limits),
    web_app_adapter = Depends(get_web_app_adapter)
):
    """
    Analyze YouTube video.
    
    Args:
        request: Video analysis request
        background_tasks: FastAPI background tasks
        user_context: User context with guest limits
        web_app_adapter: WebAppAdapter instance
        
    Returns:
        Analysis results
        
    Raises:
        HTTPException: If analysis fails
    """
    try:
        # Check guest limits
        if user_context["is_guest"]:
            if user_context["remaining_requests"] <= 0:
                raise GuestLimitExceededError("Daily analysis limit exceeded for guest users")
        
        # Validate YouTube URL
        if not validate_youtube_url(request.youtube_url):
            raise ValidationError("Invalid YouTube URL format")
        
        # Extract video ID
        video_id = extract_video_id(request.youtube_url)
        if not video_id:
            raise ValidationError("Could not extract video ID from URL")
        
        # Prepare analysis parameters
        analysis_params = {
            "youtube_url": request.youtube_url,
            "analysis_types": request.analysis_types,
            "use_cache": request.use_cache,
            "custom_instruction": request.custom_instruction or ""
        }
        
        # Add optional parameters if provided
        if request.model_name:
            analysis_params["model_name"] = request.model_name
        if request.temperature is not None:
            analysis_params["temperature"] = request.temperature
        
        # Call WebAppAdapter analyze_video method
        logger.info(f"Starting video analysis for video_id: {video_id}")
        result = await asyncio.to_thread(
            web_app_adapter.analyze_video,
            **analysis_params
        )
        
        # Process result and create response
        response = AnalysisResponse(
            video_id=video_id,
            youtube_url=request.youtube_url,
            video_info=result.get("video_info"),
            task_outputs=result.get("task_outputs", {}),
            total_token_usage=result.get("total_token_usage"),
            analysis_time=result.get("analysis_time"),
            cached=result.get("cached", False),
            chat_details=result.get("chat_details")
        )
        
        # Update guest usage in background if needed
        if user_context["is_guest"]:
            background_tasks.add_task(update_guest_usage, user_context)
        
        logger.info(f"Video analysis completed for video_id: {video_id}")
        return response
        
    except GuestLimitExceededError as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e)
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except VideoAnalysisError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Video analysis failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Video analysis service error"
        )


@router.post("/generate-content", response_model=ContentGenerationResponse)
async def generate_content(
    request: ContentGenerationRequest,
    user_context: Dict[str, Any] = Depends(check_guest_limits),
    web_app_adapter = Depends(get_web_app_adapter)
):
    """
    Generate content for analyzed video.
    
    Args:
        request: Content generation request
        user_context: User context with guest limits
        web_app_adapter: WebAppAdapter instance
        
    Returns:
        Generated content
        
    Raises:
        HTTPException: If generation fails
    """
    try:
        # Check guest limits
        if user_context["is_guest"]:
            if user_context["remaining_requests"] <= 0:
                raise GuestLimitExceededError("Daily generation limit exceeded for guest users")
        
        # Prepare generation parameters
        generation_params = {
            "video_id": request.video_id,
            "content_type": request.content_type,
            "custom_instruction": request.custom_instruction or ""
        }
        
        # Add optional parameters
        if request.model_name:
            generation_params["model_name"] = request.model_name
        if request.temperature is not None:
            generation_params["temperature"] = request.temperature
        
        # Call WebAppAdapter content generation method
        logger.info(f"Starting content generation for video_id: {request.video_id}")
        result = await asyncio.to_thread(
            web_app_adapter.generate_content,
            **generation_params
        )
        
        response = ContentGenerationResponse(
            content=result.get("content", ""),
            token_usage=result.get("token_usage"),
            content_type=request.content_type
        )
        
        logger.info(f"Content generation completed for video_id: {request.video_id}")
        return response
        
    except GuestLimitExceededError as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Content generation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Content generation service error"
        )


@router.post("/transcript", response_model=TranscriptResponse)
async def get_transcript(
    request: TranscriptRequest,
    user_context: Dict[str, Any] = Depends(check_guest_limits),
    web_app_adapter = Depends(get_web_app_adapter)
):
    """
    Get video transcript.
    
    Args:
        request: Transcript request
        user_context: User context with guest limits
        web_app_adapter: WebAppAdapter instance
        
    Returns:
        Video transcript
        
    Raises:
        HTTPException: If transcript retrieval fails
    """
    try:
        # Validate YouTube URL
        if not validate_youtube_url(request.youtube_url):
            raise ValidationError("Invalid YouTube URL format")
        
        # Call WebAppAdapter transcript method
        logger.info(f"Getting transcript for video_id: {request.video_id}")
        result = await asyncio.to_thread(
            web_app_adapter.get_transcript,
            request.youtube_url,
            request.use_cache
        )
        
        response = TranscriptResponse(
            video_id=request.video_id,
            timestamped_transcript=result.get("timestamped_transcript", ""),
            segments=result.get("segments", [])
        )
        
        logger.info(f"Transcript retrieved for video_id: {request.video_id}")
        return response
        
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Transcript retrieval failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Transcript service error"
        )


@router.post("/chat", response_model=ChatResponse)
async def chat_with_video(
    request: ChatRequest,
    user_context: Dict[str, Any] = Depends(check_guest_limits),
    web_app_adapter = Depends(get_web_app_adapter)
):
    """
    Chat about analyzed video.
    
    Args:
        request: Chat request
        user_context: User context with guest limits
        web_app_adapter: WebAppAdapter instance
        
    Returns:
        Chat response
        
    Raises:
        HTTPException: If chat fails
    """
    try:
        # Check guest limits
        if user_context["is_guest"]:
            if user_context["remaining_requests"] <= 0:
                raise GuestLimitExceededError("Daily chat limit exceeded for guest users")
        
        # Prepare chat parameters
        chat_params = {
            "video_id": request.video_id,
            "message": request.message,
            "chat_history": [msg.dict() for msg in request.chat_history]
        }
        
        # Add optional parameters
        if request.model_name:
            chat_params["model_name"] = request.model_name
        if request.temperature is not None:
            chat_params["temperature"] = request.temperature
        
        # Call WebAppAdapter chat method
        logger.info(f"Starting chat for video_id: {request.video_id}")
        result = await asyncio.to_thread(
            web_app_adapter.chat_with_video,
            **chat_params
        )
        
        response = ChatResponse(
            message=result.get("message", ""),
            token_usage=result.get("token_usage"),
            chat_session_id=result.get("chat_session_id")
        )
        
        logger.info(f"Chat completed for video_id: {request.video_id}")
        return response
        
    except GuestLimitExceededError as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Chat failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Chat service error"
        )


async def update_guest_usage(user_context: Dict[str, Any]):
    """
    Update guest usage tracking (background task).
    
    Args:
        user_context: User context with guest information
    """
    # TODO: Implement actual guest usage tracking
    # This could involve updating a cache or database
    logger.info("Guest usage updated (placeholder implementation)")