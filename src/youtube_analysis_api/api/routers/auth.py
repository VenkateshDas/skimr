"""Authentication router."""

from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer

from ...api.models.auth import (
    LoginRequest,
    LoginResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
    UserProfileResponse,
    UpdateProfileRequest
)
from ...api.models.base import SuccessResponse
from ...dependencies import get_current_user, get_user_id
from ...auth import (
    create_access_token,
    create_refresh_token,
    verify_token,
    verify_supabase_token,
    get_user_from_supabase
)
from ...exceptions import AuthenticationError, InvalidTokenError

router = APIRouter()
security = HTTPBearer()


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """
    Login with Supabase token.
    
    Args:
        request: Login request with Supabase token
        
    Returns:
        JWT tokens and user information
        
    Raises:
        HTTPException: If authentication fails
    """
    try:
        # Verify Supabase token
        user_data = await verify_supabase_token(request.supabase_token)
        user_id = user_data.get("id")
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Supabase token: user ID not found"
            )
        
        # Create JWT tokens
        token_data = {
            "sub": user_id,
            "email": user_data.get("email"),
            "aud": user_data.get("aud", "authenticated")
        }
        
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token({"sub": user_id})
        
        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            user=UserProfileResponse(
                id=user_id,
                email=user_data.get("email"),
                full_name=user_data.get("user_metadata", {}).get("full_name"),
                avatar_url=user_data.get("user_metadata", {}).get("avatar_url"),
                created_at=user_data.get("created_at"),
                updated_at=user_data.get("updated_at")
            )
        )
        
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service error"
        )


@router.post("/refresh", response_model=RefreshTokenResponse)
async def refresh_token(request: RefreshTokenRequest):
    """
    Refresh access token using refresh token.
    
    Args:
        request: Refresh token request
        
    Returns:
        New access token
        
    Raises:
        HTTPException: If refresh fails
    """
    try:
        # Verify refresh token
        payload = verify_token(request.refresh_token, token_type="refresh")
        user_id = payload.get("sub")
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token: user ID not found"
            )
        
        # Get user data from Supabase
        user_data = await get_user_from_supabase(user_id)
        if not user_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        # Create new access token
        token_data = {
            "sub": user_id,
            "email": user_data.get("email"),
            "aud": "authenticated"
        }
        
        access_token = create_access_token(token_data)
        
        return RefreshTokenResponse(
            access_token=access_token,
            token_type="bearer"
        )
        
    except InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid refresh token: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh service error"
        )


@router.get("/profile", response_model=UserProfileResponse)
async def get_profile(current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Get current user profile.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        User profile information
    """
    try:
        user_id = current_user["user_id"]
        user_data = await get_user_from_supabase(user_id)
        
        if not user_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User profile not found"
            )
        
        return UserProfileResponse(
            id=user_id,
            email=user_data.get("email"),
            full_name=user_data.get("user_metadata", {}).get("full_name"),
            avatar_url=user_data.get("user_metadata", {}).get("avatar_url"),
            created_at=user_data.get("created_at"),
            updated_at=user_data.get("updated_at")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Profile service error"
        )


@router.put("/profile", response_model=SuccessResponse)
async def update_profile(
    request: UpdateProfileRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Update user profile.
    
    Args:
        request: Profile update request
        current_user: Current authenticated user
        
    Returns:
        Success response
    """
    try:
        # TODO: Implement profile update with Supabase
        # This would require updating the user_metadata in Supabase
        
        return SuccessResponse(
            message="Profile update not yet implemented",
            data={"user_id": current_user["user_id"]}
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Profile update service error"
        )


@router.post("/logout", response_model=SuccessResponse)
async def logout(current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Logout user (invalidate token).
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        Success response
    """
    try:
        # TODO: Implement token blacklisting if needed
        # For now, just return success (client should discard tokens)
        
        return SuccessResponse(
            message="Logged out successfully",
            data={"user_id": current_user["user_id"]}
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout service error"
        )