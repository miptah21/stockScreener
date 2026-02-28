
import sys
import os
import json

# Add project root to path
sys.path.append(os.getcwd())

# Import scraper
try:
    from scraper import get_financials, scrape_financials
except ImportError:
    print("Error importing scraper. Make sure you are in the project root.")
    sys.exit(1)

ticker = "BBCA.JK"

print(f"\n--- TEST 1: Fetching {ticker} WITHOUT target_year ---")
result1 = get_financials(ticker)
print(f"Success: {result1.get('success')}")
c1 = result1.get('company', {})
print(f"Sector: {c1.get('sector')}")
print(f"Industry: {c1.get('industry')}")
print(f"Data Length: {len(result1.get('data', []))}")
if result1.get('data'):
    print(f"Latest Year: {result1['data'][0].get('year')}")

print(f"\n--- TEST 2: Fetching {ticker} WITH target_year=2023 ---")
result2 = get_financials(ticker, target_year=2023)
print(f"Success: {result2.get('success')}")
c2 = result2.get('company', {})
print(f"Sector: {c2.get('sector')}")
print(f"Industry: {c2.get('industry')}")
print(f"Data Length: {len(result2.get('data', []))}")
if result2.get('data'):
    print(f"Latest Year (should be 2023): {result2['data'][0].get('year')}")
    
# Check for differences in sector/industry
if c1.get('sector') != c2.get('sector'):
    print("\n[FAIL] Sector mismatch between calls!")
else:
    print("\n[PASS] Sector consistent.")

if c1.get('industry') != c2.get('industry'):
    print("[FAIL] Industry mismatch between calls!")
else:
    print("[PASS] Industry consistent.")
    
# Save outputs for inspection
with open("repro_result1.json", "w") as f:
    json.dump(result1, f, default=str, indent=2)
with open("repro_result2.json", "w") as f:
    json.dump(result2, f, default=str, indent=2)
