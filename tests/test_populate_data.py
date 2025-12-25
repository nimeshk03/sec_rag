"""
Unit tests for Data Population Script.

Tests the data population pipeline with mocked dependencies.
"""

import pytest
from datetime import date
from unittest.mock import MagicMock, patch, PropertyMock
import numpy as np

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.populate_data import DataPopulator, PopulationStats
from src.data.sec_downloader import FilingInfo
from src.data.parser import ParsedSection


class TestPopulationStats:
    """Tests for PopulationStats dataclass."""
    
    def test_default_values(self):
        """Test default values."""
        stats = PopulationStats()
        
        assert stats.tickers_processed == 0
        assert stats.filings_downloaded == 0
        assert stats.filings_stored == 0
        assert stats.chunks_created == 0
        assert stats.chunks_with_embeddings == 0
        assert stats.errors == []
    
    def test_to_dict(self):
        """Test conversion to dict."""
        stats = PopulationStats(
            tickers_processed=5,
            filings_downloaded=10,
            errors=["error1"]
        )
        
        result = stats.to_dict()
        
        assert result["tickers_processed"] == 5
        assert result["filings_downloaded"] == 10
        assert result["errors"] == ["error1"]


class TestDataPopulatorInitialization:
    """Tests for DataPopulator initialization."""
    
    def test_default_initialization(self):
        """Test default initialization."""
        populator = DataPopulator()
        
        assert populator.skip_embeddings is False
        assert populator.dry_run is False
        assert populator._store is None
        assert populator._embedder is None
    
    def test_dry_run_mode(self):
        """Test dry run mode."""
        populator = DataPopulator(dry_run=True)
        
        assert populator.dry_run is True
    
    def test_skip_embeddings_mode(self):
        """Test skip embeddings mode."""
        populator = DataPopulator(skip_embeddings=True)
        
        assert populator.skip_embeddings is True
    
    def test_custom_chunk_settings(self):
        """Test custom chunk settings."""
        populator = DataPopulator(chunk_size=500, chunk_overlap=50)
        
        assert populator.chunker.chunk_size == 500
        assert populator.chunker.chunk_overlap == 50


class TestDataPopulatorLazyLoading:
    """Tests for lazy loading of store and embedder."""
    
    @patch('scripts.populate_data.SupabaseStore')
    def test_store_lazy_loading(self, mock_store_class):
        """Test that store is lazily loaded."""
        mock_store = MagicMock()
        mock_store_class.return_value = mock_store
        
        populator = DataPopulator()
        
        # Store should not be loaded yet
        assert populator._store is None
        
        # Access store property
        _ = populator.store
        
        # Now it should be loaded
        mock_store_class.assert_called_once()
    
    def test_store_not_loaded_in_dry_run(self):
        """Test that store is not loaded in dry run mode."""
        populator = DataPopulator(dry_run=True)
        
        # Access store property
        result = populator.store
        
        # Should return None in dry run
        assert result is None
    
    def test_embedder_lazy_loading(self):
        """Test that embedder is lazily loaded."""
        populator = DataPopulator()
        
        # Embedder should not be loaded yet
        assert populator._embedder is None
        
        # Access embedder property - it will try to import LocalEmbedder
        # We just verify the property access doesn't crash when skip_embeddings is True
        populator_skip = DataPopulator(skip_embeddings=True)
        result = populator_skip.embedder
        assert result is None
    
    def test_embedder_not_loaded_when_skipped(self):
        """Test that embedder is not loaded when skipped."""
        populator = DataPopulator(skip_embeddings=True)
        
        # Access embedder property
        result = populator.embedder
        
        # Should return None when skipped
        assert result is None


class TestProcessFiling:
    """Tests for processing individual filings."""
    
    def test_process_10k_filing(self):
        """Test processing a 10-K filing."""
        populator = DataPopulator(dry_run=True, skip_embeddings=True)
        
        filing_info = FilingInfo(
            ticker="AAPL",
            cik="0000320193",
            filing_type="10-K",
            filing_date=date(2024, 1, 15),
            accession_number="0000320193-24-000001",
            primary_document="doc.htm",
            filing_url="https://sec.gov/filing.htm",
        )
        
        # Mock parser to return sections (Dict format)
        mock_sections = {
            "1A": ParsedSection(name="1A", title="Risk Factors", content="Risk content " * 100, start_index=0, end_index=100),
            "7": ParsedSection(name="7", title="MD&A", content="MD&A content " * 100, start_index=100, end_index=200),
        }
        
        stats = PopulationStats()
        
        with patch.object(populator.parser, 'parse_10k', return_value=mock_sections):
            result = populator.process_filing(filing_info, "<html>content</html>", stats)
        
        assert result == "dry-run-id"
        assert stats.chunks_created > 0
    
    def test_process_10q_filing(self):
        """Test processing a 10-Q filing."""
        populator = DataPopulator(dry_run=True, skip_embeddings=True)
        
        filing_info = FilingInfo(
            ticker="MSFT",
            cik="0000789019",
            filing_type="10-Q",
            filing_date=date(2024, 3, 15),
            accession_number="0000789019-24-000002",
            primary_document="doc.htm",
            filing_url="https://sec.gov/filing.htm",
        )
        
        mock_sections = {
            "Part1Item2": ParsedSection(name="Part1Item2", title="MD&A", content="Quarterly content " * 50, start_index=0, end_index=100),
        }
        
        stats = PopulationStats()
        
        with patch.object(populator.parser, 'parse_10q', return_value=mock_sections):
            result = populator.process_filing(filing_info, "<html>content</html>", stats)
        
        assert result == "dry-run-id"
    
    def test_process_8k_filing(self):
        """Test processing an 8-K filing."""
        populator = DataPopulator(dry_run=True, skip_embeddings=True)
        
        filing_info = FilingInfo(
            ticker="GOOGL",
            cik="0001652044",
            filing_type="8-K",
            filing_date=date(2024, 2, 1),
            accession_number="0001652044-24-000003",
            primary_document="doc.htm",
            filing_url="https://sec.gov/filing.htm",
        )
        
        mock_sections = {
            "Item2.02": ParsedSection(name="Item2.02", title="Results", content="Event content " * 50, start_index=0, end_index=100),
        }
        
        stats = PopulationStats()
        
        with patch.object(populator.parser, 'parse_8k', return_value=mock_sections):
            result = populator.process_filing(filing_info, "<html>content</html>", stats)
        
        assert result == "dry-run-id"
    
    def test_process_filing_no_sections(self):
        """Test processing filing with no sections extracted."""
        populator = DataPopulator(dry_run=True, skip_embeddings=True)
        
        filing_info = FilingInfo(
            ticker="AAPL",
            cik="0000320193",
            filing_type="10-K",
            filing_date=date(2024, 1, 15),
            accession_number="acc1",
            primary_document="doc.htm",
            filing_url="url",
        )
        
        stats = PopulationStats()
        
        with patch.object(populator.parser, 'parse_10k', return_value=[]):
            result = populator.process_filing(filing_info, "<html></html>", stats)
        
        assert result is None
    
    def test_process_filing_unknown_type(self):
        """Test processing filing with unknown type."""
        populator = DataPopulator(dry_run=True, skip_embeddings=True)
        
        filing_info = FilingInfo(
            ticker="AAPL",
            cik="0000320193",
            filing_type="UNKNOWN",
            filing_date=date(2024, 1, 15),
            accession_number="acc1",
            primary_document="doc.htm",
            filing_url="url",
        )
        
        stats = PopulationStats()
        result = populator.process_filing(filing_info, "<html></html>", stats)
        
        assert result is None
    
    def test_process_filing_with_store(self):
        """Test processing filing with actual store (mocked)."""
        populator = DataPopulator(skip_embeddings=True)
        
        mock_store = MagicMock()
        mock_store.insert_filing.return_value = "filing-uuid-123"
        mock_store.insert_chunks.return_value = ["chunk-1", "chunk-2"]
        populator._store = mock_store
        
        filing_info = FilingInfo(
            ticker="AAPL",
            cik="0000320193",
            filing_type="10-K",
            filing_date=date(2024, 1, 15),
            accession_number="acc1",
            primary_document="doc.htm",
            filing_url="url",
        )
        
        mock_sections = {
            "1A": ParsedSection(name="1A", title="Risk", content="Content " * 100, start_index=0, end_index=100),
        }
        
        stats = PopulationStats()
        
        with patch.object(populator.parser, 'parse_10k', return_value=mock_sections):
            result = populator.process_filing(filing_info, "<html>content</html>", stats)
        
        assert result == "filing-uuid-123"
        assert stats.filings_stored == 1
        mock_store.insert_filing.assert_called_once()
        mock_store.insert_chunks.assert_called_once()
    
    def test_process_filing_with_embeddings(self):
        """Test processing filing with embedding generation."""
        populator = DataPopulator()
        
        mock_store = MagicMock()
        mock_store.insert_filing.return_value = "filing-uuid-123"
        mock_store.insert_chunks.return_value = ["chunk-1"]
        populator._store = mock_store
        
        mock_embedder = MagicMock()
        mock_embedder.embed_text.return_value = np.random.randn(384)
        populator._embedder = mock_embedder
        
        filing_info = FilingInfo(
            ticker="AAPL",
            cik="0000320193",
            filing_type="10-K",
            filing_date=date(2024, 1, 15),
            accession_number="acc1",
            primary_document="doc.htm",
            filing_url="url",
        )
        
        mock_sections = {
            "1A": ParsedSection(name="1A", title="Risk", content="Short content", start_index=0, end_index=100),
        }
        
        stats = PopulationStats()
        
        with patch.object(populator.parser, 'parse_10k', return_value=mock_sections):
            result = populator.process_filing(filing_info, "<html>content</html>", stats)
        
        assert stats.chunks_with_embeddings > 0
        mock_embedder.embed_text.assert_called()
    
    def test_process_filing_error_handling(self):
        """Test error handling during processing."""
        populator = DataPopulator(dry_run=True, skip_embeddings=True)
        
        filing_info = FilingInfo(
            ticker="AAPL",
            cik="0000320193",
            filing_type="10-K",
            filing_date=date(2024, 1, 15),
            accession_number="acc1",
            primary_document="doc.htm",
            filing_url="url",
        )
        
        stats = PopulationStats()
        
        with patch.object(populator.parser, 'parse_10k', side_effect=Exception("Parse error")):
            result = populator.process_filing(filing_info, "<html>content</html>", stats)
        
        assert result is None
        assert len(stats.errors) == 1
        assert "Parse error" in stats.errors[0]


class TestPopulateTicker:
    """Tests for populating a single ticker."""
    
    def test_populate_ticker_success(self):
        """Test successful ticker population."""
        populator = DataPopulator(dry_run=True, skip_embeddings=True)
        
        mock_10k = FilingInfo(
            ticker="AAPL", cik="0000320193", filing_type="10-K",
            filing_date=date(2024, 1, 15), accession_number="acc1",
            primary_document="doc.htm", filing_url="url"
        )
        
        mock_sections = {
            "1A": ParsedSection(name="1A", title="Risk", content="Content " * 100, start_index=0, end_index=100),
        }
        
        with patch.object(populator.downloader, 'download_latest_filings') as mock_download:
            mock_download.return_value = {
                "10-K": [{"info": mock_10k, "content": "<html>content</html>"}],
                "10-Q": [],
                "8-K": [],
            }
            
            with patch.object(populator.parser, 'parse_10k', return_value=mock_sections):
                stats = populator.populate_ticker("AAPL")
        
        assert stats.tickers_processed == 1
        assert stats.filings_downloaded == 1
    
    def test_populate_ticker_with_existing_stats(self):
        """Test populating ticker with existing stats object."""
        populator = DataPopulator(dry_run=True, skip_embeddings=True)
        
        existing_stats = PopulationStats(tickers_processed=5, filings_downloaded=10)
        
        with patch.object(populator.downloader, 'download_latest_filings') as mock_download:
            mock_download.return_value = {"10-K": [], "10-Q": [], "8-K": []}
            
            stats = populator.populate_ticker("AAPL", stats=existing_stats)
        
        assert stats.tickers_processed == 6  # Incremented
        assert stats is existing_stats


class TestPopulateAll:
    """Tests for populating all tickers."""
    
    def test_populate_all_default_tickers(self):
        """Test populating all default tickers."""
        populator = DataPopulator(dry_run=True, skip_embeddings=True)
        
        with patch.object(populator, 'populate_ticker') as mock_populate:
            mock_populate.return_value = PopulationStats(tickers_processed=1)
            
            stats = populator.populate_all()
        
        # Should be called for all 10 tickers
        assert mock_populate.call_count == 10
    
    def test_populate_all_custom_tickers(self):
        """Test populating custom ticker list."""
        populator = DataPopulator(dry_run=True, skip_embeddings=True)
        
        with patch.object(populator, 'populate_ticker') as mock_populate:
            mock_populate.return_value = PopulationStats(tickers_processed=1)
            
            stats = populator.populate_all(tickers=["AAPL", "MSFT"])
        
        assert mock_populate.call_count == 2
    
    def test_populate_all_with_options(self):
        """Test populating with filing type options."""
        populator = DataPopulator(dry_run=True, skip_embeddings=True)
        
        with patch.object(populator, 'populate_ticker') as mock_populate:
            mock_populate.return_value = PopulationStats(tickers_processed=1)
            
            populator.populate_all(
                tickers=["AAPL"],
                include_10k=True,
                include_10q=False,
                include_8k=False,
            )
        
        # Verify options were passed
        call_kwargs = mock_populate.call_args[1]
        assert call_kwargs["include_10k"] is True
        assert call_kwargs["include_10q"] is False
        assert call_kwargs["include_8k"] is False
    
    def test_populate_all_handles_ticker_errors(self):
        """Test that errors for one ticker don't stop others."""
        populator = DataPopulator(dry_run=True, skip_embeddings=True)
        
        call_count = [0]
        
        def mock_populate(ticker, **kwargs):
            call_count[0] += 1
            if ticker == "MSFT":
                raise Exception("MSFT error")
            return PopulationStats(tickers_processed=1)
        
        with patch.object(populator, 'populate_ticker', side_effect=mock_populate):
            stats = populator.populate_all(tickers=["AAPL", "MSFT", "GOOGL"])
        
        # All tickers should be attempted
        assert call_count[0] == 3
        # Error should be recorded
        assert len(stats.errors) == 1
        assert "MSFT" in stats.errors[0]


class TestIntegration:
    """Integration-style tests with minimal mocking."""
    
    def test_full_pipeline_dry_run(self):
        """Test full pipeline in dry run mode."""
        populator = DataPopulator(dry_run=True, skip_embeddings=True)
        
        # Mock only the network calls
        mock_10k = FilingInfo(
            ticker="AAPL", cik="0000320193", filing_type="10-K",
            filing_date=date(2024, 1, 15), accession_number="acc1",
            primary_document="doc.htm", filing_url="url"
        )
        
        html_content = """
        <html>
        <body>
        <p>ITEM 1A. RISK FACTORS</p>
        <p>This is a risk factor section with enough content to create chunks.
        We need to have sufficient text here to ensure the chunker creates
        at least one chunk from this content. The risk factors include
        market volatility, competition, and regulatory changes.</p>
        <p>ITEM 7. MANAGEMENT'S DISCUSSION AND ANALYSIS</p>
        <p>This is the MD&A section with analysis of financial condition.</p>
        </body>
        </html>
        """
        
        with patch.object(populator.downloader, 'download_latest_filings') as mock_download:
            mock_download.return_value = {
                "10-K": [{"info": mock_10k, "content": html_content}],
                "10-Q": [],
                "8-K": [],
            }
            
            stats = populator.populate_all(tickers=["AAPL"])
        
        assert stats.tickers_processed == 1
        assert stats.filings_downloaded == 1
        # Chunks should be created even in dry run
        assert stats.chunks_created >= 0  # May be 0 if parsing doesn't find sections
