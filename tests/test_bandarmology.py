"""
Test suite for bandarmology error handling.
"""

import pytest
from scrapers.bandarmology import calculate_bandar_flow


class TestCalculateBandarFlow:
    """Tests for the calculate_bandar_flow function."""

    def test_empty_data_returns_no_data(self):
        result = calculate_bandar_flow(None)
        assert result['status'] == 'No Data'
        assert result['top_buyers'] == []
        assert result['top_sellers'] == []

    def test_empty_list_returns_no_data(self):
        result = calculate_bandar_flow([])
        assert result['status'] == 'No Data'

    def test_buy_side_accumulation(self):
        data = [
            {'broker': {'code': 'ZP', 'name': 'Morgan Stanley'}, 'side': 'BUY', 'value': 1000000, 'lot': 100, 'avg': 5000},
            {'broker': {'code': 'CC', 'name': 'Mandiri Sek'}, 'side': 'SELL', 'value': 100000, 'lot': 10, 'avg': 5100},
        ]
        result = calculate_bandar_flow(data)
        assert result['status'] in ('Big Accumulation', 'Accumulation')
        assert len(result['top_buyers']) >= 1
        assert result['top_buyers'][0]['code'] == 'ZP'

    def test_sell_side_distribution(self):
        data = [
            {'broker': {'code': 'ZP', 'name': 'Morgan Stanley'}, 'side': 'SELL', 'value': 1000000, 'lot': 100, 'avg': 5000},
            {'broker': {'code': 'CC', 'name': 'Mandiri Sek'}, 'side': 'BUY', 'value': 100000, 'lot': 10, 'avg': 5100},
        ]
        result = calculate_bandar_flow(data)
        assert result['status'] in ('Big Distribution', 'Distribution')
        assert len(result['top_sellers']) >= 1
        assert result['top_sellers'][0]['code'] == 'ZP'

    def test_neutral_when_balanced(self):
        data = [
            {'broker': {'code': 'ZP', 'name': 'Morgan Stanley'}, 'side': 'BUY', 'value': 100, 'lot': 1, 'avg': 100},
            {'broker': {'code': 'CC', 'name': 'Mandiri Sek'}, 'side': 'SELL', 'value': 100, 'lot': 1, 'avg': 100},
        ]
        result = calculate_bandar_flow(data)
        assert result['status'] == 'Neutral'

    def test_summary_has_net_values(self):
        data = [
            {'broker': {'code': 'ZP', 'name': 'Test'}, 'side': 'BUY', 'value': 500, 'lot': 10, 'avg': 50},
        ]
        result = calculate_bandar_flow(data)
        assert 'top_1_net' in result['summary']
        assert 'top_3_net' in result['summary']
        assert 'top_5_net' in result['summary']

    def test_formatted_values_present(self):
        data = [
            {'broker': {'code': 'ZP', 'name': 'Test'}, 'side': 'BUY', 'value': 1000000, 'lot': 100, 'avg': 10000},
        ]
        result = calculate_bandar_flow(data)
        buyer = result['top_buyers'][0]
        assert 'formatted_value' in buyer
        assert 'formatted_lot' in buyer
        assert 'formatted_avg' in buyer
