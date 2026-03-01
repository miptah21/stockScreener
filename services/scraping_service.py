"""
Scraping Service — Orchestrates data fetching.
Wraps the scraper modules and provides clean entry points
for the API layer and future scheduler.
"""

import logging
from scrapers.yahoo import get_financials as _yahoo_get_financials

logger = logging.getLogger(__name__)


def get_financials(ticker, target_year=None, freq='annual'):
    """
    Fetch financial data for a ticker.
    Delegates to the Yahoo scraper (primary source).

    Args:
        ticker: Stock ticker symbol (e.g., 'BBCA.JK', 'AAPL')
        target_year: Optional target fiscal year for scoring
        freq: 'annual' or 'quarterly'

    Returns:
        dict with financial data and scoring results
    """
    return _yahoo_get_financials(ticker, target_year=target_year, freq=freq)
