"""
Candlestick Pattern Detection Module
Pure Python/pandas/numpy implementation — no TA-Lib dependency.

Detects 16 candlestick patterns:
  Single-candle: Doji, Hammer, Inverted Hammer, Shooting Star,
                 Spinning Top, Marubozu, Dragonfly Doji, Gravestone Doji
  Multi-candle:  Bullish/Bearish Engulfing, Morning/Evening Star,
                 Three White Soldiers, Three Black Crows,
                 Bullish/Bearish Harami
"""

import numpy as np
import pandas as pd


# ─── Helpers ─────────────────────────────────────────────────────────

def _body(o, c):
    """Absolute body size."""
    return abs(c - o)


def _upper_shadow(o, c, h):
    """Upper shadow length."""
    return h - max(o, c)


def _lower_shadow(o, c, l):
    """Lower shadow length."""
    return min(o, c) - l


def _range(h, l):
    """Full candle range (high - low)."""
    return h - l


def _is_bullish(o, c):
    return c > o


def _is_bearish(o, c):
    return c < o


# ─── Single-Candle Patterns ─────────────────────────────────────────

def detect_doji(o, h, l, c):
    """
    Doji — open ≈ close (body < 10% of range), signals indecision.
    """
    r = _range(h, l)
    if r == 0:
        return None
    body = _body(o, c)
    if body / r < 0.10:
        return {
            'name': 'Doji',
            'name_id': 'Doji',
            'signal': 'neutral',
            'strength': 1,
            'description': 'Candle dengan body sangat kecil, menunjukkan keraguan pasar.',
            'description_en': 'Very small body candle indicating market indecision.',
        }
    return None


def detect_dragonfly_doji(o, h, l, c):
    """
    Dragonfly Doji — Doji with long lower shadow, bullish reversal signal.
    """
    r = _range(h, l)
    if r == 0:
        return None
    body = _body(o, c)
    ls = _lower_shadow(o, c, l)
    us = _upper_shadow(o, c, h)
    if body / r < 0.10 and ls / r > 0.60 and us / r < 0.10:
        return {
            'name': 'Dragonfly Doji',
            'name_id': 'Dragonfly Doji',
            'signal': 'bullish',
            'strength': 2,
            'description': 'Doji dengan shadow bawah panjang, sinyal reversal bullish.',
            'description_en': 'Doji with long lower shadow, bullish reversal signal.',
        }
    return None


def detect_gravestone_doji(o, h, l, c):
    """
    Gravestone Doji — Doji with long upper shadow, bearish reversal signal.
    """
    r = _range(h, l)
    if r == 0:
        return None
    body = _body(o, c)
    ls = _lower_shadow(o, c, l)
    us = _upper_shadow(o, c, h)
    if body / r < 0.10 and us / r > 0.60 and ls / r < 0.10:
        return {
            'name': 'Gravestone Doji',
            'name_id': 'Gravestone Doji',
            'signal': 'bearish',
            'strength': 2,
            'description': 'Doji dengan shadow atas panjang, sinyal reversal bearish.',
            'description_en': 'Doji with long upper shadow, bearish reversal signal.',
        }
    return None


def detect_hammer(o, h, l, c):
    """
    Hammer — small body at top, long lower shadow ≥2× body, bullish reversal.
    """
    r = _range(h, l)
    if r == 0:
        return None
    body = _body(o, c)
    ls = _lower_shadow(o, c, l)
    us = _upper_shadow(o, c, h)
    if body > 0 and ls >= 2 * body and us <= body * 0.5 and body / r <= 0.35:
        return {
            'name': 'Hammer',
            'name_id': 'Hammer',
            'signal': 'bullish',
            'strength': 2,
            'description': 'Body kecil di atas dengan shadow bawah panjang, sinyal reversal bullish.',
            'description_en': 'Small body at top with long lower shadow, bullish reversal.',
        }
    return None


def detect_inverted_hammer(o, h, l, c):
    """
    Inverted Hammer — small body at bottom, long upper shadow ≥2× body.
    """
    r = _range(h, l)
    if r == 0:
        return None
    body = _body(o, c)
    ls = _lower_shadow(o, c, l)
    us = _upper_shadow(o, c, h)
    if body > 0 and us >= 2 * body and ls <= body * 0.5 and body / r <= 0.35:
        return {
            'name': 'Inverted Hammer',
            'name_id': 'Inverted Hammer',
            'signal': 'bullish',
            'strength': 1,
            'description': 'Body kecil di bawah dengan shadow atas panjang, potensi reversal bullish.',
            'description_en': 'Small body at bottom with long upper shadow, potential bullish reversal.',
        }
    return None


def detect_shooting_star(o, h, l, c):
    """
    Shooting Star — small body at bottom, long upper shadow ≥2× body, bearish.
    Requires prior uptrend context (caller responsibility), but we detect the shape.
    """
    r = _range(h, l)
    if r == 0:
        return None
    body = _body(o, c)
    ls = _lower_shadow(o, c, l)
    us = _upper_shadow(o, c, h)
    if body > 0 and us >= 2 * body and ls <= body * 0.5 and _is_bearish(o, c) and body / r <= 0.35:
        return {
            'name': 'Shooting Star',
            'name_id': 'Shooting Star',
            'signal': 'bearish',
            'strength': 2,
            'description': 'Body kecil di bawah dengan shadow atas panjang & bearish close, sinyal reversal bearish.',
            'description_en': 'Small bearish body with long upper shadow, bearish reversal signal.',
        }
    return None


def detect_spinning_top(o, h, l, c):
    """
    Spinning Top — small body centered in range, indecision.
    """
    r = _range(h, l)
    if r == 0:
        return None
    body = _body(o, c)
    ls = _lower_shadow(o, c, l)
    us = _upper_shadow(o, c, h)
    if body / r < 0.30 and ls > body and us > body:
        # Exclude doji (even smaller body)
        if body / r >= 0.05:
            return {
                'name': 'Spinning Top',
                'name_id': 'Spinning Top',
                'signal': 'neutral',
                'strength': 1,
                'description': 'Body kecil dengan shadow atas dan bawah, menunjukkan keraguan pasar.',
                'description_en': 'Small body with upper and lower shadows, market indecision.',
            }
    return None


def detect_marubozu(o, h, l, c):
    """
    Marubozu — full body candle with minimal/no shadows, strong momentum.
    """
    r = _range(h, l)
    if r == 0:
        return None
    body = _body(o, c)
    ls = _lower_shadow(o, c, l)
    us = _upper_shadow(o, c, h)
    if body / r >= 0.80 and us / r < 0.05 and ls / r < 0.05:
        if _is_bullish(o, c):
            return {
                'name': 'Bullish Marubozu',
                'name_id': 'Bullish Marubozu',
                'signal': 'bullish',
                'strength': 3,
                'description': 'Candle full body bullish tanpa shadow, momentum kuat naik.',
                'description_en': 'Full bullish body with no shadows, strong upward momentum.',
            }
        else:
            return {
                'name': 'Bearish Marubozu',
                'name_id': 'Bearish Marubozu',
                'signal': 'bearish',
                'strength': 3,
                'description': 'Candle full body bearish tanpa shadow, momentum kuat turun.',
                'description_en': 'Full bearish body with no shadows, strong downward momentum.',
            }
    return None


# ─── Multi-Candle Patterns ──────────────────────────────────────────

def detect_engulfing(candles):
    """
    Engulfing — 2-candle pattern where 2nd body fully engulfs 1st body.
    candles: list of 2 dicts with o, h, l, c
    """
    if len(candles) < 2:
        return None
    prev, curr = candles[-2], candles[-1]
    prev_body = _body(prev['o'], prev['c'])
    curr_body = _body(curr['o'], curr['c'])

    if prev_body == 0 or curr_body == 0:
        return None

    # Bullish Engulfing: prev bearish, curr bullish, curr body engulfs prev
    if (_is_bearish(prev['o'], prev['c']) and
            _is_bullish(curr['o'], curr['c']) and
            curr['o'] <= prev['c'] and curr['c'] >= prev['o'] and
            curr_body > prev_body):
        return {
            'name': 'Bullish Engulfing',
            'name_id': 'Bullish Engulfing',
            'signal': 'bullish',
            'strength': 3,
            'description': 'Candle bullish besar menelan candle bearish sebelumnya, sinyal reversal kuat.',
            'description_en': 'Large bullish candle engulfs previous bearish candle, strong reversal.',
        }

    # Bearish Engulfing: prev bullish, curr bearish, curr body engulfs prev
    if (_is_bullish(prev['o'], prev['c']) and
            _is_bearish(curr['o'], curr['c']) and
            curr['o'] >= prev['c'] and curr['c'] <= prev['o'] and
            curr_body > prev_body):
        return {
            'name': 'Bearish Engulfing',
            'name_id': 'Bearish Engulfing',
            'signal': 'bearish',
            'strength': 3,
            'description': 'Candle bearish besar menelan candle bullish sebelumnya, sinyal reversal kuat.',
            'description_en': 'Large bearish candle engulfs previous bullish candle, strong reversal.',
        }
    return None


def detect_harami(candles):
    """
    Harami — 2-candle pattern where 2nd body is contained within 1st body.
    """
    if len(candles) < 2:
        return None
    prev, curr = candles[-2], candles[-1]
    prev_body = _body(prev['o'], prev['c'])
    curr_body = _body(curr['o'], curr['c'])

    if prev_body == 0 or curr_body == 0:
        return None

    prev_top = max(prev['o'], prev['c'])
    prev_bot = min(prev['o'], prev['c'])
    curr_top = max(curr['o'], curr['c'])
    curr_bot = min(curr['o'], curr['c'])

    # 2nd body must be inside 1st body
    if not (curr_top <= prev_top and curr_bot >= prev_bot):
        return None
    # 2nd body should be notably smaller
    if curr_body > prev_body * 0.6:
        return None

    if _is_bearish(prev['o'], prev['c']) and _is_bullish(curr['o'], curr['c']):
        return {
            'name': 'Bullish Harami',
            'name_id': 'Bullish Harami',
            'signal': 'bullish',
            'strength': 2,
            'description': 'Candle bullish kecil di dalam body bearish sebelumnya, potensi reversal.',
            'description_en': 'Small bullish candle inside previous bearish body, potential reversal.',
        }
    if _is_bullish(prev['o'], prev['c']) and _is_bearish(curr['o'], curr['c']):
        return {
            'name': 'Bearish Harami',
            'name_id': 'Bearish Harami',
            'signal': 'bearish',
            'strength': 2,
            'description': 'Candle bearish kecil di dalam body bullish sebelumnya, potensi reversal.',
            'description_en': 'Small bearish candle inside previous bullish body, potential reversal.',
        }
    return None


def detect_morning_star(candles):
    """
    Morning Star — 3-candle bullish reversal: bearish → small body → bullish.
    """
    if len(candles) < 3:
        return None
    c1, c2, c3 = candles[-3], candles[-2], candles[-1]

    r1 = _range(c1['h'], c1['l'])
    r2 = _range(c2['h'], c2['l'])
    if r1 == 0:
        return None

    body1 = _body(c1['o'], c1['c'])
    body2 = _body(c2['o'], c2['c'])
    body3 = _body(c3['o'], c3['c'])

    # c1 bearish with substantial body, c2 small body, c3 bullish with substantial body
    if (_is_bearish(c1['o'], c1['c']) and
            body1 / r1 > 0.40 and
            body2 < body1 * 0.40 and
            _is_bullish(c3['o'], c3['c']) and
            body3 > body1 * 0.40 and
            c3['c'] > (c1['o'] + c1['c']) / 2):  # c3 closes above midpoint of c1
        return {
            'name': 'Morning Star',
            'name_id': 'Morning Star',
            'signal': 'bullish',
            'strength': 3,
            'description': 'Pola 3 candle: bearish → body kecil → bullish. Sinyal reversal bullish kuat.',
            'description_en': '3-candle pattern: bearish → small body → bullish. Strong bullish reversal.',
        }
    return None


def detect_evening_star(candles):
    """
    Evening Star — 3-candle bearish reversal: bullish → small body → bearish.
    """
    if len(candles) < 3:
        return None
    c1, c2, c3 = candles[-3], candles[-2], candles[-1]

    r1 = _range(c1['h'], c1['l'])
    if r1 == 0:
        return None

    body1 = _body(c1['o'], c1['c'])
    body2 = _body(c2['o'], c2['c'])
    body3 = _body(c3['o'], c3['c'])

    if (_is_bullish(c1['o'], c1['c']) and
            body1 / r1 > 0.40 and
            body2 < body1 * 0.40 and
            _is_bearish(c3['o'], c3['c']) and
            body3 > body1 * 0.40 and
            c3['c'] < (c1['o'] + c1['c']) / 2):
        return {
            'name': 'Evening Star',
            'name_id': 'Evening Star',
            'signal': 'bearish',
            'strength': 3,
            'description': 'Pola 3 candle: bullish → body kecil → bearish. Sinyal reversal bearish kuat.',
            'description_en': '3-candle pattern: bullish → small body → bearish. Strong bearish reversal.',
        }
    return None


def detect_three_white_soldiers(candles):
    """
    Three White Soldiers — three consecutive bullish candles with higher closes.
    """
    if len(candles) < 3:
        return None
    c1, c2, c3 = candles[-3], candles[-2], candles[-1]

    all_bullish = all(_is_bullish(c['o'], c['c']) for c in [c1, c2, c3])
    higher_closes = c2['c'] > c1['c'] and c3['c'] > c2['c']
    higher_opens = c2['o'] > c1['o'] and c3['o'] > c2['o']

    # Each candle should have decent body (> 50% of range)
    decent_bodies = all(
        _body(c['o'], c['c']) / _range(c['h'], c['l']) > 0.50
        for c in [c1, c2, c3]
        if _range(c['h'], c['l']) > 0
    )

    if all_bullish and higher_closes and higher_opens and decent_bodies:
        return {
            'name': 'Three White Soldiers',
            'name_id': 'Three White Soldiers',
            'signal': 'bullish',
            'strength': 3,
            'description': 'Tiga candle bullish berturut-turut dengan close semakin tinggi, tren naik kuat.',
            'description_en': 'Three consecutive bullish candles with higher closes, strong uptrend.',
        }
    return None


def detect_three_black_crows(candles):
    """
    Three Black Crows — three consecutive bearish candles with lower closes.
    """
    if len(candles) < 3:
        return None
    c1, c2, c3 = candles[-3], candles[-2], candles[-1]

    all_bearish = all(_is_bearish(c['o'], c['c']) for c in [c1, c2, c3])
    lower_closes = c2['c'] < c1['c'] and c3['c'] < c2['c']
    lower_opens = c2['o'] < c1['o'] and c3['o'] < c2['o']

    decent_bodies = all(
        _body(c['o'], c['c']) / _range(c['h'], c['l']) > 0.50
        for c in [c1, c2, c3]
        if _range(c['h'], c['l']) > 0
    )

    if all_bearish and lower_closes and lower_opens and decent_bodies:
        return {
            'name': 'Three Black Crows',
            'name_id': 'Three Black Crows',
            'signal': 'bearish',
            'strength': 3,
            'description': 'Tiga candle bearish berturut-turut dengan close semakin rendah, tren turun kuat.',
            'description_en': 'Three consecutive bearish candles with lower closes, strong downtrend.',
        }
    return None


# ─── Main Detection Function ────────────────────────────────────────

def detect_all_patterns(df: pd.DataFrame, lookback: int = 5) -> dict:
    """
    Scan the last `lookback` candles for all candlestick patterns.

    Args:
        df: DataFrame with 'Open', 'High', 'Low', 'Close' columns
        lookback: Number of recent candles to analyze (default 5)

    Returns:
        dict with:
            'patterns': list of detected pattern dicts
            'summary': {bullish_count, bearish_count, neutral_count, overall_signal}
    """
    if df is None or len(df) < 3:
        return {
            'patterns': [],
            'summary': {
                'bullish_count': 0,
                'bearish_count': 0,
                'neutral_count': 0,
                'overall_signal': 'neutral',
                'overall_label': 'Data Tidak Cukup',
            },
        }

    # Normalize column names
    cols = {c.lower(): c for c in df.columns}
    o_col = cols.get('open', 'Open')
    h_col = cols.get('high', 'High')
    l_col = cols.get('low', 'Low')
    c_col = cols.get('close', 'Close')

    recent = df.iloc[-lookback:]
    patterns = []

    # ── Single-candle patterns on the LAST candle ──
    last = recent.iloc[-1]
    o, h, l, c = float(last[o_col]), float(last[h_col]), float(last[l_col]), float(last[c_col])

    single_detectors = [
        detect_dragonfly_doji,
        detect_gravestone_doji,
        detect_doji,           # generic doji after specialized dojis
        detect_hammer,
        detect_inverted_hammer,
        detect_shooting_star,
        detect_marubozu,
        detect_spinning_top,
    ]

    detected_names = set()
    for detector in single_detectors:
        result = detector(o, h, l, c)
        if result and result['name'] not in detected_names:
            patterns.append(result)
            detected_names.add(result['name'])

    # ── Multi-candle patterns (last 2–3 candles) ──
    candle_dicts = []
    for _, row in recent.iterrows():
        candle_dicts.append({
            'o': float(row[o_col]),
            'h': float(row[h_col]),
            'l': float(row[l_col]),
            'c': float(row[c_col]),
        })

    multi_detectors = [
        detect_engulfing,
        detect_harami,
        detect_morning_star,
        detect_evening_star,
        detect_three_white_soldiers,
        detect_three_black_crows,
    ]

    for detector in multi_detectors:
        result = detector(candle_dicts)
        if result and result['name'] not in detected_names:
            patterns.append(result)
            detected_names.add(result['name'])

    # ── Summary ──
    bullish = sum(1 for p in patterns if p['signal'] == 'bullish')
    bearish = sum(1 for p in patterns if p['signal'] == 'bearish')
    neutral = sum(1 for p in patterns if p['signal'] == 'neutral')

    # Weighted signal
    bullish_weight = sum(p['strength'] for p in patterns if p['signal'] == 'bullish')
    bearish_weight = sum(p['strength'] for p in patterns if p['signal'] == 'bearish')

    if bullish_weight > bearish_weight and bullish > 0:
        overall = 'bullish'
        label = 'Bullish'
    elif bearish_weight > bullish_weight and bearish > 0:
        overall = 'bearish'
        label = 'Bearish'
    else:
        overall = 'neutral'
        label = 'Netral'

    return {
        'patterns': patterns,
        'summary': {
            'bullish_count': bullish,
            'bearish_count': bearish,
            'neutral_count': neutral,
            'total_detected': len(patterns),
            'overall_signal': overall,
            'overall_label': label,
        },
    }
