# Subtitle Translation Endpoints Specification

## Overview

Subtitle translation endpoints that provide multilingual subtitle generation and translation capabilities for analyzed videos, integrating with the existing video analysis pipeline while supporting multiple output formats.

## Translation Router

### Base Configuration
```python
# Pseudocode: Translation router setup
router = APIRouter(prefix="/api/v1/video/subtitles", tags=["subtitles"])
```

## Data Models

### Request Models
```python
# Pseudocode: Subtitle translation request models
CLASS SubtitleGenerationRequest(BaseModel):
    PROPERTY video_id: str = Field(..., description="Video ID")
    PROPERTY target_language: str = Field(..., description="Target language code (ISO 639-1)")
    PROPERTY format: str = Field(default="srt", description="Subtitle format")
    PROPERTY model_name: Optional[str] = Field(default=None, description="Translation model to use")
    PROPERTY include_timestamps: bool = Field(default=True, description="Include timestamp information")
    PROPERTY max_chars_per_line: int = Field(default=80, ge=20, le=120, description="Maximum characters per subtitle line")
    PROPERTY max_lines_per_subtitle: int = Field(default=2, ge=1, le=3, description="Maximum lines per subtitle")
    
    @validator("target_language")
    FUNCTION validate_target_language(cls, v):
        supported_languages = get_supported_languages()
        IF v NOT IN supported_languages:
            RAISE ValueError(f"Unsupported language: {v}. Supported: {supported_languages}")
        RETURN v
    
    @validator("format")
    FUNCTION validate_format(cls, v):
        supported_formats = ["srt", "vtt", "ass", "json"]
        IF v NOT IN supported_formats:
            RAISE ValueError(f"Unsupported format: {v}. Supported: {supported_formats}")
        RETURN v

CLASS BatchTranslationRequest(BaseModel):
    PROPERTY video_id: str = Field(..., description="Video ID")
    PROPERTY target_languages: List[str] = Field(..., min_items=1, max_items=10, description="Target language codes")
    PROPERTY format: str = Field(default="srt", description="Subtitle format")
    PROPERTY model_name: Optional[str] = Field(default=None, description="Translation model to use")
    
    @validator("target_languages")
    FUNCTION validate_target_languages(cls, v):
        supported_languages = get_supported_languages()
        FOR lang IN v:
            IF lang NOT IN supported_languages:
                RAISE ValueError(f"Unsupported language: {lang}")
        RETURN v

CLASS TranslationStatusRequest(BaseModel):
    PROPERTY job_id: str = Field(..., description="Translation job ID")
```

### Response Models
```python
# Pseudocode: Subtitle translation response models
CLASS SubtitleSegment(BaseModel):
    PROPERTY index: int
    PROPERTY start_time: str
    PROPERTY end_time: str
    PROPERTY original_text: str
    PROPERTY translated_text: str
    PROPERTY confidence_score: Optional[float]

CLASS SubtitleFile(BaseModel):
    PROPERTY language: str
    PROPERTY format: str
    PROPERTY content: str
    PROPERTY download_url: Optional[str]
    PROPERTY file_size: int
    PROPERTY segment_count: int

CLASS TranslationJob(BaseModel):
    PROPERTY job_id: str
    PROPERTY video_id: str
    PROPERTY target_languages: List[str]
    PROPERTY status: str  # "pending", "processing", "completed", "failed"
    PROPERTY progress: float
    PROPERTY created_at: datetime
    PROPERTY completed_at: Optional[datetime]
    PROPERTY error_message: Optional[str]

CLASS SubtitleResponse(BaseModel):
    PROPERTY video_id: str
    PROPERTY language: str
    PROPERTY format: str
    PROPERTY segments: List[SubtitleSegment]
    PROPERTY subtitle_file: SubtitleFile
    PROPERTY translation_metadata: Dict[str, Any]

CLASS BatchTranslationResponse(BaseModel):
    PROPERTY job_id: str
    PROPERTY video_id: str
    PROPERTY target_languages: List[str]
    PROPERTY status: str
    PROPERTY completed_languages: List[str]
    PROPERTY failed_languages: List[str]
    PROPERTY results: List[SubtitleResponse]
```

## Subtitle Generation Endpoints

### POST /api/v1/video/subtitles/generate
```python
# Pseudocode: Generate subtitles for a video
@router.post("/generate", response_model=SuccessResponse[SubtitleResponse])
ASYNC FUNCTION generate_subtitles(
    request: SubtitleGenerationRequest,
    current_user: Optional[UserProfile] = Depends(get_optional_user)
) -> SuccessResponse[SubtitleResponse]:
    """
    Generate translated subtitles for a video.
    
    Requires video to be analyzed first to have transcript available.
    """
    TRY:
        # Check if feature is enabled
        IF NOT ENV.get("ENABLE_SUBTITLE_TRANSLATION", "false").lower() == "true":
            RAISE ValidationError("Subtitle translation feature is not enabled")
        
        # Check guest usage limits
        IF current_user IS None:
            guest_count = get_guest_translation_count()
            max_guest = int(ENV.get("MAX_GUEST_TRANSLATIONS", 1))
            IF guest_count >= max_guest:
                RAISE AuthenticationError("Guest translation limit reached. Please log in to continue.")
            increment_guest_translation_count()
        
        # Verify video exists and has transcript
        cache_repo = get_cache_repository()
        analysis_result = AWAIT cache_repo.get_analysis_result(request.video_id)
        
        IF NOT analysis_result:
            RAISE NotFoundError("Video analysis not found. Please analyze the video first.")
        
        # Extract transcript segments
        transcript_segments = extract_transcript_segments(analysis_result)
        IF NOT transcript_segments:
            RAISE ValidationError("No transcript available for subtitle generation")
        
        # Check if translation already exists in cache
        cache_key = f"subtitles:{request.video_id}:{request.target_language}:{request.format}"
        cached_subtitles = AWAIT cache_repo.get_cached_subtitles(cache_key)
        
        IF cached_subtitles AND request.target_language != "en":
            logger.info(f"Returning cached subtitles for {request.video_id} in {request.target_language}")
            RETURN SuccessResponse(data=cached_subtitles)
        
        # Initialize translation service
        translation_service = get_translation_service()
        
        # Prepare translation settings
        settings = {
            "model": request.model_name OR ENV.get("TRANSLATION_DEFAULT_MODEL", "gpt-4o-mini"),
            "target_language": request.target_language,
            "max_chars_per_line": request.max_chars_per_line,
            "max_lines_per_subtitle": request.max_lines_per_subtitle,
            "preserve_timing": request.include_timestamps
        }
        
        logger.info(f"Starting subtitle generation for video {request.video_id} to {request.target_language}")
        
        # Generate translated subtitles
        translated_segments = []
        FOR segment IN transcript_segments:
            IF request.target_language == "en":
                # No translation needed for English
                translated_text = segment["text"]
                confidence = 1.0
            ELSE:
                # Translate the segment
                translation_result = AWAIT translation_service.translate_text(
                    text=segment["text"],
                    target_language=request.target_language,
                    settings=settings
                )
                translated_text = translation_result["translated_text"]
                confidence = translation_result.get("confidence_score", 0.9)
            
            # Format subtitle segment
            subtitle_segment = SubtitleSegment(
                index=segment["index"],
                start_time=format_timestamp(segment["start"]),
                end_time=format_timestamp(segment["start"] + segment["duration"]),
                original_text=segment["text"],
                translated_text=translated_text,
                confidence_score=confidence
            )
            translated_segments.append(subtitle_segment)
        
        # Generate subtitle file content
        subtitle_content = generate_subtitle_file(
            segments=translated_segments,
            format=request.format,
            language=request.target_language
        )
        
        # Create subtitle file object
        subtitle_file = SubtitleFile(
            language=request.target_language,
            format=request.format,
            content=subtitle_content,
            download_url=None,  # Will be set by file service
            file_size=len(subtitle_content.encode('utf-8')),
            segment_count=len(translated_segments)
        )
        
        # Store subtitle file and get download URL
        file_service = get_file_service()
        download_url = AWAIT file_service.store_subtitle_file(
            video_id=request.video_id,
            language=request.target_language,
            format=request.format,
            content=subtitle_content,
            user_id=current_user.id IF current_user ELSE None
        )
        subtitle_file.download_url = download_url
        
        # Create response
        response = SubtitleResponse(
            video_id=request.video_id,
            language=request.target_language,
            format=request.format,
            segments=translated_segments,
            subtitle_file=subtitle_file,
            translation_metadata={
                "model_used": settings["model"],
                "translation_time": time.time(),
                "segment_count": len(translated_segments),
                "average_confidence": sum(s.confidence_score or 0 for s in translated_segments) / len(translated_segments)
            }
        )
        
        # Cache the result
        IF request.target_language != "en":
            AWAIT cache_repo.cache_subtitles(cache_key, response, ttl_hours=24)
        
        logger.info(f"Subtitle generation completed for video {request.video_id}")
        
        RETURN SuccessResponse(data=response)
        
    EXCEPT ValidationError:
        RAISE
    EXCEPT AuthenticationError:
        RAISE
    EXCEPT NotFoundError:
        RAISE
    EXCEPT Exception as e:
        logger.error(f"Error generating subtitles: {str(e)}", exc_info=True)
        RAISE ValidationError("Subtitle generation failed due to internal error")
```

### POST /api/v1/video/subtitles/batch
```python
# Pseudocode: Batch subtitle generation
@router.post("/batch", response_model=SuccessResponse[TranslationJob])
ASYNC FUNCTION generate_batch_subtitles(
    request: BatchTranslationRequest,
    current_user: UserProfile = Depends(get_current_user)
) -> SuccessResponse[TranslationJob]:
    """
    Generate subtitles for multiple languages in batch.
    
    Requires authentication for batch operations.
    """
    TRY:
        # Check if feature is enabled
        IF NOT ENV.get("ENABLE_SUBTITLE_TRANSLATION", "false").lower() == "true":
            RAISE ValidationError("Subtitle translation feature is not enabled")
        
        # Verify video exists
        cache_repo = get_cache_repository()
        analysis_result = AWAIT cache_repo.get_analysis_result(request.video_id)
        
        IF NOT analysis_result:
            RAISE NotFoundError("Video analysis not found. Please analyze the video first.")
        
        # Create translation job
        job_service = get_job_service()
        job_id = AWAIT job_service.create_translation_job(
            video_id=request.video_id,
            target_languages=request.target_languages,
            format=request.format,
            model_name=request.model_name,
            user_id=current_user.id
        )
        
        # Start background translation task
        translation_task = get_translation_task()
        AWAIT translation_task.start_batch_translation.delay(
            job_id=job_id,
            video_id=request.video_id,
            target_languages=request.target_languages,
            settings={
                "format": request.format,
                "model": request.model_name OR ENV.get("TRANSLATION_DEFAULT_MODEL", "gpt-4o-mini")
            }
        )
        
        # Return job information
        job = TranslationJob(
            job_id=job_id,
            video_id=request.video_id,
            target_languages=request.target_languages,
            status="pending",
            progress=0.0,
            created_at=datetime.utcnow(),
            completed_at=None,
            error_message=None
        )
        
        logger.info(f"Batch translation job created: {job_id} for video {request.video_id}")
        
        RETURN SuccessResponse(data=job)
        
    EXCEPT ValidationError:
        RAISE
    EXCEPT NotFoundError:
        RAISE
    EXCEPT Exception as e:
        logger.error(f"Error creating batch translation job: {str(e)}", exc_info=True)
        RAISE ValidationError("Failed to create batch translation job")
```

### GET /api/v1/video/subtitles/job/{job_id}/status
```python
# Pseudocode: Get translation job status
@router.get("/job/{job_id}/status", response_model=SuccessResponse[TranslationJob])
ASYNC FUNCTION get_translation_job_status(
    job_id: str = Path(..., description="Translation job ID"),
    current_user: UserProfile = Depends(get_current_user)
) -> SuccessResponse[TranslationJob]:
    """
    Get the status of a translation job.
    """
    TRY:
        job_service = get_job_service()
        job = AWAIT job_service.get_translation_job(job_id)
        
        IF NOT job:
            RAISE NotFoundError("Translation job not found")
        
        # Verify job ownership
        IF job.user_id != current_user.id:
            RAISE ForbiddenError("Access denied to this translation job")
        
        RETURN SuccessResponse(data=job)
        
    EXCEPT NotFoundError:
        RAISE
    EXCEPT ForbiddenError:
        RAISE
    EXCEPT Exception as e:
        logger.error(f"Error getting translation job status: {str(e)}", exc_info=True)
        RAISE ValidationError("Failed to retrieve job status")
```

### GET /api/v1/video/subtitles/{video_id}
```python
# Pseudocode: List available subtitles for a video
@router.get("/{video_id}", response_model=SuccessResponse[List[Dict[str, Any]]])
ASYNC FUNCTION list_video_subtitles(
    video_id: str = Path(..., description="Video ID"),
    current_user: Optional[UserProfile] = Depends(get_optional_user)
) -> SuccessResponse[List[Dict[str, Any]]]:
    """
    List all available subtitle languages and formats for a video.
    """
    TRY:
        file_service = get_file_service()
        available_subtitles = AWAIT file_service.list_video_subtitles(
            video_id=video_id,
            user_id=current_user.id IF current_user ELSE None
        )
        
        subtitle_list = [
            {
                "language": subtitle["language"],
                "language_name": get_language_name(subtitle["language"]),
                "format": subtitle["format"],
                "download_url": subtitle["download_url"],
                "file_size": subtitle["file_size"],
                "created_at": subtitle["created_at"],
                "segment_count": subtitle.get("segment_count", 0)
            }
            FOR subtitle IN available_subtitles
        ]
        
        RETURN SuccessResponse(data=subtitle_list)
        
    EXCEPT Exception as e:
        logger.error(f"Error listing video subtitles: {str(e)}", exc_info=True)
        RAISE ValidationError("Failed to retrieve subtitle list")
```

## Utility Functions

### Transcript Processing
```python
# Pseudocode: Extract transcript segments from analysis result
FUNCTION extract_transcript_segments(analysis_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract timestamped transcript segments from analysis result."""
    segments = []
    
    IF "video_data" IN analysis_result AND "transcript_segments" IN analysis_result["video_data"]:
        raw_segments = analysis_result["video_data"]["transcript_segments"]
        
        FOR i, segment IN enumerate(raw_segments):
            segments.append({
                "index": i + 1,
                "text": segment.get("text", ""),
                "start": segment.get("start", 0.0),
                "duration": segment.get("duration", 0.0)
            })
    
    RETURN segments

# Pseudocode: Format timestamp for subtitle files
FUNCTION format_timestamp(seconds: float) -> str:
    """Format seconds to SRT timestamp format (HH:MM:SS,mmm)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    milliseconds = int((seconds % 1) * 1000)
    
    RETURN f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"

# Pseudocode: Generate subtitle file content
FUNCTION generate_subtitle_file(segments: List[SubtitleSegment], format: str, language: str) -> str:
    """Generate subtitle file content in specified format."""
    
    IF format == "srt":
        RETURN generate_srt_content(segments)
    ELIF format == "vtt":
        RETURN generate_vtt_content(segments)
    ELIF format == "ass":
        RETURN generate_ass_content(segments, language)
    ELIF format == "json":
        RETURN generate_json_content(segments)
    ELSE:
        RAISE ValueError(f"Unsupported subtitle format: {format}")

FUNCTION generate_srt_content(segments: List[SubtitleSegment]) -> str:
    """Generate SRT format subtitle content."""
    content = []
    FOR segment IN segments:
        content.append(f"{segment.index}")
        content.append(f"{segment.start_time} --> {segment.end_time}")
        content.append(segment.translated_text)
        content.append("")  # Empty line between subtitles
    
    RETURN "\n".join(content)
```

### Language Support
```python
# Pseudocode: Get supported languages
FUNCTION get_supported_languages() -> List[str]:
    """Get list of supported language codes."""
    RETURN ENV.get("SUPPORTED_TRANSLATION_LANGUAGES", "en,es,fr,de,it,pt,ru,ja,ko,zh").split(",")

FUNCTION get_language_name(language_code: str) -> str:
    """Get human-readable language name from code."""
    language_names = {
        "en": "English",
        "es": "Spanish", 
        "fr": "French",
        "de": "German",
        "it": "Italian",
        "pt": "Portuguese",
        "ru": "Russian",
        "ja": "Japanese",
        "ko": "Korean",
        "zh": "Chinese"
    }
    RETURN language_names.get(language_code, language_code.upper())
```

### Guest Usage Tracking
```python
# Pseudocode: Guest translation usage tracking
guest_translation_counts = {}

FUNCTION get_guest_translation_count() -> int:
    client_ip = get_client_ip()
    RETURN guest_translation_counts.get(client_ip, 0)

FUNCTION increment_guest_translation_count():
    client_ip = get_client_ip()
    guest_translation_counts[client_ip] = guest_translation_counts.get(client_ip, 0) + 1
```

## TDD Test Anchors

### Subtitle Generation Tests
```python
# Test anchor: Successful subtitle generation
TEST test_generate_subtitles_success():
    WITH TestClient(app) AS client:
        # First analyze a video
        analyze_response = client.post("/api/v1/video/analyze", json={
            "youtube_url": "https://youtu.be/test_video_id",
            "analysis_types": ["Summary & Classification"]
        })
        video_id = analyze_response.json()["data"]["video_id"]
        
        # Generate subtitles
        response = client.post("/api/v1/video/subtitles/generate", json={
            "video_id": video_id,
            "target_language": "es",
            "format": "srt"
        })
        ASSERT response.status_code == 200
        ASSERT "segments" IN response.json()["data"]
        ASSERT "subtitle_file" IN response.json()["data"]

# Test anchor: Batch translation
TEST test_batch_translation():
    WITH TestClient(app) AS client:
        user_token = get_user_token()
        headers = {"Authorization": f"Bearer {user_token}"}
        
        response = client.post("/api/v1/video/subtitles/batch", 
            json={
                "video_id": "test_video_id",
                "target_languages": ["es", "fr", "de"],
                "format": "srt"
            },
            headers=headers
        )
        ASSERT response.status_code == 200
        ASSERT "job_id" IN response.json()["data"]

# Test anchor: Translation job status
TEST test_translation_job_status():
    WITH TestClient(app) AS client:
        user_token = get_user_token()
        headers = {"Authorization": f"Bearer {user_token}"}
        
        # Create batch job first
        batch_response = client.post("/api/v1/video/subtitles/batch", 
            json={
                "video_id": "test_video_id",
                "target_languages": ["es"],
                "format": "srt"
            },
            headers=headers
        )
        job_id = batch_response.json()["data"]["job_id"]
        
        # Check status
        response = client.get(f"/api/v1/video/subtitles/job/{job_id}/status", headers=headers)
        ASSERT response.status_code == 200
        ASSERT "status" IN response.json()["data"]

# Test anchor: List video subtitles
TEST test_list_video_subtitles():
    WITH TestClient(app) AS client:
        response = client.get("/api/v1/video/subtitles/test_video_id")
        ASSERT response.status_code == 200
        ASSERT isinstance(response.json()["data"], list)

# Test anchor: Guest translation limit
TEST test_guest_translation_limit():
    WITH TestClient(app) AS client:
        # First translation should succeed
        response = client.post("/api/v1/video/subtitles/generate", json={
            "video_id": "test_video_id",
            "target_language": "es",
            "format": "srt"
        })
        ASSERT response.status_code == 200
        
        # Second translation should fail for guest
        response = client.post("/api/v1/video/subtitles/generate", json={
            "video_id": "test_video_id2",
            "target_language": "fr",
            "format": "srt"
        })
        ASSERT response.status_code == 401
```

This specification provides comprehensive subtitle translation capabilities that integrate with the existing video analysis pipeline while supporting multiple languages and formats with proper guest usage controls.