"""
Centralized Configuration & Logging Setup
All environment variables and application settings in one place.
"""

import os
import logging
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Application configuration loaded from environment variables."""

    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY', os.urandom(32).hex())
    DEBUG = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'

    # API Keys
    FMP_API_KEY = os.getenv('FMP_API_KEY')
    ALPHA_VANTAGE_API_KEY = os.getenv('ALPHA_VANTAGE_API_KEY')
    SIMFIN_API_KEY = os.getenv('SIMFIN_API_KEY')
    GOAPI_API_KEY = os.getenv('GOAPI_API_KEY')
    GOAPI_API_KEY_2 = os.getenv('GOAPI_API_KEY_2')
    SECTORS_API_KEY = os.getenv('SECTORS_API_KEY')

    # CORS — comma-separated origins, or '*' for development
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', '*').split(',')

    # Cache TTL in seconds (default 5 minutes)
    CACHE_TTL = int(os.getenv('CACHE_TTL', '300'))
    CACHE_MAX_SIZE = int(os.getenv('CACHE_MAX_SIZE', '64'))

    # Rate Limiting
    RATE_LIMIT_DEFAULT = os.getenv('RATE_LIMIT', '60/minute')
    RATE_LIMIT_SCRAPE = os.getenv('RATE_LIMIT_SCRAPE', '20/minute')

    # External API Timeouts (seconds)
    REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', '10'))

    # Server
    HOST = os.getenv('HOST', '0.0.0.0')
    PORT = int(os.getenv('PORT', '5000'))


def setup_logging(level=None):
    """
    Configure structured logging for the entire application.
    Call once at startup; all modules use logging.getLogger(__name__).
    """
    log_level = level or (logging.DEBUG if Config.DEBUG else logging.INFO)

    logging.basicConfig(
        level=log_level,
        format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )

    # Quiet noisy third-party loggers
    logging.getLogger('yfinance').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('peewee').setLevel(logging.WARNING)
