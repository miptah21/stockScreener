"""
Page Routes — All pages served via Jinja2 templates.
"""

from flask import Blueprint, render_template

pages_bp = Blueprint('pages', __name__)


# ── Page Routes (Jinja2 Templates) ───────────────────────────────────

@pages_bp.route('/')
def dashboard_page():
    """Serve the Dashboard page."""
    return render_template('index.html', active_page='dashboard')


@pages_bp.route('/screening')
def screening_page():
    """Serve the Fundamental Screening page."""
    return render_template('screening.html', active_page='screening')


@pages_bp.route('/technical-screening')
def technical_screening_page():
    """Serve the Technical Screening page."""
    return render_template('technical_screening.html', active_page='technical')


@pages_bp.route('/simple-screening')
def simple_screening_page():
    """Serve the RSI & MACD Screening page."""
    return render_template('simple_screening.html', active_page='simple')


@pages_bp.route('/avg-price')
def avg_price_page():
    """Serve the Average Price page."""
    return render_template('avg_price.html', active_page='avg-price')


@pages_bp.route('/ownership')
def ownership_page():
    """Serve the Ownership page."""
    return render_template('ownership.html', active_page='ownership')


@pages_bp.route('/watchlist')
def watchlist_page():
    """Serve the Watchlist page."""
    return render_template('watchlist.html', active_page='watchlist')


@pages_bp.route('/market-overview')
def market_overview_page():
    """Serve the Market Overview page."""
    return render_template('market_overview.html', active_page='market')


@pages_bp.route('/backtest')
def backtest_page():
    """Serve the Backtest page."""
    return render_template('backtest.html', active_page='backtest')


@pages_bp.route('/sentiment')
def sentiment_page():
    """Serve the Sentiment page."""
    return render_template('sentiment.html', active_page='sentiment')


@pages_bp.route('/compare')
def compare_page():
    """Serve the Comparative Analysis page."""
    return render_template('compare.html', active_page='compare')


@pages_bp.route('/pattern-recognition')
def pattern_recognition_page():
    """Serve the Pattern Recognition page."""
    return render_template('pattern_recognition.html', active_page='patterns')


@pages_bp.route('/idx-ownership')
def idx_ownership_page():
    """Serve the IDX Shareholder page."""
    return render_template('idx_ownership.html', active_page='idx-ownership')


@pages_bp.route('/idx-tracker')
def idx_tracker_page():
    """Serve the IDX Ownership Change Tracker page."""
    return render_template('idx_tracker.html', active_page='idx-tracker')
