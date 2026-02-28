import sys
import os
sys.path.append(os.getcwd())
sys.stdout.reconfigure(encoding='utf-8')

from scraper import get_financials

def verify_cleanup(ticker):
    print(f"\n=== Verifying Data Cleanup for {ticker} ===")
    result = get_financials(ticker)
    
    if not result.get('success'):
        print(f"Failed to fetch data: {result.get('error')}")
        return

    company = result.get('company', {})
    print(f"Name: {company.get('name')}")
    print(f"Sector: {company.get('sector')}")
    print(f"Is Bank: {result.get('is_bank')}")
    
    if not result.get('data'):
        print("No yearly data found.")
        return

    latest_year = result['data'][0]
    raw = latest_year.get('raw', {})
    
    print("\n[Checking Raw Data Fields]")
    # These should be None for banks
    print(f"Gross Profit: {raw.get('gross_profit')}")
    print(f"Current Assets: {raw.get('current_assets')}")
    print(f"Current Liabilities: {raw.get('current_liabilities')}")
    
    # These should be Present
    print(f"Net Income: {raw.get('net_income')}")
    print(f"Interest Income: {raw.get('interest_income')}")

if __name__ == "__main__":
    verify_cleanup("BBRI.JK")
