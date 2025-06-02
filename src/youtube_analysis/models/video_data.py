"""Data models for video-related information."""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import datetime


@dataclass
class TranscriptSegment:
    """Represents a single transcript segment with timing."""
    text: str
    start: float
    duration: Optional[float] = None
    
    @property
    def end(self) -> float:
        """Calculate end time."""
        return self.start + (self.duration or 0)
    
    @property
    def timestamp_str(self) -> str:
        """Get formatted timestamp string."""
        minutes, seconds = divmod(int(self.start), 60)
        return f"{minutes:02d}:{seconds:02d}"


@dataclass
class VideoInfo:
    """Represents YouTube video metadata."""
    video_id: str
    title: str
    description: Optional[str] = None
    duration: Optional[int] = None
    view_count: Optional[int] = None
    like_count: Optional[int] = None
    publish_date: Optional[datetime] = None
    channel_name: Optional[str] = None
    channel_id: Optional[str] = None
    tags: Optional[List[str]] = None
    thumbnail_url: Optional[str] = None
    
    @property
    def youtube_url(self) -> str:
        """Get YouTube URL from video ID."""
        return f"https://youtu.be/{self.video_id}"


@dataclass
class VideoData:
    """Complete video data including transcript and metadata."""
    video_info: VideoInfo
    transcript: Optional[str] = None
    timestamped_transcript: Optional[str] = None
    transcript_segments: Optional[List[TranscriptSegment]] = None
    
    @property
    def video_id(self) -> str:
        """Get video ID."""
        return self.video_info.video_id
    
    @property
    def youtube_url(self) -> str:
        """Get YouTube URL."""
        return self.video_info.youtube_url
    
    @property
    def has_transcript(self) -> bool:
        """Check if transcript is available."""
        return self.transcript is not None and len(self.transcript.strip()) > 0
    
    @property
    def has_timestamps(self) -> bool:
        """Check if timestamped transcript is available."""
        return (
            self.transcript_segments is not None 
            and len(self.transcript_segments) > 0
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "video_id": self.video_id,
            "youtube_url": self.youtube_url,
            "title": self.video_info.title,
            "description": self.video_info.description,
            "transcript": self.transcript,
            "timestamped_transcript": self.timestamped_transcript,
            "transcript_segments": [
                {
                    "text": seg.text,
                    "start": seg.start,
                    "duration": seg.duration
                }
                for seg in (self.transcript_segments or [])
            ]
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VideoData":
        """Create from dictionary."""
        if not isinstance(data, dict):
            raise TypeError(f"Expected dictionary, got {type(data)}")
            
        # Validate video_id exists
        if "video_id" not in data:
            raise ValueError("Missing required field 'video_id' in data")
            
        # Create VideoInfo with fallbacks
        video_info = VideoInfo(
            video_id=data["video_id"],
            title=data.get("title", "Unknown"),
            description=data.get("description")
        )
        
        # Parse transcript segments with error handling
        transcript_segments = None
        if "transcript_segments" in data and data["transcript_segments"]:
            try:
                if isinstance(data["transcript_segments"], list):
                    transcript_segments = []
                    for seg in data["transcript_segments"]:
                        if not isinstance(seg, dict):
                            continue
                            
                        # Ensure required fields exist
                        if "text" not in seg or "start" not in seg:
                            continue
                            
                        # Handle potential type errors
                        try:
                            segment = TranscriptSegment(
                                text=str(seg["text"]),
                                start=float(seg["start"]),
                                duration=float(seg.get("duration", 0)) if seg.get("duration") is not None else None
                            )
                            transcript_segments.append(segment)
                        except (ValueError, TypeError):
                            # Skip malformed segments
                            continue
            except Exception as e:
                # Continue without transcript segments if parsing fails
                transcript_segments = None
        
        # Get transcript with fallback
        transcript = data.get("transcript")
        if transcript is not None and not isinstance(transcript, str):
            # Try to convert to string
            try:
                transcript = str(transcript)
            except:
                transcript = None
                
        # Get timestamped_transcript with fallback
        timestamped_transcript = data.get("timestamped_transcript")
        if timestamped_transcript is not None and not isinstance(timestamped_transcript, str):
            # Try to convert to string
            try:
                timestamped_transcript = str(timestamped_transcript)
            except:
                timestamped_transcript = None
        
        return cls(
            video_info=video_info,
            transcript=transcript,
            timestamped_transcript=timestamped_transcript,
            transcript_segments=transcript_segments
        )