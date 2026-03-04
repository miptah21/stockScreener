"""
ojk_scraper.py — Fetch real banking ratios (CASA, NPL, CAR, LDR, NIM, BOPO,
Coverage, CoC) from Indonesian bank data sources.

Data Sources (priority order):
1. sectors.app API (free tier, IDX-specific)
2. Cached ratios from data/bank_ratios.json (audited annual reports)
3. Returns None → caller falls back to Yahoo Finance proxy

Author: Auto-generated for finance dashboard
"""

import json
import logging
import os
import requests
from typing import Optional
from config import Config

logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────────────────────
# Load bank data from external JSON file
# ────────────────────────────────────────────────────────────────────────────
_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
_RATIOS_FILE = os.path.join(_DATA_DIR, 'bank_ratios.json')

def _load_bank_data():
    """Load bank ratios and names from external JSON file."""
    try:
        with open(_RATIOS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get('bank_names', {}), data.get('ratios', {})
    except FileNotFoundError:
        logger.warning("bank_ratios.json not found at %s — using empty data", _RATIOS_FILE)
        return {}, {}
    except json.JSONDecodeError as e:
        logger.error("Failed to parse bank_ratios.json: %s", e)
        return {}, {}

BANK_NAMES, _RAW_RATIOS = _load_bank_data()

# Convert string year keys to int for backward compatibility
CACHED_RATIOS = {}
for ticker, year_data in _RAW_RATIOS.items():
    CACHED_RATIOS[ticker] = {}
    for year_str, ratios in year_data.items():
        try:
            CACHED_RATIOS[ticker][int(year_str)] = ratios
        except (ValueError, TypeError):
            CACHED_RATIOS[ticker][year_str] = ratios


def get_bank_ratios(ticker: str, year: int = None) -> Optional[dict]:
    """
    Fetch real banking ratios for a given ticker.
    If year is provided, tries to fetch specific year data.
    If year is None, returns the latest available year.

    Returns dict with keys:
        casa, npl, car, ldr, nim, bopo, coverage, coc, source, year
    Or None if data not available.
    """
    if not ticker:
        return None

    # Normalize ticker
    ticker = ticker.upper()
    if not ticker.endswith('.JK'):
        ticker += '.JK'

    # Strategy: Check cache first if year is specified (precise historical data)
    if year:
        cached = _get_cached_ratios(ticker, year)
        if cached:
            return cached

    # If no specific year requested, or cache miss, try sectors.app (latest)
    if not year:
        result = _try_sectors_api(ticker)
        if result:
            return result

    # Fallback to cached ratios
    result = _get_cached_ratios(ticker, year)
    if result:
        return result

    logger.info(f"[OJK Scraper] No real ratios found for {ticker} (Year: {year}), fallback to Yahoo proxy")
    return None


def _try_sectors_api(ticker: str) -> Optional[dict]:
    """
    Try fetching from sectors.app API.
    Requires SECTORS_API_KEY environment variable.
    """
    api_key = Config.SECTORS_API_KEY
    if not api_key:
        return None

    # Sectors.app uses ticker without .JK suffix
    symbol = ticker.replace('.JK', '')

    try:
        url = f'https://api.sectors.app/v1/company/report/{symbol}/'
        headers = {'Authorization': api_key}
        r = requests.get(url, headers=headers, timeout=10)

        if r.status_code != 200:
            logger.debug(f"[Sectors API] {r.status_code} for {symbol}")
            return None

        data = r.json()

        # Extract ratios from sectors.app response
        ratios = {}
        financials = data.get('financials', {})

        # Map sectors.app fields to our fields
        field_map = {
            'casa': ['casa_ratio', 'casa'],
            'npl': ['npl_gross', 'npl'],
            'car': ['car', 'capital_adequacy_ratio'],
            'ldr': ['ldr', 'loan_to_deposit_ratio'],
            'nim': ['nim', 'net_interest_margin'],
            'bopo': ['bopo', 'cost_to_income_ratio'],
            'coverage': ['coverage_ratio', 'npl_coverage'],
            'coc': ['coc', 'cost_of_credit'],
        }

        for our_key, api_keys in field_map.items():
            for ak in api_keys:
                v = financials.get(ak) or data.get(ak)
                if v is not None:
                    # Convert percentage to decimal if needed
                    ratios[our_key] = v / 100 if v > 1 else v
                    break

        if ratios:
            ratios['source'] = 'sectors.app API'
            ratios['year'] = data.get('year', 'latest')
            return ratios

    except Exception as e:
        logger.debug(f"[Sectors API] Error: {e}")

    return None


def _get_cached_ratios(ticker: str, year: int = None) -> Optional[dict]:
    """Return cached ratios from JSON data file."""
    if ticker in CACHED_RATIOS:
        bank_data = CACHED_RATIOS[ticker]

        if year:
            if year in bank_data:
                result = bank_data[year].copy()
                result['year'] = year
                logger.info(f"[OJK Scraper] Using cached ratios for {ticker} FY{year}")
                return result
        else:
            # Return latest year
            int_keys = [k for k in bank_data.keys() if isinstance(k, int)]
            if int_keys:
                max_year = max(int_keys)
                result = bank_data[max_year].copy()
                result['year'] = max_year
                logger.info(f"[OJK Scraper] Using cached ratios for {ticker} FY{max_year} (Latest)")
                return result

    return None


def get_available_tickers() -> list:
    """Return list of tickers with available real ratio data."""
    return list(CACHED_RATIOS.keys())


def format_ratios_report(ratios: dict) -> str:
    """Format ratios dict into a readable report string."""
    if not ratios:
        return "No data available"

    lines = [f"Source: {ratios.get('source', '?')} (FY{ratios.get('year', '?')})"]
    fields = [
        ('CASA',     'casa',     True),
        ('NPL',      'npl',      True),
        ('CAR',      'car',      True),
        ('LDR',      'ldr',      True),
        ('NIM',      'nim',      True),
        ('BOPO',     'bopo',     True),
        ('Coverage', 'coverage', False),  # coverage is >1 (e.g. 3.15 = 315%)
        ('CoC',      'coc',      True),
    ]

    for label, key, is_pct in fields:
        v = ratios.get(key)
        if v is not None:
            if is_pct:
                lines.append(f"  {label:12s}: {v*100:.2f}%")
            else:
                lines.append(f"  {label:12s}: {v*100:.0f}%")
        else:
            lines.append(f"  {label:12s}: N/A")

    return '\n'.join(lines)


# ────────────────────────────────────────────────────────────────────────────
# CLI usage
# ────────────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    import sys
    tickers = sys.argv[1:] or ['BBCA.JK', 'BBRI.JK', 'BMRI.JK', 'BBNI.JK', 'BBTN.JK']
    for t in tickers:
        print(f"\n{'='*50}")
        print(f"Ratios for {t}")
        print('='*50)
        ratios = get_bank_ratios(t)
        print(format_ratios_report(ratios))
