"""
Unit tests for Local Embedding Generation.

Tests embedding generation, batch processing, and similarity computation.
"""

import pytest
import numpy as np
from unittest.mock import patch, MagicMock
import sys

from src.embeddings.embedder import LocalEmbedder, EmbeddingResult


class TestLocalEmbedderInitialization:
    """Tests for embedder initialization."""
    
    def test_default_configuration(self):
        """Test default embedder configuration."""
        embedder = LocalEmbedder()
        
        assert embedder.model_name == "BAAI/bge-small-en-v1.5"
        assert embedder.device == "cpu"
        assert embedder.normalize is True
        assert embedder._model is None  # Lazy loading
    
    def test_custom_configuration(self):
        """Test custom embedder configuration."""
        embedder = LocalEmbedder(
            model_name="custom/model",
            device="cuda",
            normalize=False,
            cache_dir="/tmp/cache"
        )
        
        assert embedder.model_name == "custom/model"
        assert embedder.device == "cuda"
        assert embedder.normalize is False
        assert embedder.cache_dir == "/tmp/cache"
    
    def test_embedding_dimension_constant(self):
        """Test that embedding dimension is correctly defined."""
        assert LocalEmbedder.EMBEDDING_DIM == 384


class TestEmbedText:
    """Tests for single text embedding."""
    
    @patch('sentence_transformers.SentenceTransformer')
    def test_embed_text_returns_correct_shape(self, mock_st):
        """Test that embed_text returns 384-dimensional vector."""
        mock_model = MagicMock()
        mock_model.encode.return_value = np.random.randn(384)
        mock_st.return_value = mock_model
        
        embedder = LocalEmbedder()
        result = embedder.embed_text("Test text for embedding")
        
        assert isinstance(result, np.ndarray)
        assert result.shape == (384,)
    
    @patch('sentence_transformers.SentenceTransformer')
    def test_embed_text_calls_model_correctly(self, mock_st):
        """Test that embed_text calls model with correct parameters."""
        mock_model = MagicMock()
        mock_model.encode.return_value = np.random.randn(384)
        mock_st.return_value = mock_model
        
        embedder = LocalEmbedder()
        embedder.embed_text("Sample text")
        
        mock_model.encode.assert_called_once()
        call_kwargs = mock_model.encode.call_args[1]
        assert call_kwargs['convert_to_numpy'] is True
        assert call_kwargs['normalize_embeddings'] is True
    
    def test_embed_empty_text_returns_zeros(self):
        """Test that empty text returns zero vector without loading model."""
        embedder = LocalEmbedder()
        
        result = embedder.embed_text("")
        
        assert isinstance(result, np.ndarray)
        assert result.shape == (384,)
        assert np.allclose(result, np.zeros(384))
    
    def test_embed_whitespace_only_returns_zeros(self):
        """Test that whitespace-only text returns zero vector."""
        embedder = LocalEmbedder()
        
        result = embedder.embed_text("   \n\t  ")
        
        assert np.allclose(result, np.zeros(384))


class TestEmbedBatch:
    """Tests for batch embedding."""
    
    @patch('sentence_transformers.SentenceTransformer')
    def test_embed_batch_returns_correct_shape(self, mock_st):
        """Test that embed_batch returns correct 2D array shape."""
        mock_model = MagicMock()
        mock_model.encode.return_value = np.random.randn(3, 384)
        mock_st.return_value = mock_model
        
        embedder = LocalEmbedder()
        texts = ["Text one", "Text two", "Text three"]
        result = embedder.embed_batch(texts)
        
        assert isinstance(result, np.ndarray)
        assert result.shape == (3, 384)
    
    @patch('sentence_transformers.SentenceTransformer')
    def test_embed_batch_with_batch_size(self, mock_st):
        """Test that batch_size parameter is passed correctly."""
        mock_model = MagicMock()
        mock_model.encode.return_value = np.random.randn(5, 384)
        mock_st.return_value = mock_model
        
        embedder = LocalEmbedder()
        texts = ["Text"] * 5
        embedder.embed_batch(texts, batch_size=16)
        
        call_kwargs = mock_model.encode.call_args[1]
        assert call_kwargs['batch_size'] == 16
    
    def test_embed_batch_empty_list(self):
        """Test that empty list returns empty array with correct shape."""
        embedder = LocalEmbedder()
        
        result = embedder.embed_batch([])
        
        assert isinstance(result, np.ndarray)
        assert result.shape == (0, 384)
    
    @patch('sentence_transformers.SentenceTransformer')
    def test_embed_batch_handles_empty_strings(self, mock_st):
        """Test that empty strings in batch get zero vectors."""
        mock_model = MagicMock()
        # Only 2 valid texts will be encoded
        mock_model.encode.return_value = np.ones((2, 384))
        mock_st.return_value = mock_model
        
        embedder = LocalEmbedder()
        texts = ["Valid text", "", "Another valid"]
        result = embedder.embed_batch(texts)
        
        assert result.shape == (3, 384)
        # First and third should have embeddings
        assert not np.allclose(result[0], np.zeros(384))
        # Second (empty) should be zeros
        assert np.allclose(result[1], np.zeros(384))
        assert not np.allclose(result[2], np.zeros(384))
    
    @patch('sentence_transformers.SentenceTransformer')
    def test_embed_batch_100_texts(self, mock_st):
        """Test batch processing works for 100 texts."""
        mock_model = MagicMock()
        mock_model.encode.return_value = np.random.randn(100, 384)
        mock_st.return_value = mock_model
        
        embedder = LocalEmbedder()
        texts = [f"Text number {i}" for i in range(100)]
        result = embedder.embed_batch(texts)
        
        assert result.shape == (100, 384)


class TestEmbedQuery:
    """Tests for query embedding with instruction prefix."""
    
    @patch('sentence_transformers.SentenceTransformer')
    def test_embed_query_adds_instruction_prefix(self, mock_st):
        """Test that query embedding adds BGE instruction prefix."""
        mock_model = MagicMock()
        mock_model.encode.return_value = np.random.randn(384)
        mock_st.return_value = mock_model
        
        embedder = LocalEmbedder()
        embedder.embed_query("What are the risk factors?")
        
        call_args = mock_model.encode.call_args[0][0]
        assert call_args.startswith("Represent this sentence for searching relevant passages:")
        assert "risk factors" in call_args
    
    @patch('sentence_transformers.SentenceTransformer')
    def test_embed_query_returns_correct_shape(self, mock_st):
        """Test that embed_query returns 384-dimensional vector."""
        mock_model = MagicMock()
        mock_model.encode.return_value = np.random.randn(384)
        mock_st.return_value = mock_model
        
        embedder = LocalEmbedder()
        result = embedder.embed_query("Search query")
        
        assert result.shape == (384,)
    
    def test_embed_query_empty_returns_zeros(self):
        """Test that empty query returns zero vector."""
        embedder = LocalEmbedder()
        
        result = embedder.embed_query("")
        
        assert np.allclose(result, np.zeros(384))


class TestSimilarity:
    """Tests for similarity computation."""
    
    def test_similarity_identical_vectors(self):
        """Test similarity of identical normalized vectors is 1.0."""
        embedder = LocalEmbedder(normalize=True)
        
        vec = np.random.randn(384)
        vec = vec / np.linalg.norm(vec)  # Normalize
        
        similarity = embedder.similarity(vec, vec)
        
        assert np.isclose(similarity, 1.0)
    
    def test_similarity_orthogonal_vectors(self):
        """Test similarity of orthogonal vectors is 0.0."""
        embedder = LocalEmbedder(normalize=True)
        
        vec1 = np.zeros(384)
        vec1[0] = 1.0
        vec2 = np.zeros(384)
        vec2[1] = 1.0
        
        similarity = embedder.similarity(vec1, vec2)
        
        assert np.isclose(similarity, 0.0)
    
    def test_similarity_opposite_vectors(self):
        """Test similarity of opposite vectors is -1.0."""
        embedder = LocalEmbedder(normalize=True)
        
        vec = np.random.randn(384)
        vec = vec / np.linalg.norm(vec)
        
        similarity = embedder.similarity(vec, -vec)
        
        assert np.isclose(similarity, -1.0)
    
    def test_similarity_with_zero_vector(self):
        """Test similarity with zero vector returns 0."""
        embedder = LocalEmbedder(normalize=False)
        
        vec = np.random.randn(384)
        zero = np.zeros(384)
        
        similarity = embedder.similarity(vec, zero)
        
        assert similarity == 0.0
    
    def test_similarity_unnormalized_vectors(self):
        """Test similarity computation for unnormalized vectors."""
        embedder = LocalEmbedder(normalize=False)
        
        vec1 = np.array([1.0, 0.0, 0.0] + [0.0] * 381)
        vec2 = np.array([2.0, 0.0, 0.0] + [0.0] * 381)  # Same direction, different magnitude
        
        similarity = embedder.similarity(vec1, vec2)
        
        # Should be 1.0 (same direction)
        assert np.isclose(similarity, 1.0)


class TestEmbedWithMetadata:
    """Tests for embedding with metadata."""
    
    @patch('sentence_transformers.SentenceTransformer')
    def test_embed_with_metadata_returns_result(self, mock_st):
        """Test that embed_with_metadata returns EmbeddingResult."""
        mock_model = MagicMock()
        mock_model.encode.return_value = np.random.randn(384)
        mock_st.return_value = mock_model
        
        embedder = LocalEmbedder()
        result = embedder.embed_with_metadata("Test text")
        
        assert isinstance(result, EmbeddingResult)
        assert result.text == "Test text"
        assert result.model == "BAAI/bge-small-en-v1.5"
        assert result.dimensions == 384
        assert result.embedding.shape == (384,)


class TestModelInfo:
    """Tests for model information."""
    
    def test_get_model_info_before_loading(self):
        """Test model info before model is loaded."""
        embedder = LocalEmbedder()
        info = embedder.get_model_info()
        
        assert info["model_name"] == "BAAI/bge-small-en-v1.5"
        assert info["dimensions"] == 384
        assert info["device"] == "cpu"
        assert info["normalize"] is True
        assert info["loaded"] is False
    
    @patch('sentence_transformers.SentenceTransformer')
    def test_get_model_info_after_loading(self, mock_st):
        """Test model info after model is loaded."""
        mock_st.return_value = MagicMock()
        
        embedder = LocalEmbedder()
        _ = embedder.model  # Trigger loading
        info = embedder.get_model_info()
        
        assert info["loaded"] is True
    
    @patch('sentence_transformers.SentenceTransformer')
    def test_unload_model(self, mock_st):
        """Test that unload_model clears the model."""
        mock_st.return_value = MagicMock()
        
        embedder = LocalEmbedder()
        _ = embedder.model  # Load
        assert embedder._model is not None
        
        embedder.unload_model()
        assert embedder._model is None


class TestNormalization:
    """Tests for embedding normalization."""
    
    @patch('sentence_transformers.SentenceTransformer')
    def test_normalization_enabled(self, mock_st):
        """Test that normalization is passed to model.encode."""
        mock_model = MagicMock()
        mock_model.encode.return_value = np.random.randn(384)
        mock_st.return_value = mock_model
        
        embedder = LocalEmbedder(normalize=True)
        embedder.embed_text("Test")
        
        call_kwargs = mock_model.encode.call_args[1]
        assert call_kwargs['normalize_embeddings'] is True
    
    @patch('sentence_transformers.SentenceTransformer')
    def test_normalization_disabled(self, mock_st):
        """Test that normalization can be disabled."""
        mock_model = MagicMock()
        mock_model.encode.return_value = np.random.randn(384)
        mock_st.return_value = mock_model
        
        embedder = LocalEmbedder(normalize=False)
        embedder.embed_text("Test")
        
        call_kwargs = mock_model.encode.call_args[1]
        assert call_kwargs['normalize_embeddings'] is False
    
    def test_normalize_embedding_method(self):
        """Test internal normalization method."""
        embedder = LocalEmbedder()
        
        vec = np.array([3.0, 4.0] + [0.0] * 382)  # Norm = 5
        normalized = embedder._normalize_embedding(vec)
        
        assert np.isclose(np.linalg.norm(normalized), 1.0)
        assert np.isclose(normalized[0], 0.6)
        assert np.isclose(normalized[1], 0.8)
    
    def test_normalize_zero_vector(self):
        """Test normalizing zero vector returns zero vector."""
        embedder = LocalEmbedder()
        
        zero = np.zeros(384)
        result = embedder._normalize_embedding(zero)
        
        assert np.allclose(result, zero)


class TestTextPreparation:
    """Tests for text preparation."""
    
    def test_prepare_text_normalizes_whitespace(self):
        """Test that text preparation normalizes whitespace."""
        embedder = LocalEmbedder()
        
        text = "Multiple   spaces\n\nand\tnewlines"
        prepared = embedder._prepare_text(text)
        
        assert "  " not in prepared
        assert "\n" not in prepared
        assert "\t" not in prepared


class TestEmbeddingResult:
    """Tests for EmbeddingResult dataclass."""
    
    def test_embedding_result_creation(self):
        """Test creating an EmbeddingResult."""
        embedding = np.random.randn(384)
        result = EmbeddingResult(
            embedding=embedding,
            text="Sample text",
            model="test-model",
            dimensions=384
        )
        
        assert np.array_equal(result.embedding, embedding)
        assert result.text == "Sample text"
        assert result.model == "test-model"
        assert result.dimensions == 384


class TestLazyLoading:
    """Tests for lazy model loading."""
    
    def test_model_not_loaded_on_init(self):
        """Test that model is not loaded during initialization."""
        embedder = LocalEmbedder()
        
        assert embedder._model is None
    
    @patch('sentence_transformers.SentenceTransformer')
    def test_model_loaded_on_first_use(self, mock_st):
        """Test that model is loaded on first embed call."""
        mock_st.return_value = MagicMock()
        mock_st.return_value.encode.return_value = np.random.randn(384)
        
        embedder = LocalEmbedder()
        assert embedder._model is None
        
        embedder.embed_text("Trigger loading")
        
        assert embedder._model is not None
        mock_st.assert_called_once()
    
    @patch('sentence_transformers.SentenceTransformer')
    def test_model_loaded_only_once(self, mock_st):
        """Test that model is loaded only once across multiple calls."""
        mock_st.return_value = MagicMock()
        mock_st.return_value.encode.return_value = np.random.randn(384)
        
        embedder = LocalEmbedder()
        embedder.embed_text("First call")
        embedder.embed_text("Second call")
        embedder.embed_text("Third call")
        
        # Model should only be instantiated once
        mock_st.assert_called_once()
