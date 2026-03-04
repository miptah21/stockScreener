"""
Financial Data Scraper — Flask Application
Serves the dashboard and provides API endpoints for financial data.
Supports Yahoo Finance with WSJ Markets as fallback.
"""

import logging

from flask import Flask, jsonify
from flask_cors import CORS
from flask_compress import Compress

from config import Config, setup_logging

logger = logging.getLogger(__name__)


# ─── Application Factory ─────────────────────────────────────────────

def create_app(config_class=Config):
    """Create and configure the Flask application."""
    setup_logging()

    app = Flask(__name__)
    app.config.from_object(config_class)

    # CORS
    CORS(app, origins=config_class.CORS_ORIGINS)

    # Response Compression (gzip/brotli)
    Compress(app)

    # Rate Limiting (optional — requires flask-limiter)
    try:
        from flask_limiter import Limiter
        from flask_limiter.util import get_remote_address
        limiter = Limiter(
            get_remote_address,
            app=app,
            default_limits=[config_class.RATE_LIMIT_DEFAULT],
            storage_uri="memory://",
        )
        logger.info("Rate limiting enabled: %s", config_class.RATE_LIMIT_DEFAULT)
    except ImportError:
        limiter = None
        logger.warning("flask-limiter not installed — rate limiting disabled")

    # ─── Security Headers ─────────────────────────────────────────
    @app.after_request
    def add_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        return response

    # ─── Error Handlers ───────────────────────────────────────────
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({'success': False, 'error': 'Endpoint not found'}), 404

    @app.errorhandler(429)
    def rate_limited(e):
        return jsonify({'success': False, 'error': 'Rate limit exceeded. Please slow down.'}), 429

    @app.errorhandler(500)
    def internal_error(e):
        logger.exception("Internal server error")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

    # ─── Health Check ─────────────────────────────────────────────
    @app.route('/health')
    def health():
        return jsonify({'status': 'ok'}), 200

    # ─── Register Blueprints ──────────────────────────────────────
    from routes.pages import pages_bp
    from routes.api_data import api_data_bp
    from routes.api_screeners import api_screeners_bp

    app.register_blueprint(pages_bp)
    app.register_blueprint(api_data_bp)
    app.register_blueprint(api_screeners_bp)

    return app


# ─── Entry Point ──────────────────────────────────────────────────────

app = create_app()

if __name__ == '__main__':
    app.run(debug=Config.DEBUG, host=Config.HOST, port=Config.PORT)
