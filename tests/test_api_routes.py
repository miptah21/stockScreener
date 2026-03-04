"""
Test suite for Flask API routes — smoke tests and input validation.
"""

import json
import pytest


class TestHealthEndpoint:
    """Tests for /health endpoint."""

    def test_health_returns_200(self, client):
        resp = client.get('/health')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['status'] == 'ok'


class TestPageRoutes:
    """Tests for HTML page routes."""

    def test_index_page(self, client):
        resp = client.get('/')
        assert resp.status_code == 200

    def test_screening_page(self, client):
        resp = client.get('/screening')
        assert resp.status_code == 200

    def test_avg_price_page(self, client):
        resp = client.get('/avg-price')
        assert resp.status_code == 200

    def test_ownership_page(self, client):
        resp = client.get('/ownership')
        assert resp.status_code == 200

    def test_technical_screening_page(self, client):
        resp = client.get('/technical-screening')
        assert resp.status_code == 200

    def test_simple_screening_page(self, client):
        resp = client.get('/simple-screening')
        assert resp.status_code == 200

    def test_watchlist_page(self, client):
        resp = client.get('/watchlist')
        assert resp.status_code == 200

    def test_market_overview_page(self, client):
        resp = client.get('/market-overview')
        assert resp.status_code == 200


class TestApiInputValidation:
    """Tests for API input validation — no external calls."""

    def test_scrape_missing_ticker(self, client):
        resp = client.get('/api/scrape')
        assert resp.status_code == 400

    def test_scrape_invalid_ticker(self, client):
        resp = client.get('/api/scrape?ticker=<script>')
        assert resp.status_code == 400

    def test_scrape_invalid_year(self, client):
        resp = client.get('/api/scrape?ticker=BBCA.JK&year=abc')
        assert resp.status_code == 400

    def test_history_missing_ticker(self, client):
        resp = client.get('/api/history')
        assert resp.status_code == 400

    def test_avg_price_missing_ticker(self, client):
        resp = client.get('/api/avg-price')
        assert resp.status_code == 400

    def test_bandarmology_missing_ticker(self, client):
        resp = client.get('/api/bandarmology')
        assert resp.status_code == 400

    def test_bandarmology_missing_date(self, client):
        resp = client.get('/api/bandarmology?ticker=BBCA')
        assert resp.status_code == 400

    def test_ownership_missing_ticker(self, client):
        resp = client.get('/api/ownership')
        assert resp.status_code == 400

    def test_screen_missing_list(self, client):
        resp = client.get('/api/screen')
        assert resp.status_code == 400

    def test_technical_screen_missing_list(self, client):
        resp = client.post(
            '/api/technical-screen',
            data=json.dumps({}),
            content_type='application/json'
        )
        assert resp.status_code == 400

    def test_simple_screen_missing_list(self, client):
        resp = client.post(
            '/api/simple-screen',
            data=json.dumps({}),
            content_type='application/json'
        )
        assert resp.status_code == 400


class TestApiStockLists:
    """Tests for /api/stock-lists endpoint."""

    def test_stock_lists_returns_200(self, client):
        resp = client.get('/api/stock-lists')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert 'lists' in data
        assert isinstance(data['lists'], dict)

    def test_stock_lists_has_idx_lq45(self, client):
        resp = client.get('/api/stock-lists')
        data = resp.get_json()
        assert 'idx_lq45' in data['lists']


class TestErrorHandlers:
    """Tests for error handlers."""

    def test_404_json_response(self, client):
        resp = client.get('/api/nonexistent')
        assert resp.status_code == 404
        data = resp.get_json()
        assert data['success'] is False
