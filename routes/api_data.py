"""
Data API Routes — Endpoints for fetching financial data, charts,
ownership, bandarmology, average price, market dates, market overview,
backtesting, and sentiment analysis.
"""

import re
import logging
import math
import statistics

import yfinance as yf
from flask import Blueprint, jsonify, request

from services.scraping_service import get_financials
from services.screening_service import get_stock_lists, screen_stocks
from services.market_service import get_market_overview
from services.backtest_service import run_backtest, run_optimization, run_walk_forward
from services.sentiment_service import get_sentiment_analysis
from scrapers.bandarmology import get_broker_summary, calculate_bandar_flow

logger = logging.getLogger(__name__)

# ─── Input Validation ────────────────────────────────────────────────
TICKER_PATTERN = re.compile(r'^[A-Za-z0-9.\-]{1,15}$')


def _validate_ticker(ticker: str) -> str | None:
    """Validate and sanitize ticker input. Returns cleaned ticker or None."""
    if not ticker or not isinstance(ticker, str):
        return None
    ticker = ticker.strip().upper()
    if not TICKER_PATTERN.match(ticker):
        return None
    return ticker

def _validate_multi_ticker(ticker_str: str) -> str | None:
    """Validate multiple comma-separated tickers."""
    if not ticker_str or not isinstance(ticker_str, str):
        return None
    tickers = [t.strip().upper() for t in ticker_str.split(',')]
    valid = []
    for t in tickers:
        if not TICKER_PATTERN.match(t):
            return None
        valid.append(t)
    return ','.join(valid)


api_data_bp = Blueprint('api_data', __name__)


@api_data_bp.route('/api/scrape', methods=['GET'])
def api_scrape():
    """
    API endpoint to scrape financial data.

    Query params:
        ticker (str): Stock ticker symbol (e.g., AAPL, BBCA.JK)
        year (int, optional): Target fiscal year for scoring (e.g. 2023).
                              If omitted, uses latest available data.
    """
    ticker = _validate_ticker(request.args.get('ticker'))
    if not ticker:
        return jsonify({'error': 'Valid ticker is required (letters, numbers, dots, hyphens only)'}), 400

    logger.info("Scrape request for %s", ticker)
    target_year = request.args.get('year')
    if target_year:
        try:
            target_year = int(target_year)
        except ValueError:
            return jsonify({'error': 'Year must be a number'}), 400

    freq = request.args.get('freq', 'annual').strip().lower()
    if freq not in ('annual', 'quarterly'):
        freq = 'annual'

    result = get_financials(ticker, target_year=target_year, freq=freq)

    if result.get('success'):
        return jsonify(result)
    else:
        return jsonify(result), 500


@api_data_bp.route('/api/stock-lists', methods=['GET'])
def api_stock_lists():
    """Return available stock lists for screening."""
    return jsonify({
        'success': True,
        'lists': get_stock_lists()
    })


@api_data_bp.route('/api/screen', methods=['GET', 'POST'])
def api_screen():
    """
    Screen stocks to find which ones published annual reports this year.

    GET Query params:
        list (str): Stock list key (e.g., 'idx_lq45', 'sp500_top50')

    POST JSON body:
        list (str): 'custom'
        tickers (list): List of ticker symbols
    """
    if request.method == 'POST':
        data = request.get_json() or {}
        list_key = data.get('list', 'custom')
        custom_tickers = data.get('tickers', [])
    else:
        list_key = request.args.get('list', '').strip()
        custom_tickers = request.args.get('tickers', '').split(',') if request.args.get('tickers') else []

    if not list_key:
        return jsonify({
            'success': False,
            'error': 'Parameter "list" is required.'
        }), 400

    result = screen_stocks(list_key, custom_tickers)

    if not result.get('success'):
        return jsonify(result), 400

    return jsonify(result)


@api_data_bp.route('/api/history', methods=['GET'])
def api_history():
    """
    Return historical price data for chart rendering.

    Query params:
        ticker (str): Stock ticker symbol
        period (str): Data period — 1mo, 3mo, 6mo, 1y, 5y (default: 6mo)
    """
    ticker_symbol = _validate_ticker(request.args.get('ticker'))
    if not ticker_symbol:
        return jsonify({'success': False, 'error': 'Valid ticker is required.'}), 400

    period = request.args.get('period', '6mo').strip()
    valid_periods = ['5d', '1mo', '3mo', '6mo', '1y', '2y', '5y', 'max']
    if period not in valid_periods:
        period = '6mo'

    try:
        ticker = yf.Ticker(ticker_symbol)
        hist = ticker.history(period=period)

        if hist.empty:
            return jsonify({'success': False, 'error': 'No historical data found.'}), 404

        dates = [d.strftime('%Y-%m-%d') for d in hist.index]
        closes = [round(float(c), 2) for c in hist['Close']]
        volumes = [int(v) for v in hist['Volume']]

        # Get currency info for display
        try:
            info = ticker.info or {}
            currency = info.get('currency', 'IDR')
        except Exception:
            currency = 'IDR'

        return jsonify({
            'success': True,
            'ticker': ticker_symbol,
            'period': period,
            'dates': dates,
            'closes': closes,
            'volumes': volumes,
            'currency': currency,
        })
    except Exception as e:
        logger.exception("Error fetching history for %s", ticker_symbol)
        return jsonify({'success': False, 'error': str(e)}), 500


@api_data_bp.route('/api/avg-price', methods=['GET'])
def api_avg_price():
    """
    Calculate average stock price over the last 6 months.

    Query params:
        ticker (str): Stock ticker symbol (e.g., BBCA.JK, AAPL)
    """
    ticker_symbol = _validate_ticker(request.args.get('ticker'))
    if not ticker_symbol:
        return jsonify({'success': False, 'error': 'Valid ticker is required.'}), 400

    try:
        ticker = yf.Ticker(ticker_symbol)
        hist = ticker.history(period='6mo')

        if hist.empty:
            return jsonify({'success': False, 'error': 'Tidak ada data historis untuk ticker ini.'}), 404

        closes = [round(float(c), 2) for c in hist['Close']]
        dates = [d.strftime('%Y-%m-%d') for d in hist.index]

        avg_price = round(statistics.mean(closes), 2)
        median_price = round(statistics.median(closes), 2)
        high_price = round(max(closes), 2)
        low_price = round(min(closes), 2)

        # Get current / latest price
        info = ticker.info or {}
        current_price = info.get('currentPrice') or info.get('regularMarketPrice') or closes[-1]
        current_price = round(float(current_price), 2)

        currency = info.get('currency', 'IDR')
        company_name = info.get('shortName') or info.get('longName') or ticker_symbol

        # Premium/Discount vs average
        if avg_price > 0:
            premium_discount_pct = round(((current_price - avg_price) / avg_price) * 100, 2)
        else:
            premium_discount_pct = 0

        return jsonify({
            'success': True,
            'ticker': ticker_symbol.upper(),
            'company_name': company_name,
            'currency': currency,
            'avg_price': avg_price,
            'median_price': median_price,
            'high_price': high_price,
            'low_price': low_price,
            'current_price': current_price,
            'premium_discount_pct': premium_discount_pct,
            'date_start': dates[0],
            'date_end': dates[-1],
            'total_days': len(dates),
            'dates': dates,
            'closes': closes,
        })
    except Exception as e:
        logger.exception("Error calculating avg price for %s", ticker_symbol)
        return jsonify({'success': False, 'error': str(e)}), 500


@api_data_bp.route('/api/bandarmology', methods=['GET'])
def api_bandarmology():
    """
    API endpoint to get Bandarmology analysis using range.

    Query params:
        ticker (str): Stock ticker (e.g., BBCA).
        start_date (str): Date in YYYY-MM-DD format.
        end_date (str): Date in YYYY-MM-DD format.
        date (str): Optional legacy param (treated as start=end).
    """
    ticker = _validate_ticker(request.args.get('ticker'))
    if not ticker:
        return jsonify({'error': 'Valid ticker is required'}), 400

    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    date = request.args.get('date')

    if date and not start_date:
        start_date = date
        end_date = date

    if not start_date:
        return jsonify({'error': 'Start Date is required'}), 400

    # GoAPI usually expects ticker without .JK for IDX
    ticker_clean = ticker.replace('.JK', '').upper()

    broker_data = get_broker_summary(ticker_clean, start_date, end_date)

    if isinstance(broker_data, dict) and 'error' in broker_data:
        return jsonify({'error': broker_data['error']}), 429 if 'Rate Limit' in broker_data['error'] else 400

    if broker_data is None:
        return jsonify({'error': f'Data broker tidak tersedia untuk {ticker_clean} pada tanggal tersebut. Pastikan tanggal adalah hari perdagangan.'}), 404

    analysis = calculate_bandar_flow(broker_data)

    return jsonify({
        'success': True,
        'ticker': ticker_clean,
        'start_date': start_date,
        'end_date': end_date or start_date,
        'data': analysis
    })


@api_data_bp.route('/api/market-date', methods=['GET'])
def api_market_date():
    """
    Get the last available trading date from Yahoo Finance.
    Useful for setting default date ranges.
    """
    try:
        # Use BBCA.JK as a reliable proxy for IDX market open days
        ticker = yf.Ticker("BBCA.JK")
        hist = ticker.history(period="5d")

        if not hist.empty:
            last_date = hist.index[-1].strftime('%Y-%m-%d')
            return jsonify({'success': True, 'date': last_date})

        return jsonify({'success': False, 'error': 'No market data found'}), 404

    except Exception as e:
        logger.exception("Error fetching market date")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_data_bp.route('/api/ownership', methods=['GET'])
def api_ownership():
    """
    Return ownership summary data for a stock.

    Query params:
        ticker (str): Stock ticker symbol (e.g., BBCA.JK, AAPL)
    """
    ticker_symbol = _validate_ticker(request.args.get('ticker'))
    if not ticker_symbol:
        return jsonify({'success': False, 'error': 'Valid ticker is required.'}), 400

    def safe_val(v):
        if v is None:
            return None
        try:
            f = float(v)
            return None if (math.isnan(f) or math.isinf(f)) else f
        except (ValueError, TypeError):
            return None

    try:
        ticker = yf.Ticker(ticker_symbol)
        info = ticker.info or {}

        company_name = info.get('shortName') or info.get('longName') or ticker_symbol
        current_price = info.get('currentPrice') or info.get('regularMarketPrice')
        currency = info.get('currency', 'IDR')
        sector = info.get('sector', 'N/A')
        industry = info.get('industry', 'N/A')

        # --- Ownership percentages from info ---
        insider_pct = info.get('heldPercentInsiders')
        institution_pct = info.get('heldPercentInstitutions')
        float_shares = info.get('floatShares')
        shares_outstanding = info.get('sharesOutstanding')

        # --- Major holders breakdown ---
        major_holders_data = {}
        try:
            mh = ticker.major_holders
            if mh is not None and not mh.empty:
                for _, row in mh.iterrows():
                    key = row.iloc[0] if len(row) > 1 else row.name
                    val = row.iloc[1] if len(row) > 1 else row.iloc[0]
                    if isinstance(key, str):
                        major_holders_data[key] = val
                    else:
                        major_holders_data[str(row.name)] = float(val) if val is not None else None
        except Exception:
            pass

        # Normalize: try to read from major_holders dict or fall back to info
        if not major_holders_data:
            major_holders_data = {
                'insidersPercentHeld': insider_pct,
                'institutionsPercentHeld': institution_pct,
                'institutionsFloatPercentHeld': None,
                'institutionsCount': None,
            }

        # --- Institutional holders ---
        institutional_holders = []
        try:
            ih = ticker.institutional_holders
            if ih is not None and not ih.empty:
                for _, row in ih.iterrows():
                    institutional_holders.append({
                        'dateReported': row.get('Date Reported', '').strftime('%Y-%m-%d') if hasattr(row.get('Date Reported', ''), 'strftime') else str(row.get('Date Reported', '')),
                        'holder': str(row.get('Holder', '')),
                        'pctHeld': safe_val(row.get('pctHeld')),
                        'shares': safe_val(row.get('Shares')),
                        'value': safe_val(row.get('Value')),
                        'pctChange': safe_val(row.get('pctChange')),
                    })
        except Exception:
            pass

        # --- Mutual fund holders ---
        mutualfund_holders = []
        try:
            mfh = ticker.mutualfund_holders
            if mfh is not None and not mfh.empty:
                for _, row in mfh.iterrows():
                    mutualfund_holders.append({
                        'dateReported': row.get('Date Reported', '').strftime('%Y-%m-%d') if hasattr(row.get('Date Reported', ''), 'strftime') else str(row.get('Date Reported', '')),
                        'holder': str(row.get('Holder', '')),
                        'pctHeld': safe_val(row.get('pctHeld')),
                        'shares': safe_val(row.get('Shares')),
                        'value': safe_val(row.get('Value')),
                        'pctChange': safe_val(row.get('pctChange')),
                    })
        except Exception:
            pass

        # --- Insider purchases summary ---
        insider_purchases = []
        try:
            ip = ticker.insider_purchases
            if ip is not None and not ip.empty:
                for _, row in ip.iterrows():
                    insider_purchases.append({
                        'label': str(row.iloc[0]) if len(row) > 0 else '',
                        'shares': safe_val(row.get('Shares', row.iloc[1] if len(row) > 1 else None)),
                        'trans': safe_val(row.get('Trans', row.iloc[2] if len(row) > 2 else None)),
                    })
        except Exception:
            pass

        return jsonify({
            'success': True,
            'ticker': ticker_symbol.upper(),
            'company_name': company_name,
            'current_price': safe_val(current_price),
            'currency': currency,
            'sector': sector,
            'industry': industry,
            'insider_pct': safe_val(insider_pct),
            'institution_pct': safe_val(institution_pct),
            'float_shares': safe_val(float_shares),
            'shares_outstanding': safe_val(shares_outstanding),
            'major_holders': major_holders_data,
            'institutional_holders': institutional_holders,
            'mutualfund_holders': mutualfund_holders,
            'insider_purchases': insider_purchases,
        })

    except Exception as e:
        logger.exception("Error fetching ownership for %s", ticker_symbol)
        return jsonify({'success': False, 'error': str(e)}), 500


@api_data_bp.route('/api/market-overview', methods=['GET'])
def api_market_overview():
    """
    Return aggregated market overview data.
    Includes IHSG summary, top movers, sector performance, and market breadth.
    All data is cached for 5 minutes.
    """
    try:
        data = get_market_overview()
        return jsonify({'success': True, **data})
    except Exception as e:
        logger.exception("Error fetching market overview")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_data_bp.route('/api/backtest', methods=['POST'])
def api_backtest():
    """
    Run a strategy backtest on historical data.

    POST JSON body:
        ticker (str): Stock ticker (e.g., 'BBCA.JK')
        strategy_type (str): 'rsi', 'macd', 'ema_cross', or 'combined'
        params (dict): Strategy-specific parameters
        period (str): '1y', '2y', '3y', '5y' (default: '2y')
        initial_capital (int): Starting capital in IDR (default: 100_000_000)
        fees_pct (float): Broker fees % (default: 0.15)
    """
    data = request.get_json(silent=True) or {}

    ticker = data.get('ticker', '').strip()
    if not ticker:
        return jsonify({'success': False, 'error': 'Missing ticker'}), 400

    # Validate ticker format
    clean = _validate_multi_ticker(ticker)
    if not clean:
        logger.error(f"Failed validation for ticker: '{ticker}'")
        return jsonify({'success': False, 'error': f'Invalid ticker format: {ticker}'}), 400

    strategy_type = data.get('strategy_type', 'rsi')
    params = data.get('params', {})
    period = data.get('period', '2y')
    initial_capital = int(data.get('initial_capital', 100_000_000))
    fees_pct = float(data.get('fees_pct', 0.15))
    stop_loss_pct = float(data.get('stop_loss_pct', 0))
    take_profit_pct = float(data.get('take_profit_pct', 0))

    try:
        result = run_backtest(
            ticker=clean,
            strategy_type=strategy_type,
            params=params,
            period=period,
            initial_capital=initial_capital,
            fees_pct=fees_pct,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
        )
        if result.get('success'):
            for k, v in result.items():
                if isinstance(v, dict):
                    for subk, subv in v.items():
                        logger.info(f"Key: {k}.{subk} Type: {type(subv)}")
                else:
                    logger.info(f"Key: {k} Type: {type(v)}")
        return jsonify(result)
    except Exception as e:
        logger.exception("Backtest API error")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_data_bp.route('/api/backtest/optimize', methods=['POST'])
def api_backtest_optimize():
    """
    Run grid search optimization for a strategy.

    POST JSON body:
        ticker (str): Stock ticker
        strategy_type (str): 'rsi', 'macd', 'ema_cross', 'bollinger'
        param_ranges (dict): Param name -> list of values
        period (str): '1y', '2y', '3y', '5y'
    """
    data = request.get_json(silent=True) or {}

    ticker = data.get('ticker', '').strip()
    if not ticker:
        return jsonify({'success': False, 'error': 'Missing ticker'}), 400

    clean = _validate_multi_ticker(ticker)
    if not clean:
        return jsonify({'success': False, 'error': 'Invalid ticker format'}), 400

    strategy_type = data.get('strategy_type', 'rsi')
    param_ranges = data.get('param_ranges', {})
    period = data.get('period', '2y')
    initial_capital = int(data.get('initial_capital', 100_000_000))
    fees_pct = float(data.get('fees_pct', 0.15))

    try:
        result = run_optimization(
            ticker=clean,
            strategy_type=strategy_type,
            param_ranges=param_ranges,
            period=period,
            initial_capital=initial_capital,
            fees_pct=fees_pct,
        )
        return jsonify(result)
    except Exception as e:
        logger.exception("Optimization API error")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_data_bp.route('/api/backtest/walk-forward', methods=['POST'])
def api_backtest_walk_forward():
    """
    Run walk-forward analysis: optimize on train data, validate on test data.
    """
    data = request.get_json(silent=True) or {}

    ticker = data.get('ticker', '').strip()
    if not ticker:
        return jsonify({'success': False, 'error': 'Missing ticker'}), 400

    clean = _validate_multi_ticker(ticker)
    if not clean:
        return jsonify({'success': False, 'error': 'Invalid ticker format'}), 400

    strategy_type = data.get('strategy_type', 'rsi')
    param_ranges = data.get('param_ranges', {})
    period = data.get('period', '3y')
    train_pct = int(data.get('train_pct', 70))
    initial_capital = int(data.get('initial_capital', 100_000_000))
    fees_pct = float(data.get('fees_pct', 0.15))

    try:
        result = run_walk_forward(
            ticker=clean,
            strategy_type=strategy_type,
            param_ranges=param_ranges,
            period=period,
            train_pct=train_pct,
            initial_capital=initial_capital,
            fees_pct=fees_pct,
        )
        return jsonify(result)
    except Exception as e:
        logger.exception("Walk-forward API error")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_data_bp.route('/api/sentiment', methods=['GET'])
def api_sentiment():
    """
    AI Sentiment Analysis — Aggregate news from 6 sources and analyze
    sentiment using LLMs (Claude → Gemini → VADER fallback).

    Query params:
        ticker (str): Stock ticker (e.g., BBCA.JK, AAPL)
    """
    ticker = _validate_ticker(request.args.get('ticker'))
    if not ticker:
        return jsonify({'success': False, 'error': 'Valid ticker is required.'}), 400

    try:
        result = get_sentiment_analysis(ticker)
        if result.get('success'):
            return jsonify(result)
        else:
            return jsonify(result), 500
    except Exception as e:
        logger.exception("Sentiment API error for %s", ticker)
        return jsonify({'success': False, 'error': str(e)}), 500


# ─── Comparative Analysis ────────────────────────────────────────────

@api_data_bp.route('/api/compare', methods=['POST'])
def api_compare():
    """
    Compare 2-5 stocks side-by-side.

    POST JSON body:
        tickers (list): List of 2-5 ticker symbols (e.g., ["BBCA.JK", "BBRI.JK"])
    """
    from services.compare_service import compare_stocks

    data = request.get_json(silent=True) or {}
    tickers_raw = data.get('tickers', [])

    if not isinstance(tickers_raw, list):
        return jsonify({'success': False, 'error': 'tickers must be a list.'}), 400

    # Validate each ticker
    tickers = []
    for t in tickers_raw:
        validated = _validate_ticker(str(t))
        if validated:
            tickers.append(validated)

    if len(tickers) < 2:
        return jsonify({'success': False, 'error': 'At least 2 valid tickers required.'}), 400
    if len(tickers) > 5:
        return jsonify({'success': False, 'error': 'Maximum 5 tickers allowed.'}), 400

    try:
        result = compare_stocks(tickers)
        if result.get('success'):
            return jsonify(result)
        else:
            return jsonify(result), 400
    except Exception as e:
        logger.exception("Compare API error")
        return jsonify({'success': False, 'error': str(e)}), 500
