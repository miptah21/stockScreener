"""
Financial Data Scraper — Flask Application
Serves the dashboard and provides API endpoints for financial data.
Supports Yahoo Finance with WSJ Markets as fallback.
"""

from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from scraper import get_financials
from screener import get_stock_lists, screen_stocks
from bandarmology import get_broker_summary, calculate_bandar_flow
from technical_screener import run_technical_screen, MARKET_CAP_PRESETS

app = Flask(__name__)
CORS(app)


@app.route('/')
def index():
    """Serve the main dashboard page."""
    return render_template('index.html')


@app.route('/screening')
def screening():
    """Serve the stock screening page."""
    return render_template('screening.html')


@app.route('/api/scrape', methods=['GET'])
def api_scrape():
    """
    API endpoint to scrape financial data.
    
    Query params:
        ticker (str): Stock ticker symbol (e.g., AAPL, BBCA.JK)
        year (int, optional): Target fiscal year for scoring (e.g. 2023). 
                              If omitted, uses latest available data.
    
    Returns:
        JSON with financial metrics and company info
    """
    ticker = request.args.get('ticker')
    if not ticker:
        return jsonify({'error': 'Ticker is required'}), 400

    print(f"Received scrape request for {ticker}")
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
        # Return error with 500 status code so frontend handles it as error
        return jsonify(result), 500


@app.route('/api/stock-lists', methods=['GET'])
def api_stock_lists():
    """Return available stock lists for screening."""
    return jsonify({
        'success': True,
        'lists': get_stock_lists()
    })


@app.route('/api/screen', methods=['GET', 'POST'])
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


@app.route('/api/history', methods=['GET'])
def api_history():
    """
    Return historical price data for chart rendering.

    Query params:
        ticker (str): Stock ticker symbol
        period (str): Data period — 1mo, 3mo, 6mo, 1y, 5y (default: 6mo)
    """
    import yfinance as yf

    ticker_symbol = request.args.get('ticker', '').strip()
    period = request.args.get('period', '6mo').strip()

    if not ticker_symbol:
        return jsonify({'success': False, 'error': 'Ticker is required.'}), 400

    valid_periods = ['1mo', '3mo', '6mo', '1y', '2y', '5y', 'max']
    if period not in valid_periods:
        period = '6mo'

    try:
        ticker = yf.Ticker(ticker_symbol)
        hist = ticker.history(period=period)

        if hist.empty:
            return jsonify({'success': False, 'error': 'No historical data found.'})

        dates = [d.strftime('%Y-%m-%d') for d in hist.index]
        closes = [round(float(c), 2) for c in hist['Close']]
        volumes = [int(v) for v in hist['Volume']]

        return jsonify({
            'success': True,
            'ticker': ticker_symbol,
            'period': period,
            'dates': dates,
            'closes': closes,
            'volumes': volumes,
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/avg-price')
def avg_price_page():
    """Serve the stock average price (FCA) page."""
    return render_template('avg_price.html')


@app.route('/api/avg-price', methods=['GET'])
def api_avg_price():
    """
    Calculate average stock price over the last 6 months.

    Query params:
        ticker (str): Stock ticker symbol (e.g., BBCA.JK, AAPL)

    Returns:
        JSON with average, median, high, low, current price, and daily data.
    """
    import yfinance as yf
    import statistics

    ticker_symbol = request.args.get('ticker', '').strip()
    if not ticker_symbol:
        return jsonify({'success': False, 'error': 'Ticker is required.'}), 400

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
        return jsonify({'success': False, 'error': str(e)}), 500


        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/bandarmology', methods=['GET'])
def api_bandarmology():
    """
    API endpoint to get Bandarmology analysis using range.
    
    Query params:
        ticker (str): Stock ticker (e.g., BBCA).
        start_date (str): Date in YYYY-MM-DD format.
        end_date (str): Date in YYYY-MM-DD format.
        date (str): Optional legacy param (treated as start=end).
    """
    ticker = request.args.get('ticker')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    date = request.args.get('date')
    
    if not ticker:
        return jsonify({'error': 'Ticker is required'}), 400
        
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
        return jsonify({'error': 'Failed to fetch broker data or no data available'}), 500
        
    analysis = calculate_bandar_flow(broker_data)
    
    return jsonify({
        'success': True,
        'ticker': ticker_clean,
        'start_date': start_date,
        'end_date': end_date or start_date,
        'data': analysis
    })


@app.route('/api/market-date', methods=['GET'])
def api_market_date():
    """
    Get the last available trading date from Yahoo Finance.
    Useful for setting default date ranges.
    """
    import yfinance as yf
    try:
        # Use BBCA.JK as a reliable proxy for IDX market open days
        ticker = yf.Ticker("BBCA.JK")
        # Fetch last 5 days to find the latest valid one
        hist = ticker.history(period="5d")
        
        if not hist.empty:
            last_date = hist.index[-1].strftime('%Y-%m-%d')
            return jsonify({'success': True, 'date': last_date})
            
        return jsonify({'success': False, 'error': 'No market data found'}), 404
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/ownership')
def ownership_page():
    """Serve the Ownership Summary page."""
    return render_template('ownership.html')


@app.route('/api/ownership', methods=['GET'])
def api_ownership():
    """
    Return ownership summary data for a stock.

    Query params:
        ticker (str): Stock ticker symbol (e.g., BBCA.JK, AAPL)

    Returns:
        JSON with major holders breakdown, top institutional holders,
        top mutual fund holders, and insider purchase summary.
    """
    import yfinance as yf
    import math

    ticker_symbol = request.args.get('ticker', '').strip()
    if not ticker_symbol:
        return jsonify({'success': False, 'error': 'Ticker is required.'}), 400

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
                    # Handle both old and new yfinance formats
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

        # --- Helper to safely convert values ---
        def safe_val(v):
            if v is None:
                return None
            try:
                f = float(v)
                return None if (math.isnan(f) or math.isinf(f)) else f
            except (ValueError, TypeError):
                return None

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
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/technical-screening')
def technical_screening_page():
    """Serve the Technical Analysis Screening page."""
    return render_template('technical_screening.html')


@app.route('/api/technical-screen', methods=['POST'])
def api_technical_screen():
    """
    Run technical analysis screening on a stock list.

    POST JSON body:
        list (str): Stock list key or 'custom'
        tickers (list): Custom tickers (if list='custom')
        min_market_cap (float): Min market cap filter (optional)
        max_market_cap (float): Max market cap filter (optional)
        market_cap_preset (str): Preset key like 'small', 'mid', 'large' (optional)
    """
    data = request.get_json() or {}
    list_key = data.get('list', '').strip()
    custom_tickers = data.get('tickers', [])
    preset = data.get('market_cap_preset', 'all')

    if not list_key:
        return jsonify({'success': False, 'error': 'Parameter "list" is required.'}), 400

    # Resolve market cap from preset or explicit values
    min_mc = data.get('min_market_cap')
    max_mc = data.get('max_market_cap')

    if preset and preset in MARKET_CAP_PRESETS and preset != 'all':
        p = MARKET_CAP_PRESETS[preset]
        min_mc = p['min']
        max_mc = p['max']

    result = run_technical_screen(
        list_key=list_key,
        custom_tickers=custom_tickers,
        min_market_cap=min_mc,
        max_market_cap=max_mc,
    )

    if not result.get('success'):
        return jsonify(result), 400

    return jsonify(result)


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

