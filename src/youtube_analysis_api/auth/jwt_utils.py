"""JWT token utilities for authentication."""

import jwt
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
from functools import lru_cache

from ..config import get_api_config
from ..exceptions import AuthenticationError, TokenExpiredError, InvalidTokenError


@lru_cache(maxsize=1)
def get_jwt_config() -> Dict[str, Any]:
    """Get JWT configuration."""
    config = get_api_config()
    return {
        "secret_key": config.jwt_secret_key,
        "algorithm": config.jwt_algorithm,
        "access_token_expire_minutes": config.jwt_access_token_expire_minutes,
        "refresh_token_expire_days": config.jwt_refresh_token_expire_days
    }


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Create JWT access token.
    
    Args:
        data: Token payload data
        expires_delta: Custom expiration time
        
    Returns:
        Encoded JWT token
    """
    jwt_config = get_jwt_config()
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=jwt_config["access_token_expire_minutes"]
        )
    
    to_encode.update({"exp": expire, "type": "access"})
    
    return jwt.encode(
        to_encode, 
        jwt_config["secret_key"], 
        algorithm=jwt_config["algorithm"]
    )


def create_refresh_token(data: Dict[str, Any]) -> str:
    """
    Create JWT refresh token.
    
    Args:
        data: Token payload data
        
    Returns:
        Encoded JWT refresh token
    """
    jwt_config = get_jwt_config()
    to_encode = data.copy()
    
    expire = datetime.utcnow() + timedelta(days=jwt_config["refresh_token_expire_days"])
    to_encode.update({"exp": expire, "type": "refresh"})
    
    return jwt.encode(
        to_encode,
        jwt_config["secret_key"],
        algorithm=jwt_config["algorithm"]
    )


def verify_token(token: str, token_type: str = "access") -> Dict[str, Any]:
    """
    Verify and decode JWT token.
    
    Args:
        token: JWT token to verify
        token_type: Expected token type (access/refresh)
        
    Returns:
        Decoded token payload
        
    Raises:
        AuthenticationError: If token is invalid
        TokenExpiredError: If token is expired
        InvalidTokenError: If token format is invalid
    """
    jwt_config = get_jwt_config()
    
    try:
        payload = jwt.decode(
            token,
            jwt_config["secret_key"],
            algorithms=[jwt_config["algorithm"]]
        )
        
        # Verify token type
        if payload.get("type") != token_type:
            raise InvalidTokenError(f"Invalid token type. Expected {token_type}")
        
        return payload
        
    except jwt.ExpiredSignatureError:
        raise TokenExpiredError("Token has expired")
    except jwt.InvalidTokenError as e:
        raise InvalidTokenError(f"Invalid token: {str(e)}")
    except Exception as e:
        raise AuthenticationError(f"Token verification failed: {str(e)}")


def extract_user_id(token: str) -> str:
    """
    Extract user ID from JWT token.
    
    Args:
        token: JWT token
        
    Returns:
        User ID from token
        
    Raises:
        AuthenticationError: If user ID not found in token
    """
    payload = verify_token(token)
    user_id = payload.get("sub")
    
    if not user_id:
        raise AuthenticationError("User ID not found in token")
    
    return user_id


def extract_user_email(token: str) -> Optional[str]:
    """
    Extract user email from JWT token.
    
    Args:
        token: JWT token
        
    Returns:
        User email from token if present
    """
    try:
        payload = verify_token(token)
        return payload.get("email")
    except Exception:
        return None


def is_token_expired(token: str) -> bool:
    """
    Check if token is expired without raising exception.
    
    Args:
        token: JWT token to check
        
    Returns:
        True if token is expired, False otherwise
    """
    try:
        verify_token(token)
        return False
    except TokenExpiredError:
        return True
    except Exception:
        return True


def get_token_expiry(token: str) -> Optional[datetime]:
    """
    Get token expiration time.
    
    Args:
        token: JWT token
        
    Returns:
        Token expiration datetime if valid, None otherwise
    """
    try:
        payload = verify_token(token)
        exp_timestamp = payload.get("exp")
        if exp_timestamp:
            return datetime.fromtimestamp(exp_timestamp)
        return None
    except Exception:
        return None