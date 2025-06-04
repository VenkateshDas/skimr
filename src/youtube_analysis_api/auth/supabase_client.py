"""Supabase client for authentication."""

import asyncio
from typing import Dict, Optional, Any
from functools import lru_cache
import httpx

from ..config import get_supabase_config
from ..exceptions import AuthenticationError, SupabaseError


class SupabaseClient:
    """Async Supabase client for authentication operations."""
    
    def __init__(self):
        self.config = get_supabase_config()
        self.base_url = f"{self.config.url}/auth/v1"
        self.headers = {
            "apikey": self.config.anon_key,
            "Authorization": f"Bearer {self.config.anon_key}",
            "Content-Type": "application/json"
        }
    
    async def verify_token(self, token: str) -> Dict[str, Any]:
        """
        Verify JWT token with Supabase.
        
        Args:
            token: JWT token to verify
            
        Returns:
            User data from Supabase
            
        Raises:
            AuthenticationError: If token verification fails
            SupabaseError: If Supabase API error occurs
        """
        headers = self.headers.copy()
        headers["Authorization"] = f"Bearer {token}"
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/user",
                    headers=headers,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 401:
                    raise AuthenticationError("Invalid or expired token")
                else:
                    raise SupabaseError(f"Supabase API error: {response.status_code}")
                    
            except httpx.TimeoutException:
                raise SupabaseError("Supabase API timeout")
            except httpx.RequestError as e:
                raise SupabaseError(f"Supabase API request failed: {str(e)}")
    
    async def get_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user profile from Supabase.
        
        Args:
            user_id: User ID
            
        Returns:
            User profile data if found, None otherwise
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.config.url}/rest/v1/profiles",
                    headers=self.headers,
                    params={"id": f"eq.{user_id}"},
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return data[0] if data else None
                else:
                    return None
                    
            except Exception:
                return None
    
    async def update_user_profile(self, user_id: str, profile_data: Dict[str, Any]) -> bool:
        """
        Update user profile in Supabase.
        
        Args:
            user_id: User ID
            profile_data: Profile data to update
            
        Returns:
            True if successful, False otherwise
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.patch(
                    f"{self.config.url}/rest/v1/profiles",
                    headers=self.headers,
                    params={"id": f"eq.{user_id}"},
                    json=profile_data,
                    timeout=10.0
                )
                
                return response.status_code in [200, 204]
                
            except Exception:
                return False
    
    async def check_user_exists(self, user_id: str) -> bool:
        """
        Check if user exists in Supabase.
        
        Args:
            user_id: User ID to check
            
        Returns:
            True if user exists, False otherwise
        """
        profile = await self.get_user_profile(user_id)
        return profile is not None
    
    async def get_user_metadata(self, user_id: str) -> Dict[str, Any]:
        """
        Get user metadata from Supabase.
        
        Args:
            user_id: User ID
            
        Returns:
            User metadata
        """
        profile = await self.get_user_profile(user_id)
        if profile:
            return profile.get("metadata", {})
        return {}


@lru_cache(maxsize=1)
def get_supabase_client() -> SupabaseClient:
    """Get cached Supabase client instance."""
    return SupabaseClient()


# Async helper functions
async def verify_supabase_token(token: str) -> Dict[str, Any]:
    """Verify token with Supabase."""
    client = get_supabase_client()
    return await client.verify_token(token)


async def get_user_from_supabase(user_id: str) -> Optional[Dict[str, Any]]:
    """Get user profile from Supabase."""
    client = get_supabase_client()
    return await client.get_user_profile(user_id)


class SupabaseAuthClient:
    """Supabase authentication client for user management operations."""
    
    def __init__(self, client=None):
        if client:
            # For testing with mock client
            self.client = client
            self.config = get_supabase_config()
            self.base_url = f"{self.config.url}/auth/v1"
            self.headers = {
                "apikey": self.config.anon_key,
                "Authorization": f"Bearer {self.config.anon_key}",
                "Content-Type": "application/json"
            }
        else:
            # For production use
            self.client = None
            self.config = get_supabase_config()
            self.base_url = f"{self.config.url}/auth/v1"
            self.headers = {
                "apikey": self.config.anon_key,
                "Authorization": f"Bearer {self.config.anon_key}",
                "Content-Type": "application/json"
            }
    
    async def sign_up(self, email: str, password: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Sign up a new user."""
        if self.client:
            # Use mock client for testing
            try:
                result = self.client.auth.sign_up(email=email, password=password, options={"data": metadata} if metadata else None)
                return {
                    "user": {
                        "id": result.user.id,
                        "email": result.user.email,
                        "created_at": result.user.created_at,
                        "email_confirmed_at": result.user.email_confirmed_at
                    },
                    "session": {
                        "access_token": result.session.access_token,
                        "refresh_token": result.session.refresh_token,
                        "expires_in": result.session.expires_in
                    }
                }
            except Exception as e:
                raise SupabaseError(f"Sign up failed: {str(e)}")
        
        payload = {
            "email": email,
            "password": password
        }
        if metadata:
            payload["data"] = metadata
            
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/signup",
                    headers=self.headers,
                    json=payload,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    raise SupabaseError(f"Sign up failed: {response.status_code}")
                    
            except httpx.RequestError as e:
                raise SupabaseError(f"Sign up request failed: {str(e)}")
    
    async def sign_in(self, email: str, password: str) -> Dict[str, Any]:
        """Sign in an existing user."""
        if self.client:
            # Use mock client for testing
            try:
                result = self.client.auth.sign_in_with_password(email=email, password=password)
                return {
                    "user": {
                        "id": result.user.id,
                        "email": result.user.email,
                        "created_at": result.user.created_at,
                        "email_confirmed_at": result.user.email_confirmed_at,
                        "last_sign_in_at": result.user.last_sign_in_at
                    },
                    "session": {
                        "access_token": result.session.access_token,
                        "refresh_token": result.session.refresh_token,
                        "expires_in": result.session.expires_in
                    }
                }
            except Exception as e:
                if "Invalid" in str(e):
                    raise AuthenticationError("Invalid email or password")
                raise SupabaseError(f"Sign in failed: {str(e)}")
        
        payload = {
            "email": email,
            "password": password
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/token?grant_type=password",
                    headers=self.headers,
                    json=payload,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 400:
                    raise AuthenticationError("Invalid email or password")
                else:
                    raise SupabaseError(f"Sign in failed: {response.status_code}")
                    
            except httpx.RequestError as e:
                raise SupabaseError(f"Sign in request failed: {str(e)}")
    
    async def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh an access token."""
        if self.client:
            # Use mock client for testing
            try:
                result = self.client.auth.refresh_session(refresh_token=refresh_token)
                return {
                    "session": {
                        "access_token": result.session.access_token,
                        "refresh_token": result.session.refresh_token,
                        "expires_in": result.session.expires_in
                    },
                    "user": {
                        "id": result.user.id
                    }
                }
            except Exception as e:
                if "Invalid" in str(e):
                    raise AuthenticationError("Invalid refresh token")
                raise SupabaseError(f"Token refresh failed: {str(e)}")
        
        payload = {
            "refresh_token": refresh_token
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/token?grant_type=refresh_token",
                    headers=self.headers,
                    json=payload,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 401:
                    raise AuthenticationError("Invalid refresh token")
                else:
                    raise SupabaseError(f"Token refresh failed: {response.status_code}")
                    
            except httpx.RequestError as e:
                raise SupabaseError(f"Token refresh request failed: {str(e)}")
    
    async def sign_out(self, access_token: str) -> bool:
        """Sign out a user."""
        if self.client:
            # Use mock client for testing
            try:
                self.client.auth.sign_out()
                return True
            except Exception as e:
                if "Sign out failed" in str(e):
                    raise SupabaseError("Sign out failed")
                return False
        
        headers = self.headers.copy()
        headers["Authorization"] = f"Bearer {access_token}"
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/logout",
                    headers=headers,
                    timeout=10.0
                )
                
                return response.status_code == 204
                
            except httpx.RequestError:
                return False
    
    async def get_user(self, access_token: str) -> Dict[str, Any]:
        """Get current user information."""
        if self.client:
            # Use mock client for testing
            try:
                result = self.client.auth.get_user(access_token)
                return {
                    "user": {
                        "id": result.user.id,
                        "email": result.user.email,
                        "created_at": result.user.created_at,
                        "email_confirmed_at": result.user.email_confirmed_at,
                        "last_sign_in_at": result.user.last_sign_in_at
                    }
                }
            except Exception as e:
                if "Invalid" in str(e):
                    raise AuthenticationError("Invalid token")
                raise SupabaseError(f"Get user failed: {str(e)}")
        
        headers = self.headers.copy()
        headers["Authorization"] = f"Bearer {access_token}"
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/user",
                    headers=headers,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 401:
                    raise AuthenticationError("Invalid or expired token")
                else:
                    raise SupabaseError(f"Get user failed: {response.status_code}")
                    
            except httpx.RequestError as e:
                raise SupabaseError(f"Get user request failed: {str(e)}")
    
    async def verify_token(self, access_token: str) -> Dict[str, Any]:
        """Verify an access token."""
        if self.client:
            # Use mock client for testing
            try:
                result = self.client.auth.get_user(access_token)
                return {
                    "user": {
                        "id": result.user.id,
                        "email": result.user.email
                    }
                }
            except Exception as e:
                if "Invalid" in str(e):
                    raise AuthenticationError("Invalid token")
                raise SupabaseError(f"Token verification failed: {str(e)}")
        
        return await self.get_user(access_token)


@lru_cache(maxsize=1)
def get_supabase_auth_client() -> SupabaseAuthClient:
    """Get cached Supabase auth client instance."""
    return SupabaseAuthClient()


def get_api_config():
    """Get API configuration for testing."""
    return get_supabase_config()


def create_client(url: str, key: str):
    """Create a Supabase client for testing."""
    # This is a mock implementation for testing
    class MockClient:
        def __init__(self, url, key):
            self.url = url
            self.key = key
    
    return MockClient(url, key)