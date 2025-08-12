from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SettingsModel(BaseModel):
    model: Optional[str] = Field(default=None)
    temperature: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    use_cache: Optional[bool] = Field(default=True)
    analysis_types: Optional[List[str]] = None
    transcription_model: Optional[str] = Field(default=None)
    subtitle_language: Optional[str] = Field(default="en")


class AnalyzeRequest(BaseModel):
    youtube_url: str
    settings: Optional[SettingsModel] = None


class AnalyzeResponse(BaseModel):
    result: Dict[str, Any]


class GenerateRequest(BaseModel):
    youtube_url: str
    video_id: str
    transcript_text: str
    content_type: str
    custom_instruction: Optional[str] = None
    settings: Optional[SettingsModel] = None


class GenerateResponse(BaseModel):
    content: str
    token_usage: Optional[Dict[str, int]] = None


class TranscriptRequest(BaseModel):
    youtube_url: str
    video_id: str
    use_cache: Optional[bool] = True


class TranscriptResponse(BaseModel):
    transcript: Optional[str]
    segments: Optional[List[Dict[str, Any]]]


class TranslateRequest(BaseModel):
    segments: List[Dict[str, Any]]
    source_language: Optional[str] = None
    target_language: str
    video_id: Optional[str] = None


class TranslateResponse(BaseModel):
    translated_text: Optional[str]
    translated_segments: Optional[List[Dict[str, Any]]]


class CacheClearRequest(BaseModel):
    video_id: str


class ErrorResponse(BaseModel):
    error: Dict[str, Any]


