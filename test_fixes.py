"""Quick test to verify the two failing tests are now fixed."""

import sys
sys.path.insert(0, '.')

from datetime import date
from unittest.mock import MagicMock
import numpy as np

from src.retrieval.hybrid import BM25Searcher, HybridRetriever
from src.data.store import SearchResult


def test_bm25_score():
    """Test BM25 scoring with distinctive content."""
    print("Testing BM25 scoring...")
    
    searcher = BM25Searcher()
    
    documents = [
        {"id": "doc1", "content": "litigation risks and legal proceedings with lawsuits"},
        {"id": "doc2", "content": "revenue growth and market expansion strategies"},
    ]
    
    searcher.index_documents(documents)
    
    score1 = searcher.get_score("litigation legal", "doc1")
    score2 = searcher.get_score("litigation legal", "doc2")
    
    print(f"  Score for doc1 (contains query terms): {score1}")
    print(f"  Score for doc2 (doesn't contain query terms): {score2}")
    
    assert score1 >= score2, f"Expected score1 ({score1}) >= score2 ({score2})"
    assert score1 > 0, f"Expected score1 > 0, got {score1}"
    
    print("  ✓ BM25 scoring test passed!")


def test_retrieve_combines_scores():
    """Test that retrieve combines semantic and keyword scores."""
    print("\nTesting hybrid retrieval score combination...")
    
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
    
    print(f"  Number of results: {len(results)}")
    if results:
        print(f"  Result 1 - Combined: {results[0].combined_score:.3f}, Semantic: {results[0].semantic_score:.3f}, Keyword: {results[0].keyword_score:.3f}")
        if len(results) > 1:
            print(f"  Result 2 - Combined: {results[1].combined_score:.3f}, Semantic: {results[1].semantic_score:.3f}, Keyword: {results[1].keyword_score:.3f}")
    
    assert len(results) == 2, f"Expected 2 results, got {len(results)}"
    assert results[0].combined_score >= results[1].combined_score
    assert results[0].semantic_score > 0
    
    print("  ✓ Hybrid retrieval test passed!")


if __name__ == "__main__":
    try:
        test_bm25_score()
        test_retrieve_combines_scores()
        print("\n" + "=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)
        sys.exit(0)
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
