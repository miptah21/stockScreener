
import logging
from screener import _check_single_ticker
from datetime import datetime
import traceback

# Setup logging
logging.basicConfig(level=logging.INFO)

tickers = ['GHON.JK', 'JAST.JK']
target_year = 2025

print(f"--- Debugging Errors for {tickers} ---")

for t in tickers:
    print(f"\nChecking {t}...")
    try:
        result = _check_single_ticker(t, target_year)
        print(f"Result Status: {result['status']}")
        if result['status'] == 'error':
            print(f"Error Message: {result.get('error')}")
            # We want to see the stack trace if possible, but _check_single_ticker catches it.
            # So we will try to run the logic manually below to catch the trace.
            
            print(f"\n--- Manual Trace for {t} ---")
            import yfinance as yf
            ticker = yf.Ticker(t)
            try:
                print("Attempting to fetch income_stmt...")
                stmt = ticker.income_stmt
                print("Income stmt fetch success.")
            except Exception:
                print("Exception during income_stmt fetch:")
                traceback.print_exc()
                
    except Exception as e:
        print(f"Unexpected external error: {e}")
        traceback.print_exc()
