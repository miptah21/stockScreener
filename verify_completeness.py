
import sys
import os
import json

# Add project root to path
sys.path.append(os.getcwd())

from scraper import get_financials

ticker = "BBCA.JK"
print(f"Fetching {ticker} to check data completeness...")
result = get_financials(ticker)

completeness = result.get('data_completeness')
print(f"Completeness: {completeness} ({type(completeness)})")

if completeness is None:
    print("[FAIL] Completeness is None")
elif completeness == 0:
    print("[WARN] Completeness is 0.0")
else:
    print(f"[PASS] Completeness is {completeness:.2%}")
    
# Check raw years data just in case
print(f"Number of years: {len(result.get('data', []))}")
if result.get('data'):
    raw = result['data'][0].get('raw', {})
    print(f"Sample raw keys count: {len(raw)}")
