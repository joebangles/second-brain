# Advanced Memory System Setup Guide

The Second Brain now includes an advanced memory system with semantic search, intelligent context retrieval, and automatic consolidation of session logs.

## Features

- **Semantic Search**: Find notes by meaning, not just keywords
- **Intelligent Context**: Agents automatically retrieve relevant memories when processing queries
- **Memory Consolidation**: Extract insights from session logs automatically
- **Hybrid Search**: Combines keyword (FTS5) and vector similarity search
- **Local Embeddings**: Runs entirely offline using sentence-transformers (no API costs)

## Installation

### 1. Install Dependencies

```bash
pip install sentence-transformers numpy scikit-learn
```

This will download approximately 100-150MB of dependencies (one-time).

### 2. Initialize Memory Database

The memory database will be created automatically the first time you use the system. To initialize manually:

```python
from memory.storage import MemoryDatabase

db = MemoryDatabase("memory.db")
print("Memory database initialized!")
```

### 3. Migrate Existing Notes

If you have existing notes in `notes.txt`, migrate them to the memory database:

```python
from memory.storage import MemoryDatabase
from memory.retrieval import MemoryRetrieval

# Initialize
db = MemoryDatabase("memory.db")

# Migrate notes
count = db.migrate_from_notes_txt("notes.txt")
print(f"Migrated {count} notes")

# Generate embeddings
retrieval = MemoryRetrieval(db)
retrieval.rebuild_embeddings()
print("Embeddings generated!")
```

Or use the command line:

```bash
python -m memory.storage --init --migrate notes.txt
```

## Usage

### Voice Mode

The memory system works transparently in voice mode. When you speak, the system will:

1. Transcribe your voice
2. Retrieve relevant memories based on what you said
3. Inject those memories into the agent's context
4. Process your request with full context

Example:
```bash
python app.py
# Speak: "Where did I say I had good Thai food?"
# The system will find your note about the Thai restaurant and answer
```

### Chat Mode

Chat mode uses semantic search to retrieve only relevant memories:

```bash
python app.py --chat
```

Example queries:
- "Where did I have Thai food?" - Finds restaurant notes semantically
- "What programming tips do I have?" - Retrieves coding-related notes
- "What should I remember about my dentist?" - Finds health notes

### Saving Notes

Notes are automatically saved to both `notes.txt` (backward compatibility) and the memory database with embeddings:

In chat/voice mode:
- "Remember that I loved the new Thai restaurant on Shattuck Avenue"
- "Note that Python list comprehensions are faster than loops"

The `save_note` tool will handle both file and database storage.

### Searching Notes

Use the `search_notes` tool for hybrid semantic + keyword search:

```bash
python app.py --chat
# You: "Search for restaurant recommendations"
# System will find all restaurant-related notes using semantic similarity
```

## Session Consolidation

Extract insights from past sessions and add them to memory:

### Single Session

```bash
python -m memory.consolidation --session session_20260130_123456.txt
```

### All Sessions

```bash
python -m memory.consolidation --import-all .
```

This will:
1. Parse each session log
2. Use Gemini AI to extract key facts, preferences, and topics
3. Save insights as searchable memories
4. Link them back to the original session

## Memory Management

### View Statistics

```python
from memory.storage import MemoryDatabase

db = MemoryDatabase("memory.db")
stats = db.get_stats()

print(f"Total memories: {stats['total_memories']}")
print(f"Database size: {stats['db_size_mb']} MB")
print(f"By type: {stats['by_type']}")
```

### Rebuild Embeddings

If you change the embedding model or need to fix corrupted embeddings:

```python
from memory.storage import MemoryDatabase
from memory.retrieval import MemoryRetrieval

db = MemoryDatabase("memory.db")
retrieval = MemoryRetrieval(db)

retrieval.rebuild_embeddings()
```

### Search Memories Directly

```python
from memory.storage import MemoryDatabase
from memory.retrieval import MemoryRetrieval

db = MemoryDatabase("memory.db")
retrieval = MemoryRetrieval(db)

# Semantic search
results = retrieval.hybrid_search("restaurants in Berkeley", top_k=5)

for memory in results:
    print(f"{memory.title}: {memory.content[:100]}...")
```

## Testing

Run the test suite to verify everything works:

```bash
python test_memory.py
```

This will test:
- Basic storage operations
- Embedding generation
- Hybrid search
- Statistics
- Migration from notes.txt

## Architecture

### Storage Layer
- **SQLite Database**: `memory.db`
- **FTS5 Full-Text Search**: Fast keyword matching
- **Embedding Storage**: Binary blobs of numpy arrays
- **Auto-sync Triggers**: Keep FTS index in sync with main table

### Embedding Layer
- **Model**: sentence-transformers/all-MiniLM-L6-v2
- **Dimensions**: 384
- **Performance**: ~50ms per embedding on CPU
- **Caching**: In-memory cache to avoid re-computing

### Retrieval Layer
- **Hybrid Search**: Combines FTS5 (30%) + Vector similarity (50%) + Recency (10%) + Importance (10%)
- **Reranking**: Multi-factor scoring for best results
- **Diversity Filtering**: Avoids redundant results

### Integration
- **Agent Context Injection**: `delegation_agent.py` automatically retrieves top 5 memories
- **Tool Integration**: `save_note` and `search_notes` use memory system
- **Chat Mode**: Dynamic memory retrieval per query

## File Structure

```
memory/
├── __init__.py           # Module initialization
├── types.py              # Data classes (Memory, SearchResult)
├── storage.py            # Database layer (SQLite + FTS5)
├── embeddings.py         # Sentence-transformer integration
├── retrieval.py          # Hybrid search + reranking
└── consolidation.py      # Session log analysis

tools/
├── notes_tools.py        # Updated to use memory system
└── memory_tools.py       # Admin tools for memory management
```

## Performance

- **Search Latency**: <500ms for 1000 memories
- **Embedding Generation**: ~50ms per note
- **Database Size**: ~1MB per 1000 notes + embeddings
- **Memory Usage**: ~200MB during operation (includes model)

## Troubleshooting

### "sentence-transformers not found"

Install dependencies:
```bash
pip install sentence-transformers numpy scikit-learn
```

### "Memory system unavailable"

The system gracefully falls back to file-based notes if the memory system fails. Check:
- Dependencies installed?
- `memory.db` accessible?
- Sufficient disk space?

### Slow first search

The first search loads the sentence-transformers model (~2-3 seconds). Subsequent searches are fast (<500ms).

### Migration failed

Ensure `notes.txt` exists and has the correct format:
```
--- Title ---
Date: YYYY-MM-DD HH:MM
Tags: tag1, tag2
Content here
```

## Future Enhancements

Easy upgrades planned:
- **Cloud Embeddings**: Switch to Gemini embeddings for better quality
- **FAISS Index**: 100x faster vector search for 10k+ memories
- **Importance Scoring**: Auto-boost frequently accessed memories
- **Temporal Decay**: Reduce importance of old unused memories
- **Graph Relations**: Track relationships between memories

See the plan file for details on upgrading to advanced features.

## Support

For issues or questions:
1. Check this guide
2. Run `python test_memory.py` to verify installation
3. Review memory system statistics
4. Check logs for error messages
