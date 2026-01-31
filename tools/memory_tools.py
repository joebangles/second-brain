"""
Administrative tools for memory system management.
"""

from pathlib import Path
from google.adk.tools import FunctionTool

from memory.storage import MemoryDatabase
from memory.retrieval import MemoryRetrieval


def get_memory_stats() -> str:
    """Get statistics about the memory system."""
    try:
        db = MemoryDatabase("memory.db")
        stats = db.get_stats()

        output = ["Memory System Statistics:", ""]
        output.append(f"Total memories: {stats['total_memories']}")
        output.append(f"Database size: {stats['db_size_mb']} MB")
        output.append("")
        output.append("Memories by type:")
        for mem_type, count in stats['by_type'].items():
            output.append(f"  - {mem_type}: {count}")

        return "\n".join(output)
    except Exception as e:
        return f"Error getting memory stats: {e}"


def rebuild_memory_index() -> str:
    """Rebuild embeddings and FTS index from scratch."""
    try:
        db = MemoryDatabase("memory.db")
        retrieval = MemoryRetrieval(db)

        retrieval.rebuild_embeddings()

        return "Memory index rebuilt successfully!"
    except Exception as e:
        return f"Error rebuilding index: {e}"


def migrate_notes_to_memory(notes_file: str = "notes.txt") -> str:
    """Migrate notes from notes.txt to memory database."""
    try:
        if not Path(notes_file).exists():
            return f"File not found: {notes_file}"

        db = MemoryDatabase("memory.db")
        count = db.migrate_from_notes_txt(notes_file)

        if count == 0:
            return "No notes found to migrate"

        # Generate embeddings for migrated notes
        retrieval = MemoryRetrieval(db)
        retrieval.rebuild_embeddings()

        return f"Successfully migrated {count} notes and generated embeddings"
    except Exception as e:
        return f"Error migrating notes: {e}"


# Create tool instances
memory_stats_tool = FunctionTool(get_memory_stats)
rebuild_index_tool = FunctionTool(rebuild_memory_index)
migrate_notes_tool = FunctionTool(migrate_notes_to_memory)
