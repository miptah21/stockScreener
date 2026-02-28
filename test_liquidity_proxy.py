"""Verify Cash Ratio and Retained Earnings as proxies for Bank Score. (Fixed)"""
import sys
sys.path.insert(0, '.')
from scraper import get_financials
import yfinance as yf

# TICKERS = ['BBCA.JK', 'Adira Dinamika Multi Finance Tbk', 'BBRI.JK']  
TICKERS = ['BBCA.JK', 'BBRI.JK', 'PNLF.JK']

lines = []

def _pct(val):
    return f"{val:.2%}" if val is not None else "N/A"
    
def _fmt(val):
    return f"{val:,.0f}" if val is not None else "N/A"

for ticker in TICKERS:
    lines.append(f"\n{'='*60}")
    lines.append(f"TESTING proxies for: {ticker}")
    lines.append(f"{'='*60}")
    
    result = get_financials(ticker)
    
    if not result.get('data'):
        lines.append("  No data found.")
        continue
        
    for i, year_data in enumerate(result['data']):
        raw = year_data['raw']
        
        # Cash Ratio Proxy (Cash / Assets)
        cash = raw.get('cash_financial')
        if not cash:
            cash = raw.get('cash_equivalents')
        assets = raw.get('total_assets')
        
        cash_ratio = None
        if cash and assets:
            cash_ratio = cash / assets
            
        # Retained Earnings Proxy (Safety Buffer)
        re = raw.get('retained_earnings')
        re_ratio = None
        if re and assets:
            re_ratio = re / assets
            
        try:
            prev_re = result['data'][i+1]['raw'].get('retained_earnings')
            re_growth = (re - prev_re)/prev_re if re and prev_re else None
        except:
            re_growth = None

        lines.append(f"  Year {year_data['year']}:")
        lines.append(f"    Cash/Asset (Liq): {_pct(cash_ratio)} (Cash={_fmt(cash)} / Ast={_fmt(assets)})")
        lines.append(f"    RE/Asset (Safety): {_pct(re_ratio)} (RE={_fmt(re)})")
        lines.append(f"    RE Growth: {_pct(re_growth)}")

output = "\n".join(lines)
print(output)

with open("test_liquidity_proxy.log", "w", encoding="utf-8") as f:
    f.write(output)
