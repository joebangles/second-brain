"""Notes tools for Second Brain."""

from datetime import datetime
from google.adk.tools import FunctionTool


def save_note(title: str, content: str, tags: str = "") -> str:
    """Save a note to the second brain.
    
    Args:
        title: The title of the note
        content: The content of the note
        tags: Optional comma-separated tags
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    with open("notes.txt", "a", encoding="utf-8") as f:
        f.write(f"\n--- {title} ---\n")
        f.write(f"Date: {timestamp}\n")
        if tags:
            f.write(f"Tags: {tags}\n")
        f.write(f"{content}\n")
    return f"Note saved: '{title}'"


def search_notes(query: str) -> str:
    """Search through saved notes.
    
    Args:
        query: The search query
    """
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
