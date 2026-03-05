"""
Backtesting Service — Run strategy backtests using VectorBT.
Supports RSI, MACD, EMA Cross, and Combined strategies.
"""

import logging
import math

import numpy as np
import pandas as pd
import yfinance as yf
import vectorbt as vbt

logger = logging.getLogger(__name__)

# Valid periods for backtesting
VALID_PERIODS = ['1y', '2y', '3y', '5y']

# Default IDX broker fees (buy + sell)
DEFAULT_FEES_PCT = 0.15

# Index aliases (shared with api_data.py)
INDEX_ALIASES = {
    'IHSG': '^JKSE',
    'LQ45': '^JKLQ45',
    'IDX30': '^JKIDX30',
    'DJI': '^DJI',
    'DOWJONES': '^DJI',
    'SPX': '^GSPC',
    'SP500': '^GSPC',
    'NASDAQ': '^IXIC',
    'IXIC': '^IXIC',
    'NIKKEI': '^N225',
    'HSI': '^HSI',
    'HANGSENG': '^HSI',
    'STI': '^STI',
    'KOSPI': '^KS11',
    'FTSE': '^FTSE',
    'DAX': '^GDAXI',
}

# Benchmark mapping: ticker suffix/prefix → benchmark index
BENCHMARK_MAP = {
    '.JK': ('^JKSE', 'IHSG'),
    '.L': ('^FTSE', 'FTSE 100'),
    '.T': ('^N225', 'Nikkei 225'),
    '.HK': ('^HSI', 'Hang Seng'),
    '.KS': ('^KS11', 'KOSPI'),
    '.SI': ('^STI', 'STI'),
    '.DE': ('^GDAXI', 'DAX'),
}


def _normalize_ticker(raw: str) -> str:
    """
    Normalize a ticker for Yahoo Finance.
    - Resolve index aliases (IHSG → ^JKSE, SPX → ^GSPC, etc.)
    - If ticker already has a suffix (.JK, .L, etc.) or starts with ^, use as-is
    - If ticker looks like a plain IDX ticker (4 uppercase letters), append .JK
    - Otherwise, use as-is (e.g., AAPL, MSFT, TSLA)
    """
    t = raw.strip().upper()
    # Check index alias first
    if t in INDEX_ALIASES:
        return INDEX_ALIASES[t]
    # Already has suffix or is an index
    if '.' in t or t.startswith('^'):
        return t
    # Heuristic: 4-letter all-alpha tickers are likely IDX
    if t.isalpha() and len(t) == 4:
        return f"{t}.JK"
    # Everything else (AAPL, MSFT, BRK-B, etc.) — use as-is
    return t


def _get_benchmark(ticker: str):
    """Determine the appropriate benchmark index for a ticker."""
    upper = ticker.upper()
    # If the ticker IS an index, no benchmark needed
    if upper.startswith('^'):
        return None, None
    # Match by suffix
    for suffix, (bm_ticker, bm_name) in BENCHMARK_MAP.items():
        if upper.endswith(suffix.upper()):
            return bm_ticker, bm_name
    # Default: S&P 500 for US/international stocks
    return '^GSPC', 'S&P 500'


def _detect_currency(ticker_obj):
    """Detect currency from yfinance ticker info."""
    try:
        info = ticker_obj.info or {}
        return info.get('currency', 'USD')
    except Exception:
        return 'USD'


def _safe_val(v, default=0.0):
    """Safely convert to float, handle NaN/Inf."""
    try:
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return default
        return f
    except (TypeError, ValueError):
        return default


def _compute_rsi(closes, period=14):
    """Compute RSI series from close prices."""
    delta = closes.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)


def _compute_ema(closes, period):
    """Compute EMA series."""
    return closes.ewm(span=period, adjust=False).mean()


def _compute_macd(closes, fast=12, slow=26, signal=9):
    """Compute MACD line, signal line, and histogram."""
    ema_fast = _compute_ema(closes, fast)
    ema_slow = _compute_ema(closes, slow)
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def _generate_signals(hist, strategy_type, params):
    """
    Generate entry/exit boolean Series/DataFrames based on strategy type and params.
    """
    if isinstance(hist, pd.DataFrame) and 'Close' in hist.columns:
        closes = hist['Close']
    else:
        closes = hist  # fallback if passed Series directly

    if isinstance(closes, pd.DataFrame):
        entries = pd.DataFrame(False, index=closes.index, columns=closes.columns)
        exits = pd.DataFrame(False, index=closes.index, columns=closes.columns)
    else:
        entries = pd.Series(False, index=closes.index)
        exits = pd.Series(False, index=closes.index)

    if strategy_type == 'custom':
        custom_code = params.get('custom_code', '')
        if not custom_code:
            raise ValueError("Kode strategi custom kosong.")
            
        local_dict = {}
        try:
            # Sandbox the string execution
            exec(custom_code, globals(), local_dict)
            if 'custom_strategy' not in local_dict:
                raise ValueError("Kode tidak memiliki fungsi bernama 'custom_strategy(hist)'")
                
            func = local_dict['custom_strategy']
            # Execute with full historical dataframe
            e, x = func(hist)
            entries = e
            exits = x
            
        except Exception as e:
            raise ValueError(f"Error pada Custom Strategy: {str(e)}")

    elif strategy_type == 'rsi':
        period = int(params.get('rsi_period', 14))
        entry_threshold = float(params.get('rsi_entry', 30))
        exit_threshold = float(params.get('rsi_exit', 70))

        rsi = _compute_rsi(closes, period)
        # Buy when RSI crosses below entry threshold
        entries = (rsi < entry_threshold) & (rsi.shift(1) >= entry_threshold)
        # Sell when RSI crosses above exit threshold
        exits = (rsi > exit_threshold) & (rsi.shift(1) <= exit_threshold)

    elif strategy_type == 'macd':
        fast = int(params.get('macd_fast', 12))
        slow = int(params.get('macd_slow', 26))
        signal = int(params.get('macd_signal', 9))

        macd_line, signal_line, _ = _compute_macd(closes, fast, slow, signal)
        # Buy on bullish crossover (MACD crosses above signal)
        entries = (macd_line > signal_line) & (macd_line.shift(1) <= signal_line.shift(1))
        # Sell on bearish crossover (MACD crosses below signal)
        exits = (macd_line < signal_line) & (macd_line.shift(1) >= signal_line.shift(1))

    elif strategy_type == 'ema_cross':
        short_period = int(params.get('ema_short', 12))
        long_period = int(params.get('ema_long', 26))

        ema_short = _compute_ema(closes, short_period)
        ema_long = _compute_ema(closes, long_period)
        # Buy when short EMA crosses above long EMA
        entries = (ema_short > ema_long) & (ema_short.shift(1) <= ema_long.shift(1))
        # Sell when short EMA crosses below long EMA
        exits = (ema_short < ema_long) & (ema_short.shift(1) >= ema_long.shift(1))

    elif strategy_type == 'combined':
        # RSI + MACD combined
        rsi_period = int(params.get('rsi_period', 14))
        rsi_entry = float(params.get('rsi_entry', 30))
        rsi_exit = float(params.get('rsi_exit', 70))
        macd_fast = int(params.get('macd_fast', 12))
        macd_slow = int(params.get('macd_slow', 26))
        macd_signal = int(params.get('macd_signal', 9))

        rsi = _compute_rsi(closes, rsi_period)
        macd_line, signal_line, _ = _compute_macd(closes, macd_fast, macd_slow, macd_signal)

        rsi_buy = rsi < rsi_entry
        macd_buy = (macd_line > signal_line) & (macd_line.shift(1) <= signal_line.shift(1))

        rsi_sell = rsi > rsi_exit
        macd_sell = (macd_line < signal_line) & (macd_line.shift(1) >= signal_line.shift(1))

        # Entry: MACD bullish cross while RSI is oversold
        entries = macd_buy & rsi_buy
        # Exit: either RSI overbought or MACD bearish cross
        exits = rsi_sell | macd_sell

    elif strategy_type == 'bollinger':
        bb_period = int(params.get('bb_period', 20))
        bb_std = float(params.get('bb_std', 2.0))

        middle = closes.rolling(bb_period).mean()
        std = closes.rolling(bb_period).std()
        upper = middle + bb_std * std
        lower = middle - bb_std * std

        # Buy when price crosses below lower band
        entries = (closes < lower) & (closes.shift(1) >= lower.shift(1))
        # Sell when price crosses above upper band
        exits = (closes > upper) & (closes.shift(1) <= upper.shift(1))

    # Fill NaN with False
    entries = entries.fillna(False).astype(bool)
    exits = exits.fillna(False).astype(bool)

    return entries, exits


def _extract_trades(portfolio):
    """Extract trade log from VectorBT portfolio."""
    trades = []
    try:
        records = portfolio.trades.records_readable
        if records is None or records.empty:
            return trades

        for _, row in records.iterrows():
            entry_date = str(row.get('Entry Timestamp', ''))[:10]
            exit_date = str(row.get('Exit Timestamp', ''))[:10]
            entry_price = _safe_val(row.get('Avg Entry Price', 0))
            exit_price = _safe_val(row.get('Avg Exit Price', 0))
            pnl = _safe_val(row.get('PnL', 0))
            ret = _safe_val(row.get('Return', 0))
            size = _safe_val(row.get('Size', 0))
            direction = str(row.get('Direction', 'Long'))

            trades.append({
                'entry_date': entry_date,
                'exit_date': exit_date,
                'entry_price': round(entry_price, 2),
                'exit_price': round(exit_price, 2),
                'size': round(size, 2),
                'pnl': round(pnl, 2),
                'return_pct': round(ret * 100, 2),
                'direction': direction,
            })
    except Exception as e:
        logger.warning(f"Error extracting trades: {e}")

    return trades


def run_backtest(ticker, strategy_type, params, period='2y',
                 initial_capital=100_000_000, fees_pct=0.15,
                 stop_loss_pct=0, take_profit_pct=0):
    """
    Run a backtest for a given ticker and strategy.

    Args:
        ticker: Stock ticker (e.g., 'BBCA.JK')
        strategy_type: 'rsi', 'macd', 'ema_cross', or 'combined'
        params: Strategy-specific parameters dict
        period: Historical period ('1y', '2y', '3y', '5y')
        initial_capital: Starting capital in IDR
        fees_pct: Round-trip broker fees percentage
        stop_loss_pct: Stop loss percentage (0 = disabled)
        take_profit_pct: Take profit percentage (0 = disabled)

    Returns:
        dict with success, summary, equity_curve, drawdown_curve,
        price_data, benchmark_curve, trades
    """
    if period not in VALID_PERIODS:
        return {'success': False, 'error': f'Invalid period. Use: {VALID_PERIODS}'}

    valid_strategies = ('rsi', 'macd', 'ema_cross', 'combined', 'bollinger', 'custom')
    if strategy_type not in valid_strategies:
        return {'success': False, 'error': f'Invalid strategy_type. Use: {valid_strategies}'}

    try:
        # 1. Fetch historical data for one or multiple tickers
        tickers = [_normalize_ticker(t) for t in ticker.split(',')]

        if len(tickers) == 1:
            stock = yf.Ticker(tickers[0])
            try:
                hist = stock.history(period=period)
            except (TypeError, KeyError, ValueError) as e:
                return {'success': False, 'error': f'No data available for {tickers[0]}. Ticker may be invalid or delisted.'}
        else:
            try:
                hist = yf.download(tickers, period=period, progress=False)
            except (TypeError, KeyError, ValueError) as e:
                return {'success': False, 'error': f'No data available for one or more tickers. Some may be invalid or delisted.'}

        if hist.empty or len(hist) < 50:
            return {'success': False, 'error': f'Insufficient data for {ticker} ({period})'}

        if isinstance(hist, pd.DataFrame):
            if getattr(hist.columns, 'nlevels', 1) > 1:
                closes = hist['Close']
            elif 'Close' in hist.columns:
                closes = hist['Close']
            else:
                closes = hist
        else:
            closes = hist

        # 2. Generate entry/exit signals
        entries, exits = _generate_signals(hist, strategy_type, params)

        # Check if any signals were generated
        has_signals = entries.any().any() if isinstance(entries, pd.DataFrame) else entries.any()
        
        if not has_signals:
            bh_ret = round(((closes.iloc[-1] / closes.iloc[0]) - 1).mean() * 100, 2) if isinstance(closes, pd.DataFrame) else round(((closes.iloc[-1] / closes.iloc[0]) - 1) * 100, 2)
            return {
                'success': True,
                'summary': {
                    'total_return_pct': 0,
                    'win_rate': 0,
                    'max_drawdown_pct': 0,
                    'sharpe_ratio': 0,
                    'total_trades': 0,
                    'profit_factor': 0,
                    'buy_hold_return_pct': bh_ret,
                },
                'equity_curve': {
                    'dates': [closes.index[0].strftime('%Y-%m-%d'),
                              closes.index[-1].strftime('%Y-%m-%d')],
                    'values': [initial_capital, initial_capital],
                },
                'drawdown_curve': {'dates': [], 'values': []},
                'price_data': {'dates': [], 'prices': []},
                'benchmark_curve': {'dates': [], 'values': []},
                'trades': [],
                'message': 'Tidak ada sinyal trading yang dihasilkan. Coba sesuaikan parameter strategi atau logic code.',
            }

        # 3. Run VectorBT portfolio simulation
        fees = fees_pct / 100
        pf_kwargs = dict(
            close=closes,
            entries=entries,
            exits=exits,
            init_cash=initial_capital,
            fees=fees,
            freq='1D',
        )
        if isinstance(closes, pd.DataFrame):
            pf_kwargs['cash_sharing'] = True
            pf_kwargs['group_by'] = True

        # Add stop loss / take profit if specified
        if stop_loss_pct and stop_loss_pct > 0:
            pf_kwargs['sl_stop'] = stop_loss_pct / 100
        if take_profit_pct and take_profit_pct > 0:
            pf_kwargs['tp_stop'] = take_profit_pct / 100

        portfolio = vbt.Portfolio.from_signals(**pf_kwargs)

        # 4. Extract metrics
        stats = portfolio.stats()

        total_return = _safe_val(stats.get('Total Return [%]', 0))
        max_dd = _safe_val(stats.get('Max Drawdown [%]', 0))
        sharpe = _safe_val(stats.get('Sharpe Ratio', 0))
        total_trades = int(_safe_val(stats.get('Total Trades', 0)))
        win_rate = _safe_val(stats.get('Win Rate [%]', 0))

        # Profit factor
        try:
            trades_records = portfolio.trades.records_readable
            if trades_records is not None and not trades_records.empty:
                winning = trades_records[trades_records['PnL'] > 0]['PnL'].sum()
                losing = abs(trades_records[trades_records['PnL'] < 0]['PnL'].sum())
                if losing > 0:
                    profit_factor = round(winning / losing, 2)
                elif winning > 0:
                    # All trades are winners, cap at 999.99
                    profit_factor = 999.99
                else:
                    profit_factor = 0
            else:
                profit_factor = 0
        except Exception:
            profit_factor = 0

        # Buy & Hold comparison
        if isinstance(closes, pd.DataFrame):
            buy_hold_return = round(((closes.iloc[-1] / closes.iloc[0]) - 1).mean() * 100, 2)
        else:
            buy_hold_return = round(((closes.iloc[-1] / closes.iloc[0]) - 1) * 100, 2)

        # 5. Equity curve
        equity = portfolio.value()
        if len(equity) > 500:
            step = max(1, len(equity) // 500)
            equity_sampled = equity.iloc[::step]
        else:
            equity_sampled = equity

        equity_dates = [d.strftime('%Y-%m-%d') for d in equity_sampled.index]
        equity_values = [round(_safe_val(v), 0) for v in equity_sampled.values]

        # 6. Drawdown curve
        drawdown = portfolio.drawdown()
        if len(drawdown) > 500:
            dd_sampled = drawdown.iloc[::step]
        else:
            dd_sampled = drawdown
        dd_dates = [d.strftime('%Y-%m-%d') for d in dd_sampled.index]
        dd_values = [round(_safe_val(v) * 100, 2) for v in dd_sampled.values]

        # 7. Price data for chart
        if isinstance(closes, pd.DataFrame):
            price_series = closes.iloc[:, 0]
        else:
            price_series = closes

        if len(price_series) > 500:
            price_sampled = price_series.iloc[::step]
        else:
            price_sampled = price_series
            
        price_dates = [d.strftime('%Y-%m-%d') for d in price_sampled.index]
        price_values = [round(_safe_val(v), 0) for v in price_sampled.values]

        # 8. Benchmark — auto-detect based on ticker market
        benchmark_data = {'dates': [], 'values': []}
        bm_ticker_sym, bm_name = _get_benchmark(tickers[0])
        try:
            if bm_ticker_sym:
                bm_hist = yf.Ticker(bm_ticker_sym).history(period=period)
                if not bm_hist.empty and len(bm_hist) > 10:
                    stock_start = hist.index.min()
                    stock_end = hist.index.max()
                    if bm_hist.index.tz is not None and stock_start.tzinfo is None:
                        bm_hist.index = bm_hist.index.tz_localize(None)
                    elif bm_hist.index.tz is None and stock_start.tzinfo is not None:
                        stock_start = stock_start.tz_localize(None)
                        stock_end = stock_end.tz_localize(None)
                    bm_clipped = bm_hist.loc[
                        (bm_hist.index >= stock_start) & (bm_hist.index <= stock_end)
                    ]
                    if not bm_clipped.empty and len(bm_clipped) > 5:
                        bm_norm = (bm_clipped['Close'] / bm_clipped['Close'].iloc[0]) * initial_capital
                        if len(bm_norm) > 500:
                            bm_sampled = bm_norm.iloc[::max(1, len(bm_norm) // 500)]
                        else:
                            bm_sampled = bm_norm
                        benchmark_data = {
                            'dates': [d.strftime('%Y-%m-%d') for d in bm_sampled.index],
                            'values': [round(_safe_val(v), 0) for v in bm_sampled.values],
                        }
        except Exception:
            pass  # Non-critical, skip if fails

        # Detect currency for display
        try:
            currency = _detect_currency(yf.Ticker(tickers[0]))
        except Exception:
            currency = 'IDR'

        # 9. Trade log
        trade_log = _extract_trades(portfolio)

        return {
            'success': True,
            'currency': currency,
            'benchmark_name': bm_name,
            'summary': {
                'total_return_pct': float(round(total_return, 2)),
                'win_rate': float(round(win_rate, 2)),
                'max_drawdown_pct': float(round(-abs(max_dd), 2)),
                'sharpe_ratio': float(round(sharpe, 2)),
                'total_trades': int(total_trades),
                'profit_factor': float(profit_factor),
                'buy_hold_return_pct': float(buy_hold_return),
            },
            'equity_curve': {
                'dates': equity_dates,
                'values': equity_values,
            },
            'drawdown_curve': {
                'dates': dd_dates,
                'values': dd_values,
            },
            'price_data': {
                'dates': price_dates,
                'prices': price_values,
            },
            'benchmark_curve': benchmark_data,
            'monthly_returns': _compute_monthly_returns(portfolio),
            'trades': trade_log,
        }

    except Exception as e:
        logger.exception(f"Backtest error for {ticker}")
        return {'success': False, 'error': str(e)}


def _compute_monthly_returns(portfolio):
    """Compute monthly return matrix {year: {month: return%}}."""
    try:
        equity = portfolio.value()
        monthly = equity.resample('ME').last()
        monthly_ret = monthly.pct_change() * 100

        result = {}
        for date, ret in monthly_ret.items():
            year = str(date.year)
            month = date.month
            if year not in result:
                result[year] = {}
            result[year][str(month)] = round(_safe_val(ret), 2)
        return result
    except Exception:
        return {}


def run_optimization(ticker, strategy_type, param_ranges, period='2y',
                     initial_capital=100_000_000, fees_pct=0.15):
    """
    Run grid search optimization across parameter ranges.
    Uses VectorBT's vectorized multi-column simulation.

    Args:
        ticker: Stock ticker (e.g., 'BBCA.JK')
        strategy_type: 'rsi', 'macd', 'ema_cross', 'bollinger'
        param_ranges: Dict of param_name -> list of values
        period: '1y', '2y', '3y', '5y'
        initial_capital: Starting capital
        fees_pct: Broker fees %

    Returns:
        dict with success, results (sorted by Sharpe), best_params
    """
    from itertools import product

    if period not in VALID_PERIODS:
        return {'success': False, 'error': f'Invalid period. Use: {VALID_PERIODS}'}

    try:
        tickers = [t.strip().upper() for t in ticker.split(',')]
        if len(tickers) > 1:
            return {'success': False, 'error': 'Optimasi saat ini hanya mendukung Single Ticker.'}
            
        clean_ticker = _normalize_ticker(tickers[0])

        stock = yf.Ticker(clean_ticker)
        try:
            hist = stock.history(period=period)
        except (TypeError, KeyError, ValueError) as e:
            return {'success': False, 'error': f'No data available for {clean_ticker}. Ticker may be invalid or delisted.'}
        if hist.empty or len(hist) < 50:
            return {'success': False, 'error': f'Insufficient data for {clean_ticker}'}

        closes = hist['Close']
        fees = fees_pct / 100

        # Build all param combinations and generate signals
        entries_list = []
        exits_list = []
        combos = []

        if strategy_type == 'rsi':
            entry_vals = param_ranges.get('rsi_entry', [30])
            exit_vals = param_ranges.get('rsi_exit', [70])
            rsi_period = int(param_ranges.get('rsi_period', [14])[0]) if isinstance(param_ranges.get('rsi_period'), list) else 14
            rsi = _compute_rsi(closes, rsi_period)

            for ev, xv in product(entry_vals, exit_vals):
                if ev >= xv:
                    continue  # skip invalid: entry must be < exit
                e = ((rsi < ev) & (rsi.shift(1) >= ev)).fillna(False)
                x = ((rsi > xv) & (rsi.shift(1) <= xv)).fillna(False)
                entries_list.append(e)
                exits_list.append(x)
                combos.append({'rsi_entry': ev, 'rsi_exit': xv})

        elif strategy_type == 'macd':
            fast_vals = param_ranges.get('macd_fast', [12])
            slow_vals = param_ranges.get('macd_slow', [26])
            signal_vals = param_ranges.get('macd_signal', [9])

            for f, s, sig in product(fast_vals, slow_vals, signal_vals):
                if f >= s:
                    continue
                ml, sl, _ = _compute_macd(closes, f, s, sig)
                e = ((ml > sl) & (ml.shift(1) <= sl.shift(1))).fillna(False)
                x = ((ml < sl) & (ml.shift(1) >= sl.shift(1))).fillna(False)
                entries_list.append(e)
                exits_list.append(x)
                combos.append({'macd_fast': f, 'macd_slow': s, 'macd_signal': sig})

        elif strategy_type == 'ema_cross':
            short_vals = param_ranges.get('ema_short', [12])
            long_vals = param_ranges.get('ema_long', [26])

            for sv, lv in product(short_vals, long_vals):
                if sv >= lv:
                    continue
                es = _compute_ema(closes, sv)
                el = _compute_ema(closes, lv)
                e = ((es > el) & (es.shift(1) <= el.shift(1))).fillna(False)
                x = ((es < el) & (es.shift(1) >= el.shift(1))).fillna(False)
                entries_list.append(e)
                exits_list.append(x)
                combos.append({'ema_short': sv, 'ema_long': lv})

        elif strategy_type == 'bollinger':
            period_vals = param_ranges.get('bb_period', [20])
            std_vals = param_ranges.get('bb_std', [2.0])

            for p, sd in product(period_vals, std_vals):
                mid = closes.rolling(p).mean()
                std = closes.rolling(p).std()
                lower = mid - sd * std
                upper = mid + sd * std
                e = ((closes < lower) & (closes.shift(1) >= lower.shift(1))).fillna(False)
                x = ((closes > upper) & (closes.shift(1) <= upper.shift(1))).fillna(False)
                entries_list.append(e)
                exits_list.append(x)
                combos.append({'bb_period': p, 'bb_std': sd})
        else:
            return {'success': False, 'error': f'Optimization not supported for: {strategy_type}'}

        if not combos:
            return {'success': False, 'error': 'No valid parameter combinations generated'}

        # Stack as DataFrame columns for vectorized simulation
        all_entries = pd.concat(entries_list, axis=1).astype(bool)
        all_exits = pd.concat(exits_list, axis=1).astype(bool)

        pf = vbt.Portfolio.from_signals(
            closes, all_entries, all_exits,
            init_cash=initial_capital, fees=fees, freq='1D'
        )

        # Extract metrics per combo
        total_returns = pf.total_return()
        sharpe_ratios = pf.sharpe_ratio()
        max_drawdowns = pf.max_drawdown()
        trade_counts = pf.trades.count()

        results = []
        for i, combo in enumerate(combos):
            results.append({
                **combo,
                'total_return_pct': round(_safe_val(float(total_returns.iloc[i]) * 100), 2),
                'sharpe_ratio': round(_safe_val(float(sharpe_ratios.iloc[i])), 2),
                'max_drawdown_pct': round(_safe_val(float(max_drawdowns.iloc[i]) * 100), 2),
                'total_trades': int(_safe_val(float(trade_counts.iloc[i]))),
            })

        # Sort by Sharpe ratio descending
        results.sort(key=lambda x: x['sharpe_ratio'], reverse=True)

        best = results[0] if results else {}

        return {
            'success': True,
            'results': results,
            'total_combos': len(results),
            'best_params': best,
        }

    except Exception as e:
        logger.exception(f"Optimization error for {ticker}")
        return {'success': False, 'error': str(e)}


def run_walk_forward(ticker, strategy_type, param_ranges, period='3y',
                     train_pct=70, initial_capital=100_000_000, fees_pct=0.15):
    """
    Walk-Forward Analysis: optimize on training data, validate on test data.

    Args:
        ticker: Stock ticker
        strategy_type: 'rsi', 'macd', 'ema_cross', 'bollinger'
        param_ranges: Dict of param_name -> list of values
        period: '2y', '3y', '5y' (need enough data for split)
        train_pct: Percentage of data for training (default 70%)
        initial_capital: Starting capital
        fees_pct: Broker fees %

    Returns:
        dict with in_sample, out_of_sample results, best_params,
        equity curves for both periods
    """
    from itertools import product

    if period not in VALID_PERIODS:
        return {'success': False, 'error': f'Invalid period. Use: {VALID_PERIODS}'}

    try:
        tickers = [t.strip().upper() for t in ticker.split(',')]
        if len(tickers) > 1:
            return {'success': False, 'error': 'Walk-Forward saat ini hanya mendukung Single Ticker.'}
            
        clean_ticker = _normalize_ticker(tickers[0])

        stock = yf.Ticker(clean_ticker)
        try:
            hist = stock.history(period=period)
        except (TypeError, KeyError, ValueError) as e:
            return {'success': False, 'error': f'No data available for {clean_ticker}. Ticker may be invalid or delisted.'}
        if hist.empty or len(hist) < 100:
            return {'success': False, 'error': f'Insufficient data for {clean_ticker} (need 100+ days)'}

        closes = hist['Close']

        # Split into train/test
        split_idx = int(len(closes) * train_pct / 100)
        train_closes = closes.iloc[:split_idx]
        test_closes = closes.iloc[split_idx:]

        if len(train_closes) < 50 or len(test_closes) < 20:
            return {'success': False, 'error': 'Not enough data after split. Use longer period.'}

        fees = fees_pct / 100

        # ── Phase 1: Optimize on training data ──
        entries_list = []
        exits_list = []
        combos = []

        if strategy_type == 'rsi':
            entry_vals = param_ranges.get('rsi_entry', [30])
            exit_vals = param_ranges.get('rsi_exit', [70])
            rsi_period = int(param_ranges.get('rsi_period', [14])[0]) if isinstance(param_ranges.get('rsi_period'), list) else 14
            rsi = _compute_rsi(train_closes, rsi_period)
            for ev, xv in product(entry_vals, exit_vals):
                if ev >= xv:
                    continue
                e = ((rsi < ev) & (rsi.shift(1) >= ev)).fillna(False)
                x = ((rsi > xv) & (rsi.shift(1) <= xv)).fillna(False)
                entries_list.append(e)
                exits_list.append(x)
                combos.append({'rsi_period': rsi_period, 'rsi_entry': ev, 'rsi_exit': xv})

        elif strategy_type == 'macd':
            fast_vals = param_ranges.get('macd_fast', [12])
            slow_vals = param_ranges.get('macd_slow', [26])
            signal_vals = param_ranges.get('macd_signal', [9])
            for f, s, sig in product(fast_vals, slow_vals, signal_vals):
                if f >= s:
                    continue
                ml, sl, _ = _compute_macd(train_closes, f, s, sig)
                e = ((ml > sl) & (ml.shift(1) <= sl.shift(1))).fillna(False)
                x = ((ml < sl) & (ml.shift(1) >= sl.shift(1))).fillna(False)
                entries_list.append(e)
                exits_list.append(x)
                combos.append({'macd_fast': f, 'macd_slow': s, 'macd_signal': sig})

        elif strategy_type == 'ema_cross':
            short_vals = param_ranges.get('ema_short', [12])
            long_vals = param_ranges.get('ema_long', [26])
            for sv, lv in product(short_vals, long_vals):
                if sv >= lv:
                    continue
                es = _compute_ema(train_closes, sv)
                el = _compute_ema(train_closes, lv)
                e = ((es > el) & (es.shift(1) <= el.shift(1))).fillna(False)
                x = ((es < el) & (es.shift(1) >= el.shift(1))).fillna(False)
                entries_list.append(e)
                exits_list.append(x)
                combos.append({'ema_short': sv, 'ema_long': lv})

        elif strategy_type == 'bollinger':
            period_vals = param_ranges.get('bb_period', [20])
            std_vals = param_ranges.get('bb_std', [2.0])
            for p, sd in product(period_vals, std_vals):
                mid = train_closes.rolling(p).mean()
                std_s = train_closes.rolling(p).std()
                lower = mid - sd * std_s
                upper = mid + sd * std_s
                e = ((train_closes < lower) & (train_closes.shift(1) >= lower.shift(1))).fillna(False)
                x = ((train_closes > upper) & (train_closes.shift(1) <= upper.shift(1))).fillna(False)
                entries_list.append(e)
                exits_list.append(x)
                combos.append({'bb_period': p, 'bb_std': sd})
        else:
            return {'success': False, 'error': f'Walk-forward not supported for: {strategy_type}'}

        if not combos:
            return {'success': False, 'error': 'No valid parameter combinations'}

        # Vectorized training simulation
        all_entries = pd.concat(entries_list, axis=1).astype(bool)
        all_exits = pd.concat(exits_list, axis=1).astype(bool)
        pf_train = vbt.Portfolio.from_signals(
            train_closes, all_entries, all_exits,
            init_cash=initial_capital, fees=fees, freq='1D'
        )

        # Find best combo by Sharpe
        sharpes = pf_train.sharpe_ratio()
        best_idx = int(sharpes.argmax()) if not sharpes.isna().all() else 0
        best_combo = combos[best_idx]

        # In-sample metrics
        in_return = round(_safe_val(float(pf_train.total_return().iloc[best_idx]) * 100), 2)
        in_sharpe = round(_safe_val(float(sharpes.iloc[best_idx])), 2)
        in_dd = round(_safe_val(float(pf_train.max_drawdown().iloc[best_idx]) * 100), 2)
        in_trades = int(_safe_val(float(pf_train.trades.count().iloc[best_idx])))

        # In-sample equity curve
        in_equity = pf_train.value().iloc[:, best_idx]
        if len(in_equity) > 300:
            step = max(1, len(in_equity) // 300)
            in_eq_s = in_equity.iloc[::step]
        else:
            in_eq_s = in_equity
        in_eq_data = {
            'dates': [d.strftime('%Y-%m-%d') for d in in_eq_s.index],
            'values': [round(_safe_val(v), 0) for v in in_eq_s.values],
        }

        # ── Phase 2: Validate on test data with best params ──
        test_entries, test_exits = _generate_signals(test_closes, strategy_type, best_combo)

        if not test_entries.any():
            out_return = 0
            out_sharpe = 0
            out_dd = 0
            out_trades = 0
            out_eq_data = {
                'dates': [test_closes.index[0].strftime('%Y-%m-%d'),
                          test_closes.index[-1].strftime('%Y-%m-%d')],
                'values': [initial_capital, initial_capital],
            }
        else:
            pf_test = vbt.Portfolio.from_signals(
                test_closes, test_entries, test_exits,
                init_cash=initial_capital, fees=fees, freq='1D'
            )
            test_stats = pf_test.stats()
            out_return = round(_safe_val(test_stats.get('Total Return [%]', 0)), 2)
            out_sharpe = round(_safe_val(test_stats.get('Sharpe Ratio', 0)), 2)
            out_dd = round(_safe_val(test_stats.get('Max Drawdown [%]', 0)), 2)
            out_trades = int(_safe_val(test_stats.get('Total Trades', 0)))

            out_equity = pf_test.value()
            if len(out_equity) > 300:
                step = max(1, len(out_equity) // 300)
                out_eq_s = out_equity.iloc[::step]
            else:
                out_eq_s = out_equity
            out_eq_data = {
                'dates': [d.strftime('%Y-%m-%d') for d in out_eq_s.index],
                'values': [round(_safe_val(v), 0) for v in out_eq_s.values],
            }

        # Robustness score: how well does out-of-sample track in-sample?
        if in_sharpe > 0 and out_sharpe > 0:
            robustness = round(min(out_sharpe / max(in_sharpe, 0.01), 2.0) * 100, 0)
        elif out_sharpe >= 0:
            robustness = 50
        else:
            robustness = 0

        return {
            'success': True,
            'best_params': best_combo,
            'total_combos': len(combos),
            'train_period': {
                'start': train_closes.index[0].strftime('%Y-%m-%d'),
                'end': train_closes.index[-1].strftime('%Y-%m-%d'),
                'days': len(train_closes),
            },
            'test_period': {
                'start': test_closes.index[0].strftime('%Y-%m-%d'),
                'end': test_closes.index[-1].strftime('%Y-%m-%d'),
                'days': len(test_closes),
            },
            'in_sample': {
                'total_return_pct': in_return,
                'sharpe_ratio': in_sharpe,
                'max_drawdown_pct': round(-abs(in_dd), 2),
                'total_trades': in_trades,
            },
            'out_of_sample': {
                'total_return_pct': out_return,
                'sharpe_ratio': out_sharpe,
                'max_drawdown_pct': round(-abs(out_dd), 2),
                'total_trades': out_trades,
            },
            'in_sample_equity': in_eq_data,
            'out_of_sample_equity': out_eq_data,
            'robustness_score': robustness,
        }

    except Exception as e:
        logger.exception(f"Walk-forward error for {ticker}")
        return {'success': False, 'error': str(e)}


