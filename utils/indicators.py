"""
Shared Technical Indicators Module
Canonical implementations of RSI, MACD, and classification functions.
Used by both simple_screener.py and technical_screener.py to eliminate duplication.
"""

import pandas as pd
import numpy as np


# ─── RSI Calculation (Wilder's Smoothing) ────────────────────────────

def calculate_rsi(closes: pd.Series, period: int = 14) -> pd.Series:
    """
    Calculate RSI using Wilder's smoothing method.

    Args:
        closes: Series of closing prices
        period: RSI period (default 14)

    Returns:
        Series of RSI values
    """
    delta = closes.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)

    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def classify_rsi(rsi_value: float, prev_rsi: float = None) -> dict:
    """
    Classify RSI into a zone with label and color.

    Returns:
        dict with zone, label, and color_class
    """
    if rsi_value is None or np.isnan(rsi_value):
        return {'zone': 'unknown', 'label': 'N/A', 'color': 'neutral'}

    if rsi_value >= 70:
        return {'zone': 'overbought', 'label': 'Overbought', 'color': 'sell'}
    elif rsi_value <= 30:
        return {'zone': 'oversold', 'label': 'Oversold', 'color': 'buy'}
    elif rsi_value <= 40:
        if prev_rsi is not None and prev_rsi <= 30:
            return {'zone': 'emerging_bullish', 'label': 'Emerging Bullish', 'color': 'buy_mild'}
        return {'zone': 'neutral_low', 'label': 'Neutral Low', 'color': 'neutral'}
    elif rsi_value >= 60:
        return {'zone': 'bullish', 'label': 'Bullish', 'color': 'bullish'}
    else:
        return {'zone': 'neutral', 'label': 'Neutral', 'color': 'neutral'}


# ─── MACD Calculation ────────────────────────────────────────────────

def calculate_macd(closes: pd.Series,
                   fast: int = 12,
                   slow: int = 26,
                   signal_period: int = 9) -> dict:
    """
    Calculate MACD line, Signal line, and Histogram.

    Returns:
        dict with macd_line, signal_line, histogram as Series
    """
    ema_fast = closes.ewm(span=fast, adjust=False).mean()
    ema_slow = closes.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
    histogram = macd_line - signal_line

    return {
        'macd_line': macd_line,
        'signal_line': signal_line,
        'histogram': histogram,
    }


def detect_macd_crossover(macd_line: pd.Series,
                          signal_line: pd.Series,
                          lookback: int = 3) -> dict:
    """
    Detect MACD crossover within the last `lookback` bars.

    Returns:
        dict with crossover type, label, color, and how many bars ago
    """
    if len(macd_line) < lookback + 1 or len(signal_line) < lookback + 1:
        return {
            'type': 'unknown',
            'label': 'N/A',
            'color': 'neutral',
            'bars_ago': None,
        }

    # Check recent bars for crossover
    for i in range(1, lookback + 1):
        idx = -i
        prev_idx = idx - 1

        if prev_idx < -len(macd_line):
            break

        # Current bar
        macd_now = macd_line.iloc[idx]
        signal_now = signal_line.iloc[idx]
        # Previous bar
        macd_prev = macd_line.iloc[prev_idx]
        signal_prev = signal_line.iloc[prev_idx]

        # Bullish crossover: MACD crossed ABOVE signal
        if macd_prev <= signal_prev and macd_now > signal_now:
            return {
                'type': 'bullish_cross',
                'label': f'Bullish Cross ({i}d ago)' if i > 1 else 'Bullish Cross (Today)',
                'color': 'buy',
                'bars_ago': i - 1,
            }

        # Bearish crossover: MACD crossed BELOW signal
        if macd_prev >= signal_prev and macd_now < signal_now:
            return {
                'type': 'bearish_cross',
                'label': f'Bearish Cross ({i}d ago)' if i > 1 else 'Bearish Cross (Today)',
                'color': 'sell',
                'bars_ago': i - 1,
            }

    # No crossover — check current position
    current_macd = macd_line.iloc[-1]
    current_signal = signal_line.iloc[-1]

    if current_macd > current_signal:
        return {
            'type': 'above_signal',
            'label': 'Di Atas Signal',
            'color': 'bullish',
            'bars_ago': None,
        }
    else:
        return {
            'type': 'below_signal',
            'label': 'Di Bawah Signal',
            'color': 'bearish',
            'bars_ago': None,
        }
