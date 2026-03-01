"""
Simple Technical Screener — RSI(14) + MACD(12,26,9)
Original 2-indicator screener with composite scoring (-4 to +4).
Uses yfinance historical data and pandas for all calculations.
"""

import logging
import yfinance as yf
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
from screeners.stock_lists import STOCK_LISTS
from utils.indicators import calculate_rsi, classify_rsi, calculate_macd, detect_macd_crossover

logger = logging.getLogger(__name__)


# ─── Composite Signal ────────────────────────────────────────────────
def compute_composite_signal(rsi_zone: str, macd_cross_type: str) -> dict:
    """
    Combine RSI zone and MACD crossover into a composite signal.

    Scoring:
        RSI:  oversold=+2, emerging_bullish=+1, neutral/neutral_low=0, bullish=+1, overbought=-2
        MACD: bullish_cross=+2, above_signal=+1, below_signal=-1, bearish_cross=-2

    Total score mapped to signal:
        >= 3  → Strong Buy
        1-2   → Buy
        -1-0  → Neutral
        -2    → Sell
        <= -3 → Strong Sell
    """
    rsi_scores = {
        'oversold': 2,
        'emerging_bullish': 1,
        'neutral_low': 0,
        'neutral': 0,
        'bullish': 1,
        'overbought': -2,
        'unknown': 0,
    }
    macd_scores = {
        'bullish_cross': 2,
        'above_signal': 1,
        'below_signal': -1,
        'bearish_cross': -2,
    }

    score = rsi_scores.get(rsi_zone, 0) + macd_scores.get(macd_cross_type, 0)

    if score >= 3:
        return {'signal': 'Strong Buy', 'color': 'strong_buy', 'score': score}
    elif score >= 1:
        return {'signal': 'Buy', 'color': 'buy', 'score': score}
    elif score >= -1:
        return {'signal': 'Neutral', 'color': 'neutral', 'score': score}
    elif score >= -2:
        return {'signal': 'Sell', 'color': 'sell', 'score': score}
    else:
        return {'signal': 'Strong Sell', 'color': 'strong_sell', 'score': score}


# ─── Single Ticker Analysis ──────────────────────────────────────────
def analyze_single_ticker(ticker_symbol: str) -> dict:
    """
    Perform simple RSI + MACD analysis on a single ticker.
    Fetches 6 months of daily data, calculates RSI(14), MACD(12,26,9).

    Returns:
        dict with all analysis results
    """
    try:
        ticker = yf.Ticker(ticker_symbol)

        # Fetch company info
        company_name = ticker_symbol
        sector = 'N/A'
        market_cap = None
        currency = 'IDR'
        price = None

        try:
            info = ticker.info or {}
            company_name = info.get('longName', info.get('shortName', ticker_symbol))
            sector = info.get('sector', 'N/A')
            market_cap = info.get('marketCap')
            currency = info.get('currency', 'IDR')
            price = info.get('currentPrice', info.get('regularMarketPrice'))
        except Exception:
            pass

        # Fetch historical data (6 months for EMA-26 warmup)
        hist = ticker.history(period='6mo')

        if hist is None or hist.empty or len(hist) < 30:
            return {
                'ticker': ticker_symbol,
                'company_name': company_name,
                'status': 'error',
                'error': 'Data historis tidak cukup (< 30 hari)',
            }

        closes = hist['Close']

        # ── RSI ──
        rsi_series = calculate_rsi(closes, period=14)
        rsi_current = float(rsi_series.iloc[-1]) if not rsi_series.empty else None
        rsi_prev = float(rsi_series.iloc[-2]) if len(rsi_series) >= 2 else None
        rsi_info = classify_rsi(rsi_current, rsi_prev)

        # ── MACD ──
        macd_data = calculate_macd(closes)
        macd_current = float(macd_data['macd_line'].iloc[-1])
        signal_current = float(macd_data['signal_line'].iloc[-1])
        histogram_current = float(macd_data['histogram'].iloc[-1])
        macd_cross = detect_macd_crossover(
            macd_data['macd_line'],
            macd_data['signal_line'],
            lookback=3,
        )

        # ── Composite Signal ──
        composite = compute_composite_signal(rsi_info['zone'], macd_cross['type'])

        # ── Price change ──
        price_change_pct = None
        if len(closes) >= 2:
            prev_close = float(closes.iloc[-2])
            curr_close = float(closes.iloc[-1])
            if prev_close > 0:
                price_change_pct = round(((curr_close - prev_close) / prev_close) * 100, 2)

        # Use latest close if price is unavailable
        if price is None and not closes.empty:
            price = float(closes.iloc[-1])

        return {
            'ticker': ticker_symbol,
            'company_name': company_name,
            'sector': sector,
            'currency': currency,
            'price': round(price, 2) if price else None,
            'price_change_pct': price_change_pct,
            'market_cap': market_cap,
            # RSI
            'rsi': round(rsi_current, 2) if rsi_current and not np.isnan(rsi_current) else None,
            'rsi_zone': rsi_info['zone'],
            'rsi_label': rsi_info['label'],
            'rsi_color': rsi_info['color'],
            # MACD
            'macd_line': round(macd_current, 4) if not np.isnan(macd_current) else None,
            'signal_line': round(signal_current, 4) if not np.isnan(signal_current) else None,
            'histogram': round(histogram_current, 4) if not np.isnan(histogram_current) else None,
            'macd_cross_type': macd_cross['type'],
            'macd_cross_label': macd_cross['label'],
            'macd_cross_color': macd_cross['color'],
            'macd_cross_bars_ago': macd_cross['bars_ago'],
            # Composite
            'composite_signal': composite['signal'],
            'composite_color': composite['color'],
            'composite_score': composite['score'],
            # Status
            'status': 'success',
        }

    except Exception as e:
        return {
            'ticker': ticker_symbol,
            'company_name': ticker_symbol,
            'status': 'error',
            'error': str(e),
        }


# ─── Market Cap Presets (IDR) ─────────────────────────────────────────
MARKET_CAP_PRESETS = {
    'all':       {'label': 'Semua',       'min': None,   'max': None},
    'micro':     {'label': 'Micro Cap',   'min': None,   'max': 1e12},
    'small':     {'label': 'Small Cap',   'min': 1e12,   'max': 10e12},
    'mid':       {'label': 'Mid Cap',     'min': 10e12,  'max': 50e12},
    'large':     {'label': 'Large Cap',   'min': 50e12,  'max': 200e12},
    'mega':      {'label': 'Mega Cap',    'min': 200e12, 'max': None},
}


# ─── Main Screener Function ──────────────────────────────────────────
def run_simple_screen(list_key: str,
                      custom_tickers: list = None,
                      min_market_cap: float = None,
                      max_market_cap: float = None) -> dict:
    """
    Run simple RSI + MACD screening on a list of stocks.

    Args:
        list_key: Key from STOCK_LISTS or 'custom'
        custom_tickers: Custom ticker symbols (if list_key is 'custom')
        min_market_cap: Minimum market cap filter (None = no minimum)
        max_market_cap: Maximum market cap filter (None = no maximum)

    Returns:
        dict with screening results
    """
    # Resolve ticker list
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
        return {'success': False, 'error': f'Unknown stock list: {list_key}'}

    if not tickers:
        return {'success': False, 'error': 'Tidak ada ticker yang diberikan.'}

    # Parallel scanning
    results = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            executor.submit(analyze_single_ticker, t): t
            for t in tickers
        }
        for future in as_completed(futures):
            result = future.result()
            results.append(result)

    # Apply market cap filter
    if min_market_cap is not None or max_market_cap is not None:
        filtered = []
        for r in results:
            mcap = r.get('market_cap')
            if mcap is None:
                filtered.append(r)
                continue
            if min_market_cap is not None and mcap < min_market_cap:
                continue
            if max_market_cap is not None and mcap > max_market_cap:
                continue
            filtered.append(r)
        results = filtered

    # Sort by composite score (best signals first)
    results.sort(key=lambda x: (
        x['status'] != 'success',
        -x.get('composite_score', -99),
    ))

    # Count stats
    successful = [r for r in results if r['status'] == 'success']
    errors = [r for r in results if r['status'] == 'error']

    signal_counts = {
        'strong_buy': 0, 'buy': 0, 'neutral': 0, 'sell': 0, 'strong_sell': 0,
    }
    for r in successful:
        sig = r.get('composite_color', 'neutral')
        if sig in signal_counts:
            signal_counts[sig] += 1

    return {
        'success': True,
        'list_name': list_name,
        'list_description': list_description,
        'total_scanned': len(results),
        'success_count': len(successful),
        'error_count': len(errors),
        'signal_counts': signal_counts,
        'market_cap_presets': {
            k: v['label'] for k, v in MARKET_CAP_PRESETS.items()
        },
        'results': results,
    }
