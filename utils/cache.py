"""
Cache Utility Module
Provides a unified TTL cache interface.
Currently in-memory (cachetools); swappable to Redis for horizontal scaling.
"""

import logging
from functools import wraps
from cachetools import TTLCache

logger = logging.getLogger(__name__)


# ─── Default Caches ───────────────────────────────────────────────
# Scraper results cache (ticker → financial data)
scraper_cache = TTLCache(maxsize=200, ttl=900)  # 15 min

# Screener results cache (list_key → screening results)
screener_cache = TTLCache(maxsize=50, ttl=600)  # 10 min

# Stock lists metadata cache (static, long TTL)
stock_lists_cache = TTLCache(maxsize=1, ttl=3600)  # 1 hour


def cached(cache_instance, key_func=None):
    """
    Decorator for caching function results with TTL.

    Args:
        cache_instance: A TTLCache instance to store results.
        key_func: Optional callable(args, kwargs) -> cache key.
                  Defaults to first positional arg.

    Usage:
        @cached(scraper_cache)
        def get_financials(ticker): ...

        @cached(screener_cache, key_func=lambda a, kw: a[0])
        def run_screen(list_key, ...): ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if key_func:
                key = key_func(args, kwargs)
            elif args:
                key = str(args[0])
            else:
                key = func.__name__

            if key in cache_instance:
                logger.debug("Cache HIT for %s (key=%s)", func.__name__, key)
                return cache_instance[key]

            logger.debug("Cache MISS for %s (key=%s)", func.__name__, key)
            result = func(*args, **kwargs)
            cache_instance[key] = result
            return result
        return wrapper
    return decorator


def clear_all():
    """Clear all caches. Useful for testing or forced refresh."""
    scraper_cache.clear()
    screener_cache.clear()
    stock_lists_cache.clear()
    logger.info("All caches cleared")
