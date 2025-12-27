"""
Hybrid Retrieval System for SEC Filing RAG.

Combines semantic (vector) search with BM25 keyword search for improved retrieval.
Uses configurable weights for score fusion and supports filtering by filing type and section.
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Set
from datetime import date
import numpy as np

from rank_bm25 import BM25Okapi


@dataclass
class RetrievalResult:
    """Result from hybrid retrieval."""
    chunk_id: str
    content: str
    section_name: str
    filing_type: str
    filing_date: date
    ticker: str
    
    # Scores
    semantic_score: float = 0.0
    keyword_score: float = 0.0
    combined_score: float = 0.0
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RetrievalConfig:
    """Configuration for hybrid retrieval."""
    semantic_weight: float = 0.7
    keyword_weight: float = 0.3
    max_results: int = 10
    days_back: int = 365
    min_score_threshold: float = 0.0
    
    def __post_init__(self):
        """Validate weights sum to 1.0."""
        total = self.semantic_weight + self.keyword_weight
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"Weights must sum to 1.0, got {total}")


class QueryPreprocessor:
    """Preprocesses queries for improved retrieval."""
    
    # Financial domain stopwords to potentially remove
    DOMAIN_STOPWORDS = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been",
        "being", "have", "has", "had", "do", "does", "did", "will",
        "would", "could", "should", "may", "might", "must", "shall",
    }
    
    # Query expansion mappings for financial terms
    TERM_EXPANSIONS = {
        "risk": ["risks", "risk factors", "uncertainties", "exposure"],
        "litigation": ["lawsuit", "legal proceedings", "legal action", "court"],
        "revenue": ["sales", "income", "earnings", "net sales"],
        "debt": ["borrowings", "obligations", "liabilities", "loans"],
        "competition": ["competitors", "competitive", "market competition"],
        "regulation": ["regulatory", "compliance", "government", "legal requirements"],
        "cybersecurity": ["cyber", "security breach", "data breach", "hacking"],
        "supply chain": ["suppliers", "supply disruption", "logistics"],
        "earnings": ["quarterly results", "financial results", "net income"],
        "guidance": ["outlook", "forecast", "projections", "expectations"],
    }
    
    def __init__(self, expand_terms: bool = True, remove_stopwords: bool = False):
        """
        Initialize preprocessor.
        
        Args:
            expand_terms: Whether to expand financial terms
            remove_stopwords: Whether to remove common stopwords
        """
        self.expand_terms = expand_terms
        self.remove_stopwords = remove_stopwords
    
    def preprocess(self, query: str) -> str:
        """
        Preprocess a query for retrieval.
        
        Args:
            query: Raw query string
            
        Returns:
            Preprocessed query
        """
        # Normalize whitespace
        query = " ".join(query.split())
        
        # Lowercase for matching
        query_lower = query.lower()
        
        # Expand terms if enabled
        if self.expand_terms:
            expanded_terms = []
            for term, expansions in self.TERM_EXPANSIONS.items():
                if term in query_lower:
                    expanded_terms.extend(expansions[:2])  # Add top 2 expansions
            
            if expanded_terms:
                query = f"{query} {' '.join(expanded_terms)}"
        
        return query
    
    def tokenize(self, text: str) -> List[str]:
        """
        Tokenize text for BM25.
        
        Args:
            text: Text to tokenize
            
        Returns:
            List of tokens
        """
        # Simple tokenization: lowercase, split on non-alphanumeric
        tokens = re.findall(r'\b[a-zA-Z0-9]+\b', text.lower())
        
        # Remove stopwords if enabled
        if self.remove_stopwords:
            tokens = [t for t in tokens if t not in self.DOMAIN_STOPWORDS]
        
        return tokens


class BM25Searcher:
    """BM25 keyword search implementation."""
    
    def __init__(self, preprocessor: Optional[QueryPreprocessor] = None):
        """
        Initialize BM25 searcher.
        
        Args:
            preprocessor: Query preprocessor instance
        """
        self.preprocessor = preprocessor or QueryPreprocessor()
        self._corpus: List[str] = []
        self._corpus_ids: List[str] = []
        self._bm25: Optional[BM25Okapi] = None
    
    def index_documents(self, documents: List[Dict[str, Any]]) -> None:
        """
        Index documents for BM25 search.
        
        Args:
            documents: List of documents with 'id' and 'content' keys
        """
        self._corpus = []
        self._corpus_ids = []
        tokenized_corpus = []
        
        for doc in documents:
            self._corpus.append(doc["content"])
            self._corpus_ids.append(doc["id"])
            tokens = self.preprocessor.tokenize(doc["content"])
            tokenized_corpus.append(tokens)
        
        if tokenized_corpus:
            self._bm25 = BM25Okapi(tokenized_corpus)
    
    def search(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """
        Search indexed documents.
        
        Args:
            query: Search query
            top_k: Number of results to return
            
        Returns:
            List of results with id and score
        """
        if not self._bm25 or not self._corpus:
            return []
        
        # Tokenize query
        query_tokens = self.preprocessor.tokenize(query)
        
        if not query_tokens:
            return []
        
        # Get BM25 scores
        scores = self._bm25.get_scores(query_tokens)
        
        # Get top-k indices
        top_indices = np.argsort(scores)[::-1][:top_k]
        
        results = []
        for idx in top_indices:
            if scores[idx] > 0:
                results.append({
                    "id": self._corpus_ids[idx],
                    "content": self._corpus[idx],
                    "score": float(scores[idx]),
                })
        
        return results
    
    def get_score(self, query: str, doc_id: str) -> float:
        """
        Get BM25 score for a specific document.
        
        Args:
            query: Search query
            doc_id: Document ID
            
        Returns:
            BM25 score (0.0 if not found)
        """
        if not self._bm25 or doc_id not in self._corpus_ids:
            return 0.0
        
        query_tokens = self.preprocessor.tokenize(query)
        if not query_tokens:
            return 0.0
        
        idx = self._corpus_ids.index(doc_id)
        scores = self._bm25.get_scores(query_tokens)
        return float(scores[idx])


class HybridRetriever:
    """
    Hybrid retrieval combining semantic and keyword search.
    
    Uses configurable weights (default 70% semantic, 30% keyword) to combine
    vector similarity scores with BM25 keyword scores.
    """
    
    def __init__(
        self,
        store=None,
        embedder=None,
        config: Optional[RetrievalConfig] = None
    ):
        """
        Initialize hybrid retriever.
        
        Args:
            store: SupabaseStore instance for vector search
            embedder: LocalEmbedder instance for query embedding
            config: Retrieval configuration
        """
        self._store = store
        self._embedder = embedder
        self.config = config or RetrievalConfig()
        self.preprocessor = QueryPreprocessor()
        self.bm25_searcher = BM25Searcher(self.preprocessor)
    
    @property
    def store(self):
        """Lazy load store."""
        if self._store is None:
            from src.data.store import SupabaseStore
            self._store = SupabaseStore()
        return self._store
    
    @property
    def embedder(self):
        """Lazy load embedder."""
        if self._embedder is None:
            from src.embeddings.embedder import LocalEmbedder
            self._embedder = LocalEmbedder()
        return self._embedder
    
    def retrieve(
        self,
        query: str,
        ticker: str,
        filing_types: Optional[List[str]] = None,
        section_names: Optional[List[str]] = None,
        max_results: Optional[int] = None,
        days_back: Optional[int] = None
    ) -> List[RetrievalResult]:
        """
        Perform hybrid retrieval combining semantic and keyword search.
        
        Args:
            query: Search query
            ticker: Stock ticker to search
            filing_types: Optional list of filing types to filter (e.g., ["10-K"])
            section_names: Optional list of section names to filter (e.g., ["1A"])
            max_results: Override default max results
            days_back: Override default days back
            
        Returns:
            List of retrieval results ranked by combined score
        """
        max_results = max_results or self.config.max_results
        days_back = days_back or self.config.days_back
        
        # Preprocess query
        processed_query = self.preprocessor.preprocess(query)
        
        # Step 1: Semantic search via vector similarity
        query_embedding = self.embedder.embed_query(processed_query)
        
        # Fetch more results for reranking
        fetch_count = max_results * 3
        
        semantic_results = self.store.vector_search(
            query_embedding=query_embedding,
            ticker=ticker,
            match_count=fetch_count,
            days_back=days_back,
            filing_types=filing_types,
            section_names=section_names,
        )
        
        if not semantic_results:
            return []
        
        # Step 2: Build BM25 index from semantic results
        documents = [
            {"id": r.id, "content": r.content}
            for r in semantic_results
        ]
        self.bm25_searcher.index_documents(documents)
        
        # Step 3: Get BM25 scores for the query
        bm25_results = self.bm25_searcher.search(query, top_k=len(documents))
        bm25_scores = {r["id"]: r["score"] for r in bm25_results}
        
        # Normalize BM25 scores to 0-1 range
        if bm25_scores:
            max_bm25 = max(bm25_scores.values()) if bm25_scores.values() else 1.0
            if max_bm25 > 0:
                bm25_scores = {k: v / max_bm25 for k, v in bm25_scores.items()}
        
        # Step 4: Combine scores and create results
        results = []
        for sr in semantic_results:
            semantic_score = sr.similarity
            keyword_score = bm25_scores.get(sr.id, 0.0)
            
            combined_score = (
                self.config.semantic_weight * semantic_score +
                self.config.keyword_weight * keyword_score
            )
            
            if combined_score >= self.config.min_score_threshold:
                results.append(RetrievalResult(
                    chunk_id=sr.id,
                    content=sr.content,
                    section_name=sr.section_name,
                    filing_type=sr.filing_type,
                    filing_date=sr.filing_date,
                    ticker=ticker,
                    semantic_score=semantic_score,
                    keyword_score=keyword_score,
                    combined_score=combined_score,
                ))
        
        # Step 5: Sort by combined score and limit results
        results.sort(key=lambda x: x.combined_score, reverse=True)
        return results[:max_results]
    
    def retrieve_for_safety_check(
        self,
        ticker: str,
        query_aspects: Optional[List[str]] = None,
        max_results_per_aspect: int = 5
    ) -> List[RetrievalResult]:
        """
        Multi-faceted retrieval for comprehensive safety analysis.
        
        Retrieves chunks covering multiple risk aspects for thorough analysis.
        
        Args:
            ticker: Stock ticker to analyze
            query_aspects: List of aspects to query (default: standard risk aspects)
            max_results_per_aspect: Results per aspect query
            
        Returns:
            Deduplicated list of retrieval results from all aspects
        """
        # Default risk aspects for safety analysis
        if query_aspects is None:
            query_aspects = [
                "litigation risks and legal proceedings",
                "regulatory risks and compliance issues",
                "financial risks and debt obligations",
                "competitive risks and market position",
                "operational risks and supply chain",
                "cybersecurity and data privacy risks",
            ]
        
        all_results: Dict[str, RetrievalResult] = {}
        
        for aspect in query_aspects:
            aspect_results = self.retrieve(
                query=aspect,
                ticker=ticker,
                filing_types=["10-K", "10-Q"],  # Focus on periodic filings
                section_names=["1A", "7", "7A"],  # Risk factors and MD&A
                max_results=max_results_per_aspect,
            )
            
            # Deduplicate by chunk_id, keeping highest score
            for result in aspect_results:
                if result.chunk_id not in all_results:
                    all_results[result.chunk_id] = result
                elif result.combined_score > all_results[result.chunk_id].combined_score:
                    all_results[result.chunk_id] = result
        
        # Sort by combined score
        results = list(all_results.values())
        results.sort(key=lambda x: x.combined_score, reverse=True)
        
        return results
    
    def retrieve_by_section(
        self,
        query: str,
        ticker: str,
        section_name: str,
        filing_type: Optional[str] = None,
        max_results: int = 10
    ) -> List[RetrievalResult]:
        """
        Retrieve from a specific section.
        
        Args:
            query: Search query
            ticker: Stock ticker
            section_name: Section to search (e.g., "1A" for Risk Factors)
            filing_type: Optional filing type filter
            max_results: Maximum results
            
        Returns:
            List of retrieval results from the specified section
        """
        filing_types = [filing_type] if filing_type else None
        
        return self.retrieve(
            query=query,
            ticker=ticker,
            filing_types=filing_types,
            section_names=[section_name],
            max_results=max_results,
        )
    
    def retrieve_risk_factors(
        self,
        query: str,
        ticker: str,
        max_results: int = 10
    ) -> List[RetrievalResult]:
        """
        Convenience method to retrieve from Risk Factors section (Item 1A).
        
        Args:
            query: Search query
            ticker: Stock ticker
            max_results: Maximum results
            
        Returns:
            List of retrieval results from Risk Factors
        """
        return self.retrieve_by_section(
            query=query,
            ticker=ticker,
            section_name="1A",
            filing_type="10-K",
            max_results=max_results,
        )
    
    def retrieve_mda(
        self,
        query: str,
        ticker: str,
        filing_type: str = "10-K",
        max_results: int = 10
    ) -> List[RetrievalResult]:
        """
        Convenience method to retrieve from MD&A section.
        
        Args:
            query: Search query
            ticker: Stock ticker
            filing_type: "10-K" (Item 7) or "10-Q" (Item 2)
            max_results: Maximum results
            
        Returns:
            List of retrieval results from MD&A
        """
        # MD&A is Item 7 in 10-K, Item 2 in 10-Q
        section = "7" if filing_type == "10-K" else "2"
        
        return self.retrieve_by_section(
            query=query,
            ticker=ticker,
            section_name=section,
            filing_type=filing_type,
            max_results=max_results,
        )
