"""
conftest.py — Shared pytest fixtures for the Finance Screener test suite.
"""

import pytest
from app import create_app


@pytest.fixture
def app():
    """Create a test Flask application."""
    app = create_app()
    app.config['TESTING'] = True
    return app


@pytest.fixture
def client(app):
    """Create a test HTTP client."""
    return app.test_client()
