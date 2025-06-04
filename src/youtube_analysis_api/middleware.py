"""Middleware for the FastAPI application."""

import time
import uuid
import logging
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import RequestResponseEndpoint

from .config import get_api_config
from .exceptions import APIError


logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging HTTP requests and responses."""
    
    async def dispatch(
        self, 
        request: Request, 
        call_next: RequestResponseEndpoint
    ) -> Response:
        """
        Process request and log details.
        
        Args:
            request: FastAPI request object
            call_next: Next middleware/endpoint
            
        Returns:
            Response object
        """
        # Generate request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        # Log request start
        start_time = time.time()
        client_ip = request.client.host if request.client else "unknown"
        
        logger.info(
            f"Request started - ID: {request_id}, "
            f"Method: {request.method}, "
            f"URL: {request.url}, "
            f"Client IP: {client_ip}"
        )
        
        try:
            # Process request
            response = await call_next(request)
            
            # Log successful response
            process_time = time.time() - start_time
            logger.info(
                f"Request completed - ID: {request_id}, "
                f"Status: {response.status_code}, "
                f"Duration: {process_time:.3f}s"
            )
            
            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id
            
            return response
            
        except Exception as e:
            # Log error
            process_time = time.time() - start_time
            logger.error(
                f"Request failed - ID: {request_id}, "
                f"Error: {str(e)}, "
                f"Duration: {process_time:.3f}s"
            )
            raise


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Middleware for handling and formatting errors."""
    
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint
    ) -> Response:
        """
        Process request and handle errors.
        
        Args:
            request: FastAPI request object
            call_next: Next middleware/endpoint
            
        Returns:
            Response object
        """
        try:
            return await call_next(request)
            
        except APIError as e:
            # Handle known API errors
            logger.warning(f"API Error: {e.message} (Code: {e.error_code})")
            return Response(
                content=e.to_json(),
                status_code=e.status_code,
                headers={"Content-Type": "application/json"}
            )
            
        except Exception as e:
            # Handle unexpected errors
            request_id = getattr(request.state, "request_id", "unknown")
            logger.error(f"Unexpected error in request {request_id}: {str(e)}")
            
            error_response = {
                "success": False,
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected error occurred"
                },
                "request_id": request_id
            }
            
            return Response(
                content=str(error_response).replace("'", '"'),
                status_code=500,
                headers={"Content-Type": "application/json"}
            )


def setup_cors_middleware(app) -> None:
    """
    Setup CORS middleware for the application.
    
    Args:
        app: FastAPI application instance
    """
    config = get_api_config()
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"]
    )


def setup_middleware(app) -> None:
    """
    Setup all middleware for the application.
    
    Args:
        app: FastAPI application instance
    """
    # Add middleware in reverse order (last added = first executed)
    
    # Error handling (outermost)
    app.add_middleware(ErrorHandlingMiddleware)
    
    # Request logging
    app.add_middleware(RequestLoggingMiddleware)
    
    # CORS (innermost, closest to routes)
    setup_cors_middleware(app)
    
    logger.info("Middleware setup completed")


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware for rate limiting (placeholder for future implementation)."""
    
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint
    ) -> Response:
        """
        Process request with rate limiting.
        
        Args:
            request: FastAPI request object
            call_next: Next middleware/endpoint
            
        Returns:
            Response object
        """
        # TODO: Implement rate limiting logic
        # For now, just pass through
        return await call_next(request)