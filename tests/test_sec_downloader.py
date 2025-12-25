"""
Unit tests for SEC EDGAR Downloader.

Tests filing list retrieval and download functionality with mocked responses.
"""

import pytest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch
import json

from src.data.sec_downloader import SECDownloader, FilingInfo


class TestSECDownloaderInitialization:
    """Tests for downloader initialization."""
    
    def test_default_initialization(self):
        """Test default initialization."""
        downloader = SECDownloader()
        
        assert downloader.user_agent == "SEC-RAG-System admin@example.com"
        assert downloader.session is not None
    
    def test_custom_user_agent(self):
        """Test custom user agent."""
        downloader = SECDownloader(user_agent="Custom Agent test@test.com")
        
        assert downloader.user_agent == "Custom Agent test@test.com"
    
    def test_session_headers(self):
        """Test that session has proper headers."""
        downloader = SECDownloader(user_agent="Test Agent")
        
        assert "User-Agent" in downloader.session.headers
        assert downloader.session.headers["User-Agent"] == "Test Agent"


class TestTickerToCIK:
    """Tests for ticker to CIK mapping."""
    
    def test_get_cik_known_ticker(self):
        """Test getting CIK for known ticker."""
        downloader = SECDownloader()
        
        assert downloader.get_cik("AAPL") == "0000320193"
        assert downloader.get_cik("MSFT") == "0000789019"
        assert downloader.get_cik("NVDA") == "0001045810"
    
    def test_get_cik_case_insensitive(self):
        """Test that CIK lookup is case insensitive."""
        downloader = SECDownloader()
        
        assert downloader.get_cik("aapl") == "0000320193"
        assert downloader.get_cik("Aapl") == "0000320193"
    
    def test_get_cik_unknown_ticker(self):
        """Test getting CIK for unknown ticker."""
        downloader = SECDownloader()
        
        assert downloader.get_cik("UNKNOWN") is None
        assert downloader.get_cik("XYZ123") is None
    
    def test_supported_tickers(self):
        """Test getting list of supported tickers."""
        tickers = SECDownloader.get_supported_tickers()
        
        assert len(tickers) == 10
        assert "AAPL" in tickers
        assert "MSFT" in tickers
        assert "GOOGL" in tickers
        assert "NVDA" in tickers


class TestRateLimiting:
    """Tests for rate limiting."""
    
    @patch('time.sleep')
    @patch('time.time')
    def test_rate_limiting_enforced(self, mock_time, mock_sleep):
        """Test that rate limiting is enforced."""
        mock_time.side_effect = [0, 0.05, 0.05]  # Simulate fast requests
        
        downloader = SECDownloader()
        downloader._last_request_time = 0
        
        downloader._rate_limit()
        
        # Should sleep for remaining time
        mock_sleep.assert_called()


class TestGetFilingList:
    """Tests for getting filing lists."""
    
    def test_get_filing_list_success(self):
        """Test successful filing list retrieval."""
        downloader = SECDownloader()
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "filings": {
                "recent": {
                    "form": ["10-K", "10-Q", "8-K", "10-K"],
                    "filingDate": [
                        date.today().isoformat(),
                        (date.today() - timedelta(days=30)).isoformat(),
                        (date.today() - timedelta(days=60)).isoformat(),
                        (date.today() - timedelta(days=400)).isoformat(),  # Too old
                    ],
                    "accessionNumber": ["0001-24-001", "0001-24-002", "0001-24-003", "0001-23-001"],
                    "primaryDocument": ["doc1.htm", "doc2.htm", "doc3.htm", "doc4.htm"],
                }
            }
        }
        
        with patch.object(downloader, '_make_request', return_value=mock_response):
            filings = downloader.get_filing_list("AAPL", days_back=365)
        
        assert len(filings) == 3  # 4th is too old
        assert all(isinstance(f, FilingInfo) for f in filings)
    
    def test_get_filing_list_with_type_filter(self):
        """Test filing list with type filter."""
        downloader = SECDownloader()
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "filings": {
                "recent": {
                    "form": ["10-K", "10-Q", "8-K"],
                    "filingDate": [
                        date.today().isoformat(),
                        date.today().isoformat(),
                        date.today().isoformat(),
                    ],
                    "accessionNumber": ["0001-24-001", "0001-24-002", "0001-24-003"],
                    "primaryDocument": ["doc1.htm", "doc2.htm", "doc3.htm"],
                }
            }
        }
        
        with patch.object(downloader, '_make_request', return_value=mock_response):
            filings = downloader.get_filing_list("AAPL", filing_types=["10-K"])
        
        assert len(filings) == 1
        assert filings[0].filing_type == "10-K"
    
    def test_get_filing_list_unknown_ticker(self):
        """Test filing list for unknown ticker."""
        downloader = SECDownloader()
        
        filings = downloader.get_filing_list("UNKNOWN")
        
        assert filings == []
    
    def test_get_filing_list_request_failure(self):
        """Test filing list when request fails."""
        downloader = SECDownloader()
        
        with patch.object(downloader, '_make_request', return_value=None):
            filings = downloader.get_filing_list("AAPL")
        
        assert filings == []
    
    def test_get_filing_list_invalid_json(self):
        """Test filing list with invalid JSON response."""
        downloader = SECDownloader()
        
        mock_response = MagicMock()
        mock_response.json.side_effect = ValueError("Invalid JSON")
        
        with patch.object(downloader, '_make_request', return_value=mock_response):
            filings = downloader.get_filing_list("AAPL")
        
        assert filings == []


class TestGetLatestFiling:
    """Tests for getting latest filing."""
    
    def test_get_latest_filing_success(self):
        """Test getting latest filing."""
        downloader = SECDownloader()
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "filings": {
                "recent": {
                    "form": ["10-K", "10-K"],
                    "filingDate": [
                        (date.today() - timedelta(days=30)).isoformat(),
                        (date.today() - timedelta(days=365)).isoformat(),
                    ],
                    "accessionNumber": ["0001-24-001", "0001-23-001"],
                    "primaryDocument": ["doc1.htm", "doc2.htm"],
                }
            }
        }
        
        with patch.object(downloader, '_make_request', return_value=mock_response):
            filing = downloader.get_latest_filing("AAPL", "10-K")
        
        assert filing is not None
        assert filing.filing_type == "10-K"
        # Should return the most recent one
        assert filing.accession_number == "0001-24-001"
    
    def test_get_latest_filing_not_found(self):
        """Test when no filing is found."""
        downloader = SECDownloader()
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "filings": {
                "recent": {
                    "form": ["8-K"],
                    "filingDate": [date.today().isoformat()],
                    "accessionNumber": ["0001-24-001"],
                    "primaryDocument": ["doc1.htm"],
                }
            }
        }
        
        with patch.object(downloader, '_make_request', return_value=mock_response):
            filing = downloader.get_latest_filing("AAPL", "10-K")
        
        assert filing is None


class TestDownloadFiling:
    """Tests for downloading filing content."""
    
    def test_download_filing_success(self):
        """Test successful filing download."""
        downloader = SECDownloader()
        
        filing = FilingInfo(
            ticker="AAPL",
            cik="0000320193",
            filing_type="10-K",
            filing_date=date.today(),
            accession_number="0001-24-001",
            primary_document="doc.htm",
            filing_url="https://sec.gov/filing/doc.htm",
        )
        
        mock_response = MagicMock()
        mock_response.text = "<html>Filing content</html>"
        
        with patch.object(downloader, '_make_request', return_value=mock_response):
            content = downloader.download_filing(filing)
        
        assert content == "<html>Filing content</html>"
    
    def test_download_filing_failure(self):
        """Test filing download failure."""
        downloader = SECDownloader()
        
        filing = FilingInfo(
            ticker="AAPL",
            cik="0000320193",
            filing_type="10-K",
            filing_date=date.today(),
            accession_number="0001-24-001",
            primary_document="doc.htm",
            filing_url="https://sec.gov/filing/doc.htm",
        )
        
        with patch.object(downloader, '_make_request', return_value=None):
            content = downloader.download_filing(filing)
        
        assert content is None


class TestDownloadLatestFilings:
    """Tests for downloading latest filings for a ticker."""
    
    def test_download_latest_filings(self):
        """Test downloading all latest filings."""
        downloader = SECDownloader()
        
        mock_10k = FilingInfo(
            ticker="AAPL", cik="0000320193", filing_type="10-K",
            filing_date=date.today(), accession_number="acc1",
            primary_document="doc.htm", filing_url="url1"
        )
        mock_10q = FilingInfo(
            ticker="AAPL", cik="0000320193", filing_type="10-Q",
            filing_date=date.today(), accession_number="acc2",
            primary_document="doc.htm", filing_url="url2"
        )
        
        with patch.object(downloader, 'get_latest_filing') as mock_get_latest:
            with patch.object(downloader, 'get_filing_list') as mock_get_list:
                with patch.object(downloader, 'download_filing') as mock_download:
                    mock_get_latest.side_effect = [mock_10k, mock_10q]
                    mock_get_list.return_value = []
                    mock_download.return_value = "<html>content</html>"
                    
                    results = downloader.download_latest_filings("AAPL", include_8k=False)
        
        assert len(results["10-K"]) == 1
        assert len(results["10-Q"]) == 1
        assert results["10-K"][0]["content"] == "<html>content</html>"
    
    def test_download_latest_filings_skip_types(self):
        """Test skipping certain filing types."""
        downloader = SECDownloader()
        
        with patch.object(downloader, 'get_latest_filing') as mock_get_latest:
            with patch.object(downloader, 'get_filing_list') as mock_get_list:
                mock_get_latest.return_value = None
                mock_get_list.return_value = []
                
                results = downloader.download_latest_filings(
                    "AAPL",
                    include_10k=False,
                    include_10q=False,
                    include_8k=False
                )
        
        assert results["10-K"] == []
        assert results["10-Q"] == []
        assert results["8-K"] == []


class TestFilingInfo:
    """Tests for FilingInfo dataclass."""
    
    def test_filing_info_creation(self):
        """Test FilingInfo creation."""
        filing = FilingInfo(
            ticker="AAPL",
            cik="0000320193",
            filing_type="10-K",
            filing_date=date(2024, 1, 15),
            accession_number="0000320193-24-000001",
            primary_document="aapl-20231230.htm",
            filing_url="https://sec.gov/filing.htm",
        )
        
        assert filing.ticker == "AAPL"
        assert filing.filing_type == "10-K"
        assert filing.filing_date == date(2024, 1, 15)
