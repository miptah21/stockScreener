"""
Test suite for scrapers/ojk.py — OJK bank ratios loaded from JSON.
"""

import json
import os
import pytest

from scrapers.ojk import (
    get_bank_ratios, get_available_tickers,
    BANK_NAMES, CACHED_RATIOS, format_ratios_report,
)


class TestOjkDataLoading:
    """Tests for loading bank data from JSON file."""

    def test_bank_names_loaded(self):
        assert BANK_NAMES is not None
        assert isinstance(BANK_NAMES, dict)
        assert len(BANK_NAMES) >= 10

    def test_cached_ratios_loaded(self):
        assert CACHED_RATIOS is not None
        assert isinstance(CACHED_RATIOS, dict)
        assert len(CACHED_RATIOS) >= 10

    def test_bank_names_have_jk_suffix(self):
        for ticker in BANK_NAMES:
            assert ticker.endswith('.JK'), f"{ticker} missing .JK suffix"

    def test_known_banks_present(self):
        expected = ['BBCA.JK', 'BBRI.JK', 'BMRI.JK', 'BBNI.JK', 'BBTN.JK']
        for ticker in expected:
            assert ticker in BANK_NAMES, f"Missing bank: {ticker}"
            assert ticker in CACHED_RATIOS, f"Missing ratio data for: {ticker}"


class TestGetBankRatios:
    """Tests for the get_bank_ratios function."""

    def test_known_bank_returns_data(self):
        result = get_bank_ratios('BBCA.JK')
        assert result is not None
        assert isinstance(result, dict)

    def test_result_has_required_fields(self):
        result = get_bank_ratios('BBCA.JK')
        assert result is not None
        for field in ['casa', 'npl', 'car', 'ldr', 'nim', 'bopo', 'source']:
            assert field in result, f"Missing field: {field}"

    def test_unknown_ticker_returns_none(self):
        result = get_bank_ratios('ZZZZ.JK')
        assert result is None

    def test_ticker_normalization(self):
        """Tickers without .JK should be normalized."""
        result = get_bank_ratios('BBCA')
        assert result is not None

    def test_specific_year(self):
        result = get_bank_ratios('BBCA.JK', year=2025)
        if result:
            assert result.get('year') == 2025

    def test_empty_ticker_returns_none(self):
        assert get_bank_ratios('') is None
        assert get_bank_ratios(None) is None


class TestGetAvailableTickers:
    """Tests for the get_available_tickers function."""

    def test_returns_list(self):
        result = get_available_tickers()
        assert isinstance(result, list)
        assert len(result) >= 10

    def test_tickers_have_jk_suffix(self):
        for ticker in get_available_tickers():
            assert ticker.endswith('.JK')


class TestFormatReport:
    """Tests for the format_ratios_report function."""

    def test_format_none(self):
        assert format_ratios_report(None) == "No data available"

    def test_format_valid_ratios(self):
        ratios = {'casa': 0.85, 'npl': 0.017, 'source': 'Test', 'year': 2025}
        result = format_ratios_report(ratios)
        assert 'CASA' in result
        assert '85.00%' in result


class TestJsonDataIntegrity:
    """Verify the bank_ratios.json file structure."""

    def test_json_file_exists(self):
        json_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'data', 'bank_ratios.json'
        )
        assert os.path.exists(json_path), "bank_ratios.json not found"

    def test_json_is_valid(self):
        json_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'data', 'bank_ratios.json'
        )
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        assert 'bank_names' in data
        assert 'ratios' in data
        assert '_meta' in data

    def test_ratio_values_are_decimal(self):
        """All ratio values should be decimals (0-1), not percentages (0-100)."""
        for ticker, years in CACHED_RATIOS.items():
            for year, ratios in years.items():
                for key in ['casa', 'npl', 'car', 'ldr', 'nim', 'bopo', 'coc']:
                    val = ratios.get(key)
                    if val is not None:
                        assert 0 <= val <= 1.5, (
                            f"{ticker} {year} {key}={val} looks like a percentage, not a decimal"
                        )
