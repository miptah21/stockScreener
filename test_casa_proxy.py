"""Verify Cost of Funds (Interest Expense / Liabilities) as CASA Proxy."""
import sys
sys.path.insert(0, '.')
from scraper import get_financials

TICKERS = ['BBCA.JK', 'PNLF.JK', 'BBRI.JK']
lines = []

for ticker in TICKERS:
    lines.append(f"\n{'='*60}")
    lines.append(f"TESTING: {ticker}")
    lines.append(f"{'='*60}")
    
    result = get_financials(ticker)
    
    if not result.get('success'):
        lines.append(f"  ERROR: {result.get('error')}")
        continue
    
    if not result.get('data'):
        lines.append("  No data found.")
        continue
        
    for i, year_data in enumerate(result['data']):
        raw = year_data['raw']
        metrics = year_data['metrics']
        
        int_exp = raw.get('interest_expense')
        # Try to find liabilities in raw if available, otherwise calculate from assets - equity
        tot_liab = raw.get('total_liabilities') # Use snake_case key from scraper
        if tot_liab is None and raw.get('total_assets') and raw.get('total_equity'):
             tot_liab = raw['total_assets'] - raw['total_equity']
             
        if tot_liab and int_exp is not None:
            # Cost of Funds = Int Exp / Liabilities
            cof = int_exp / tot_liab
            lines.append(f"  Year {year_data['year']}: Int Exp={int_exp:,.0f}, Liab={tot_liab:,.0f}, CoF={cof:.2%} (Proxy CASA Inverse)")
        else:
            lines.append(f"  Year {year_data['year']}: Data missing (Int Exp={int_exp}, Liab={tot_liab})")

output = "\n".join(lines)
print(output)

with open("test_casa_proxy.log", "w", encoding="utf-8") as f:
    f.write(output)
print("\nDone - see test_casa_proxy.log")
