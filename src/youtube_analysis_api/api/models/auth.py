"""Authentication models for the API."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, validator


class LoginRequest(BaseModel):
    """Login request model."""
    
    email: str = Field(..., description="User email address")
    password: str = Field(..., min_length=6, description="User password")


class SignupRequest(BaseModel):
    """Signup request model."""
    
    email: str = Field(..., description="User email address")
    password: str = Field(..., min_length=6, description="User password")
    confirm_password: str = Field(..., description="Password confirmation")
    
    @validator("confirm_password")
    def validate_passwords_match(cls, v, values):
        """Validate that passwords match."""
        if "password" in values and v != values["password"]:
            raise ValueError("Passwords do not match")
        return v


class RefreshTokenRequest(BaseModel):
    """Refresh token request model."""
    
    refresh_token: str = Field(..., description="Refresh token")


class PasswordResetRequest(BaseModel):
    """Password reset request model."""
    
    email: str = Field(..., description="User email address")


class PasswordUpdateRequest(BaseModel):
    """Password update request model."""
    
    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=6, description="New password")


class UserProfile(BaseModel):
    """User profile model."""
    
    id: str
    email: str
    created_at: datetime
    email_confirmed: bool
    last_sign_in: Optional[datetime] = None


class TokenData(BaseModel):
    """JWT token data model."""
    
    user_id: str
    email: str
    exp: datetime


class AuthResponse(BaseModel):
    """Authentication response model."""
    
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserProfile


class LogoutResponse(BaseModel):
    """Logout response model."""
    
    message: str = "Successfully logged out"


class PasswordResetResponse(BaseModel):
    """Password reset response model."""
    
    message: str = "Password reset email sent"


class LoginResponse(BaseModel):
    """Login response model."""
    
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserProfile


class RefreshTokenResponse(BaseModel):
    """Refresh token response model."""
    
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserProfileResponse(BaseModel):
    """User profile response model."""
    
    user: UserProfile


class UpdateProfileRequest(BaseModel):
    """Update profile request model."""
    
    email: Optional[str] = Field(None, description="New email address")