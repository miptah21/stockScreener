
import logging
from screener import _check_single_ticker
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO)

ticker = "NIKL.JK"
target_year = datetime.now().year - 1

print(f"Testing Screener Fallback for {ticker} (Year: {target_year})...")

# Run the check
result = _check_single_ticker(ticker, target_year)

print("\nResult:")
print(f"Ticker: {result['ticker']}")
print(f"Has Report: {result['has_current_year_report']}")
print(f"Source: {result.get('source', 'Unknown')}")
print(f"Latest Year: {result['latest_report_year']}")

if result['status'] == 'error':
    print(f"Error: {result.get('error')}")
    
# Verification
if result['has_current_year_report']:
    print("\nSUCCESS: Report detected!")
else:
    print("\nFAILURE: Report NOT detected.")
