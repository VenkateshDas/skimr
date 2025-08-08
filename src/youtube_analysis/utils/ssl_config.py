"""
SSL Configuration Helper for YouTube Analysis

This module provides SSL configuration utilities to handle certificate verification issues
that commonly occur in development environments or systems with corporate firewalls.
"""

import ssl
import os
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
        
        return ydl_opts
    
    def configure_requests_session(self, session):
        """Configure requests session for SSL handling."""
        if not self.verify_ssl:
            session.verify = False
            logger.debug("Requests session configured to bypass SSL verification")
        return session


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

