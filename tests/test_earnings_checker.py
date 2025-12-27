"""
Unit tests for the Earnings Proximity Checker.

Tests cover:
- EarningsProximity dataclass
- EarningsChecker initialization
- Earnings proximity detection
- Threshold-based warnings
- Multiple ticker checking
- Blackout period detection
- Earnings data population
"""

import pytest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from src.safety.earnings import EarningsChecker, EarningsProximity
from src.data.store import EarningsEntry


class TestEarningsProximity:
    """Tests for EarningsProximity dataclass."""
    
    def test_no_upcoming_earnings(self):
        """Test result when no earnings are upcoming."""
        result = EarningsProximity(
            ticker="AAPL",
            has_upcoming_earnings=False,
            threshold_days=3
        )
        
        assert result.ticker == "AAPL"
        assert result.has_upcoming_earnings is False
        assert result.days_until_earnings is None
        assert result.is_within_threshold is False
        assert result.warning_message is None
    
    def test_earnings_within_threshold(self):
        """Test result when earnings are within threshold."""
        earnings_date = date.today() + timedelta(days=2)
        
        result = EarningsProximity(
            ticker="AAPL",
            has_upcoming_earnings=True,
            days_until_earnings=2,
            earnings_date=earnings_date,
            time_of_day="AMC",
            is_within_threshold=True,
            threshold_days=3
        )
        
        assert result.has_upcoming_earnings is True
        assert result.days_until_earnings == 2
        assert result.is_within_threshold is True
        assert "WARNING" in result.warning_message
        assert "AAPL" in result.warning_message
        assert "2 day(s)" in result.warning_message
    
    def test_earnings_outside_threshold(self):
        """Test result when earnings are outside threshold."""
        earnings_date = date.today() + timedelta(days=10)
        
        result = EarningsProximity(
            ticker="AAPL",
            has_upcoming_earnings=True,
            days_until_earnings=10,
            earnings_date=earnings_date,
            time_of_day="BMO",
            is_within_threshold=False,
            threshold_days=3
        )
        
        assert result.has_upcoming_earnings is True
        assert result.is_within_threshold is False
        assert "WARNING" not in result.warning_message
        assert "Upcoming earnings" in result.warning_message


class TestEarningsCheckerInitialization:
    """Tests for EarningsChecker initialization."""
    
    def test_default_initialization(self):
        """Test initialization with defaults."""
        checker = EarningsChecker()
        
        assert checker.threshold_days == 3
        assert checker._store is None
    
    def test_custom_threshold(self):
        """Test initialization with custom threshold."""
        checker = EarningsChecker(threshold_days=5)
        
        assert checker.threshold_days == 5
    
    def test_with_injected_store(self):
        """Test initialization with injected store."""
        mock_store = MagicMock()
        checker = EarningsChecker(store=mock_store)
        
        assert checker._store is mock_store
        assert checker.store is mock_store
    
    def test_lazy_store_loading(self):
        """Test that store is lazy-loaded."""
        checker = EarningsChecker()
        
        assert checker._store is None
        
        # Accessing store property should trigger lazy load
        with patch('src.safety.earnings.SupabaseStore') as mock_store_class:
            mock_instance = MagicMock()
            mock_store_class.return_value = mock_instance
            
            store = checker.store
            
            assert store is not None
            mock_store_class.assert_called_once()


class TestEarningsProximityChecking:
    """Tests for earnings proximity checking."""
    
    def test_check_no_upcoming_earnings(self):
        """Test checking when no earnings are upcoming."""
        mock_store = MagicMock()
        mock_store.get_next_earnings.return_value = None
        
        checker = EarningsChecker(store=mock_store, threshold_days=3)
        result = checker.check_earnings_proximity("AAPL")
        
        assert result.ticker == "AAPL"
        assert result.has_upcoming_earnings is False
        assert result.days_until_earnings is None
        assert result.is_within_threshold is False
        mock_store.get_next_earnings.assert_called_once()
    
    def test_check_earnings_within_threshold(self):
        """Test checking when earnings are within threshold."""
        mock_store = MagicMock()
        reference_date = date(2024, 1, 15)
        earnings_date = date(2024, 1, 17)  # 2 days away
        
        mock_store.get_next_earnings.return_value = EarningsEntry(
            ticker="AAPL",
            earnings_date=earnings_date,
            time_of_day="AMC",
            fiscal_quarter="Q1 2024"
        )
        
        checker = EarningsChecker(store=mock_store, threshold_days=3)
        result = checker.check_earnings_proximity("AAPL", reference_date=reference_date)
        
        assert result.has_upcoming_earnings is True
        assert result.days_until_earnings == 2
        assert result.earnings_date == earnings_date
        assert result.time_of_day == "AMC"
        assert result.is_within_threshold is True
    
    def test_check_earnings_outside_threshold(self):
        """Test checking when earnings are outside threshold."""
        mock_store = MagicMock()
        reference_date = date(2024, 1, 15)
        earnings_date = date(2024, 1, 25)  # 10 days away
        
        mock_store.get_next_earnings.return_value = EarningsEntry(
            ticker="AAPL",
            earnings_date=earnings_date,
            time_of_day="BMO"
        )
        
        checker = EarningsChecker(store=mock_store, threshold_days=3)
        result = checker.check_earnings_proximity("AAPL", reference_date=reference_date)
        
        assert result.has_upcoming_earnings is True
        assert result.days_until_earnings == 10
        assert result.is_within_threshold is False
    
    def test_check_earnings_on_threshold_boundary(self):
        """Test checking when earnings are exactly on threshold."""
        mock_store = MagicMock()
        reference_date = date(2024, 1, 15)
        earnings_date = date(2024, 1, 18)  # Exactly 3 days away
        
        mock_store.get_next_earnings.return_value = EarningsEntry(
            ticker="AAPL",
            earnings_date=earnings_date,
            time_of_day="UNKNOWN"
        )
        
        checker = EarningsChecker(store=mock_store, threshold_days=3)
        result = checker.check_earnings_proximity("AAPL", reference_date=reference_date)
        
        assert result.days_until_earnings == 3
        assert result.is_within_threshold is True  # <= threshold
    
    def test_check_earnings_today(self):
        """Test checking when earnings are today."""
        mock_store = MagicMock()
        reference_date = date(2024, 1, 15)
        earnings_date = date(2024, 1, 15)  # Today
        
        mock_store.get_next_earnings.return_value = EarningsEntry(
            ticker="AAPL",
            earnings_date=earnings_date,
            time_of_day="AMC"
        )
        
        checker = EarningsChecker(store=mock_store, threshold_days=3)
        result = checker.check_earnings_proximity("AAPL", reference_date=reference_date)
        
        assert result.days_until_earnings == 0
        assert result.is_within_threshold is True


class TestMultipleTickerChecking:
    """Tests for checking multiple tickers."""
    
    def test_check_multiple_tickers(self):
        """Test checking earnings for multiple tickers."""
        mock_store = MagicMock()
        reference_date = date(2024, 1, 15)
        
        def mock_get_next_earnings(ticker, after_date):
            if ticker == "AAPL":
                return EarningsEntry(
                    ticker="AAPL",
                    earnings_date=date(2024, 1, 17),
                    time_of_day="AMC"
                )
            elif ticker == "MSFT":
                return EarningsEntry(
                    ticker="MSFT",
                    earnings_date=date(2024, 1, 25),
                    time_of_day="BMO"
                )
            else:
                return None
        
        mock_store.get_next_earnings.side_effect = mock_get_next_earnings
        
        checker = EarningsChecker(store=mock_store, threshold_days=3)
        results = checker.check_multiple_tickers(
            ["AAPL", "MSFT", "GOOGL"],
            reference_date=reference_date
        )
        
        assert len(results) == 3
        assert results["AAPL"].is_within_threshold is True
        assert results["MSFT"].is_within_threshold is False
        assert results["GOOGL"].has_upcoming_earnings is False
    
    def test_get_tickers_with_upcoming_earnings(self):
        """Test getting tickers with upcoming earnings."""
        mock_store = MagicMock()
        
        mock_store.get_upcoming_earnings.return_value = [
            EarningsEntry(ticker="AAPL", earnings_date=date(2024, 1, 17), time_of_day="AMC"),
            EarningsEntry(ticker="MSFT", earnings_date=date(2024, 1, 20), time_of_day="BMO"),
            EarningsEntry(ticker="AAPL", earnings_date=date(2024, 1, 25), time_of_day="AMC"),  # Duplicate
        ]
        
        checker = EarningsChecker(store=mock_store)
        tickers = checker.get_tickers_with_upcoming_earnings(
            ["AAPL", "MSFT", "GOOGL"],
            days_ahead=14
        )
        
        assert len(tickers) == 2  # Deduplicated
        assert "AAPL" in tickers
        assert "MSFT" in tickers


class TestBlackoutPeriod:
    """Tests for earnings blackout period detection."""
    
    def test_blackout_before_earnings(self):
        """Test blackout period before earnings."""
        mock_store = MagicMock()
        reference_date = date(2024, 1, 15)
        earnings_date = date(2024, 1, 17)  # 2 days away
        
        mock_store.get_next_earnings.return_value = EarningsEntry(
            ticker="AAPL",
            earnings_date=earnings_date,
            time_of_day="AMC"
        )
        
        checker = EarningsChecker(store=mock_store, threshold_days=3)
        is_blackout = checker.is_earnings_blackout("AAPL", reference_date=reference_date)
        
        assert is_blackout is True
    
    def test_blackout_after_earnings(self):
        """Test blackout period after earnings."""
        mock_store = MagicMock()
        reference_date = date(2024, 1, 17)
        past_earnings_date = date(2024, 1, 15)  # 2 days ago
        
        # First call returns no upcoming earnings
        # Second call (looking back) returns the past earnings
        mock_store.get_next_earnings.side_effect = [
            None,  # No upcoming earnings
            EarningsEntry(ticker="AAPL", earnings_date=past_earnings_date, time_of_day="AMC")
        ]
        
        checker = EarningsChecker(store=mock_store, threshold_days=3)
        is_blackout = checker.is_earnings_blackout("AAPL", reference_date=reference_date)
        
        assert is_blackout is True
    
    def test_not_in_blackout(self):
        """Test when not in blackout period."""
        mock_store = MagicMock()
        reference_date = date(2024, 1, 15)
        earnings_date = date(2024, 1, 25)  # 10 days away
        
        mock_store.get_next_earnings.return_value = EarningsEntry(
            ticker="AAPL",
            earnings_date=earnings_date,
            time_of_day="AMC"
        )
        
        checker = EarningsChecker(store=mock_store, threshold_days=3)
        is_blackout = checker.is_earnings_blackout("AAPL", reference_date=reference_date)
        
        assert is_blackout is False


class TestEarningsDataPopulation:
    """Tests for earnings data population."""
    
    def test_populate_single_earnings(self):
        """Test populating a single earnings entry."""
        mock_store = MagicMock()
        mock_store.update_earnings.return_value = "test-uuid-123"
        
        checker = EarningsChecker(store=mock_store)
        entry_id = checker.populate_earnings_data(
            ticker="AAPL",
            earnings_date=date(2024, 1, 25),
            time_of_day="AMC",
            fiscal_quarter="Q1 2024",
            source="test"
        )
        
        assert entry_id == "test-uuid-123"
        mock_store.update_earnings.assert_called_once()
        
        # Verify the entry passed to store
        call_args = mock_store.update_earnings.call_args[0][0]
        assert call_args.ticker == "AAPL"
        assert call_args.earnings_date == date(2024, 1, 25)
        assert call_args.time_of_day == "AMC"
        assert call_args.fiscal_quarter == "Q1 2024"
    
    def test_bulk_populate_earnings(self):
        """Test bulk populating earnings data."""
        mock_store = MagicMock()
        mock_store.update_earnings.side_effect = ["uuid-1", "uuid-2", "uuid-3"]
        
        checker = EarningsChecker(store=mock_store)
        
        earnings_data = [
            {
                "ticker": "AAPL",
                "earnings_date": "2024-01-25",
                "time_of_day": "AMC",
                "fiscal_quarter": "Q1 2024"
            },
            {
                "ticker": "MSFT",
                "earnings_date": date(2024, 1, 30),
                "time_of_day": "BMO"
            },
            {
                "ticker": "GOOGL",
                "earnings_date": "2024-02-05"
            }
        ]
        
        entry_ids = checker.bulk_populate_earnings(earnings_data)
        
        assert len(entry_ids) == 3
        assert entry_ids == ["uuid-1", "uuid-2", "uuid-3"]
        assert mock_store.update_earnings.call_count == 3
    
    def test_bulk_populate_with_date_conversion(self):
        """Test bulk populate handles date string conversion."""
        mock_store = MagicMock()
        mock_store.update_earnings.return_value = "uuid-1"
        
        checker = EarningsChecker(store=mock_store)
        
        earnings_data = [
            {
                "ticker": "AAPL",
                "earnings_date": "2024-01-25",  # String date
            }
        ]
        
        entry_ids = checker.bulk_populate_earnings(earnings_data)
        
        assert len(entry_ids) == 1
        
        # Verify date was converted
        call_args = mock_store.update_earnings.call_args[0][0]
        assert isinstance(call_args.earnings_date, date)
        assert call_args.earnings_date == date(2024, 1, 25)


class TestIntegration:
    """Integration-style tests."""
    
    def test_full_earnings_check_workflow(self):
        """Test complete earnings checking workflow."""
        mock_store = MagicMock()
        reference_date = date(2024, 1, 15)
        
        # Setup mock data
        mock_store.get_next_earnings.return_value = EarningsEntry(
            ticker="AAPL",
            earnings_date=date(2024, 1, 17),
            time_of_day="AMC",
            fiscal_quarter="Q1 2024"
        )
        
        # Create checker and check proximity
        checker = EarningsChecker(store=mock_store, threshold_days=3)
        result = checker.check_earnings_proximity("AAPL", reference_date=reference_date)
        
        # Verify complete result
        assert result.ticker == "AAPL"
        assert result.has_upcoming_earnings is True
        assert result.days_until_earnings == 2
        assert result.is_within_threshold is True
        assert result.warning_message is not None
        assert "WARNING" in result.warning_message
        
        # Verify blackout status
        is_blackout = checker.is_earnings_blackout("AAPL", reference_date=reference_date)
        assert is_blackout is True
