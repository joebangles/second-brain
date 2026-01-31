"""
Test script for the advanced memory system.
"""

import sys
from pathlib import Path


def test_storage():
    """Test 1: Basic Storage"""
    print("Test 1: Basic Storage")
    print("-" * 50)

    from memory.storage import MemoryDatabase

    db = MemoryDatabase("test_memory.db")

    # Add a test note
    memory_id = db.add_memory(
        title="Test Note",
        content="This is a test of the memory system",
        memory_type="note"
    )

    # Retrieve it
    memory = db.get_memory(memory_id)
    assert memory.title == "Test Note", "Title mismatch"
    assert memory.content == "This is a test of the memory system", "Content mismatch"

    print("✓ Storage working correctly")
    print(f"  Created memory ID: {memory_id}")
    print(f"  Title: {memory.title}")
    print(f"  Content: {memory.content}")
    print()

    return db


def test_embeddings(db):
    """Test 2: Embedding Generation"""
    print("Test 2: Embedding Generation")
    print("-" * 50)

    from memory.embeddings import EmbeddingService

    embedder = EmbeddingService()

    # Generate embeddings
    print("  Generating embeddings (this may take a moment)...")
    emb1 = embedder.embed_text("I love Thai food")
    emb2 = embedder.embed_text("Thai cuisine is delicious")
    emb3 = embedder.embed_text("Python programming")

    # Check similarity
    sim_12 = embedder.cosine_similarity(emb1, emb2)
    sim_13 = embedder.cosine_similarity(emb1, emb3)

    print(f"  Similarity (Thai food vs Thai cuisine): {sim_12:.3f}")
    print(f"  Similarity (Thai food vs Python): {sim_13:.3f}")

    assert sim_12 > 0.5, "Thai food and Thai cuisine should be similar"
    assert sim_13 < 0.5, "Thai food and Python should be different"

    print("✓ Embeddings working correctly")
    print()


def test_hybrid_search(db):
    """Test 3: Hybrid Search"""
    print("Test 3: Hybrid Search")
    print("-" * 50)

    from memory.retrieval import MemoryRetrieval

    # Add test memories with embeddings
    retrieval = MemoryRetrieval(db)

    print("  Adding test memories...")
    retrieval.add_memory_with_embedding(
        "Thai Restaurant",
        "Great Thai place in Berkeley with amazing pad thai",
        "note"
    )
    retrieval.add_memory_with_embedding(
        "Dentist Appointment",
        "Remember to call dentist next week for checkup",
        "note"
    )
    retrieval.add_memory_with_embedding(
        "Python Tips",
        "Use list comprehensions for efficiency in Python",
        "note"
    )

    # Search by meaning (semantic)
    print("  Searching: 'where should I eat Thai food?'")
    results = retrieval.hybrid_search("where should I eat Thai food?", top_k=3)

    print(f"  Found {len(results)} results")
    assert len(results) > 0, "Should find at least one result"

    # Check that Thai restaurant is in top result
    top_result = results[0]
    print(f"  Top result: {top_result.title}")
    assert "Thai" in top_result.title or "Thai" in top_result.content, \
        "Thai restaurant should be top result"

    print("✓ Semantic search working correctly")
    print()


def test_stats(db):
    """Test 4: Database Statistics"""
    print("Test 4: Database Statistics")
    print("-" * 50)

    stats = db.get_stats()

    print(f"  Total memories: {stats['total_memories']}")
    print(f"  Database size: {stats['db_size_mb']} MB")
    print("  Memories by type:")
    for mem_type, count in stats['by_type'].items():
        print(f"    - {mem_type}: {count}")

    assert stats['total_memories'] >= 4, "Should have at least 4 memories"

    print("✓ Statistics working correctly")
    print()


def test_migration():
    """Test 5: Notes.txt Migration"""
    print("Test 5: Notes.txt Migration")
    print("-" * 50)

    if not Path("notes.txt").exists():
        print("  Skipping: notes.txt not found")
        print()
        return

    from memory.storage import MemoryDatabase
    from memory.retrieval import MemoryRetrieval

    # Create a fresh database for migration test
    db_migration = MemoryDatabase("test_migration.db")

    # Migrate notes
    print("  Migrating notes from notes.txt...")
    count = db_migration.migrate_from_notes_txt("notes.txt")

    print(f"  Migrated {count} notes")

    if count > 0:
        # Generate embeddings
        print("  Generating embeddings for migrated notes...")
        retrieval = MemoryRetrieval(db_migration)
        retrieval.rebuild_embeddings()

        print("✓ Migration working correctly")
    else:
        print("  No notes to migrate")

    print()

    # Clean up
    db_migration.close()
    Path("test_migration.db").unlink(missing_ok=True)


def cleanup():
    """Clean up test databases"""
    print("Cleaning up test files...")
    Path("test_memory.db").unlink(missing_ok=True)
    print("✓ Cleanup complete")
    print()


def main():
    """Run all tests"""
    print("=" * 50)
    print("Memory System Test Suite")
    print("=" * 50)
    print()

    try:
        # Run tests
        db = test_storage()
        test_embeddings(db)
        test_hybrid_search(db)
        test_stats(db)
        test_migration()

        # Close database
        db.close()

        # Clean up
        cleanup()

        print("=" * 50)
        print("All tests passed! ✓")
        print("=" * 50)
        print()
        print("Next steps:")
        print("1. Install dependencies: pip install sentence-transformers numpy scikit-learn")
        print("2. Initialize memory database: python -c \"from memory import MemoryDatabase; MemoryDatabase('memory.db')\"")
        print("3. Migrate existing notes: python -c \"from memory import *; db=MemoryDatabase('memory.db'); db.migrate_from_notes_txt('notes.txt')\"")
        print("4. Test in chat mode: python app.py --chat")

        return 0

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

        # Clean up even on failure
        try:
            cleanup()
        except:
            pass

        return 1


if __name__ == "__main__":
    sys.exit(main())
