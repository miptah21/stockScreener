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

    if strategy_type not in ('rsi', 'macd', 'ema_cross', 'combined'):
        return {'success': False, 'error': 'Invalid strategy_type'}

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
            'trades': trade_log,
        }

    except Exception as e:
        logger.exception(f"Backtest error for {ticker}")
        return {'success': False, 'error': str(e)}

