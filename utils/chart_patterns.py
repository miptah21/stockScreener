"""
Chart Pattern Detection Module
Detects geometric price patterns using scipy.signal.find_peaks.

Patterns detected:
  - Double Top / Double Bottom
  - Head and Shoulders / Inverse Head and Shoulders
  - Ascending Triangle / Descending Triangle
"""

import logging

import numpy as np
import pandas as pd

try:
    from scipy.signal import find_peaks
except ImportError:
    find_peaks = None

logger = logging.getLogger(__name__)


# ─── Local Extrema Detection ────────────────────────────────────────

def _find_local_extrema(closes: np.ndarray, distance: int = 10,
                         prominence: float = None):
    """
    Find local maxima (peaks) and minima (troughs) in price data.

    Args:
        closes: Array of closing prices
        distance: Minimum distance between peaks
        prominence: Minimum prominence of peaks (auto-calculated if None)

    Returns:
        (peak_indices, trough_indices) as numpy arrays
    """
    if find_peaks is None:
        logger.warning("scipy not installed — chart pattern detection disabled")
        return np.array([]), np.array([])

    if len(closes) < distance * 2:
        return np.array([]), np.array([])

    # Auto-calculate prominence as % of price range
    if prominence is None:
        price_range = closes.max() - closes.min()
        prominence = price_range * 0.03  # 3% of range

    # Find peaks (local maxima)
    peak_idx, peak_props = find_peaks(
        closes, distance=distance, prominence=prominence
    )

    # Find troughs (local minima) by inverting data
    trough_idx, trough_props = find_peaks(
        -closes, distance=distance, prominence=prominence
    )

    return peak_idx, trough_idx


# ─── Pattern Detectors ──────────────────────────────────────────────

def _detect_double_top(closes, peaks, troughs):
    """
    Double Top — two peaks at similar price with a trough between them.
    Bearish reversal pattern.
    """
    results = []
    if len(peaks) < 2:
        return results

    for i in range(len(peaks) - 1):
        p1_idx, p2_idx = peaks[i], peaks[i + 1]
        p1_price, p2_price = closes[p1_idx], closes[p2_idx]

        # Peaks should be at similar levels (within 3%)
        avg_peak = (p1_price + p2_price) / 2
        if avg_peak == 0:
            continue
        price_diff_pct = abs(p1_price - p2_price) / avg_peak

        if price_diff_pct > 0.03:
            continue

        # Find trough between peaks
        between_troughs = troughs[(troughs > p1_idx) & (troughs < p2_idx)]
        if len(between_troughs) == 0:
            continue

        trough_idx = between_troughs[np.argmin(closes[between_troughs])]
        neckline = closes[trough_idx]

        # Trough should be notably lower than peaks (at least 2%)
        if neckline >= avg_peak * 0.98:
            continue

        # Calculate confidence based on symmetry and depth
        symmetry = 1 - price_diff_pct / 0.03  # Higher when peaks are equal
        depth = (avg_peak - neckline) / avg_peak
        confidence = int(min(100, (symmetry * 50 + min(depth * 10, 1) * 50)))

        # Target price = neckline - (peak_avg - neckline)
        target = neckline - (avg_peak - neckline)

        results.append({
            'name': 'Double Top',
            'name_id': 'Double Top',
            'signal': 'bearish',
            'confidence': confidence,
            'neckline': round(float(neckline), 2),
            'target_price': round(float(target), 2),
            'peak1_idx': int(p1_idx),
            'peak2_idx': int(p2_idx),
            'description': f'Dua puncak di level ~{avg_peak:.0f}, neckline {neckline:.0f}. Target: {target:.0f}.',
            'description_en': f'Two peaks at ~{avg_peak:.0f}, neckline {neckline:.0f}. Target: {target:.0f}.',
        })

    return results


def _detect_double_bottom(closes, peaks, troughs):
    """
    Double Bottom — two troughs at similar price with a peak between them.
    Bullish reversal pattern.
    """
    results = []
    if len(troughs) < 2:
        return results

    for i in range(len(troughs) - 1):
        t1_idx, t2_idx = troughs[i], troughs[i + 1]
        t1_price, t2_price = closes[t1_idx], closes[t2_idx]

        avg_trough = (t1_price + t2_price) / 2
        if avg_trough == 0:
            continue
        price_diff_pct = abs(t1_price - t2_price) / avg_trough

        if price_diff_pct > 0.03:
            continue

        between_peaks = peaks[(peaks > t1_idx) & (peaks < t2_idx)]
        if len(between_peaks) == 0:
            continue

        peak_idx = between_peaks[np.argmax(closes[between_peaks])]
        neckline = closes[peak_idx]

        if neckline <= avg_trough * 1.02:
            continue

        symmetry = 1 - price_diff_pct / 0.03
        depth = (neckline - avg_trough) / neckline if neckline > 0 else 0
        confidence = int(min(100, (symmetry * 50 + min(depth * 10, 1) * 50)))

        target = neckline + (neckline - avg_trough)

        results.append({
            'name': 'Double Bottom',
            'name_id': 'Double Bottom',
            'signal': 'bullish',
            'confidence': confidence,
            'neckline': round(float(neckline), 2),
            'target_price': round(float(target), 2),
            'trough1_idx': int(t1_idx),
            'trough2_idx': int(t2_idx),
            'description': f'Dua lembah di level ~{avg_trough:.0f}, neckline {neckline:.0f}. Target: {target:.0f}.',
            'description_en': f'Two troughs at ~{avg_trough:.0f}, neckline {neckline:.0f}. Target: {target:.0f}.',
        })

    return results


def _detect_head_shoulders(closes, peaks, troughs):
    """
    Head and Shoulders — three peaks where middle is highest (bearish).
    """
    results = []
    if len(peaks) < 3:
        return results

    for i in range(len(peaks) - 2):
        ls_idx, head_idx, rs_idx = peaks[i], peaks[i + 1], peaks[i + 2]
        ls_price = closes[ls_idx]
        head_price = closes[head_idx]
        rs_price = closes[rs_idx]

        # Head must be highest
        if head_price <= ls_price or head_price <= rs_price:
            continue

        # Shoulders should be at similar levels (within 5%)
        avg_shoulder = (ls_price + rs_price) / 2
        if avg_shoulder == 0:
            continue
        shoulder_diff = abs(ls_price - rs_price) / avg_shoulder
        if shoulder_diff > 0.05:
            continue

        # Find neckline (connect troughs between shoulder and head)
        left_troughs = troughs[(troughs > ls_idx) & (troughs < head_idx)]
        right_troughs = troughs[(troughs > head_idx) & (troughs < rs_idx)]

        if len(left_troughs) == 0 or len(right_troughs) == 0:
            continue

        left_neckline = closes[left_troughs[np.argmin(closes[left_troughs])]]
        right_neckline = closes[right_troughs[np.argmin(closes[right_troughs])]]
        neckline = (left_neckline + right_neckline) / 2

        # Head should be notably above neckline
        head_height = head_price - neckline
        if head_height <= 0:
            continue

        symmetry = 1 - shoulder_diff / 0.05
        prominence = head_height / head_price if head_price > 0 else 0
        confidence = int(min(100, (symmetry * 40 + min(prominence * 10, 1) * 60)))

        target = neckline - head_height

        results.append({
            'name': 'Head and Shoulders',
            'name_id': 'Head and Shoulders',
            'signal': 'bearish',
            'confidence': confidence,
            'neckline': round(float(neckline), 2),
            'target_price': round(float(target), 2),
            'head_price': round(float(head_price), 2),
            'description': f'H&S: Head {head_price:.0f}, Shoulders ~{avg_shoulder:.0f}, Neckline {neckline:.0f}. Target: {target:.0f}.',
            'description_en': f'H&S: Head {head_price:.0f}, Shoulders ~{avg_shoulder:.0f}, Neckline {neckline:.0f}. Target: {target:.0f}.',
        })

    return results


def _detect_inverse_head_shoulders(closes, peaks, troughs):
    """
    Inverse Head and Shoulders — three troughs where middle is lowest (bullish).
    """
    results = []
    if len(troughs) < 3:
        return results

    for i in range(len(troughs) - 2):
        ls_idx, head_idx, rs_idx = troughs[i], troughs[i + 1], troughs[i + 2]
        ls_price = closes[ls_idx]
        head_price = closes[head_idx]
        rs_price = closes[rs_idx]

        # Head must be lowest
        if head_price >= ls_price or head_price >= rs_price:
            continue

        avg_shoulder = (ls_price + rs_price) / 2
        if avg_shoulder == 0:
            continue
        shoulder_diff = abs(ls_price - rs_price) / avg_shoulder
        if shoulder_diff > 0.05:
            continue

        left_peaks = peaks[(peaks > ls_idx) & (peaks < head_idx)]
        right_peaks = peaks[(peaks > head_idx) & (peaks < rs_idx)]

        if len(left_peaks) == 0 or len(right_peaks) == 0:
            continue

        left_neckline = closes[left_peaks[np.argmax(closes[left_peaks])]]
        right_neckline = closes[right_peaks[np.argmax(closes[right_peaks])]]
        neckline = (left_neckline + right_neckline) / 2

        head_depth = neckline - head_price
        if head_depth <= 0:
            continue

        symmetry = 1 - shoulder_diff / 0.05
        prominence = head_depth / neckline if neckline > 0 else 0
        confidence = int(min(100, (symmetry * 40 + min(prominence * 10, 1) * 60)))

        target = neckline + head_depth

        results.append({
            'name': 'Inverse Head and Shoulders',
            'name_id': 'Inverse Head and Shoulders',
            'signal': 'bullish',
            'confidence': confidence,
            'neckline': round(float(neckline), 2),
            'target_price': round(float(target), 2),
            'head_price': round(float(head_price), 2),
            'description': f'Inv H&S: Head {head_price:.0f}, Shoulders ~{avg_shoulder:.0f}, Neckline {neckline:.0f}. Target: {target:.0f}.',
            'description_en': f'Inv H&S: Head {head_price:.0f}, Shoulders ~{avg_shoulder:.0f}, Neckline {neckline:.0f}. Target: {target:.0f}.',
        })

    return results


def _detect_ascending_triangle(closes, peaks, troughs):
    """
    Ascending Triangle — flat top resistance + rising support (bullish continuation).
    """
    results = []
    if len(peaks) < 2 or len(troughs) < 2:
        return results

    # Check last few peaks for flat resistance
    recent_peaks = peaks[-4:] if len(peaks) >= 4 else peaks
    if len(recent_peaks) < 2:
        return results

    peak_prices = closes[recent_peaks]
    avg_resistance = np.mean(peak_prices)
    if avg_resistance == 0:
        return results
    resistance_flat = np.std(peak_prices) / avg_resistance < 0.02  # Within 2%

    if not resistance_flat:
        return results

    # Check if troughs are rising
    recent_troughs = troughs[-4:] if len(troughs) >= 4 else troughs
    if len(recent_troughs) < 2:
        return results

    trough_prices = closes[recent_troughs]
    rising_support = all(
        trough_prices[j] >= trough_prices[j - 1] * 0.99
        for j in range(1, len(trough_prices))
    )

    if not rising_support:
        return results

    flatness = 1 - np.std(peak_prices) / avg_resistance / 0.02
    confidence = int(min(100, flatness * 70 + 30))

    results.append({
        'name': 'Ascending Triangle',
        'name_id': 'Ascending Triangle',
        'signal': 'bullish',
        'confidence': confidence,
        'resistance': round(float(avg_resistance), 2),
        'support_trend': 'rising',
        'description': f'Resistance flat ~{avg_resistance:.0f} dengan support yang naik. Pola bullish continuation.',
        'description_en': f'Flat resistance ~{avg_resistance:.0f} with rising support. Bullish continuation.',
    })

    return results


def _detect_descending_triangle(closes, peaks, troughs):
    """
    Descending Triangle — flat bottom support + falling resistance (bearish continuation).
    """
    results = []
    if len(peaks) < 2 or len(troughs) < 2:
        return results

    recent_troughs = troughs[-4:] if len(troughs) >= 4 else troughs
    if len(recent_troughs) < 2:
        return results

    trough_prices = closes[recent_troughs]
    avg_support = np.mean(trough_prices)
    if avg_support == 0:
        return results
    support_flat = np.std(trough_prices) / avg_support < 0.02

    if not support_flat:
        return results

    recent_peaks = peaks[-4:] if len(peaks) >= 4 else peaks
    if len(recent_peaks) < 2:
        return results

    peak_prices = closes[recent_peaks]
    falling_resistance = all(
        peak_prices[j] <= peak_prices[j - 1] * 1.01
        for j in range(1, len(peak_prices))
    )

    if not falling_resistance:
        return results

    flatness = 1 - np.std(trough_prices) / avg_support / 0.02
    confidence = int(min(100, flatness * 70 + 30))

    results.append({
        'name': 'Descending Triangle',
        'name_id': 'Descending Triangle',
        'signal': 'bearish',
        'confidence': confidence,
        'support': round(float(avg_support), 2),
        'resistance_trend': 'falling',
        'description': f'Support flat ~{avg_support:.0f} dengan resistance yang turun. Pola bearish continuation.',
        'description_en': f'Flat support ~{avg_support:.0f} with falling resistance. Bearish continuation.',
    })

    return results


# ─── Main Detection Function ────────────────────────────────────────

def detect_chart_patterns(df: pd.DataFrame, lookback: int = 120) -> list:
    """
    Detect chart patterns in the price data.

    Args:
        df: DataFrame with 'Close', 'High', 'Low' columns
        lookback: Number of bars to analyze (default 120 ~ 6 months)

    Returns:
        list of detected chart pattern dicts
    """
    if df is None or len(df) < 30:
        return []

    if find_peaks is None:
        return []

    # Use recent data
    recent = df.iloc[-lookback:] if len(df) > lookback else df

    # Normalize column names
    cols = {c.lower(): c for c in recent.columns}
    c_col = cols.get('close', 'Close')

    closes = recent[c_col].values.astype(float)

    # Find local extrema
    peaks, troughs = _find_local_extrema(closes, distance=8)

    if len(peaks) < 2 and len(troughs) < 2:
        return []

    # Run all detectors
    all_patterns = []
    all_patterns.extend(_detect_double_top(closes, peaks, troughs))
    all_patterns.extend(_detect_double_bottom(closes, peaks, troughs))
    all_patterns.extend(_detect_head_shoulders(closes, peaks, troughs))
    all_patterns.extend(_detect_inverse_head_shoulders(closes, peaks, troughs))
    all_patterns.extend(_detect_ascending_triangle(closes, peaks, troughs))
    all_patterns.extend(_detect_descending_triangle(closes, peaks, troughs))

    # Sort by confidence (highest first)
    all_patterns.sort(key=lambda p: p.get('confidence', 0), reverse=True)

    # Keep top 5 to avoid noise
    return all_patterns[:5]
