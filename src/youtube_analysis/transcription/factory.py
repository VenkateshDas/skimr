"""Factory for creating transcription providers."""

from typing import Optional
from .base import BaseTranscriber
from .whisper import WhisperTranscriber

class TranscriberFactory:
    """Factory for creating transcribers."""
    
    @staticmethod
    def create_transcriber(transcriber_type: str = "whisper", **kwargs) -> BaseTranscriber:
        """
        Create a transcriber instance based on type.
        
        Args:
            transcriber_type: Type of transcriber ('whisper' currently the only supported type)
            **kwargs: Additional arguments to pass to the transcriber constructor
            
        Returns:
            A BaseTranscriber implementation
            
        Raises:
            ValueError: If transcriber_type is not supported
        """
        if transcriber_type.lower() == "whisper":
            # Extract model_name if provided
            model_name = kwargs.get("model_name")
            return WhisperTranscriber(default_model=model_name)
        else:
            raise ValueError(f"Unsupported transcriber type: {transcriber_type}") 