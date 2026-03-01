"""
Stock Screener Module
Scans a list of tickers to find which stocks have published
annual financial reports for the previous fiscal year.
"""

import yfinance as yf
import pandas as pd
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from scrapers.yahoo import scrape_financials
from screeners.stock_lists import STOCK_LISTS


def get_stock_lists():
    """Return available stock lists metadata."""
    return {
        key: {
            'name': val['name'],
            'description': val['description'],
            'count': len(val['tickers']),
            'market': val.get('market', 'IDX'),
        }
        for key, val in STOCK_LISTS.items()
    }


def _check_single_ticker(ticker_symbol: str, target_year: int) -> dict:
    """
    Check if a single ticker has published annual financial report
    for the target fiscal year (previous year).
    
    Returns a dict with ticker info and latest report status.
    """
    try:
        ticker = yf.Ticker(ticker_symbol)
        
        company_name = ticker_symbol
        sector = 'N/A'
        market_cap = None
        currency = 'USD'
        
        try:
            info = ticker.info
            if info:
                company_name = info.get('longName', info.get('shortName', ticker_symbol))
                sector = info.get('sector', 'N/A')
                market_cap = info.get('marketCap', None)
                currency = info.get('currency', 'USD')
                price = info.get('currentPrice', info.get('regularMarketPrice', None))
        except Exception:
            pass
        
        # Status flags
        has_report = False
        source = 'N/A' # Yahoo Financials, IDX API, or Yahoo News
        
        # 1. Check Yahoo Financials (Income Statement)
        try:
            income_stmt = ticker.income_stmt
            if income_stmt is not None and not income_stmt.empty:
                for col_candidate in income_stmt.columns:
                    if hasattr(col_candidate, 'year'):
                        col_data = income_stmt[col_candidate]
                        if col_data.notna().any():
                            latest_year = col_candidate.year
                            if latest_year >= target_year:
                                has_report = True
                                source = 'Yahoo Financials'
                            break
        except Exception:
            # If Yahoo fails (e.g. rate limit, decryption error), ignore and move to fallbacks
            pass
        
        # 2. Fallback: Check Official IDX API (if Yahoo is outdated)
        # This handles cases like NIKL.JK where report is on IDX but not yet parsed by Yahoo
        if not has_report:
            idx_status = _check_idx_official(ticker_symbol, target_year)
            if idx_status:
                has_report = True
                latest_year = target_year # Assumed based on file existence
                source = 'IDX Website (API)'
        
        # 3. Fallback: Check Yahoo News for "Financial Report" announcements
        if not has_report:
            if _check_news_for_report(ticker, target_year):
                has_report = True
                latest_year = target_year
                source = 'News (Likely Published)'

        return {
            'ticker': ticker_symbol,
            'company_name': company_name,
            'sector': sector,
            'currency': currency,
            'market_cap': market_cap,
            'price': price,
            'latest_report_year': latest_year,
            'has_current_year_report': has_report,
            'source': source,
            'status': 'success',
        }
    except Exception as e:
        return {
            'ticker': ticker_symbol,
            'company_name': ticker_symbol,
            'sector': 'N/A',
            'currency': 'N/A',
            'market_cap': None,
            'latest_report_year': None,
            'has_current_year_report': False,
            'source': 'Error',
            'status': 'error',
            'error': str(e),
        }


def _check_idx_official(ticker_symbol: str, target_year: int) -> bool:
    """
    Check IDX official API for financial report.
    Returns True if a report file exists for the target year.
    Safely handles 403 Forbidden (common on cloud IPs).
    """
    import requests
    
    # Remove .JK suffix for IDX query
    code = ticker_symbol.replace('.JK', '').replace('.jk', '')
    
    # IDX API Endpoint
    url = f"https://www.idx.co.id/primary/ListedCompany/GetFinancialReport?indexFrom=1&pageSize=12&year={target_year}&reportType=rdf&kodeEmiten={code}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://www.idx.co.id/id/perusahaan-tercatat/laporan-keuangan-dan-tahunan',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'X-Requested-With': 'XMLHttpRequest'
    }
    
    try:
        # Timeout short to avoid hanging if blocked
        r = requests.get(url, headers=headers, timeout=5)
        
        if r.status_code == 200:
            data = r.json()
            # Check if any results found
            if 'ResultCount' in data and data['ResultCount'] > 0:
                return True
            if 'Results' in data and len(data['Results']) > 0:
                return True
                
        return False
    except Exception:
        # Connection error, timeout, or non-JSON response -> assume failed/blocked
        return False


def _check_news_for_report(ticker_obj: yf.Ticker, target_year: int) -> bool:
    """
    Scan Yahoo Finance news for keywords indicating annual report release.
    """
    try:
        news = ticker_obj.news
        if not news:
            return False
            
        keywords = [
            "laporan keuangan", "financial statement", "financial report", 
            "laba bersih", "net profit", f"kinerja {target_year}", f"performance {target_year}"
        ]
        
        current_year_start = datetime(target_year + 1, 1, 1).timestamp() # Jan 1st of following year
        
        for item in news:
            title = item.get('title', '').lower()
            pub_time = item.get('providerPublishTime', 0)
            
            # Check if news is recent (from valid reporting period)
            if pub_time > 0 and pub_time >= current_year_start - 30*24*3600: # allow Dec prev year
                for kw in keywords:
                    if kw in title:
                        return True
                        
        return False
    except Exception:
        return False


def screen_stocks(list_key: str, custom_tickers: list = None) -> dict:
    """
    Screen a list of stocks to find which ones have published
    annual financial reports for the current year.
    
    Args:
        list_key: Key from STOCK_LISTS or 'custom'
        custom_tickers: List of custom ticker symbols (if list_key is 'custom')
    
    Returns:
        dict with screening results
    """
    current_year = datetime.now().year
    target_year = current_year - 1  # Check for previous year's report
    
    if list_key == 'custom' and custom_tickers:
        tickers = [t.strip().upper() for t in custom_tickers if t.strip()]
        list_name = 'Custom List'
        list_description = f'{len(tickers)} saham kustom'
    elif list_key in STOCK_LISTS:
        stock_list = STOCK_LISTS[list_key]
        tickers = stock_list['tickers']
        list_name = stock_list['name']
        list_description = stock_list['description']
    else:
        return {
            'success': False,
            'error': f'Unknown stock list: {list_key}'
        }
    
    if not tickers:
        return {
            'success': False,
            'error': 'No tickers provided.'
        }
    
    results = []
    total = len(tickers)
    
    # Use thread pool for parallel fetching (max 5 concurrent)
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_ticker = {
            executor.submit(_check_single_ticker, t, target_year): t
            for t in tickers
        }
        
        for future in as_completed(future_to_ticker):
            result = future.result()
            results.append(result)
    
    # Sort: current year reports first, then by ticker
    results.sort(key=lambda x: (not x['has_current_year_report'], x['ticker']))
    
    # Count stats
    with_report = [r for r in results if r['has_current_year_report']]
    without_report = [r for r in results if not r['has_current_year_report']]
    errors = [r for r in results if r['status'] == 'error']
    
    return {
        'success': True,
        'list_name': list_name,
        'list_description': list_description,
        'target_year': target_year,
        'total_scanned': total,
        'with_report_count': len(with_report),
        'without_report_count': len(without_report),
        'error_count': len(errors),
        'results': results,
    }
