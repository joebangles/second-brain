"""
Core storage layer for the memory system using SQLite.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from .types import Memory


class MemoryDatabase:
    """SQLite-based storage for memories with FTS5 full-text search."""

    def __init__(self, db_path: str = "memory.db"):
        """Initialize database connection and create schema if needed."""
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_schema()

    def _create_schema(self):
        """Create database schema with FTS5 and triggers."""
        cursor = self.conn.cursor()

        # Main memory entries table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_type TEXT NOT NULL,
                title TEXT,
                content TEXT NOT NULL,
                metadata TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                importance_score REAL DEFAULT 0.5,
                access_count INTEGER DEFAULT 0,
                last_accessed DATETIME,
                source_type TEXT,
                source_id TEXT
            )
        """)

        # Embedding storage table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS embeddings (
                memory_id INTEGER PRIMARY KEY,
                embedding BLOB NOT NULL,
                model_version TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(memory_id) REFERENCES memories(id) ON DELETE CASCADE
            )
        """)

        # Full-text search index
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                title,
                content,
                content='memories',
                content_rowid='id'
            )
        """)

        # Triggers to keep FTS in sync
        # Check if triggers exist before creating them
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='trigger' AND name='memories_ai'
        """)
        if not cursor.fetchone():
            cursor.execute("""
                CREATE TRIGGER memories_ai AFTER INSERT ON memories BEGIN
                    INSERT INTO memories_fts(rowid, title, content)
                    VALUES (new.id, new.title, new.content);
                END
            """)

        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='trigger' AND name='memories_ad'
        """)
        if not cursor.fetchone():
            cursor.execute("""
                CREATE TRIGGER memories_ad AFTER DELETE ON memories BEGIN
                    DELETE FROM memories_fts WHERE rowid = old.id;
                END
            """)

        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='trigger' AND name='memories_au'
        """)
        if not cursor.fetchone():
            cursor.execute("""
                CREATE TRIGGER memories_au AFTER UPDATE ON memories BEGIN
                    DELETE FROM memories_fts WHERE rowid = old.id;
                    INSERT INTO memories_fts(rowid, title, content)
                    VALUES (new.id, new.title, new.content);
                END
            """)

        self.conn.commit()

    def add_memory(
        self,
        content: str,
        memory_type: str = "note",
        title: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        source_type: str = "manual",
        source_id: Optional[str] = None,
        importance_score: float = 0.5,
    ) -> int:
        """
        Add a new memory to the database.

        Returns the memory ID.
        """
        cursor = self.conn.cursor()

        # Serialize metadata to JSON
        metadata_json = json.dumps(metadata) if metadata else "{}"

        cursor.execute("""
            INSERT INTO memories (
                memory_type, title, content, metadata,
                importance_score, source_type, source_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            memory_type, title, content, metadata_json,
            importance_score, source_type, source_id
        ))

        self.conn.commit()
        return cursor.lastrowid

    def get_memory(self, memory_id: int) -> Optional[Memory]:
        """Retrieve a memory by ID."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM memories WHERE id = ?", (memory_id,))
        row = cursor.fetchone()

        if not row:
            return None

        return self._row_to_memory(row)

    def update_memory(
        self,
        memory_id: int,
        title: Optional[str] = None,
        content: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        importance_score: Optional[float] = None,
    ) -> bool:
        """Update an existing memory. Returns True if successful."""
        # Get existing memory
        memory = self.get_memory(memory_id)
        if not memory:
            return False

        cursor = self.conn.cursor()

        # Build update query dynamically
        updates = []
        params = []

        if title is not None:
            updates.append("title = ?")
            params.append(title)

        if content is not None:
            updates.append("content = ?")
            params.append(content)

        if metadata is not None:
            updates.append("metadata = ?")
            params.append(json.dumps(metadata))

        if importance_score is not None:
            updates.append("importance_score = ?")
            params.append(importance_score)

        if not updates:
            return True  # Nothing to update

        params.append(memory_id)
        query = f"UPDATE memories SET {', '.join(updates)} WHERE id = ?"

        cursor.execute(query, params)
        self.conn.commit()

        return True

    def delete_memory(self, memory_id: int) -> bool:
        """Delete a memory and its embedding. Returns True if successful."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        self.conn.commit()

        return cursor.rowcount > 0

    def get_all_memories(self, limit: Optional[int] = None) -> List[Memory]:
        """Get all memories, optionally limited."""
        cursor = self.conn.cursor()

        if limit:
            cursor.execute(
                "SELECT * FROM memories ORDER BY timestamp DESC LIMIT ?",
                (limit,)
            )
        else:
            cursor.execute("SELECT * FROM memories ORDER BY timestamp DESC")

        return [self._row_to_memory(row) for row in cursor.fetchall()]

    def search_by_source_type(self, source_type: str) -> List[Memory]:
        """Get all memories from a specific source type."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM memories WHERE source_type = ? ORDER BY timestamp DESC",
            (source_type,)
        )

        return [self._row_to_memory(row) for row in cursor.fetchall()]

    def update_access_stats(self, memory_id: int):
        """Update access count and last accessed timestamp for a memory."""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE memories
            SET access_count = access_count + 1,
                last_accessed = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (memory_id,))
        self.conn.commit()

    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        cursor = self.conn.cursor()

        # Total memories
        cursor.execute("SELECT COUNT(*) FROM memories")
        total = cursor.fetchone()[0]

        # Memories by type
        cursor.execute("""
            SELECT memory_type, COUNT(*) as count
            FROM memories
            GROUP BY memory_type
        """)
        by_type = {row[0]: row[1] for row in cursor.fetchall()}

        # Database size
        db_size = Path(self.db_path).stat().st_size if Path(self.db_path).exists() else 0

        return {
            'total_memories': total,
            'by_type': by_type,
            'db_size_bytes': db_size,
            'db_size_mb': round(db_size / (1024 * 1024), 2),
        }

    def migrate_from_notes_txt(self, file_path: str) -> int:
        """
        Import existing notes from notes.txt file.

        Returns the number of notes imported.
        """
        if not Path(file_path).exists():
            return 0

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Parse notes.txt format
        # --- [Title] ---
        # Date: YYYY-MM-DD HH:MM
        # Tags: comma-separated tags
        # [Content]

        notes = content.split('\n---')
        imported = 0

        for note_text in notes:
            note_text = note_text.strip()
            if not note_text:
                continue

            lines = note_text.split('\n')
            title = None
            date_str = None
            tags = []
            content_lines = []

            i = 0
            while i < len(lines):
                line = lines[i].strip()

                # Extract title from first line (may have --- around it)
                if i == 0:
                    title = line.replace('---', '').strip()
                    i += 1
                    continue

                # Extract date
                if line.startswith('Date:'):
                    date_str = line.replace('Date:', '').strip()
                    i += 1
                    continue

                # Extract tags
                if line.startswith('Tags:'):
                    tags_str = line.replace('Tags:', '').strip()
                    tags = [t.strip() for t in tags_str.split(',') if t.strip()]
                    i += 1
                    continue

                # Rest is content
                content_lines.append(line)
                i += 1

            content = '\n'.join(content_lines).strip()

            if not content and not title:
                continue

            # Parse timestamp
            timestamp = None
            if date_str:
                try:
                    # Try parsing different date formats
                    for fmt in ['%Y-%m-%d %H:%M', '%Y-%m-%d', '%Y-%m-%d %H:%M:%S']:
                        try:
                            timestamp = datetime.strptime(date_str, fmt)
                            break
                        except ValueError:
                            continue
                except Exception:
                    pass

            # Add to database
            metadata = {'tags': tags} if tags else {}

            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO memories (
                    memory_type, title, content, metadata,
                    timestamp, source_type
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                'note', title, content, json.dumps(metadata),
                timestamp.isoformat() if timestamp else datetime.now().isoformat(),
                'migrated'
            ))

            imported += 1

        self.conn.commit()
        return imported

    def _row_to_memory(self, row: sqlite3.Row) -> Memory:
        """Convert a database row to a Memory object."""
        metadata = json.loads(row['metadata']) if row['metadata'] else {}

        # Parse timestamps
        timestamp = None
        if row['timestamp']:
            try:
                timestamp = datetime.fromisoformat(row['timestamp'])
            except Exception:
                pass

        last_accessed = None
        if row['last_accessed']:
            try:
                last_accessed = datetime.fromisoformat(row['last_accessed'])
            except Exception:
                pass

        return Memory(
            id=row['id'],
            memory_type=row['memory_type'],
            title=row['title'],
            content=row['content'],
            metadata=metadata,
            timestamp=timestamp,
            importance_score=row['importance_score'],
            access_count=row['access_count'],
            last_accessed=last_accessed,
            source_type=row['source_type'],
            source_id=row['source_id'],
        )

    def close(self):
        """Close the database connection."""
        self.conn.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
