"""Notes tools for Second Brain with advanced memory system."""

from datetime import datetime
from google.adk.tools import FunctionTool
from typing import Optional

# Import memory system
try:
    from memory.storage import MemoryDatabase
    from memory.retrieval import MemoryRetrieval
    MEMORY_AVAILABLE = True
except ImportError:
    MEMORY_AVAILABLE = False


# Global memory system instances
_db: Optional[MemoryDatabase] = None
_retrieval: Optional[MemoryRetrieval] = None


def _get_memory_system():
    """Get or initialize the memory system."""
    global _db, _retrieval
    if _db is None and MEMORY_AVAILABLE:
        try:
            _db = MemoryDatabase("memory.db")
            _retrieval = MemoryRetrieval(_db)
        except Exception as e:
            print(f"Warning: Memory system unavailable: {e}")
            return None, None
    return _db, _retrieval


def save_note(title: str, content: str, tags: str = "") -> str:
    """Save a note to the second brain.

    Args:
        title: The title of the note
        content: The content of the note
        tags: Optional comma-separated tags
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Save to memory database if available
    db, retrieval = _get_memory_system()
    if db and retrieval:
        try:
            # Parse tags
            tag_list = [t.strip() for t in tags.split(",")] if tags else []
            metadata = {'tags': tag_list} if tag_list else {}

            # Add to memory database with embedding
            retrieval.add_memory_with_embedding(
                title=title,
                content=content,
                memory_type='note',
                metadata=metadata,
                source_type='manual'
            )
        except Exception as e:
            print(f"Warning: Failed to save to memory database: {e}")

    # Also save to notes.txt for backward compatibility
    with open("notes.txt", "a", encoding="utf-8") as f:
        f.write(f"\n--- {title} ---\n")
        f.write(f"Date: {timestamp}\n")
        if tags:
            f.write(f"Tags: {tags}\n")
        f.write(f"{content}\n")

    return f"Note saved: '{title}'"


def search_notes(query: str) -> str:
    """Search through saved notes using hybrid semantic + keyword search.

    Args:
        query: The search query
    """
    # Try memory system first for semantic search
    db, retrieval = _get_memory_system()
    if db and retrieval:
        try:
            results = retrieval.hybrid_search(query, top_k=10)

            if not results:
                return f"No notes found matching '{query}'"

            # Format results
            output = [f"Found {len(results)} note(s) matching '{query}':\n"]
            for i, memory in enumerate(results, 1):
                output.append(f"\n{i}. {memory.title or 'Untitled'}")
                if memory.timestamp:
                    output.append(f"   Date: {memory.timestamp.strftime('%Y-%m-%d %H:%M')}")

                # Show tags if available
                if memory.metadata and 'tags' in memory.metadata:
                    tags = memory.metadata['tags']
                    if tags:
                        output.append(f"   Tags: {', '.join(tags)}")

                # Show content preview (first 200 chars)
                content_preview = memory.content[:200]
                if len(memory.content) > 200:
                    content_preview += "..."
                output.append(f"   {content_preview}")

            return "\n".join(output)
        except Exception as e:
            print(f"Warning: Memory search failed, falling back to file search: {e}")

    # Fall back to simple file search
    try:
        with open("notes.txt", "r", encoding="utf-8") as f:
            content = f.read()
            if query.lower() in content.lower():
                return f"Found notes containing '{query}':\n{content}"
            return f"No notes found containing '{query}'"
    except FileNotFoundError:
        return "No notes saved yet"


# Create tool instances
notes_save_tool = FunctionTool(save_note)
notes_search_tool = FunctionTool(search_notes)
