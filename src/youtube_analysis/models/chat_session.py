"""Data models for chat sessions."""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum


class MessageRole(Enum):
    """Chat message role enumeration."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class ChatMessage:
    """Represents a single chat message."""
    role: MessageRole
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "role": self.role.value,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChatMessage":
        """Create from dictionary."""
        return cls(
            role=MessageRole(data["role"]),
            content=data["content"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            metadata=data.get("metadata")
        )


@dataclass
class ChatSession:
    """Represents a complete chat session."""
    session_id: str
    video_id: str
    youtube_url: str
    messages: List[ChatMessage] = field(default_factory=list)
    agent_details: Optional[Dict[str, Any]] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    is_active: bool = True
    
    def add_message(self, message: ChatMessage) -> None:
        """Add a message to the session."""
        self.messages.append(message)
        self.updated_at = datetime.now()
    
    def add_user_message(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Add a user message."""
        message = ChatMessage(
            role=MessageRole.USER,
            content=content,
            metadata=metadata
        )
        self.add_message(message)
    
    def add_assistant_message(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Add an assistant message."""
        message = ChatMessage(
            role=MessageRole.ASSISTANT,
            content=content,
            metadata=metadata
        )
        self.add_message(message)
    
    @property
    def message_count(self) -> int:
        """Get total message count."""
        return len(self.messages)
    
    @property
    def user_message_count(self) -> int:
        """Get user message count."""
        return len([msg for msg in self.messages if msg.role == MessageRole.USER])
    
    @property
    def last_activity(self) -> datetime:
        """Get last activity timestamp."""
        return self.updated_at
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "session_id": self.session_id,
            "video_id": self.video_id,
            "youtube_url": self.youtube_url,
            "messages": [msg.to_dict() for msg in self.messages],
            "agent_details": self.agent_details,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "is_active": self.is_active
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChatSession":
        """Create from dictionary."""
        messages = [
            ChatMessage.from_dict(msg_data)
            for msg_data in data.get("messages", [])
        ]
        
        return cls(
            session_id=data["session_id"],
            video_id=data["video_id"],
            youtube_url=data["youtube_url"],
            messages=messages,
            agent_details=data.get("agent_details"),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            is_active=data.get("is_active", True)
        )