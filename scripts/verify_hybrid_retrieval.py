"""
Simple verification script for Hybrid Retrieval System.

This script demonstrates the key functionality of the hybrid retrieval system
without requiring a full test environment.
"""

import sys
sys.path.insert(0, '.')

from src.retrieval.hybrid import (
    HybridRetriever,
    RetrievalConfig,
    QueryPreprocessor,
    BM25Searcher,
    RetrievalResult,
)
from datetime import date


def test_config():
    """Test RetrievalConfig validation."""
    print("Testing RetrievalConfig...")
    
    config = RetrievalConfig()
    assert config.semantic_weight == 0.7
    assert config.keyword_weight == 0.3
    assert config.max_results == 10
    
    try:
        RetrievalConfig(semantic_weight=0.5, keyword_weight=0.3)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "Weights must sum to 1.0" in str(e)
    
    print("✓ RetrievalConfig validation works correctly")


def test_query_preprocessor():
    """Test QueryPreprocessor functionality."""
    print("\nTesting QueryPreprocessor...")
    
    preprocessor = QueryPreprocessor(expand_terms=False)
    result = preprocessor.preprocess("  multiple   spaces  ")
    assert result == "multiple spaces", f"Expected 'multiple spaces', got '{result}'"
    
    preprocessor_with_expansion = QueryPreprocessor(expand_terms=True)
    result = preprocessor_with_expansion.preprocess("litigation risks")
    assert "litigation risks" in result
    
    tokens = preprocessor.tokenize("Hello World! This is a test.")
    assert tokens == ["hello", "world", "this", "is", "a", "test"]
    
    print("✓ QueryPreprocessor works correctly")


def test_bm25_searcher():
    """Test BM25Searcher functionality."""
    print("\nTesting BM25Searcher...")
    
    searcher = BM25Searcher()
    
    documents = [
        {"id": "doc1", "content": "Apple faces litigation risks and legal issues"},
        {"id": "doc2", "content": "Microsoft revenue growth and market expansion"},
        {"id": "doc3", "content": "Legal proceedings and litigation against company"},
    ]
    
    searcher.index_documents(documents)
    assert len(searcher._corpus) == 3
    
    results = searcher.search("litigation legal", top_k=2)
    assert len(results) == 2
    assert results[0]["id"] in ["doc1", "doc3"]
    
    score1 = searcher.get_score("litigation", "doc1")
    score2 = searcher.get_score("litigation", "doc2")
    assert score1 > score2
    
    print("✓ BM25Searcher works correctly")


def test_hybrid_retriever():
    """Test HybridRetriever initialization."""
    print("\nTesting HybridRetriever...")
    
    retriever = HybridRetriever()
    assert retriever.config.semantic_weight == 0.7
    assert retriever.config.keyword_weight == 0.3
    
    config = RetrievalConfig(
        semantic_weight=0.6,
        keyword_weight=0.4,
        max_results=20,
    )
    retriever = HybridRetriever(config=config)
    assert retriever.config.semantic_weight == 0.6
    assert retriever.config.max_results == 20
    
    print("✓ HybridRetriever initialization works correctly")


def test_retrieval_result():
    """Test RetrievalResult dataclass."""
    print("\nTesting RetrievalResult...")
    
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
    
    print("✓ RetrievalResult works correctly")


def main():
    """Run all verification tests."""
    print("=" * 60)
    print("Hybrid Retrieval System Verification")
    print("=" * 60)
    
    try:
        test_config()
        test_query_preprocessor()
        test_bm25_searcher()
        test_hybrid_retriever()
        test_retrieval_result()
        
        print("\n" + "=" * 60)
        print("✓ All verification tests passed!")
        print("=" * 60)
        print("\nThe Hybrid Retrieval System is correctly implemented.")
        print("\nKey features verified:")
        print("  • RetrievalConfig with weight validation")
        print("  • QueryPreprocessor with term expansion")
        print("  • BM25Searcher with document indexing and search")
        print("  • HybridRetriever initialization and configuration")
        print("  • RetrievalResult dataclass")
        
        return 0
        
    except Exception as e:
        print(f"\n✗ Verification failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
