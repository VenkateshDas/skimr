"""Base response models for the API."""

from datetime import datetime
from typing import Any, Optional, TypeVar, Generic
from pydantic import BaseModel, Field


T = TypeVar('T')


class BaseResponse(BaseModel):
    """Base response model."""
    
    success: bool
    timestamp: datetime = Field(default_factory=datetime.now)
    request_id: Optional[str] = None


class SuccessResponse(BaseResponse, Generic[T]):
    """Success response model."""
    
    success: bool = True
    data: T


class ErrorResponse(BaseModel):
    """Error response details."""
    
    error_code: str
    detail: str
    timestamp: datetime = Field(default_factory=datetime.now)
    request_id: Optional[str] = None


class ErrorResponseModel(BaseResponse):
    """Error response model."""
    
    success: bool = False
    error: ErrorResponse


class HealthStatus(BaseModel):
    """Health check response model."""
    
    status: str
    timestamp: datetime = Field(default_factory=datetime.now)
    version: str
    dependencies: dict[str, str] = Field(default_factory=dict)


class PaginationMeta(BaseModel):
    """Pagination metadata."""
    
    page: int = Field(ge=1)
    per_page: int = Field(ge=1, le=100)
    total: int = Field(ge=0)
    pages: int = Field(ge=0)
    has_next: bool
    has_prev: bool


class PaginatedResponse(BaseResponse, Generic[T]):
    """Paginated response model."""
    
    success: bool = True
    data: list[T]
    meta: PaginationMeta


class HealthResponse(SuccessResponse[HealthStatus]):
    """Health check response model."""
    pass