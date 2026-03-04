"""
Test suite for scoring utility functions.
"""

import pytest
import pandas as pd

from scrapers.scoring.utils import (
    _pct, _ratio, _fmt,
    _safe_get, _safe_divide,
    _format_number, _format_ratio,
    _get_financial_subsector, _is_financial_sector,
)


class TestFormattingFunctions:
    """Tests for display formatting utilities."""

    def test_pct_with_value(self):
        assert _pct(0.85) == '85.00%'
        assert _pct(0.017) == '1.70%'

    def test_pct_with_none(self):
        assert _pct(None) == 'N/A'

    def test_ratio_with_value(self):
        assert _ratio(0.1234) == '0.1234'

    def test_ratio_with_none(self):
        assert _ratio(None) == 'N/A'

    def test_fmt_trillions(self):
        assert 'T' in _fmt(1.5e12)

    def test_fmt_billions(self):
        assert 'B' in _fmt(2.5e9)

    def test_fmt_millions(self):
        assert 'M' in _fmt(3.5e6)

    def test_fmt_small_number(self):
        result = _fmt(1234)
        assert '1,234' in result

    def test_fmt_negative(self):
        result = _fmt(-1e9)
        assert result.startswith('-')
        assert 'B' in result

    def test_fmt_none(self):
        assert _fmt(None) == 'N/A'


class TestSafeFunctions:
    """Tests for safe data access utilities."""

    def test_safe_divide_normal(self):
        assert _safe_divide(10, 5) == 2.0

    def test_safe_divide_by_zero(self):
        assert _safe_divide(10, 0) is None

    def test_safe_divide_with_none(self):
        assert _safe_divide(None, 5) is None
        assert _safe_divide(10, None) is None

    def test_safe_get_with_valid_df(self):
        df = pd.DataFrame({'2024': [100, 200]}, index=['Revenue', 'COGS'])
        result = _safe_get(df, '2024', ['Revenue'])
        assert result == 100.0

    def test_safe_get_with_missing_key(self):
        df = pd.DataFrame({'2024': [100]}, index=['Revenue'])
        result = _safe_get(df, '2024', ['NonExistent'])
        assert result is None

    def test_safe_get_with_none_df(self):
        assert _safe_get(None, '2024', ['Revenue']) is None

    def test_safe_get_with_empty_df(self):
        df = pd.DataFrame()
        assert _safe_get(df, '2024', ['Revenue']) is None

    def test_safe_get_fallback_keys(self):
        """Should try multiple keys and return first match."""
        df = pd.DataFrame({'2024': [100, 200]}, index=['TotalRevenue', 'Revenue'])
        result = _safe_get(df, '2024', ['NonExistent', 'Revenue'])
        assert result == 200.0

    def test_format_number(self):
        assert _format_number(3.14159) == 3.14
        assert _format_number(None) is None

    def test_format_ratio(self):
        assert _format_ratio(0.123456789) == 0.123457
        assert _format_ratio(None) is None


class TestSectorDetection:
    """Tests for financial sector detection."""

    def test_bank_detection(self):
        assert _get_financial_subsector('Financial Services', 'Banks—Regional') == 'bank'

    def test_insurance_detection(self):
        assert _get_financial_subsector('Financial Services', 'Insurance—Life') == 'insurance'

    def test_leasing_detection(self):
        assert _get_financial_subsector('Financial Services', 'Credit Services') == 'leasing'

    def test_securities_detection(self):
        assert _get_financial_subsector('Financial Services', 'Capital Markets') == 'securities'

    def test_real_estate_detection(self):
        assert _get_financial_subsector('Real Estate', 'REIT—Residential') == 'real_estate'

    def test_non_financial_returns_none(self):
        assert _get_financial_subsector('Technology', 'Software—Application') is None

    def test_is_financial_sector_bank(self):
        assert _is_financial_sector('Financial Services', 'Banks—Regional') is True

    def test_is_financial_not_real_estate(self):
        assert _is_financial_sector('Real Estate', 'REIT') is False

    def test_is_financial_non_financial(self):
        assert _is_financial_sector('Technology', 'Software') is False
