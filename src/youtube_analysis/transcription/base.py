from abc import ABC, abstractmethod
from .models import Transcript

class BaseTranscriber(ABC):
    """Abstract interface for a transcript provider."""

    @abstractmethod
    async def get(self, *, video_id: str, language: str) -> Transcript:  # noqa: D401
        """Return *Transcript* for *video_id* or raise `TranscriptUnavailable`."""


class TranscriptUnavailable(Exception):
    """Raised when no captions are available and ASR also fails.""" 