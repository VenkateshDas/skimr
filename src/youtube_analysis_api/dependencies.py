"""FastAPI dependencies for authentication and service injection."""

from typing import Optional, Dict, Any
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .auth import verify_token, extract_user_id, verify_supabase_token
from .exceptions import AuthenticationError, TokenExpiredError, InvalidTokenError
from .config import get_api_config


# Security scheme for JWT tokens
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Dict[str, Any]:
    """
    Get current authenticated user from JWT token.
    
    Args:
        credentials: HTTP authorization credentials
        
    Returns:
        User information dictionary
        
    Raises:
        HTTPException: If authentication fails
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        # Verify JWT token
        payload = verify_token(credentials.credentials)
        user_id = payload.get("sub")
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: user ID not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Verify with Supabase
        user_data = await verify_supabase_token(credentials.credentials)
        
        return {
            "user_id": user_id,
            "email": user_data.get("email"),
            "user_metadata": user_data.get("user_metadata", {}),
            "app_metadata": user_data.get("app_metadata", {}),
            "token": credentials.credentials
        }
        
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service error"
        )


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[Dict[str, Any]]:
    """
    Get current user if authenticated, None otherwise.
    
    Args:
        credentials: HTTP authorization credentials
        
    Returns:
        User information dictionary if authenticated, None otherwise
    """
    if not credentials:
        return None
    
    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None


def get_user_id(current_user: Dict[str, Any] = Depends(get_current_user)) -> str:
    """
    Extract user ID from current user.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        User ID
    """
    return current_user["user_id"]


def get_user_email(current_user: Dict[str, Any] = Depends(get_current_user)) -> Optional[str]:
    """
    Extract user email from current user.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        User email if available
    """
    return current_user.get("email")


async def check_guest_limits(
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user)
) -> Dict[str, Any]:
    """
    Check guest user limits and return user context.
    
    Args:
        current_user: Current user if authenticated
        
    Returns:
        User context with guest status and limits
    """
    config = get_api_config()
    
    if current_user:
        return {
            "is_guest": False,
            "user_id": current_user["user_id"],
            "email": current_user.get("email"),
            "daily_limit": None,  # No limit for authenticated users
            "remaining_requests": None
        }
    else:
        return {
            "is_guest": True,
            "user_id": None,
            "email": None,
            "daily_limit": config.guest_daily_limit,
            "remaining_requests": config.guest_daily_limit  # TODO: Implement actual tracking
        }


def require_authentication(
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Require authentication - raises 401 if not authenticated.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        Current user information
    """
    return current_user


def get_service_factory():
    """
    Get service factory instance.
    
    Returns:
        ServiceFactory instance
    """
    # Import here to avoid circular imports
    from src.services.service_factory import ServiceFactory
    return ServiceFactory()


def get_web_app_adapter(service_factory = Depends(get_service_factory)):
    """
    Get WebAppAdapter instance.
    
    Args:
        service_factory: ServiceFactory instance
        
    Returns:
        WebAppAdapter instance
    """
    return service_factory.get_web_app_adapter()