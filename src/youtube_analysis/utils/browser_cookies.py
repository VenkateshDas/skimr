"""
Browser Cookie Extraction Utility for YouTube Analysis

This module provides utilities to extract cookies from popular browsers
and convert them to Netscape format for use with yt-dlp.
"""

import os
import sqlite3
import json
import base64
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
import tempfile
import shutil
import platform

from .logging import get_logger

logger = get_logger("browser_cookies")


class BrowserCookieExtractor:
    """Extract cookies from popular browsers for YouTube authentication."""
    
    def __init__(self):
        self.system = platform.system().lower()
        
    def extract_youtube_cookies(self, browser: str = "auto") -> Optional[str]:
        """
        Extract YouTube cookies from browser and return path to Netscape cookies.txt file.
        
        Args:
            browser: Browser to extract from ('chrome', 'firefox', 'safari', 'edge', 'auto')
            
        Returns:
            Path to generated cookies.txt file, or None if extraction failed
        """
        if browser == "auto":
            # Try browsers in order of preference
            for browser_name in ["chrome", "firefox", "safari", "edge"]:
                try:
                    result = self._extract_from_browser(browser_name)
                    if result:
                        return result
                except Exception as e:
                    logger.debug(f"Failed to extract from {browser_name}: {e}")
                    continue
            return None
        else:
            return self._extract_from_browser(browser)
    
    def _extract_from_browser(self, browser: str) -> Optional[str]:
        """Extract cookies from specific browser."""
        method_map = {
            "chrome": self._extract_chrome_cookies,
            "firefox": self._extract_firefox_cookies,
            "safari": self._extract_safari_cookies,
            "edge": self._extract_edge_cookies,
        }
        
        if browser not in method_map:
            raise ValueError(f"Unsupported browser: {browser}")
            
        return method_map[browser]()
    
    def _get_chrome_cookie_path(self) -> Optional[Path]:
        """Get Chrome cookie database path for current OS."""
        if self.system == "windows":
            base = Path.home() / "AppData/Local/Google/Chrome/User Data/Default"
        elif self.system == "darwin":  # macOS
            base = Path.home() / "Library/Application Support/Google/Chrome/Default"
        elif self.system == "linux":
            base = Path.home() / ".config/google-chrome/Default"
        else:
            return None
            
        cookie_path = base / "Cookies"
        return cookie_path if cookie_path.exists() else None
    
    def _get_firefox_cookie_path(self) -> Optional[Path]:
        """Get Firefox cookie database path for current OS."""
        if self.system == "windows":
            base = Path.home() / "AppData/Roaming/Mozilla/Firefox/Profiles"
        elif self.system == "darwin":  # macOS
            base = Path.home() / "Library/Application Support/Firefox/Profiles"
        elif self.system == "linux":
            base = Path.home() / ".mozilla/firefox"
        else:
            return None
            
        if not base.exists():
            return None
            
        # Find the default profile
        for profile_dir in base.iterdir():
            if profile_dir.is_dir() and "default" in profile_dir.name.lower():
                cookie_path = profile_dir / "cookies.sqlite"
                if cookie_path.exists():
                    return cookie_path
        return None
    
    def _extract_chrome_cookies(self) -> Optional[str]:
        """Extract YouTube cookies from Chrome."""
        cookie_path = self._get_chrome_cookie_path()
        if not cookie_path:
            logger.warning("Chrome cookie database not found")
            return None
            
        try:
            # Create temporary copy to avoid locking issues
            temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
            shutil.copy2(cookie_path, temp_db.name)
            temp_db.close()
            
            # Connect to the database
            conn = sqlite3.connect(temp_db.name)
            cursor = conn.cursor()
            
            # Query YouTube cookies
            query = """
            SELECT name, value, host_key, path, expires_utc, is_secure, is_httponly
            FROM cookies 
            WHERE host_key LIKE '%youtube.com%' OR host_key LIKE '%.google.com%'
            """
            
            cursor.execute(query)
            cookies = cursor.fetchall()
            conn.close()
            
            # Clean up temp file
            os.unlink(temp_db.name)
            
            if not cookies:
                logger.warning("No YouTube cookies found in Chrome")
                return None
                
            # Convert to Netscape format
            return self._convert_to_netscape_format(cookies, "chrome")
            
        except Exception as e:
            logger.error(f"Failed to extract Chrome cookies: {e}")
            return None
    
    def _extract_firefox_cookies(self) -> Optional[str]:
        """Extract YouTube cookies from Firefox."""
        cookie_path = self._get_firefox_cookie_path()
        if not cookie_path:
            logger.warning("Firefox cookie database not found")
            return None
            
        try:
            # Create temporary copy
            temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
            shutil.copy2(cookie_path, temp_db.name)
            temp_db.close()
            
            # Connect to the database
            conn = sqlite3.connect(temp_db.name)
            cursor = conn.cursor()
            
            # Query YouTube cookies
            query = """
            SELECT name, value, host, path, expiry, isSecure, isHttpOnly
            FROM moz_cookies 
            WHERE host LIKE '%youtube.com%' OR host LIKE '%.google.com%'
            """
            
            cursor.execute(query)
            cookies = cursor.fetchall()
            conn.close()
            
            # Clean up temp file
            os.unlink(temp_db.name)
            
            if not cookies:
                logger.warning("No YouTube cookies found in Firefox")
                return None
                
            # Convert to Netscape format
            return self._convert_to_netscape_format(cookies, "firefox")
            
        except Exception as e:
            logger.error(f"Failed to extract Firefox cookies: {e}")
            return None
    
    def _extract_safari_cookies(self) -> Optional[str]:
        """Extract YouTube cookies from Safari (macOS only)."""
        if self.system != "darwin":
            logger.warning("Safari extraction only supported on macOS")
            return None
            
        cookie_path = Path.home() / "Library/Cookies/Cookies.binarycookies"
        if not cookie_path.exists():
            logger.warning("Safari cookie file not found")
            return None
            
        logger.warning("Safari cookie extraction requires additional implementation")
        # Safari uses a binary format that requires special parsing
        # For now, recommend using Chrome or Firefox
        return None
    
    def _extract_edge_cookies(self) -> Optional[str]:
        """Extract YouTube cookies from Microsoft Edge."""
        if self.system == "windows":
            base = Path.home() / "AppData/Local/Microsoft/Edge/User Data/Default"
        elif self.system == "darwin":  # macOS
            base = Path.home() / "Library/Application Support/Microsoft Edge/Default"
        elif self.system == "linux":
            base = Path.home() / ".config/microsoft-edge/Default"
        else:
            return None
            
        cookie_path = base / "Cookies"
        if not cookie_path.exists():
            logger.warning("Edge cookie database not found")
            return None
            
        # Edge uses the same format as Chrome
        try:
            # Create temporary copy
            temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
            shutil.copy2(cookie_path, temp_db.name)
            temp_db.close()
            
            # Connect to the database
            conn = sqlite3.connect(temp_db.name)
            cursor = conn.cursor()
            
            # Query YouTube cookies
            query = """
            SELECT name, value, host_key, path, expires_utc, is_secure, is_httponly
            FROM cookies 
            WHERE host_key LIKE '%youtube.com%' OR host_key LIKE '%.google.com%'
            """
            
            cursor.execute(query)
            cookies = cursor.fetchall()
            conn.close()
            
            # Clean up temp file
            os.unlink(temp_db.name)
            
            if not cookies:
                logger.warning("No YouTube cookies found in Edge")
                return None
                
            # Convert to Netscape format
            return self._convert_to_netscape_format(cookies, "edge")
            
        except Exception as e:
            logger.error(f"Failed to extract Edge cookies: {e}")
            return None
    
    def _convert_to_netscape_format(self, cookies: List[tuple], browser: str) -> str:
        """Convert browser cookies to Netscape format."""
        try:
            # Create temporary cookies.txt file
            temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
            
            # Write Netscape header
            temp_file.write("# Netscape HTTP Cookie File\n")
            temp_file.write("# This is a generated file! Do not edit.\n\n")
            
            for cookie in cookies:
                if browser in ["chrome", "edge"]:
                    name, value, host_key, path, expires_utc, is_secure, is_httponly = cookie
                    # Convert Chrome timestamp (microseconds since Windows epoch) to Unix timestamp
                    if expires_utc:
                        expires = int(expires_utc / 1000000 - 11644473600)  # Convert to Unix timestamp
                    else:
                        expires = 0
                elif browser == "firefox":
                    name, value, host_key, path, expires, is_secure, is_httponly = cookie
                    expires = expires or 0
                else:
                    continue
                
                # Clean up host_key
                domain = host_key.lstrip('.')
                domain_flag = "TRUE" if host_key.startswith('.') else "FALSE"
                
                # Format: domain, domain_flag, path, secure, expires, name, value
                secure_flag = "TRUE" if is_secure else "FALSE"
                
                line = f"{domain}\t{domain_flag}\t{path}\t{secure_flag}\t{expires}\t{name}\t{value}\n"
                temp_file.write(line)
            
            temp_file.close()
            logger.info(f"Generated cookies.txt file: {temp_file.name}")
            return temp_file.name
            
        except Exception as e:
            logger.error(f"Failed to convert cookies to Netscape format: {e}")
            return None


def setup_browser_cookies(browser: str = "auto") -> bool:
    """
    Extract browser cookies and configure environment for yt-dlp.
    
    Args:
        browser: Browser to extract from ('chrome', 'firefox', 'safari', 'edge', 'auto')
        
    Returns:
        True if cookies were successfully extracted and configured
    """
    extractor = BrowserCookieExtractor()
    cookies_file = extractor.extract_youtube_cookies(browser)
    
    if cookies_file:
        # Set environment variable for yt-dlp
        os.environ["YTDLP_COOKIES_FILE"] = cookies_file
        logger.info(f"Browser cookies configured for yt-dlp: {cookies_file}")
        return True
    else:
        logger.warning("Failed to extract browser cookies")
        return False


def enable_browser_cookies_flag():
    """
    Enable browser cookie extraction with a simple flag.
    This is the main function users should call to enable browser cookies.
    """
    try:
        # Check if cookies are already configured
        if os.getenv("YTDLP_COOKIES_FILE") or os.getenv("YTDLP_COOKIES") or os.getenv("YTDLP_COOKIES_BASE64"):
            logger.info("Cookies already configured via environment variables")
            return True
            
        # Try to extract from browser
        success = setup_browser_cookies()
        if success:
            logger.info("✅ Browser cookies enabled successfully!")
            print("🍪 Browser cookies have been extracted and configured for YouTube access.")
            print("   This helps bypass 'Sign in to confirm you're not a bot' messages.")
            return True
        else:
            logger.warning("❌ Failed to extract browser cookies")
            print("⚠️  Could not extract browser cookies. Please ensure:")
            print("   - You're logged into YouTube in your browser")
            print("   - Your browser is closed (to release cookie database locks)")
            print("   - You have Chrome, Firefox, or Edge installed")
            return False
            
    except Exception as e:
        logger.error(f"Error enabling browser cookies: {e}")
        print(f"❌ Error: {e}")
        return False