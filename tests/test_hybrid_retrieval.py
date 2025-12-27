"""
Unit tests for the Hybrid Retrieval System.

Tests cover:
- RetrievalConfig validation
- QueryPreprocessor functionality
- BM25Searcher indexing and search
- HybridRetriever combining semantic and keyword search
- Filtering by filing type and section
- Safety check multi-faceted retrieval
"""

import pytest
from datetime import date
from unittest.mock import MagicMock, patch
import numpy as np

from src.retrieval.hybrid import (
    HybridRetriever,
    RetrievalResult,
    RetrievalConfig,
    QueryPreprocessor,
    BM25Searcher,
)
from src.data.store import SearchResult


class TestRetrievalConfig:
    """Tests for RetrievalConfig dataclass."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = RetrievalConfig()
        
        assert config.semantic_weight == 0.7
        assert config.keyword_weight == 0.3
        assert config.max_results == 10
        assert config.days_back == 365
        assert config.min_score_threshold == 0.0
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = RetrievalConfig(
            semantic_weight=0.6,
            keyword_weight=0.4,
            max_results=20,
            days_back=180,
            min_score_threshold=0.5,
        )
        
        assert config.semantic_weight == 0.6
        assert config.keyword_weight == 0.4
        assert config.max_results == 20
    
    def test_weights_must_sum_to_one(self):
        """Test that weights must sum to 1.0."""
        with pytest.raises(ValueError, match="Weights must sum to 1.0"):
            RetrievalConfig(semantic_weight=0.5, keyword_weight=0.3)
    
    def test_weights_validation_tolerance(self):
        """Test weight validation has small tolerance for floating point."""
        # Should not raise - within tolerance
        config = RetrievalConfig(semantic_weight=0.7001, keyword_weight=0.2999)
        assert config is not None


class TestQueryPreprocessor:
    """Tests for QueryPreprocessor."""
    
    def test_initialization(self):
        """Test preprocessor initialization."""
        preprocessor = QueryPreprocessor()
        assert preprocessor.expand_terms is True
        assert preprocessor.remove_stopwords is False
    
    def test_preprocess_normalizes_whitespace(self):
        """Test whitespace normalization."""
        preprocessor = QueryPreprocessor(expand_terms=False)
        
        result = preprocessor.preprocess("  multiple   spaces  here  ")
        assert result == "multiple spaces here"
    
    def test_preprocess_expands_terms(self):
        """Test financial term expansion."""
        preprocessor = QueryPreprocessor(expand_terms=True)
        
        result = preprocessor.preprocess("litigation risks")
        
        # Should contain original query
        assert "litigation risks" in result
        # Should contain expansions
        assert "lawsuit" in result or "legal proceedings" in result
    
    def test_preprocess_no_expansion(self):
        """Test with term expansion disabled."""
        preprocessor = QueryPreprocessor(expand_terms=False)
        
        result = preprocessor.preprocess("litigation risks")
        
        assert result == "litigation risks"
        assert "lawsuit" not in result
    
    def test_tokenize_basic(self):
        """Test basic tokenization."""
        preprocessor = QueryPreprocessor()
        
        tokens = preprocessor.tokenize("Hello World! This is a test.")
        
        assert tokens == ["hello", "world", "this", "is", "a", "test"]
    
    def test_tokenize_removes_stopwords(self):
        """Test tokenization with stopword removal."""
        preprocessor = QueryPreprocessor(remove_stopwords=True)
        
        tokens = preprocessor.tokenize("The company is facing risks")
        
        assert "the" not in tokens
        assert "is" not in tokens
        assert "company" in tokens
        assert "facing" in tokens
        assert "risks" in tokens
    
    def test_tokenize_handles_special_chars(self):
        """Test tokenization handles special characters."""
        preprocessor = QueryPreprocessor()
        
        tokens = preprocessor.tokenize("Item 1A: Risk Factors (10-K)")
        
        assert "item" in tokens
        assert "1a" in tokens
        assert "risk" in tokens
        assert "factors" in tokens
        assert "10" in tokens
        assert "k" in tokens


class TestBM25Searcher:
    """Tests for BM25Searcher."""
    
    def test_initialization(self):
        """Test BM25 searcher initialization."""
        searcher = BM25Searcher()
        
        assert searcher._corpus == []
        assert searcher._corpus_ids == []
        assert searcher._bm25 is None
    
    def test_index_documents(self):
        """Test document indexing."""
        searcher = BM25Searcher()
        
        documents = [
            {"id": "doc1", "content": "Apple faces litigation risks"},
            {"id": "doc2", "content": "Microsoft revenue growth"},
            {"id": "doc3", "content": "Legal proceedings against company"},
        ]
        
        searcher.index_documents(documents)
        
        assert len(searcher._corpus) == 3
        assert len(searcher._corpus_ids) == 3
        assert searcher._bm25 is not None
    
    def test_search_returns_relevant_results(self):
        """Test search returns relevant documents."""
        searcher = BM25Searcher()
        
        documents = [
            {"id": "doc1", "content": "Apple faces litigation risks and legal issues"},
            {"id": "doc2", "content": "Microsoft revenue growth and market expansion"},
            {"id": "doc3", "content": "Legal proceedings and litigation against company"},
        ]
        
        searcher.index_documents(documents)
        results = searcher.search("litigation legal", top_k=2)
        
        assert len(results) == 2
        # Documents with litigation/legal should rank higher
        result_ids = [r["id"] for r in results]
        assert "doc1" in result_ids or "doc3" in result_ids
    
    def test_search_empty_corpus(self):
        """Test search on empty corpus."""
        searcher = BM25Searcher()
        
        results = searcher.search("test query")
        
        assert results == []
    
    def test_search_empty_query(self):
        """Test search with empty query."""
        searcher = BM25Searcher()
        
        documents = [{"id": "doc1", "content": "Some content"}]
        searcher.index_documents(documents)
        
        results = searcher.search("")
        
        assert results == []
    
    def test_get_score_for_document(self):
        """Test getting score for specific document."""
        searcher = BM25Searcher()
        
        # Use a larger corpus to ensure proper BM25 IDF calculation
        documents = [
            {"id": "doc1", "content": "The company faces significant litigation risks and ongoing legal proceedings with multiple lawsuits pending in various jurisdictions"},
            {"id": "doc2", "content": "Revenue growth has been strong with market expansion strategies driving increased sales across all product lines"},
            {"id": "doc3", "content": "The board of directors approved the quarterly dividend payment to shareholders of record"},
            {"id": "doc4", "content": "New product launches are scheduled for next quarter with marketing campaigns planned"},
            {"id": "doc5", "content": "Supply chain disruptions have impacted manufacturing operations and delivery timelines"},
        ]
        
        searcher.index_documents(documents)
        
        score1 = searcher.get_score("litigation legal lawsuits", "doc1")
        score2 = searcher.get_score("litigation legal lawsuits", "doc2")
        
        # doc1 should score higher as it contains the query terms
        assert score1 > score2, f"Expected doc1 score ({score1}) > doc2 score ({score2})"
        # doc1 should have a positive score
        assert score1 > 0, f"Expected doc1 score > 0, got {score1}"
    
    def test_get_score_unknown_document(self):
        """Test getting score for unknown document."""
        searcher = BM25Searcher()
        
        documents = [{"id": "doc1", "content": "test content"}]
        searcher.index_documents(documents)
        
        score = searcher.get_score("test", "unknown_doc")
        
        assert score == 0.0


class TestHybridRetriever:
    """Tests for HybridRetriever."""
    
    def test_initialization_with_defaults(self):
        """Test initialization with default config."""
        retriever = HybridRetriever()
        
        assert retriever.config.semantic_weight == 0.7
        assert retriever.config.keyword_weight == 0.3
        assert retriever._store is None
        assert retriever._embedder is None
    
    def test_initialization_with_custom_config(self):
        """Test initialization with custom config."""
        config = RetrievalConfig(
            semantic_weight=0.6,
            keyword_weight=0.4,
            max_results=20,
        )
        retriever = HybridRetriever(config=config)
        
        assert retriever.config.semantic_weight == 0.6
        assert retriever.config.max_results == 20
    
    def test_initialization_with_injected_dependencies(self):
        """Test initialization with injected store and embedder."""
        mock_store = MagicMock()
        mock_embedder = MagicMock()
        
        retriever = HybridRetriever(store=mock_store, embedder=mock_embedder)
        
        assert retriever._store is mock_store
        assert retriever._embedder is mock_embedder
    
    def test_retrieve_combines_scores(self):
        """Test that retrieve combines semantic and keyword scores."""
        mock_store = MagicMock()
        mock_embedder = MagicMock()
        
        # Setup mock embedder
        mock_embedder.embed_query.return_value = np.random.rand(384)
        
        # Setup mock store with search results
        mock_store.vector_search.return_value = [
            SearchResult(
                id="chunk1",
                content="litigation risks and legal proceedings",
                section_name="1A",
                filing_type="10-K",
                filing_date=date(2024, 1, 15),
                similarity=0.9,
            ),
            SearchResult(
                id="chunk2",
                content="revenue growth and market expansion",
                section_name="7",
                filing_type="10-K",
                filing_date=date(2024, 1, 15),
                similarity=0.7,
            ),
        ]
        
        retriever = HybridRetriever(store=mock_store, embedder=mock_embedder)
        results = retriever.retrieve("litigation risks", ticker="AAPL")
        
        assert len(results) == 2
        # First result should have higher combined score
        assert results[0].combined_score >= results[1].combined_score
        # Verify scores are combined
        assert results[0].semantic_score > 0
        # Verify embedder and store were called
        mock_embedder.embed_query.assert_called_once()
        mock_store.vector_search.assert_called_once()
    
    def test_retrieve_with_filing_type_filter(self):
        """Test retrieval with filing type filter."""
        mock_store = MagicMock()
        mock_embedder = MagicMock()
        mock_embedder.embed_query.return_value = np.random.rand(384)
        mock_store.vector_search.return_value = []
        
        retriever = HybridRetriever(store=mock_store, embedder=mock_embedder)
        retriever.retrieve("test query", ticker="AAPL", filing_types=["10-K"])
        
        # Verify filing_types was passed to vector_search
        call_kwargs = mock_store.vector_search.call_args[1]
        assert call_kwargs["filing_types"] == ["10-K"]
    
    def test_retrieve_with_section_filter(self):
        """Test retrieval with section name filter."""
        mock_store = MagicMock()
        mock_embedder = MagicMock()
        mock_embedder.embed_query.return_value = np.random.rand(384)
        mock_store.vector_search.return_value = []
        
        retriever = HybridRetriever(store=mock_store, embedder=mock_embedder)
        retriever.retrieve("test query", ticker="AAPL", section_names=["1A"])
        
        # Verify section_names was passed to vector_search
        call_kwargs = mock_store.vector_search.call_args[1]
        assert call_kwargs["section_names"] == ["1A"]
    
    def test_retrieve_empty_results(self):
        """Test retrieval with no results."""
        mock_store = MagicMock()
        mock_embedder = MagicMock()
        mock_embedder.embed_query.return_value = np.random.rand(384)
        mock_store.vector_search.return_value = []
        
        retriever = HybridRetriever(store=mock_store, embedder=mock_embedder)
        results = retriever.retrieve("test query", ticker="AAPL")
        
        assert results == []
    
    def test_retrieve_respects_max_results(self):
        """Test that retrieve respects max_results limit."""
        mock_store = MagicMock()
        mock_embedder = MagicMock()
        mock_embedder.embed_query.return_value = np.random.rand(384)
        
        # Return more results than max
        mock_store.vector_search.return_value = [
            SearchResult(
                id=f"chunk{i}",
                content=f"content {i}",
                section_name="1A",
                filing_type="10-K",
                filing_date=date(2024, 1, 15),
                similarity=0.9 - i * 0.1,
            )
            for i in range(10)
        ]
        
        config = RetrievalConfig(max_results=5)
        retriever = HybridRetriever(store=mock_store, embedder=mock_embedder, config=config)
        results = retriever.retrieve("test query", ticker="AAPL")
        
        assert len(results) <= 5


class TestHybridRetrieverSafetyCheck:
    """Tests for safety check retrieval."""
    
    def test_retrieve_for_safety_check_default_aspects(self):
        """Test safety check retrieval uses default aspects."""
        mock_store = MagicMock()
        mock_embedder = MagicMock()
        mock_embedder.embed_query.return_value = np.random.rand(384)
        mock_store.vector_search.return_value = [
            SearchResult(
                id="chunk1",
                content="risk content",
                section_name="1A",
                filing_type="10-K",
                filing_date=date(2024, 1, 15),
                similarity=0.8,
            ),
        ]
        
        retriever = HybridRetriever(store=mock_store, embedder=mock_embedder)
        results = retriever.retrieve_for_safety_check(ticker="AAPL")
        
        # Should have called vector_search multiple times (once per aspect)
        assert mock_store.vector_search.call_count >= 6  # 6 default aspects
    
    def test_retrieve_for_safety_check_custom_aspects(self):
        """Test safety check retrieval with custom aspects."""
        mock_store = MagicMock()
        mock_embedder = MagicMock()
        mock_embedder.embed_query.return_value = np.random.rand(384)
        mock_store.vector_search.return_value = []
        
        retriever = HybridRetriever(store=mock_store, embedder=mock_embedder)
        custom_aspects = ["custom risk 1", "custom risk 2"]
        
        retriever.retrieve_for_safety_check(ticker="AAPL", query_aspects=custom_aspects)
        
        assert mock_store.vector_search.call_count == 2
    
    def test_retrieve_for_safety_check_deduplicates(self):
        """Test that safety check retrieval deduplicates results."""
        mock_store = MagicMock()
        mock_embedder = MagicMock()
        mock_embedder.embed_query.return_value = np.random.rand(384)
        
        # Return same chunk for different queries
        mock_store.vector_search.return_value = [
            SearchResult(
                id="same_chunk",
                content="risk content",
                section_name="1A",
                filing_type="10-K",
                filing_date=date(2024, 1, 15),
                similarity=0.8,
            ),
        ]
        
        retriever = HybridRetriever(store=mock_store, embedder=mock_embedder)
        results = retriever.retrieve_for_safety_check(
            ticker="AAPL",
            query_aspects=["aspect1", "aspect2", "aspect3"]
        )
        
        # Should only have one result despite multiple queries returning same chunk
        assert len(results) == 1
        assert results[0].chunk_id == "same_chunk"


class TestHybridRetrieverConvenienceMethods:
    """Tests for convenience retrieval methods."""
    
    def test_retrieve_by_section(self):
        """Test retrieve_by_section method."""
        mock_store = MagicMock()
        mock_embedder = MagicMock()
        mock_embedder.embed_query.return_value = np.random.rand(384)
        mock_store.vector_search.return_value = []
        
        retriever = HybridRetriever(store=mock_store, embedder=mock_embedder)
        retriever.retrieve_by_section(
            query="test",
            ticker="AAPL",
            section_name="1A",
            filing_type="10-K",
        )
        
        call_kwargs = mock_store.vector_search.call_args[1]
        assert call_kwargs["section_names"] == ["1A"]
        assert call_kwargs["filing_types"] == ["10-K"]
    
    def test_retrieve_risk_factors(self):
        """Test retrieve_risk_factors convenience method."""
        mock_store = MagicMock()
        mock_embedder = MagicMock()
        mock_embedder.embed_query.return_value = np.random.rand(384)
        mock_store.vector_search.return_value = []
        
        retriever = HybridRetriever(store=mock_store, embedder=mock_embedder)
        retriever.retrieve_risk_factors(query="litigation", ticker="AAPL")
        
        call_kwargs = mock_store.vector_search.call_args[1]
        assert call_kwargs["section_names"] == ["1A"]
        assert call_kwargs["filing_types"] == ["10-K"]
    
    def test_retrieve_mda_10k(self):
        """Test retrieve_mda for 10-K filings."""
        mock_store = MagicMock()
        mock_embedder = MagicMock()
        mock_embedder.embed_query.return_value = np.random.rand(384)
        mock_store.vector_search.return_value = []
        
        retriever = HybridRetriever(store=mock_store, embedder=mock_embedder)
        retriever.retrieve_mda(query="revenue", ticker="AAPL", filing_type="10-K")
        
        call_kwargs = mock_store.vector_search.call_args[1]
        assert call_kwargs["section_names"] == ["7"]  # Item 7 in 10-K
    
    def test_retrieve_mda_10q(self):
        """Test retrieve_mda for 10-Q filings."""
        mock_store = MagicMock()
        mock_embedder = MagicMock()
        mock_embedder.embed_query.return_value = np.random.rand(384)
        mock_store.vector_search.return_value = []
        
        retriever = HybridRetriever(store=mock_store, embedder=mock_embedder)
        retriever.retrieve_mda(query="revenue", ticker="AAPL", filing_type="10-Q")
        
        call_kwargs = mock_store.vector_search.call_args[1]
        assert call_kwargs["section_names"] == ["2"]  # Item 2 in 10-Q


class TestRetrievalResult:
    """Tests for RetrievalResult dataclass."""
    
    def test_retrieval_result_creation(self):
        """Test creating a retrieval result."""
        result = RetrievalResult(
            chunk_id="chunk1",
            content="test content",
            section_name="1A",
            filing_type="10-K",
            filing_date=date(2024, 1, 15),
            ticker="AAPL",
            semantic_score=0.9,
            keyword_score=0.5,
            combined_score=0.78,
        )
        
        assert result.chunk_id == "chunk1"
        assert result.semantic_score == 0.9
        assert result.keyword_score == 0.5
        assert result.combined_score == 0.78
    
    def test_retrieval_result_default_scores(self):
        """Test retrieval result default score values."""
        result = RetrievalResult(
            chunk_id="chunk1",
            content="test",
            section_name="1A",
            filing_type="10-K",
            filing_date=date(2024, 1, 15),
            ticker="AAPL",
        )
        
        assert result.semantic_score == 0.0
        assert result.keyword_score == 0.0
        assert result.combined_score == 0.0
        assert result.metadata == {}


class TestIntegration:
    """Integration-style tests for the hybrid retrieval system."""
    
    def test_full_retrieval_pipeline(self):
        """Test the full retrieval pipeline with mocked dependencies."""
        mock_store = MagicMock()
        mock_embedder = MagicMock()
        
        # Setup embedder
        mock_embedder.embed_query.return_value = np.random.rand(384)
        
        # Setup store with realistic results
        mock_store.vector_search.return_value = [
            SearchResult(
                id="chunk1",
                content="The company faces significant litigation risks including ongoing lawsuits related to patent infringement.",
                section_name="1A",
                filing_type="10-K",
                filing_date=date(2024, 1, 15),
                similarity=0.92,
            ),
            SearchResult(
                id="chunk2",
                content="Legal proceedings may result in material adverse effects on our financial condition.",
                section_name="1A",
                filing_type="10-K",
                filing_date=date(2024, 1, 15),
                similarity=0.85,
            ),
            SearchResult(
                id="chunk3",
                content="Revenue increased by 15% compared to the prior year period.",
                section_name="7",
                filing_type="10-K",
                filing_date=date(2024, 1, 15),
                similarity=0.45,
            ),
        ]
        
        retriever = HybridRetriever(store=mock_store, embedder=mock_embedder)
        results = retriever.retrieve("litigation risks", ticker="AAPL")
        
        # Verify results are properly ranked
        assert len(results) == 3
        
        # First two results should have higher combined scores (contain litigation/legal)
        assert results[0].combined_score > results[2].combined_score
        
        # Verify all fields are populated
        for result in results:
            assert result.chunk_id is not None
            assert result.content is not None
            assert result.semantic_score > 0
            assert result.combined_score > 0
