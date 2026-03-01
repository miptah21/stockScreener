"""
Technical Analysis Stock Screener
Scans stocks for RSI(14) zones, MACD(12,26,9) crossover signals,
with market cap filtering support.
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


# ─── EMA Calculation ─────────────────────────────────────────────────
def calculate_ema(closes: pd.Series, period: int) -> pd.Series:
    """Calculate Exponential Moving Average."""
    return closes.ewm(span=period, adjust=False).mean()


def analyze_trend(closes: pd.Series, ema50: pd.Series, ema200: pd.Series) -> dict:
    """
    Classify trend based on price vs EMA50 vs EMA200 alignment.

    Returns:
        dict with trend state, label, and color
    """
    price = closes.iloc[-1]
    e50 = ema50.iloc[-1]
    e200 = ema200.iloc[-1]

    if np.isnan(e50) or np.isnan(e200):
        return {'trend': 'unknown', 'label': 'N/A', 'color': 'neutral'}

    if price > e50 > e200:
        return {'trend': 'strong_uptrend', 'label': 'Strong Uptrend', 'color': 'strong_buy'}
    elif price > e50 and e50 <= e200:
        return {'trend': 'uptrend', 'label': 'Uptrend', 'color': 'buy'}
    elif price > e200:
        return {'trend': 'sideways', 'label': 'Sideways', 'color': 'neutral'}
    elif price < e50 < e200:
        return {'trend': 'strong_downtrend', 'label': 'Strong Downtrend', 'color': 'strong_sell'}
    elif price < e50:
        return {'trend': 'downtrend', 'label': 'Downtrend', 'color': 'sell'}
    else:
        return {'trend': 'sideways', 'label': 'Sideways', 'color': 'neutral'}


# ─── Volume Analysis ─────────────────────────────────────────────────
def analyze_volume(volumes: pd.Series, period: int = 20) -> dict:
    """
    Analyze current volume vs average volume.

    Returns:
        dict with volume_ratio, spike flag, and signal
    """
    if volumes is None or volumes.empty or len(volumes) < period:
        return {
            'volume_ratio': None, 'volume_spike': False,
            'volume_signal': 'unknown', 'label': 'N/A', 'color': 'neutral',
        }

    avg_volume = volumes.iloc[-period:].mean()
    current_volume = volumes.iloc[-1]

    if avg_volume <= 0:
        return {
            'volume_ratio': None, 'volume_spike': False,
            'volume_signal': 'unknown', 'label': 'N/A', 'color': 'neutral',
        }

    ratio = float(current_volume / avg_volume)
    spike = ratio >= 1.5

    if ratio >= 1.5:
        signal = 'bullish'
        label = f'Spike ({ratio:.1f}×)'
        color = 'buy'
    elif ratio >= 1.0:
        signal = 'above_avg'
        label = f'Above Avg ({ratio:.1f}×)'
        color = 'bullish'
    elif ratio >= 0.7:
        signal = 'normal'
        label = f'Normal ({ratio:.1f}×)'
        color = 'neutral'
    else:
        signal = 'low'
        label = f'Low ({ratio:.1f}×)'
        color = 'bearish'

    return {
        'volume_ratio': round(ratio, 2),
        'volume_spike': spike,
        'volume_signal': signal,
        'label': label,
        'color': color,
    }


# ─── ATR Calculation ─────────────────────────────────────────────────
def calculate_atr(high: pd.Series, low: pd.Series,
                  close: pd.Series, period: int = 14) -> dict:
    """
    Calculate Average True Range and ATR%.

    Returns:
        dict with atr value, atr_pct, and volatility signal
    """
    if len(close) < period + 1:
        return {
            'atr': None, 'atr_pct': None,
            'atr_signal': 'unknown', 'label': 'N/A', 'color': 'neutral',
        }

    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr = true_range.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    atr_val = float(atr.iloc[-1])
    price = float(close.iloc[-1])

    if price <= 0 or np.isnan(atr_val):
        return {
            'atr': None, 'atr_pct': None,
            'atr_signal': 'unknown', 'label': 'N/A', 'color': 'neutral',
        }

    atr_pct = (atr_val / price) * 100

    if atr_pct > 5:
        signal = 'extreme'
        label = f'Extreme ({atr_pct:.1f}%)'
        color = 'sell'
    elif atr_pct >= 1:
        signal = 'healthy'
        label = f'Healthy ({atr_pct:.1f}%)'
        color = 'buy'
    else:
        signal = 'low'
        label = f'Low ({atr_pct:.1f}%)'
        color = 'neutral'

    return {
        'atr': round(atr_val, 2),
        'atr_pct': round(atr_pct, 2),
        'atr_signal': signal,
        'label': label,
        'color': color,
    }


# ─── Bollinger Bands ─────────────────────────────────────────────────
def calculate_bollinger(closes: pd.Series, period: int = 20,
                        std_dev: float = 2.0) -> dict:
    """
    Calculate Bollinger Bands, %B, and bandwidth.

    Returns:
        dict with upper, lower, middle bands, pct_b, bandwidth, and signal
    """
    if len(closes) < period:
        return {
            'bb_upper': None, 'bb_lower': None, 'bb_middle': None,
            'bb_pct_b': None, 'bb_bandwidth': None,
            'bb_signal': 'unknown', 'label': 'N/A', 'color': 'neutral',
        }

    middle = closes.rolling(window=period).mean()
    std = closes.rolling(window=period).std()
    upper = middle + (std * std_dev)
    lower = middle - (std * std_dev)

    mid_val = float(middle.iloc[-1])
    up_val = float(upper.iloc[-1])
    lo_val = float(lower.iloc[-1])
    price = float(closes.iloc[-1])

    if np.isnan(mid_val) or (up_val - lo_val) == 0:
        return {
            'bb_upper': None, 'bb_lower': None, 'bb_middle': None,
            'bb_pct_b': None, 'bb_bandwidth': None,
            'bb_signal': 'unknown', 'label': 'N/A', 'color': 'neutral',
        }

    pct_b = (price - lo_val) / (up_val - lo_val)
    bandwidth = (up_val - lo_val) / mid_val

    if pct_b > 1.0:
        signal = 'overbought'
        label = 'Overbought'
        color = 'sell'
    elif pct_b < 0.0:
        signal = 'oversold'
        label = 'Oversold'
        color = 'buy'
    elif pct_b < 0.2:
        signal = 'near_lower'
        label = 'Near Lower'
        color = 'buy_mild'
    elif pct_b > 0.8:
        signal = 'near_upper'
        label = 'Near Upper'
        color = 'bearish'
    else:
        signal = 'neutral'
        label = 'Neutral'
        color = 'neutral'

    return {
        'bb_upper': round(up_val, 2),
        'bb_lower': round(lo_val, 2),
        'bb_middle': round(mid_val, 2),
        'bb_pct_b': round(pct_b, 4),
        'bb_bandwidth': round(bandwidth, 4),
        'bb_signal': signal,
        'label': label,
        'color': color,
    }


# ─── ADX (Average Directional Index) ────────────────────────────────
def calculate_adx(high: pd.Series, low: pd.Series,
                  close: pd.Series, period: int = 14) -> dict:
    """
    Calculate ADX, DI+, and DI- for trend strength measurement.

    Returns:
        dict with adx, di_plus, di_minus, and trend strength signal
    """
    if len(close) < period * 2:
        return {
            'adx': None, 'di_plus': None, 'di_minus': None,
            'adx_signal': 'unknown', 'label': 'N/A', 'color': 'neutral',
        }

    # +DM / -DM
    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0),
                        index=close.index)
    minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0),
                         index=close.index)

    # True Range
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # Smoothed values (Wilder's smoothing)
    atr = true_range.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    smooth_plus_dm = plus_dm.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    smooth_minus_dm = minus_dm.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    # DI+ and DI-
    di_plus = 100 * (smooth_plus_dm / atr)
    di_minus = 100 * (smooth_minus_dm / atr)

    # DX and ADX
    di_sum = di_plus + di_minus
    di_sum = di_sum.replace(0, np.nan)
    dx = 100 * ((di_plus - di_minus).abs() / di_sum)
    adx = dx.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    adx_val = float(adx.iloc[-1])
    di_p = float(di_plus.iloc[-1])
    di_m = float(di_minus.iloc[-1])

    if np.isnan(adx_val):
        return {
            'adx': None, 'di_plus': None, 'di_minus': None,
            'adx_signal': 'unknown', 'label': 'N/A', 'color': 'neutral',
        }

    if adx_val >= 25:
        signal = 'trending'
        label = f'Trending ({adx_val:.0f})'
        color = 'buy' if di_p > di_m else 'sell'
    elif adx_val >= 20:
        signal = 'weak'
        label = f'Weak ({adx_val:.0f})'
        color = 'neutral'
    else:
        signal = 'no_trend'
        label = f'No Trend ({adx_val:.0f})'
        color = 'bearish'

    return {
        'adx': round(adx_val, 2),
        'di_plus': round(di_p, 2),
        'di_minus': round(di_m, 2),
        'adx_signal': signal,
        'label': label,
        'color': color,
    }


# ─── RSI Divergence Detection ────────────────────────────────────────
def detect_divergence(closes: pd.Series, rsi_series: pd.Series,
                      lookback: int = 14) -> dict:
    """
    Detect bullish/bearish divergence between price and RSI.
    Bullish: price makes lower low, RSI makes higher low.
    Bearish: price makes higher high, RSI makes lower high.

    Returns:
        dict with divergence type label and color
    """
    if len(closes) < lookback + 5 or len(rsi_series) < lookback + 5:
        return {'divergence': 'none', 'label': 'None', 'color': 'neutral'}

    # Get the recent segment
    price_seg = closes.iloc[-(lookback + 5):].values
    rsi_seg = rsi_series.iloc[-(lookback + 5):].values

    # Remove NaN
    valid = ~(np.isnan(price_seg) | np.isnan(rsi_seg))
    if valid.sum() < lookback:
        return {'divergence': 'none', 'label': 'None', 'color': 'neutral'}

    price_seg = price_seg[valid]
    rsi_seg = rsi_seg[valid]

    # Split into two halves for comparison
    mid = len(price_seg) // 2

    first_price_low = price_seg[:mid].min()
    second_price_low = price_seg[mid:].min()
    first_rsi_low = rsi_seg[:mid].min()
    second_rsi_low = rsi_seg[mid:].min()

    first_price_high = price_seg[:mid].max()
    second_price_high = price_seg[mid:].max()
    first_rsi_high = rsi_seg[:mid].max()
    second_rsi_high = rsi_seg[mid:].max()

    # Bullish divergence: price lower low + RSI higher low
    if second_price_low < first_price_low and second_rsi_low > first_rsi_low:
        return {'divergence': 'bullish', 'label': 'Bullish Div', 'color': 'buy'}

    # Bearish divergence: price higher high + RSI lower high
    if second_price_high > first_price_high and second_rsi_high < first_rsi_high:
        return {'divergence': 'bearish', 'label': 'Bearish Div', 'color': 'sell'}

    return {'divergence': 'none', 'label': 'None', 'color': 'neutral'}


# ─── Confluence Score (0-100 Multi-Indicator) ────────────────────────
def compute_confluence_score(rsi_zone: str, macd_cross_type: str,
                             volume_signal: str, trend: str,
                             atr_signal: str, bb_signal: str,
                             adx_signal: str, divergence: str) -> dict:
    """
    Compute confluence score (0-100) from all indicators.

    Components:
        RSI          : max 20 points
        MACD         : max 20 points
        Volume       : max 20 points
        Trend (EMA)  : max 20 points
        ATR          : max 10 points
        Bonus (BB/ADX/Div) : max 10 points

    Score thresholds:
        80-100 → Strong Buy
        60-79  → Buy
        40-59  → Neutral
        20-39  → Sell
        0-19   → Strong Sell
    """
    # RSI component (max 20)
    rsi_scores = {
        'oversold': 20, 'emerging_bullish': 15,
        'neutral_low': 10, 'neutral': 10,
        'bullish': 15, 'overbought': 0, 'unknown': 10,
    }
    rsi_pts = rsi_scores.get(rsi_zone, 10)

    # MACD component (max 20)
    macd_scores = {
        'bullish_cross': 20, 'above_signal': 15,
        'below_signal': 5, 'bearish_cross': 0,
    }
    macd_pts = macd_scores.get(macd_cross_type, 10)

    # Volume component (max 20)
    vol_scores = {
        'bullish': 20, 'above_avg': 15,
        'normal': 10, 'low': 5, 'unknown': 10,
    }
    vol_pts = vol_scores.get(volume_signal, 10)

    # Trend component (max 20)
    trend_scores = {
        'strong_uptrend': 20, 'uptrend': 15,
        'sideways': 10, 'downtrend': 5,
        'strong_downtrend': 0, 'unknown': 10,
    }
    trend_pts = trend_scores.get(trend, 10)

    # ATR component (max 10)
    atr_scores = {'healthy': 10, 'low': 3, 'extreme': 5, 'unknown': 5}
    atr_pts = atr_scores.get(atr_signal, 5)

    # Bonus component — best of BB/ADX/Divergence (max 10)
    bonus_candidates = []
    # BB bonus
    if bb_signal in ('oversold', 'near_lower'):
        bonus_candidates.append(10 if bb_signal == 'oversold' else 8)
    elif bb_signal in ('overbought', 'near_upper'):
        bonus_candidates.append(0)
    else:
        bonus_candidates.append(5)

    # ADX bonus
    if adx_signal == 'trending':
        bonus_candidates.append(5)
    else:
        bonus_candidates.append(2)

    # Divergence bonus
    if divergence == 'bullish':
        bonus_candidates.append(10)
    elif divergence == 'bearish':
        bonus_candidates.append(0)
    else:
        bonus_candidates.append(3)

    bonus_pts = max(bonus_candidates) if bonus_candidates else 0

    score = rsi_pts + macd_pts + vol_pts + trend_pts + atr_pts + bonus_pts

    # Clamp
    score = max(0, min(100, score))

    # Classify
    if score >= 80:
        signal = 'Strong Buy'
        color = 'strong_buy'
    elif score >= 60:
        signal = 'Buy'
        color = 'buy'
    elif score >= 40:
        signal = 'Neutral'
        color = 'neutral'
    elif score >= 20:
        signal = 'Sell'
        color = 'sell'
    else:
        signal = 'Strong Sell'
        color = 'strong_sell'

    # Count bullish indicators (out of 6 main)
    bullish_count = 0
    if rsi_zone in ('oversold', 'emerging_bullish', 'bullish'):
        bullish_count += 1
    if macd_cross_type in ('bullish_cross', 'above_signal'):
        bullish_count += 1
    if volume_signal in ('bullish', 'above_avg'):
        bullish_count += 1
    if trend in ('strong_uptrend', 'uptrend'):
        bullish_count += 1
    if atr_signal == 'healthy':
        bullish_count += 1
    if bb_signal in ('oversold', 'near_lower') or divergence == 'bullish' or adx_signal == 'trending':
        bullish_count += 1

    return {
        'signal': signal,
        'color': color,
        'score': score,
        'confidence_count': f'{bullish_count}/6',
        'score_breakdown': {
            'rsi': rsi_pts,
            'macd': macd_pts,
            'volume': vol_pts,
            'trend': trend_pts,
            'atr': atr_pts,
            'bonus': bonus_pts,
        },
    }


# ─── Single Ticker Analysis ──────────────────────────────────────────
def analyze_single_ticker(ticker_symbol: str) -> dict:
    """
    Perform full technical analysis on a single ticker.
    Fetches 1 year of daily data, calculates 7 indicators:
    RSI(14), MACD(12,26,9), Volume(20), EMA 50/200, ATR(14),
    Bollinger Bands(20,2), ADX(14), RSI Divergence.

    Returns:
        dict with all analysis results and confluence score (0-100)
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

        # Fetch historical data (1 year for EMA-200 warmup)
        hist = ticker.history(period='1y')

        if hist is None or hist.empty or len(hist) < 30:
            return {
                'ticker': ticker_symbol,
                'company_name': company_name,
                'status': 'error',
                'error': 'Data historis tidak cukup (< 30 hari)',
            }

        closes = hist['Close']
        highs = hist['High']
        lows = hist['Low']
        volumes = hist['Volume']

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

        # ── EMA Trend ──
        ema50 = calculate_ema(closes, 50)
        ema200 = calculate_ema(closes, 200)
        trend_info = analyze_trend(closes, ema50, ema200)

        # ── Volume ──
        vol_info = analyze_volume(volumes, period=20)

        # ── ATR ──
        atr_info = calculate_atr(highs, lows, closes, period=14)

        # ── Bollinger Bands ──
        bb_info = calculate_bollinger(closes, period=20, std_dev=2.0)

        # ── ADX ──
        adx_info = calculate_adx(highs, lows, closes, period=14)

        # ── RSI Divergence ──
        div_info = detect_divergence(closes, rsi_series, lookback=14)

        # ── Confluence Score (0-100) ──
        confluence = compute_confluence_score(
            rsi_zone=rsi_info['zone'],
            macd_cross_type=macd_cross['type'],
            volume_signal=vol_info['volume_signal'],
            trend=trend_info['trend'],
            atr_signal=atr_info['atr_signal'],
            bb_signal=bb_info['bb_signal'],
            adx_signal=adx_info['adx_signal'],
            divergence=div_info['divergence'],
        )

        # ── Stop Loss (Price - 2×ATR) ──
        stop_loss = None
        if atr_info['atr'] is not None and price is not None:
            stop_loss = round(price - 2 * atr_info['atr'], 2)
        elif atr_info['atr'] is not None and not closes.empty:
            stop_loss = round(float(closes.iloc[-1]) - 2 * atr_info['atr'], 2)

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
            # EMA Trend
            'ema50': round(float(ema50.iloc[-1]), 2) if not np.isnan(ema50.iloc[-1]) else None,
            'ema200': round(float(ema200.iloc[-1]), 2) if not np.isnan(ema200.iloc[-1]) else None,
            'trend': trend_info['trend'],
            'trend_label': trend_info['label'],
            'trend_color': trend_info['color'],
            # Volume
            'volume_ratio': vol_info['volume_ratio'],
            'volume_spike': vol_info['volume_spike'],
            'volume_signal': vol_info['volume_signal'],
            'volume_label': vol_info['label'],
            'volume_color': vol_info['color'],
            # ATR
            'atr': atr_info['atr'],
            'atr_pct': atr_info['atr_pct'],
            'atr_signal': atr_info['atr_signal'],
            'atr_label': atr_info['label'],
            'atr_color': atr_info['color'],
            # Bollinger Bands
            'bb_upper': bb_info['bb_upper'],
            'bb_lower': bb_info['bb_lower'],
            'bb_middle': bb_info['bb_middle'],
            'bb_pct_b': bb_info['bb_pct_b'],
            'bb_bandwidth': bb_info['bb_bandwidth'],
            'bb_signal': bb_info['bb_signal'],
            'bb_label': bb_info['label'],
            'bb_color': bb_info['color'],
            # ADX
            'adx': adx_info['adx'],
            'di_plus': adx_info['di_plus'],
            'di_minus': adx_info['di_minus'],
            'adx_signal': adx_info['adx_signal'],
            'adx_label': adx_info['label'],
            'adx_color': adx_info['color'],
            # Divergence
            'divergence': div_info['divergence'],
            'divergence_label': div_info['label'],
            'divergence_color': div_info['color'],
            # Risk Management
            'stop_loss': stop_loss,
            # Confluence Score
            'confluence_score': confluence['score'],
            'confidence_count': confluence['confidence_count'],
            'score_breakdown': confluence['score_breakdown'],
            # Backward compat
            'composite_signal': confluence['signal'],
            'composite_color': confluence['color'],
            'composite_score': confluence['score'],
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


# ─── Batch Download & Analyze ─────────────────────────────────────────
def _fetch_info_safe(ticker_symbol: str) -> dict:
    """Fetch ticker.info safely, return minimal dict on failure."""
    try:
        info = yf.Ticker(ticker_symbol).info or {}
        return {
            'company_name': info.get('longName', info.get('shortName', ticker_symbol)),
            'sector': info.get('sector', 'N/A'),
            'market_cap': info.get('marketCap'),
            'currency': info.get('currency', 'IDR'),
            'price': info.get('currentPrice', info.get('regularMarketPrice')),
        }
    except Exception:
        return {
            'company_name': ticker_symbol,
            'sector': 'N/A',
            'market_cap': None,
            'currency': 'IDR',
            'price': None,
        }


def _analyze_from_dataframe(ticker_symbol: str, hist: pd.DataFrame,
                            info: dict) -> dict:
    """
    Compute all 7 technical indicators from a pre-downloaded DataFrame.
    Same output schema as analyze_single_ticker().
    """
    try:
        if hist is None or hist.empty or len(hist) < 30:
            return {
                'ticker': ticker_symbol,
                'company_name': info.get('company_name', ticker_symbol),
                'status': 'error',
                'error': 'Data historis tidak cukup (< 30 hari)',
            }

        closes = hist['Close']
        highs = hist['High']
        lows = hist['Low']
        volumes = hist['Volume']

        company_name = info.get('company_name', ticker_symbol)
        sector = info.get('sector', 'N/A')
        market_cap = info.get('market_cap')
        currency = info.get('currency', 'IDR')
        price = info.get('price')

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
            macd_data['macd_line'], macd_data['signal_line'], lookback=3,
        )

        # ── EMA Trend ──
        ema50 = calculate_ema(closes, 50)
        ema200 = calculate_ema(closes, 200)
        trend_info = analyze_trend(closes, ema50, ema200)

        # ── Volume ──
        vol_info = analyze_volume(volumes, period=20)

        # ── ATR ──
        atr_info = calculate_atr(highs, lows, closes, period=14)

        # ── Bollinger Bands ──
        bb_info = calculate_bollinger(closes, period=20, std_dev=2.0)

        # ── ADX ──
        adx_info = calculate_adx(highs, lows, closes, period=14)

        # ── RSI Divergence ──
        div_info = detect_divergence(closes, rsi_series, lookback=14)

        # ── Confluence Score ──
        confluence = compute_confluence_score(
            rsi_zone=rsi_info['zone'],
            macd_cross_type=macd_cross['type'],
            volume_signal=vol_info['volume_signal'],
            trend=trend_info['trend'],
            atr_signal=atr_info['atr_signal'],
            bb_signal=bb_info['bb_signal'],
            adx_signal=adx_info['adx_signal'],
            divergence=div_info['divergence'],
        )

        # ── Stop Loss ──
        stop_loss = None
        if atr_info['atr'] is not None and price is not None:
            stop_loss = round(price - 2 * atr_info['atr'], 2)
        elif atr_info['atr'] is not None and not closes.empty:
            stop_loss = round(float(closes.iloc[-1]) - 2 * atr_info['atr'], 2)

        # ── Price change ──
        price_change_pct = None
        if len(closes) >= 2:
            prev_close = float(closes.iloc[-2])
            curr_close = float(closes.iloc[-1])
            if prev_close > 0:
                price_change_pct = round(
                    ((curr_close - prev_close) / prev_close) * 100, 2)

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
            'rsi': round(rsi_current, 2) if rsi_current and not np.isnan(rsi_current) else None,
            'rsi_zone': rsi_info['zone'],
            'rsi_label': rsi_info['label'],
            'rsi_color': rsi_info['color'],
            'macd_line': round(macd_current, 4) if not np.isnan(macd_current) else None,
            'signal_line': round(signal_current, 4) if not np.isnan(signal_current) else None,
            'histogram': round(histogram_current, 4) if not np.isnan(histogram_current) else None,
            'macd_cross_type': macd_cross['type'],
            'macd_cross_label': macd_cross['label'],
            'macd_cross_color': macd_cross['color'],
            'macd_cross_bars_ago': macd_cross['bars_ago'],
            'ema50': round(float(ema50.iloc[-1]), 2) if not np.isnan(ema50.iloc[-1]) else None,
            'ema200': round(float(ema200.iloc[-1]), 2) if not np.isnan(ema200.iloc[-1]) else None,
            'trend': trend_info['trend'],
            'trend_label': trend_info['label'],
            'trend_color': trend_info['color'],
            'volume_ratio': vol_info['volume_ratio'],
            'volume_spike': vol_info['volume_spike'],
            'volume_signal': vol_info['volume_signal'],
            'volume_label': vol_info['label'],
            'volume_color': vol_info['color'],
            'atr': atr_info['atr'],
            'atr_pct': atr_info['atr_pct'],
            'atr_signal': atr_info['atr_signal'],
            'atr_label': atr_info['label'],
            'atr_color': atr_info['color'],
            'bb_upper': bb_info['bb_upper'],
            'bb_lower': bb_info['bb_lower'],
            'bb_middle': bb_info['bb_middle'],
            'bb_pct_b': bb_info['bb_pct_b'],
            'bb_bandwidth': bb_info['bb_bandwidth'],
            'bb_signal': bb_info['bb_signal'],
            'bb_label': bb_info['label'],
            'bb_color': bb_info['color'],
            'adx': adx_info['adx'],
            'di_plus': adx_info['di_plus'],
            'di_minus': adx_info['di_minus'],
            'adx_signal': adx_info['adx_signal'],
            'adx_label': adx_info['label'],
            'adx_color': adx_info['color'],
            'divergence': div_info['divergence'],
            'divergence_label': div_info['label'],
            'divergence_color': div_info['color'],
            'stop_loss': stop_loss,
            'confluence_score': confluence['score'],
            'confidence_count': confluence['confidence_count'],
            'score_breakdown': confluence['score_breakdown'],
            'composite_signal': confluence['signal'],
            'composite_color': confluence['color'],
            'composite_score': confluence['score'],
            'status': 'success',
        }
    except Exception as e:
        return {
            'ticker': ticker_symbol,
            'company_name': info.get('company_name', ticker_symbol),
            'status': 'error',
            'error': str(e),
        }


def batch_download_and_analyze(tickers: list, period: str = '1y') -> list:
    """
    Batch-download OHLCV for multiple tickers via yf.download(),
    then compute indicators + fetch info in parallel.
    Much faster than per-ticker yf.Ticker().history().
    """
    results = []
    if not tickers:
        return results

    # Step 1: Batch download all OHLCV data in one network call
    try:
        if len(tickers) == 1:
            raw = yf.download(tickers, period=period, progress=False,
                              threads=True, auto_adjust=True)
            # Single ticker → simple DataFrame (no MultiIndex columns)
            batch_data = {tickers[0]: raw}
        else:
            raw = yf.download(tickers, period=period, group_by='ticker',
                              progress=False, threads=True, auto_adjust=True)
            batch_data = {}
            for t in tickers:
                try:
                    df = raw[t].dropna(how='all')
                    batch_data[t] = df
                except (KeyError, Exception):
                    batch_data[t] = pd.DataFrame()
    except Exception as e:
        logger.error("Batch download failed: %s — falling back to per-ticker", e)
        # Fallback: use original per-ticker method
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {executor.submit(analyze_single_ticker, t): t
                       for t in tickers}
            for future in as_completed(futures):
                results.append(future.result())
        return results

    # Step 2: Fetch ticker.info in parallel (for company name, market cap, etc.)
    info_map = {}
    with ThreadPoolExecutor(max_workers=10) as executor:
        info_futures = {executor.submit(_fetch_info_safe, t): t
                        for t in tickers}
        for future in as_completed(info_futures):
            t = info_futures[future]
            info_map[t] = future.result()

    # Step 3: Compute indicators from pre-downloaded data
    for t in tickers:
        hist = batch_data.get(t, pd.DataFrame())
        info = info_map.get(t, {'company_name': t})
        result = _analyze_from_dataframe(t, hist, info)
        results.append(result)

    return results


# ─── Main Screener Function ──────────────────────────────────────────
def run_technical_screen(list_key: str,
                         custom_tickers: list = None,
                         min_market_cap: float = None,
                         max_market_cap: float = None,
                         offset: int = None,
                         limit: int = None) -> dict:
    """
    Run technical analysis screening on a list of stocks.

    Args:
        list_key: Key from STOCK_LISTS or 'custom'
        custom_tickers: Custom ticker symbols (if list_key is 'custom')
        min_market_cap: Minimum market cap filter (None = no minimum)
        max_market_cap: Maximum market cap filter (None = no maximum)
        offset: Starting index for chunked requests (None = all)
        limit: Number of tickers per chunk (None = all)

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

    total_tickers = len(tickers)

    # Chunked mode: slice the ticker list
    is_chunked = offset is not None and limit is not None
    if is_chunked:
        batch_tickers = tickers[offset:offset + limit]
        has_more = (offset + limit) < total_tickers
    else:
        batch_tickers = tickers
        has_more = False

    if not batch_tickers:
        return {
            'success': True,
            'list_name': list_name,
            'list_description': list_description,
            'total_scanned': 0,
            'total_tickers': total_tickers,
            'offset': offset or 0,
            'limit': limit or total_tickers,
            'has_more': False,
            'success_count': 0,
            'error_count': 0,
            'signal_counts': {
                'strong_buy': 0, 'buy': 0, 'neutral': 0,
                'sell': 0, 'strong_sell': 0,
            },
            'avg_score': 0,
            'market_cap_presets': {
                k: v['label'] for k, v in MARKET_CAP_PRESETS.items()
            },
            'results': [],
        }

    # Use batch download for speed
    results = batch_download_and_analyze(batch_tickers, period='1y')

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

    # Sort by confluence score (best signals first)
    results.sort(key=lambda x: (
        x['status'] != 'success',
        -x.get('confluence_score', x.get('composite_score', -99)),
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

    # Average score
    scores = [r.get('confluence_score', 0) for r in successful
              if r.get('confluence_score') is not None]
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0

    return {
        'success': True,
        'list_name': list_name,
        'list_description': list_description,
        'total_scanned': len(results),
        'total_tickers': total_tickers,
        'offset': offset if offset is not None else 0,
        'limit': limit if limit is not None else total_tickers,
        'has_more': has_more,
        'success_count': len(successful),
        'error_count': len(errors),
        'signal_counts': signal_counts,
        'avg_score': avg_score,
        'market_cap_presets': {
            k: v['label'] for k, v in MARKET_CAP_PRESETS.items()
        },
        'results': results,
    }

