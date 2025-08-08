"""
SSL Patch Module for YouTube Analysis

This module applies aggressive SSL patches to handle certificate verification issues.
USE ONLY IN DEVELOPMENT OR TESTING ENVIRONMENTS.
"""

import ssl
import urllib.request
import urllib3
import warnings
from typing import Optional
from .logging import get_logger

logger = get_logger("ssl_patch")


class SSLPatcher:
    """Aggressive SSL patcher for development environments."""
    
    def __init__(self):
        self.patches_applied = False
        self.original_functions = {}
    
    def apply_patches(self):
        """Apply all SSL bypass patches."""
        if self.patches_applied:
            logger.debug("SSL patches already applied")
            return
        
        try:
            # Patch 1: Python's default SSL context
            self._patch_python_ssl()
            
            # Patch 2: urllib3 SSL warnings
            self._patch_urllib3_warnings()
            
            # Patch 3: urllib requests
            self._patch_urllib()
            
            # Patch 4: YouTube Transcript API specific patches
            self._patch_youtube_transcript_api()
            
            self.patches_applied = True
            logger.warning("Aggressive SSL patches applied - USE ONLY IN DEVELOPMENT!")
            
        except Exception as e:
            logger.error(f"Failed to apply SSL patches: {e}")
    
    def _patch_python_ssl(self):
        """Patch Python's SSL context creation."""
        # Store original function
        if not hasattr(ssl, '_original_create_default_https_context'):
            ssl._original_create_default_https_context = ssl.create_default_context
        
        def create_unverified_context(*args, **kwargs):
            context = ssl._original_create_default_https_context(*args, **kwargs)
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            return context
        
        ssl.create_default_context = create_unverified_context
        ssl._create_default_https_context = ssl._create_unverified_context
        
        logger.debug("Patched Python SSL context creation")
    
    def _patch_urllib3_warnings(self):
        """Disable urllib3 SSL warnings."""
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        urllib3.disable_warnings(urllib3.exceptions.SubjectAltNameWarning)
        urllib3.disable_warnings(urllib3.exceptions.SNIMissingWarning)
        
        logger.debug("Disabled urllib3 SSL warnings")
    
    def _patch_urllib(self):
        """Patch urllib for SSL bypass."""
        try:
            # Create unverified context for urllib
            unverified_context = ssl._create_unverified_context()
            
            # Store original opener
            if not hasattr(urllib.request, '_original_urlopen'):
                urllib.request._original_urlopen = urllib.request.urlopen
            
            def patched_urlopen(url, data=None, timeout=None, *, cafile=None, capath=None, cadefault=False, context=None):
                return urllib.request._original_urlopen(url, data, timeout, cafile=cafile, capath=capath, cadefault=cadefault, context=unverified_context)
            
            urllib.request.urlopen = patched_urlopen
            
            logger.debug("Patched urllib for SSL bypass")
            
        except Exception as e:
            logger.warning(f"Failed to patch urllib: {e}")
    
    def _patch_youtube_transcript_api(self):
        """Patch YouTube Transcript API for SSL bypass."""
        try:
            # Try to patch the requests session used by youtube-transcript-api
            import requests
            from requests.adapters import HTTPAdapter
            from urllib3.util.retry import Retry
            
            class NoSSLVerifyHTTPAdapter(HTTPAdapter):
                def init_poolmanager(self, *args, **kwargs):
                    kwargs['ssl_context'] = ssl._create_unverified_context()
                    return super().init_poolmanager(*args, **kwargs)
            
            # Monkey patch requests to use our adapter
            original_session_init = requests.Session.__init__
            
            def patched_session_init(self, *args, **kwargs):
                original_session_init(self, *args, **kwargs)
                self.verify = False
                self.mount('https://', NoSSLVerifyHTTPAdapter())
                self.mount('http://', NoSSLVerifyHTTPAdapter())
            
            requests.Session.__init__ = patched_session_init
            
            logger.debug("Patched YouTube Transcript API requests for SSL bypass")
            
        except Exception as e:
            logger.warning(f"Failed to patch YouTube Transcript API: {e}")
    
    def remove_patches(self):
        """Remove all applied patches (restore original behavior)."""
        if not self.patches_applied:
            return
        
        try:
            # Restore Python SSL context
            if hasattr(ssl, '_original_create_default_https_context'):
                ssl.create_default_context = ssl._original_create_default_https_context
                ssl._create_default_https_context = ssl.create_default_context
            
            # Restore urllib
            if hasattr(urllib.request, '_original_urlopen'):
                urllib.request.urlopen = urllib.request._original_urlopen
            
            self.patches_applied = False
            logger.info("SSL patches removed")
            
        except Exception as e:
            logger.error(f"Failed to remove SSL patches: {e}")


# Global patcher instance
_ssl_patcher = None


def get_ssl_patcher() -> SSLPatcher:
    """Get global SSL patcher instance."""
    global _ssl_patcher
    if _ssl_patcher is None:
        _ssl_patcher = SSLPatcher()
    return _ssl_patcher


def apply_aggressive_ssl_patches():
    """Apply aggressive SSL patches for development."""
    patcher = get_ssl_patcher()
    patcher.apply_patches()


def remove_ssl_patches():
    """Remove SSL patches and restore normal behavior."""
    patcher = get_ssl_patcher()
    patcher.remove_patches()


def create_manual_fix_instructions() -> str:
    """Generate manual fix instructions for SSL certificate issues."""
    instructions = """
# Manual SSL Certificate Fix for macOS

If you're still experiencing SSL certificate errors, try these manual fixes:

## Option 1: Install certificates using Python's certifi
```bash
pip install certifi
python -c "import ssl; import certifi; print(certifi.where())"
```

## Option 2: Update macOS certificates
```bash
# Update macOS certificate store
/Applications/Python\ 3.x/Install\ Certificates.command
```

## Option 3: Set environment variables
```bash
export PYTHONHTTPSVERIFY=0
export CURL_CA_BUNDLE=""
export REQUESTS_CA_BUNDLE=""
export SSL_VERIFY=false
```

## Option 4: Bypass SSL for this session only
Add this to your script:
```python
import ssl
ssl._create_default_https_context = ssl._create_unverified_context

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
```

## Option 5: Use a different video (as a test)
Try with a video that has captions available:
https://www.youtube.com/watch?v=dQw4w9WgXcQ

## Option 6: Run with specific environment
```bash
YOUTUBE_ANALYSIS_DISABLE_SSL_VERIFY=1 PYTHONHTTPSVERIFY=0 python your_script.py
```
"""
    return instructions 

