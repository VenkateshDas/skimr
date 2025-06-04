# FastAPI Backend Core Specification

## Overview

This specification defines the core FastAPI backend layer that bridges the existing Python services with the new Node.js frontend. The API follows RESTful principles with WebSocket support for streaming operations.

## Architecture Integration

### Service Factory Integration
```python
# Pseudocode: FastAPI dependency injection
DEPENDENCY get_service_factory() -> ServiceFactory:
    RETURN global_service_factory_instance

DEPENDENCY get_analysis_service(factory: ServiceFactory) -> AnalysisService:
    RETURN factory.get_analysis_service()

DEPENDENCY get_chat_service(factory: ServiceFactory) -> ChatService:
    RETURN factory.get_chat_service()
```

### Environment Configuration
```python
# Environment variables (no hardcoded values)
API_HOST = ENV.get("API_HOST", "0.0.0.0")
API_PORT = ENV.get("API_PORT", 8000)
API_DEBUG = ENV.get("API_DEBUG", "false").lower() == "true"
API_CORS_ORIGINS = ENV.get("API_CORS_ORIGINS", "http://localhost:3000").split(",")
API_SECRET_KEY = ENV.get("API_SECRET_KEY")  # Required for JWT
API_ACCESS_TOKEN_EXPIRE_MINUTES = ENV.get("API_ACCESS_TOKEN_EXPIRE_MINUTES", 30)
```

## Core FastAPI Application

### Application Setup
```python
# Pseudocode: FastAPI app initialization
FUNCTION create_app() -> FastAPI:
    app = FastAPI(
        title="YouTube Analysis API",
        description="Backend API for YouTube video analysis",
        version=ENV.get("APP_VERSION", "1.0.0"),
        debug=API_DEBUG
    )
    
    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=API_CORS_ORIGINS,
        allow_credentials=true,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"]
    )
    
    # Request logging middleware
    app.add_middleware(RequestLoggingMiddleware)
    
    # Error handling middleware
    app.add_middleware(ErrorHandlingMiddleware)
    
    # Include routers
    app.include_router(auth_router, prefix="/api/v1/auth", tags=["authentication"])
    app.include_router(video_router, prefix="/api/v1/video", tags=["video"])
    app.include_router(config_router, prefix="/api/v1/config", tags=["configuration"])
    app.include_router(cache_router, prefix="/api/v1/cache", tags=["cache"])
    
    RETURN app
```

### Error Handling
```python
# Pseudocode: Global error handlers
CLASS APIError(Exception):
    PROPERTY status_code: int
    PROPERTY detail: str
    PROPERTY error_code: str

CLASS ValidationError(APIError):
    CONSTRUCTOR(detail: str):
        self.status_code = 422
        self.detail = detail
        self.error_code = "VALIDATION_ERROR"

CLASS AuthenticationError(APIError):
    CONSTRUCTOR(detail: str = "Authentication required"):
        self.status_code = 401
        self.detail = detail
        self.error_code = "AUTHENTICATION_ERROR"

CLASS NotFoundError(APIError):
    CONSTRUCTOR(detail: str = "Resource not found"):
        self.status_code = 404
        self.detail = detail
        self.error_code = "NOT_FOUND"

# Error response model
CLASS ErrorResponse(BaseModel):
    PROPERTY error_code: str
    PROPERTY detail: str
    PROPERTY timestamp: datetime
    PROPERTY request_id: Optional[str]
```

### Request/Response Models
```python
# Pseudocode: Base response models
CLASS BaseResponse(BaseModel):
    PROPERTY success: bool
    PROPERTY timestamp: datetime = Field(default_factory=datetime.now)
    PROPERTY request_id: Optional[str]

CLASS SuccessResponse(BaseResponse):
    PROPERTY success: bool = True
    PROPERTY data: Any

CLASS ErrorResponseModel(BaseResponse):
    PROPERTY success: bool = False
    PROPERTY error: ErrorResponse
```

## Authentication Integration

### JWT Token Models
```python
# Pseudocode: JWT token models
CLASS TokenData(BaseModel):
    PROPERTY user_id: str
    PROPERTY email: str
    PROPERTY exp: datetime

CLASS TokenResponse(BaseModel):
    PROPERTY access_token: str
    PROPERTY token_type: str = "bearer"
    PROPERTY expires_in: int
    PROPERTY user: UserProfile

CLASS UserProfile(BaseModel):
    PROPERTY id: str
    PROPERTY email: str
    PROPERTY created_at: datetime
    PROPERTY is_active: bool
```

### Authentication Dependencies
```python
# Pseudocode: Auth dependencies
ASYNC FUNCTION get_current_user(token: str = Depends(oauth2_scheme)) -> UserProfile:
    TRY:
        payload = jwt.decode(token, API_SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("sub")
        IF user_id IS None:
            RAISE AuthenticationError("Invalid token")
        
        # Verify user exists in Supabase
        supabase_client = get_supabase_client()
        user_response = supabase_client.auth.get_user(token)
        
        IF user_response.user IS None:
            RAISE AuthenticationError("User not found")
        
        RETURN UserProfile(
            id=user_response.user.id,
            email=user_response.user.email,
            created_at=user_response.user.created_at,
            is_active=True
        )
    EXCEPT JWTError:
        RAISE AuthenticationError("Invalid token")

FUNCTION get_optional_user(token: Optional[str] = Depends(optional_oauth2_scheme)) -> Optional[UserProfile]:
    IF token IS None:
        RETURN None
    TRY:
        RETURN get_current_user(token)
    EXCEPT AuthenticationError:
        RETURN None
```

## Middleware Components

### Request Logging Middleware
```python
# Pseudocode: Request logging
CLASS RequestLoggingMiddleware:
    ASYNC FUNCTION __call__(request: Request, call_next):
        request_id = str(uuid4())
        request.state.request_id = request_id
        
        start_time = time.time()
        
        logger.info(f"Request {request_id}: {request.method} {request.url}")
        
        response = AWAIT call_next(request)
        
        process_time = time.time() - start_time
        logger.info(f"Request {request_id} completed in {process_time:.3f}s with status {response.status_code}")
        
        response.headers["X-Request-ID"] = request_id
        RETURN response
```

### Error Handling Middleware
```python
# Pseudocode: Error handling
CLASS ErrorHandlingMiddleware:
    ASYNC FUNCTION __call__(request: Request, call_next):
        TRY:
            RETURN AWAIT call_next(request)
        EXCEPT APIError as e:
            RETURN JSONResponse(
                status_code=e.status_code,
                content=ErrorResponseModel(
                    error=ErrorResponse(
                        error_code=e.error_code,
                        detail=e.detail,
                        timestamp=datetime.now(),
                        request_id=getattr(request.state, "request_id", None)
                    )
                ).dict()
            )
        EXCEPT Exception as e:
            logger.error(f"Unhandled error: {e}", exc_info=True)
            RETURN JSONResponse(
                status_code=500,
                content=ErrorResponseModel(
                    error=ErrorResponse(
                        error_code="INTERNAL_ERROR",
                        detail="Internal server error",
                        timestamp=datetime.now(),
                        request_id=getattr(request.state, "request_id", None)
                    )
                ).dict()
            )
```

## Health Check Endpoints

### System Health
```python
# Pseudocode: Health check endpoints
CLASS HealthStatus(BaseModel):
    PROPERTY status: str
    PROPERTY timestamp: datetime
    PROPERTY version: str
    PROPERTY dependencies: Dict[str, str]

@router.get("/health", response_model=HealthStatus)
ASYNC FUNCTION health_check():
    dependencies = {}
    
    # Check Supabase connection
    TRY:
        supabase_client = get_supabase_client()
        # Simple query to test connection
        supabase_client.table("auth.users").select("count").limit(1).execute()
        dependencies["supabase"] = "healthy"
    EXCEPT Exception:
        dependencies["supabase"] = "unhealthy"
    
    # Check service factory
    TRY:
        factory = get_service_factory()
        dependencies["service_factory"] = "healthy"
    EXCEPT Exception:
        dependencies["service_factory"] = "unhealthy"
    
    RETURN HealthStatus(
        status="healthy" IF all(status == "healthy" FOR status IN dependencies.values()) ELSE "degraded",
        timestamp=datetime.now(),
        version=ENV.get("APP_VERSION", "1.0.0"),
        dependencies=dependencies
    )
```

## TDD Test Anchors

### Core Application Tests
```python
# Test anchor: FastAPI app creation
TEST test_create_app():
    app = create_app()
    ASSERT app.title == "YouTube Analysis API"
    ASSERT "/api/v1/auth" IN [route.path FOR route IN app.routes]

# Test anchor: CORS configuration
TEST test_cors_configuration():
    app = create_app()
    cors_middleware = FIND_MIDDLEWARE(app, CORSMiddleware)
    ASSERT cors_middleware IS NOT None
    ASSERT "http://localhost:3000" IN cors_middleware.allow_origins

# Test anchor: Error handling
TEST test_error_handling():
    WITH TestClient(app) AS client:
        response = client.get("/nonexistent")
        ASSERT response.status_code == 404
        ASSERT response.json()["success"] == False
        ASSERT "error" IN response.json()

# Test anchor: Health check
TEST test_health_check():
    WITH TestClient(app) AS client:
        response = client.get("/health")
        ASSERT response.status_code == 200
        ASSERT "status" IN response.json()
        ASSERT "dependencies" IN response.json()
```

### Authentication Tests
```python
# Test anchor: JWT token validation
TEST test_jwt_token_validation():
    valid_token = create_test_jwt_token(user_id="test_user")
    user = AWAIT get_current_user(valid_token)
    ASSERT user.id == "test_user"

# Test anchor: Invalid token handling
TEST test_invalid_token_handling():
    WITH pytest.raises(AuthenticationError):
        AWAIT get_current_user("invalid_token")

# Test anchor: Optional authentication
TEST test_optional_authentication():
    user = get_optional_user(None)
    ASSERT user IS None
```

### Middleware Tests
```python
# Test anchor: Request logging
TEST test_request_logging():
    WITH TestClient(app) AS client:
        response = client.get("/health")
        ASSERT "X-Request-ID" IN response.headers

# Test anchor: Error middleware
TEST test_error_middleware():
    # Mock an endpoint that raises an exception
    WITH TestClient(app) AS client:
        response = client.get("/test-error")
        ASSERT response.status_code == 500
        ASSERT response.json()["success"] == False
```

## Configuration Requirements

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
SUPABASE_KEY=your-supabase-key

# Application version
APP_VERSION=1.0.0
```

### Optional Environment Variables
```bash
# Request timeout settings
API_REQUEST_TIMEOUT=30
API_MAX_REQUEST_SIZE=10485760  # 10MB

# Rate limiting
API_RATE_LIMIT_REQUESTS=100
API_RATE_LIMIT_WINDOW=60  # seconds

# Logging
API_LOG_LEVEL=INFO
API_LOG_FORMAT=json
```

This core specification provides the foundation for the FastAPI backend, integrating with the existing service architecture while providing a clean REST API interface for the Node.js frontend.