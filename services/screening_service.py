"""
Screening Service — Orchestrates stock screening operations.
Wraps the screener modules and provides clean entry points
for the API layer and future scheduler.
"""

import logging
from screeners.report_screener import get_stock_lists as _get_stock_lists
from screeners.report_screener import screen_stocks as _screen_stocks
from screeners.technical_screener import run_technical_screen as _run_technical_screen
from screeners.simple_screener import run_simple_screen as _run_simple_screen
from utils.constants import MARKET_CAP_PRESETS

logger = logging.getLogger(__name__)


def get_stock_lists():
    """Return available stock lists metadata."""
    return _get_stock_lists()


def screen_stocks(list_key, custom_tickers=None):
    """
    Screen stocks for annual report availability.

    Args:
        list_key: Key from STOCK_LISTS or 'custom'
        custom_tickers: List of custom ticker symbols
    """
    return _screen_stocks(list_key, custom_tickers)


def run_technical_screen(list_key=None, custom_tickers=None,
                         min_market_cap=None, max_market_cap=None,
                         market_cap_preset=None,
                         offset=None, limit=None):
    """
    Run multi-indicator technical screening.

    Args:
        list_key: Stock list key or 'custom'
        custom_tickers: Custom tickers if list_key='custom'
        min_market_cap/max_market_cap: Market cap range filter
        market_cap_preset: Preset key like 'small', 'mid', 'large'
        offset: Starting index for chunked requests
        limit: Number of tickers per chunk
    """
    # Resolve preset into min/max if provided
    if market_cap_preset and market_cap_preset in MARKET_CAP_PRESETS:
        preset = MARKET_CAP_PRESETS[market_cap_preset]
        min_market_cap = min_market_cap or preset.get('min')
        max_market_cap = max_market_cap or preset.get('max')

    return _run_technical_screen(
        list_key=list_key,
        custom_tickers=custom_tickers,
        min_market_cap=min_market_cap,
        max_market_cap=max_market_cap,
        offset=offset,
        limit=limit,
    )


def run_simple_screen(list_key=None, custom_tickers=None,
                      market_cap_preset=None,
                      offset=None, limit=None):
    """
    Run simple RSI + MACD screening.

    Args:
        list_key: Stock list key or 'custom'
        custom_tickers: Custom tickers if list_key='custom'
        market_cap_preset: Preset key like 'small', 'mid', 'large'
        offset: Starting index for chunked requests
        limit: Number of tickers per chunk
    """
    # Resolve preset into min/max
    min_mc = None
    max_mc = None
    if market_cap_preset and market_cap_preset in MARKET_CAP_PRESETS:
        preset = MARKET_CAP_PRESETS[market_cap_preset]
        min_mc = preset.get('min')
        max_mc = preset.get('max')

    return _run_simple_screen(
        list_key=list_key,
        custom_tickers=custom_tickers,
        min_market_cap=min_mc,
        max_market_cap=max_mc,
        offset=offset,
        limit=limit,
    )

