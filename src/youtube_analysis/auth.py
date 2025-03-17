"""Authentication module for the YouTube Analyzer app."""

import os
from typing import Optional, Tuple, Any
import streamlit as st
from supabase import create_client, Client
from functools import wraps
from .utils.logging import get_logger

logger = get_logger(__name__)

def init_supabase() -> Client:
    """
    Initialize Supabase client.
    
    Returns:
        Supabase client instance
    """
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    
    if not supabase_url or not supabase_key:
        raise ValueError("Supabase URL and key must be set in environment variables")
    
    return create_client(supabase_url, supabase_key)

def init_auth_state():
    """Initialize authentication state in session."""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "user" not in st.session_state:
        st.session_state.user = None
    if "show_auth" not in st.session_state:
        st.session_state.show_auth = False

def login(email: str, password: str) -> Tuple[bool, Optional[str]]:
    """
    Log in a user with email and password.
    
    Args:
        email: User's email
        password: User's password
    
    Returns:
        Tuple of (success, error_message)
    """
    try:
        supabase = init_supabase()
        auth_response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        
        # Store user data in session state
        st.session_state.authenticated = True
        st.session_state.user = auth_response.user
        st.session_state.show_auth = False
        
        logger.info(f"User {email} logged in successfully")
        return True, None
    
    except Exception as e:
        logger.error(f"Login failed for {email}: {str(e)}")
        return False, str(e)

def signup(email: str, password: str) -> Tuple[bool, Optional[str]]:
    """
    Sign up a new user.
    
    Args:
        email: User's email
        password: User's password
    
    Returns:
        Tuple of (success, error_message)
    """
    try:
        supabase = init_supabase()
        auth_response = supabase.auth.sign_up({
            "email": email,
            "password": password
        })
        
        logger.info(f"User {email} signed up successfully")
        return True, None
    
    except Exception as e:
        logger.error(f"Signup failed for {email}: {str(e)}")
        return False, str(e)

def logout():
    """Log out the current user."""
    try:
        supabase = init_supabase()
        supabase.auth.sign_out()
        
        # Clear session state
        st.session_state.authenticated = False
        st.session_state.user = None
        st.session_state.show_auth = False
        
        logger.info("User logged out successfully")
        return True
    
    except Exception as e:
        logger.error(f"Logout failed: {str(e)}")
        return False

def get_current_user() -> Optional[Any]:
    """
    Get the current authenticated user.
    
    Returns:
        User object or None if not authenticated
    """
    return st.session_state.user if st.session_state.authenticated else None

def require_auth(func):
    """
    Decorator to require authentication for a function.
    
    Args:
        func: Function to wrap
    
    Returns:
        Wrapped function that checks for authentication
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not st.session_state.authenticated:
            st.warning("Please log in to access this feature.")
            st.session_state.show_auth = True
            return None
        return func(*args, **kwargs)
    return wrapper

def display_auth_ui():
    """Display the authentication UI components."""
    # Create tabs for login and signup
    tab1, tab2 = st.tabs(["Login", "Sign Up"])
    
    with tab1:
        st.markdown("### Login")
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        
        if st.button("Login", key="login_button"):
            success, error = login(email, password)
            if success:
                st.success("Logged in successfully!")
                st.rerun()
            else:
                st.error(f"Login failed: {error}")
    
    with tab2:
        st.markdown("### Sign Up")
        email = st.text_input("Email", key="signup_email")
        password = st.text_input("Password", type="password", key="signup_password")
        confirm_password = st.text_input("Confirm Password", type="password", key="signup_confirm_password")
        
        if st.button("Sign Up", key="signup_button"):
            if password != confirm_password:
                st.error("Passwords do not match!")
            else:
                success, error = signup(email, password)
                if success:
                    st.success("Signed up successfully! Please check your email for verification.")
                else:
                    st.error(f"Signup failed: {error}") 