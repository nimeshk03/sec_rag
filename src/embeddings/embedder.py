"""
Local Embedding Generation Module

Generates 384-dimensional embeddings using BGE-small-en-v1.5 model.
Optimized for CPU inference on free tier deployments.
"""

import numpy as np
from typing import List, Optional, Union
from dataclasses import dataclass


@dataclass
class EmbeddingResult:
    """Result of an embedding operation."""
    embedding: np.ndarray
    text: str
    model: str
    dimensions: int


class LocalEmbedder:
    """
    Local embedding generator using sentence-transformers.
    
    Uses BGE-small-en-v1.5 model which produces 384-dimensional embeddings.
    Optimized for CPU inference with minimal memory footprint.
    """
    
    DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"
    EMBEDDING_DIM = 384
    
    def __init__(
        self,
        model_name: Optional[str] = None,
        device: str = "cpu",
        normalize: bool = True,
        cache_dir: Optional[str] = None
    ):
        """
        Initialize the embedder.
        
        Args:
            model_name: HuggingFace model name (default: BAAI/bge-small-en-v1.5)
            device: Device to run inference on (default: cpu)
            normalize: Whether to L2-normalize embeddings (default: True)
            cache_dir: Directory to cache model files
        """
        self.model_name = model_name or self.DEFAULT_MODEL
        self.device = device
        self.normalize = normalize
        self.cache_dir = cache_dir
        self._model = None
    
    @property
    def model(self):
        """Lazy load the model on first use."""
        if self._model is None:
            self._load_model()
        return self._model
    
    def _load_model(self):
        """Load the sentence transformer model."""
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError(
                "sentence-transformers is required. "
                "Install with: pip install sentence-transformers"
            )
        
        self._model = SentenceTransformer(
            self.model_name,
            device=self.device,
            cache_folder=self.cache_dir
        )
    
    def _normalize_embedding(self, embedding: np.ndarray) -> np.ndarray:
        """L2 normalize an embedding vector."""
        norm = np.linalg.norm(embedding)
        if norm > 0:
            return embedding / norm
        return embedding
    
    def _prepare_text(self, text: str) -> str:
        """
        Prepare text for embedding.
        
        BGE models work better with instruction prefix for queries.
        """
        # Clean up whitespace
        text = ' '.join(text.split())
        return text
    
    def embed_text(self, text: str) -> np.ndarray:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text to embed
            
        Returns:
            384-dimensional numpy array
        """
        if not text or not text.strip():
            return np.zeros(self.EMBEDDING_DIM)
        
        prepared = self._prepare_text(text)
        embedding = self.model.encode(
            prepared,
            convert_to_numpy=True,
            normalize_embeddings=self.normalize
        )
        
        return embedding
    
    def embed_batch(
        self,
        texts: List[str],
        batch_size: int = 32,
        show_progress: bool = False
    ) -> np.ndarray:
        """
        Generate embeddings for multiple texts.
        
        Args:
            texts: List of texts to embed
            batch_size: Number of texts to process at once
            show_progress: Whether to show progress bar
            
        Returns:
            2D numpy array of shape (n_texts, 384)
        """
        if not texts:
            return np.array([]).reshape(0, self.EMBEDDING_DIM)
        
        # Filter and prepare texts
        prepared_texts = []
        valid_indices = []
        
        for i, text in enumerate(texts):
            if text and text.strip():
                prepared_texts.append(self._prepare_text(text))
                valid_indices.append(i)
        
        if not prepared_texts:
            return np.zeros((len(texts), self.EMBEDDING_DIM))
        
        # Generate embeddings
        embeddings = self.model.encode(
            prepared_texts,
            batch_size=batch_size,
            convert_to_numpy=True,
            normalize_embeddings=self.normalize,
            show_progress_bar=show_progress
        )
        
        # Create result array with zeros for empty texts
        result = np.zeros((len(texts), self.EMBEDDING_DIM))
        for i, idx in enumerate(valid_indices):
            result[idx] = embeddings[i]
        
        return result
    
    def embed_query(self, query: str) -> np.ndarray:
        """
        Generate embedding for a search query.
        
        BGE models recommend prefixing queries with an instruction
        for better retrieval performance.
        
        Args:
            query: Search query text
            
        Returns:
            384-dimensional numpy array
        """
        if not query or not query.strip():
            return np.zeros(self.EMBEDDING_DIM)
        
        # BGE instruction prefix for queries
        instruction = "Represent this sentence for searching relevant passages: "
        prepared = instruction + self._prepare_text(query)
        
        embedding = self.model.encode(
            prepared,
            convert_to_numpy=True,
            normalize_embeddings=self.normalize
        )
        
        return embedding
    
    def embed_with_metadata(self, text: str) -> EmbeddingResult:
        """
        Generate embedding with full metadata.
        
        Args:
            text: Text to embed
            
        Returns:
            EmbeddingResult with embedding and metadata
        """
        embedding = self.embed_text(text)
        
        return EmbeddingResult(
            embedding=embedding,
            text=text,
            model=self.model_name,
            dimensions=self.EMBEDDING_DIM
        )
    
    def similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """
        Compute cosine similarity between two embeddings.
        
        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector
            
        Returns:
            Cosine similarity score between -1 and 1
        """
        # If embeddings are already normalized, dot product = cosine similarity
        if self.normalize:
            return float(np.dot(embedding1, embedding2))
        
        # Otherwise compute full cosine similarity
        norm1 = np.linalg.norm(embedding1)
        norm2 = np.linalg.norm(embedding2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return float(np.dot(embedding1, embedding2) / (norm1 * norm2))
    
    def get_model_info(self) -> dict:
        """
        Get information about the loaded model.
        
        Returns:
            Dict with model name, dimensions, device, etc.
        """
        return {
            "model_name": self.model_name,
            "dimensions": self.EMBEDDING_DIM,
            "device": self.device,
            "normalize": self.normalize,
            "loaded": self._model is not None
        }
    
    def unload_model(self):
        """Unload the model to free memory."""
        self._model = None
