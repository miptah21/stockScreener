"""
Unit tests for utils/support_resistance.py — Support/Resistance Detection
"""

import pytest
import pandas as pd
import numpy as np

from utils.support_resistance import detect_sr_levels, _cluster_levels


class TestClusterLevels:
    def test_empty(self):
        result = _cluster_levels(np.array([]))
        assert result == []

    def test_single_level(self):
        result = _cluster_levels(np.array([100.0]))
        assert len(result) == 1
        assert result[0]['price'] == 100.0
        assert result[0]['count'] == 1

    def test_nearby_levels_merged(self):
        # 100, 100.5, 101 are within 1.5% → should merge
        result = _cluster_levels(np.array([100.0, 100.5, 101.0]), threshold_pct=0.015)
        assert len(result) == 1
        assert result[0]['count'] == 3

    def test_distant_levels_separate(self):
        # 100 and 120 are 20% apart → separate clusters
        result = _cluster_levels(np.array([100.0, 120.0]), threshold_pct=0.015)
        assert len(result) == 2


class TestDetectSRLevels:
    def _make_df(self, closes, volumes=None):
        """Create DataFrame from close prices."""
        n = len(closes)
        highs = [c * 1.01 for c in closes]
        lows = [c * 0.99 for c in closes]
        if volumes is None:
            volumes = [1000000] * n
        return pd.DataFrame({
            'Open': closes,
            'High': highs,
            'Low': lows,
            'Close': closes,
            'Volume': volumes,
        })

    def test_empty_df(self):
        result = detect_sr_levels(pd.DataFrame())
        assert result['support_levels'] == []
        assert result['resistance_levels'] == []
        assert result['current_zone'] == 'unknown'

    def test_none_df(self):
        result = detect_sr_levels(None)
        assert result['support_levels'] == []

    def test_insufficient_data(self):
        df = self._make_df([100, 101, 102])
        result = detect_sr_levels(df)
        assert result['support_levels'] == []

    def test_returns_structure(self):
        """Test with synthetic data that has clear peaks and troughs."""
        np.random.seed(42)
        t = np.linspace(0, 4 * np.pi, 120)
        closes = (100 + 10 * np.sin(t) + np.random.randn(120) * 0.3).tolist()
        df = self._make_df(closes)
        result = detect_sr_levels(df)

        assert 'support_levels' in result
        assert 'resistance_levels' in result
        assert 'current_zone' in result
        assert 'current_price' in result
        assert isinstance(result['support_levels'], list)
        assert isinstance(result['resistance_levels'], list)

    def test_level_structure(self):
        """Verify each level has required fields."""
        np.random.seed(42)
        t = np.linspace(0, 4 * np.pi, 120)
        closes = (100 + 10 * np.sin(t)).tolist()
        df = self._make_df(closes)
        result = detect_sr_levels(df)

        for level in result['support_levels'] + result['resistance_levels']:
            assert 'price' in level
            assert 'touches' in level
            assert 'strength' in level

    def test_support_below_price(self):
        """All support levels should be below current price."""
        np.random.seed(42)
        t = np.linspace(0, 4 * np.pi, 120)
        closes = (100 + 10 * np.sin(t)).tolist()
        df = self._make_df(closes)
        result = detect_sr_levels(df)

        current_price = result['current_price']
        if current_price:
            for level in result['support_levels']:
                assert level['price'] < current_price

    def test_resistance_above_price(self):
        """All resistance levels should be above current price."""
        np.random.seed(42)
        t = np.linspace(0, 4 * np.pi, 120)
        closes = (100 + 10 * np.sin(t)).tolist()
        df = self._make_df(closes)
        result = detect_sr_levels(df)

        current_price = result['current_price']
        if current_price:
            for level in result['resistance_levels']:
                assert level['price'] > current_price

    def test_max_levels_respected(self):
        """Should not return more than max_levels per side."""
        np.random.seed(42)
        t = np.linspace(0, 8 * np.pi, 250)
        closes = (100 + 10 * np.sin(t)).tolist()
        df = self._make_df(closes)
        result = detect_sr_levels(df, max_levels=3)

        assert len(result['support_levels']) <= 3
        assert len(result['resistance_levels']) <= 3

    def test_current_zone_valid_values(self):
        """Current zone should be one of the known values."""
        np.random.seed(42)
        t = np.linspace(0, 4 * np.pi, 120)
        closes = (100 + 10 * np.sin(t)).tolist()
        df = self._make_df(closes)
        result = detect_sr_levels(df)

        valid_zones = {
            'near_support', 'near_resistance', 'mid_range',
            'above_support', 'below_resistance', 'unknown',
        }
        assert result['current_zone'] in valid_zones
