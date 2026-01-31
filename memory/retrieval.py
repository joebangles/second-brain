"""
Hybrid search combining keyword (FTS5) and semantic (vector) search.
"""

import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Optional

import numpy as np

from .storage import MemoryDatabase
from .embeddings import get_embedding_service
from .types import Memory, SearchResult


class MemoryRetrieval:
    """Hybrid search and retrieval for memories."""

    def __init__(self, database: MemoryDatabase):
        """
        Initialize retrieval system.

        Args:
            database: MemoryDatabase instance
        """
        self.db = database
        self.embedder = get_embedding_service()

    def hybrid_search(
        self,
        query: str,
        top_k: int = 10,
        weights: Optional[Dict[str, float]] = None
    ) -> List[Memory]:
        """
        Perform hybrid search combining keyword and semantic search.

        Args:
            query: Search query
            top_k: Number of results to return
            weights: Score weights (keyword_score, semantic_score, recency, importance)

        Returns:
            List of Memory objects sorted by relevance
        """
        if weights is None:
            weights = {
                'keyword_score': 0.3,
                'semantic_score': 0.5,
                'recency': 0.1,
                'importance': 0.1,
            }

        # Get candidates from both search methods
        keyword_results = self._fts_search(query, limit=20)
        semantic_results = self._vector_search(query, limit=20)

        # Merge results
        candidates = self._merge_results(keyword_results, semantic_results)

        # Rerank with multiple factors
        ranked = self._rerank(candidates, weights)

        # Diversity filtering (avoid too similar results)
        diverse = self._diversify_results(ranked, top_k)

        # Return only Memory objects
        return [result.memory for result in diverse[:top_k]]

    def _fts_search(self, query: str, limit: int = 20) -> Dict[int, float]:
        """
        Perform FTS5 keyword search.

        Returns:
            Dict mapping memory_id -> BM25 score
        """
        cursor = self.db.conn.cursor()

        # Escape FTS5 special characters and prepare query
        # FTS5 uses BM25 ranking by default
        try:
            cursor.execute("""
                SELECT rowid, rank
                FROM memories_fts
                WHERE memories_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """, (query, limit))

            results = {}
            for row in cursor.fetchall():
                memory_id = row[0]
                rank = row[1]  # BM25 rank (negative, closer to 0 is better)
                # Convert rank to positive score (negate and normalize)
                score = -rank
                results[memory_id] = score

            return results

        except sqlite3.OperationalError:
            # Query might have FTS5 syntax issues, fall back to simple search
            return {}

    def _vector_search(self, query: str, limit: int = 20) -> Dict[int, float]:
        """
        Perform vector similarity search.

        Returns:
            Dict mapping memory_id -> cosine similarity score
        """
        # Generate query embedding
        query_embedding = self.embedder.embed_text(query)

        # Get all memories with embeddings
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT e.memory_id, e.embedding
            FROM embeddings e
            INNER JOIN memories m ON e.memory_id = m.id
        """)

        # Calculate similarities
        similarities = []
        for row in cursor.fetchall():
            memory_id = row[0]
            embedding_blob = row[1]

            # Deserialize embedding
            memory_embedding = self.embedder.deserialize_embedding(embedding_blob)

            # Calculate cosine similarity
            similarity = self.embedder.cosine_similarity(query_embedding, memory_embedding)
            similarities.append((memory_id, similarity))

        # Sort by similarity and take top results
        similarities.sort(key=lambda x: x[1], reverse=True)
        top_results = similarities[:limit]

        return {memory_id: score for memory_id, score in top_results}

    def _merge_results(
        self,
        keyword_results: Dict[int, float],
        semantic_results: Dict[int, float]
    ) -> List[SearchResult]:
        """
        Merge keyword and semantic search results.

        Returns:
            List of SearchResult objects with both scores
        """
        # Get all unique memory IDs
        all_ids = set(keyword_results.keys()) | set(semantic_results.keys())

        candidates = []
        for memory_id in all_ids:
            memory = self.db.get_memory(memory_id)
            if not memory:
                continue

            # Get scores (0 if not present)
            keyword_score = keyword_results.get(memory_id, 0.0)
            semantic_score = semantic_results.get(memory_id, 0.0)

            result = SearchResult(
                memory=memory,
                keyword_score=keyword_score,
                semantic_score=semantic_score,
            )
            candidates.append(result)

        return candidates

    def _rerank(
        self,
        candidates: List[SearchResult],
        weights: Dict[str, float]
    ) -> List[SearchResult]:
        """
        Rerank candidates using multiple factors.

        Args:
            candidates: List of SearchResult objects
            weights: Score weights for different factors

        Returns:
            Sorted list of SearchResult objects
        """
        if not candidates:
            return []

        # Normalize keyword scores (0-1 range)
        keyword_scores = [c.keyword_score for c in candidates]
        keyword_min = min(keyword_scores) if keyword_scores else 0
        keyword_max = max(keyword_scores) if keyword_scores else 1
        keyword_range = keyword_max - keyword_min if keyword_max != keyword_min else 1

        # Normalize semantic scores (already 0-1 from cosine similarity)
        semantic_scores = [c.semantic_score for c in candidates]

        # Calculate recency scores (more recent = higher score)
        now = datetime.now()
        for candidate in candidates:
            # Normalize keyword score
            if keyword_range > 0:
                candidate.keyword_score = (candidate.keyword_score - keyword_min) / keyword_range
            else:
                candidate.keyword_score = 0.0

            # Semantic score already normalized (0-1)

            # Recency score (exponential decay)
            if candidate.memory.timestamp:
                age_days = (now - candidate.memory.timestamp).total_seconds() / (24 * 3600)
                # Decay over 30 days
                candidate.recency_score = np.exp(-age_days / 30)
            else:
                candidate.recency_score = 0.0

            # Importance score (already 0-1)
            candidate.importance_score = candidate.memory.importance_score

            # Calculate final weighted score
            candidate.final_score = (
                weights.get('keyword_score', 0.3) * candidate.keyword_score +
                weights.get('semantic_score', 0.5) * candidate.semantic_score +
                weights.get('recency', 0.1) * candidate.recency_score +
                weights.get('importance', 0.1) * candidate.importance_score
            )

        # Sort by final score
        candidates.sort(key=lambda x: x.final_score, reverse=True)

        return candidates

    def _diversify_results(
        self,
        results: List[SearchResult],
        top_k: int,
        similarity_threshold: float = 0.95
    ) -> List[SearchResult]:
        """
        Apply diversity filtering to avoid redundant results.

        Args:
            results: Sorted search results
            top_k: Number of results to return
            similarity_threshold: Minimum similarity to consider results redundant

        Returns:
            Diversified list of results
        """
        if not results:
            return []

        # Get embeddings for all results
        cursor = self.db.conn.cursor()
        embeddings_map = {}

        for result in results:
            cursor.execute(
                "SELECT embedding FROM embeddings WHERE memory_id = ?",
                (result.memory.id,)
            )
            row = cursor.fetchone()
            if row:
                embeddings_map[result.memory.id] = self.embedder.deserialize_embedding(row[0])

        # Select diverse results
        diverse = []
        for result in results:
            if len(diverse) >= top_k:
                break

            # Check if too similar to already selected results
            is_redundant = False
            result_emb = embeddings_map.get(result.memory.id)

            if result_emb is not None:
                for selected in diverse:
                    selected_emb = embeddings_map.get(selected.memory.id)
                    if selected_emb is not None:
                        similarity = self.embedder.cosine_similarity(result_emb, selected_emb)
                        if similarity > similarity_threshold:
                            is_redundant = True
                            break

            if not is_redundant:
                diverse.append(result)

        return diverse

    def update_access_stats(self, memory_ids: List[int]):
        """Update access statistics for retrieved memories."""
        for memory_id in memory_ids:
            self.db.update_access_stats(memory_id)

    def add_memory_with_embedding(
        self,
        content: str,
        memory_type: str = "note",
        title: Optional[str] = None,
        metadata: Optional[Dict] = None,
        source_type: str = "manual",
        source_id: Optional[str] = None,
    ) -> int:
        """
        Add a memory and generate its embedding.

        Returns:
            Memory ID
        """
        # Add to database
        memory_id = self.db.add_memory(
            content=content,
            memory_type=memory_type,
            title=title,
            metadata=metadata,
            source_type=source_type,
            source_id=source_id,
        )

        # Generate and store embedding
        embedding_text = f"{title or ''} {content}".strip()
        embedding = self.embedder.embed_text(embedding_text)
        serialized = self.embedder.serialize_embedding(embedding)

        # Store in database
        cursor = self.db.conn.cursor()
        cursor.execute("""
            INSERT INTO embeddings (memory_id, embedding, model_version)
            VALUES (?, ?, ?)
        """, (memory_id, serialized, self.embedder.model_name))
        self.db.conn.commit()

        return memory_id

    def rebuild_embeddings(self, batch_size: int = 10):
        """
        Rebuild all embeddings from scratch.

        Useful after changing embedding model or fixing corrupted embeddings.
        """
        # Get all memories
        memories = self.db.get_all_memories()

        print(f"Rebuilding embeddings for {len(memories)} memories...")

        # Process in batches
        for i in range(0, len(memories), batch_size):
            batch = memories[i:i + batch_size]

            # Prepare texts
            texts = []
            memory_ids = []
            for memory in batch:
                text = f"{memory.title or ''} {memory.content}".strip()
                texts.append(text)
                memory_ids.append(memory.id)

            # Generate embeddings
            embeddings = self.embedder.embed_batch(texts)

            # Store in database
            cursor = self.db.conn.cursor()
            for memory_id, embedding in zip(memory_ids, embeddings):
                serialized = self.embedder.serialize_embedding(embedding)

                # Delete old embedding
                cursor.execute("DELETE FROM embeddings WHERE memory_id = ?", (memory_id,))

                # Insert new embedding
                cursor.execute("""
                    INSERT INTO embeddings (memory_id, embedding, model_version)
                    VALUES (?, ?, ?)
                """, (memory_id, serialized, self.embedder.model_name))

            self.db.conn.commit()

            print(f"  Processed {min(i + batch_size, len(memories))}/{len(memories)}")

        print("Embedding rebuild complete!")
