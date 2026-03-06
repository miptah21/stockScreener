"""
Support & Resistance Level Detection Module
Uses scipy.signal.find_peaks for local extrema + clustering for level consolidation.
"""

import logging

import numpy as np
import pandas as pd

def find_peaks(x, distance=1, prominence=None):
    """Custom peak detection to replace scipy and save 140MB bundle size."""
    if len(x) < 3:
        return np.array([]), {}
        
    peaks = []
    for i in range(1, len(x) - 1):
        if x[i] > x[i - 1] and x[i] > x[i + 1]:
            peaks.append(i)
            
    if distance > 1 and peaks:
        peaks.sort(key=lambda idx: x[idx], reverse=True)
        filtered = []
        for p in peaks:
            if not any(abs(p - fp) < distance for fp in filtered):
                filtered.append(p)
        peaks = sorted(filtered)
        
    if prominence is not None and peaks:
        filtered = []
        for p in peaks:
            left_min = np.min(x[max(0, p - 20):p]) if p > 0 else x[p]
            right_min = np.min(x[p + 1:min(len(x), p + 20)]) if p < len(x) - 1 else x[p]
            if x[p] - min(left_min, right_min) >= prominence:
                filtered.append(p)
        peaks = filtered
        
    return np.array(peaks), {}

logger = logging.getLogger(__name__)


def _cluster_levels(prices: np.ndarray, threshold_pct: float = 0.015) -> list:
    """
    Cluster nearby price levels together.
    Levels within `threshold_pct` of each other are merged.

    Returns:
        list of dicts: [{price, count, indices}]
    """
    if len(prices) == 0:
        return []

    sorted_prices = np.sort(prices)
    clusters = []
    current_cluster = [sorted_prices[0]]

    for i in range(1, len(sorted_prices)):
        if current_cluster[-1] == 0:
            current_cluster.append(sorted_prices[i])
            continue
        if abs(sorted_prices[i] - current_cluster[-1]) / current_cluster[-1] <= threshold_pct:
            current_cluster.append(sorted_prices[i])
        else:
            clusters.append({
                'price': round(float(np.mean(current_cluster)), 2),
                'count': len(current_cluster),
            })
            current_cluster = [sorted_prices[i]]

    # Don't forget the last cluster
    if current_cluster:
        clusters.append({
            'price': round(float(np.mean(current_cluster)), 2),
            'count': len(current_cluster),
        })

    return clusters


def _score_level(level_price, all_closes, all_highs, all_lows,
                 all_volumes, threshold_pct=0.015):
    """
    Score a support/resistance level based on:
    - Touch count: how many times price came within threshold
    - Recency: more recent touches score higher
    - Volume: higher volume at touches scores higher
    """
    touches = 0
    volume_at_touches = 0.0
    recency_score = 0.0
    n = len(all_closes)

    for i in range(n):
        # Check if price touched this level (close, high, or low within threshold)
        prices_to_check = [all_closes[i], all_highs[i], all_lows[i]]
        touched = any(
            abs(p - level_price) / level_price <= threshold_pct
            for p in prices_to_check
            if level_price > 0
        )
        if touched:
            touches += 1
            # Recency: more recent = higher weight (linear decay)
            recency_score += (i + 1) / n
            volume_at_touches += all_volumes[i] if i < len(all_volumes) else 0

    # Normalize scores
    touch_score = min(touches / 5.0, 1.0) * 40  # max 40 pts
    recency_normalized = (recency_score / max(touches, 1)) * 30  # max 30 pts
    avg_vol = volume_at_touches / max(touches, 1)
    overall_avg_vol = np.mean(all_volumes) if len(all_volumes) > 0 else 1
    vol_ratio = min(avg_vol / max(overall_avg_vol, 1), 2.0)
    vol_score = vol_ratio / 2.0 * 30  # max 30 pts

    strength = int(min(100, touch_score + recency_normalized + vol_score))

    return {
        'touches': touches,
        'strength': strength,
        'avg_volume_ratio': round(vol_ratio, 2),
    }


def detect_sr_levels(df: pd.DataFrame,
                     lookback: int = 120,
                     max_levels: int = 5) -> dict:
    """
    Detect support and resistance levels from price data.

    Args:
        df: DataFrame with 'Open', 'High', 'Low', 'Close', 'Volume' columns
        lookback: Number of bars to analyze (default 120 ~ 6 months)
        max_levels: Maximum number of S/R levels to return per side

    Returns:
        dict with support_levels, resistance_levels, current_zone
    """
    empty_result = {
        'support_levels': [],
        'resistance_levels': [],
        'current_zone': 'unknown',
        'current_price': None,
    }

    if df is None or len(df) < 20:
        return empty_result

    # Use recent data
    recent = df.iloc[-lookback:] if len(df) > lookback else df

    # Normalize column names
    cols = {c.lower(): c for c in recent.columns}
    c_col = cols.get('close', 'Close')
    h_col = cols.get('high', 'High')
    l_col = cols.get('low', 'Low')
    v_col = cols.get('volume', 'Volume')

    closes = recent[c_col].values.astype(float)
    highs = recent[h_col].values.astype(float)
    lows = recent[l_col].values.astype(float)
    volumes = recent[v_col].values.astype(float) if v_col in recent.columns else np.ones(len(closes))

    current_price = float(closes[-1])

    # Find local extrema
    price_range = closes.max() - closes.min()
    if price_range == 0:
        return empty_result

    prominence = price_range * 0.02  # 2% of range

    peak_idx, _ = find_peaks(closes, distance=5, prominence=prominence)
    trough_idx, _ = find_peaks(-closes, distance=5, prominence=prominence)

    if len(peak_idx) == 0 and len(trough_idx) == 0:
        return empty_result

    # Also consider recent high and low explicitly
    peak_prices = closes[peak_idx] if len(peak_idx) > 0 else np.array([])
    trough_prices = closes[trough_idx] if len(trough_idx) > 0 else np.array([])

    # Add highs at peaks and lows at troughs for better accuracy
    resistance_candidates = np.concatenate([
        peak_prices,
        highs[peak_idx] if len(peak_idx) > 0 else np.array([]),
    ])
    support_candidates = np.concatenate([
        trough_prices,
        lows[trough_idx] if len(trough_idx) > 0 else np.array([]),
    ])

    # Cluster levels
    resistance_clusters = _cluster_levels(resistance_candidates)
    support_clusters = _cluster_levels(support_candidates)

    # Score each level
    scored_resistance = []
    for cluster in resistance_clusters:
        if cluster['price'] <= current_price:
            continue  # Resistance must be above current price
        scoring = _score_level(
            cluster['price'], closes, highs, lows, volumes
        )
        scored_resistance.append({
            'price': cluster['price'],
            'touches': scoring['touches'],
            'strength': scoring['strength'],
            'cluster_count': cluster['count'],
        })

    scored_support = []
    for cluster in support_clusters:
        if cluster['price'] >= current_price:
            continue  # Support must be below current price
        scoring = _score_level(
            cluster['price'], closes, highs, lows, volumes
        )
        scored_support.append({
            'price': cluster['price'],
            'touches': scoring['touches'],
            'strength': scoring['strength'],
            'cluster_count': cluster['count'],
        })

    # Sort by strength (highest first) and limit
    scored_resistance.sort(key=lambda x: x['strength'], reverse=True)
    scored_support.sort(key=lambda x: x['strength'], reverse=True)

    resistance_levels = scored_resistance[:max_levels]
    support_levels = scored_support[:max_levels]

    # Sort by price for display (resistance: ascending, support: descending)
    resistance_levels.sort(key=lambda x: x['price'])
    support_levels.sort(key=lambda x: x['price'], reverse=True)

    # Determine current zone
    nearest_support = support_levels[0]['price'] if support_levels else None
    nearest_resistance = resistance_levels[0]['price'] if resistance_levels else None

    if nearest_support and nearest_resistance:
        range_size = nearest_resistance - nearest_support
        if range_size > 0:
            position = (current_price - nearest_support) / range_size
            if position < 0.25:
                zone = 'near_support'
                zone_label = 'Dekat Support'
            elif position > 0.75:
                zone = 'near_resistance'
                zone_label = 'Dekat Resistance'
            else:
                zone = 'mid_range'
                zone_label = 'Tengah Range'
        else:
            zone = 'unknown'
            zone_label = 'N/A'
    elif nearest_support:
        zone = 'above_support'
        zone_label = 'Di Atas Support'
    elif nearest_resistance:
        zone = 'below_resistance'
        zone_label = 'Di Bawah Resistance'
    else:
        zone = 'unknown'
        zone_label = 'N/A'

    return {
        'support_levels': support_levels,
        'resistance_levels': resistance_levels,
        'current_zone': zone,
        'current_zone_label': zone_label,
        'current_price': round(current_price, 2),
    }
