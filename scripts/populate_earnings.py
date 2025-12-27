"""
Populate earnings calendar data for major tech tickers.

This script populates the earnings_calendar table with upcoming
earnings dates for the 10 major tech stocks used in the system.
"""

import sys
from datetime import date, timedelta
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.safety.earnings import EarningsChecker


def get_upcoming_earnings_data():
    """
    Get earnings data for major tech stocks.
    
    Note: These are example dates. In production, you would fetch
    real earnings dates from a financial data API (e.g., Alpha Vantage,
    Yahoo Finance, or a paid service like Polygon.io).
    
    Returns:
        List of earnings data dictionaries
    """
    # Base date for calculating upcoming earnings
    today = date.today()
    
    # Example earnings data - adjust dates as needed
    # Format: ticker, days_from_today, time_of_day, fiscal_quarter
    earnings_schedule = [
        # Tech stocks
        ("AAPL", 15, "AMC", "Q1 2025"),   # Apple
        ("MSFT", 22, "AMC", "Q2 2025"),   # Microsoft
        ("GOOGL", 28, "AMC", "Q4 2024"),  # Alphabet
        ("AMZN", 35, "AMC", "Q4 2024"),   # Amazon
        ("NVDA", 25, "AMC", "Q4 2024"),   # NVIDIA
        
        # Financials
        ("JPM", 18, "BMO", "Q4 2024"),    # JPMorgan Chase
        ("BAC", 20, "BMO", "Q4 2024"),    # Bank of America
        
        # Safe Havens (ETFs - no earnings, but we track for consistency)
        ("GLD", 999, "UNKNOWN", "N/A"),   # Gold ETF - no earnings
        ("TLT", 999, "UNKNOWN", "N/A"),   # Treasury Bond ETF - no earnings
        ("SPY", 999, "UNKNOWN", "N/A"),   # S&P 500 ETF - no earnings
    ]
    
    earnings_data = []
    for ticker, days_offset, time_of_day, fiscal_quarter in earnings_schedule:
        earnings_date = today + timedelta(days=days_offset)
        earnings_data.append({
            "ticker": ticker,
            "earnings_date": earnings_date.isoformat(),
            "time_of_day": time_of_day,
            "fiscal_quarter": fiscal_quarter,
            "source": "manual_population"
        })
    
    return earnings_data


def populate_earnings(dry_run: bool = False):
    """
    Populate earnings calendar with data.
    
    Args:
        dry_run: If True, only print what would be done
    """
    print("=" * 70)
    print("Earnings Calendar Population Script")
    print("=" * 70)
    print()
    
    # Get earnings data
    earnings_data = get_upcoming_earnings_data()
    
    print(f"Preparing to populate {len(earnings_data)} earnings entries:")
    print()
    
    # Display what will be populated
    for entry in earnings_data:
        print(f"  {entry['ticker']:6} - {entry['earnings_date']} "
              f"({entry['time_of_day']}) - {entry['fiscal_quarter']}")
    
    print()
    
    if dry_run:
        print("DRY RUN MODE - No data will be written to database")
        print()
        return
    
    # Initialize checker and populate
    print("Connecting to database and populating earnings...")
    try:
        checker = EarningsChecker()
        entry_ids = checker.bulk_populate_earnings(earnings_data)
        
        print()
        print("✓ Successfully populated earnings calendar!")
        print(f"  Created/updated {len(entry_ids)} entries")
        print()
        
        # Verify by checking a few tickers
        print("Verification - checking upcoming earnings:")
        print()
        
        test_tickers = ["AAPL", "MSFT", "NVDA", "JPM", "BAC"]
        for ticker in test_tickers:
            result = checker.check_earnings_proximity(ticker)
            if result.has_upcoming_earnings:
                status = "⚠️  WITHIN THRESHOLD" if result.is_within_threshold else "✓  Scheduled"
                print(f"  {ticker:6} - {result.days_until_earnings} days away "
                      f"({result.earnings_date}) - {status}")
            else:
                print(f"  {ticker:6} - No upcoming earnings found")
        
        print()
        print("=" * 70)
        print("Earnings population complete!")
        print("=" * 70)
        
    except Exception as e:
        print()
        print(f"✗ Error populating earnings: {e}")
        print()
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Populate earnings calendar for major tech stocks"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without writing to database"
    )
    
    args = parser.parse_args()
    
    populate_earnings(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
