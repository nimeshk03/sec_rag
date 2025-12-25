"""
SEC EDGAR Filing Downloader.

Downloads SEC filings (10-K, 10-Q, 8-K) from the EDGAR database.
"""

import time
import requests
from dataclasses import dataclass
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)


@dataclass
class FilingInfo:
    """Information about a SEC filing."""
    ticker: str
    cik: str
    filing_type: str
    filing_date: date
    accession_number: str
    primary_document: str
    filing_url: str


class SECDownloader:
    """
    Downloads SEC filings from EDGAR.
    
    Uses the SEC EDGAR API with proper rate limiting and user agent.
    """
    
    BASE_URL = "https://data.sec.gov"
    SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
    FILING_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{document}"
    
    # CIK mappings for supported tickers
    TICKER_TO_CIK = {
        "AAPL": "0000320193",
        "AMZN": "0001018724",
        "BAC": "0000070858",
        "GOOGL": "0001652044",
        "JPM": "0000019617",
        "MSFT": "0000789019",
        "NVDA": "0001045810",
        "SPY": "0000884394",
        "TLT": "0000893220",
        "GLD": "0001222333",
    }
    
    # Rate limiting: SEC requires max 10 requests per second
    REQUEST_DELAY = 0.15  # 150ms between requests
    
    def __init__(self, user_agent: str = "SEC-RAG-System admin@example.com"):
        """
        Initialize downloader with user agent.
        
        Args:
            user_agent: Required by SEC - should include contact email
        """
        self.user_agent = user_agent
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.user_agent,
            "Accept-Encoding": "gzip, deflate",
        })
        self._last_request_time = 0
    
    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.REQUEST_DELAY:
            time.sleep(self.REQUEST_DELAY - elapsed)
        self._last_request_time = time.time()
    
    def _make_request(self, url: str) -> Optional[requests.Response]:
        """Make a rate-limited request."""
        self._rate_limit()
        
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            logger.error(f"Request failed for {url}: {e}")
            return None
    
    def get_cik(self, ticker: str) -> Optional[str]:
        """
        Get CIK for a ticker.
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            CIK string or None if not found
        """
        return self.TICKER_TO_CIK.get(ticker.upper())
    
    def get_filing_list(
        self,
        ticker: str,
        filing_types: Optional[List[str]] = None,
        days_back: int = 365
    ) -> List[FilingInfo]:
        """
        Get list of filings for a ticker.
        
        Args:
            ticker: Stock ticker symbol
            filing_types: List of filing types to filter (e.g., ["10-K", "10-Q"])
            days_back: How far back to search
            
        Returns:
            List of FilingInfo objects
        """
        cik = self.get_cik(ticker)
        if not cik:
            logger.warning(f"Unknown ticker: {ticker}")
            return []
        
        # Fetch submissions JSON
        url = self.SUBMISSIONS_URL.format(cik=cik)
        response = self._make_request(url)
        
        if not response:
            return []
        
        try:
            data = response.json()
        except ValueError:
            logger.error(f"Invalid JSON response for {ticker}")
            return []
        
        filings = []
        cutoff_date = date.today() - timedelta(days=days_back)
        
        # Parse recent filings
        recent = data.get("filings", {}).get("recent", {})
        if not recent:
            return []
        
        forms = recent.get("form", [])
        filing_dates = recent.get("filingDate", [])
        accession_numbers = recent.get("accessionNumber", [])
        primary_documents = recent.get("primaryDocument", [])
        
        for i, form in enumerate(forms):
            # Filter by filing type
            if filing_types and form not in filing_types:
                continue
            
            # Parse filing date
            try:
                filing_date = date.fromisoformat(filing_dates[i])
            except (ValueError, IndexError):
                continue
            
            # Filter by date
            if filing_date < cutoff_date:
                continue
            
            # Build filing info
            accession = accession_numbers[i].replace("-", "")
            primary_doc = primary_documents[i]
            
            filing_url = self.FILING_URL.format(
                cik=cik.lstrip("0"),
                accession=accession,
                document=primary_doc
            )
            
            filings.append(FilingInfo(
                ticker=ticker.upper(),
                cik=cik,
                filing_type=form,
                filing_date=filing_date,
                accession_number=accession_numbers[i],
                primary_document=primary_doc,
                filing_url=filing_url,
            ))
        
        return filings
    
    def get_latest_filing(
        self,
        ticker: str,
        filing_type: str
    ) -> Optional[FilingInfo]:
        """
        Get the most recent filing of a specific type.
        
        Args:
            ticker: Stock ticker symbol
            filing_type: Filing type (10-K, 10-Q, 8-K)
            
        Returns:
            FilingInfo or None if not found
        """
        filings = self.get_filing_list(
            ticker,
            filing_types=[filing_type],
            days_back=730  # Look back 2 years for annual reports
        )
        
        if not filings:
            return None
        
        # Return most recent
        return max(filings, key=lambda f: f.filing_date)
    
    def download_filing(self, filing: FilingInfo) -> Optional[str]:
        """
        Download the content of a filing.
        
        Args:
            filing: FilingInfo object
            
        Returns:
            Filing HTML content or None if download fails
        """
        response = self._make_request(filing.filing_url)
        
        if not response:
            return None
        
        return response.text
    
    def download_latest_filings(
        self,
        ticker: str,
        include_10k: bool = True,
        include_10q: bool = True,
        include_8k: bool = True,
        days_back_8k: int = 30
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Download latest filings for a ticker.
        
        Args:
            ticker: Stock ticker symbol
            include_10k: Include latest 10-K
            include_10q: Include latest 10-Q
            include_8k: Include 8-K filings from days_back_8k
            days_back_8k: Days to look back for 8-K filings
            
        Returns:
            Dict with filing types as keys and list of {info, content} dicts
        """
        results = {
            "10-K": [],
            "10-Q": [],
            "8-K": [],
        }
        
        # Get 10-K
        if include_10k:
            filing = self.get_latest_filing(ticker, "10-K")
            if filing:
                content = self.download_filing(filing)
                if content:
                    results["10-K"].append({
                        "info": filing,
                        "content": content,
                    })
                    logger.info(f"Downloaded 10-K for {ticker} ({filing.filing_date})")
        
        # Get 10-Q
        if include_10q:
            filing = self.get_latest_filing(ticker, "10-Q")
            if filing:
                content = self.download_filing(filing)
                if content:
                    results["10-Q"].append({
                        "info": filing,
                        "content": content,
                    })
                    logger.info(f"Downloaded 10-Q for {ticker} ({filing.filing_date})")
        
        # Get 8-K filings
        if include_8k:
            filings = self.get_filing_list(
                ticker,
                filing_types=["8-K"],
                days_back=days_back_8k
            )
            for filing in filings:
                content = self.download_filing(filing)
                if content:
                    results["8-K"].append({
                        "info": filing,
                        "content": content,
                    })
                    logger.info(f"Downloaded 8-K for {ticker} ({filing.filing_date})")
        
        return results
    
    @classmethod
    def get_supported_tickers(cls) -> List[str]:
        """Get list of supported ticker symbols."""
        return list(cls.TICKER_TO_CIK.keys())
