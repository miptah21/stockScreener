"""
Alternative Financial Data Scraper Module (Multi-Source Fallback)
Uses multiple data sources when Yahoo Finance data is missing or incomplete.

Fallback chain:
1. Financial Modeling Prep (FMP) API — structured JSON, fast
2. SimFin API — structured JSON, good coverge
3. Macrotrends.net — HTML scraping, slower but no API key needed
4. Alpha Vantage — structured JSON, rate-limited (25/day free)

Note:
- FMP and Alpha Vantage free tiers only support US stocks
- Macrotrends only covers US stocks
- For IDX (.JK) tickers, Yahoo Finance remains the only free source
"""

import logging
import re
import time
import random
import traceback
import requests
from bs4 import BeautifulSoup
from config import Config
from utils.helpers import (
    safe_divide as _safe_div,
    format_number as _fmt_n,
    format_ratio as _fmt_r,
    format_percent as _pct,
    format_ratio_str as _ratio_s,
    format_big_number as _big,
    calculate_piotroski_standard as _calc_piotroski,
    METRICS_INFO,
)

logger = logging.getLogger(__name__)

# ─── API Keys (from centralized config) ────────────────────────────────────────

FMP_API_KEY = Config.FMP_API_KEY
ALPHA_VANTAGE_API_KEY = Config.ALPHA_VANTAGE_API_KEY
SIMFIN_API_KEY = Config.SIMFIN_API_KEY


# ─── Main entry point ──────────────────────────────────────────────────────────

def scrape_fallback_financials(ticker_symbol: str) -> dict:
    """
    Scrape financial data from alternative sources (FMP -> SimFin -> Macrotrends -> Alpha Vantage).
    Renamed from scrape_wsj_financials to reflect actual behavior.

    Returns dict with same structure as scrape_financials() from scraper.py.
    """
    ticker = ticker_symbol.strip().upper()

    # IDX tickers — no free fallback API supports these
    if ticker.endswith('.JK'):
        return {
            'success': False,
            'error': f'Tidak ada sumber data alternatif gratis untuk ticker IDX ({ticker}). Yahoo Finance adalah satu-satunya sumber gratis untuk saham Indonesia.',
            'data_source': 'none',
        }

    # Try FMP first (fastest, best structured data)
    logger.info("Trying FMP for %s", ticker)
    result = _try_fmp(ticker)
    if result and result.get('success'):
        result['data_source'] = 'fmp'
        return result
    
    # Try SimFin (API key required)
    logger.info("Trying SimFin for %s", ticker)
    result = _try_simfin(ticker)
    if result and result.get('success'):
        result['data_source'] = 'simfin'
        return result

    # Try Macrotrends (no API key, HTML scraping)
    logger.info("Trying Macrotrends for %s", ticker)
    result = _try_macrotrends(ticker)
    if result and result.get('success'):
        result['data_source'] = 'macrotrends'
        return result

    # Try Alpha Vantage (rate-limited)
    logger.info("Trying Alpha Vantage for %s", ticker)
    result = _try_alpha_vantage(ticker)
    if result and result.get('success'):
        result['data_source'] = 'alphavantage'
        return result

    return {
        'success': False,
        'error': f'Semua sumber data alternatif gagal untuk {ticker}. Periksa koneksi internet atau coba lagi nanti.',
        'data_source': 'none',
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  SOURCE 1: Financial Modeling Prep (FMP)
# ═══════════════════════════════════════════════════════════════════════════════

def _try_fmp(ticker: str) -> dict | None:
    """Fetch financial data from FMP stable API."""
    try:
        base = "https://financialmodelingprep.com/stable"
        params = {'symbol': ticker, 'period': 'annual', 'limit': 5, 'apikey': FMP_API_KEY}

        # Fetch all three statements
        income = _fmp_get(f"{base}/income-statement", params)
        balance = _fmp_get(f"{base}/balance-sheet-statement", params)
        cashflow = _fmp_get(f"{base}/cash-flow-statement", params)

        if not income:
            logger.warning("FMP: No income statement data for %s", ticker)
            return None

        # Build combined yearly data
        years = []
        yearly_data = []

        for i, inc in enumerate(income):
            year = inc.get('calendarYear', inc.get('date', '')[:4])
            if not year:
                continue
            years.append(str(year))

            # Find matching balance sheet and cash flow
            bal = balance[i] if i < len(balance) else {}
            cf = cashflow[i] if i < len(cashflow) else {}

            raw_net_income = _fmp_num(inc, 'netIncome')
            raw_revenue = _fmp_num(inc, 'revenue')
            raw_gross_profit = _fmp_num(inc, 'grossProfit')
            raw_total_assets = _fmp_num(bal, 'totalAssets')
            raw_current_assets = _fmp_num(bal, 'totalCurrentAssets')
            raw_current_liabilities = _fmp_num(bal, 'totalCurrentLiabilities')
            raw_long_term_debt = _fmp_num(bal, 'longTermDebt')
            raw_operating_cashflow = _fmp_num(cf, 'operatingCashFlow')
            raw_shares = _fmp_num(inc, 'weightedAverageShsOut')

            roa = _safe_div(raw_net_income, raw_total_assets)
            current_ratio = _safe_div(raw_current_assets, raw_current_liabilities)
            gross_margin = _safe_div(raw_gross_profit, raw_revenue)
            asset_turnover = _safe_div(raw_revenue, raw_total_assets)
            lt_debt_ratio = _safe_div(raw_long_term_debt, raw_total_assets)
            accrual = None
            if raw_net_income is not None and raw_operating_cashflow is not None and raw_total_assets and raw_total_assets != 0:
                accrual = (raw_net_income - raw_operating_cashflow) / raw_total_assets

            yearly_data.append({
                'year': str(year),
                'date': inc.get('date', f'{year}-12-31'),
                'raw': {
                    'net_income': _fmt_n(raw_net_income),
                    'total_revenue': _fmt_n(raw_revenue),
                    'gross_profit': _fmt_n(raw_gross_profit),
                    'total_assets': _fmt_n(raw_total_assets),
                    'current_assets': _fmt_n(raw_current_assets),
                    'current_liabilities': _fmt_n(raw_current_liabilities),
                    'long_term_debt': _fmt_n(raw_long_term_debt),
                    'operating_cashflow': _fmt_n(raw_operating_cashflow),
                    'shares_outstanding': _fmt_n(raw_shares),
                },
                'metrics': {
                    'roa': _fmt_r(roa),
                    'cash_flow': _fmt_n(raw_operating_cashflow),
                    'net_income': _fmt_n(raw_net_income),
                    'accrual': _fmt_r(accrual),
                    'lt_debt_ratio': _fmt_r(lt_debt_ratio),
                    'current_ratio': _fmt_r(current_ratio),
                    'gross_margin': _fmt_r(gross_margin),
                    'asset_turnover': _fmt_r(asset_turnover),
                },
            })

        if not yearly_data:
            return None

        currency = income[0].get('reportedCurrency', 'USD')

        return {
            'success': True,
            'ticker': ticker,
            'company': {
                'name': income[0].get('symbol', ticker),
                'sector': 'N/A',
                'industry': 'N/A',
                'currency': currency,
                'market_cap': None,
                'current_price': None,
            },
            'years': years,
            'data': yearly_data,
            'piotroski': _calc_piotroski(yearly_data),
            'is_bank': False,
            'metrics_info': _metrics_info(),
        }
    except Exception as e:
        logger.error("FMP error for %s: %s", ticker, e)
        return None


def _fmp_get(url, params):
    """Helper to fetch FMP API endpoint."""
    try:
        r = requests.get(url, params=params, timeout=15)
        if r.status_code == 200:
            data = r.json()
            return data if isinstance(data, list) else []
        logger.warning("FMP HTTP %d for %s", r.status_code, url)
        return []
    except Exception as e:
        logger.error("FMP request error: %s", e)
        return []


def _fmp_num(obj, key):
    v = obj.get(key)
    if v is None or v == '' or v == 'None':
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


# ═══════════════════════════════════════════════════════════════════════════════
#  SOURCE 2: SimFin API
# ═══════════════════════════════════════════════════════════════════════════════

def _try_simfin(ticker: str) -> dict | None:
    """Fetch financial data from SimFin API."""
    try:
        # Resolve ticker to SimFin ID (using search)
        simfin_id = _simfin_resolve_id(ticker)
        if not simfin_id:
            logger.warning("SimFin: Could not resolve ID for %s", ticker)
            return None
        
        base_url = "https://simfin.com/api/v2/companies/statements"
        params = {
            'statement': 'pl,bs,cf', # Profit & Loss, Balance Sheet, Cash Flow
            'ticker': ticker, 
            'period': 'fy', # Full Year
            'years': 5,
            'api-key': SIMFIN_API_KEY
        }
        
        # Strategy: Fetch PL first to check availability
        pl = _simfin_get(base_url, {**params, 'statement': 'pl'})
        bs = _simfin_get(base_url, {**params, 'statement': 'bs'})
        cf = _simfin_get(base_url, {**params, 'statement': 'cf'})

        if not pl or 'data' not in pl[0]:
            logger.warning("SimFin: No PL data for %s", ticker)
            return None

        # Helper to extract column index
        def get_col_idx(columns, name):
            if name in columns:
                return columns.index(name)
            return -1

        # Parse PL
        pl_data = pl[0].get('data', [])
        pl_cols = pl[0].get('columns', [])
        
        idx_date = get_col_idx(pl_cols, 'Publish Date')
        if idx_date == -1: idx_date = get_col_idx(pl_cols, 'Report Date')
        idx_year = get_col_idx(pl_cols, 'Fiscal Year')
        idx_rev = get_col_idx(pl_cols, 'Revenue')
        idx_ni = get_col_idx(pl_cols, 'Net Income')
        idx_gp = get_col_idx(pl_cols, 'Gross Profit')
        
        years = []
        yearly_data_map = {}

        for row in pl_data:
            year = str(row[idx_year])
            if year in years: continue
            years.append(year)
            
            yearly_data_map[year] = {
                'net_income': row[idx_ni] if idx_ni != -1 else None,
                'total_revenue': row[idx_rev] if idx_rev != -1 else None,
                'gross_profit': row[idx_gp] if idx_gp != -1 else None,
                'date': row[idx_date] if idx_date != -1 else f"{year}-12-31"
            }

        if not years:
            return None

        # Parse BS
        bs_data = bs[0].get('data', []) if bs else []
        bs_cols = bs[0].get('columns', []) if bs else []
        
        idx_bs_year = get_col_idx(bs_cols, 'Fiscal Year')
        idx_ta = get_col_idx(bs_cols, 'Total Assets')
        idx_ca = get_col_idx(bs_cols, 'Total Current Assets')
        idx_cl = get_col_idx(bs_cols, 'Total Current Liabilities')
        idx_ltd = get_col_idx(bs_cols, 'Long Term Debt')
        idx_shares = get_col_idx(bs_cols, 'Common Outstanding Shares')

        for row in bs_data:
            year = str(row[idx_bs_year])
            if year not in yearly_data_map: continue
            
            d = yearly_data_map[year]
            d['total_assets'] = row[idx_ta] if idx_ta != -1 else None
            d['current_assets'] = row[idx_ca] if idx_ca != -1 else None
            d['current_liabilities'] = row[idx_cl] if idx_cl != -1 else None
            d['long_term_debt'] = row[idx_ltd] if idx_ltd != -1 else None
            d['shares_outstanding'] = row[idx_shares] if idx_shares != -1 else None

        # Parse CF
        cf_data = cf[0].get('data', []) if cf else []
        cf_cols = cf[0].get('columns', []) if cf else []
        
        idx_cf_year = get_col_idx(cf_cols, 'Fiscal Year')
        idx_ocf = get_col_idx(cf_cols, 'Net Cash from Operating Activities')
        
        for row in cf_data:
            year = str(row[idx_cf_year])
            if year not in yearly_data_map: continue
             
            d = yearly_data_map[year]
            d['operating_cashflow'] = row[idx_ocf] if idx_ocf != -1 else None

        # Construct final list
        final_data = []
        for year in sorted(years, reverse=True)[:5]:
            raw = yearly_data_map[year]
            
            r_ni = raw.get('net_income')
            r_rev = raw.get('total_revenue')
            r_gp = raw.get('gross_profit')
            r_ta = raw.get('total_assets')
            r_ca = raw.get('current_assets')
            r_cl = raw.get('current_liabilities')
            r_ltd = raw.get('long_term_debt')
            r_ocf = raw.get('operating_cashflow')
            r_shares = raw.get('shares_outstanding')

            roa = _safe_div(r_ni, r_ta)
            cr = _safe_div(r_ca, r_cl)
            gm = _safe_div(r_gp, r_rev)
            at = _safe_div(r_rev, r_ta)
            ldr = _safe_div(r_ltd, r_ta)
            acc = None
            if r_ni is not None and r_ocf is not None and r_ta and r_ta != 0:
                acc = (r_ni - r_ocf) / r_ta

            final_data.append({
                'year': year, 'date': raw['date'],
                'raw': {
                    'net_income': _fmt_n(r_ni), 'total_revenue': _fmt_n(r_rev),
                    'gross_profit': _fmt_n(r_gp), 'total_assets': _fmt_n(r_ta),
                    'current_assets': _fmt_n(r_ca), 'current_liabilities': _fmt_n(r_cl),
                    'long_term_debt': _fmt_n(r_ltd), 'operating_cashflow': _fmt_n(r_ocf),
                    'shares_outstanding': _fmt_n(r_shares),
                },
                'metrics': {
                    'roa': _fmt_r(roa), 'cash_flow': _fmt_n(r_ocf), 'net_income': _fmt_n(r_ni),
                    'accrual': _fmt_r(acc), 'lt_debt_ratio': _fmt_r(ldr),
                    'current_ratio': _fmt_r(cr), 'gross_margin': _fmt_r(gm),
                    'asset_turnover': _fmt_r(at),
                },
            })

        return {
            'success': True, 'ticker': ticker,
            'company': {'name': ticker, 'sector': 'N/A', 'industry': 'N/A',
                        'currency': 'USD', 'market_cap': None, 'current_price': None},
            'years': sorted(years, reverse=True)[:5], 'data': final_data,
            'piotroski': _calc_piotroski(final_data), 'is_bank': False, 'metrics_info': _metrics_info(),
        }

    except Exception as e:
        logger.error("SimFin error: %s", e)
        return None

def _simfin_resolve_id(ticker: str) -> str | None:
    try:
        r = requests.get(
            "https://simfin.com/api/v2/companies/general",
            params={'ticker': ticker, 'api-key': SIMFIN_API_KEY},
            timeout=10
        )
        if r.status_code == 200:
            data = r.json()
            if data and isinstance(data, list) and 'data' in data[0]:
                return str(data[0]['data'][0][0]) 
    except Exception:
        pass
    return None

def _simfin_get(url, params):
    try:
        r = requests.get(url, params=params, timeout=15)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return []


# ═══════════════════════════════════════════════════════════════════════════════
#  SOURCE 3: Macrotrends.net (HTML scraping)
# ═══════════════════════════════════════════════════════════════════════════════

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
]

_MT_PAGES = {
    'revenue': 'revenue', 'net-income': 'net_income', 'gross-profit': 'gross_profit',
    'total-assets': 'total_assets', 'total-current-assets': 'current_assets',
    'total-current-liabilities': 'current_liabilities', 'long-term-debt': 'long_term_debt',
    'cash-flow-from-operating-activities': 'operating_cashflow',
}


def _try_macrotrends(ticker: str) -> dict | None:
    """Fetch data from macrotrends.net by scraping individual metric pages."""
    try:
        slug = _mt_resolve_slug(ticker)
        if not slug:
            logger.warning("Macrotrends: Could not resolve slug for %s", ticker)
            return None

        session = requests.Session()
        session.headers.update({
            'User-Agent': random.choice(_USER_AGENTS),
            'Accept': 'text/html,application/xhtml+xml,*/*',
            'Accept-Language': 'en-US,en;q=0.9',
        })

        base_url = f"https://www.macrotrends.net/stocks/charts/{slug}"
        all_data = {}

        for page, key in _MT_PAGES.items():
            url = f"{base_url}/{page}"
            try:
                r = session.get(url, timeout=20)
                if r.status_code == 200:
                    parsed = _mt_parse_table(r.text)
                    all_data[key] = parsed
                    logger.debug("Macrotrends %s: %d years", key, len(parsed))
                else:
                    all_data[key] = {}
            except Exception:
                all_data[key] = {}
            time.sleep(random.uniform(1.0, 2.5))

        # Determine years
        year_counts = {}
        for vals in all_data.values():
            for y in vals:
                year_counts[y] = year_counts.get(y, 0) + 1

        years = sorted([y for y, c in year_counts.items() if c >= 2], reverse=True)[:5]
        if not years:
            return None

        yearly_data = []
        for year in years:
            r_ni = all_data.get('net_income', {}).get(year)
            r_rev = all_data.get('revenue', {}).get(year)
            r_gp = all_data.get('gross_profit', {}).get(year)
            r_ta = all_data.get('total_assets', {}).get(year)
            r_ca = all_data.get('current_assets', {}).get(year)
            r_cl = all_data.get('current_liabilities', {}).get(year)
            r_ltd = all_data.get('long_term_debt', {}).get(year)
            r_ocf = all_data.get('operating_cashflow', {}).get(year)

            roa = _safe_div(r_ni, r_ta)
            cr = _safe_div(r_ca, r_cl)
            gm = _safe_div(r_gp, r_rev)
            at = _safe_div(r_rev, r_ta)
            ldr = _safe_div(r_ltd, r_ta)
            acc = None
            if r_ni is not None and r_ocf is not None and r_ta and r_ta != 0:
                acc = (r_ni - r_ocf) / r_ta

            yearly_data.append({
                'year': year, 'date': f'{year}-12-31',
                'raw': {
                    'net_income': _fmt_n(r_ni), 'total_revenue': _fmt_n(r_rev),
                    'gross_profit': _fmt_n(r_gp), 'total_assets': _fmt_n(r_ta),
                    'current_assets': _fmt_n(r_ca), 'current_liabilities': _fmt_n(r_cl),
                    'long_term_debt': _fmt_n(r_ltd), 'operating_cashflow': _fmt_n(r_ocf),
                    'shares_outstanding': None,
                },
                'metrics': {
                    'roa': _fmt_r(roa), 'cash_flow': _fmt_n(r_ocf), 'net_income': _fmt_n(r_ni),
                    'accrual': _fmt_r(acc), 'lt_debt_ratio': _fmt_r(ldr),
                    'current_ratio': _fmt_r(cr), 'gross_margin': _fmt_r(gm),
                    'asset_turnover': _fmt_r(at),
                },
            })

        if not yearly_data:
            return None

        name = slug.split('/')[1].replace('-', ' ').title() if '/' in slug else ticker
        return {
            'success': True, 'ticker': ticker,
            'company': {'name': name, 'sector': 'N/A', 'industry': 'N/A',
                        'currency': 'USD', 'market_cap': None, 'current_price': None},
            'years': years, 'data': yearly_data,
            'piotroski': _calc_piotroski(yearly_data), 'is_bank': False, 'metrics_info': _metrics_info(),
        }
    except Exception as e:
        logger.error("Macrotrends error: %s", e)
        return None


def _mt_resolve_slug(ticker: str) -> str | None:
    """Resolve ticker to macrotrends slug via search API."""
    try:
        session = requests.Session()
        session.headers.update({'User-Agent': random.choice(_USER_AGENTS)})
        r = session.get(
            f"https://www.macrotrends.net/assets/php/stock_search_process.php?input={ticker}&country=&sec_type=stock",
            timeout=15
        )
        if r.status_code == 200:
            results = r.json()
            for item in (results or []):
                if isinstance(item, list) and len(item) >= 2:
                    m = re.search(r'/stocks/charts/([^/]+/[^/]+)', item[1])
                    if m:
                        slug = m.group(1)
                        if slug.split('/')[0].upper() == ticker.upper():
                            return slug
            # Use first result if no exact match
            if results and isinstance(results[0], list) and len(results[0]) >= 2:
                m = re.search(r'/stocks/charts/([^/]+/[^/]+)', results[0][1])
                if m:
                    return m.group(1)
    except Exception as e:
        logger.error("Macrotrends slug resolution error: %s", e)
    return None


def _mt_parse_table(html: str) -> dict:
    """Parse macrotrends table, return {year: value_in_actual}."""
    soup = BeautifulSoup(html, 'html.parser')
    result = {}
    for table in soup.find_all('table'):
        for row in table.find_all('tr'):
            cells = row.find_all(['td', 'th'])
            if len(cells) < 2:
                continue
            date_text = cells[0].get_text(strip=True)
            ym = re.search(r'20\d{2}', date_text)
            if not ym:
                continue
            year = ym.group()
            val_text = cells[-1].get_text(strip=True).replace(',', '').replace('$', '').replace('\xa0', '')
            if val_text in ('-', '--', 'N/A', '—', ''):
                continue
            neg = False
            if val_text.startswith('(') and val_text.endswith(')'):
                neg = True
                val_text = val_text[1:-1]
            try:
                v = float(val_text)
                if neg:
                    v = -v
                if year not in result:
                    result[year] = v * 1_000_000  # macrotrends reports in millions
            except (ValueError, TypeError):
                continue
    return result


# ═══════════════════════════════════════════════════════════════════════════════
#  SOURCE 4: Alpha Vantage
# ═══════════════════════════════════════════════════════════════════════════════

def _try_alpha_vantage(ticker: str) -> dict | None:
    """Fetch financial data from Alpha Vantage API."""
    try:
        base_params = {'symbol': ticker, 'apikey': ALPHA_VANTAGE_API_KEY}

        income = requests.get('https://www.alphavantage.co/query',
                              params={**base_params, 'function': 'INCOME_STATEMENT'}, timeout=15).json()
        time.sleep(1)  # Respect rate limits
        balance = requests.get('https://www.alphavantage.co/query',
                               params={**base_params, 'function': 'BALANCE_SHEET'}, timeout=15).json()
        time.sleep(1)
        cashflow = requests.get('https://www.alphavantage.co/query',
                                params={**base_params, 'function': 'CASH_FLOW'}, timeout=15).json()

        inc_reports = income.get('annualReports', [])[:5]
        bal_reports = balance.get('annualReports', [])[:5]
        cf_reports = cashflow.get('annualReports', [])[:5]

        if not inc_reports:
            logger.warning("Alpha Vantage: No data for %s", ticker)
            return None

        years = []
        yearly_data = []

        for i, inc in enumerate(inc_reports):
            year = inc.get('fiscalDateEnding', '')[:4]
            if not year:
                continue
            years.append(year)

            bal = bal_reports[i] if i < len(bal_reports) else {}
            cf = cf_reports[i] if i < len(cf_reports) else {}

            r_ni = _av_num(inc, 'netIncome')
            r_rev = _av_num(inc, 'totalRevenue')
            r_gp = _av_num(inc, 'grossProfit')
            r_ta = _av_num(bal, 'totalAssets')
            r_ca = _av_num(bal, 'totalCurrentAssets')
            r_cl = _av_num(bal, 'totalCurrentLiabilities')
            r_ltd = _av_num(bal, 'longTermDebt')
            r_ocf = _av_num(cf, 'operatingCashflow')
            r_shares = _av_num(inc, 'commonStockSharesOutstanding')

            roa = _safe_div(r_ni, r_ta)
            cr = _safe_div(r_ca, r_cl)
            gm = _safe_div(r_gp, r_rev)
            at = _safe_div(r_rev, r_ta)
            ldr = _safe_div(r_ltd, r_ta)
            acc = None
            if r_ni is not None and r_ocf is not None and r_ta and r_ta != 0:
                acc = (r_ni - r_ocf) / r_ta

            yearly_data.append({
                'year': year, 'date': inc.get('fiscalDateEnding', f'{year}-12-31'),
                'raw': {
                    'net_income': _fmt_n(r_ni), 'total_revenue': _fmt_n(r_rev),
                    'gross_profit': _fmt_n(r_gp), 'total_assets': _fmt_n(r_ta),
                    'current_assets': _fmt_n(r_ca), 'current_liabilities': _fmt_n(r_cl),
                    'long_term_debt': _fmt_n(r_ltd), 'operating_cashflow': _fmt_n(r_ocf),
                    'shares_outstanding': _fmt_n(r_shares),
                },
                'metrics': {
                    'roa': _fmt_r(roa), 'cash_flow': _fmt_n(r_ocf), 'net_income': _fmt_n(r_ni),
                    'accrual': _fmt_r(acc), 'lt_debt_ratio': _fmt_r(ldr),
                    'current_ratio': _fmt_r(cr), 'gross_margin': _fmt_r(gm),
                    'asset_turnover': _fmt_r(at),
                },
            })

        if not yearly_data:
            return None

        currency = income.get('annualReports', [{}])[0].get('reportedCurrency', 'USD')
        return {
            'success': True, 'ticker': ticker,
            'company': {'name': income.get('symbol', ticker), 'sector': 'N/A', 'industry': 'N/A',
                        'currency': currency, 'market_cap': None, 'current_price': None},
            'years': years, 'data': yearly_data,
            'piotroski': _calc_piotroski(yearly_data), 'is_bank': False, 'metrics_info': _metrics_info(),
        }
    except Exception as e:
        logger.error("Alpha Vantage error: %s", e)
        return None


def _av_num(obj, key):
    v = obj.get(key)
    if v is None or v == 'None' or v == '':
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


# ═══════════════════════════════════════════════════════════════════════════════
#  Shared helpers — imported from financial_helpers.py
#  _safe_div, _fmt_n, _fmt_r, _pct, _ratio_s, _big,
#  _calc_piotroski, METRICS_INFO
# ═══════════════════════════════════════════════════════════════════════════════


def _metrics_info() -> dict:
    """Return shared METRICS_INFO dict (backward compat wrapper)."""
    return METRICS_INFO

