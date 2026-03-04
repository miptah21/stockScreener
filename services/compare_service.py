"""
Compare Service — Side-by-side comparative analysis for multiple stocks.
Uses yf.download() for batch price history and scrape_financials() for fundamentals.
"""

import logging
import math
from concurrent.futures import ThreadPoolExecutor, as_completed

import yfinance as yf
import pandas as pd

from scrapers.yahoo import scrape_financials

logger = logging.getLogger(__name__)

# ─── Constants ───────────────────────────────────────────────────────

# Radar chart dimensions (6 axes)
RADAR_AXES = ['Profitability', 'Growth', 'Efficiency', 'Leverage', 'Quality', 'Valuation']

# Color palette for up to 5 tickers
COLORS = [
    {'bg': 'rgba(99, 102, 241, 0.2)',  'border': '#6366f1'},   # indigo
    {'bg': 'rgba(16, 185, 129, 0.2)',  'border': '#10b981'},   # emerald
    {'bg': 'rgba(244, 63, 94, 0.2)',   'border': '#f43f5e'},   # rose
    {'bg': 'rgba(245, 158, 11, 0.2)',  'border': '#f59e0b'},   # amber
    {'bg': 'rgba(34, 211, 238, 0.2)',  'border': '#22d3ee'},   # cyan
]

# Comparison metrics config: (key, label, format, higher_is_better)
GENERAL_METRICS = [
    ('market_cap',       'Market Cap',         'number',  True),
    ('current_price',    'Current Price',      'price',   None),
    ('pe_ratio',         'P/E Ratio',          'ratio',   False),
    ('pb_ratio',         'P/B Ratio',          'ratio',   False),
    ('dividend_yield',   'Dividend Yield',     'pct',     True),
    ('roa',              'ROA',                'pct',     True),
    ('roe',              'ROE',                'pct',     True),
    ('net_margin',       'Net Margin',         'pct',     True),
    ('gross_margin',     'Gross Margin',       'pct',     True),
    ('asset_turnover',   'Asset Turnover',     'ratio',   True),
    ('current_ratio',    'Current Ratio',      'ratio',   True),
    ('der',              'Debt/Equity',        'ratio',   False),
    ('revenue',          'Revenue',            'number',  True),
    ('net_income',       'Net Income',         'number',  True),
    ('operating_cf',     'Operating Cash Flow','number',  True),
    ('piotroski',        'Piotroski F-Score',  'score',   True),
]

BANK_METRICS = [
    ('market_cap',       'Market Cap',         'number',  True),
    ('current_price',    'Current Price',      'price',   None),
    ('pe_ratio',         'P/E Ratio',          'ratio',   False),
    ('pb_ratio',         'P/B Ratio',          'ratio',   False),
    ('dividend_yield',   'Dividend Yield',     'pct',     True),
    ('roa',              'ROA',                'pct',     True),
    ('roe',              'ROE',                'pct',     True),
    ('nim',              'NIM',                'pct',     True),
    ('bopo',             'BOPO',               'pct',     False),
    ('cost_of_funds',    'Cost of Funds',      'pct',     False),
    ('der',              'Debt/Equity',        'ratio',   False),
    ('revenue',          'Revenue',            'number',  True),
    ('net_income',       'Net Income',         'number',  True),
    ('operating_cf',     'Operating Cash Flow','number',  True),
    ('piotroski',        'Bank Quality Score', 'score',   True),
]


# ─── Helper Functions ────────────────────────────────────────────────

def _safe_float(val, default=None):
    """Safely convert to float."""
    if val is None:
        return default
    try:
        f = float(val)
        return default if (math.isnan(f) or math.isinf(f)) else f
    except (ValueError, TypeError):
        return default


def _normalize_to_100(series: pd.Series) -> list:
    """Normalize a price series so the first valid value = 100."""
    if series.empty:
        return []
        
    # Drop all NaN values to find the first valid trading price
    valid_series = series.dropna()
    if valid_series.empty:
        return []
        
    first = valid_series.iloc[0]
    if first == 0:
        return []
        
    normalized = (series / first) * 100
    return [round(v, 2) if not pd.isna(v) else None for v in normalized]


def _compute_revenue_growth(data_list: list) -> float | None:
    """Compute YoY revenue growth from scrape_financials data."""
    if len(data_list) < 2:
        return None
    curr_rev = _safe_float(data_list[0].get('raw', {}).get('total_revenue'))
    prev_rev = _safe_float(data_list[1].get('raw', {}).get('total_revenue'))
    if curr_rev is None or prev_rev is None or prev_rev == 0:
        return None
    return (curr_rev - prev_rev) / abs(prev_rev)


def _clamp(val, lo=0, hi=100):
    """Clamp a value to [lo, hi]."""
    if val is None:
        return 0
    return max(lo, min(hi, val))


# ─── Main Compare Function ──────────────────────────────────────────

def compare_stocks(tickers: list[str]) -> dict:
    """
    Compare 2-5 stocks side-by-side.

    Returns:
        {
            success: bool,
            tickers_data: [ { ticker, name, sector, industry, ... } ],
            price_performance: { labels: [...], datasets: [...] },
            radar_data: { labels: [...], datasets: [...] },
            comparison_table: [ { key, label, format, higher_is_better, values: {ticker: val} } ],
            colors: [ {bg, border} ]
        }
    """
    if not tickers or len(tickers) < 2:
        return {'success': False, 'error': 'At least 2 tickers are required.'}
    if len(tickers) > 5:
        return {'success': False, 'error': 'Maximum 5 tickers allowed.'}

    # Clean tickers
    tickers = [t.strip().upper() for t in tickers]

    # ─── 1. Fetch fundamentals in parallel ────────────────────────
    fundamentals = {}
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_map = {executor.submit(scrape_financials, t): t for t in tickers}
        for future in as_completed(future_map):
            t = future_map[future]
            try:
                result = future.result()
                if result and result.get('success'):
                    fundamentals[t] = result
                else:
                    fundamentals[t] = None
                    logger.warning("Failed to fetch fundamentals for %s: %s",
                                   t, result.get('error', 'Unknown') if result else 'None')
            except Exception as e:
                fundamentals[t] = None
                logger.error("Exception fetching %s: %s", t, e)

    # Check that at least 2 tickers succeeded
    valid_tickers = [t for t in tickers if fundamentals.get(t)]
    if len(valid_tickers) < 2:
        return {'success': False, 'error': 'Could not fetch data for enough tickers. Need at least 2.'}

    # ─── 2. Fetch price history (batch download) ─────────────────
    price_performance = _get_price_performance(valid_tickers)

    # ─── 3. Extract ticker info ──────────────────────────────────
    tickers_data = []
    all_bank = True
    for t in valid_tickers:
        fd = fundamentals[t]
        company = fd.get('company', {})
        is_bank = fd.get('is_bank', False)
        if not is_bank:
            all_bank = False

        # Get info values from yfinance for P/E, P/B, div yield
        info_data = _get_ticker_info(t)

        tickers_data.append({
            'ticker': t,
            'name': company.get('name', t),
            'sector': company.get('sector', 'N/A'),
            'industry': company.get('industry', 'N/A'),
            'currency': company.get('currency', 'USD'),
            'market_cap': company.get('market_cap'),
            'current_price': company.get('current_price'),
            'is_bank': is_bank,
            'pe_ratio': info_data.get('pe_ratio'),
            'pb_ratio': info_data.get('pb_ratio'),
            'dividend_yield': info_data.get('dividend_yield'),
        })

    # ─── 4. Build comparison table ───────────────────────────────
    metrics_config = BANK_METRICS if all_bank else GENERAL_METRICS
    comparison_table = _build_comparison_table(valid_tickers, fundamentals, tickers_data, metrics_config)

    # ─── 5. Build radar chart data ───────────────────────────────
    radar_data = _build_radar_data(valid_tickers, fundamentals, tickers_data)

    return {
        'success': True,
        'tickers_data': tickers_data,
        'price_performance': price_performance,
        'radar_data': radar_data,
        'comparison_table': comparison_table,
        'colors': COLORS[:len(valid_tickers)],
    }


# ─── Price Performance ───────────────────────────────────────────────

def _get_price_performance(tickers: list[str]) -> dict:
    """Download batch price data and normalize to 100."""
    try:
        df = yf.download(tickers, period='1y', progress=False, threads=True)
        if df.empty:
            return {'labels': [], 'datasets': []}

        # Handle multi-ticker columns: ('Close', 'BBCA.JK'), ('Close', 'BBRI.JK'), etc.
        if isinstance(df.columns, pd.MultiIndex):
            close = df['Close']
        else:
            # Single ticker fallback
            close = df[['Close']].rename(columns={'Close': tickers[0]})

        # Generate date labels
        labels = [d.strftime('%Y-%m-%d') for d in close.index]

        datasets = []
        for i, t in enumerate(tickers):
            if t in close.columns:
                series = close[t].dropna()
                if not series.empty:
                    # Reindex to match the full index so labels align
                    full_series = close[t]
                    normalized = _normalize_to_100(full_series)
                    color = COLORS[i % len(COLORS)]
                    datasets.append({
                        'label': t,
                        'data': normalized,
                        'borderColor': color['border'],
                        'backgroundColor': color['bg'],
                        'borderWidth': 2,
                        'pointRadius': 0,
                        'tension': 0.3,
                        'fill': False,
                    })

        return {'labels': labels, 'datasets': datasets}

    except Exception as e:
        logger.error("Error fetching price performance: %s", e)
        return {'labels': [], 'datasets': []}


# ─── Ticker Info (P/E, P/B, Div Yield) ───────────────────────────────

def _get_ticker_info(ticker: str) -> dict:
    """Fetch P/E, P/B, dividend yield from yfinance info."""
    try:
        info = yf.Ticker(ticker).info or {}
        return {
            'pe_ratio': _safe_float(info.get('trailingPE', info.get('forwardPE'))),
            'pb_ratio': _safe_float(info.get('priceToBook')),
            'dividend_yield': _safe_float(info.get('dividendYield')),
        }
    except Exception:
        return {'pe_ratio': None, 'pb_ratio': None, 'dividend_yield': None}


# ─── Comparison Table Builder ────────────────────────────────────────

def _build_comparison_table(tickers, fundamentals, tickers_data, metrics_config):
    """Build the side-by-side metrics comparison table."""
    # Create lookup for ticker info data
    info_lookup = {td['ticker']: td for td in tickers_data}

    table = []
    for key, label, fmt, higher_is_better in metrics_config:
        row = {
            'key': key,
            'label': label,
            'format': fmt,
            'higher_is_better': higher_is_better,
            'values': {},
        }

        for t in tickers:
            val = _extract_metric(t, key, fundamentals, info_lookup)
            row['values'][t] = val

        # Determine best/worst for color coding
        # For certain metrics where lower is better (e.g., P/E ratio, DER), filter out negative 
        # values before finding the "best" so that negative P/E or DER isn't marked as best.
        numeric_vals = {t: v for t, v in row['values'].items() if v is not None and isinstance(v, (int, float))}
        
        if numeric_vals and higher_is_better is not None:
            if higher_is_better:
                # Higher is better (e.g. ROA, Margin)
                best_ticker = max(numeric_vals, key=numeric_vals.get)
                worst_ticker = min(numeric_vals, key=numeric_vals.get)
            else:
                # Lower is better (e.g. P/E, P/B, BOPO, DER)
                # Exclude negative values when looking for the 'best' (minimum positive value)
                positive_numeric_vals = {t: v for t, v in numeric_vals.items() if v > 0}
                
                # Best is the lowest valid (positive) value
                if positive_numeric_vals:
                    best_ticker = min(positive_numeric_vals, key=positive_numeric_vals.get)
                else: 
                    best_ticker = None
                    
                # Worst is the highest value (or the lowest negative value if all are negative)
                worst_ticker = max(numeric_vals, key=numeric_vals.get) 
                
                # If there are negative values, they are worse than any positive value.
                # So the one with the lowest negative value is truly the worst.
                neg_vals = {t: v for t, v in numeric_vals.items() if v < 0}
                if neg_vals:
                    worst_ticker = min(neg_vals, key=neg_vals.get)

            row['best'] = best_ticker
            row['worst'] = worst_ticker if len(numeric_vals) > 1 else None
        else:
            row['best'] = None
            row['worst'] = None

        table.append(row)

    return table


def _extract_metric(ticker, key, fundamentals, info_lookup):
    """Extract a single metric value for a given ticker."""
    fd = fundamentals.get(ticker)
    info = info_lookup.get(ticker, {})

    if fd is None:
        return None

    latest = fd.get('data', [{}])[0] if fd.get('data') else {}
    metrics = latest.get('metrics', {})
    raw = latest.get('raw', {})

    # Direct info fields
    if key == 'market_cap':
        return _safe_float(fd.get('company', {}).get('market_cap'))
    elif key == 'current_price':
        return _safe_float(fd.get('company', {}).get('current_price'))
    elif key == 'pe_ratio':
        return info.get('pe_ratio')
    elif key == 'pb_ratio':
        return info.get('pb_ratio')
    elif key == 'dividend_yield':
        return info.get('dividend_yield')
    elif key == 'piotroski':
        pio = fd.get('piotroski', {})
        return _safe_float(pio.get('score'))

    # Metrics from scrape_financials
    elif key == 'roa':
        return _safe_float(metrics.get('roa'))
    elif key == 'roe':
        return _safe_float(metrics.get('roe'))
    elif key == 'net_margin':
        return _safe_float(metrics.get('net_margin'))
    elif key == 'gross_margin':
        return _safe_float(metrics.get('gross_margin'))
    elif key == 'asset_turnover':
        return _safe_float(metrics.get('asset_turnover'))
    elif key == 'current_ratio':
        return _safe_float(metrics.get('current_ratio'))
    elif key == 'der':
        return _safe_float(metrics.get('der'))
    elif key == 'nim':
        return _safe_float(metrics.get('nim'))
    elif key == 'bopo':
        return _safe_float(metrics.get('bopo'))
    elif key == 'cost_of_funds':
        return _safe_float(metrics.get('cost_of_funds'))

    # Raw financials
    elif key == 'revenue':
        return _safe_float(raw.get('total_revenue'))
    elif key == 'net_income':
        return _safe_float(raw.get('net_income'))
    elif key == 'operating_cf':
        return _safe_float(raw.get('operating_cashflow'))

    return None


# ─── Radar Chart Builder ─────────────────────────────────────────────

def _build_radar_data(tickers, fundamentals, tickers_data):
    """
    Build radar chart data with 6 axes:
    Profitability (ROA), Growth (Revenue YoY), Efficiency (Asset Turnover),
    Leverage (DER inverted), Quality (Piotroski), Valuation (P/E inverted).
    All normalized to 0-100 scale.
    """
    info_lookup = {td['ticker']: td for td in tickers_data}

    datasets = []
    for i, t in enumerate(tickers):
        fd = fundamentals.get(t)
        if not fd:
            continue

        latest = fd.get('data', [{}])[0] if fd.get('data') else {}
        metrics = latest.get('metrics', {})
        data_list = fd.get('data', [])
        info = info_lookup.get(t, {})

        # 1. Profitability: ROA (typical range -0.1 to 0.3 → scale to 0-100)
        roa = _safe_float(metrics.get('roa'), 0)
        profitability = _clamp((roa + 0.05) / 0.30 * 100)

        # 2. Growth: Revenue YoY growth (-50% to +50% → 0-100)
        growth_raw = _compute_revenue_growth(data_list)
        growth = _clamp(((growth_raw or 0) + 0.5) / 1.0 * 100)

        # 3. Efficiency: Asset Turnover (0 to 2 → 0-100)
        at = _safe_float(metrics.get('asset_turnover'), 0)
        efficiency = _clamp(at / 2.0 * 100)

        # 4. Leverage: DER inverted (lower is better: 0 to 5 → 100 to 0)
        der = _safe_float(metrics.get('der'), 1)
        leverage = _clamp((1 - der / 5.0) * 100)

        # 5. Quality: Piotroski F-Score (0 to 9/11 → 0-100)
        pio = fd.get('piotroski', {})
        pio_score = _safe_float(pio.get('score'), 0)
        pio_max = _safe_float(pio.get('max_score'), 9)
        quality = _clamp(pio_score / max(pio_max, 1) * 100)

        # 6. Valuation: P/E inverted (lower P/E = better: 0~50 → 100~0)
        pe = info.get('pe_ratio')
        if pe and pe > 0:
            valuation = _clamp((1 - pe / 50.0) * 100)
        else:
            valuation = 50  # default neutral

        color = COLORS[i % len(COLORS)]
        datasets.append({
            'label': t,
            'data': [
                round(profitability, 1),
                round(growth, 1),
                round(efficiency, 1),
                round(leverage, 1),
                round(quality, 1),
                round(valuation, 1),
            ],
            'borderColor': color['border'],
            'backgroundColor': color['bg'],
            'borderWidth': 2,
            'pointBackgroundColor': color['border'],
            'pointRadius': 4,
        })

    return {
        'labels': RADAR_AXES,
        'datasets': datasets,
    }
