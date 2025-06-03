"""Utilities for language processing and management."""

from typing import Dict, Optional, List
import logging

logger = logging.getLogger("youtube_analysis.utils.language")

# ISO 639-1 language codes and names
# Common languages prioritized
SUPPORTED_LANGUAGES = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "zh": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "ru": "Russian",
    "ar": "Arabic",
    "hi": "Hindi",
    "pt": "Portuguese",
    "it": "Italian",
    "nl": "Dutch",
    "tr": "Turkish",
    "pl": "Polish",
    "vi": "Vietnamese",
    "th": "Thai",
    "id": "Indonesian",
    "sv": "Swedish",
    "fi": "Finnish",
    "no": "Norwegian",
    "da": "Danish",
    "cs": "Czech",
    "el": "Greek",
    "he": "Hebrew",
    "hu": "Hungarian",
    "ro": "Romanian",
    "uk": "Ukrainian",
    "fa": "Persian",
    "ms": "Malay",
    "ta": "Tamil",
    "bn": "Bengali",
    "ur": "Urdu"
}

def get_supported_languages() -> Dict[str, str]:
    """
    Get a dictionary of supported languages with their ISO codes.
    
    Returns:
        Dict mapping ISO 639-1 codes to language names
    """
    return SUPPORTED_LANGUAGES

def validate_language_code(language_code: str) -> bool:
    """
    Validate if a language code is supported.
    
    Args:
        language_code: ISO 639-1 language code
        
    Returns:
        True if language code is valid, False otherwise
    """
    return language_code in SUPPORTED_LANGUAGES

def get_language_name(language_code: str) -> Optional[str]:
    """
    Get language name from language code.
    
    Args:
        language_code: ISO 639-1 language code
        
    Returns:
        Language name or None if invalid
    """
    return SUPPORTED_LANGUAGES.get(language_code) 