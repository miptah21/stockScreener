"""
Backtesting Service — Run strategy backtests using a custom Pandas engine.
Supports RSI, MACD, EMA Cross, Bollinger, Combined, and Custom strategies.
"""

import logging
import math

import numpy as np
import pandas as pd
import yfinance as yf

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
    - Otherwise, use as-is (users should explicitly use .JK for IDX stocks)
    """
    t = raw.strip().upper()
    # Check index alias first
    if t in INDEX_ALIASES:
        return INDEX_ALIASES[t]
    # Already has suffix or is an index — use as-is
    if '.' in t or t.startswith('^'):
        return t
    # All other tickers — use as-is (e.g., AAPL, MSFT, BBCA without .JK)
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
    Generate entry/exit boolean Series based on strategy type and params.
    
    Args:
        hist: DataFrame with OHLCV columns, or a Series of close prices.
        strategy_type: Strategy identifier string.
        params: Dict of strategy parameters.
    
    Returns:
        (entries, exits) as boolean Series.
    """
    # Robustly extract close prices from DataFrame or Series
    if isinstance(hist, pd.DataFrame) and 'Close' in hist.columns:
        closes = hist['Close']
    elif isinstance(hist, pd.Series):
        closes = hist
    else:
        closes = hist

    # Ensure we work with a 1D Series
    if isinstance(closes, pd.DataFrame):
        closes = closes.iloc[:, 0]

    entries = pd.Series(False, index=closes.index)
    exits = pd.Series(False, index=closes.index)

    if strategy_type == 'custom':
        custom_code = params.get('custom_code', '')
        if not custom_code:
            raise ValueError("Kode strategi custom kosong.")

        # Restricted execution — only allow safe builtins
        safe_builtins = {
            'abs': abs, 'max': max, 'min': min, 'round': round,
            'len': len, 'range': range, 'int': int, 'float': float,
            'True': True, 'False': False, 'None': None,
            'print': print,
        }
        safe_globals = {
            '__builtins__': safe_builtins,
            'pd': pd,
            'np': np,
        }
        local_dict = {}
        try:
            exec(custom_code, safe_globals, local_dict)
            if 'custom_strategy' not in local_dict:
                raise ValueError("Kode tidak memiliki fungsi bernama 'custom_strategy(hist)'")

            func = local_dict['custom_strategy']
            # Provide a DataFrame-like input
            if isinstance(hist, pd.Series):
                hist_input = pd.DataFrame({'Close': hist})
            else:
                hist_input = hist
            e, x = func(hist_input)
            entries = e
            exits = x

        except Exception as e:
            raise ValueError(f"Error pada Custom Strategy: {str(e)}")

    elif strategy_type == 'rsi':
        period = int(params.get('rsi_period', 14))
        entry_threshold = float(params.get('rsi_entry', 30))
        exit_threshold = float(params.get('rsi_exit', 70))

        rsi = _compute_rsi(closes, period)
        entries = (rsi < entry_threshold) & (rsi.shift(1) >= entry_threshold)
        exits = (rsi > exit_threshold) & (rsi.shift(1) <= exit_threshold)

    elif strategy_type == 'macd':
        fast = int(params.get('macd_fast', 12))
        slow = int(params.get('macd_slow', 26))
        signal = int(params.get('macd_signal', 9))

        macd_line, signal_line, _ = _compute_macd(closes, fast, slow, signal)
        entries = (macd_line > signal_line) & (macd_line.shift(1) <= signal_line.shift(1))
        exits = (macd_line < signal_line) & (macd_line.shift(1) >= signal_line.shift(1))

    elif strategy_type == 'ema_cross':
        short_period = int(params.get('ema_short', 12))
        long_period = int(params.get('ema_long', 26))

        ema_short = _compute_ema(closes, short_period)
        ema_long = _compute_ema(closes, long_period)
        entries = (ema_short > ema_long) & (ema_short.shift(1) <= ema_long.shift(1))
        exits = (ema_short < ema_long) & (ema_short.shift(1) >= ema_long.shift(1))

    elif strategy_type == 'combined':
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

        entries = macd_buy & rsi_buy
        exits = rsi_sell | macd_sell

    elif strategy_type == 'bollinger':
        bb_period = int(params.get('bb_period', 20))
        bb_std = float(params.get('bb_std', 2.0))

        middle = closes.rolling(bb_period).mean()
        std = closes.rolling(bb_period).std()
        upper = middle + bb_std * std
        lower = middle - bb_std * std

        entries = (closes < lower) & (closes.shift(1) >= lower.shift(1))
        exits = (closes > upper) & (closes.shift(1) <= upper.shift(1))

    # Fill NaN with False
    entries = entries.fillna(False).astype(bool)
    exits = exits.fillna(False).astype(bool)

    return entries, exits


# ─── Custom Pandas Backtest Engine ────────────────────────────────────

def _run_pandas_backtest(closes, entries, exits, initial_capital, fees,
                         stop_loss_pct=0, take_profit_pct=0):
    """
    Run a backtest simulation using pure pandas logic.

    Simulates a simple long-only strategy:
    - On entry signal, buy as many shares as capital allows.
    - On exit signal, sell all shares.
    - Stop-loss/take-profit checked daily if position is open.

    Returns:
        dict with keys: equity (Series), trades (list of dicts),
        total_return, max_drawdown, sharpe_ratio, win_rate,
        total_trades, profit_factor.
    """
    cash = float(initial_capital)
    position = 0.0       # shares held
    entry_price = 0.0
    entry_date = None
    trades = []

    equity_values = []
    equity_dates = []

    sl = stop_loss_pct / 100 if stop_loss_pct and stop_loss_pct > 0 else 0
    tp = take_profit_pct / 100 if take_profit_pct and take_profit_pct > 0 else 0

    for i in range(len(closes)):
        date = closes.index[i]
        price = float(closes.iloc[i])

        # Check stop-loss / take-profit if in position
        if position > 0:
            change = (price - entry_price) / entry_price
            if (sl > 0 and change <= -sl) or (tp > 0 and change >= tp):
                # Exit by SL/TP
                sell_value = position * price
                fee = sell_value * fees
                cash += sell_value - fee
                pnl = (price - entry_price) * position - (entry_price * position * fees) - fee
                trades.append({
                    'entry_date': entry_date.strftime('%Y-%m-%d') if hasattr(entry_date, 'strftime') else str(entry_date)[:10],
                    'exit_date': date.strftime('%Y-%m-%d') if hasattr(date, 'strftime') else str(date)[:10],
                    'entry_price': round(entry_price, 2),
                    'exit_price': round(price, 2),
                    'size': round(position, 2),
                    'pnl': round(pnl, 2),
                    'return_pct': round(change * 100, 2),
                    'direction': 'Long',
                })
                position = 0.0
                entry_price = 0.0
                entry_date = None

        # Process exit signal (sell all)
        if position > 0 and exits.iloc[i]:
            sell_value = position * price
            fee = sell_value * fees
            cash += sell_value - fee
            change = (price - entry_price) / entry_price
            pnl = (price - entry_price) * position - (entry_price * position * fees) - fee
            trades.append({
                'entry_date': entry_date.strftime('%Y-%m-%d') if hasattr(entry_date, 'strftime') else str(entry_date)[:10],
                'exit_date': date.strftime('%Y-%m-%d') if hasattr(date, 'strftime') else str(date)[:10],
                'entry_price': round(entry_price, 2),
                'exit_price': round(price, 2),
                'size': round(position, 2),
                'pnl': round(pnl, 2),
                'return_pct': round(change * 100, 2),
                'direction': 'Long',
            })
            position = 0.0
            entry_price = 0.0
            entry_date = None

        # Process entry signal (buy)
        if position == 0 and entries.iloc[i]:
            fee_factor = 1 + fees
            shares = math.floor(cash / (price * fee_factor))
            if shares > 0:
                cost = shares * price
                fee = cost * fees
                cash -= cost + fee
                position = float(shares)
                entry_price = price
                entry_date = date

        # Record equity
        portfolio_value = cash + position * price
        equity_values.append(portfolio_value)
        equity_dates.append(date)

    equity = pd.Series(equity_values, index=equity_dates)

    # ── Compute metrics ──
    total_return_pct = ((equity.iloc[-1] / initial_capital) - 1) * 100 if len(equity) > 0 else 0

    # Max drawdown
    running_max = equity.cummax()
    drawdown = (equity - running_max) / running_max
    max_drawdown_pct = abs(float(drawdown.min())) * 100 if len(drawdown) > 0 else 0

    # Sharpe ratio (annualized, assuming 252 trading days)
    daily_returns = equity.pct_change().dropna()
    if len(daily_returns) > 1 and daily_returns.std() > 0:
        sharpe = (daily_returns.mean() / daily_returns.std()) * np.sqrt(252)
    else:
        sharpe = 0.0

    # Win rate
    total_trades = len(trades)
    winning_trades = [t for t in trades if t['pnl'] > 0]
    losing_trades = [t for t in trades if t['pnl'] < 0]
    win_rate = (len(winning_trades) / total_trades * 100) if total_trades > 0 else 0

    # Profit factor
    total_wins = sum(t['pnl'] for t in winning_trades)
    total_losses = abs(sum(t['pnl'] for t in losing_trades))
    if total_losses > 0:
        profit_factor = round(total_wins / total_losses, 2)
    elif total_wins > 0:
        profit_factor = 999.99
    else:
        profit_factor = 0

    return {
        'equity': equity,
        'drawdown': drawdown,
        'trades': trades,
        'total_return_pct': round(_safe_val(total_return_pct), 2),
        'max_drawdown_pct': round(_safe_val(max_drawdown_pct), 2),
        'sharpe_ratio': round(_safe_val(sharpe), 2),
        'win_rate': round(_safe_val(win_rate), 2),
        'total_trades': total_trades,
        'profit_factor': profit_factor,
    }


# ─── Main Backtest Functions ─────────────────────────────────────────

def run_backtest(ticker, strategy_type, params, period='2y',
                 initial_capital=100_000_000, fees_pct=0.15,
                 stop_loss_pct=0, take_profit_pct=0):
    """
    Run a backtest for a given ticker and strategy.

    Args:
        ticker: Stock ticker (e.g., 'BBCA.JK')
        strategy_type: 'rsi', 'macd', 'ema_cross', 'combined', 'bollinger', 'custom'
        params: Strategy-specific parameters dict
        period: Historical period ('1y', '2y', '3y', '5y')
        initial_capital: Starting capital
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
        # 1. Fetch historical data
        tickers = [_normalize_ticker(t) for t in ticker.split(',')]

        if len(tickers) == 1:
            stock = yf.Ticker(tickers[0])
            try:
                hist = stock.history(period=period)
            except (TypeError, KeyError, ValueError):
                return {'success': False, 'error': f'No data available for {tickers[0]}. Ticker may be invalid or delisted.'}
        else:
            try:
                hist = yf.download(tickers, period=period, progress=False)
            except (TypeError, KeyError, ValueError):
                return {'success': False, 'error': 'No data available for one or more tickers. Some may be invalid or delisted.'}

        if hist.empty or len(hist) < 50:
            return {'success': False, 'error': f'Insufficient data for {ticker} ({period})'}

        # Extract closes as 1D Series
        if isinstance(hist, pd.DataFrame):
            if getattr(hist.columns, 'nlevels', 1) > 1:
                closes = hist['Close'].iloc[:, 0]
            elif 'Close' in hist.columns:
                closes = hist['Close']
            else:
                closes = hist.iloc[:, 0]
        else:
            closes = hist

        if isinstance(closes, pd.DataFrame):
            closes = closes.iloc[:, 0]

        # 2. Generate entry/exit signals
        entries, exits = _generate_signals(hist, strategy_type, params)

        # Check if any signals were generated
        has_signals = entries.any()

        if not has_signals:
            bh_ret = round(((closes.iloc[-1] / closes.iloc[0]) - 1) * 100, 2)
            return {
                'success': True,
                'resolved_ticker': ', '.join(tickers),
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

        # 3. Run pandas backtest simulation
        fees = fees_pct / 100
        bt = _run_pandas_backtest(
            closes, entries, exits, initial_capital, fees,
            stop_loss_pct=stop_loss_pct, take_profit_pct=take_profit_pct
        )

        # Buy & Hold comparison
        buy_hold_return = round(((closes.iloc[-1] / closes.iloc[0]) - 1) * 100, 2)

        # 4. Equity curve (sampled for chart)
        equity = bt['equity']
        step = max(1, len(equity) // 500) if len(equity) > 500 else 1
        equity_sampled = equity.iloc[::step]
        equity_dates = [d.strftime('%Y-%m-%d') for d in equity_sampled.index]
        equity_values = [round(_safe_val(v), 0) for v in equity_sampled.values]

        # 5. Drawdown curve
        drawdown = bt['drawdown']
        dd_sampled = drawdown.iloc[::step]
        dd_dates = [d.strftime('%Y-%m-%d') for d in dd_sampled.index]
        dd_values = [round(_safe_val(v) * 100, 2) for v in dd_sampled.values]

        # 6. Price data for chart
        price_sampled = closes.iloc[::step]
        price_dates = [d.strftime('%Y-%m-%d') for d in price_sampled.index]
        price_values = [round(_safe_val(v), 0) for v in price_sampled.values]

        # 7. Benchmark — auto-detect based on ticker market
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
                        bm_close = bm_clipped['Close']
                        if isinstance(bm_close, pd.DataFrame):
                            bm_close = bm_close.iloc[:, 0]
                        bm_norm = (bm_close / bm_close.iloc[0]) * initial_capital
                        bm_step = max(1, len(bm_norm) // 500) if len(bm_norm) > 500 else 1
                        bm_sampled = bm_norm.iloc[::bm_step]
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

        return {
            'success': True,
            'resolved_ticker': ', '.join(tickers),
            'currency': currency,
            'benchmark_name': bm_name,
            'summary': {
                'total_return_pct': float(bt['total_return_pct']),
                'win_rate': float(bt['win_rate']),
                'max_drawdown_pct': float(round(-abs(bt['max_drawdown_pct']), 2)),
                'sharpe_ratio': float(bt['sharpe_ratio']),
                'total_trades': int(bt['total_trades']),
                'profit_factor': float(bt['profit_factor']),
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
            'monthly_returns': _compute_monthly_returns(equity),
            'trades': bt['trades'],
        }

    except Exception as e:
        logger.exception(f"Backtest error for {ticker}")
        return {'success': False, 'error': str(e)}


def _compute_monthly_returns(equity):
    """Compute monthly return matrix {year: {month: return%}}."""
    try:
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
        except (TypeError, KeyError, ValueError):
            return {'success': False, 'error': f'No data available for {clean_ticker}. Ticker may be invalid or delisted.'}
        if hist.empty or len(hist) < 50:
            return {'success': False, 'error': f'Insufficient data for {clean_ticker}'}

        closes = hist['Close']
        if isinstance(closes, pd.DataFrame):
            closes = closes.iloc[:, 0]
        fees = fees_pct / 100

        # Build all param combinations
        combos = []

        if strategy_type == 'rsi':
            entry_vals = param_ranges.get('rsi_entry', [30])
            exit_vals = param_ranges.get('rsi_exit', [70])
            for ev, xv in product(entry_vals, exit_vals):
                if ev >= xv:
                    continue
                combos.append({'rsi_entry': ev, 'rsi_exit': xv})

        elif strategy_type == 'macd':
            fast_vals = param_ranges.get('macd_fast', [12])
            slow_vals = param_ranges.get('macd_slow', [26])
            signal_vals = param_ranges.get('macd_signal', [9])
            for f, s, sig in product(fast_vals, slow_vals, signal_vals):
                if f >= s:
                    continue
                combos.append({'macd_fast': f, 'macd_slow': s, 'macd_signal': sig})

        elif strategy_type == 'ema_cross':
            short_vals = param_ranges.get('ema_short', [12])
            long_vals = param_ranges.get('ema_long', [26])
            for sv, lv in product(short_vals, long_vals):
                if sv >= lv:
                    continue
                combos.append({'ema_short': sv, 'ema_long': lv})

        elif strategy_type == 'bollinger':
            period_vals = param_ranges.get('bb_period', [20])
            std_vals = param_ranges.get('bb_std', [2.0])
            for p, sd in product(period_vals, std_vals):
                combos.append({'bb_period': p, 'bb_std': sd})
        else:
            return {'success': False, 'error': f'Optimization not supported for: {strategy_type}'}

        if not combos:
            return {'success': False, 'error': 'No valid parameter combinations generated'}

        # Run backtest for each combo
        results = []
        for combo in combos:
            entries, exits = _generate_signals(closes, strategy_type, combo)
            if not entries.any():
                results.append({
                    **combo,
                    'total_return_pct': 0,
                    'sharpe_ratio': 0,
                    'max_drawdown_pct': 0,
                    'total_trades': 0,
                })
                continue

            bt = _run_pandas_backtest(closes, entries, exits, initial_capital, fees)
            results.append({
                **combo,
                'total_return_pct': bt['total_return_pct'],
                'sharpe_ratio': bt['sharpe_ratio'],
                'max_drawdown_pct': round(-abs(bt['max_drawdown_pct']), 2),
                'total_trades': bt['total_trades'],
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
        except (TypeError, KeyError, ValueError):
            return {'success': False, 'error': f'No data available for {clean_ticker}. Ticker may be invalid or delisted.'}
        if hist.empty or len(hist) < 100:
            return {'success': False, 'error': f'Insufficient data for {clean_ticker} (need 100+ days)'}

        closes = hist['Close']
        if isinstance(closes, pd.DataFrame):
            closes = closes.iloc[:, 0]

        # Split into train/test
        split_idx = int(len(closes) * train_pct / 100)
        train_closes = closes.iloc[:split_idx]
        test_closes = closes.iloc[split_idx:]

        if len(train_closes) < 50 or len(test_closes) < 20:
            return {'success': False, 'error': 'Not enough data after split. Use longer period.'}

        fees = fees_pct / 100

        # ── Phase 1: Optimize on training data ──
        combos = []

        if strategy_type == 'rsi':
            entry_vals = param_ranges.get('rsi_entry', [30])
            exit_vals = param_ranges.get('rsi_exit', [70])
            rsi_period = int(param_ranges.get('rsi_period', [14])[0]) if isinstance(param_ranges.get('rsi_period'), list) else 14
            for ev, xv in product(entry_vals, exit_vals):
                if ev >= xv:
                    continue
                combos.append({'rsi_period': rsi_period, 'rsi_entry': ev, 'rsi_exit': xv})

        elif strategy_type == 'macd':
            fast_vals = param_ranges.get('macd_fast', [12])
            slow_vals = param_ranges.get('macd_slow', [26])
            signal_vals = param_ranges.get('macd_signal', [9])
            for f, s, sig in product(fast_vals, slow_vals, signal_vals):
                if f >= s:
                    continue
                combos.append({'macd_fast': f, 'macd_slow': s, 'macd_signal': sig})

        elif strategy_type == 'ema_cross':
            short_vals = param_ranges.get('ema_short', [12])
            long_vals = param_ranges.get('ema_long', [26])
            for sv, lv in product(short_vals, long_vals):
                if sv >= lv:
                    continue
                combos.append({'ema_short': sv, 'ema_long': lv})

        elif strategy_type == 'bollinger':
            period_vals = param_ranges.get('bb_period', [20])
            std_vals = param_ranges.get('bb_std', [2.0])
            for p, sd in product(period_vals, std_vals):
                combos.append({'bb_period': p, 'bb_std': sd})
        else:
            return {'success': False, 'error': f'Walk-forward not supported for: {strategy_type}'}

        if not combos:
            return {'success': False, 'error': 'No valid parameter combinations'}

        # Run backtest for each combo on training data
        best_sharpe = -999
        best_idx = 0
        train_results = []

        for i, combo in enumerate(combos):
            entries, exits = _generate_signals(train_closes, strategy_type, combo)
            if not entries.any():
                train_results.append({
                    'total_return_pct': 0, 'sharpe_ratio': 0,
                    'max_drawdown_pct': 0, 'total_trades': 0,
                    'equity': pd.Series([initial_capital, initial_capital],
                                       index=[train_closes.index[0], train_closes.index[-1]]),
                })
                continue

            bt = _run_pandas_backtest(train_closes, entries, exits, initial_capital, fees)
            train_results.append(bt)
            if bt['sharpe_ratio'] > best_sharpe:
                best_sharpe = bt['sharpe_ratio']
                best_idx = i

        best_combo = combos[best_idx]
        best_train = train_results[best_idx]

        # In-sample metrics
        in_return = best_train['total_return_pct']
        in_sharpe = best_train['sharpe_ratio']
        in_dd = best_train['max_drawdown_pct']
        in_trades = best_train['total_trades']

        # In-sample equity curve
        in_equity = best_train['equity']
        in_step = max(1, len(in_equity) // 300) if len(in_equity) > 300 else 1
        in_eq_s = in_equity.iloc[::in_step]
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
            bt_test = _run_pandas_backtest(test_closes, test_entries, test_exits, initial_capital, fees)
            out_return = bt_test['total_return_pct']
            out_sharpe = bt_test['sharpe_ratio']
            out_dd = bt_test['max_drawdown_pct']
            out_trades = bt_test['total_trades']

            out_equity = bt_test['equity']
            out_step = max(1, len(out_equity) // 300) if len(out_equity) > 300 else 1
            out_eq_s = out_equity.iloc[::out_step]
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
