import sys
import os
sys.path.append(os.getcwd())
sys.stdout.reconfigure(encoding='utf-8')

from scraper import get_financials

def verify_bank(ticker):
    print(f"\n=== Verifying Bank Valuation for {ticker} ===")
    result = get_financials(ticker)
    
    if not result.get('success'):
        print(f"Failed to fetch data: {result.get('error')}")
        return

    print(f"Name: {result['company']['name']}")
    print(f"Sector: {result['company']['sector']}")
    print(f"Is Bank: {result['is_bank']}")
    print(f"PBV (Company Info): {result['company'].get('pbv')}")
    
    val = result.get('bank_valuation')
    if val:
        print("\n--- Bank Valuation Data ---")
        print(f"Available: {val['available']}")
        print(f"Current PBV: {val.get('pbv')}")
        print(f"Fair PBV: {val.get('fair_pbv')}")
        print(f"ROE Current: {val.get('roe_current')}")
        print(f"ROE Prev: {val.get('roe_prev')}")
        print(f"Status: {val.get('status')}")
        print(f"Verdict: {val.get('verdict')}")
    else:
        print("\n[!] Bank Valuation data missing!")

if __name__ == "__main__":
    # Test a known bank
    verify_bank("BBRI.JK")
    
    # Test a non-bank to ensure it doesn't have it
    # verify_bank("ASII.JK")
