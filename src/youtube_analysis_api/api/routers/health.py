"""Health check router."""

from fastapi import APIRouter
from ...api.models.base import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.
    
    Returns:
        Health status response
    """
    return HealthResponse(
        status="healthy",
        message="YouTube Analysis API is running",
        version="1.0.0"
    )


@router.get("/health/detailed")
async def detailed_health_check():
    """
    Detailed health check endpoint.
    
    Returns:
        Detailed health status
    """
    # TODO: Add checks for database, external services, etc.
    return {
        "status": "healthy",
        "version": "1.0.0",
        "services": {
            "api": "healthy",
            "database": "not_implemented",
            "supabase": "not_checked",
            "llm_services": "not_checked"
        },
        "timestamp": "2024-01-01T00:00:00Z"  # TODO: Use actual timestamp
    }