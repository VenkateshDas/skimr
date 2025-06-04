# FastAPI Backend Implementation Pseudocode

## Overview

This document provides comprehensive pseudocode for implementing the FastAPI backend that integrates with the existing Clean Architecture services while providing RESTful API access for the Node.js frontend.

## Module 1: Core Application Setup

### Application Factory
```python
# Pseudocode: FastAPI application factory
MODULE fastapi_app_factory:

    IMPORT FastAPI, CORSMiddleware, HTTPException
    IMPORT logging, os, uuid
    FROM service_factory IMPORT get_service_factory
    FROM middleware IMPORT RequestLoggingMiddleware, ErrorHandlingMiddleware
    FROM routers IMPORT auth_router, video_router, chat_router, cache_router, config_router

    FUNCTION create_app() -> FastAPI:
        """Create and configure FastAPI application."""
        
        # Initialize app with metadata
        app = FastAPI(
            title=ENV.get("API_TITLE", "YouTube Analysis API"),
            description="Backend API for YouTube video analysis and chat",
            version=ENV.get("APP_VERSION", "1.0.0"),
            debug=ENV.get("API_DEBUG", "false").lower() == "true",
            docs_url="/docs" IF ENV.get("ENVIRONMENT") != "production" ELSE None,
            redoc_url="/redoc" IF ENV.get("ENVIRONMENT") != "production" ELSE None
        )
        
        # Configure CORS
        cors_origins = ENV.get("API_CORS_ORIGINS", "http://localhost:3000").split(",")
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            allow_headers=["*"]
        )
        
        # Add custom middleware
        app.add_middleware(RequestLoggingMiddleware)
        app.add_middleware(ErrorHandlingMiddleware)
        
        # Include API routers
        app.include_router(auth_router, prefix="/api/v1/auth", tags=["authentication"])
        app.include_router(video_router, prefix="/api/v1/video", tags=["video"])
        app.include_router(chat_router, prefix="/api/v1/video/chat", tags=["chat"])
        app.include_router(cache_router, prefix="/api/v1/cache", tags=["cache"])
        app.include_router(config_router, prefix="/api/v1/config", tags=["configuration"])
        
        # Add health check endpoint
        @app.get("/health")
        ASYNC FUNCTION health_check():
            RETURN {
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "version": ENV.get("APP_VERSION", "1.0.0")
            }
        
        # Initialize service factory on startup
        @app.on_event("startup")
        ASYNC FUNCTION startup_event():
            logger.info("Initializing FastAPI application")
            service_factory = get_service_factory()
            app.state.service_factory = service_factory
        
        # Cleanup on shutdown
        @app.on_event("shutdown")
        ASYNC FUNCTION shutdown_event():
            logger.info("Shutting down FastAPI application")
            IF hasattr(app.state, "service_factory"):
                AWAIT app.state.service_factory.cleanup()
        
        RETURN app

    # TDD Test Anchors
    TEST test_app_creation():
        app = create_app()
        ASSERT app.title == "YouTube Analysis API"
        ASSERT "/api/v1/auth" IN [route.path FOR route IN app.routes]
    
    TEST test_cors_configuration():
        app = create_app()
        cors_middleware = find_middleware(app, CORSMiddleware)
        ASSERT cors_middleware IS NOT None
```

### Environment Configuration
```python
# Pseudocode: Environment configuration management
MODULE config_manager:

    IMPORT os
    FROM typing IMPORT Dict, Any, Optional
    FROM dataclasses IMPORT dataclass

    @dataclass
    CLASS APIConfig:
        """API configuration settings."""
        host: str = ENV.get("API_HOST", "0.0.0.0")
        port: int = int(ENV.get("API_PORT", 8000))
        debug: bool = ENV.get("API_DEBUG", "false").lower() == "true"
        secret_key: str = ENV.get("API_SECRET_KEY", "")
        cors_origins: List[str] = ENV.get("API_CORS_ORIGINS", "http://localhost:3000").split(",")
        access_token_expire_minutes: int = int(ENV.get("API_ACCESS_TOKEN_EXPIRE_MINUTES", 30))
        
        FUNCTION validate(self) -> List[str]:
            """Validate configuration and return list of errors."""
            errors = []
            IF NOT self.secret_key:
                errors.append("API_SECRET_KEY is required")
            IF self.access_token_expire_minutes < 1:
                errors.append("API_ACCESS_TOKEN_EXPIRE_MINUTES must be positive")
            RETURN errors

    FUNCTION get_api_config() -> APIConfig:
        """Get validated API configuration."""
        config = APIConfig()
        errors = config.validate()
        IF errors:
            RAISE ValueError(f"Configuration errors: {', '.join(errors)}")
        RETURN config

    # TDD Test Anchors
    TEST test_config_validation():
        # Test with missing secret key
        WITH patch.dict(os.environ, {"API_SECRET_KEY": ""}):
            WITH pytest.raises(ValueError):
                get_api_config()
    
    TEST test_config_defaults():
        config = APIConfig()
        ASSERT config.host == "0.0.0.0"
        ASSERT config.port == 8000
```

## Module 2: Authentication Integration

### JWT Token Management
```python
# Pseudocode: JWT token management
MODULE jwt_manager:

    IMPORT jwt, datetime
    FROM typing IMPORT Dict, Any, Optional
    FROM models IMPORT UserProfile
    FROM exceptions IMPORT AuthenticationError

    CLASS JWTManager:
        FUNCTION __init__(self, secret_key: str, algorithm: str = "HS256"):
            self.secret_key = secret_key
            self.algorithm = algorithm
            self.expire_minutes = int(ENV.get("API_ACCESS_TOKEN_EXPIRE_MINUTES", 30))
        
        FUNCTION create_access_token(self, user_data: Dict[str, Any]) -> str:
            """Create JWT access token."""
            to_encode = user_data.copy()
            expire = datetime.utcnow() + timedelta(minutes=self.expire_minutes)
            to_encode.update({
                "exp": expire,
                "iat": datetime.utcnow(),
                "type": "access"
            })
            
            encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
            RETURN encoded_jwt
        
        FUNCTION verify_token(self, token: str) -> Dict[str, Any]:
            """Verify and decode JWT token."""
            TRY:
                payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
                
                # Check token type
                IF payload.get("type") != "access":
                    RAISE AuthenticationError("Invalid token type")
                
                # Check expiration
                exp = payload.get("exp")
                IF exp AND datetime.utcfromtimestamp(exp) < datetime.utcnow():
                    RAISE AuthenticationError("Token has expired")
                
                RETURN payload
            EXCEPT jwt.ExpiredSignatureError:
                RAISE AuthenticationError("Token has expired")
            EXCEPT jwt.InvalidTokenError:
                RAISE AuthenticationError("Invalid token")

    # Global JWT manager instance
    jwt_manager = None

    FUNCTION get_jwt_manager() -> JWTManager:
        """Get global JWT manager instance."""
        GLOBAL jwt_manager
        IF jwt_manager IS None:
            secret_key = ENV.get("API_SECRET_KEY")
            IF NOT secret_key:
                RAISE ValueError("API_SECRET_KEY environment variable is required")
            jwt_manager = JWTManager(secret_key)
        RETURN jwt_manager

    # TDD Test Anchors
    TEST test_token_creation_and_verification():
        manager = JWTManager("test-secret")
        user_data = {"sub": "user123", "email": "test@example.com"}
        token = manager.create_access_token(user_data)
        
        payload = manager.verify_token(token)
        ASSERT payload["sub"] == "user123"
        ASSERT payload["email"] == "test@example.com"
    
    TEST test_expired_token():
        manager = JWTManager("test-secret")
        # Create token with past expiration
        WITH patch("datetime.datetime") AS mock_datetime:
            mock_datetime.utcnow.return_value = datetime(2023, 1, 1)
            token = manager.create_access_token({"sub": "user123"})
        
        WITH pytest.raises(AuthenticationError):
            manager.verify_token(token)
```

### Authentication Dependencies
```python
# Pseudocode: FastAPI authentication dependencies
MODULE auth_dependencies:

    IMPORT supabase
    FROM fastapi IMPORT Depends, HTTPException, status
    FROM fastapi.security IMPORT OAuth2PasswordBearer
    FROM typing IMPORT Optional
    FROM models IMPORT UserProfile
    FROM jwt_manager IMPORT get_jwt_manager

    # OAuth2 schemes
    oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
    optional_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

    ASYNC FUNCTION get_current_user(token: str = Depends(oauth2_scheme)) -> UserProfile:
        """Get current authenticated user."""
        TRY:
            # Verify JWT token
            jwt_manager = get_jwt_manager()
            payload = jwt_manager.verify_token(token)
            
            user_id = payload.get("sub")
            email = payload.get("email")
            
            IF NOT user_id OR NOT email:
                RAISE HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token payload"
                )
            
            # Verify user exists in Supabase
            supabase_client = get_supabase_client()
            user_response = supabase_client.auth.get_user(token)
            
            IF NOT user_response.user:
                RAISE HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found"
                )
            
            RETURN UserProfile(
                id=user_response.user.id,
                email=user_response.user.email,
                created_at=datetime.fromisoformat(user_response.user.created_at),
                email_confirmed=user_response.user.email_confirmed_at IS NOT None
            )
            
        EXCEPT AuthenticationError as e:
            RAISE HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e)
            )
        EXCEPT Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            RAISE HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication failed"
            )

    ASYNC FUNCTION get_optional_user(token: Optional[str] = Depends(optional_oauth2_scheme)) -> Optional[UserProfile]:
        """Get current user if authenticated, None otherwise."""
        IF token IS None:
            RETURN None
        
        TRY:
            RETURN AWAIT get_current_user(token)
        EXCEPT HTTPException:
            RETURN None

    FUNCTION get_supabase_client():
        """Get Supabase client instance."""
        url = ENV.get("SUPABASE_URL")
        key = ENV.get("SUPABASE_ANON_KEY")
        
        IF NOT url OR NOT key:
            RAISE ValueError("Supabase credentials not configured")
        
        RETURN supabase.create_client(url, key)

    # TDD Test Anchors
    TEST test_get_current_user_valid_token():
        WITH patch("auth_dependencies.get_jwt_manager") AS mock_jwt:
            WITH patch("auth_dependencies.get_supabase_client") AS mock_supabase:
                mock_jwt.return_value.verify_token.return_value = {
                    "sub": "user123",
                    "email": "test@example.com"
                }
                mock_supabase.return_value.auth.get_user.return_value.user.id = "user123"
                
                user = AWAIT get_current_user("valid_token")
                ASSERT user.id == "user123"
    
    TEST test_get_optional_user_no_token():
        user = AWAIT get_optional_user(None)
        ASSERT user IS None
```

## Module 3: Video Analysis Integration

### WebApp Adapter Integration
```python
# Pseudocode: Video analysis endpoint integration
MODULE video_analysis_endpoints:

    FROM fastapi IMPORT APIRouter, Depends, HTTPException, Query, Path
    FROM typing IMPORT Optional, Dict, Any
    FROM models IMPORT VideoAnalysisRequest, AnalysisResponse, UserProfile
    FROM auth_dependencies IMPORT get_optional_user
    FROM service_factory IMPORT get_service_factory
    FROM webapp_adapter IMPORT WebAppAdapter

    router = APIRouter()

    FUNCTION get_webapp_adapter() -> WebAppAdapter:
        """Dependency to get WebAppAdapter instance."""
        service_factory = get_service_factory()
        RETURN WebAppAdapter()

    @router.post("/analyze")
    ASYNC FUNCTION analyze_video(
        request: VideoAnalysisRequest,
        current_user: Optional[UserProfile] = Depends(get_optional_user),
        webapp_adapter: WebAppAdapter = Depends(get_webapp_adapter)
    ) -> Dict[str, Any]:
        """
        Analyze YouTube video using existing WebAppAdapter.
        
        Integrates with WebAppAdapter.analyze_video() method.
        """
        TRY:
            # Check guest usage limits
            IF current_user IS None:
                guest_count = get_guest_analysis_count()
                max_guest = int(ENV.get("MAX_GUEST_ANALYSES", 1))
                IF guest_count >= max_guest:
                    RAISE HTTPException(
                        status_code=401,
                        detail="Guest analysis limit reached. Please log in to continue."
                    )
                increment_guest_analysis_count()
            
            # Validate YouTube URL
            IF NOT webapp_adapter.validate_youtube_url(request.youtube_url):
                RAISE HTTPException(
                    status_code=422,
                    detail="Invalid YouTube URL"
                )
            
            # Prepare settings for WebAppAdapter
            settings = {
                "model": request.model_name OR ENV.get("LLM_DEFAULT_MODEL", "gpt-4o-mini"),
                "temperature": request.temperature OR float(ENV.get("LLM_DEFAULT_TEMPERATURE", 0.2)),
                "use_cache": request.use_cache,
                "analysis_types": request.analysis_types,
                "custom_instruction": request.custom_instruction OR ""
            }
            
            logger.info(f"Starting video analysis for {request.youtube_url}")
            
            # Call existing WebAppAdapter method
            results, error = AWAIT webapp_adapter.analyze_video(
                youtube_url=request.youtube_url,
                settings=settings
            )
            
            IF error:
                logger.error(f"Analysis failed: {error}")
                RAISE HTTPException(status_code=422, detail=f"Analysis failed: {error}")
            
            IF NOT results:
                RAISE HTTPException(status_code=422, detail="Analysis produced no results")
            
            # Transform results to API response format
            analysis_response = transform_analysis_results(results)
            
            logger.info(f"Analysis completed for video {analysis_response['video_id']}")
            
            RETURN {
                "success": True,
                "data": analysis_response,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        EXCEPT HTTPException:
            RAISE
        EXCEPT Exception as e:
            logger.error(f"Unexpected error in video analysis: {str(e)}", exc_info=True)
            RAISE HTTPException(status_code=500, detail="Analysis failed due to internal error")

    FUNCTION transform_analysis_results(results: Dict[str, Any]) -> Dict[str, Any]:
        """Transform WebAppAdapter results to API response format."""
        
        # Extract video info
        video_info = None
        IF "video_info" IN results:
            info = results["video_info"]
            video_info = {
                "video_id": results.get("video_id", ""),
                "title": info.get("title", ""),
                "description": info.get("description"),
                "duration": info.get("duration"),
                "view_count": info.get("view_count"),
                "channel_name": info.get("channel_name"),
                "thumbnail_url": info.get("thumbnail_url")
            }
        
        # Transform task outputs
        task_outputs = {}
        IF "task_outputs" IN results:
            FOR task_name, output IN results["task_outputs"].items():
                task_outputs[task_name] = {
                    "task_name": task_name,
                    "content": output.get("content", ""),
                    "token_usage": output.get("token_usage"),
                    "execution_time": output.get("execution_time"),
                    "status": output.get("status", "completed")
                }
        
        RETURN {
            "video_id": results.get("video_id", ""),
            "youtube_url": results.get("youtube_url", ""),
            "video_info": video_info,
            "task_outputs": task_outputs,
            "total_token_usage": results.get("total_token_usage"),
            "analysis_time": results.get("analysis_time"),
            "cached": results.get("cached", False),
            "chat_details": results.get("chat_details")
        }

    # Guest usage tracking (in-memory for simplicity)
    guest_analysis_counts = {}

    FUNCTION get_guest_analysis_count() -> int:
        client_ip = get_client_ip()
        RETURN guest_analysis_counts.get(client_ip, 0)

    FUNCTION increment_guest_analysis_count():
        client_ip = get_client_ip()
        guest_analysis_counts[client_ip] = guest_analysis_counts.get(client_ip, 0) + 1

    FUNCTION get_client_ip() -> str:
        # Extract client IP from request context
        RETURN "127.0.0.1"  # Placeholder

    # TDD Test Anchors
    TEST test_video_analysis_success():
        WITH TestClient(app) AS client:
            response = client.post("/api/v1/video/analyze", json={
                "youtube_url": "https://youtu.be/test_video_id",
                "analysis_types": ["Summary & Classification"]
            })
            ASSERT response.status_code == 200
            ASSERT "video_id" IN response.json()["data"]
    
    TEST test_invalid_youtube_url():
        WITH TestClient(app) AS client:
            response = client.post("/api/v1/video/analyze", json={
                "youtube_url": "https://invalid-url.com",
                "analysis_types": ["Summary & Classification"]
            })
            ASSERT response.status_code == 422
```

## Module 4: Real-time Chat System

### WebSocket Chat Handler
```python
# Pseudocode: WebSocket chat implementation
MODULE websocket_chat:

    FROM fastapi IMPORT WebSocket, WebSocketDisconnect, Query
    FROM typing IMPORT Optional, Dict, Any
    FROM auth_dependencies IMPORT get_optional_user
    FROM webapp_adapter IMPORT WebAppAdapter
    FROM service_factory IMPORT get_service_factory

    CLASS WebSocketManager:
        """Manage WebSocket connections and chat sessions."""
        
        FUNCTION __init__(self):
            self.active_connections: Dict[str, WebSocket] = {}
            self.session_connections: Dict[str, List[str]] = {}
        
        ASYNC FUNCTION connect(self, websocket: WebSocket, session_id: str):
            """Accept WebSocket connection and register session."""
            AWAIT websocket.accept()
            connection_id = str(uuid4())
            self.active_connections[connection_id] = websocket
            
            IF session_id NOT IN self.session_connections:
                self.session_connections[session_id] = []
            self.session_connections[session_id].append(connection_id)
            
            RETURN connection_id
        
        FUNCTION disconnect(self, connection_id: str, session_id: str):
            """Remove WebSocket connection."""
            IF connection_id IN self.active_connections:
                del self.active_connections[connection_id]
            
            IF session_id IN self.session_connections:
                IF connection_id IN self.session_connections[session_id]:
                    self.session_connections[session_id].remove(connection_id)
                
                IF NOT self.session_connections[session_id]:
                    del self.session_connections[session_id]
        
        ASYNC FUNCTION send_to_connection(self, connection_id: str, message: Dict[str, Any]):
            """Send message to specific connection."""
            IF connection_id IN self.active_connections:
                websocket = self.active_connections[connection_id]
                AWAIT websocket.send_json(message)

    # Global WebSocket manager
    websocket_manager = WebSocketManager()

    ASYNC FUNCTION websocket_chat_endpoint(
        websocket: WebSocket,
        video_id: str = Query(...),
        session_id: Optional[str] = Query(default=None),
        token: Optional[str] = Query(default=None)
    ):
        """
        WebSocket endpoint for real-time chat streaming.
        
        Integrates with WebAppAdapter.get_chat_response_stream method.
        """
        connection_id = None
        
        TRY:
            # Accept connection
            connection_id = AWAIT websocket_manager.connect(websocket, session_id or "default")
            
            # Authenticate user (optional for guest access)
            current_user = None
            IF token:
                current_user = AWAIT authenticate_websocket_user(token)
            
            # Initialize chat session
            chat_service = get_service_factory().get_chat_service()
            IF NOT session_id:
                session_id = AWAIT chat_service.create_session(video_id, current_user)
            
            # Get video context for chat
            webapp_adapter = WebAppAdapter()
            video_context = AWAIT get_video_context(video_id)
            
            IF NOT video_context:
                AWAIT websocket.send_json({
                    "type": "error",
                    "error": "Video context not found. Please analyze the video first."
                })
                AWAIT websocket.close(code=4004)
                RETURN
            
            logger.info(f"WebSocket chat session started: {session_id} for video {video_id}")
            
            # Send session confirmation
            AWAIT websocket.send_json({
                "type": "session_started",
                "session_id": session_id,
                "video_id": video_id
            })
            
            # Message handling loop
            WHILE True:
                # Receive message from client
                data = AWAIT websocket.receive_json()
                
                IF data.get("type") == "chat_message":
                    AWAIT handle_chat_message(
                        websocket=websocket,
                        message_data=data,
                        session_id=session_id,
                        video_id=video_id,
                        video_context=video_context,
                        current_user=current_user,
                        webapp_adapter=webapp_adapter
                    )
                
                ELIF data.get("type") == "ping":
                    AWAIT websocket.send_json({"type": "pong"})
                
                ELSE:
                    AWAIT websocket.send_json({
                        "type": "error",
                        "error": "Unknown message type"
                    })
        
        EXCEPT WebSocketDisconnect:
            logger.info(f"WebSocket disconnected for session {session_id}")
        
        EXCEPT Exception as e:
            logger.error(f"WebSocket error: {str(e)}", exc_info=True)
            TRY:
                AWAIT websocket.send_json({
                    "type": "error",
                    "error": "Internal server error"
                })
                AWAIT websocket.close(code=1011)
            EXCEPT:
                PASS
        
        FINALLY:
            IF connection_id:
                websocket_manager.disconnect(connection_id, session_id or "default")

    ASYNC FUNCTION handle_chat_message(
        websocket: WebSocket,
        message_data: Dict[str, Any],
        session_id: str,
        video_id: str,
        video_context: Dict[str, Any],
        current_user: Optional[UserProfile],
        webapp_adapter: WebAppAdapter
    ):
        """Handle individual chat message with streaming response."""
        
        TRY:
            message = message_data.get("message", "").strip()
            IF NOT message:
                AWAIT websocket.send_json({
                    "type": "error",
                    "error": "Message cannot be empty"
                })
                RETURN
            
            # Check rate limiting for guests
            IF current_user IS None:
                rate_limit_key = f"chat_rate_limit:{websocket.client.host}"
                IF NOT check_rate_limit(rate_limit_key, max_requests=10, window_seconds=60):
                    AWAIT websocket.send_json({
                        "type": "error",
                        "error": "Rate limit exceeded. Please slow down."
                    })
                    RETURN
            
            # Prepare chat settings
            settings = {
                "model": message_data.get("model_name") OR ENV.get("LLM_DEFAULT_MODEL", "gpt-4o-mini"),
                "temperature": message_data.get("temperature") OR float(ENV.get("LLM_DEFAULT_TEMPERATURE", 0.2)),
                "use_context": message_data.get("use_context", True)
            }
            
            # Save user message
            chat_service = get_service_factory().get_chat_service()
            user_message_id = AWAIT chat_service.save_message(
                session_id=session_id,
                content=message,
                role="user",
                user_id=current_user.id IF current_user ELSE None
            )
            
            # Send user message confirmation
            AWAIT websocket.send_json({
                "type": "user_message_saved",
                "message_id": user_message_id,
                "content": message
            })
            
            # Start streaming response
            AWAIT websocket.send_json({
                "type": "assistant_response_start"
            })
            
            # Get streaming response from WebAppAdapter
            response_content = ""
            total_token_usage = None
            
            ASYNC FOR chunk IN webapp_adapter.get_chat_response_stream(
                message=message,
                video_id=video_id,
                session_id=session_id,
                video_context=video_context,
                settings=settings
            ):
                IF chunk.get("error"):
                    AWAIT websocket.send_json({
                        "type": "error",
                        "error": chunk["error"]
                    })
                    RETURN
                
                IF chunk.get("content"):
                    response_content += chunk["content"]
                    AWAIT websocket.send_json({
                        "type": "assistant_response_chunk",
                        "content": chunk["content"],
                        "is_final": False
                    })
                
                IF chunk.get("token_usage"):
                    total_token_usage = chunk["token_usage"]
            
            # Save assistant response
            assistant_message_id = AWAIT chat_service.save_message(
                session_id=session_id,
                content=response_content,
                role="assistant",
                token_usage=total_token_usage
            )
            
            # Send final response
            AWAIT websocket.send_json({
                "type": "assistant_response_complete",
                "message_id": assistant_message_id,
                "content": response_content,
                "token_usage": total_token_usage
            })
            
            logger.info(f"Chat message processed for session {session_id}")
            
        EXCEPT Exception as e:
            logger.error(f"Error handling chat message: {str(e)}", exc_info=True)
            AWAIT websocket.send_json({
                "type": "error",
                "error": "Failed to process message"
            })

    # Rate limiting utility
    rate_limit_store = {}

    FUNCTION check_rate_limit(key: str, max_requests: int, window_seconds: int) -> bool:
        """Check if request is within rate limit."""
        now = time.time()
        window_start = now - window_seconds
        
        # Clean old entries
        IF key IN rate_limit_store:
            rate_limit_store[key] = [
                timestamp FOR timestamp IN rate_limit_store[key]
                IF timestamp > window_start
            ]
        ELSE:
            rate_limit_store[key] = []
        
        # Check limit
        IF len(rate_limit_store[key]) >= max_requests:
            RETURN False
        
        # Add current request
        rate_limit_store[key].append(now)
        RETURN True

    # TDD Test Anchors
    TEST test_websocket_connection():
        WITH TestClient(app) AS client:
            WITH client.websocket_connect("/api/v1/video/chat/ws?video_id=test") AS websocket:
                data = websocket.receive_json()
                ASSERT data["type"] == "session_started"
    
    TEST test_chat_message_handling():
        WITH TestClient(app) AS client:
            WITH client.websocket_connect("/api/v1/video/chat/ws?video_id=test") AS websocket:
                websocket.send_json({
                    "type": "chat_message",
                    "message": "What is this video about?"
                })
                response = websocket.receive_json()
                ASSERT response["type"] == "user_message_saved"
```

## Module 5: Pydantic Models

### Request/Response Models
```python
# Pseudocode: Pydantic models for API
MODULE api_models:

    FROM pydantic IMPORT BaseModel, Field, validator
    FROM typing IMPORT List, Optional, Dict, Any
    FROM datetime IMPORT datetime
    FROM enum IMPORT Enum

    # Base response models
    CLASS BaseResponse(BaseModel):
        success: bool
        timestamp: datetime = Field(default_factory=datetime.utcnow)
        request_id: Optional[str] = None

    CLASS SuccessResponse(BaseResponse):
        success: bool = True
        data: Any

    CLASS ErrorResponse(BaseModel):
        error_code: str
        detail: str
        timestamp: datetime = Field(default_factory=datetime.utcnow)
        request_id: Optional[str] = None

    # Video analysis models
    CLASS VideoAnalysisRequest(BaseModel):
        youtube_url: str = Field(..., description="YouTube video URL")
        analysis_types: List[str] = Field(default=["Summary & Classification"])
        model_name: Optional[str] = Field(default=None)
        temperature: Optional[float] = Field(default=None, ge=0.0, le=1.0)
        use_cache: bool = Field(default=True)
        custom_instruction: Optional[str] = Field(default="")
        
        @validator("youtube_url")
        FUNCTION validate_youtube_url(cls, v):
            FROM utils.youtube_utils IMPORT validate_youtube_url
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

    CLASS VideoInfo(BaseModel):
        video_id: str
        title: str
        description: Optional[str]
        duration: Optional[int]
        view_count: Optional[int]
        channel_name: Optional[str]
        thumbnail_url: Optional[str]

    CLASS TaskOutput(BaseModel):
        task_name: str
        content: str
        token_usage: Optional[Dict[str, int]]
        execution_time: Optional[float]
        status: str

    CLASS AnalysisResponse(BaseModel):
        video_id: str
        youtube_url: str
        video_info: Optional[VideoInfo]
        task_outputs: Dict[str, TaskOutput]
        total_token_usage: Optional[Dict[str, int]]
        analysis_time: Optional[float]
        cached: bool
        chat_details: Optional[Dict[str, Any]]

    # Authentication models
    CLASS LoginRequest(BaseModel):
        email: str = Field(..., description="User email address")
        password: str = Field(..., min_length=6, description="User password")

    CLASS UserProfile(BaseModel):
        id: str
        email: str
        created_at: datetime
        email_confirmed: bool
        last_sign_in: Optional[datetime]

    CLASS AuthResponse(BaseModel):
        access_token: str
        refresh_token: str
        token_type: str = "bearer"
        expires_in: int
        user: UserProfile

    # Chat models
    CLASS ChatMessage(BaseModel):
        message: str = Field(..., min_length=1, max_length=2000)
        video_id: str
        session_id: Optional[str] = None
        model_name: Optional[str] = None
        temperature: Optional[float] = Field(default=None, ge=0.0, le=1.0)
        use_context: bool = True

    CLASS ChatMessageResponse(BaseModel):
        message_id: str
        content: str
        role: str  # "user" or "assistant"
        timestamp: datetime
        token_usage: Optional[Dict[str, int]]

    # TDD Test Anchors
    TEST test_video_analysis_request_validation():
        # Valid request
        request = VideoAnalysisRequest(
            youtube_url="https://youtu.be/test_video_id",
            analysis_types=["Summary & Classification"]
        )
        ASSERT request.youtube_url == "https://youtu.be/test_video_id"
        
        # Invalid URL
        WITH pytest.raises(ValueError):
            VideoAnalysisRequest(
                youtube_url="invalid-url",
                analysis_types=["Summary & Classification"]
            )
    
    TEST test_chat_message_validation():
        # Valid message
        message = ChatMessage(
            message="What is this video about?",
            video_id="test_video_id"
        )
        ASSERT message.message == "What is this video about?"
        
        # Empty message
        WITH pytest.raises(ValueError):
            ChatMessage(message="", video_id="test_video_id")
```

## Module 6: Error Handling and Middleware

### Custom Exception Handlers
```python
# Pseudocode: Error handling and middleware
MODULE error_handling:

    FROM fastapi IMPORT Request, HTTPException
    FROM fastapi.responses IMPORT JSONResponse
    FROM typing IMPORT Dict, Any
    FROM datetime IMPORT datetime
    IMPORT logging, time, uuid

    # Custom exceptions
    CLASS APIError(Exception):
        FUNCTION __init__(self, status_code: int, detail: str, error_code: str):
            self.status_code = status_code
            self.detail = detail
            self.error_code = error_code

    CLASS ValidationError(APIError):
        FUNCTION __init__(self, detail: str):
            super().__init__(422, detail, "VALIDATION_ERROR")

    CLASS AuthenticationError(APIError):
        FUNCTION __init__(self, detail: str = "Authentication required"):
            super().__init__(401, detail, "AUTHENTICATION_ERROR")

    CLASS NotFoundError(APIError):
        FUNCTION __init__(self, detail: str = "Resource not found"):
            super().__init__(404, detail, "NOT_FOUND")

    # Request logging middleware
    CLASS RequestLoggingMiddleware:
        FUNCTION __init__(self, app):
            self.app = app
        
        ASYNC FUNCTION __call__(self, request: Request, call_next):
            request_id = str(uuid.uuid4())
            request.state.request_id = request_id
            
            start_time = time.time()
            
            logger.info(f"Request {request_id}: {request.method} {request.url}")
            
            response = AWAIT call_next(request)
            
            process_time = time.time() - start_time
            logger.info(f"Request {request_id} completed in {process_time:.3f}s with status {response.status_code}")
            
            response.headers["X-Request-ID"] = request_id
            RETURN response

    # Error handling middleware
    CLASS ErrorHandlingMiddleware:
        FUNCTION __init__(self, app):
            self.app = app
        
        ASYNC FUNCTION __call__(self, request: Request, call_next):
            TRY:
                RETURN AWAIT call_next(request)
            EXCEPT APIError as e:
                RETURN JSONResponse(
                    status_code=e.status_code,
                    content={
                        "success": False,
                        "error": {
                            "error_code": e.error_code,
                            "detail": e.detail,
                            "timestamp": datetime.utcnow().isoformat(),
                            "request_id": getattr(request.state, "request_id", None)
                        }
                    }
                )
            EXCEPT HTTPException as e:
                RETURN JSONResponse(
                    status_code=e.status_code,
                    content={
                        "success": False,
                        "error": {
                            "error_code": "HTTP_ERROR",
                            "detail": e.detail,
                            "timestamp": datetime.utcnow().isoformat(),
                            "request_id": getattr(request.state, "request_id", None)
                        }
                    }
                )
            EXCEPT Exception as e:
                logger.error(f"Unhandled error: {e}", exc_info=True)
                RETURN JSONResponse(
                    status_code=500,
                    content={
                        "success": False,
                        "error": {
                            "error_code": "INTERNAL_ERROR",
                            "detail": "Internal server error",
                            "timestamp": datetime.utcnow().isoformat(),
                            "request_id": getattr(request.state, "request_id", None)
                        }
                    }
                )

    # TDD Test Anchors
    TEST test_error_handling_middleware():
        # Test API error handling
        WITH TestClient(app) AS client:
            # Mock endpoint that raises APIError
            response = client.get("/test-api-error")
            ASSERT response.status_code == 422
            ASSERT response.json()["success"] == False
            ASSERT "error" IN response.json()
    
    TEST test_request_logging_middleware():
        WITH TestClient(app) AS client:
            response = client.get("/health")
            ASSERT "X-Request-ID" IN response.headers
```

## Module 7: Dependency Injection

### Service Dependencies
```python
# Pseudocode: FastAPI dependency injection
MODULE dependencies:

    FROM fastapi IMPORT Depends
    FROM service_factory IMPORT get_service_factory, ServiceFactory
    FROM adapters.webapp_adapter IMPORT WebAppAdapter
    FROM repositories IMPORT CacheRepository
    FROM services IMPORT AnalysisService, ChatService, TranscriptService

    # Service factory dependency
    FUNCTION get_service_factory_dependency() -> ServiceFactory:
        """Get service factory instance."""
        RETURN get_service_factory()

    # Service dependencies
    FUNCTION get_analysis_service(
        factory: ServiceFactory = Depends(get_service_factory_dependency)
    ) -> AnalysisService:
        """Get analysis service instance."""
        RETURN factory.get_analysis_service()

    FUNCTION get_chat_service(
        factory: ServiceFactory = Depends(get_service_factory_dependency)
    ) -> ChatService:
        """Get chat service instance."""
        RETURN factory.get_chat_service()

    FUNCTION get_transcript_service(
        factory: ServiceFactory = Depends(get_service_factory_dependency)
    ) -> TranscriptService:
        """Get transcript service instance."""
        RETURN factory.get_transcript_service()

    FUNCTION get_cache_repository(
        factory: ServiceFactory = Depends(get_service_factory_dependency)
    ) -> CacheRepository:
        """Get cache repository instance."""
        RETURN factory.get_cache_repository()

    FUNCTION get_webapp_adapter(
        factory: ServiceFactory = Depends(get_service_factory_dependency)
    ) -> WebAppAdapter:
        """Get WebApp adapter instance."""
        RETURN WebAppAdapter()

    # Admin user dependency
    FUNCTION get_current_user_admin(
        current_user: UserProfile = Depends(get_current_user)
    ) -> UserProfile:
        """Get current user and verify admin privileges."""
        # Check if user has admin role
        admin_emails = ENV.get("ADMIN_EMAILS", "").split(",")
        IF current_user.email NOT IN admin_emails:
            RAISE HTTPException(
                status_code=403,
                detail="Admin privileges required"
            )
        RETURN current_user

    # TDD Test Anchors
    TEST test_service_dependencies():
        factory = get_service_factory_dependency()
        analysis_service = get_analysis_service(factory)
        ASSERT analysis_service IS NOT None
        ASSERT isinstance(analysis_service, AnalysisService)
    
    TEST test_admin_user_dependency():
        WITH patch.dict(os.environ, {"ADMIN_EMAILS": "admin@example.com"}):
            admin_user = UserProfile(
                id="admin123",
                email="admin@example.com",
                created_at=datetime.utcnow(),
                email_confirmed=True
            )
            result = get_current_user_admin(admin_user)
            ASSERT result.email == "admin@example.com"
        
        # Test non-admin user
        WITH pytest.raises(HTTPException):
            regular_user = UserProfile(
                id="user123",
                email="user@example.com",
                created_at=datetime.utcnow(),
                email_confirmed=True
            )
            get_current_user_admin(regular_user)
```

## Environment Configuration

### Required Environment Variables
```bash
# Core API settings
API_SECRET_KEY=your-secret-key-here  # Required for JWT
API_HOST=0.0.0.0
API_PORT=8000
API_DEBUG=false
API_CORS_ORIGINS=http://localhost:3000,https://yourdomain.com

# Token settings
API_ACCESS_TOKEN_EXPIRE_MINUTES=30

# Supabase integration (inherited from existing config)
SUPABASE_URL=your-supabase-url
SUPABASE_ANON_KEY=your-supabase-key

# Application settings
APP_VERSION=1.0.0
ENVIRONMENT=production

# Feature flags
ENABLE_GUEST_ACCESS=true
ENABLE_CHAT=true
ENABLE_STREAMING=true
ENABLE_CACHING=true
ENABLE_SUBTITLE_TRANSLATION=false

# Usage limits
MAX_GUEST_ANALYSES=1
MAX_GUEST_TRANSLATIONS=1
MAX_CONCURRENT_ANALYSES=10
RATE_LIMIT_PER_MINUTE=60

# Admin settings
ADMIN_EMAILS=admin@example.com,superuser@example.com

# LLM settings (inherited from existing config)
LLM_DEFAULT_MODEL=gpt-4o-mini
LLM_DEFAULT_TEMPERATURE=0.2
```

## Integration Testing Strategy

### TDD Test Structure
```python
# Pseudocode: Integration test structure
MODULE integration_tests:

    # Test complete video analysis flow
    TEST test_complete_video_analysis_flow():
        WITH TestClient(app) AS client:
            # 1. Analyze video
            response = client.post("/api/v1/video/analyze", json={
                "youtube_url": "https://youtu.be/test_video_id",
                "analysis_types": ["Summary & Classification"]
            })
            ASSERT response.status_code == 200
            video_id = response.json()["data"]["video_id"]
            
            # 2. Generate additional content
            response = client.post("/api/v1/video/content/generate", json={
                "video_id": video_id,
                "content_type": "Blog Post"
            })
            ASSERT response.status_code == 200
            
            # 3. Get transcript
            response = client.get(f"/api/v1/video/transcript?youtube_url=https://youtu.be/{video_id}&video_id={video_id}")
            ASSERT response.status_code == 200

    # Test authentication flow
    TEST test_authentication_flow():
        WITH TestClient(app) AS client:
            # 1. Login
            response = client.post("/api/v1/auth/login", json={
                "email": "test@example.com",
                "password": "password123"
            })
            ASSERT response.status_code == 200
            token = response.json()["data"]["access_token"]
            
            # 2. Access protected endpoint
            headers = {"Authorization": f"Bearer {token}"}
            response = client.get("/api/v1/auth/me", headers=headers)
            ASSERT response.status_code == 200

    # Test WebSocket chat flow
    TEST test_websocket_chat_flow():
        WITH TestClient(app) AS client:
            WITH client.websocket_connect("/api/v1/video/chat/ws?video_id=test_video") AS websocket:
                # Receive session start
                data = websocket.receive_json()
                ASSERT data["type"] == "session_started"
                
                # Send message
                websocket.send_json({
                    "type": "chat_message",
                    "message": "What is this video about?"
                })
                
                # Receive response
                data = websocket.receive_json()
                ASSERT data["type"] == "user_message_saved"

    # Test error handling
    TEST test_error_handling():
        WITH TestClient(app) AS client:
            # Test validation error
            response = client.post("/api/v1/video/analyze", json={
                "youtube_url": "invalid-url"
            })
            ASSERT response.status_code == 422
            ASSERT response.json()["success"] == False
            
            # Test authentication error
            response = client.get("/api/v1/auth/me")
            ASSERT response.status_code == 401

    # Test guest usage limits
    TEST test_guest_usage_limits():
        WITH TestClient(app) AS client:
            # First analysis should succeed
            response = client.post("/api/v1/video/analyze", json={
                "youtube_url": "https://youtu.be/test_video_id",
                "analysis_types": ["Summary & Classification"]
            })
            ASSERT response.status_code == 200
            
            # Second analysis should fail for guest
            response = client.post("/api/v1/video/analyze", json={
                "youtube_url": "https://youtu.be/test_video_id2",
                "analysis_types": ["Summary & Classification"]
            })
            ASSERT response.status_code == 401
```

This comprehensive pseudocode provides a complete implementation guide for the FastAPI backend that:

1. **Integrates seamlessly** with existing [`WebAppAdapter`](src/youtube_analysis/adapters/webapp_adapter.py:20) methods
2. **Preserves Clean Architecture** by using the [`ServiceFactory`](src/youtube_analysis/service_factory.py:13) dependency injection pattern
3. **Provides modular structure** with each module under 500 lines
4. **Includes comprehensive TDD anchors** for testing
5. **Uses environment variables** for all configuration (no hardcoded values)
6. **Supports async/await patterns** for optimal performance
7. **Implements proper error handling** and logging strategies
8. **Maintains existing data model compatibility** with [`AnalysisResult`](src/youtube_analysis/models/analysis_result.py:245) and [`TokenUsage`](src/youtube_analysis/models/analysis_result.py:45)

The pseudocode is ready for implementation and provides clear guidance for creating a production-ready FastAPI backend that bridges the existing Python services with the new Node.js frontend.