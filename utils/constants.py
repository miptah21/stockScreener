"""
Shared constants for the Stock Screener application.
Single source of truth for values used across multiple modules.
"""

# ─── Market Cap Presets (IDR) ─────────────────────────────────────────
MARKET_CAP_PRESETS = {
    'all':       {'label': 'Semua',       'min': None,   'max': None},
    'micro':     {'label': 'Micro Cap',   'min': None,   'max': 1e12},
    'small':     {'label': 'Small Cap',   'min': 1e12,   'max': 10e12},
    'mid':       {'label': 'Mid Cap',     'min': 10e12,  'max': 50e12},
    'large':     {'label': 'Large Cap',   'min': 50e12,  'max': 200e12},
    'mega':      {'label': 'Mega Cap',    'min': 200e12, 'max': None},
}
