
import yfinance as yf
from datetime import datetime

ticker_symbol = "NIKL.JK"
target_year = datetime.now().year - 1

print(f"Checking {ticker_symbol} for year {target_year}...")

try:
    ticker = yf.Ticker(ticker_symbol)
    income_stmt = ticker.income_stmt
    print("\nIncome Statement Columns:")
    if income_stmt is not None and not income_stmt.empty:
        print(income_stmt.columns)
        has_report = False
        for col in income_stmt.columns:
            if hasattr(col, 'year') and col.year >= target_year:
                print(f"Found report for year {col.year}")
                has_report = True
        
        if not has_report:
            print(f"No report found for {target_year} or later.")
    else:
        print("Income statement is empty or None.")

except Exception as e:
    print(f"Error: {e}")
