
import yfinance as yf
from datetime import datetime

ticker = yf.Ticker("NIKL.JK")

print("Checking Earnings Dates...")
try:
    dates = ticker.earnings_dates
    if dates is not None and not dates.empty:
        print(dates.head())
    else:
        print("No earnings dates found.")
except Exception as e:
    print(f"Earnings Dates Error: {e}")

print("\nChecking News...")
try:
    news = ticker.news
    if news:
        for n in news:
            print(f" - {n.get('title')} ({n.get('providerPublishTime')})")
    else:
        print("No news found.")
except Exception as e:
    print(f"News Error: {e}")

print("\nChecking Calendar...")
try:
    cal = ticker.calendar
    if cal:
        print(cal)
    else:
        print("No calendar found.")
except Exception as e:
    print(f"Calendar Error: {e}")
