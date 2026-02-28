"""
Detailed verification of Bank Quality Score calculations for BBCA.JK.
Prints raw data, intermediate values, and final pass/fail for each criterion.
"""
import sys
sys.path.insert(0, '.')
from scraper import get_financials

result = get_financials('BBCA.JK')

if not result.get('success'):
    print(f"ERROR: {result.get('error')}")
    sys.exit(1)

data = result['data']
if len(data) < 2:
    print("ERROR: Need at least 2 years of data")
    sys.exit(1)

curr = data[0]
prev = data[1]
cm = curr['metrics']
pm = prev['metrics']
cr = curr['raw']
pr = prev['raw']

lines = []
lines.append(f"{'='*70}")
lines.append(f"BANK QUALITY SCORE — DETAIL VERIFICATION: BBCA.JK")
lines.append(f"Current Year: {curr['year']}  |  Previous Year: {prev['year']}")
lines.append(f"{'='*70}")

# Piotroski result
pio = result['piotroski']
lines.append(f"\nScore: {pio['score']} / {pio['max_score']}  ({pio['strength']})")
lines.append(f"Score Label: {pio['score_label']}")
lines.append("")

# === RAW DATA ===
lines.append(f"{'─'*70}")
lines.append("RAW DATA (current vs previous)")
lines.append(f"{'─'*70}")

raw_keys = [
    'net_income', 'total_revenue', 'total_assets', 'total_equity',
    'total_liabilities', 'interest_income', 'interest_expense',
    'operating_income', 'total_operating_expense', 'write_off',
    'retained_earnings', 'cash_financial', 'shares_outstanding',
]
for k in raw_keys:
    cv = cr.get(k)
    pv = pr.get(k)
    cv_s = f"{cv:,.0f}" if cv is not None else "None"
    pv_s = f"{pv:,.0f}" if pv is not None else "None"
    lines.append(f"  {k:30s}  curr={cv_s:>20s}  prev={pv_s:>20s}")

# === METRICS ===
lines.append(f"\n{'─'*70}")
lines.append("COMPUTED METRICS (current vs previous)")
lines.append(f"{'─'*70}")

metric_keys = ['roa', 'nim', 'roe', 'bopo', 'cost_of_funds', 'coc',
               'cash_flow', 'net_income', 'accrual', 'lt_debt_ratio',
               'current_ratio', 'gross_margin', 'asset_turnover']
for k in metric_keys:
    cv = cm.get(k)
    pv = pm.get(k)
    cv_s = f"{cv*100:.4f}%" if cv is not None else "None"
    pv_s = f"{pv*100:.4f}%" if pv is not None else "None"
    lines.append(f"  {k:30s}  curr={cv_s:>14s}  prev={pv_s:>14s}")

# === CRITERION-BY-CRITERION ===
lines.append(f"\n{'='*70}")
lines.append("CRITERION-BY-CRITERION VERIFICATION")
lines.append(f"{'='*70}")

for c in pio['criteria']:
    status = "✓ PASS" if c['passed'] else "✗ FAIL"
    lines.append(f"\n  #{c['id']:2d}. {c['name']}")
    lines.append(f"      Category: {c['category']}")
    lines.append(f"      Result:   {status}")
    lines.append(f"      Detail:   {c['description']}")

# Manual re-calculations
lines.append(f"\n{'='*70}")
lines.append("MANUAL RE-CALCULATION CHECK")
lines.append(f"{'='*70}")

# 1. ROA Positif
roa = cm.get('roa')
lines.append(f"\n#1 ROA Positif:")
lines.append(f"   net_income={cr.get('net_income')}  total_assets={cr.get('total_assets')}")
if cr.get('net_income') and cr.get('total_assets'):
    manual_roa = cr['net_income'] / cr['total_assets']
    lines.append(f"   Manual ROA = {manual_roa*100:.4f}%  |  Stored = {roa*100:.4f}% if roa else 'None'")
    lines.append(f"   Match: {abs(manual_roa - roa) < 1e-10 if roa else False}")

# 2. ROA Meningkat
lines.append(f"\n#2 ROA Meningkat:")
roa_p = pm.get('roa')
lines.append(f"   Current ROA = {roa*100:.4f}%" if roa else "   Current ROA = None")
lines.append(f"   Previous ROA = {roa_p*100:.4f}%" if roa_p else "   Previous ROA = None")
if roa is not None and roa_p is not None:
    lines.append(f"   Increasing? {roa > roa_p}")

# 3. CASA Ratio
cof = cm.get('cost_of_funds')
lines.append(f"\n#3 CASA Ratio (or Cost of Funds proxy):")
casa = cm.get('casa')
if casa:
     lines.append(f"   CASA = {casa*100:.4f}%")
     lines.append(f"   >= 50%? {casa >= 0.50}")
else:
    lines.append(f"   CASA not found, checking CoF proxy:")
    lines.append(f"   interest_expense={cr.get('interest_expense')}  total_liabilities={cr.get('total_liabilities')}")
    if cr.get('interest_expense') is not None and cr.get('total_liabilities'):
        manual_cof = cr['interest_expense'] / cr['total_liabilities']
        lines.append(f"   Manual CoF = {manual_cof*100:.4f}%  |  Stored = {cof*100:.4f}%" if cof else f"   Manual CoF = {manual_cof*100:.4f}%  |  Stored = None")

# 4. NPL (or CoC proxy)
npl = cm.get('npl')
coc_val = cm.get('coc')
lines.append(f"\n#4 NPL (or CoC proxy):")
if npl:
    lines.append(f"   NPL = {npl*100:.4f}%")
    lines.append(f"   < 5%? {npl < 0.05}")
else:
    lines.append(f"   NPL not found, checking CoC proxy:")
    lines.append(f"   write_off={cr.get('write_off')}  total_assets={cr.get('total_assets')}")
    if cr.get('write_off') is not None and cr.get('total_assets'):
        manual_coc = abs(cr['write_off']) / cr['total_assets']
        lines.append(f"   Manual CoC = |{cr['write_off']}| / {cr['total_assets']} = {manual_coc*100:.4f}%")
        lines.append(f"   < 5%? {manual_coc < 0.05}")

# 5. CoC Baik (or Stabil)
lines.append(f"\n#5 CoC Baik / Stabil:")
lines.append(f"   Stored CoC = {coc_val*100:.4f}%" if coc_val else "   Stored CoC = None")
if coc_val:
    lines.append(f"   <= 2%? {coc_val <= 0.02}")

# 6. CAR (Equity/Assets)
lines.append(f"\n#6 CAR (Equity/Assets):")
car = cm.get('car')
if car:
    lines.append(f"   CAR = {car*100:.4f}%")
    lines.append(f"   >= 12%? {car >= 0.12}")
elif cr.get('total_equity') and cr.get('total_assets'):
    eq_ratio = cr['total_equity'] / cr['total_assets']
    lines.append(f"   Equity/Assets = {cr['total_equity']:,.0f} / {cr['total_assets']:,.0f} = {eq_ratio*100:.4f}%")
    lines.append(f"   >= 12%? {eq_ratio >= 0.12}")

# 7. Coverage Ratio
lines.append(f"\n#7 Coverage Ratio:")
cov = cm.get('coverage_ratio') or cm.get('coverage')
if cov:
    lines.append(f"   Coverage = {cov*100:.4f}%")
    lines.append(f"   >= 100%? {cov >= 1.0}")
else:
    lines.append("   Coverage data not available")

# 8. NIM
lines.append(f"\n#8 NIM:")
nim_c = cm.get('nim')
nim_p = pm.get('nim')
lines.append(f"   Current NIM = {nim_c*100:.4f}%" if nim_c else "   Current NIM = None")
lines.append(f"   Previous NIM = {nim_p*100:.4f}%" if nim_p else "   Previous NIM = None")
if nim_c is not None and nim_p is not None:
    diff = nim_c - nim_p
    lines.append(f"   Diff = {diff*100:.4f}pp")
    lines.append(f"   Increasing? {nim_c > nim_p}")
    lines.append(f"   Stable (|diff| <= 0.5pp)? {abs(diff) <= 0.005}")

# 9. LDR
lines.append(f"\n#9 LDR:")
ldr = cm.get('ldr')
if ldr:
    lines.append(f"   LDR = {ldr*100:.4f}%")
    lines.append(f"   <= 92%? {ldr <= 0.92}")
else:
    cash = cr.get('cash_financial')
    assets = cr.get('total_assets')
    if cash is not None and assets:
        pseudo_ldr = (assets - cash) / assets
        lines.append(f"   Pseudo-LDR = (assets - cash) / assets = {pseudo_ldr*100:.4f}%")
        lines.append(f"   < 95%? {pseudo_ldr < 0.95}")

# 10. BOPO
lines.append(f"\n#10 BOPO:")
bopo_c = cm.get('bopo')
bopo_p = pm.get('bopo')
lines.append(f"   Current BOPO = {bopo_c*100:.4f}%" if bopo_c else "   Current BOPO = None")
lines.append(f"   Previous BOPO = {bopo_p*100:.4f}%" if bopo_p else "   Previous BOPO = None")
if bopo_c is not None and bopo_p is not None:
    lines.append(f"   Decreasing? {bopo_c < bopo_p}")

output = "\n".join(lines)
print(output)

with open("verify_bank_score.log", "w", encoding="utf-8") as f:
    f.write(output)
print("\n\nDone — see verify_bank_score.log")
