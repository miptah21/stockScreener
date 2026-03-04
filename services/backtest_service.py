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


def _generate_signals(closes, strategy_type, params):
    """
    Generate entry/exit boolean Series based on strategy type and params.

    Returns:
        (entries: pd.Series[bool], exits: pd.Series[bool])
    """
    n = len(closes)
    entries = pd.Series(False, index=closes.index)
    exits = pd.Series(False, index=closes.index)

    if strategy_type == 'rsi':
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

    valid_strategies = ('rsi', 'macd', 'ema_cross', 'combined', 'bollinger')
    if strategy_type not in valid_strategies:
        return {'success': False, 'error': f'Invalid strategy_type. Use: {valid_strategies}'}

    try:
        # 1. Fetch historical data
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period)

        if hist.empty or len(hist) < 50:
            return {'success': False, 'error': f'Insufficient data for {ticker} ({period})'}

        closes = hist['Close']

        # 2. Generate entry/exit signals
        entries, exits = _generate_signals(closes, strategy_type, params)

        # Check if any signals were generated
        if not entries.any():
            return {
                'success': True,
                'summary': {
                    'total_return_pct': 0,
                    'win_rate': 0,
                    'max_drawdown_pct': 0,
                    'sharpe_ratio': 0,
                    'total_trades': 0,
                    'profit_factor': 0,
                    'buy_hold_return_pct': round(
                        ((closes.iloc[-1] / closes.iloc[0]) - 1) * 100, 2
                    ),
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
                'message': 'Tidak ada sinyal trading yang dihasilkan. Coba sesuaikan parameter strategi.',
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
                profit_factor = round(winning / max(losing, 1), 2)
            else:
                profit_factor = 0
        except Exception:
            profit_factor = 0

        # Buy & Hold comparison
        buy_hold_return = round(
            ((closes.iloc[-1] / closes.iloc[0]) - 1) * 100, 2
        )

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
        if len(closes) > 500:
            price_sampled = closes.iloc[::step]
        else:
            price_sampled = closes
        price_dates = [d.strftime('%Y-%m-%d') for d in price_sampled.index]
        price_values = [round(_safe_val(v), 0) for v in price_sampled.values]

        # 8. Benchmark (IHSG / ^JKSE)
        benchmark_data = {'dates': [], 'values': []}
        try:
            ihsg = yf.Ticker('^JKSE').history(period=period)
            if not ihsg.empty and len(ihsg) > 10:
                ihsg_norm = (ihsg['Close'] / ihsg['Close'].iloc[0]) * initial_capital
                if len(ihsg_norm) > 500:
                    ihsg_sampled = ihsg_norm.iloc[::max(1, len(ihsg_norm) // 500)]
                else:
                    ihsg_sampled = ihsg_norm
                benchmark_data = {
                    'dates': [d.strftime('%Y-%m-%d') for d in ihsg_sampled.index],
                    'values': [round(_safe_val(v), 0) for v in ihsg_sampled.values],
                }
        except Exception:
            pass  # Non-critical, skip if fails

        # 9. Trade log
        trade_log = _extract_trades(portfolio)

        return {
            'success': True,
            'summary': {
                'total_return_pct': round(total_return, 2),
                'win_rate': round(win_rate, 2),
                'max_drawdown_pct': round(-abs(max_dd), 2),
                'sharpe_ratio': round(sharpe, 2),
                'total_trades': total_trades,
                'profit_factor': profit_factor,
                'buy_hold_return_pct': buy_hold_return,
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
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period)
        if hist.empty or len(hist) < 50:
            return {'success': False, 'error': f'Insufficient data for {ticker}'}

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
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period)
        if hist.empty or len(hist) < 100:
            return {'success': False, 'error': f'Insufficient data for {ticker} (need 100+ days)'}

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


