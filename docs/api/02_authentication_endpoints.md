# Authentication Endpoints Specification

## Overview

Authentication endpoints that integrate with the existing Supabase authentication service, providing JWT-based authentication for the Node.js frontend.

## Authentication Router

### Base Configuration
```python
# Pseudocode: Authentication router setup
router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])

# OAuth2 scheme for JWT tokens
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
optional_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)
```

## Data Models

### Request Models
```python
# Pseudocode: Authentication request models
CLASS LoginRequest(BaseModel):
    PROPERTY email: str = Field(..., description="User email address")
    PROPERTY password: str = Field(..., min_length=6, description="User password")

CLASS SignupRequest(BaseModel):
    PROPERTY email: str = Field(..., description="User email address")
    PROPERTY password: str = Field(..., min_length=6, description="User password")
    PROPERTY confirm_password: str = Field(..., description="Password confirmation")
    
    @validator("confirm_password")
    FUNCTION validate_passwords_match(cls, v, values):
        IF "password" IN values AND v != values["password"]:
            RAISE ValueError("Passwords do not match")
        RETURN v

CLASS RefreshTokenRequest(BaseModel):
    PROPERTY refresh_token: str = Field(..., description="Refresh token")

CLASS PasswordResetRequest(BaseModel):
    PROPERTY email: str = Field(..., description="User email address")

CLASS PasswordUpdateRequest(BaseModel):
    PROPERTY current_password: str = Field(..., description="Current password")
    PROPERTY new_password: str = Field(..., min_length=6, description="New password")
```

### Response Models
```python
# Pseudocode: Authentication response models
CLASS UserProfile(BaseModel):
    PROPERTY id: str
    PROPERTY email: str
    PROPERTY created_at: datetime
    PROPERTY email_confirmed: bool
    PROPERTY last_sign_in: Optional[datetime]

CLASS AuthResponse(BaseModel):
    PROPERTY access_token: str
    PROPERTY refresh_token: str
    PROPERTY token_type: str = "bearer"
    PROPERTY expires_in: int
    PROPERTY user: UserProfile

CLASS LogoutResponse(BaseModel):
    PROPERTY message: str = "Successfully logged out"

CLASS PasswordResetResponse(BaseModel):
    PROPERTY message: str = "Password reset email sent"
```

## Authentication Endpoints

### POST /api/v1/auth/login
```python
# Pseudocode: User login endpoint
@router.post("/login", response_model=SuccessResponse[AuthResponse])
ASYNC FUNCTION login(
    request: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service)
) -> SuccessResponse[AuthResponse]:
    """
    Authenticate user with email and password.
    
    Returns JWT access token and refresh token.
    """
    TRY:
        # Authenticate with Supabase
        supabase_client = get_supabase_client()
        auth_response = supabase_client.auth.sign_in_with_password({
            "email": request.email,
            "password": request.password
        })
        
        IF auth_response.user IS None:
            RAISE AuthenticationError("Invalid credentials")
        
        # Create JWT token
        access_token = create_access_token(
            data={"sub": auth_response.user.id, "email": auth_response.user.email}
        )
        
        # Extract user profile
        user_profile = UserProfile(
            id=auth_response.user.id,
            email=auth_response.user.email,
            created_at=datetime.fromisoformat(auth_response.user.created_at),
            email_confirmed=auth_response.user.email_confirmed_at IS NOT None,
            last_sign_in=datetime.fromisoformat(auth_response.user.last_sign_in_at) IF auth_response.user.last_sign_in_at ELSE None
        )
        
        auth_data = AuthResponse(
            access_token=access_token,
            refresh_token=auth_response.session.refresh_token,
            expires_in=int(ENV.get("API_ACCESS_TOKEN_EXPIRE_MINUTES", 30)) * 60,
            user=user_profile
        )
        
        logger.info(f"User {request.email} logged in successfully")
        
        RETURN SuccessResponse(data=auth_data)
        
    EXCEPT Exception as e:
        logger.error(f"Login failed for {request.email}: {str(e)}")
        RAISE AuthenticationError("Invalid credentials")
```

### POST /api/v1/auth/signup
```python
# Pseudocode: User signup endpoint
@router.post("/signup", response_model=SuccessResponse[AuthResponse])
ASYNC FUNCTION signup(
    request: SignupRequest,
    auth_service: AuthService = Depends(get_auth_service)
) -> SuccessResponse[AuthResponse]:
    """
    Register new user account.
    
    Creates account in Supabase and returns authentication tokens.
    """
    TRY:
        # Create user in Supabase
        supabase_client = get_supabase_client()
        auth_response = supabase_client.auth.sign_up({
            "email": request.email,
            "password": request.password
        })
        
        IF auth_response.user IS None:
            RAISE ValidationError("Failed to create user account")
        
        # Create JWT token
        access_token = create_access_token(
            data={"sub": auth_response.user.id, "email": auth_response.user.email}
        )
        
        # Extract user profile
        user_profile = UserProfile(
            id=auth_response.user.id,
            email=auth_response.user.email,
            created_at=datetime.fromisoformat(auth_response.user.created_at),
            email_confirmed=auth_response.user.email_confirmed_at IS NOT None,
            last_sign_in=None
        )
        
        auth_data = AuthResponse(
            access_token=access_token,
            refresh_token=auth_response.session.refresh_token IF auth_response.session ELSE "",
            expires_in=int(ENV.get("API_ACCESS_TOKEN_EXPIRE_MINUTES", 30)) * 60,
            user=user_profile
        )
        
        logger.info(f"User {request.email} signed up successfully")
        
        RETURN SuccessResponse(data=auth_data)
        
    EXCEPT Exception as e:
        logger.error(f"Signup failed for {request.email}: {str(e)}")
        RAISE ValidationError("Failed to create user account")
```

### POST /api/v1/auth/logout
```python
# Pseudocode: User logout endpoint
@router.post("/logout", response_model=SuccessResponse[LogoutResponse])
ASYNC FUNCTION logout(
    current_user: UserProfile = Depends(get_current_user)
) -> SuccessResponse[LogoutResponse]:
    """
    Logout current user.
    
    Invalidates the current session in Supabase.
    """
    TRY:
        # Sign out from Supabase
        supabase_client = get_supabase_client()
        supabase_client.auth.sign_out()
        
        logger.info(f"User {current_user.email} logged out successfully")
        
        RETURN SuccessResponse(data=LogoutResponse())
        
    EXCEPT Exception as e:
        logger.error(f"Logout failed for user {current_user.email}: {str(e)}")
        # Return success even if logout fails to avoid client-side issues
        RETURN SuccessResponse(data=LogoutResponse())
```

### POST /api/v1/auth/refresh
```python
# Pseudocode: Token refresh endpoint
@router.post("/refresh", response_model=SuccessResponse[AuthResponse])
ASYNC FUNCTION refresh_token(
    request: RefreshTokenRequest
) -> SuccessResponse[AuthResponse]:
    """
    Refresh access token using refresh token.
    """
    TRY:
        # Refresh session with Supabase
        supabase_client = get_supabase_client()
        auth_response = supabase_client.auth.refresh_session(request.refresh_token)
        
        IF auth_response.user IS None:
            RAISE AuthenticationError("Invalid refresh token")
        
        # Create new JWT token
        access_token = create_access_token(
            data={"sub": auth_response.user.id, "email": auth_response.user.email}
        )
        
        # Extract user profile
        user_profile = UserProfile(
            id=auth_response.user.id,
            email=auth_response.user.email,
            created_at=datetime.fromisoformat(auth_response.user.created_at),
            email_confirmed=auth_response.user.email_confirmed_at IS NOT None,
            last_sign_in=datetime.fromisoformat(auth_response.user.last_sign_in_at) IF auth_response.user.last_sign_in_at ELSE None
        )
        
        auth_data = AuthResponse(
            access_token=access_token,
            refresh_token=auth_response.session.refresh_token,
            expires_in=int(ENV.get("API_ACCESS_TOKEN_EXPIRE_MINUTES", 30)) * 60,
            user=user_profile
        )
        
        RETURN SuccessResponse(data=auth_data)
        
    EXCEPT Exception as e:
        logger.error(f"Token refresh failed: {str(e)}")
        RAISE AuthenticationError("Invalid refresh token")
```

### GET /api/v1/auth/me
```python
# Pseudocode: Get current user profile
@router.get("/me", response_model=SuccessResponse[UserProfile])
ASYNC FUNCTION get_current_user_profile(
    current_user: UserProfile = Depends(get_current_user)
) -> SuccessResponse[UserProfile]:
    """
    Get current authenticated user profile.
    """
    RETURN SuccessResponse(data=current_user)
```

### POST /api/v1/auth/password-reset
```python
# Pseudocode: Password reset request
@router.post("/password-reset", response_model=SuccessResponse[PasswordResetResponse])
ASYNC FUNCTION request_password_reset(
    request: PasswordResetRequest
) -> SuccessResponse[PasswordResetResponse]:
    """
    Request password reset email.
    """
    TRY:
        # Send password reset email via Supabase
        supabase_client = get_supabase_client()
        supabase_client.auth.reset_password_email(request.email)
        
        logger.info(f"Password reset requested for {request.email}")
        
        RETURN SuccessResponse(data=PasswordResetResponse())
        
    EXCEPT Exception as e:
        logger.error(f"Password reset failed for {request.email}: {str(e)}")
        # Return success to avoid email enumeration
        RETURN SuccessResponse(data=PasswordResetResponse())
```

## Utility Functions

### JWT Token Management
```python
# Pseudocode: JWT utilities
FUNCTION create_access_token(data: Dict[str, Any]) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=int(ENV.get("API_ACCESS_TOKEN_EXPIRE_MINUTES", 30)))
    to_encode.update({"exp": expire})
    
    encoded_jwt = jwt.encode(to_encode, ENV.get("API_SECRET_KEY"), algorithm="HS256")
    RETURN encoded_jwt

FUNCTION verify_token(token: str) -> Dict[str, Any]:
    TRY:
        payload = jwt.decode(token, ENV.get("API_SECRET_KEY"), algorithms=["HS256"])
        RETURN payload
    EXCEPT JWTError:
        RAISE AuthenticationError("Invalid token")
```

### Supabase Client
```python
# Pseudocode: Supabase client factory
FUNCTION get_supabase_client() -> Client:
    supabase_url = ENV.get("SUPABASE_URL")
    supabase_key = ENV.get("SUPABASE_KEY")
    
    IF NOT supabase_url OR NOT supabase_key:
        RAISE ValueError("Supabase credentials not configured")
    
    RETURN create_client(supabase_url, supabase_key)
```

## TDD Test Anchors

### Authentication Flow Tests
```python
# Test anchor: Successful login
TEST test_successful_login():
    WITH TestClient(app) AS client:
        response = client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "password123"
        })
        ASSERT response.status_code == 200
        ASSERT "access_token" IN response.json()["data"]
        ASSERT "user" IN response.json()["data"]

# Test anchor: Invalid credentials
TEST test_invalid_credentials():
    WITH TestClient(app) AS client:
        response = client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "wrongpassword"
        })
        ASSERT response.status_code == 401
        ASSERT response.json()["success"] == False

# Test anchor: User signup
TEST test_user_signup():
    WITH TestClient(app) AS client:
        response = client.post("/api/v1/auth/signup", json={
            "email": "newuser@example.com",
            "password": "password123",
            "confirm_password": "password123"
        })
        ASSERT response.status_code == 200
        ASSERT "access_token" IN response.json()["data"]

# Test anchor: Password mismatch
TEST test_password_mismatch():
    WITH TestClient(app) AS client:
        response = client.post("/api/v1/auth/signup", json={
            "email": "newuser@example.com",
            "password": "password123",
            "confirm_password": "different"
        })
        ASSERT response.status_code == 422

# Test anchor: Protected endpoint access
TEST test_protected_endpoint_access():
    WITH TestClient(app) AS client:
        # Without token
        response = client.get("/api/v1/auth/me")
        ASSERT response.status_code == 401
        
        # With valid token
        token = create_test_jwt_token()
        response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        ASSERT response.status_code == 200

# Test anchor: Token refresh
TEST test_token_refresh():
    WITH TestClient(app) AS client:
        refresh_token = create_test_refresh_token()
        response = client.post("/api/v1/auth/refresh", json={
            "refresh_token": refresh_token
        })
        ASSERT response.status_code == 200
        ASSERT "access_token" IN response.json()["data"]
```

### Validation Tests
```python
# Test anchor: Email validation
TEST test_email_validation():
    WITH TestClient(app) AS client:
        response = client.post("/api/v1/auth/login", json={
            "email": "invalid-email",
            "password": "password123"
        })
        ASSERT response.status_code == 422

# Test anchor: Password length validation
TEST test_password_length_validation():
    WITH TestClient(app) AS client:
        response = client.post("/api/v1/auth/signup", json={
            "email": "test@example.com",
            "password": "123",  # Too short
            "confirm_password": "123"
        })
        ASSERT response.status_code == 422
```

## Error Handling

### Authentication Errors
```python
# Pseudocode: Authentication error responses
EXCEPTION_HANDLER(AuthenticationError)
FUNCTION handle_auth_error(request: Request, exc: AuthenticationError):
    RETURN JSONResponse(
        status_code=401,
        content=ErrorResponseModel(
            error=ErrorResponse(
                error_code="AUTHENTICATION_ERROR",
                detail=exc.detail,
                timestamp=datetime.now(),
                request_id=getattr(request.state, "request_id", None)
            )
        ).dict()
    )
```

## Environment Configuration

### Required Variables
```bash
# JWT configuration
API_SECRET_KEY=your-secret-key-here  # Required
API_ACCESS_TOKEN_EXPIRE_MINUTES=30

# Supabase configuration (inherited)
SUPABASE_URL=your-supabase-url
SUPABASE_KEY=your-supabase-key
```

This authentication specification provides secure JWT-based authentication that integrates seamlessly with the existing Supabase authentication service while providing a clean REST API for the Node.js frontend.