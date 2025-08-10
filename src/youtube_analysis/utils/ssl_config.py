"""
SSL Configuration Helper for YouTube Analysis

This module provides SSL configuration utilities to handle certificate verification issues
that commonly occur in development environments or systems with corporate firewalls.
"""

import ssl
import os
import base64
import tempfile
from pathlib import Path
import certifi
import urllib3
from typing import Optional
from .logging import get_logger

logger = get_logger("ssl_config")


class SSLConfig:
    """SSL Configuration manager for handling certificate issues."""
    
    def __init__(self, verify_ssl: Optional[bool] = None):
        """
        Initialize SSL configuration.
        
        Args:
            verify_ssl: Whether to verify SSL certificates. If None, auto-detect based on environment.
        """
        self.verify_ssl = self._determine_ssl_verification(verify_ssl)
        self.ssl_context = None
        self._cookies_file_path: Optional[Path] = None
        self._setup_ssl_context()
        
    def _determine_ssl_verification(self, verify_ssl: Optional[bool]) -> bool:
        """Determine whether to verify SSL certificates."""
        if verify_ssl is not None:
            return verify_ssl
        
        # Check environment variables
        if os.getenv("YOUTUBE_ANALYSIS_DISABLE_SSL_VERIFY", "").lower() in ("1", "true", "yes"):
            logger.warning("SSL verification disabled via environment variable")
            return False
        
        # Check if we're in a development environment
        if os.getenv("ENVIRONMENT", "").lower() in ("dev", "development", "local"):
            logger.info("Development environment detected, allowing SSL bypass")
            return False
        
        # Default to secure behavior
        return True
    
    def _setup_ssl_context(self):
        """Setup SSL context based on configuration."""
        if self.verify_ssl:
            # Use default SSL context with certificate verification
            try:
                self.ssl_context = ssl.create_default_context()
                # Try to use certifi certificates if available
                self.ssl_context.load_verify_locations(certifi.where())
                logger.info("SSL context configured with certificate verification")
            except Exception as e:
                logger.warning(f"Failed to setup SSL context with certifi: {e}")
                self.ssl_context = ssl.create_default_context()
        else:
            # Create unverified SSL context for development
            self.ssl_context = ssl.create_default_context()
            self.ssl_context.check_hostname = False
            self.ssl_context.verify_mode = ssl.CERT_NONE
            
            # Disable urllib3 SSL warnings
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
            logger.warning("SSL verification disabled - use only in development!")
    
    def configure_environment(self):
        """Configure environment variables for SSL handling."""
        if not self.verify_ssl:
            # Set environment variables that various libraries check
            os.environ["PYTHONHTTPSVERIFY"] = "0"
            os.environ["CURL_CA_BUNDLE"] = ""
            os.environ["REQUESTS_CA_BUNDLE"] = ""
            
            # Additional aggressive SSL bypass environment variables
            # Note: Don't set SSL_VERIFY=false as it confuses httpx
            # os.environ["SSL_VERIFY"] = "false"  # This causes httpx to treat "false" as a file path
            
            # Only clear these if they exist to avoid confusion
            if "HTTPS_CA_BUNDLE" in os.environ:
                del os.environ["HTTPS_CA_BUNDLE"]
            if "SSL_CERT_FILE" in os.environ:
                del os.environ["SSL_CERT_FILE"] 
            if "SSL_CERT_DIR" in os.environ:
                del os.environ["SSL_CERT_DIR"]
            
            # Configure Python's SSL context globally
            try:
                import ssl as _ssl
                _ssl._create_default_https_context = _ssl._create_unverified_context
                logger.debug("Configured Python to use unverified SSL context globally")
            except Exception as e:
                logger.warning(f"Failed to configure global SSL context: {e}")
            
            logger.info("Environment configured for aggressive SSL bypass")
    
    def get_ssl_context(self) -> ssl.SSLContext:
        """Get the configured SSL context."""
        return self.ssl_context
    
    def get_urllib3_config(self) -> dict:
        """Get urllib3 configuration for requests."""
        if self.verify_ssl:
            return {"verify": True, "cert_reqs": "CERT_REQUIRED"}
        else:
            return {"verify": False, "cert_reqs": "CERT_NONE"}
    
    def configure_yt_dlp_options(self, ydl_opts: dict) -> dict:
        """Configure yt-dlp options for SSL handling."""
        if not self.verify_ssl:
            ydl_opts.update({
                "nocheckcertificate": True,
                "prefer_insecure": True,
                # Additional aggressive SSL bypass options
                "no_check_certificate": True,
                "insecure": True,
                # Delegate downloads to curl which supports --insecure (-k)
                "external_downloader": "curl",
                "external_downloader_args": {
                    "default": ["-k", "--retry", "3", "--retry-delay", "1"],
                },
                "extractor_args": {
                    "youtube": {
                        "skip": ["dash", "hls", "live_chat", "subtitles"],
                        "player_skip": ["js"],
                    }
                },
                # Force specific user agent that might work better
                "http_headers": {
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }
            })
            logger.debug("yt-dlp configured with aggressive SSL bypass options")
        
        # Apply proxy for yt-dlp if provided via env (kept here for reuse)
        try:
            proxy = os.getenv("YTDLP_PROXY") or os.getenv("YOUTUBE_PROXY_HTTPS") or os.getenv("YOUTUBE_PROXY_HTTP")
            if proxy:
                ydl_opts["proxy"] = proxy
        except Exception:
            pass
        
        return ydl_opts
    
    def configure_requests_session(self, session):
        """Configure requests session for SSL handling."""
        if not self.verify_ssl:
            session.verify = False
            logger.debug("Requests session configured to bypass SSL verification")
        return session

    def _ensure_cookies_file_from_env(self) -> Optional[Path]:
        """Create a cookies.txt file from environment variables if provided.

        Supported env vars:
        - YTDLP_COOKIES_FILE: Absolute path to an existing cookies.txt file
        - YTDLP_COOKIES: Raw Netscape cookies.txt content
        - YTDLP_COOKIES_BASE64: Base64-encoded Netscape cookies.txt content
        """
        # If we've already materialized a cookies file, reuse it
        if self._cookies_file_path and self._cookies_file_path.exists():
            return self._cookies_file_path

        # Direct file path provided
        file_path = os.getenv("YTDLP_COOKIES_FILE")
        if file_path:
            p = Path(file_path)
            if p.exists():
                self._cookies_file_path = p
                logger.info(f"Using yt-dlp cookies file from YTDLP_COOKIES_FILE: {p}")
                return p
            logger.warning(f"YTDLP_COOKIES_FILE set but file not found: {p}")

        # Raw cookies content
        raw = os.getenv("YTDLP_COOKIES")
        b64 = os.getenv("YTDLP_COOKIES_BASE64")
        content: Optional[bytes] = None
        if raw:
            content = raw.encode("utf-8")
        elif b64:
            try:
                content = base64.b64decode(b64)
            except Exception as e:
                logger.warning(f"Failed to decode YTDLP_COOKIES_BASE64: {e}")

        if content:
            try:
                tmp_dir = Path(os.getenv("YTDLP_COOKIES_DIR", tempfile.gettempdir()))
                tmp_dir.mkdir(parents=True, exist_ok=True)
                path = tmp_dir / "yt_cookies.txt"
                path.write_bytes(content)
                self._cookies_file_path = path
                logger.info(f"Materialized yt-dlp cookies to {path}")
                return path
            except Exception as e:
                logger.warning(f"Failed to write cookies file: {e}")

        return None

    def apply_yt_dlp_cookies(self, ydl_opts: dict) -> dict:
        """Inject cookies and headers into yt-dlp options based on env vars.

        - Adds 'cookiefile' pointing to a cookies.txt if provided via env
        - Applies YTDLP_ACCEPT_LANGUAGE and YTDLP_USER_AGENT to http_headers if set
        """
        try:
            cookies_path = self._ensure_cookies_file_from_env()
            if cookies_path:
                ydl_opts["cookiefile"] = str(cookies_path)

            # Optionally override headers
            headers = ydl_opts.get("http_headers") or {}
            accept_lang = os.getenv("YTDLP_ACCEPT_LANGUAGE")
            if accept_lang:
                headers["Accept-Language"] = accept_lang
            user_agent = os.getenv("YTDLP_USER_AGENT")
            if user_agent:
                headers["User-Agent"] = user_agent
            if headers:
                ydl_opts["http_headers"] = headers

        except Exception as e:
            logger.warning(f"Failed to apply yt-dlp cookies/headers: {e}")

        return ydl_opts


# Global SSL configuration instance
_ssl_config = None


def get_ssl_config() -> SSLConfig:
    """Get global SSL configuration instance."""
    global _ssl_config
    if _ssl_config is None:
        _ssl_config = SSLConfig()
        _ssl_config.configure_environment()
    return _ssl_config


def configure_ssl_for_development():
    """Configure SSL settings for development environment."""
    global _ssl_config
    _ssl_config = SSLConfig(verify_ssl=False)
    _ssl_config.configure_environment()
    
    # Apply aggressive SSL patches
    try:
        from .ssl_patch import apply_aggressive_ssl_patches
        apply_aggressive_ssl_patches()
        logger.info("SSL configured for development environment with aggressive patches")
    except Exception as e:
        logger.warning(f"Failed to apply aggressive SSL patches: {e}")
        logger.info("SSL configured for development environment (basic mode)")


def reset_ssl_config():
    """Reset SSL configuration to default secure settings."""
    global _ssl_config
    _ssl_config = SSLConfig(verify_ssl=True)
    logger.info("SSL configuration reset to secure defaults") 

