import yfinance as yf
import pandas as pd
from datetime import datetime

logger_tickers = ['BBCA.JK', 'ASII.JK', 'TLKM.JK']

def debug_ticker(symbol):
    print(f"--- Debugging {symbol} ---")
    t = yf.Ticker(symbol)
    
    try:
        # Fast Info check
        print(f"Fast Info Last Price: {t.fast_info.last_price}")
    except Exception as e:
        print(f"Fast Info Error: {e}")

    try:
        # Income Stmt check
        inc = t.income_stmt
        if inc is None or inc.empty:
            print("Income Statement is None or Empty")
        else:
            print("Income Statement Columns:", inc.columns)
            latest = inc.columns[0]
            print(f"Latest Report Date: {latest}")
            if hasattr(latest, 'year'):
                print(f"Latest Year: {latest.year}")
            else:
                print(f"Latest column type: {type(latest)}")
    except Exception as e:
        print(f"Income Stmt Error: {e}")
    print("\n")

if __name__ == "__main__":
    for tick in logger_tickers:
        debug_ticker(tick)
