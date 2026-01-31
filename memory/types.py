"""
Data types for the memory system.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List


@dataclass
class Memory:
    """Represents a memory entry."""
    id: Optional[int] = None
    memory_type: str = "note"  # 'note', 'conversation', 'insight', 'fact'
    title: Optional[str] = None
    content: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: Optional[datetime] = None
    importance_score: float = 0.5
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    source_type: str = "manual"  # 'manual', 'voice', 'session', 'consolidated'
    source_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            'id': self.id,
            'memory_type': self.memory_type,
            'title': self.title,
            'content': self.content,
            'metadata': self.metadata,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'importance_score': self.importance_score,
            'access_count': self.access_count,
            'last_accessed': self.last_accessed.isoformat() if self.last_accessed else None,
            'source_type': self.source_type,
            'source_id': self.source_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Memory':
        """Create Memory from dictionary."""
        # Parse datetime strings
        if data.get('timestamp') and isinstance(data['timestamp'], str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        if data.get('last_accessed') and isinstance(data['last_accessed'], str):
            data['last_accessed'] = datetime.fromisoformat(data['last_accessed'])

        return cls(**data)


@dataclass
class SearchResult:
    """Represents a search result with scoring information."""
    memory: Memory
    keyword_score: float = 0.0
    semantic_score: float = 0.0
    recency_score: float = 0.0
    importance_score: float = 0.0
    final_score: float = 0.0

    def __lt__(self, other):
        """Allow sorting by final score."""
        return self.final_score < other.final_score

    def __gt__(self, other):
        """Allow sorting by final score."""
        return self.final_score > other.final_score
