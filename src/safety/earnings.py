"""
Earnings Proximity Checker for SEC Filing RAG System.

Detects upcoming earnings announcements and provides warnings
when earnings are within the configured threshold.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

from src.data.store import SupabaseStore, EarningsEntry


@dataclass
class EarningsProximity:
    """Earnings proximity check result."""
    ticker: str
    has_upcoming_earnings: bool
    days_until_earnings: Optional[int] = None
    earnings_date: Optional[date] = None
    time_of_day: Optional[str] = None
    is_within_threshold: bool = False
    threshold_days: int = 3
    
    @property
    def warning_message(self) -> Optional[str]:
        """Generate warning message if earnings are approaching."""
        if not self.has_upcoming_earnings:
            return None
        
        if self.is_within_threshold:
            return (
                f"WARNING: Earnings for {self.ticker} in {self.days_until_earnings} day(s) "
                f"on {self.earnings_date.isoformat()} ({self.time_of_day})"
            )
        
        return (
            f"Upcoming earnings for {self.ticker} in {self.days_until_earnings} day(s) "
            f"on {self.earnings_date.isoformat()}"
        )


class EarningsChecker:
    """
    Earnings proximity checker.
    
    Detects upcoming earnings announcements and determines if they
    are within the warning threshold (default: 3 days).
    """
    
    DEFAULT_THRESHOLD_DAYS = 3
    DEFAULT_LOOKBACK_DAYS = 90
    
    def __init__(
        self,
        store: Optional[SupabaseStore] = None,
        threshold_days: int = DEFAULT_THRESHOLD_DAYS
    ):
        """
        Initialize earnings checker.
        
        Args:
            store: Supabase store instance (lazy-loaded if not provided)
            threshold_days: Number of days before earnings to trigger warning
        """
        self._store = store
        self.threshold_days = threshold_days
    
    @property
    def store(self) -> SupabaseStore:
        """Lazy-load store instance."""
        if self._store is None:
            self._store = SupabaseStore()
        return self._store
    
    def check_earnings_proximity(
        self,
        ticker: str,
        reference_date: Optional[date] = None
    ) -> EarningsProximity:
        """
        Check if earnings are approaching for a ticker.
        
        Args:
            ticker: Stock ticker to check
            reference_date: Date to check from (default: today)
            
        Returns:
            EarningsProximity result with warning status
        """
        if reference_date is None:
            reference_date = date.today()
        
        # Get next earnings date
        earnings_entry = self.store.get_next_earnings(
            ticker=ticker,
            after_date=reference_date
        )
        
        # No upcoming earnings found
        if earnings_entry is None:
            return EarningsProximity(
                ticker=ticker,
                has_upcoming_earnings=False,
                threshold_days=self.threshold_days
            )
        
        # Calculate days until earnings
        days_until = (earnings_entry.earnings_date - reference_date).days
        
        # Check if within threshold
        is_within_threshold = days_until <= self.threshold_days
        
        return EarningsProximity(
            ticker=ticker,
            has_upcoming_earnings=True,
            days_until_earnings=days_until,
            earnings_date=earnings_entry.earnings_date,
            time_of_day=earnings_entry.time_of_day,
            is_within_threshold=is_within_threshold,
            threshold_days=self.threshold_days
        )
    
    def check_multiple_tickers(
        self,
        tickers: list[str],
        reference_date: Optional[date] = None
    ) -> dict[str, EarningsProximity]:
        """
        Check earnings proximity for multiple tickers.
        
        Args:
            tickers: List of stock tickers
            reference_date: Date to check from (default: today)
            
        Returns:
            Dictionary mapping ticker to EarningsProximity result
        """
        results = {}
        for ticker in tickers:
            results[ticker] = self.check_earnings_proximity(ticker, reference_date)
        return results
    
    def get_tickers_with_upcoming_earnings(
        self,
        tickers: list[str],
        days_ahead: int = 14,
        reference_date: Optional[date] = None
    ) -> list[str]:
        """
        Get list of tickers with earnings in the next N days.
        
        Args:
            tickers: List of tickers to check
            days_ahead: Number of days to look ahead
            reference_date: Date to check from (default: today)
            
        Returns:
            List of tickers with upcoming earnings
        """
        if reference_date is None:
            reference_date = date.today()
        
        end_date = reference_date + timedelta(days=days_ahead)
        
        # Get all upcoming earnings for these tickers
        upcoming = self.store.get_upcoming_earnings(
            days_ahead=days_ahead,
            tickers=tickers
        )
        
        # Return unique tickers
        return list(set(entry.ticker for entry in upcoming))
    
    def is_earnings_blackout(
        self,
        ticker: str,
        reference_date: Optional[date] = None
    ) -> bool:
        """
        Check if ticker is in earnings blackout period.
        
        A blackout period is defined as within threshold_days before
        or after earnings announcement.
        
        Args:
            ticker: Stock ticker
            reference_date: Date to check from (default: today)
            
        Returns:
            True if in blackout period
        """
        if reference_date is None:
            reference_date = date.today()
        
        # Check upcoming earnings
        proximity = self.check_earnings_proximity(ticker, reference_date)
        if proximity.is_within_threshold:
            return True
        
        # Check recent earnings (within threshold days in the past)
        past_date = reference_date - timedelta(days=self.threshold_days)
        
        # Get earnings in the past threshold window
        earnings_entry = self.store.get_next_earnings(
            ticker=ticker,
            after_date=past_date
        )
        
        if earnings_entry and earnings_entry.earnings_date <= reference_date:
            days_since = (reference_date - earnings_entry.earnings_date).days
            if days_since <= self.threshold_days:
                return True
        
        return False
    
    def populate_earnings_data(
        self,
        ticker: str,
        earnings_date: date,
        time_of_day: str = "UNKNOWN",
        fiscal_quarter: Optional[str] = None,
        source: str = "manual"
    ) -> str:
        """
        Add or update earnings data for a ticker.
        
        Args:
            ticker: Stock ticker
            earnings_date: Date of earnings announcement
            time_of_day: Time of day (BMO, AMC, UNKNOWN)
            fiscal_quarter: Fiscal quarter (e.g., "Q1 2024")
            source: Data source identifier
            
        Returns:
            Entry UUID
        """
        entry = EarningsEntry(
            ticker=ticker,
            earnings_date=earnings_date,
            time_of_day=time_of_day,
            fiscal_quarter=fiscal_quarter,
            source=source
        )
        
        return self.store.update_earnings(entry)
    
    def bulk_populate_earnings(
        self,
        earnings_data: list[dict]
    ) -> list[str]:
        """
        Bulk populate earnings calendar data.
        
        Args:
            earnings_data: List of dicts with keys:
                - ticker: Stock ticker
                - earnings_date: Date or ISO string
                - time_of_day: Optional time of day
                - fiscal_quarter: Optional fiscal quarter
                - source: Optional source identifier
                
        Returns:
            List of entry UUIDs
        """
        entry_ids = []
        
        for data in earnings_data:
            # Convert date string if needed
            earnings_date = data["earnings_date"]
            if isinstance(earnings_date, str):
                earnings_date = date.fromisoformat(earnings_date)
            
            entry_id = self.populate_earnings_data(
                ticker=data["ticker"],
                earnings_date=earnings_date,
                time_of_day=data.get("time_of_day", "UNKNOWN"),
                fiscal_quarter=data.get("fiscal_quarter"),
                source=data.get("source", "bulk_import")
            )
            entry_ids.append(entry_id)
        
        return entry_ids
