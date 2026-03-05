"""
Unit tests for utils/patterns.py — Candlestick Pattern Detection
"""

import pytest
import pandas as pd
import numpy as np

from utils.patterns import (
    detect_doji,
    detect_dragonfly_doji,
    detect_gravestone_doji,
    detect_hammer,
    detect_inverted_hammer,
    detect_shooting_star,
    detect_spinning_top,
    detect_marubozu,
    detect_engulfing,
    detect_harami,
    detect_morning_star,
    detect_evening_star,
    detect_three_white_soldiers,
    detect_three_black_crows,
    detect_all_patterns,
)


# ─── Single-Candle Pattern Tests ────────────────────────────────────

class TestDoji:
    def test_classic_doji(self):
        # Body = 0.5, range = 10 → body/range = 5% < 10%
        result = detect_doji(o=100, h=105, l=95, c=100.5)
        assert result is not None
        assert result['name'] == 'Doji'
        assert result['signal'] == 'neutral'

    def test_no_doji_when_body_large(self):
        # Body = 5, range = 10 → 50%
        result = detect_doji(o=95, h=105, l=95, c=100)
        assert result is None

    def test_flat_candle(self):
        # range = 0 → should return None
        result = detect_doji(o=100, h=100, l=100, c=100)
        assert result is None


class TestDragonflyDoji:
    def test_detect(self):
        # body ≈ 0, long lower shadow, no upper shadow
        result = detect_dragonfly_doji(o=100, h=100.2, l=90, c=100)
        assert result is not None
        assert result['signal'] == 'bullish'

    def test_no_detect_with_upper_shadow(self):
        result = detect_dragonfly_doji(o=100, h=108, l=90, c=100)
        assert result is None


class TestGravestoneDoji:
    def test_detect(self):
        result = detect_gravestone_doji(o=100, h=110, l=99.8, c=100)
        assert result is not None
        assert result['signal'] == 'bearish'


class TestHammer:
    def test_bullish_hammer(self):
        # small body at top, lower shadow ≥ 2× body
        result = detect_hammer(o=98, h=100, l=90, c=100)
        assert result is not None
        assert result['signal'] == 'bullish'
        assert result['name'] == 'Hammer'

    def test_no_hammer_when_body_too_large(self):
        result = detect_hammer(o=90, h=100, l=89, c=100)
        assert result is None


class TestInvertedHammer:
    def test_detect(self):
        result = detect_inverted_hammer(o=90, h=100, l=89, c=92)
        assert result is not None
        assert result['signal'] == 'bullish'


class TestShootingStar:
    def test_detect(self):
        # Bearish close, long upper shadow
        result = detect_shooting_star(o=100, h=110, l=98, c=98)
        assert result is not None
        assert result['signal'] == 'bearish'


class TestSpinningTop:
    def test_detect(self):
        # Small body, shadows on both sides > body
        result = detect_spinning_top(o=99, h=105, l=95, c=101)
        assert result is not None
        assert result['signal'] == 'neutral'


class TestMarubozu:
    def test_bullish_marubozu(self):
        result = detect_marubozu(o=90, h=100, l=90, c=100)
        assert result is not None
        assert result['signal'] == 'bullish'
        assert result['strength'] == 3

    def test_bearish_marubozu(self):
        result = detect_marubozu(o=100, h=100, l=90, c=90)
        assert result is not None
        assert result['signal'] == 'bearish'


# ─── Multi-Candle Pattern Tests ────────────────────────────────────

class TestEngulfing:
    def test_bullish_engulfing(self):
        candles = [
            {'o': 102, 'h': 103, 'l': 98, 'c': 99},  # bearish
            {'o': 98, 'h': 106, 'l': 97, 'c': 105},   # bullish engulfing
        ]
        result = detect_engulfing(candles)
        assert result is not None
        assert result['name'] == 'Bullish Engulfing'
        assert result['signal'] == 'bullish'

    def test_bearish_engulfing(self):
        candles = [
            {'o': 98, 'h': 103, 'l': 97, 'c': 102},   # bullish
            {'o': 103, 'h': 104, 'l': 95, 'c': 96},    # bearish engulfing
        ]
        result = detect_engulfing(candles)
        assert result is not None
        assert result['name'] == 'Bearish Engulfing'

    def test_no_engulfing_same_direction(self):
        candles = [
            {'o': 98, 'h': 103, 'l': 97, 'c': 102},  # bullish
            {'o': 99, 'h': 107, 'l': 98, 'c': 106},   # also bullish, not engulfing
        ]
        result = detect_engulfing(candles)
        assert result is None

    def test_insufficient_data(self):
        result = detect_engulfing([{'o': 100, 'h': 101, 'l': 99, 'c': 100}])
        assert result is None


class TestHarami:
    def test_bullish_harami(self):
        candles = [
            {'o': 105, 'h': 106, 'l': 95, 'c': 96},   # large bearish
            {'o': 99, 'h': 101, 'l': 98, 'c': 100},    # small bullish inside
        ]
        result = detect_harami(candles)
        assert result is not None
        assert result['name'] == 'Bullish Harami'


class TestMorningStar:
    def test_detect(self):
        candles = [
            {'o': 110, 'h': 111, 'l': 100, 'c': 101},  # big bearish
            {'o': 101, 'h': 102, 'l': 99, 'c': 100},    # small body
            {'o': 100, 'h': 112, 'l': 99, 'c': 111},    # big bullish
        ]
        result = detect_morning_star(candles)
        assert result is not None
        assert result['signal'] == 'bullish'


class TestEveningStar:
    def test_detect(self):
        candles = [
            {'o': 100, 'h': 111, 'l': 99, 'c': 110},   # big bullish
            {'o': 110, 'h': 112, 'l': 109, 'c': 111},   # small body
            {'o': 111, 'h': 112, 'l': 100, 'c': 101},   # big bearish
        ]
        result = detect_evening_star(candles)
        assert result is not None
        assert result['signal'] == 'bearish'


class TestThreeWhiteSoldiers:
    def test_detect(self):
        candles = [
            {'o': 90, 'h': 98, 'l': 90, 'c': 97},
            {'o': 95, 'h': 104, 'l': 95, 'c': 103},
            {'o': 101, 'h': 110, 'l': 101, 'c': 109},
        ]
        result = detect_three_white_soldiers(candles)
        assert result is not None
        assert result['signal'] == 'bullish'


class TestThreeBlackCrows:
    def test_detect(self):
        candles = [
            {'o': 110, 'h': 110, 'l': 101, 'c': 102},
            {'o': 104, 'h': 104, 'l': 96, 'c': 97},
            {'o': 99, 'h': 99, 'l': 90, 'c': 91},
        ]
        result = detect_three_black_crows(candles)
        assert result is not None
        assert result['signal'] == 'bearish'


# ─── detect_all_patterns Integration Test ───────────────────────────

class TestDetectAllPatterns:
    def _make_df(self, rows):
        """Helper to create a DataFrame from list of (o, h, l, c) tuples."""
        df = pd.DataFrame(rows, columns=['Open', 'High', 'Low', 'Close'])
        return df

    def test_empty_dataframe(self):
        result = detect_all_patterns(pd.DataFrame())
        assert result['patterns'] == []
        assert result['summary']['overall_signal'] == 'neutral'

    def test_none_input(self):
        result = detect_all_patterns(None)
        assert result['patterns'] == []

    def test_doji_detection_in_df(self):
        df = self._make_df([
            (100, 105, 95, 102),
            (102, 108, 97, 105),
            (105, 108, 100, 103),
            (103, 107, 98, 104),
            (104, 109, 99, 104.3),  # doji-like
        ])
        result = detect_all_patterns(df)
        assert isinstance(result['patterns'], list)
        assert isinstance(result['summary'], dict)
        assert 'bullish_count' in result['summary']
        assert 'overall_signal' in result['summary']

    def test_bullish_engulfing_in_df(self):
        df = self._make_df([
            (100, 102, 98, 101),
            (101, 104, 99, 103),
            (103, 105, 100, 104),
            (106, 107, 100, 101),    # bearish
            (100, 110, 99, 109),     # bullish engulfing
        ])
        result = detect_all_patterns(df)
        names = [p['name'] for p in result['patterns']]
        assert 'Bullish Engulfing' in names

    def test_lowercase_columns(self):
        df = pd.DataFrame({
            'open': [100, 101, 102, 103, 104],
            'high': [105, 106, 107, 108, 109],
            'low': [95, 96, 97, 98, 99],
            'close': [102, 103, 104, 105, 104.2],
        })
        result = detect_all_patterns(df)
        assert isinstance(result['summary'], dict)
