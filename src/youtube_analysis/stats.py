"""Statistics tracking module for the YouTube Analyzer app."""

from typing import Optional, Dict, Any
import logging
from .auth import init_supabase, init_supabase_admin, get_current_user

logger = logging.getLogger(__name__)

def increment_summary_count(user_id: str) -> bool:
    """
    Increment the summary count for a user in Supabase.
    
    Args:
        user_id: The user ID to update the count for
        
    Returns:
        True if successful, False otherwise
    """
    try:
        logger.info(f"Starting to increment summary count for user {user_id}")
        
        # Use admin client to bypass Row Level Security
        supabase = init_supabase_admin()
        logger.info("Supabase admin client initialized")
        
        table_name = "user_summaries"  # Make sure this matches the name in setup_supabase_tables.sql
        
        # First, check if the user already has a record
        logger.info(f"Checking {table_name} table for user {user_id}")
        response = supabase.table(table_name).select("*").eq("user_id", user_id).execute()
        
        if response.data and len(response.data) > 0:
            # User exists, update the count
            current_count = response.data[0].get("summary_count", 0)
            new_count = current_count + 1
            
            logger.info(f"Updating summary count from {current_count} to {new_count}")
            
            # Update the record
            update_response = supabase.table(table_name).update({
                "summary_count": new_count,
                "last_updated": "now()"
            }).eq("user_id", user_id).execute()
            
            logger.info(f"Updated summary count for user {user_id} to {new_count}")
            return True
        else:
            # User doesn't exist, create a new record
            logger.info(f"No existing record found for user {user_id}, creating new record")
            
            insert_response = supabase.table(table_name).insert({
                "user_id": user_id,
                "summary_count": 1,
                "last_updated": "now()"
            }).execute()
            
            logger.info(f"Created new summary count record for user {user_id}")
            return True
    
    except Exception as e:
        logger.error(f"Error updating summary count for user {user_id}: {str(e)}")
        return False

def get_summary_count(user_id: Optional[str] = None) -> Optional[int]:
    """
    Get the current summary count for a user.
    
    Args:
        user_id: The user ID to get the count for, or None to use the current user
        
    Returns:
        The summary count or None if not found or error
    """
    try:
        # If no user_id provided, get the current user
        if user_id is None:
            user = get_current_user()
            if not user:
                logger.warning("No user logged in, cannot get summary count")
                return None
            user_id = user.id
        
        logger.info(f"Getting summary count for user {user_id}")
        
        table_name = "user_summaries"  # Make sure this matches the name in setup_supabase_tables.sql
        
        # For reading data, we can either use the admin client (if we want to read counts for all users)
        # or the regular client (if we only want to read the current user's count)
        # Using admin client to ensure consistent access
        supabase = init_supabase_admin()
        response = supabase.table(table_name).select("summary_count").eq("user_id", user_id).execute()
        
        if response.data and len(response.data) > 0:
            count = response.data[0].get("summary_count", 0)
            logger.info(f"Found summary count for user {user_id}: {count}")
            return count
        else:
            logger.info(f"No summary count record found for user {user_id}, returning 0")
            return 0
    
    except Exception as e:
        logger.error(f"Error getting summary count for user {user_id}: {str(e)}")
        return None

def get_user_stats() -> Optional[Dict[str, Any]]:
    """
    Get comprehensive stats for the current user.
    
    Returns:
        A dictionary of user stats or None if error
    """
    try:
        user = get_current_user()
        if not user:
            logger.warning("No user logged in, cannot get user stats")
            return None
        
        user_id = user.id
        
        # Get summary count
        summary_count = get_summary_count(user_id)
        
        # Build stats object
        stats = {
            "user_id": user_id,
            "summary_count": summary_count or 0,
            "email": user.email
        }
        
        return stats
    
    except Exception as e:
        logger.error(f"Error getting user stats: {str(e)}")
        return None 