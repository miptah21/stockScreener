
import yfinance as yf
from screener import _check_idx_official, _check_news_for_report
from datetime import datetime

tickers = ['EXCL.JK', 'BBRI.JK']
target_year = 2025

print(f"--- Debugging Data for FY{target_year} ---")

for t in tickers:
    print(f"\nChecking {t}...")
    try:
        tick = yf.Ticker(t)
        
        # 1. Check Income Statement
        inc = tick.income_stmt
        print(f"Yahoo Finance Income Stmt Columns: {inc.columns if inc is not None else 'None'}")
        
        has_yahoo = False
        if inc is not None and not inc.empty:
            for col in inc.columns:
                if hasattr(col, 'year') and col.year >= target_year:
                    print(f"Found Yahoo data for year: {col.year}")
                    has_yahoo = True
        
        if not has_yahoo:
            print(f"Yahoo Finance: No data for {target_year}")

        # 2. Check IDX API
        print("Checking IDX Website API...")
        idx_status = _check_idx_official(t, target_year)
        print(f"IDX API Result: {idx_status} (Note: might be False if 403 Forbidden)")

        # 3. Check News
        print("Checking News...")
        news_status = _check_news_for_report(tick, target_year)
        print(f"News Search Result: {news_status}")

    except Exception as e:
        print(f"Error checking {t}: {e}")
