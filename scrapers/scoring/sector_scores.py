"""
Sector-specific financial scoring.
Extracted from yahoo.py for modularity.
"""

import logging
from scrapers.scoring.utils import (
    _pct, _ratio, _fmt, _safe_divide, _format_number, _format_ratio,
)

logger = logging.getLogger(__name__)


def _calculate_insurance_score(yearly_data: list) -> dict:
    """
    Calculate Insurance Financial Score — 11 Kriteria.
    9 Kriteria Dasar (sama untuk Asuransi/Leasing/Sekuritas):
    1.  ROA > 0
    2.  Net Income YoY Growth > 0
    3.  Operating Cash Flow > 0
    4.  Equity Growth > 0
    5.  Debt to Equity tidak naik signifikan
    6.  Asset Growth positif
    7.  ROE > 10%
    8.  Net Margin stabil/naik
    9.  Expense Ratio membaik
    2 Kriteria Tambahan Asuransi:
    10. RBC proxy (Equity / Total Liabilities — solvency margin)
    11. Combined Ratio proxy (Underwriting Income / Premium Revenue)
    """
    if len(yearly_data) < 2:
        return {'available': False, 'reason': 'Butuh minimal 2 tahun data.'}
    current = yearly_data[0]
    previous = yearly_data[1]
    cm = current['metrics']
    pm = previous['metrics']
    cr = current['raw']
    pr = previous['raw']
    criteria = []
    total_score = 0
    # ── 1. ROA > 0 ──────────────────────────────────────────────────────────
    passed = cm['roa'] is not None and cm['roa'] > 0
    criteria.append({
        'id': 1, 'name': 'ROA Positif', 'category': 'Profitabilitas',
        'description': f"ROA: {_pct(cm['roa'])}. Harus positif.",
        'passed': passed
    })
    total_score += int(passed)
    # ── 2. Net Income YoY Growth > 0 ────────────────────────────────────────
    ni_curr = cr.get('net_income')
    ni_prev = pr.get('net_income')
    passed = (ni_curr is not None and ni_prev is not None and ni_curr > ni_prev)
    if ni_curr is not None and ni_prev is not None and ni_prev != 0:
        growth = (ni_curr - ni_prev) / abs(ni_prev) * 100
        desc = f"Net Income: {_fmt(ni_curr)} vs {_fmt(ni_prev)} (YoY: {growth:+.1f}%)"
    else:
        desc = f"Net Income: {_fmt(ni_curr)} vs {_fmt(ni_prev)}"
    criteria.append({
        'id': 2, 'name': 'Net Income Growth > 0', 'category': 'Profitabilitas',
        'description': desc, 'passed': passed
    })
    total_score += int(passed)
    # ── 3. Operating Cash Flow > 0 ──────────────────────────────────────────
    passed = cm['cash_flow'] is not None and cm['cash_flow'] > 0
    criteria.append({
        'id': 3, 'name': 'Cash Flow Operasi Positif', 'category': 'Profitabilitas',
        'description': f"CFO: {_fmt(cm['cash_flow'])}. Harus positif.",
        'passed': passed
    })
    total_score += int(passed)
    # ── 4. Equity Growth > 0 ────────────────────────────────────────────────
    eq_curr = cr.get('total_equity')
    eq_prev = pr.get('total_equity')
    passed = (eq_curr is not None and eq_prev is not None and eq_curr > eq_prev)
    if eq_curr is not None and eq_prev is not None and eq_prev != 0:
        growth = (eq_curr - eq_prev) / abs(eq_prev) * 100
        desc = f"Equity: {_fmt(eq_curr)} vs {_fmt(eq_prev)} (Growth: {growth:+.1f}%)"
    else:
        desc = f"Equity: {_fmt(eq_curr)} vs {_fmt(eq_prev)}"
    criteria.append({
        'id': 4, 'name': 'Equity Growth Positif', 'category': 'Solvabilitas',
        'description': desc, 'passed': passed
    })
    total_score += int(passed)
    # ── 5. Debt to Equity tidak naik signifikan ─────────────────────────────
    eq_c = cr.get('total_equity')
    eq_p = pr.get('total_equity')
    liab_curr = cr.get('total_liabilities')
    liab_prev = pr.get('total_liabilities')
    # Fallback: liabilities = assets - equity
    if liab_curr is None and cr.get('total_assets') and eq_c:
        liab_curr = cr['total_assets'] - eq_c
    if liab_prev is None and pr.get('total_assets') and eq_p:
        liab_prev = pr['total_assets'] - eq_p
    der_curr = liab_curr / eq_c if (liab_curr is not None and eq_c and eq_c != 0) else None
    der_prev = liab_prev / eq_p if (liab_prev is not None and eq_p and eq_p != 0) else None
    if der_curr is not None and der_prev is not None:
        # Naik signifikan = naik > 10%
        passed = der_curr <= der_prev * 1.10
        desc = f"DER: {der_curr:.2f}x vs {der_prev:.2f}x. {'Stabil/Turun.' if passed else 'Naik signifikan (>10%).'}"
    elif der_curr is not None:
        passed = der_curr < 3.0  # Threshold wajar untuk asuransi
        desc = f"DER: {der_curr:.2f}x. Trend tidak diketahui."
    else:
        passed = True
        desc = "Data DER tidak tersedia."
    criteria.append({
        'id': 5, 'name': 'DER Tidak Naik Signifikan', 'category': 'Leverage',
        'description': desc, 'passed': passed
    })
    total_score += int(passed)
    # ── 6. Asset Growth positif ─────────────────────────────────────────────
    ast_curr = cr.get('total_assets')
    ast_prev = pr.get('total_assets')
    passed = (ast_curr is not None and ast_prev is not None and ast_curr > ast_prev)
    if ast_curr is not None and ast_prev is not None and ast_prev != 0:
        growth = (ast_curr - ast_prev) / abs(ast_prev) * 100
        desc = f"Total Assets: {_fmt(ast_curr)} vs {_fmt(ast_prev)} (Growth: {growth:+.1f}%)"
    else:
        desc = f"Total Assets: {_fmt(ast_curr)} vs {_fmt(ast_prev)}"
    criteria.append({
        'id': 6, 'name': 'Asset Growth Positif', 'category': 'Pertumbuhan',
        'description': desc, 'passed': passed
    })
    total_score += int(passed)
    # ── 7. ROE > 10% ───────────────────────────────────────────────────────
    roe_curr = cm.get('roe')
    passed = roe_curr is not None and roe_curr > 0.10
    criteria.append({
        'id': 7, 'name': 'ROE > 10%', 'category': 'Profitabilitas',
        'description': f"ROE: {_pct(roe_curr)}. {'Baik (>10%).' if passed else 'Rendah (≤10%).' if roe_curr is not None else 'N/A.'}",
        'passed': passed
    })
    total_score += int(passed)
    # ── 8. Net Margin stabil/naik ───────────────────────────────────────────
    rev_curr = cr.get('total_revenue')
    rev_prev = pr.get('total_revenue')
    nm_curr = ni_curr / rev_curr if (ni_curr is not None and rev_curr and rev_curr != 0) else None
    nm_prev = ni_prev / rev_prev if (ni_prev is not None and rev_prev and rev_prev != 0) else None
    if nm_curr is not None and nm_prev is not None:
        diff = nm_curr - nm_prev
        passed = diff >= -0.005  # Toleransi 0.5 pp
        desc = f"Net Margin: {_pct(nm_curr)} vs {_pct(nm_prev)}. {'Stabil/Naik.' if passed else 'Menurun.'}"
    elif nm_curr is not None:
        passed = nm_curr > 0
        desc = f"Net Margin: {_pct(nm_curr)}. Trend tidak diketahui."
    else:
        passed = False
        desc = "Data Net Margin tidak tersedia."
    criteria.append({
        'id': 8, 'name': 'Net Margin Stabil / Naik', 'category': 'Efisiensi',
        'description': desc, 'passed': passed
    })
    total_score += int(passed)
    # ── 9. Expense Ratio membaik ────────────────────────────────────────────
    opex_curr = cr.get('total_operating_expense')
    opex_prev = pr.get('total_operating_expense')
    er_curr = opex_curr / rev_curr if (opex_curr is not None and rev_curr and rev_curr != 0) else None
    er_prev = opex_prev / rev_prev if (opex_prev is not None and rev_prev and rev_prev != 0) else None
    if er_curr is not None and er_prev is not None:
        passed = er_curr < er_prev
        desc = f"Expense Ratio: {_pct(er_curr)} vs {_pct(er_prev)}. {'Membaik (turun).' if passed else 'Memburuk (naik).'}"
    elif er_curr is not None:
        passed = er_curr < 0.85
        desc = f"Expense Ratio: {_pct(er_curr)}. Trend tidak diketahui."
    else:
        passed = False
        desc = "Data Expense Ratio tidak tersedia."
    criteria.append({
        'id': 9, 'name': 'Expense Ratio Membaik', 'category': 'Efisiensi',
        'description': desc, 'passed': passed
    })
    total_score += int(passed)
    # ── 10. RBC Proxy: Equity / Total Liabilities (Solvency Margin) ─────────
    # RBC (Risk Based Capital) minimum OJK = 120%. Proxy: Equity/Liabilities ≥ 33% (≈ RBC ~133%)
    rbc_proxy = eq_c / liab_curr if (eq_c and liab_curr and liab_curr != 0) else None
    rbc_prev = eq_p / liab_prev if (eq_p and liab_prev and liab_prev != 0) else None
    if rbc_proxy is not None:
        if rbc_proxy >= 0.33:
            passed = True
            desc = f"RBC Proxy (Equity/Liab): {_pct(rbc_proxy)}. Solvabilitas kuat (≥33%)."
        elif rbc_prev is not None and rbc_proxy > rbc_prev:
            passed = True
            desc = f"RBC Proxy: {_pct(rbc_proxy)} vs {_pct(rbc_prev)}. Meningkat."
        else:
            passed = False
            desc = f"RBC Proxy (Equity/Liab): {_pct(rbc_proxy)}. Rendah (<33%)."
    else:
        passed = False
        desc = "Data untuk proxy RBC tidak tersedia."
    criteria.append({
        'id': 10, 'name': 'RBC Proxy (Solvabilitas)', 'category': 'Solvabilitas Asuransi',
        'description': desc, 'passed': passed
    })
    total_score += int(passed)
    # ── 11. Combined Ratio Proxy: Underwriting Income / Premium Revenue ─────
    # Combined Ratio < 100% = underwriting profit. Proxy: (Revenue - Claims) / Revenue > 0
    claims_curr = cr.get('net_policyholder_claims')
    claims_prev = pr.get('net_policyholder_claims')
    if claims_curr is not None and rev_curr and rev_curr != 0:
        # Underwriting margin = (Revenue - Claims) / Revenue
        uw_margin_curr = (rev_curr - abs(claims_curr)) / rev_curr
        if claims_prev is not None and rev_prev and rev_prev != 0:
            uw_margin_prev = (rev_prev - abs(claims_prev)) / rev_prev
        else:
            uw_margin_prev = None
        if uw_margin_curr > 0:
            passed = True
            desc = f"Combined Ratio Proxy (UW Margin): {_pct(uw_margin_curr)}. Underwriting Profit."
        elif uw_margin_prev is not None and uw_margin_curr > uw_margin_prev:
            passed = True
            desc = f"Combined Ratio Proxy: {_pct(uw_margin_curr)} vs {_pct(uw_margin_prev)}. Membaik."
        else:
            passed = False
            desc = f"Combined Ratio Proxy (UW Margin): {_pct(uw_margin_curr)}. Underwriting Loss."
    else:
        # Fallback: loss_ratio if available
        lr = cm.get('loss_ratio')
        lr_prev_val = pm.get('loss_ratio')
        if lr is not None:
            passed = lr < 1.0
            if lr_prev_val is not None:
                desc = f"Loss Ratio (fallback): {_pct(lr)} vs {_pct(lr_prev_val)}. {'<100% = Profit.' if passed else '≥100% = Loss.'}"
            else:
                desc = f"Loss Ratio (fallback): {_pct(lr)}. {'<100% = Profit.' if passed else '≥100% = Loss.'}"
        else:
            passed = False
            desc = "Data klaim/premi tidak tersedia untuk proxy Combined Ratio."
    criteria.append({
        'id': 11, 'name': 'Combined Ratio Proxy', 'category': 'Underwriting Asuransi',
        'description': desc, 'passed': passed
    })
    total_score += int(passed)
    # Determine strength
    if total_score >= 9: strength = 'Sangat Kuat'; strength_color = 'emerald'
    elif total_score >= 7: strength = 'Kuat'; strength_color = 'blue'
    elif total_score >= 5: strength = 'Moderat'; strength_color = 'amber'
    else: strength = 'Lemah'; strength_color = 'rose'
    return {
        'available': True,
        'score': total_score,
        'max_score': 11,
        'strength': strength,
        'strength_color': strength_color,
        'current_year': current['year'],
        'previous_year': previous['year'],
        'criteria': criteria,
        'score_type': 'insurance',
        'score_label': 'Insurance Quality Score',
    }


# ═══════════════════════════════════════════════════════════════════════════════
# LEASING QUALITY SCORE
# ═══════════════════════════════════════════════════════════════════════════════

def _calculate_leasing_score(yearly_data: list) -> dict:
    """
    Calculate Leasing Quality Score — 11 Kriteria.
    9 Kriteria Dasar:
    1.  ROA > 0
    2.  Net Income YoY Growth > 0
    3.  Operating Cash Flow > 0
    4.  Equity Growth > 0
    5.  Debt to Equity tidak naik signifikan
    6.  Asset Growth positif
    7.  ROE > 10%
    8.  Net Margin stabil/naik
    9.  Expense Ratio membaik
    2 Kriteria Tambahan Leasing:
    10. NPF proxy (Allowance for Loan Loss / Total Loans = Write Off / Net Loans)
    11. Coverage Ratio (Retained Earnings / |Write Off|)
    """
    if len(yearly_data) < 2:
        return {'available': False, 'reason': 'Butuh minimal 2 tahun data.'}
    current = yearly_data[0]
    previous = yearly_data[1]
    cm = current['metrics']
    pm = previous['metrics']
    cr = current['raw']
    pr = previous['raw']
    criteria = []
    total_score = 0
    # ── 1. ROA > 0 ──────────────────────────────────────────────────────────
    passed = cm['roa'] is not None and cm['roa'] > 0
    criteria.append({
        'id': 1, 'name': 'ROA Positif', 'category': 'Profitabilitas',
        'description': f"ROA: {_pct(cm['roa'])}. Harus positif.",
        'passed': passed
    })
    total_score += int(passed)
    # ── 2. Net Income YoY Growth > 0 ────────────────────────────────────────
    ni_curr = cr.get('net_income')
    ni_prev = pr.get('net_income')
    passed = (ni_curr is not None and ni_prev is not None and ni_curr > ni_prev)
    if ni_curr is not None and ni_prev is not None and ni_prev != 0:
        growth = (ni_curr - ni_prev) / abs(ni_prev) * 100
        desc = f"Net Income: {_fmt(ni_curr)} vs {_fmt(ni_prev)} (YoY: {growth:+.1f}%)"
    else:
        desc = f"Net Income: {_fmt(ni_curr)} vs {_fmt(ni_prev)}"
    criteria.append({
        'id': 2, 'name': 'Net Income Growth > 0', 'category': 'Profitabilitas',
        'description': desc, 'passed': passed
    })
    total_score += int(passed)
    # ── 3. Operating Cash Flow > 0 ──────────────────────────────────────────
    passed = cm['cash_flow'] is not None and cm['cash_flow'] > 0
    criteria.append({
        'id': 3, 'name': 'Cash Flow Operasi Positif', 'category': 'Profitabilitas',
        'description': f"CFO: {_fmt(cm['cash_flow'])}. Harus positif.",
        'passed': passed
    })
    total_score += int(passed)
    # ── 4. Equity Growth > 0 ────────────────────────────────────────────────
    eq_curr = cr.get('total_equity')
    eq_prev = pr.get('total_equity')
    passed = (eq_curr is not None and eq_prev is not None and eq_curr > eq_prev)
    if eq_curr is not None and eq_prev is not None and eq_prev != 0:
        growth = (eq_curr - eq_prev) / abs(eq_prev) * 100
        desc = f"Equity: {_fmt(eq_curr)} vs {_fmt(eq_prev)} (Growth: {growth:+.1f}%)"
    else:
        desc = f"Equity: {_fmt(eq_curr)} vs {_fmt(eq_prev)}"
    criteria.append({
        'id': 4, 'name': 'Equity Growth Positif', 'category': 'Solvabilitas',
        'description': desc, 'passed': passed
    })
    total_score += int(passed)
    # ── 5. Debt to Equity tidak naik signifikan ─────────────────────────────
    eq_c = cr.get('total_equity')
    eq_p = pr.get('total_equity')
    liab_curr = cr.get('total_liabilities')
    liab_prev = pr.get('total_liabilities')
    if liab_curr is None and cr.get('total_assets') and eq_c:
        liab_curr = cr['total_assets'] - eq_c
    if liab_prev is None and pr.get('total_assets') and eq_p:
        liab_prev = pr['total_assets'] - eq_p
    der_curr = liab_curr / eq_c if (liab_curr is not None and eq_c and eq_c != 0) else None
    der_prev = liab_prev / eq_p if (liab_prev is not None and eq_p and eq_p != 0) else None
    if der_curr is not None and der_prev is not None:
        passed = der_curr <= der_prev * 1.10
        desc = f"DER: {der_curr:.2f}x vs {der_prev:.2f}x. {'Stabil/Turun.' if passed else 'Naik signifikan (>10%).'}"
    elif der_curr is not None:
        passed = der_curr < 5.0  # Leasing biasanya lebih leveraged
        desc = f"DER: {der_curr:.2f}x. Trend tidak diketahui."
    else:
        passed = True
        desc = "Data DER tidak tersedia."
    criteria.append({
        'id': 5, 'name': 'DER Tidak Naik Signifikan', 'category': 'Leverage',
        'description': desc, 'passed': passed
    })
    total_score += int(passed)
    # ── 6. Asset Growth positif ─────────────────────────────────────────────
    ast_curr = cr.get('total_assets')
    ast_prev = pr.get('total_assets')
    passed = (ast_curr is not None and ast_prev is not None and ast_curr > ast_prev)
    if ast_curr is not None and ast_prev is not None and ast_prev != 0:
        growth = (ast_curr - ast_prev) / abs(ast_prev) * 100
        desc = f"Total Assets: {_fmt(ast_curr)} vs {_fmt(ast_prev)} (Growth: {growth:+.1f}%)"
    else:
        desc = f"Total Assets: {_fmt(ast_curr)} vs {_fmt(ast_prev)}"
    criteria.append({
        'id': 6, 'name': 'Asset Growth Positif', 'category': 'Pertumbuhan',
        'description': desc, 'passed': passed
    })
    total_score += int(passed)
    # ── 7. ROE > 10% ───────────────────────────────────────────────────────
    roe_curr = cm.get('roe')
    passed = roe_curr is not None and roe_curr > 0.10
    criteria.append({
        'id': 7, 'name': 'ROE > 10%', 'category': 'Profitabilitas',
        'description': f"ROE: {_pct(roe_curr)}. {'Baik (>10%).' if passed else 'Rendah (≤10%).' if roe_curr is not None else 'N/A.'}",
        'passed': passed
    })
    total_score += int(passed)
    # ── 8. Net Margin stabil/naik ───────────────────────────────────────────
    rev_curr = cr.get('total_revenue')
    rev_prev = pr.get('total_revenue')
    nm_curr = ni_curr / rev_curr if (ni_curr is not None and rev_curr and rev_curr != 0) else None
    nm_prev = ni_prev / rev_prev if (ni_prev is not None and rev_prev and rev_prev != 0) else None
    if nm_curr is not None and nm_prev is not None:
        diff = nm_curr - nm_prev
        passed = diff >= -0.005
        desc = f"Net Margin: {_pct(nm_curr)} vs {_pct(nm_prev)}. {'Stabil/Naik.' if passed else 'Menurun.'}"
    elif nm_curr is not None:
        passed = nm_curr > 0
        desc = f"Net Margin: {_pct(nm_curr)}. Trend tidak diketahui."
    else:
        passed = False
        desc = "Data Net Margin tidak tersedia."
    criteria.append({
        'id': 8, 'name': 'Net Margin Stabil / Naik', 'category': 'Efisiensi',
        'description': desc, 'passed': passed
    })
    total_score += int(passed)
    # ── 9. Expense Ratio membaik ────────────────────────────────────────────
    opex_curr = cr.get('total_operating_expense')
    opex_prev = pr.get('total_operating_expense')
    er_curr = opex_curr / rev_curr if (opex_curr is not None and rev_curr and rev_curr != 0) else None
    er_prev = opex_prev / rev_prev if (opex_prev is not None and rev_prev and rev_prev != 0) else None
    if er_curr is not None and er_prev is not None:
        passed = er_curr < er_prev
        desc = f"Expense Ratio: {_pct(er_curr)} vs {_pct(er_prev)}. {'Membaik (turun).' if passed else 'Memburuk (naik).'}"
    elif er_curr is not None:
        passed = er_curr < 0.85
        desc = f"Expense Ratio: {_pct(er_curr)}. Trend tidak diketahui."
    else:
        passed = False
        desc = "Data Expense Ratio tidak tersedia."
    criteria.append({
        'id': 9, 'name': 'Expense Ratio Membaik', 'category': 'Efisiensi',
        'description': desc, 'passed': passed
    })
    total_score += int(passed)
    # ── 10. NPF Proxy: Write Off / Net Loans ───────────────────────────────
    # NPF (Non Performing Financing) proxy = Allowance for Loan Loss / Total Loans
    # Using Write Off as proxy for allowance/provision
    write_off_curr = cr.get('write_off')
    write_off_prev = pr.get('write_off')
    loans_curr = cr.get('total_loans')
    loans_prev = pr.get('total_loans')
    npf_curr = abs(write_off_curr) / loans_curr if (write_off_curr is not None and loans_curr and loans_curr != 0) else None
    npf_prev = abs(write_off_prev) / loans_prev if (write_off_prev is not None and loans_prev and loans_prev != 0) else None
    if npf_curr is not None:
        if npf_curr < 0.05:
            passed = True
            desc = f"NPF Proxy (WriteOff/Loans): {_pct(npf_curr)}. Sehat (<5%)."
        elif npf_prev is not None and npf_curr < npf_prev:
            passed = True
            desc = f"NPF Proxy: {_pct(npf_curr)} vs {_pct(npf_prev)}. Membaik (turun)."
        else:
            passed = False
            desc = f"NPF Proxy (WriteOff/Loans): {_pct(npf_curr)}. Tinggi (≥5%)."
    else:
        # Fallback: Cost of Credit (coc) if available
        coc = cm.get('coc')
        coc_p = pm.get('coc')
        if coc is not None:
            if coc < 0.03:
                passed = True
                desc = f"CoC (fallback NPF): {_pct(coc)}. Sehat (<3%)."
            elif coc_p is not None and coc < coc_p:
                passed = True
                desc = f"CoC (fallback NPF): {_pct(coc)} vs {_pct(coc_p)}. Membaik."
            else:
                passed = False
                desc = f"CoC (fallback NPF): {_pct(coc)}. Tinggi."
        else:
            passed = False
            desc = "Data NPF/WriteOff/Loans tidak tersedia."
    criteria.append({
        'id': 10, 'name': 'NPF Proxy (Kualitas Piutang)', 'category': 'Kualitas Aset Leasing',
        'description': desc, 'passed': passed
    })
    total_score += int(passed)
    # ── 11. Coverage Ratio: Retained Earnings / |Write Off| ─────────────────
    re_curr = cr.get('retained_earnings')
    re_prev = pr.get('retained_earnings')
    if re_curr is not None and write_off_curr is not None and abs(write_off_curr) > 0:
        cov = re_curr / abs(write_off_curr)
        if re_prev is not None and write_off_prev is not None and abs(write_off_prev) > 0:
            cov_prev = re_prev / abs(write_off_prev)
        else:
            cov_prev = None
        if cov >= 1.0:
            passed = True
            desc = f"Coverage (RE/WriteOff): {cov:.2f}x. Cadangan kuat (≥1x)."
        elif cov_prev is not None and cov > cov_prev:
            passed = True
            desc = f"Coverage: {cov:.2f}x vs {cov_prev:.2f}x. Meningkat."
        else:
            passed = False
            desc = f"Coverage (RE/WriteOff): {cov:.2f}x. Rendah (<1x)."
    elif re_curr is not None and (write_off_curr is None or write_off_curr == 0):
        # No write off = no bad loans to cover = good
        passed = True
        desc = "Tidak ada pencadangan kredit (Write Off = 0). Kualitas aset baik."
    else:
        passed = False
        desc = "Data Retained Earnings / Write Off tidak tersedia."
    criteria.append({
        'id': 11, 'name': 'Coverage Ratio (Cadangan)', 'category': 'Kualitas Aset Leasing',
        'description': desc, 'passed': passed
    })
    total_score += int(passed)
    # Determine strength
    if total_score >= 9: strength = 'Sangat Kuat'; strength_color = 'emerald'
    elif total_score >= 7: strength = 'Kuat'; strength_color = 'blue'
    elif total_score >= 5: strength = 'Moderat'; strength_color = 'amber'
    else: strength = 'Lemah'; strength_color = 'rose'
    return {
        'available': True,
        'score': total_score,
        'max_score': 11,
        'strength': strength,
        'strength_color': strength_color,
        'current_year': current['year'],
        'previous_year': previous['year'],
        'criteria': criteria,
        'score_type': 'leasing',
        'score_label': 'Leasing Quality Score',
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SECURITIES QUALITY SCORE
# ═══════════════════════════════════════════════════════════════════════════════

def _calculate_securities_score(yearly_data: list) -> dict:
    """
    Calculate Securities Quality Score — 11 Kriteria.
    9 Kriteria Dasar:
    1.  ROA > 0
    2.  Net Income YoY Growth > 0
    3.  Operating Cash Flow > 0
    4.  Equity Growth > 0
    5.  Debt to Equity tidak naik signifikan
    6.  Asset Growth positif
    7.  ROE > 10%
    8.  Net Margin stabil/naik
    9.  Expense Ratio membaik
    2 Kriteria Tambahan Sekuritas:
    10. AUM Growth proxy (Revenue YoY Growth — broker sangat bergantung transaksi)
    11. MKBD proxy (Equity / Total Assets — Modal Kerja Bersih Disesuaikan)
    """
    if len(yearly_data) < 2:
        return {'available': False, 'reason': 'Butuh minimal 2 tahun data.'}
    current = yearly_data[0]
    previous = yearly_data[1]
    cm = current['metrics']
    pm = previous['metrics']
    cr = current['raw']
    pr = previous['raw']
    criteria = []
    total_score = 0
    # ── 1. ROA > 0 ──────────────────────────────────────────────────────────
    passed = cm['roa'] is not None and cm['roa'] > 0
    criteria.append({
        'id': 1, 'name': 'ROA Positif', 'category': 'Profitabilitas',
        'description': f"ROA: {_pct(cm['roa'])}. Harus positif.",
        'passed': passed
    })
    total_score += int(passed)
    # ── 2. Net Income YoY Growth > 0 ────────────────────────────────────────
    ni_curr = cr.get('net_income')
    ni_prev = pr.get('net_income')
    passed = (ni_curr is not None and ni_prev is not None and ni_curr > ni_prev)
    if ni_curr is not None and ni_prev is not None and ni_prev != 0:
        growth = (ni_curr - ni_prev) / abs(ni_prev) * 100
        desc = f"Net Income: {_fmt(ni_curr)} vs {_fmt(ni_prev)} (YoY: {growth:+.1f}%)"
    else:
        desc = f"Net Income: {_fmt(ni_curr)} vs {_fmt(ni_prev)}"
    criteria.append({
        'id': 2, 'name': 'Net Income Growth > 0', 'category': 'Profitabilitas',
        'description': desc, 'passed': passed
    })
    total_score += int(passed)
    # ── 3. Operating Cash Flow > 0 ──────────────────────────────────────────
    passed = cm['cash_flow'] is not None and cm['cash_flow'] > 0
    criteria.append({
        'id': 3, 'name': 'Cash Flow Operasi Positif', 'category': 'Profitabilitas',
        'description': f"CFO: {_fmt(cm['cash_flow'])}. Harus positif.",
        'passed': passed
    })
    total_score += int(passed)
    # ── 4. Equity Growth > 0 ────────────────────────────────────────────────
    eq_curr = cr.get('total_equity')
    eq_prev = pr.get('total_equity')
    passed = (eq_curr is not None and eq_prev is not None and eq_curr > eq_prev)
    if eq_curr is not None and eq_prev is not None and eq_prev != 0:
        growth = (eq_curr - eq_prev) / abs(eq_prev) * 100
        desc = f"Equity: {_fmt(eq_curr)} vs {_fmt(eq_prev)} (Growth: {growth:+.1f}%)"
    else:
        desc = f"Equity: {_fmt(eq_curr)} vs {_fmt(eq_prev)}"
    criteria.append({
        'id': 4, 'name': 'Equity Growth Positif', 'category': 'Solvabilitas',
        'description': desc, 'passed': passed
    })
    total_score += int(passed)
    # ── 5. Debt to Equity tidak naik signifikan ─────────────────────────────
    eq_c = cr.get('total_equity')
    eq_p = pr.get('total_equity')
    liab_curr = cr.get('total_liabilities')
    liab_prev = pr.get('total_liabilities')
    if liab_curr is None and cr.get('total_assets') and eq_c:
        liab_curr = cr['total_assets'] - eq_c
    if liab_prev is None and pr.get('total_assets') and eq_p:
        liab_prev = pr['total_assets'] - eq_p
    der_curr = liab_curr / eq_c if (liab_curr is not None and eq_c and eq_c != 0) else None
    der_prev = liab_prev / eq_p if (liab_prev is not None and eq_p and eq_p != 0) else None
    if der_curr is not None and der_prev is not None:
        passed = der_curr <= der_prev * 1.10
        desc = f"DER: {der_curr:.2f}x vs {der_prev:.2f}x. {'Stabil/Turun.' if passed else 'Naik signifikan (>10%).'}"
    elif der_curr is not None:
        passed = der_curr < 3.0
        desc = f"DER: {der_curr:.2f}x. Trend tidak diketahui."
    else:
        passed = True
        desc = "Data DER tidak tersedia."
    criteria.append({
        'id': 5, 'name': 'DER Tidak Naik Signifikan', 'category': 'Leverage',
        'description': desc, 'passed': passed
    })
    total_score += int(passed)
    # ── 6. Asset Growth positif ─────────────────────────────────────────────
    ast_curr = cr.get('total_assets')
    ast_prev = pr.get('total_assets')
    passed = (ast_curr is not None and ast_prev is not None and ast_curr > ast_prev)
    if ast_curr is not None and ast_prev is not None and ast_prev != 0:
        growth = (ast_curr - ast_prev) / abs(ast_prev) * 100
        desc = f"Total Assets: {_fmt(ast_curr)} vs {_fmt(ast_prev)} (Growth: {growth:+.1f}%)"
    else:
        desc = f"Total Assets: {_fmt(ast_curr)} vs {_fmt(ast_prev)}"
    criteria.append({
        'id': 6, 'name': 'Asset Growth Positif', 'category': 'Pertumbuhan',
        'description': desc, 'passed': passed
    })
    total_score += int(passed)
    # ── 7. ROE > 10% ───────────────────────────────────────────────────────
    roe_curr = cm.get('roe')
    passed = roe_curr is not None and roe_curr > 0.10
    criteria.append({
        'id': 7, 'name': 'ROE > 10%', 'category': 'Profitabilitas',
        'description': f"ROE: {_pct(roe_curr)}. {'Baik (>10%).' if passed else 'Rendah (≤10%).' if roe_curr is not None else 'N/A.'}",
        'passed': passed
    })
    total_score += int(passed)
    # ── 8. Net Margin stabil/naik ───────────────────────────────────────────
    rev_curr = cr.get('total_revenue')
    rev_prev = pr.get('total_revenue')
    nm_curr = ni_curr / rev_curr if (ni_curr is not None and rev_curr and rev_curr != 0) else None
    nm_prev = ni_prev / rev_prev if (ni_prev is not None and rev_prev and rev_prev != 0) else None
    if nm_curr is not None and nm_prev is not None:
        diff = nm_curr - nm_prev
        passed = diff >= -0.005
        desc = f"Net Margin: {_pct(nm_curr)} vs {_pct(nm_prev)}. {'Stabil/Naik.' if passed else 'Menurun.'}"
    elif nm_curr is not None:
        passed = nm_curr > 0
        desc = f"Net Margin: {_pct(nm_curr)}. Trend tidak diketahui."
    else:
        passed = False
        desc = "Data Net Margin tidak tersedia."
    criteria.append({
        'id': 8, 'name': 'Net Margin Stabil / Naik', 'category': 'Efisiensi',
        'description': desc, 'passed': passed
    })
    total_score += int(passed)
    # ── 9. Expense Ratio membaik ────────────────────────────────────────────
    opex_curr = cr.get('total_operating_expense')
    opex_prev = pr.get('total_operating_expense')
    er_curr = opex_curr / rev_curr if (opex_curr is not None and rev_curr and rev_curr != 0) else None
    er_prev = opex_prev / rev_prev if (opex_prev is not None and rev_prev and rev_prev != 0) else None
    if er_curr is not None and er_prev is not None:
        passed = er_curr < er_prev
        desc = f"Expense Ratio: {_pct(er_curr)} vs {_pct(er_prev)}. {'Membaik (turun).' if passed else 'Memburuk (naik).'}"
    elif er_curr is not None:
        passed = er_curr < 0.85
        desc = f"Expense Ratio: {_pct(er_curr)}. Trend tidak diketahui."
    else:
        passed = False
        desc = "Data Expense Ratio tidak tersedia."
    criteria.append({
        'id': 9, 'name': 'Expense Ratio Membaik', 'category': 'Efisiensi',
        'description': desc, 'passed': passed
    })
    total_score += int(passed)
    # ── 10. AUM Growth Proxy: Revenue YoY Growth ───────────────────────────
    # Broker/sekuritas sangat bergantung pada volume transaksi.
    # Revenue = proxy untuk AUM (Asset Under Management) growth.
    if rev_curr is not None and rev_prev is not None and rev_prev != 0:
        rev_growth = (rev_curr - rev_prev) / abs(rev_prev)
        passed = rev_growth > 0
        desc = f"Revenue Growth (proxy AUM): {_pct(rev_growth)}. {'Positif — indikasi AUM naik.' if passed else 'Negatif — indikasi AUM turun.'}"
    else:
        passed = False
        desc = "Data Revenue tidak tersedia untuk proxy AUM Growth."
    criteria.append({
        'id': 10, 'name': 'AUM Growth Proxy (Revenue Growth)', 'category': 'Pertumbuhan Sekuritas',
        'description': desc, 'passed': passed
    })
    total_score += int(passed)
    # ── 11. MKBD Proxy: Equity / Total Assets ──────────────────────────────
    # MKBD (Modal Kerja Bersih Disesuaikan) proxy = Equity / Total Assets
    # Higher ratio = more capital buffer for trading operations
    mkbd_curr = eq_c / ast_curr if (eq_c and ast_curr and ast_curr != 0) else None
    mkbd_prev = eq_p / ast_prev if (eq_p and ast_prev and ast_prev != 0) else None
    if mkbd_curr is not None:
        if mkbd_curr >= 0.20:
            passed = True
            desc = f"MKBD Proxy (Equity/Assets): {_pct(mkbd_curr)}. Modal kuat (≥20%)."
        elif mkbd_prev is not None and mkbd_curr > mkbd_prev:
            passed = True
            desc = f"MKBD Proxy: {_pct(mkbd_curr)} vs {_pct(mkbd_prev)}. Meningkat."
        else:
            passed = False
            desc = f"MKBD Proxy (Equity/Assets): {_pct(mkbd_curr)}. Rendah (<20%)."
    else:
        passed = False
        desc = "Data Equity/Assets tidak tersedia untuk proxy MKBD."
    criteria.append({
        'id': 11, 'name': 'MKBD Proxy (Modal Kerja)', 'category': 'Solvabilitas Sekuritas',
        'description': desc, 'passed': passed
    })
    total_score += int(passed)
    # Determine strength
    if total_score >= 9: strength = 'Sangat Kuat'; strength_color = 'emerald'
    elif total_score >= 7: strength = 'Kuat'; strength_color = 'blue'
    elif total_score >= 5: strength = 'Moderat'; strength_color = 'amber'
    else: strength = 'Lemah'; strength_color = 'rose'
    return {
        'available': True,
        'score': total_score,
        'max_score': 11,
        'strength': strength,
        'strength_color': strength_color,
        'current_year': current['year'],
        'previous_year': previous['year'],
        'criteria': criteria,
        'score_type': 'securities',
        'score_label': 'Securities Quality Score',
    }
def _calculate_financial_valuation(pbv: float, roe_current: float, roe_prev: float,
                                    subsector: str = 'bank', cost_of_equity: float = None) -> dict:
    """
    Calculate Financial Valuation based on Residual Income Model (PBV vs ROE).
    Applies to all financial sub-sectors: bank, insurance, leasing, securities.
    Cost of Equity defaults vary by industry to reflect different risk profiles.
    Logic:
    - Fair PBV ≈ ROE / Cost of Equity.
    - If PBV < Fair PBV and ROE > Cost of Equity: Undervalued (Good).
    - If PBV > Fair PBV and ROE < Cost of Equity: Overvalued (Bad).
    Args:
        pbv: Price to Book Value ratio.
        roe_current: Return on Equity (current year).
        roe_prev: Return on Equity (previous year).
        subsector: Financial sub-sector ('bank', 'insurance', 'leasing', 'securities').
        cost_of_equity: Override Cost of Equity (default: auto per subsector).
    Returns:
        dict with valuation analysis.
    """
    # ── Subsector-specific defaults ─────────────────────────────────────
    COE_DEFAULTS = {
        'bank': 0.10,        # Stable, regulated, lower risk
        'insurance': 0.12,   # Long-tail liabilities, investment risk
        'leasing': 0.13,     # Credit risk, higher leverage
        'securities': 0.14,  # Cyclical, volatile earnings
    }
    LABELS = {
        'bank':       {'icon': '🏦', 'title': 'Bank Valuation',       'entity': 'bank'},
        'insurance':  {'icon': '🛡️', 'title': 'Insurance Valuation',  'entity': 'perusahaan asuransi'},
        'leasing':    {'icon': '🏢', 'title': 'Leasing Valuation',    'entity': 'perusahaan multifinance'},
        'securities': {'icon': '📊', 'title': 'Securities Valuation', 'entity': 'perusahaan sekuritas'},
    }
    if cost_of_equity is None:
        cost_of_equity = COE_DEFAULTS.get(subsector, 0.12)
    label = LABELS.get(subsector, LABELS['bank'])
    if pbv is None or roe_current is None:
        return {
            'available': False,
            'reason': 'Data PBV atau ROE tidak tersedia.',
            'icon': label['icon'],
            'title': label['title'],
            'subsector': subsector,
        }
    # Fair PBV (Justified PBV)
    # Simple Gordon Growth / Residual Income implication: P/B = (ROE - g) / (COE - g)
    # Simplified for screening: Fair PBV = ROE / COE
    fair_pbv = roe_current / cost_of_equity
    # Valuation Status
    # Undervalued: Price < Value (PBV < Fair PBV)
    # Overvalued: Price > Value (PBV > Fair PBV)
    status = "Fairly Valued"
    color = "blue"
    # Margin of safety / Premium threshold (e.g., 20% diff)
    if pbv < fair_pbv * 0.8:
        status = "Undervalued"
        color = "emerald"
    elif pbv > fair_pbv * 1.2:
        status = "Overvalued"
        color = "rose"
    # ROE Trend
    roe_trend = "Stabil"
    if roe_prev is not None:
        if roe_current > roe_prev * 1.05:
            roe_trend = "Meningkat"
        elif roe_current < roe_prev * 0.95:
            roe_trend = "Menurun"
    # Verdict logic — entity-specific description
    entity = label['entity']
    verdict = "Hold / Neutral"
    verdict_desc = "Valuasi wajar sesuai dengan profitabilitas saat ini."
    roe_used = roe_current
    if status == "Undervalued" and roe_current > cost_of_equity:
        verdict = "BUY / Accumulate"
        verdict_desc = f"Saham ini dihargai MURAH (PBV {pbv:.2f}x) padahal profitabilitas TINGGI (ROE {roe_current:.1%}). Potensi upside ke Fair PBV {fair_pbv:.2f}x."
    elif status == "Overvalued" and roe_current < cost_of_equity:
        verdict = "SELL / Avoid"
        verdict_desc = f"Saham ini dihargai MAHAL (PBV {pbv:.2f}x) padahal profitabilitas RENDAH (ROE {roe_current:.1%}). Risiko downside tinggi."
    elif status == "Undervalued" and roe_current < cost_of_equity:
        verdict = "Value Trap Risk"
        verdict_desc = "PBV rendah, tapi ROE juga rendah. Hati-hati jebakan valuasi (profitabilitas buruk)."
    elif status == "Overvalued" and roe_current > cost_of_equity:
        verdict = "Premium Quality"
        verdict_desc = f"Harga premium wajar untuk {entity} dengan profitabilitas superior."
        # Weighted average? Or just simple.
        # If trend is rising, maybe trust current more.
        # Let's use simple avg to be conservative.
        if roe_prev is not None:
            roe_used = (roe_current + roe_prev) / 2
    # Justified PBV = (ROE - g) / (Ke - g)
    # If ROE < Ke, Justified PBV < 1.0
    # Define variables for Gordon Growth Model
    ke = cost_of_equity
    g = 0.05 # Sustainable Growth Rate assumption (5% nominal GDP growth)
    try:
        justified_pbv = (roe_used - g) / (ke - g)
    except ZeroDivisionError:
        justified_pbv = 0
    # Cap min/max
    if justified_pbv < 0: justified_pbv = 0 # Loss making usually
    # Disclaimer:
    # If ROE is very high (>30%), model might overshoot because g is constant.
    # Cap PBV reasonable max e.g. 4.0x or 5.0x
    if justified_pbv > 5.0: justified_pbv = 5.0
    # Valuation verdict
    verdict = 'Fair Valued'
    upside = 0
    # We compare with ACTUAL PBV to determine Over/Undervalued
    if pbv is not None:
        if pbv < justified_pbv * 0.8: # >20% discount
            verdict = 'Undervalued'
        elif pbv > justified_pbv * 1.2: # >20% premium
            verdict = 'Overvalued'
        upside = (justified_pbv - pbv) / pbv if pbv > 0 else 0
    else:
        verdict = 'N/A (Historical)'
        upside = 0
    return {
        'available': True,
        'method': 'Justified PBV (Gordon Growth)',
        # Keys used by frontend renderBankValuation()
        'pbv': pbv,
        'fair_pbv': justified_pbv,
        'roe_current': roe_current,
        'roe_prev': roe_prev,
        'cost_of_equity': ke,
        'status': verdict,
        'status_color': color,
        'verdict': verdict,
        'description': verdict_desc,
        'roe_trend': roe_trend,
        'icon': label['icon'],
        'title': label['title'],
        'subsector': subsector,
        # Internal model fields
        'roe_used': roe_used,
        'ke': ke,
        'g': g,
        'justified_pbv': justified_pbv,
        'actual_pbv': pbv,
        'upside': upside,
    }
def _calculate_bank_score_v2(yearly_data: list) -> dict:
    """
    Calculate Bank Quality Score — 10 Kriteria Industri Perbankan.
    Uses injected metrics in yearly_data (cm/pm) for calculation.
    """
    if len(yearly_data) < 2:
        return {
            'available': False,
            'reason': 'Butuh minimal 2 tahun data untuk menghitung skor.'
        }
    current = yearly_data[0]
    previous = yearly_data[1]
    cm = current['metrics']
    pm = previous['metrics']
    cr = current['raw']
    pr = previous['raw']
    criteria = []
    total_score = 0
    # ── Recalculate ROA & NIM using Average Assets (standar PSAK/OJK) ────
    curr_assets = cr.get('total_assets')
    prev_assets = pr.get('total_assets')
    curr_ni = cr.get('net_income')
    prev_ni = pr.get('net_income')
    # Average Total Assets for current period (curr + prev / 2)
    avg_assets_curr = (curr_assets + prev_assets) / 2 if (curr_assets and prev_assets) else curr_assets
    # ROA with Average Total Assets
    roa_avg = curr_ni / avg_assets_curr if (curr_ni is not None and avg_assets_curr) else None
    # For ROA trend: also calculate previous period ROA with avg assets
    # Previous period avg assets needs the year before previous (index 2)
    if len(yearly_data) > 2:
        pp_assets = yearly_data[2]['raw'].get('total_assets')
        avg_assets_prev = (prev_assets + pp_assets) / 2 if (prev_assets and pp_assets) else prev_assets
    else:
        avg_assets_prev = prev_assets
    roa_avg_prev = prev_ni / avg_assets_prev if (prev_ni is not None and avg_assets_prev) else None
    # NIM with Average Total Assets
    curr_ii = cr.get('interest_income')
    curr_ie = cr.get('interest_expense') or 0
    prev_ii = pr.get('interest_income')
    prev_ie = pr.get('interest_expense') or 0
    nim_avg = (curr_ii - curr_ie) / avg_assets_curr if (curr_ii is not None and avg_assets_curr) else None
    nim_avg_prev = (prev_ii - prev_ie) / avg_assets_prev if (prev_ii is not None and avg_assets_prev) else None
    # Override NIM if OJK data (nim) is injected and looks valid
    if cm.get('nim') is not None:
        nim_final = cm['nim']
        nim_prev_final = pm.get('nim') if pm.get('nim') is not None else nim_avg_prev
    else:
        nim_final = nim_avg
        nim_prev_final = nim_avg_prev


    # ── 1. ROA Positif ──────────────────────────────────────────────────────
    passed = roa_avg is not None and roa_avg > 0
    criteria.append({
        'id': 1,
        'name': 'ROA Positif',
        'category': 'Profitabilitas',
        'description': f"ROA (avg assets) = {_pct(roa_avg)}. Harus positif.",
        'passed': passed
    })
    total_score += int(passed)
    # ── 2. ROA Meningkat ────────────────────────────────────────────────────
    passed = (roa_avg is not None and roa_avg_prev is not None and roa_avg > roa_avg_prev)
    criteria.append({
        'id': 2,
        'name': 'ROA Meningkat',
        'category': 'Profitabilitas',
        'description': f"ROA (avg assets): {_pct(roa_avg)} vs {_pct(roa_avg_prev)}. Harus meningkat.",
        'passed': passed
    })
    total_score += int(passed)
    # ── 3. CASA Ratio Meningkat ──────────────────────────────────────────────
    # Logic: Pass if CASA >= 50% OR CASA Increased
    passed_2 = False
    casa_curr = cm.get('casa')
    casa_prev = pm.get('casa')
    if casa_curr is not None:
        if casa_curr >= 0.50:
            passed_2 = True
            desc_2 = f"CASA: {_pct(casa_curr)}. Sehat (≥ 50%)."
        elif casa_prev is not None and casa_curr > casa_prev:
            passed_2 = True
            desc_2 = f"CASA: {_pct(casa_curr)} vs {_pct(casa_prev)}. Meningkat."
        else:
            desc_2 = f"CASA: {_pct(casa_curr)}. Rendah (< 50%) & Tidak meningkat."
    else:
        # Fallback: Proxy via CoF
        cof_curr = cm.get('cost_of_funds')
        cof_prev = pm.get('cost_of_funds')
        if cof_curr is not None and cof_prev is not None:
            if cof_curr < cof_prev:
                passed_2 = True
                desc_2 = f"CoF (proxy CASA): {_pct(cof_curr)} vs {_pct(cof_prev)}. Membaik (turun)."
            else:
                desc_2 = f"CoF (proxy CASA): {_pct(cof_curr)}. Tidak membaik."
        elif cof_curr is not None and cof_curr <= 0.03:
                passed_2 = True
                desc_2 = f"CoF (proxy CASA): {_pct(cof_curr)}. Sehat (< 3%)."
        else:
            desc_2 = "Data CASA/CoF tidak tersedia."
    criteria.append({
        'id': 3,
        'name': 'CASA Ratio Meningkat / Tinggi',
        'category': 'Efisiensi Pendanaan',
        'description': desc_2,
        'passed': passed_2
    })
    total_score += int(passed_2)
    # ── 4. NPL Gross < 5% (atau Menurun) ───────────────────────────────────
    # Logic: Pass if NPL < 5% OR NPL Decreased
    passed_4 = False
    npl_curr = cm.get('npl')
    npl_prev = pm.get('npl')
    if npl_curr is not None:
        if npl_curr < 0.05:
            passed_4 = True
            desc_4 = f"NPL Gross: {_pct(npl_curr)}. Sehat (< 5%)."
        elif npl_prev is not None and npl_curr < npl_prev:
            passed_4 = True
            desc_4 = f"NPL Gross: {_pct(npl_curr)} vs {_pct(npl_prev)}. > 5% tapi Membaik (turun)."
        else:
            desc_4 = f"NPL Gross: {_pct(npl_curr)}. Tinggi (≥ 5%) & Tidak membaik."
    else:
        # Fallback CoC
        coc_curr = cm.get('coc')
        coc_prev = pm.get('coc')
        if coc_curr is not None:
            if coc_curr < 0.02: # Strict proxy logic
                passed_4 = True
                desc_4 = f"CoC (proxy NPL): {_pct(coc_curr)}. Sehat (< 2%)."
            elif coc_prev is not None and coc_curr < coc_prev:
                passed_4 = True
                desc_4 = f"CoC (proxy NPL): {_pct(coc_curr)} vs {_pct(coc_prev)}. Membaik."
            else:
                desc_4 = f"CoC (proxy NPL): {_pct(coc_curr)}. Tinggi/Stabil."
        else:
            desc_4 = "Data NPL/CoC tidak tersedia."
    criteria.append({
        'id': 4,
        'name': 'NPL Gross < 5% (atau Menurun)',
        'category': 'Kualitas Aset',
        'description': desc_4,
        'passed': passed_4
    })
    total_score += int(passed_4)
    # ── 5. CoC Baik / Stabil ───────────────────────────────────────────────
    # Logic: Pass if CoC <= 2% OR Decreased
    passed_10 = False
    coc_curr = cm.get('coc')
    coc_prev = pm.get('coc')
    if coc_curr is not None:
        if coc_curr <= 0.02:
            passed_10 = True
            desc_10 = f"Cost of Credit: {_pct(coc_curr)}. Baik (≤ 2%)."
        elif coc_prev is not None and coc_curr < coc_prev:
             passed_10 = True
             desc_10 = f"Cost of Credit: {_pct(coc_curr)} vs {_pct(coc_prev)}. Membaik (turun)."
        else:
             desc_10 = f"Cost of Credit: {_pct(coc_curr)}. Tinggi (> 2%)."
    else:
        desc_10 = "Data CoC tidak tersedia."
    criteria.append({
        'id': 5,
        'name': 'CoC Rendah / Stabil',
        'category': 'Kualitas Aset',
        'description': desc_10,
        'passed': passed_10
    })
    total_score += int(passed_10)
    # ── 6. CAR (Capital Adequacy) Kuat ──────────────────────────────────────
    # Logic: Pass if CAR >= 12% OR Increased
    passed_5 = False
    car_curr = cm.get('car')
    car_prev = pm.get('car')
    if car_curr is not None:
        if car_curr >= 0.12:
            passed_5 = True
            desc_5 = f"CAR: {_pct(car_curr)}. Kuat (≥ 12%)."
        elif car_prev is not None and car_curr > car_prev:
            passed_5 = True
            desc_5 = f"CAR: {_pct(car_curr)} vs {_pct(car_prev)}. Membaik (naik)."
        else:
            desc_5 = f"CAR: {_pct(car_curr)}. Rendah (< 12%)."
    else:
        # Proxy: Equity/Assets
        eq_ast_curr = cr.get('total_equity') / cr.get('total_assets') if (cr.get('total_equity') and cr.get('total_assets')) else None
        eq_ast_prev = pr.get('total_equity') / pr.get('total_assets') if (pr.get('total_equity') and pr.get('total_assets')) else None
        if eq_ast_curr is not None and eq_ast_curr >= 0.12:
            passed_5 = True
            desc_5 = f"Equity/Assets: {_pct(eq_ast_curr)}. Kuat (≥ 12%)."
        elif eq_ast_curr is not None and eq_ast_prev is not None and eq_ast_curr > eq_ast_prev:
            passed_5 = True
            desc_5 = f"Equity/Assets: {_pct(eq_ast_curr)} vs {_pct(eq_ast_prev)}. Meningkat."
        else:
            desc_5 = "Data CAR tidak tersedia."
    criteria.append({
        'id': 6,
        'name': 'CAR (Capital Adequacy) Kuat / Meningkat',
        'category': 'Solvabilitas',
        'description': desc_5,
        'passed': passed_5
    })
    total_score += int(passed_5)
    # ── 7. Coverage Ratio (CKPN) > 100% ────────────────────────────────────
    # Logic: Pass if Cov >= 100% OR Increased
    passed_9 = False
    cov_curr = cm.get('coverage_ratio') or cm.get('coverage')
    cov_prev = pm.get('coverage_ratio') or pm.get('coverage')
    if cov_curr is not None:
        if cov_curr >= 1.0:
            passed_9 = True
            desc_9 = f"Coverage: {_pct(cov_curr)}. Aman (> 100%)."
        elif cov_prev is not None and cov_curr > cov_prev:
            passed_9 = True
            desc_9 = f"Coverage: {_pct(cov_curr)} vs {_pct(cov_prev)}. Meningkat."
        else:
            desc_9 = f"Coverage: {_pct(cov_curr)}. Rendah (< 100%)."
    else:
        passed_9 = False
        desc_9 = "Data Coverage tidak tersedia."
    criteria.append({
        'id': 7,
        'name': 'Coverage Ratio > 100% / Meningkat',
        'category': 'Solvabilitas',
        'description': desc_9,
        'passed': passed_9
    })
    total_score += int(passed_9)
    # ── 8. NIM Meningkat / Stabil ───────────────────────────────────────────
    passed_6 = False
    if nim_final is not None and nim_prev_final is not None:
        nim_diff = nim_final - nim_prev_final
        if nim_final > nim_prev_final:
            passed_6 = True
            desc_6 = f"NIM: {_pct(nim_final)} vs {_pct(nim_prev_final)}. Meningkat."
        elif abs(nim_diff) <= 0.005: 
            passed_6 = True
            desc_6 = f"NIM: {_pct(nim_final)}. Stabil."
        else:
            desc_6 = f"NIM: {_pct(nim_final)} vs {_pct(nim_prev_final)}. Menurun."
    elif nim_final is not None:
         desc_6 = f"NIM: {_pct(nim_final)}. Trend tidak diketahui."
    else:
         desc_6 = "Data NIM tidak tersedia."
    criteria.append({
        'id': 8,
        'name': 'NIM Meningkat / Stabil',
        'category': 'Profitabilitas Bank',
        'description': desc_6,
        'passed': passed_6
    })
    total_score += int(passed_6)
    # ── 9. LDR (Likuiditas) Sehat ───────────────────────────────────────────
    # Logic: Pass if LDR <= 92% OR (LDR > 92% and Decreased)
    passed_7 = False
    ldr_curr = cm.get('ldr')
    ldr_prev = pm.get('ldr')
    if ldr_curr is not None:
        if ldr_curr <= 0.92:
            passed_7 = True
            desc_7 = f"LDR: {_pct(ldr_curr)}. Sehat (≤ 92%)."
        elif ldr_prev is not None and ldr_curr < ldr_prev:
             passed_7 = True
             desc_7 = f"LDR: {_pct(ldr_curr)} vs {_pct(ldr_prev)}. Tinggi tapi Membaik (turun)."
        else:
             desc_7 = f"LDR: {_pct(ldr_curr)}. Tinggi (> 92%)."
    else:
        # Fallback pseudo-LDR
        desc_7 = "Data LDR tidak tersedia." # Simplified for fallback
    criteria.append({
        'id': 9,
        'name': 'LDR Sehat (≤ 92%) / Membaik',
        'category': 'Likuiditas',
        'description': desc_7,
        'passed': passed_7
    })
    total_score += int(passed_7)
    # ── 10. BOPO Menurun ─────────────────────────────────────────────────────
    # Logic: Pass if BOPO < Prev OR BOPO < 80%
    passed_8 = False
    bopo_curr = cm.get('bopo')
    bopo_prev = pm.get('bopo')
    if bopo_curr is not None:
        if bopo_prev is not None and bopo_curr < bopo_prev:
            passed_8 = True
            desc_8 = f"BOPO: {_pct(bopo_curr)} vs {_pct(bopo_prev)}. Membaik (turun)."
        elif bopo_curr < 0.80:
            passed_8 = True
            desc_8 = f"BOPO: {_pct(bopo_curr)}. Efisien (< 80%)."
        else:
            if bopo_prev:
                desc_8 = f"BOPO: {_pct(bopo_curr)} vs {_pct(bopo_prev)}. Memburuk (naik)."
            else:
                desc_8 = f"BOPO: {_pct(bopo_curr)}. > 80%."
    else:
        desc_8 = "Data BOPO tidak tersedia."
    criteria.append({
        'id': 10,
        'name': 'BOPO Menurun / Efisien',
        'category': 'Efisiensi Operasional',
        'description': desc_8,
        'passed': passed_8
    })
    total_score += int(passed_8)
    # Determine strength label
    if total_score >= 8:
        strength = 'Sangat Kuat'
        strength_color = 'emerald'
    elif total_score >= 6:
        strength = 'Kuat'
        strength_color = 'blue'
    elif total_score >= 4:
        strength = 'Moderat'
        strength_color = 'amber'
    else:
        strength = 'Lemah'
        strength_color = 'rose'
    return {
        'available': True,
        'score': total_score,
        'max_score': 10,
        'strength': strength,
        'strength_color': strength_color,
        'current_year': current['year'],
        'previous_year': previous['year'],
        'criteria': criteria,
        'score_type': 'bank',
        'score_label': 'Bank Quality Score',
    }
