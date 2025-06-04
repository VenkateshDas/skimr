"""Main FastAPI application factory."""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from .config import get_api_config
from .middleware import setup_middleware
from .api.models.base import HealthResponse
from .exceptions import APIError


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    
    Args:
        app: FastAPI application instance
    """
    # Startup
    logger.info("Starting YouTube Analysis API...")
    config = get_api_config()
    logger.info(f"Environment: {config.environment}")
    logger.info(f"Debug mode: {config.debug}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down YouTube Analysis API...")


def create_app() -> FastAPI:
    """
    Create and configure FastAPI application.
    
    Returns:
        Configured FastAPI application instance
    """
    config = get_api_config()
    
    # Create FastAPI app
    app = FastAPI(
        title="YouTube Analysis API",
        description="RESTful API for YouTube video analysis and content generation",
        version="1.0.0",
        debug=config.debug,
        lifespan=lifespan,
        docs_url="/docs" if config.debug else None,
        redoc_url="/redoc" if config.debug else None
    )
    
    # Setup middleware
    setup_middleware(app)
    
    # Health check endpoint
    @app.get("/health", response_model=HealthResponse, tags=["Health"])
    async def health_check():
        """Health check endpoint."""
        return HealthResponse(
            status="healthy",
            message="YouTube Analysis API is running",
            version="1.0.0"
        )
    
    # Root endpoint
    @app.get("/", tags=["Root"])
    async def root():
        """Root endpoint."""
        return {
            "message": "YouTube Analysis API",
            "version": "1.0.0",
            "docs": "/docs" if config.debug else "Documentation disabled in production"
        }
    
    # Exception handlers
    @app.exception_handler(APIError)
    async def api_error_handler(request, exc: APIError):
        """Handle API errors."""
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": {
                    "code": exc.error_code,
                    "message": exc.message
                }
            }
        )
    
    # Import and include routers
    from .api.routers import auth, video_analysis, health
    
    # Include routers with prefixes
    app.include_router(
        health.router,
        prefix="/api/v1",
        tags=["Health"]
    )
    
    app.include_router(
        auth.router,
        prefix="/api/v1/auth",
        tags=["Authentication"]
    )
    
    app.include_router(
        video_analysis.router,
        prefix="/api/v1/video",
        tags=["Video Analysis"]
    )
    
    logger.info("FastAPI application created successfully")
    return app


# Create app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    
    config = get_api_config()
    uvicorn.run(
        "app:app",
        host=config.host,
        port=config.port,
        reload=config.debug,
        log_level="info"
    )