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

def init_supabase_admin() -> Client:
    """
    Initialize Supabase client with service role key for admin operations.
    This bypasses Row Level Security and should only be used for internal operations.
    
    Returns:
        Supabase admin client instance
    """
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_service_key = os.getenv("SUPABASE_SERVICE_KEY")
    
    if not supabase_url:
        raise ValueError("Supabase URL must be set in environment variables")
    
    if not supabase_service_key:
        logger.warning("SUPABASE_SERVICE_KEY not found, falling back to regular key")
        return init_supabase()
    
    logger.info("Using service role key for admin operations")
    return create_client(supabase_url, supabase_service_key)

def init_auth_state():
    """Initialize authentication state in session."""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "user" not in st.session_state:
        st.session_state.user = None
    if "show_auth" not in st.session_state:
        # Don't show auth UI by default
        st.session_state.show_auth = False
    if "guest_analysis_count" not in st.session_state:
        st.session_state.guest_analysis_count = 0

def check_guest_usage(max_guest_analyses=1):
    """
    Check if a guest user has exceeded their free analysis limit.
    
    Args:
        max_guest_analyses: Maximum number of analyses allowed for guests
        
    Returns:
        bool: True if guest can continue, False if they need to log in
    """
    # If user is authenticated, always allow
    if st.session_state.authenticated:
        return True
        
    # Check if guest has exceeded their limit
    if st.session_state.guest_analysis_count >= max_guest_analyses:
        return False
        
    # Guest still has free analyses
    return True

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
        # Allow limited guest usage
        if check_guest_usage():
            return func(*args, **kwargs)
        # Guest has exceeded free limit
        st.warning("You've reached the limit of free analyses. Please log in to continue.")
        st.session_state.show_auth = True
        return None
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