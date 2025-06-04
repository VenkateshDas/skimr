# Video Analysis Endpoints Specification

## Overview

Core video analysis endpoints that integrate with the existing [`WebAppAdapter`](../../../src/youtube_analysis/adapters/webapp_adapter.py:20) methods to provide RESTful access to video analysis functionality.

## Video Analysis Router

### Base Configuration
```python
# Pseudocode: Video analysis router setup
router = APIRouter(prefix="/api/v1/video", tags=["video"])
```

## Data Models

### Request Models
```python
# Pseudocode: Video analysis request models
CLASS VideoAnalysisRequest(BaseModel):
    PROPERTY youtube_url: str = Field(..., description="YouTube video URL")
    PROPERTY analysis_types: List[str] = Field(default=["Summary & Classification"], description="Types of analysis to perform")
    PROPERTY model_name: str = Field(default=None, description="LLM model to use")
    PROPERTY temperature: float = Field(default=None, ge=0.0, le=1.0, description="Generation temperature")
    PROPERTY use_cache: bool = Field(default=True, description="Whether to use cached results")
    PROPERTY custom_instruction: Optional[str] = Field(default="", description="Custom instruction for analysis")
    
    @validator("youtube_url")
    FUNCTION validate_youtube_url(cls, v):
        IF NOT validate_youtube_url(v):
            RAISE ValueError("Invalid YouTube URL")
        RETURN v
    
    @validator("analysis_types")
    FUNCTION validate_analysis_types(cls, v):
        valid_types = ["Summary & Classification", "Action Plan", "Blog Post", "LinkedIn Post", "X Tweet"]
        FOR analysis_type IN v:
            IF analysis_type NOT IN valid_types:
                RAISE ValueError(f"Invalid analysis type: {analysis_type}")
        RETURN v

CLASS ContentGenerationRequest(BaseModel):
    PROPERTY video_id: str = Field(..., description="Video ID")
    PROPERTY content_type: str = Field(..., description="Type of content to generate")
    PROPERTY model_name: str = Field(default=None, description="LLM model to use")
    PROPERTY temperature: float = Field(default=None, ge=0.0, le=1.0, description="Generation temperature")
    PROPERTY custom_instruction: Optional[str] = Field(default="", description="Custom instruction for generation")

CLASS TranscriptRequest(BaseModel):
    PROPERTY youtube_url: str = Field(..., description="YouTube video URL")
    PROPERTY video_id: str = Field(..., description="Video ID")
    PROPERTY use_cache: bool = Field(default=True, description="Whether to use cached transcript")
    
    @validator("youtube_url")
    FUNCTION validate_youtube_url(cls, v):
        IF NOT validate_youtube_url(v):
            RAISE ValueError("Invalid YouTube URL")
        RETURN v
```

### Response Models
```python
# Pseudocode: Video analysis response models
CLASS VideoInfo(BaseModel):
    PROPERTY video_id: str
    PROPERTY title: str
    PROPERTY description: Optional[str]
    PROPERTY duration: Optional[int]
    PROPERTY view_count: Optional[int]
    PROPERTY channel_name: Optional[str]
    PROPERTY thumbnail_url: Optional[str]

CLASS TaskOutput(BaseModel):
    PROPERTY task_name: str
    PROPERTY content: str
    PROPERTY token_usage: Optional[Dict[str, int]]
    PROPERTY execution_time: Optional[float]
    PROPERTY status: str

CLASS AnalysisResponse(BaseModel):
    PROPERTY video_id: str
    PROPERTY youtube_url: str
    PROPERTY video_info: Optional[VideoInfo]
    PROPERTY task_outputs: Dict[str, TaskOutput]
    PROPERTY total_token_usage: Optional[Dict[str, int]]
    PROPERTY analysis_time: Optional[float]
    PROPERTY cached: bool
    PROPERTY chat_details: Optional[Dict[str, Any]]

CLASS ContentGenerationResponse(BaseModel):
    PROPERTY content: str
    PROPERTY token_usage: Optional[Dict[str, int]]
    PROPERTY content_type: str

CLASS TranscriptSegment(BaseModel):
    PROPERTY text: str
    PROPERTY start: float
    PROPERTY duration: Optional[float]

CLASS TranscriptResponse(BaseModel):
    PROPERTY video_id: str
    PROPERTY timestamped_transcript: str
    PROPERTY segments: List[TranscriptSegment]
```

## Video Analysis Endpoints

### POST /api/v1/video/analyze
```python
# Pseudocode: Main video analysis endpoint
@router.post("/analyze", response_model=SuccessResponse[AnalysisResponse])
ASYNC FUNCTION analyze_video(
    request: VideoAnalysisRequest,
    current_user: Optional[UserProfile] = Depends(get_optional_user),
    webapp_adapter: WebAppAdapter = Depends(get_webapp_adapter)
) -> SuccessResponse[AnalysisResponse]:
    """
    Perform comprehensive video analysis.
    
    Integrates with existing WebAppAdapter.analyze_video method.
    """
    TRY:
        # Check guest usage limits if not authenticated
        IF current_user IS None:
            guest_count = get_guest_analysis_count()
            max_guest = int(ENV.get("MAX_GUEST_ANALYSES", 1))
            IF guest_count >= max_guest:
                RAISE AuthenticationError("Guest analysis limit reached. Please log in to continue.")
            increment_guest_analysis_count()
        
        # Validate YouTube URL
        IF NOT webapp_adapter.validate_youtube_url(request.youtube_url):
            RAISE ValidationError("Invalid YouTube URL")
        
        # Prepare settings for WebAppAdapter
        settings = {
            "model": request.model_name OR ENV.get("LLM_DEFAULT_MODEL", "gpt-4o-mini"),
            "temperature": request.temperature OR float(ENV.get("LLM_DEFAULT_TEMPERATURE", 0.2)),
            "use_cache": request.use_cache,
            "analysis_types": request.analysis_types,
            "custom_instruction": request.custom_instruction
        }
        
        logger.info(f"Starting video analysis for {request.youtube_url}")
        
        # Call existing WebAppAdapter method
        results, error = AWAIT webapp_adapter.analyze_video(
            youtube_url=request.youtube_url,
            settings=settings
        )
        
        IF error:
            logger.error(f"Analysis failed: {error}")
            RAISE ValidationError(f"Analysis failed: {error}")
        
        IF NOT results:
            RAISE ValidationError("Analysis produced no results")
        
        # Transform results to API response format
        analysis_response = transform_analysis_results(results)
        
        logger.info(f"Analysis completed for video {analysis_response.video_id}")
        
        RETURN SuccessResponse(data=analysis_response)
        
    EXCEPT ValidationError:
        RAISE
    EXCEPT AuthenticationError:
        RAISE
    EXCEPT Exception as e:
        logger.error(f"Unexpected error in video analysis: {str(e)}", exc_info=True)
        RAISE ValidationError("Analysis failed due to internal error")
```

### POST /api/v1/video/content/generate
```python
# Pseudocode: Additional content generation endpoint
@router.post("/content/generate", response_model=SuccessResponse[ContentGenerationResponse])
ASYNC FUNCTION generate_additional_content(
    request: ContentGenerationRequest,
    current_user: Optional[UserProfile] = Depends(get_optional_user),
    webapp_adapter: WebAppAdapter = Depends(get_webapp_adapter)
) -> SuccessResponse[ContentGenerationResponse]:
    """
    Generate additional content for an analyzed video.
    
    Integrates with WebAppAdapter.generate_additional_content method.
    """
    TRY:
        # Get cached analysis result to extract transcript
        cache_repo = get_cache_repository()
        analysis_result = AWAIT cache_repo.get_analysis_result(request.video_id)
        
        IF NOT analysis_result:
            RAISE NotFoundError("Video analysis not found. Please analyze the video first.")
        
        # Extract transcript from cached result
        transcript_text = ""
        IF hasattr(analysis_result, 'video_data') AND analysis_result.video_data:
            transcript_text = analysis_result.video_data.get('transcript', '')
        
        IF NOT transcript_text:
            RAISE ValidationError("No transcript available for content generation")
        
        # Prepare settings
        settings = {
            "model": request.model_name OR ENV.get("LLM_DEFAULT_MODEL", "gpt-4o-mini"),
            "temperature": request.temperature OR float(ENV.get("LLM_DEFAULT_TEMPERATURE", 0.2)),
            "custom_instruction": request.custom_instruction
        }
        
        # Get YouTube URL from analysis result
        youtube_url = analysis_result.youtube_url
        
        logger.info(f"Generating {request.content_type} for video {request.video_id}")
        
        # Call existing WebAppAdapter method
        content, error, token_usage = AWAIT webapp_adapter.generate_additional_content(
            youtube_url=youtube_url,
            video_id=request.video_id,
            transcript_text=transcript_text,
            content_type=request.content_type,
            settings=settings
        )
        
        IF error:
            logger.error(f"Content generation failed: {error}")
            RAISE ValidationError(f"Content generation failed: {error}")
        
        IF NOT content:
            RAISE ValidationError("Content generation produced no results")
        
        response = ContentGenerationResponse(
            content=content,
            token_usage=token_usage,
            content_type=request.content_type
        )
        
        logger.info(f"Content generation completed for video {request.video_id}")
        
        RETURN SuccessResponse(data=response)
        
    EXCEPT NotFoundError:
        RAISE
    EXCEPT ValidationError:
        RAISE
    EXCEPT Exception as e:
        logger.error(f"Unexpected error in content generation: {str(e)}", exc_info=True)
        RAISE ValidationError("Content generation failed due to internal error")
```

### GET /api/v1/video/transcript
```python
# Pseudocode: Transcript retrieval endpoint
@router.get("/transcript", response_model=SuccessResponse[TranscriptResponse])
ASYNC FUNCTION get_transcript(
    youtube_url: str = Query(..., description="YouTube video URL"),
    video_id: str = Query(..., description="Video ID"),
    use_cache: bool = Query(True, description="Whether to use cached transcript"),
    current_user: Optional[UserProfile] = Depends(get_optional_user),
    webapp_adapter: WebAppAdapter = Depends(get_webapp_adapter)
) -> SuccessResponse[TranscriptResponse]:
    """
    Get transcript details for a video.
    
    Integrates with WebAppAdapter.get_transcript_details method.
    """
    TRY:
        # Validate YouTube URL
        IF NOT webapp_adapter.validate_youtube_url(youtube_url):
            RAISE ValidationError("Invalid YouTube URL")
        
        logger.info(f"Getting transcript for video {video_id}")
        
        # Call existing WebAppAdapter method
        timestamped_transcript, segments, error = webapp_adapter.get_transcript_details(
            youtube_url=youtube_url,
            video_id=video_id,
            use_cache=use_cache
        )
        
        IF error:
            logger.error(f"Transcript retrieval failed: {error}")
            RAISE ValidationError(f"Transcript retrieval failed: {error}")
        
        IF NOT timestamped_transcript OR NOT segments:
            RAISE NotFoundError("Transcript not available for this video")
        
        # Transform segments to API response format
        transcript_segments = [
            TranscriptSegment(
                text=seg["text"],
                start=seg["start"],
                duration=seg.get("duration")
            )
            FOR seg IN segments
        ]
        
        response = TranscriptResponse(
            video_id=video_id,
            timestamped_transcript=timestamped_transcript,
            segments=transcript_segments
        )
        
        logger.info(f"Transcript retrieved for video {video_id}")
        
        RETURN SuccessResponse(data=response)
        
    EXCEPT ValidationError:
        RAISE
    EXCEPT NotFoundError:
        RAISE
    EXCEPT Exception as e:
        logger.error(f"Unexpected error in transcript retrieval: {str(e)}", exc_info=True)
        RAISE ValidationError("Transcript retrieval failed due to internal error")
```

### GET /api/v1/video/{video_id}/info
```python
# Pseudocode: Video info endpoint
@router.get("/{video_id}/info", response_model=SuccessResponse[VideoInfo])
ASYNC FUNCTION get_video_info(
    video_id: str = Path(..., description="Video ID"),
    webapp_adapter: WebAppAdapter = Depends(get_webapp_adapter)
) -> SuccessResponse[VideoInfo]:
    """
    Get video information and metadata.
    """
    TRY:
        youtube_url = f"https://youtu.be/{video_id}"
        
        # Call existing WebAppAdapter method
        video_info = webapp_adapter.get_video_info(youtube_url)
        
        IF NOT video_info:
            RAISE NotFoundError("Video information not available")
        
        response = VideoInfo(
            video_id=video_id,
            title=video_info.get("title", ""),
            description=video_info.get("description"),
            duration=video_info.get("duration"),
            view_count=video_info.get("view_count"),
            channel_name=video_info.get("channel_name"),
            thumbnail_url=video_info.get("thumbnail_url")
        )
        
        RETURN SuccessResponse(data=response)
        
    EXCEPT NotFoundError:
        RAISE
    EXCEPT Exception as e:
        logger.error(f"Error getting video info for {video_id}: {str(e)}")
        RAISE ValidationError("Failed to retrieve video information")
```

## Utility Functions

### Result Transformation
```python
# Pseudocode: Transform WebAppAdapter results to API format
FUNCTION transform_analysis_results(results: Dict[str, Any]) -> AnalysisResponse:
    """Transform WebAppAdapter results to API response format."""
    
    # Extract video info
    video_info = None
    IF "video_info" IN results:
        info = results["video_info"]
        video_info = VideoInfo(
            video_id=results.get("video_id", ""),
            title=info.get("title", ""),
            description=info.get("description"),
            duration=info.get("duration"),
            view_count=info.get("view_count"),
            channel_name=info.get("channel_name"),
            thumbnail_url=info.get("thumbnail_url")
        )
    
    # Transform task outputs
    task_outputs = {}
    IF "task_outputs" IN results:
        FOR task_name, output IN results["task_outputs"].items():
            task_outputs[task_name] = TaskOutput(
                task_name=task_name,
                content=output.get("content", ""),
                token_usage=output.get("token_usage"),
                execution_time=output.get("execution_time"),
                status=output.get("status", "completed")
            )
    
    RETURN AnalysisResponse(
        video_id=results.get("video_id", ""),
        youtube_url=results.get("youtube_url", ""),
        video_info=video_info,
        task_outputs=task_outputs,
        total_token_usage=results.get("total_token_usage"),
        analysis_time=results.get("analysis_time"),
        cached=results.get("cached", False),
        chat_details=results.get("chat_details")
    )
```

### Guest Usage Tracking
```python
# Pseudocode: Guest usage tracking (in-memory for simplicity)
guest_analysis_counts = {}

FUNCTION get_guest_analysis_count() -> int:
    # In production, this would use Redis or database
    client_ip = get_client_ip()
    RETURN guest_analysis_counts.get(client_ip, 0)

FUNCTION increment_guest_analysis_count():
    client_ip = get_client_ip()
    guest_analysis_counts[client_ip] = guest_analysis_counts.get(client_ip, 0) + 1

FUNCTION get_client_ip() -> str:
    # Extract client IP from request headers
    RETURN request.client.host
```

## TDD Test Anchors

### Video Analysis Tests
```python
# Test anchor: Successful video analysis
TEST test_video_analysis_success():
    WITH TestClient(app) AS client:
        response = client.post("/api/v1/video/analyze", json={
            "youtube_url": "https://youtu.be/test_video_id",
            "analysis_types": ["Summary & Classification"]
        })
        ASSERT response.status_code == 200
        ASSERT "video_id" IN response.json()["data"]
        ASSERT "task_outputs" IN response.json()["data"]

# Test anchor: Invalid YouTube URL
TEST test_invalid_youtube_url():
    WITH TestClient(app) AS client:
        response = client.post("/api/v1/video/analyze", json={
            "youtube_url": "https://invalid-url.com",
            "analysis_types": ["Summary & Classification"]
        })
        ASSERT response.status_code == 422

# Test anchor: Guest usage limit
TEST test_guest_usage_limit():
    WITH TestClient(app) AS client:
        # First request should succeed
        response = client.post("/api/v1/video/analyze", json={
            "youtube_url": "https://youtu.be/test_video_id",
            "analysis_types": ["Summary & Classification"]
        })
        ASSERT response.status_code == 200
        
        # Second request should fail for guest
        response = client.post("/api/v1/video/analyze", json={
            "youtube_url": "https://youtu.be/test_video_id2",
            "analysis_types": ["Summary & Classification"]
        })
        ASSERT response.status_code == 401

# Test anchor: Content generation
TEST test_content_generation():
    WITH TestClient(app) AS client:
        # First analyze a video
        analyze_response = client.post("/api/v1/video/analyze", json={
            "youtube_url": "https://youtu.be/test_video_id",
            "analysis_types": ["Summary & Classification"]
        })
        video_id = analyze_response.json()["data"]["video_id"]
        
        # Then generate additional content
        response = client.post("/api/v1/video/content/generate", json={
            "video_id": video_id,
            "content_type": "Blog Post"
        })
        ASSERT response.status_code == 200
        ASSERT "content" IN response.json()["data"]

# Test anchor: Transcript retrieval
TEST test_transcript_retrieval():
    WITH TestClient(app) AS client:
        response = client.get("/api/v1/video/transcript", params={
            "youtube_url": "https://youtu.be/test_video_id",
            "video_id": "test_video_id"
        })
        ASSERT response.status_code == 200
        ASSERT "timestamped_transcript" IN response.json()["data"]
        ASSERT "segments" IN response.json()["data"]
```

### Validation Tests
```python
# Test anchor: Analysis type validation
TEST test_invalid_analysis_type():
    WITH TestClient(app) AS client:
        response = client.post("/api/v1/video/analyze", json={
            "youtube_url": "https://youtu.be/test_video_id",
            "analysis_types": ["Invalid Type"]
        })
        ASSERT response.status_code == 422

# Test anchor: Temperature validation
TEST test_temperature_validation():
    WITH TestClient(app) AS client:
        response = client.post("/api/v1/video/analyze", json={
            "youtube_url": "https://youtu.be/test_video_id",
            "temperature": 2.0  # Invalid: > 1.0
        })
        ASSERT response.status_code == 422
```

This specification provides comprehensive video analysis endpoints that integrate seamlessly with the existing WebAppAdapter while providing a clean REST API interface for the Node.js frontend.