import yfinance as yf
import pandas as pd

logger_tickers = ['BBCA.JK', 'ASII.JK', 'TLKM.JK', 'AAPL']

def debug_ticker_quarterly(symbol):
    print(f"--- Debugging {symbol} ---")
    t = yf.Ticker(symbol)
    
    try:
        # Annual
        inc = t.income_stmt
        if inc is not None and not inc.empty:
            print(f"Annual Columns: {inc.columns}")
        else:
            print("Annual: None")
            
        # Quarterly
        q_inc = t.quarterly_income_stmt
        if q_inc is not None and not q_inc.empty:
            print(f"Quarterly Columns: {q_inc.columns}")
            latest = q_inc.columns[0]
            print(f"Latest Quarterly: {latest}")
        else:
            print("Quarterly: None")

    except Exception as e:
        print(f"Error: {e}")
    print("\n")

if __name__ == "__main__":
    for tick in logger_tickers:
        debug_ticker_quarterly(tick)
