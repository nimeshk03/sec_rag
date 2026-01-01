#!/usr/bin/env python3
"""
Script to download and index SEC filings for multiple tickers.
This populates the database with actual filing data for testing.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.data.sec_downloader import SECDownloader
from src.data.parser import SECFilingParser
from src.data.chunker import TextChunker
from src.embeddings.embedder import LocalEmbedder
from src.data.store import SupabaseStore
from datetime import datetime

# Tickers to index
TICKERS = ["AAPL", "MSFT", "GOOGL", "TSLA", "AMZN"]

# Filing types to download
FILING_TYPES = ["10-K"]  # Start with annual reports

def index_ticker(ticker: str, filing_type: str = "10-K"):
    """Download and index the latest filing for a ticker."""
    print(f"\n{'='*60}")
    print(f"Processing {ticker} - {filing_type}")
    print(f"{'='*60}")
    
    try:
        # Initialize components
        downloader = SECDownloader()
        parser = SECFilingParser()
        chunker = TextChunker()
        embedder = LocalEmbedder()
        store = SupabaseStore()
        
        # Get CIK for ticker
        cik = downloader.get_cik(ticker)
        if not cik:
            print(f"❌ Could not find CIK for {ticker}")
            return False
        
        print(f"✓ Found CIK: {cik}")
        
        # Get latest filing
        print(f"Fetching latest {filing_type} filing...")
        filing_info = downloader.get_latest_filing(ticker, filing_type)
        
        if not filing_info:
            print(f"❌ No {filing_type} filing found for {ticker}")
            return False
        
        print(f"✓ Found filing: {filing_info.accession_number}")
        print(f"  Date: {filing_info.filing_date}")
        
        # Download filing content
        print("Downloading filing content...")
        filing_html = downloader.download_filing(filing_info.filing_url)
        
        if not filing_html:
            print(f"❌ Failed to download filing")
            return False
        
        print(f"✓ Downloaded {len(filing_html)} bytes")
        
        # Parse filing
        print("Parsing filing sections...")
        sections = parser.parse(filing_html, filing_type)
        
        if not sections:
            print(f"❌ No sections parsed from filing")
            return False
        
        print(f"✓ Parsed {len(sections)} sections")
        for section in sections:
            print(f"  - {section.section_name}: {len(section.content)} chars")
        
        # Store filing metadata
        print("Storing filing metadata...")
        filing_id = store.insert_filing(
            ticker=ticker,
            cik=cik,
            filing_type=filing_type,
            filing_date=filing_info.filing_date,
            accession_number=filing_info.accession_number,
            filing_url=filing_info.filing_url
        )
        
        if not filing_id:
            print(f"❌ Failed to store filing metadata")
            return False
        
        print(f"✓ Stored filing with ID: {filing_id}")
        
        # Chunk sections
        print("Chunking sections...")
        all_chunks = []
        for section in sections:
            chunks = chunker.chunk_section(
                text=section.content,
                section=section.section_name,
                metadata={
                    "ticker": ticker,
                    "filing_type": filing_type,
                    "filing_date": filing_info.filing_date
                }
            )
            all_chunks.extend(chunks)
        
        print(f"✓ Created {len(all_chunks)} chunks")
        
        # Generate embeddings
        print("Generating embeddings...")
        texts = [chunk.text for chunk in all_chunks]
        embeddings = embedder.embed_batch(texts, batch_size=32)
        
        print(f"✓ Generated {len(embeddings)} embeddings")
        
        # Store chunks with embeddings
        print("Storing chunks...")
        chunk_data = []
        for chunk, embedding in zip(all_chunks, embeddings):
            chunk_data.append({
                "filing_id": filing_id,
                "text": chunk.text,
                "section": chunk.metadata.get("section", "unknown"),
                "chunk_index": chunk.metadata.get("chunk_index", 0),
                "embedding": embedding.tolist()
            })
        
        success = store.insert_chunks(chunk_data)
        
        if not success:
            print(f"❌ Failed to store chunks")
            return False
        
        print(f"✓ Stored {len(chunk_data)} chunks with embeddings")
        
        print(f"\n✅ Successfully indexed {ticker} {filing_type}")
        return True
        
    except Exception as e:
        print(f"\n❌ Error indexing {ticker}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Index filings for all tickers."""
    print("="*60)
    print("SEC Filing Indexing Script")
    print("="*60)
    print(f"Tickers: {', '.join(TICKERS)}")
    print(f"Filing types: {', '.join(FILING_TYPES)}")
    print("="*60)
    
    results = {}
    
    for ticker in TICKERS:
        for filing_type in FILING_TYPES:
            success = index_ticker(ticker, filing_type)
            results[f"{ticker}-{filing_type}"] = success
    
    # Summary
    print("\n" + "="*60)
    print("INDEXING SUMMARY")
    print("="*60)
    
    successful = sum(1 for v in results.values() if v)
    total = len(results)
    
    for key, success in results.items():
        status = "✅ Success" if success else "❌ Failed"
        print(f"{key}: {status}")
    
    print(f"\nTotal: {successful}/{total} successful")
    print("="*60)
    
    return 0 if successful == total else 1

if __name__ == "__main__":
    sys.exit(main())
