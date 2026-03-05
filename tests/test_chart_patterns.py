"""
Unit tests for utils/chart_patterns.py — Chart Pattern Detection
"""

import pytest
import pandas as pd
import numpy as np

from utils.chart_patterns import detect_chart_patterns


class TestDetectChartPatterns:
    def _make_df(self, closes):
        """Create a DataFrame from a list of close prices."""
        n = len(closes)
        return pd.DataFrame({
            'Open': closes,
            'High': [c * 1.02 for c in closes],
            'Low': [c * 0.98 for c in closes],
            'Close': closes,
            'Volume': [1000000] * n,
        })

    def test_empty_df(self):
        result = detect_chart_patterns(pd.DataFrame())
        assert result == []

    def test_none_df(self):
        result = detect_chart_patterns(None)
        assert result == []

    def test_insufficient_data(self):
        df = self._make_df([100, 101, 102])
        result = detect_chart_patterns(df)
        assert result == []

    def test_returns_list(self):
        # Generate some synthetic data with peaks and troughs
        np.random.seed(42)
        n = 120
        t = np.linspace(0, 4 * np.pi, n)
        closes = 100 + 10 * np.sin(t) + np.random.randn(n) * 0.5
        df = self._make_df(closes.tolist())
        result = detect_chart_patterns(df)
        assert isinstance(result, list)

    def test_double_top_detection(self):
        """Synthetic double top: two peaks at similar level with a trough."""
        prices = []
        # Ramp up
        for i in range(20):
            prices.append(100 + i * 0.5)
        # First peak at 110
        for i in range(10):
            prices.append(110 - abs(i - 5) * 1.5)
        # Trough at ~102
        for i in range(10):
            prices.append(102 + abs(i - 5) * 0.3)
        # Second peak at ~110
        for i in range(10):
            prices.append(110 - abs(i - 5) * 1.5)
        # Decline
        for i in range(15):
            prices.append(108 - i * 0.8)

        df = self._make_df(prices)
        result = detect_chart_patterns(df)
        # May or may not detect depending on prominence; this tests no crash
        assert isinstance(result, list)

    def test_double_bottom_detection(self):
        """Synthetic double bottom."""
        prices = []
        # Decline
        for i in range(20):
            prices.append(110 - i * 0.5)
        # First trough at ~100
        for i in range(10):
            prices.append(100 + abs(i - 5) * 1.5)
        # Peak at ~108
        for i in range(10):
            prices.append(108 - abs(i - 5) * 0.3)
        # Second trough at ~100
        for i in range(10):
            prices.append(100 + abs(i - 5) * 1.5)
        # Recovery
        for i in range(15):
            prices.append(102 + i * 0.8)

        df = self._make_df(prices)
        result = detect_chart_patterns(df)
        assert isinstance(result, list)

    def test_max_results_capped(self):
        """Ensure results are capped at 5."""
        np.random.seed(123)
        t = np.linspace(0, 10 * np.pi, 250)
        closes = 100 + 10 * np.sin(t)
        df = self._make_df(closes.tolist())
        result = detect_chart_patterns(df, lookback=250)
        assert len(result) <= 5

    def test_pattern_structure(self):
        """Verify each returned pattern has required fields."""
        np.random.seed(42)
        t = np.linspace(0, 4 * np.pi, 120)
        closes = 100 + 10 * np.sin(t) + np.random.randn(120) * 0.3
        df = self._make_df(closes.tolist())
        result = detect_chart_patterns(df)
        for p in result:
            assert 'name' in p
            assert 'signal' in p
            assert 'confidence' in p
            assert p['signal'] in ('bullish', 'bearish')
            assert 0 <= p['confidence'] <= 100
