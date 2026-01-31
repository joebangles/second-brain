"""
Embedding generation using sentence-transformers.
"""

import hashlib
import pickle
from typing import List, Optional

import numpy as np


class EmbeddingService:
    """Service for generating and managing text embeddings."""

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        """
        Initialize the embedding service.

        Args:
            model_name: Name of the sentence-transformers model to use
        """
        self.model_name = model_name
        self._model = None
        self._cache = {}  # Simple in-memory cache

    def _load_model(self):
        """Lazy load the sentence-transformers model."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self.model_name)
            except ImportError:
                raise ImportError(
                    "sentence-transformers is required. Install with: "
                    "pip install sentence-transformers"
                )

    def embed_text(self, text: str, use_cache: bool = True) -> np.ndarray:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed
            use_cache: Whether to use cached embeddings

        Returns:
            NumPy array of embeddings (384 dimensions for all-MiniLM-L6-v2)
        """
        if not text or not text.strip():
            # Return zero vector for empty text
            self._load_model()
            return np.zeros(self._model.get_sentence_embedding_dimension())

        # Check cache
        if use_cache:
            cache_key = self._get_cache_key(text)
            if cache_key in self._cache:
                return self._cache[cache_key]

        self._load_model()
        embedding = self._model.encode(text, convert_to_numpy=True)

        # Cache the result
        if use_cache:
            cache_key = self._get_cache_key(text)
            self._cache[cache_key] = embedding

        return embedding

    def embed_batch(self, texts: List[str], use_cache: bool = True) -> List[np.ndarray]:
        """
        Generate embeddings for a batch of texts (more efficient than one-by-one).

        Args:
            texts: List of texts to embed
            use_cache: Whether to use cached embeddings

        Returns:
            List of NumPy arrays
        """
        if not texts:
            return []

        # Check which texts need embedding
        embeddings = [None] * len(texts)
        texts_to_embed = []
        indices_to_embed = []

        for i, text in enumerate(texts):
            if not text or not text.strip():
                # Zero vector for empty text
                self._load_model()
                embeddings[i] = np.zeros(self._model.get_sentence_embedding_dimension())
                continue

            if use_cache:
                cache_key = self._get_cache_key(text)
                if cache_key in self._cache:
                    embeddings[i] = self._cache[cache_key]
                    continue

            texts_to_embed.append(text)
            indices_to_embed.append(i)

        # Embed uncached texts in batch
        if texts_to_embed:
            self._load_model()
            batch_embeddings = self._model.encode(
                texts_to_embed,
                convert_to_numpy=True,
                show_progress_bar=len(texts_to_embed) > 10
            )

            # Store results
            for idx, embedding in zip(indices_to_embed, batch_embeddings):
                embeddings[idx] = embedding

                # Cache it
                if use_cache:
                    cache_key = self._get_cache_key(texts[idx])
                    self._cache[cache_key] = embedding

        return embeddings

    def cosine_similarity(self, emb1: np.ndarray, emb2: np.ndarray) -> float:
        """
        Calculate cosine similarity between two embeddings.

        Args:
            emb1: First embedding
            emb2: Second embedding

        Returns:
            Similarity score between -1 and 1 (higher is more similar)
        """
        # Normalize vectors
        norm1 = np.linalg.norm(emb1)
        norm2 = np.linalg.norm(emb2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(np.dot(emb1, emb2) / (norm1 * norm2))

    def serialize_embedding(self, embedding: np.ndarray) -> bytes:
        """
        Serialize embedding to bytes for database storage.

        Args:
            embedding: NumPy array to serialize

        Returns:
            Bytes representation
        """
        return pickle.dumps(embedding, protocol=pickle.HIGHEST_PROTOCOL)

    def deserialize_embedding(self, blob: bytes) -> np.ndarray:
        """
        Deserialize embedding from bytes.

        Args:
            blob: Bytes representation

        Returns:
            NumPy array
        """
        return pickle.loads(blob)

    def get_embedding_dimension(self) -> int:
        """Get the dimension of embeddings produced by this model."""
        self._load_model()
        return self._model.get_sentence_embedding_dimension()

    def _get_cache_key(self, text: str) -> str:
        """Generate cache key for text."""
        # Use hash of text as cache key
        return hashlib.md5(text.encode('utf-8')).hexdigest()

    def clear_cache(self):
        """Clear the embedding cache."""
        self._cache.clear()


# Singleton instance for reuse
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """Get or create the global embedding service instance."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
