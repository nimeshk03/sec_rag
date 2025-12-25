#!/usr/bin/env python3
"""
Data Population Script for SEC Filing RAG System.

Downloads SEC filings, parses them, generates embeddings, and stores in Supabase.

Usage:
    python scripts/populate_data.py [--tickers AAPL,MSFT] [--dry-run] [--skip-embeddings]
"""

import argparse
import logging
import sys
import os
from datetime import date
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.sec_downloader import SECDownloader, FilingInfo
from src.data.parser import SECFilingParser
from src.data.chunker import FilingChunker
from src.data.store import SupabaseStore, Filing, Chunk

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


@dataclass
class PopulationStats:
    """Statistics from data population run."""
    tickers_processed: int = 0
    filings_downloaded: int = 0
    filings_stored: int = 0
    chunks_created: int = 0
    chunks_with_embeddings: int = 0
    errors: List[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "tickers_processed": self.tickers_processed,
            "filings_downloaded": self.filings_downloaded,
            "filings_stored": self.filings_stored,
            "chunks_created": self.chunks_created,
            "chunks_with_embeddings": self.chunks_with_embeddings,
            "errors": self.errors,
        }


class DataPopulator:
    """
    Orchestrates the data population pipeline.
    
    Pipeline:
    1. Download filings from SEC EDGAR
    2. Parse filings to extract sections
    3. Chunk sections into smaller pieces
    4. Generate embeddings for chunks
    5. Store everything in Supabase
    """
    
    def __init__(
        self,
        user_agent: str = "SEC-RAG-System admin@example.com",
        chunk_size: int = 800,
        chunk_overlap: int = 100,
        skip_embeddings: bool = False,
        dry_run: bool = False,
    ):
        """
        Initialize the data populator.
        
        Args:
            user_agent: User agent for SEC requests
            chunk_size: Target chunk size in characters
            chunk_overlap: Overlap between chunks
            skip_embeddings: If True, skip embedding generation
            dry_run: If True, don't store to database
        """
        self.downloader = SECDownloader(user_agent=user_agent)
        self.parser = SECFilingParser()
        self.chunker = FilingChunker(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        self.skip_embeddings = skip_embeddings
        self.dry_run = dry_run
        
        # Lazy load store and embedder
        self._store = None
        self._embedder = None
    
    @property
    def store(self) -> SupabaseStore:
        """Lazy load Supabase store."""
        if self._store is None and not self.dry_run:
            self._store = SupabaseStore()
        return self._store
    
    @property
    def embedder(self):
        """Lazy load embedder."""
        if self._embedder is None and not self.skip_embeddings:
            from src.embeddings import LocalEmbedder
            self._embedder = LocalEmbedder()
        return self._embedder
    
    def process_filing(
        self,
        filing_info: FilingInfo,
        content: str,
        stats: PopulationStats
    ) -> Optional[str]:
        """
        Process a single filing through the pipeline.
        
        Args:
            filing_info: Filing metadata
            content: Raw HTML content
            stats: Stats object to update
            
        Returns:
            Filing ID if successful, None otherwise
        """
        try:
            # Parse the filing
            if filing_info.filing_type == "10-K":
                sections = self.parser.parse_10k(content)
            elif filing_info.filing_type == "10-Q":
                sections = self.parser.parse_10q(content)
            elif filing_info.filing_type == "8-K":
                sections = self.parser.parse_8k(content)
            else:
                logger.warning(f"Unknown filing type: {filing_info.filing_type}")
                return None
            
            if not sections:
                logger.warning(f"No sections extracted from {filing_info.ticker} {filing_info.filing_type}")
                return None
            
            # Create chunks - sections is a Dict[str, ParsedSection]
            all_chunks = self.chunker.chunk_filing(
                sections={section_id: section.content for section_id, section in sections.items()},
                filing_type=filing_info.filing_type,
                ticker=filing_info.ticker,
            )
            
            if not all_chunks:
                logger.warning(f"No chunks created for {filing_info.ticker} {filing_info.filing_type}")
                return None
            
            logger.info(f"Created {len(all_chunks)} chunks for {filing_info.ticker} {filing_info.filing_type}")
            
            if self.dry_run:
                stats.chunks_created += len(all_chunks)
                return "dry-run-id"
            
            # Store filing metadata
            filing = Filing(
                ticker=filing_info.ticker,
                filing_type=filing_info.filing_type,
                filing_date=filing_info.filing_date,
                accession_number=filing_info.accession_number,
                source_url=filing_info.filing_url,
            )
            
            filing_id = self.store.insert_filing(filing)
            stats.filings_stored += 1
            
            # Generate embeddings if not skipped
            chunk_objects = []
            for i, chunk in enumerate(all_chunks):
                embedding = None
                if not self.skip_embeddings and self.embedder:
                    embedding = self.embedder.embed_text(chunk.text)
                    stats.chunks_with_embeddings += 1
                
                chunk_objects.append(Chunk(
                    filing_id=filing_id,
                    section_name=chunk.metadata.get("section_id", "unknown"),
                    content=chunk.text,
                    chunk_index=chunk.metadata.get("chunk_index", i),
                    embedding=embedding,
                    total_chunks=len(all_chunks),
                    word_count=len(chunk.text.split()),
                ))
            
            # Store chunks
            self.store.insert_chunks(chunk_objects)
            stats.chunks_created += len(chunk_objects)
            
            return filing_id
            
        except Exception as e:
            error_msg = f"Error processing {filing_info.ticker} {filing_info.filing_type}: {e}"
            logger.error(error_msg)
            stats.errors.append(error_msg)
            return None
    
    def populate_ticker(
        self,
        ticker: str,
        include_10k: bool = True,
        include_10q: bool = True,
        include_8k: bool = True,
        days_back_8k: int = 30,
        stats: Optional[PopulationStats] = None
    ) -> PopulationStats:
        """
        Populate data for a single ticker.
        
        Args:
            ticker: Stock ticker symbol
            include_10k: Include latest 10-K
            include_10q: Include latest 10-Q
            include_8k: Include 8-K filings
            days_back_8k: Days to look back for 8-K
            stats: Optional stats object to update
            
        Returns:
            PopulationStats with results
        """
        if stats is None:
            stats = PopulationStats()
        
        logger.info(f"Processing ticker: {ticker}")
        
        # Download filings
        filings = self.downloader.download_latest_filings(
            ticker=ticker,
            include_10k=include_10k,
            include_10q=include_10q,
            include_8k=include_8k,
            days_back_8k=days_back_8k,
        )
        
        # Process each filing type
        for filing_type, filing_list in filings.items():
            for filing_data in filing_list:
                stats.filings_downloaded += 1
                self.process_filing(
                    filing_info=filing_data["info"],
                    content=filing_data["content"],
                    stats=stats,
                )
        
        stats.tickers_processed += 1
        return stats
    
    def populate_all(
        self,
        tickers: Optional[List[str]] = None,
        include_10k: bool = True,
        include_10q: bool = True,
        include_8k: bool = True,
        days_back_8k: int = 30,
    ) -> PopulationStats:
        """
        Populate data for all tickers.
        
        Args:
            tickers: List of tickers (default: all supported)
            include_10k: Include latest 10-K
            include_10q: Include latest 10-Q
            include_8k: Include 8-K filings
            days_back_8k: Days to look back for 8-K
            
        Returns:
            PopulationStats with results
        """
        if tickers is None:
            tickers = SECDownloader.get_supported_tickers()
        
        stats = PopulationStats()
        
        logger.info(f"Starting data population for {len(tickers)} tickers")
        logger.info(f"Tickers: {', '.join(tickers)}")
        logger.info(f"Options: 10-K={include_10k}, 10-Q={include_10q}, 8-K={include_8k}")
        
        if self.dry_run:
            logger.info("DRY RUN MODE - No data will be stored")
        
        if self.skip_embeddings:
            logger.info("SKIP EMBEDDINGS MODE - No embeddings will be generated")
        
        for ticker in tickers:
            try:
                self.populate_ticker(
                    ticker=ticker,
                    include_10k=include_10k,
                    include_10q=include_10q,
                    include_8k=include_8k,
                    days_back_8k=days_back_8k,
                    stats=stats,
                )
            except Exception as e:
                error_msg = f"Failed to process ticker {ticker}: {e}"
                logger.error(error_msg)
                stats.errors.append(error_msg)
        
        logger.info("=" * 50)
        logger.info("Population Complete!")
        logger.info(f"Tickers processed: {stats.tickers_processed}")
        logger.info(f"Filings downloaded: {stats.filings_downloaded}")
        logger.info(f"Filings stored: {stats.filings_stored}")
        logger.info(f"Chunks created: {stats.chunks_created}")
        logger.info(f"Chunks with embeddings: {stats.chunks_with_embeddings}")
        if stats.errors:
            logger.warning(f"Errors: {len(stats.errors)}")
            for error in stats.errors:
                logger.warning(f"  - {error}")
        
        return stats


def main():
    """Main entry point for the population script."""
    parser = argparse.ArgumentParser(
        description="Populate SEC filing data for RAG system"
    )
    parser.add_argument(
        "--tickers",
        type=str,
        help="Comma-separated list of tickers (default: all supported)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't store to database, just show what would be done",
    )
    parser.add_argument(
        "--skip-embeddings",
        action="store_true",
        help="Skip embedding generation (faster for testing)",
    )
    parser.add_argument(
        "--no-10k",
        action="store_true",
        help="Skip 10-K filings",
    )
    parser.add_argument(
        "--no-10q",
        action="store_true",
        help="Skip 10-Q filings",
    )
    parser.add_argument(
        "--no-8k",
        action="store_true",
        help="Skip 8-K filings",
    )
    parser.add_argument(
        "--days-back-8k",
        type=int,
        default=30,
        help="Days to look back for 8-K filings (default: 30)",
    )
    parser.add_argument(
        "--user-agent",
        type=str,
        default="SEC-RAG-System admin@example.com",
        help="User agent for SEC requests",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=800,
        help="Target chunk size in characters (default: 800)",
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=100,
        help="Overlap between chunks (default: 100)",
    )
    
    args = parser.parse_args()
    
    # Parse tickers
    tickers = None
    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(",")]
    
    # Create populator
    populator = DataPopulator(
        user_agent=args.user_agent,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        skip_embeddings=args.skip_embeddings,
        dry_run=args.dry_run,
    )
    
    # Run population
    stats = populator.populate_all(
        tickers=tickers,
        include_10k=not args.no_10k,
        include_10q=not args.no_10q,
        include_8k=not args.no_8k,
        days_back_8k=args.days_back_8k,
    )
    
    # Exit with error code if there were failures
    if stats.errors:
        sys.exit(1)
    
    return stats


if __name__ == "__main__":
    main()
