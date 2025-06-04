"""Authentication module for the YouTube Analysis API."""

from .jwt_utils import (
    create_access_token,
    create_refresh_token,
    verify_token,
    extract_user_id,
    extract_user_email,
    is_token_expired,
    get_token_expiry
)
from .supabase_client import (
    SupabaseClient,
    get_supabase_client,
    verify_supabase_token,
    get_user_from_supabase
)

__all__ = [
    "create_access_token",
    "create_refresh_token", 
    "verify_token",
    "extract_user_id",
    "extract_user_email",
    "is_token_expired",
    "get_token_expiry",
    "SupabaseClient",
    "get_supabase_client",
    "verify_supabase_token",
    "get_user_from_supabase"
]