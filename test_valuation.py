"""Test _calculate_financial_valuation for all financial subsectors."""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, '.')
from scraper import _calculate_financial_valuation

lines = []

def test(name, result, checks):
    ok = all(checks)
    status = "PASS" if ok else "FAIL"
    lines.append(f"  [{status}] {name}")
    if not ok:
        lines.append(f"         Result: {result}")

# ═══ 1. Bank (COE = 10%) ═══
lines.append("\n═══ Bank Subsector ═══")
r = _calculate_financial_valuation(1.0, 0.15, 0.14, subsector='bank')
test("Bank default COE = 10%", r, [r['cost_of_equity'] == 0.10])
test("Bank icon = 🏦", r, [r['icon'] == '🏦'])
test("Bank title = Bank Valuation", r, [r['title'] == 'Bank Valuation'])
test("Bank Fair PBV = ROE/COE = 1.5", r, [abs(r['fair_pbv'] - 1.5) < 0.01])
test("Bank Undervalued (PBV 1.0 < Fair 1.5*0.8=1.2)", r, [r['status'] == 'Undervalued'])
test("Bank BUY (ROE > COE)", r, [r['verdict'] == 'BUY / Accumulate'])

# ═══ 2. Insurance (COE = 12%) ═══
lines.append("\n═══ Insurance Subsector ═══")
r = _calculate_financial_valuation(2.0, 0.18, 0.16, subsector='insurance')
test("Insurance default COE = 12%", r, [r['cost_of_equity'] == 0.12])
test("Insurance icon = 🛡️", r, [r['icon'] == '🛡️'])
test("Insurance title", r, [r['title'] == 'Insurance Valuation'])
test("Insurance Fair PBV = 0.18/0.12 = 1.5", r, [abs(r['fair_pbv'] - 1.5) < 0.01])

# ═══ 3. Leasing (COE = 13%) ═══
lines.append("\n═══ Leasing Subsector ═══")
r = _calculate_financial_valuation(0.3, 0.08, 0.10, subsector='leasing')
test("Leasing default COE = 13%", r, [r['cost_of_equity'] == 0.13])
test("Leasing icon = 🏢", r, [r['icon'] == '🏢'])
test("Leasing title", r, [r['title'] == 'Leasing Valuation'])
test("Leasing Value Trap (ROE < COE, Undervalued)", r, [r['verdict'] == 'Value Trap Risk'])
test("Leasing entity in Premium desc", True, ['multifinance' in _calculate_financial_valuation(3.0, 0.20, 0.18, subsector='leasing')['description']])

# ═══ 4. Securities (COE = 14%) ═══
lines.append("\n═══ Securities Subsector ═══")
r = _calculate_financial_valuation(3.0, 0.20, 0.22, subsector='securities')
test("Securities default COE = 14%", r, [r['cost_of_equity'] == 0.14])
test("Securities icon = 📊", r, [r['icon'] == '📊'])
test("Securities title", r, [r['title'] == 'Securities Valuation'])
test("Securities ROE trend Menurun (0.20 < 0.22*0.95)", r, [r['roe_trend'] == 'Menurun'])

# ═══ 5. Edge Cases ═══
lines.append("\n═══ Edge Cases ═══")
r = _calculate_financial_valuation(None, 0.15, 0.14, subsector='bank')
test("None PBV → not available", r, [r['available'] == False])
test("None PBV still has icon", r, [r['icon'] == '🏦'])

r = _calculate_financial_valuation(1.0, None, 0.14, subsector='insurance')
test("None ROE → not available", r, [r['available'] == False])
test("None ROE still has icon", r, [r['icon'] == '🛡️'])

# ═══ 6. Custom COE Override ═══
lines.append("\n═══ Custom COE Override ═══")
r = _calculate_financial_valuation(1.0, 0.15, 0.14, subsector='bank', cost_of_equity=0.20)
test("Custom COE overrides default", r, [r['cost_of_equity'] == 0.20])
test("Fair PBV uses custom COE", r, [abs(r['fair_pbv'] - 0.75) < 0.01])

# === Summary ===
output = "\n".join(lines)
passes = output.count("[PASS]")
fails = output.count("[FAIL]")

summary = f"\n{'='*40}\nTOTAL: {passes} passed, {fails} failed\n"
if fails == 0:
    summary += "All tests passed!\n"

# Write to file for reliable output on Windows
with open("test_valuation_output.txt", "w", encoding="utf-8") as f:
    f.write(output + summary)

try:
    print(output + summary)
except Exception:
    print(f"(output written to test_valuation_output.txt)")
    print(f"TOTAL: {passes} passed, {fails} failed")

if fails > 0:
    sys.exit(1)
