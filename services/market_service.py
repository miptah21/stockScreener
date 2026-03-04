"""
Market Overview Service — IHSG summary, top movers, sector performance, breadth.
All data fetched from Yahoo Finance with 5-minute TTL cache.
"""

import logging
import random

import yfinance as yf

from screeners.stock_lists import STOCK_LISTS
from utils.cache import cached, market_cache

logger = logging.getLogger(__name__)

# Sectors to track (exclude non-sector lists)
SECTOR_KEYS = [
    'idx_finansial', 'idx_mineral_energi', 'idx_mineral_non_energi',
    'idx_utilitas', 'idx_industri_proses', 'idx_layanan_teknologi',
    'idx_komunikasi', 'idx_konsumen_tidak_tahan_lama',
    'idx_layanan_kesehatan', 'idx_layanan_konsumen',
    'idx_transportasi', 'idx_perdagangan_ritel',
    'idx_produsen_pabrikan', 'idx_layanan_industri',
    'idx_layanan_distribusi', 'idx_teknologi_kesehatan',
    'idx_konsumen_tahan_lama', 'idx_layanan_komersil',
    'idx_teknologi_elektronik',
]

# Sector emoji mapping for UI
SECTOR_EMOJI = {
    'idx_finansial': '🏦', 'idx_mineral_energi': '⛏️',
    'idx_mineral_non_energi': '🪨', 'idx_utilitas': '⚡',
    'idx_industri_proses': '🏭', 'idx_layanan_teknologi': '💻',
    'idx_komunikasi': '📡', 'idx_konsumen_tidak_tahan_lama': '🛒',
    'idx_layanan_kesehatan': '🏥', 'idx_layanan_konsumen': '🎭',
    'idx_transportasi': '🚢', 'idx_perdagangan_ritel': '🏪',
    'idx_produsen_pabrikan': '🔧', 'idx_layanan_industri': '🏗️',
    'idx_layanan_distribusi': '📦', 'idx_teknologi_kesehatan': '🧬',
    'idx_konsumen_tahan_lama': '🏠', 'idx_layanan_komersil': '💼',
    'idx_teknologi_elektronik': '📱',
}

# Sample size per sector (to avoid too many API calls)
SECTOR_SAMPLE_SIZE = 5


def _safe_float(val, default=0.0):
    """Safely convert to float."""
    try:
        f = float(val)
        return default if (f != f) else f  # NaN check
    except (TypeError, ValueError):
        return default


@cached(market_cache, key_func=lambda a, kw: 'ihsg')
def get_ihsg_summary():
    """Fetch IHSG (^JKSE) index summary: price, change, volume, OHLC."""
    try:
        ticker = yf.Ticker('^JKSE')
        hist = ticker.history(period='5d')

        if hist.empty:
            return {'success': False, 'error': 'No IHSG data available'}

        latest = hist.iloc[-1]
        prev = hist.iloc[-2] if len(hist) >= 2 else latest

        close = _safe_float(latest['Close'])
        prev_close = _safe_float(prev['Close'])
        change = round(close - prev_close, 2)
        change_pct = round((change / prev_close) * 100, 2) if prev_close > 0 else 0

        return {
            'success': True,
            'value': round(close, 2),
            'change': change,
            'change_pct': change_pct,
            'open': round(_safe_float(latest['Open']), 2),
            'high': round(_safe_float(latest['High']), 2),
            'low': round(_safe_float(latest['Low']), 2),
            'volume': int(_safe_float(latest['Volume'])),
            'prev_close': round(prev_close, 2),
            'date': hist.index[-1].strftime('%Y-%m-%d'),
        }
    except Exception as e:
        logger.exception("Error fetching IHSG summary")
        return {'success': False, 'error': str(e)}


@cached(market_cache, key_func=lambda a, kw: 'movers')
def get_top_movers(n=10):
    """
    Get top N gainers and losers from LQ45.
    Uses yfinance batch download for efficiency.
    """
    try:
        lq45 = STOCK_LISTS.get('idx_lq45', {}).get('tickers', [])
        if not lq45:
            return {'success': False, 'error': 'LQ45 ticker list not found'}

        tickers_str = ' '.join(lq45)
        data = yf.download(tickers_str, period='5d', group_by='ticker',
                           progress=False, threads=True)

        results = []
        for ticker in lq45:
            try:
                if len(lq45) == 1:
                    df = data
                else:
                    df = data[ticker]

                if df.empty or len(df) < 2:
                    continue

                latest_close = _safe_float(df['Close'].iloc[-1])
                prev_close = _safe_float(df['Close'].iloc[-2])

                if prev_close <= 0 or latest_close <= 0:
                    continue

                change = round(latest_close - prev_close, 2)
                change_pct = round((change / prev_close) * 100, 2)

                results.append({
                    'ticker': ticker,
                    'price': round(latest_close, 2),
                    'change': change,
                    'change_pct': change_pct,
                    'volume': int(_safe_float(df['Volume'].iloc[-1])),
                })
            except Exception:
                continue

        # Sort by change_pct
        gainers = sorted(results, key=lambda x: x['change_pct'], reverse=True)[:n]
        losers = sorted(results, key=lambda x: x['change_pct'])[:n]

        return {
            'success': True,
            'gainers': gainers,
            'losers': losers,
            'all_results': results,
            'total_stocks': len(results),
        }
    except Exception as e:
        logger.exception("Error fetching top movers")
        return {'success': False, 'error': str(e)}


@cached(market_cache, key_func=lambda a, kw: 'sectors')
def get_sector_performance():
    """
    Calculate average daily change% per sector.
    Samples SECTOR_SAMPLE_SIZE tickers per sector,
    then downloads ALL samples in a single batch for efficiency.
    """
    try:
        # 1. Collect all samples across sectors
        sector_samples = {}  # key -> {info, sample}
        all_tickers = set()

        for key in SECTOR_KEYS:
            info = STOCK_LISTS.get(key)
            if not info:
                continue
            tickers = info['tickers']
            sample = random.sample(tickers, min(SECTOR_SAMPLE_SIZE, len(tickers)))
            sector_samples[key] = {'info': info, 'sample': sample}
            all_tickers.update(sample)

        if not all_tickers:
            return {'success': False, 'error': 'No sector tickers found'}

        # 2. Single batch download for ALL tickers
        tickers_list = list(all_tickers)
        tickers_str = ' '.join(tickers_list)
        data = yf.download(tickers_str, period='5d', group_by='ticker',
                           progress=False, threads=True)

        is_single = len(tickers_list) == 1

        # 3. Pre-compute change% for each ticker
        ticker_changes = {}
        for t in tickers_list:
            try:
                if is_single:
                    df = data
                else:
                    df = data[t]

                if df.empty or len(df) < 2:
                    continue

                latest = _safe_float(df['Close'].iloc[-1])
                prev = _safe_float(df['Close'].iloc[-2])
                if prev > 0 and latest > 0:
                    ticker_changes[t] = ((latest - prev) / prev) * 100
            except Exception:
                continue

        # 4. Group by sector and compute averages
        sectors = []
        for key, entry in sector_samples.items():
            info = entry['info']
            sample = entry['sample']
            changes = [ticker_changes[t] for t in sample if t in ticker_changes]

            avg_change = round(sum(changes) / len(changes), 2) if changes else 0.0

            sectors.append({
                'key': key,
                'name': info['name'],
                'emoji': SECTOR_EMOJI.get(key, '📊'),
                'change_pct': avg_change,
                'sample_size': len(changes),
                'total_tickers': len(info['tickers']),
            })

        # Sort by change_pct descending
        sectors.sort(key=lambda x: x['change_pct'], reverse=True)

        return {'success': True, 'sectors': sectors}
    except Exception as e:
        logger.exception("Error fetching sector performance")
        return {'success': False, 'error': str(e)}


@cached(market_cache, key_func=lambda a, kw: 'breadth')
def get_market_breadth():
    """
    Market breadth: count advancing/declining/flat stocks from ALL LQ45 data.
    Uses the full results list from get_top_movers.
    """
    try:
        movers = get_top_movers()
        if not movers.get('success'):
            return {'success': False, 'error': 'Could not fetch movers data'}

        all_stocks = movers.get('all_results', [])
        if not all_stocks:
            return {'success': False, 'error': 'No stock data available'}

        advancing = sum(1 for s in all_stocks if s['change_pct'] > 0)
        declining = sum(1 for s in all_stocks if s['change_pct'] < 0)
        flat = sum(1 for s in all_stocks if s['change_pct'] == 0)
        total = len(all_stocks)

        return {
            'success': True,
            'advancing': advancing,
            'declining': declining,
            'flat': flat,
            'total': total,
            'ad_ratio': round(advancing / max(declining, 1), 2),
        }
    except Exception as e:
        logger.exception("Error calculating market breadth")
        return {'success': False, 'error': str(e)}


def get_market_overview():
    """Aggregate all market data into a single response."""
    return {
        'ihsg': get_ihsg_summary(),
        'movers': get_top_movers(),
        'sectors': get_sector_performance(),
        'breadth': get_market_breadth(),
    }
