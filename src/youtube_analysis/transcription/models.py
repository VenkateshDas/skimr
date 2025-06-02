from dataclasses import dataclass
from typing import List, Optional

@dataclass
class TranscriptSegment:
    """Represents a single segment of a transcript with timing information."""
    text: str
    start: float
    duration: Optional[float] = None
    
    @property
    def end(self) -> float:
        """Calculate end time of the segment."""
        return self.start + (self.duration or 0)
    
    @property
    def timestamp_str(self) -> str:
        """Get formatted timestamp string for display."""
        minutes, seconds = divmod(int(self.start), 60)
        return f"{minutes:02d}:{seconds:02d}"
    
    def to_dict(self):
        """Convert to dictionary for serialization."""
        return {
            "text": self.text,
            "start": self.start,
            "duration": self.duration
        }


@dataclass
class Transcript:
    """Represents a complete transcript with metadata."""
    video_id: str
    language: str
    source: str  # Where the transcript came from (youtube, whisper, etc.)
    segments: List[TranscriptSegment]
    
    @property
    def text(self) -> str:
        """Get plain text transcript with all segments joined."""
        return " ".join([segment.text for segment in self.segments])
    
    @property
    def timestamped_text(self) -> str:
        """Get transcript text with timestamps prefixed."""
        return "\n".join([
            f"[{segment.timestamp_str}] {segment.text}" 
            for segment in self.segments
        ])
    
    def to_dict(self):
        """Convert to dictionary for serialization."""
        return {
            "video_id": self.video_id,
            "language": self.language,
            "source": self.source,
            "segments": [segment.to_dict() for segment in self.segments]
        } 