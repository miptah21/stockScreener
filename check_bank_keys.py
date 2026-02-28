"""Check for Loan/Deposit/Allowance keys in Yahoo Finance data."""
import sys
sys.path.insert(0, '.')
from scraper import get_financials
import yfinance as yf

TICKER = 'BBCA.JK'

print(f"Checking keys for {TICKER}...")
t = yf.Ticker(TICKER)
bs = t.balance_sheet
inc = t.income_stmt

def find_keys(df, keywords):
    found = []
    for key in df.index:
        key_lower = str(key).lower()
        for kw in keywords:
            if kw in key_lower:
                val = df.loc[key].iloc[0] if not df.loc[key].empty else 'Empty'
                found.append(f"{key}: {val}")
    return found

keywords = ['loan', 'deposit', 'allowance', 'provision', 'reserve', 'impairment', 'credit', 'financing', 'customer']

print("\n--- Balance Sheet Matches ---")
matches_bs = find_keys(bs, keywords)
for m in matches_bs:
    print(m)
    
print("\n--- Income Statement Matches ---")
matches_inc = find_keys(inc, keywords)
for m in matches_inc:
    print(m)

result = get_financials(TICKER)
if result.get('data'):
    raw = result['data'][0].get('raw', {})
    print("\n--- Scraper Raw Keys ---")
    keys_raw = sorted(raw.keys())
    # print only bank relevant ones
    relevant = [k for k in keys_raw if any(x in k for x in keywords)]
    print(relevant)
