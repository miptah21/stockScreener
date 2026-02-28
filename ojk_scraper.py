"""
ojk_scraper.py — Fetch real banking ratios (CASA, NPL, CAR, LDR, NIM, BOPO,
Coverage, CoC) from Indonesian bank data sources.

Data Sources (priority order):
1. sectors.app API (free tier, IDX-specific)
2. Cached ratios from latest audited annual reports (Big 5 banks)
3. Returns None → caller falls back to Yahoo Finance proxy

Author: Auto-generated for finance dashboard
"""

import logging
import requests
from typing import Optional

logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────────────────────
# Ticker → Bank Name mapping for IDX banks
# ────────────────────────────────────────────────────────────────────────────
BANK_NAMES = {
    'BBCA.JK': 'Bank Central Asia',
    'BBRI.JK': 'Bank Rakyat Indonesia',
    'BMRI.JK': 'Bank Mandiri',
    'BBNI.JK': 'Bank Negara Indonesia',
    'BBTN.JK': 'Bank Tabungan Negara',
    'BRIS.JK': 'Bank Syariah Indonesia',
    'BDMN.JK': 'Bank Danamon',
    'BNII.JK': 'Bank Maybank Indonesia',
    'MEGA.JK': 'Bank Mega',
    'BNGA.JK': 'Bank CIMB Niaga',
    'PNBN.JK': 'Bank Panin',
    'NISP.JK': 'Bank OCBC NISP',
    'BNLI.JK': 'Bank Permata',
    'BTPN.JK': 'Bank BTPN',
    'BJBR.JK': 'Bank BJB',
    'BJTM.JK': 'Bank Jatim',
}

# ────────────────────────────────────────────────────────────────────────────
# Cached ratios from latest published results
# Source: Each bank's published Annual Report / Investor Presentation
#
# Fields: casa, npl, car, ldr, nim, bopo, coverage, coc (as decimals)
# e.g. NPL 1.8% → 0.018
#
# Last updated: Feb 2026 — using FY2025 data where available
# ────────────────────────────────────────────────────────────────────────────
CACHED_RATIOS = {
    'BBCA.JK': {
        2025: {
            'casa': 0.850, 'npl': 0.017, 'car': 0.266, 'ldr': 0.770, 'nim': 0.057, 'bopo': 0.307, 'coverage': 1.838, 'coc': 0.004, 'source': 'BCA FY2025 Results'
        },
        2024: {
            'casa': 0.820, 'npl': 0.019, 'car': 0.290, 'ldr': 0.780, 'nim': 0.055, 'bopo': 0.400, 'coverage': 2.300, 'coc': 0.005, 'source': 'BCA FY2024 Results'
        }
    },
    'BBRI.JK': {
        2025: {
            'casa': 0.673, 'npl': 0.031, 'car': 0.254, 'ldr': 0.865, 'nim': 0.077, 'bopo': 0.679, 'coverage': 1.831, 'coc': 0.020, 'source': 'BRI Q3 2025 Report'
        },
        2024: {
            'casa': 0.650, 'npl': 0.030, 'car': 0.250, 'ldr': 0.840, 'nim': 0.076, 'bopo': 0.680, 'coverage': 2.000, 'coc': 0.022, 'source': 'BRI FY2024 Results'
        }
    },
    'BMRI.JK': {
        2025: {
            'casa': 0.708, 'npl': 0.010, 'car': 0.194, 'ldr': 0.876, 'nim': 0.049, 'bopo': 0.435, 'coverage': 2.00, 'coc': 0.005, 'source': 'Bank Mandiri FY2025 Results'
        },
        2024: {
            'casa': 0.750, 'npl': 0.012, 'car': 0.200, 'ldr': 0.860, 'nim': 0.050, 'bopo': 0.450, 'coverage': 2.500, 'coc': 0.006, 'source': 'Bank Mandiri FY2024 Results'
        }
    },
    'BBNI.JK': {
        2025: {
            'casa': 0.700, 'npl': 0.019, 'car': 0.207, 'ldr': 0.864, 'nim': 0.039, 'bopo': 0.451, 'coverage': 2.055, 'coc': 0.010, 'source': 'BNI FY2025 Results'
        },
        2024: {
            'casa': 0.690, 'npl': 0.021, 'car': 0.210, 'ldr': 0.850, 'nim': 0.040, 'bopo': 0.460, 'coverage': 2.100, 'coc': 0.012, 'source': 'BNI FY2024 Results'
        }
    },
    'BBTN.JK': {
        2025: {
            'casa': 0.550, 'npl': 0.031, 'car': 0.165, 'ldr': 0.886, 'nim': 0.042, 'bopo': 0.700, 'coverage': 1.30, 'coc': 0.015, 'source': 'BTN FY2025 Results'
        },
        2024: {
            'casa': 0.500, 'npl': 0.030, 'car': 0.160, 'ldr': 0.900, 'nim': 0.038, 'bopo': 0.728, 'coverage': 1.40, 'coc': 0.018, 'source': 'BTN FY2024 Results'
        }
    },
    # Default others to 2025 only format for now, but wrapped in year dict
    'BRIS.JK': { 2025: { 'casa': 0.616, 'npl': 0.018, 'car': 0.220, 'ldr': 0.839, 'nim': 0.057, 'bopo': 0.700, 'coverage': 1.50, 'coc': 0.008, 'source': 'BSI FY2025 Results' }},
    'BDMN.JK': { 2025: { 'casa': 0.403, 'npl': 0.018, 'car': 0.248, 'ldr': 0.930, 'nim': 0.066, 'bopo': 0.772, 'coverage': 2.749, 'coc': 0.010, 'source': 'Danamon Q3 2025 Report' }},
    'BNGA.JK': { 2025: { 'casa': 0.679, 'npl': 0.020, 'car': 0.247, 'ldr': 0.811, 'nim': 0.040, 'bopo': 0.732, 'coverage': 1.80, 'coc': 0.008, 'source': 'CIMB Niaga Q3 2025 Report' }},
    'MEGA.JK': { 2025: { 'casa': 0.350, 'npl': 0.017, 'car': 0.305, 'ldr': 0.645, 'nim': 0.042, 'bopo': 0.691, 'coverage': 2.00, 'coc': 0.005, 'source': 'Bank Mega FY2025 Results' }},
    'PNBN.JK': { 2025: { 'casa': 0.400, 'npl': 0.028, 'car': 0.375, 'ldr': 0.890, 'nim': 0.042, 'bopo': 0.798, 'coverage': 1.50, 'coc': 0.012, 'source': 'Bank Panin Q3 2025 Report' }},
    'NISP.JK': { 2025: { 'casa': 0.580, 'npl': 0.019, 'car': 0.245, 'ldr': 0.708, 'nim': 0.039, 'bopo': 0.692, 'coverage': 1.80, 'coc': 0.008, 'source': 'OCBC NISP FY2025 Results' }},
    'BNLI.JK': { 2025: { 'casa': 0.639, 'npl': 0.021, 'car': 0.346, 'ldr': 0.845, 'nim': 0.040, 'bopo': 0.766, 'coverage': 1.60, 'coc': 0.008, 'source': 'Bank Permata FY2025 Results' }},
    'BTPN.JK': { 2025: { 'casa': 0.350, 'npl': 0.031, 'car': 0.577, 'ldr': 0.848, 'nim': 0.230, 'bopo': 0.697, 'coverage': 1.50, 'coc': 0.010, 'source': 'BTPN Syariah FY2025 Results' }},
    'BJBR.JK': { 2025: { 'casa': 0.467, 'npl': 0.027, 'car': 0.198, 'ldr': 0.892, 'nim': 0.037, 'bopo': 0.780, 'coverage': 1.30, 'coc': 0.012, 'source': 'BJB Q3 2025 Report' }},
    'BJTM.JK': { 2025: { 'casa': 0.584, 'npl': 0.041, 'car': 0.243, 'ldr': 0.820, 'nim': 0.061, 'bopo': 0.750, 'coverage': 1.20, 'coc': 0.015, 'source': 'Bank Jatim Q3 2025 Report' }},
    'BNII.JK': { 2025: { 'casa': 0.523, 'npl': 0.024, 'car': 0.271, 'ldr': 0.775, 'nim': 0.043, 'bopo': 0.891, 'coverage': 1.50, 'coc': 0.010, 'source': 'Maybank Indonesia Q3 2025 Report' }},
}


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

    # 1. Try sectors.app API (if API key is configured)
    # Note: sectors.app usually returns latest TTM/Annual. 
    # If specific year is requested and sectors.app returns different year, we might mismatch.
    # For now, if year is None, we prioritize sectors.app. 
    # If year is specified, we prioritize cache if it matches, or check if sectors.app matches.
    
    # Strategy: Check cache first if year is specified, because cache has precise historical data.
    if year:
        cached = _get_cached_ratios(ticker, year)
        if cached:
            return cached

    # If no specific year requested, or cache miss for that year, try sectors.app (latest)
    if not year:
        result = _try_sectors_api(ticker)
        if result:
            return result

    # 2. Use cached ratios from annual reports (fallback or if year matches)
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
    import os
    api_key = os.environ.get('SECTORS_API_KEY')
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
    """Return cached ratios from hardcoded annual report data."""
    if ticker in CACHED_RATIOS:
        bank_data = CACHED_RATIOS[ticker]
        
        # bank_data is now Dict[Year, Dict] or Dict (for backward compatibility if any left)
        # Check structure
        first_val = next(iter(bank_data.values()))
        if not isinstance(first_val, dict):
            # Old structure: simple dict
            # Check if year matches or if year is None
            data_year = bank_data.get('year')
            if year and data_year != year:
                return None
            result = bank_data.copy()
            logger.info(f"[OJK Scraper] Using cached ratios for {ticker} ({result.get('source')})")
            return result
        
        # New structure: Dict[int, Dict]
        if year:
            if year in bank_data:
                result = bank_data[year].copy()
                result['year'] = year # Ensure year is in dict
                logger.info(f"[OJK Scraper] Using cached ratios for {ticker} FY{year}")
                return result
        else:
            # Return latest year
            max_year = max(bank_data.keys())
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
