"""
Page Routes — Serves HTML templates for all pages.
"""

from flask import Blueprint, render_template

pages_bp = Blueprint('pages', __name__)


@pages_bp.route('/')
def index():
    """Serve the main dashboard page."""
    return render_template('index.html', active_page='dashboard')


@pages_bp.route('/screening')
def screening():
    """Serve the stock screening page."""
    return render_template('screening.html', active_page='screening')


@pages_bp.route('/avg-price')
def avg_price_page():
    """Serve the stock average price (FCA) page."""
    return render_template('avg_price.html', active_page='avg-price')


@pages_bp.route('/ownership')
def ownership_page():
    """Serve the Ownership Summary page."""
    return render_template('ownership.html', active_page='ownership')


@pages_bp.route('/technical-screening')
def technical_screening_page():
    """Serve the Technical Analysis Screening page."""
    return render_template('technical_screening.html', active_page='technical')


@pages_bp.route('/simple-screening')
def simple_screening_page():
    """Serve the Simple RSI & MACD Screening page."""
    return render_template('simple_screening.html', active_page='simple')


@pages_bp.route('/watchlist')
def watchlist_page():
    """Serve the Watchlist & Portfolio page."""
    return render_template('watchlist.html', active_page='watchlist')


@pages_bp.route('/market-overview')
def market_overview_page():
    """Serve the Market Overview Dashboard page."""
    return render_template('market_overview.html', active_page='market')


@pages_bp.route('/backtest')
def backtest_page():
    """Serve the Backtesting Engine page."""
    return render_template('backtest.html', active_page='backtest')

