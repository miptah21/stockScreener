"""
Piotroski F-Score calculation (standard non-bank companies).
Extracted from yahoo.py for modularity.
"""

import logging
from scrapers.scoring.utils import (
    _pct, _ratio, _fmt, _safe_divide, _format_number, _format_ratio,
    _get_financial_subsector,
)

logger = logging.getLogger(__name__)


def _calculate_piotroski(yearly_data: list, sector: str = 'N/A', industry: str = 'N/A', ticker: str = '') -> dict:
    """
    Calculate Piotroski F-Score (standard or sector-modified).
    Auto-detects financial sub-sector and uses appropriate scoring.
    """
    subsector = _get_financial_subsector(sector, industry)
    if subsector == 'bank':
        # Bank Quality Score (using injected OJK data if available)
        return _calculate_bank_score_v2(yearly_data)
    elif subsector == 'insurance':
        return _calculate_insurance_score(yearly_data)
    elif subsector == 'leasing':
        return _calculate_leasing_score(yearly_data)
    elif subsector == 'securities':
        return _calculate_securities_score(yearly_data)
    return _calculate_standard_piotroski(yearly_data)


def _get_year_indices(yearly_data: list, target_year: int = None) -> tuple:
    """
    Helper to find current and previous year indices based on target_year.
    Returns (current_index, previous_index) or (None, None) if invalid.
    """
def _calculate_standard_piotroski(yearly_data: list) -> dict:
    """
    Calculate standard Piotroski F-Score (for non-bank companies).
    Compares latest year with previous year.
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

    
    # 1. ROA Positif
    passed = cm['roa'] is not None and cm['roa'] > 0
    criteria.append({
        'id': 1,
        'name': 'ROA Positif',
        'category': 'Profitabilitas',
        'description': f"ROA tahun ini = {_pct(cm['roa'])}. Harus positif.",
        'passed': passed
    })
    total_score += int(passed)

    
    # 2. Operating Cash Flow Positif
    passed = cm['cash_flow'] is not None and cm['cash_flow'] > 0
    criteria.append({
        'id': 2,
        'name': 'Cash Flow Operasi Positif',
        'category': 'Profitabilitas',
        'description': f"Operating Cash Flow = {_fmt(cm['cash_flow'])}. Harus positif.",
        'passed': passed
    })
    total_score += int(passed)

    
    # 3. ROA meningkat
    passed = (cm['roa'] is not None and pm['roa'] is not None and cm['roa'] > pm['roa'])
    criteria.append({
        'id': 3,
        'name': 'ROA Meningkat',
        'category': 'Profitabilitas',
        'description': f"ROA: {_pct(cm['roa'])} vs {_pct(pm['roa'])} (tahun lalu). Harus meningkat.",
        'passed': passed
    })
    total_score += int(passed)

    
    # 4. Kualitas Laba (Accrual) — Cash Flow > Net Income means accrual is negative
    passed = (cm['accrual'] is not None and cm['accrual'] < 0)
    criteria.append({
        'id': 4,
        'name': 'Kualitas Laba (Accrual)',
        'category': 'Profitabilitas',
        'description': f"Accrual = {_pct(cm['accrual'])}. Cash Flow harus > Net Income (accrual negatif).",
        'passed': passed
    })
    total_score += int(passed)

    
    # 5. Rasio Utang Jangka Panjang menurun
    if cm['lt_debt_ratio'] is None and pm['lt_debt_ratio'] is None:
        passed = True
        desc_5 = "Tidak ada utang jangka panjang di kedua tahun. Leverage = 0."
    elif cm['lt_debt_ratio'] is not None and pm['lt_debt_ratio'] is not None:
        passed = cm['lt_debt_ratio'] < pm['lt_debt_ratio']
        desc_5 = f"LT Debt Ratio: {_pct(cm['lt_debt_ratio'])} vs {_pct(pm['lt_debt_ratio'])} (tahun lalu). Harus menurun."
    elif cm['lt_debt_ratio'] is None:
        passed = True
        desc_5 = f"Utang jangka panjang dihapus (sebelumnya {_pct(pm['lt_debt_ratio'])})."
    else:
        passed = False
        desc_5 = f"Utang jangka panjang baru muncul ({_pct(cm['lt_debt_ratio'])})."
    criteria.append({
        'id': 5,
        'name': 'Rasio Utang Jangka Panjang Menurun',
        'category': 'Leverage',
        'description': desc_5,
        'passed': passed
    })
    total_score += int(passed)

    
    # 6. Current Ratio meningkat
    passed = (cm['current_ratio'] is not None and pm['current_ratio'] is not None
              and cm['current_ratio'] > pm['current_ratio'])
    criteria.append({
        'id': 6,
        'name': 'Current Ratio Meningkat',
        'category': 'Leverage',
        'description': f"Current Ratio: {_ratio(cm['current_ratio'])} vs {_ratio(pm['current_ratio'])} (tahun lalu). Harus meningkat.",
        'passed': passed
    })
    total_score += int(passed)

    
    # 7. Tidak menerbitkan saham baru
    curr_shares = cr.get('shares_outstanding')
    prev_shares = pr.get('shares_outstanding')
    if curr_shares is not None and prev_shares is not None:
        passed = curr_shares <= prev_shares
        desc = f"Saham beredar: {_fmt(curr_shares)} vs {_fmt(prev_shares)} (tahun lalu). Tidak boleh bertambah."
    else:
        passed = True
        desc = "Data saham beredar tidak tersedia. Diasumsikan tidak ada penerbitan baru."
    criteria.append({
        'id': 7,
        'name': 'Tidak Menerbitkan Saham Baru',
        'category': 'Leverage',
        'description': desc,
        'passed': passed
    })
    total_score += int(passed)

    
    # 8. Gross Margin membaik
    passed = (cm['gross_margin'] is not None and pm['gross_margin'] is not None
              and cm['gross_margin'] > pm['gross_margin'])
    criteria.append({
        'id': 8,
        'name': 'Gross Margin Membaik',
        'category': 'Efisiensi Operasional',
        'description': f"Gross Margin: {_pct(cm['gross_margin'])} vs {_pct(pm['gross_margin'])} (tahun lalu). Harus meningkat.",
        'passed': passed
    })
    total_score += int(passed)

    
    # 9. Asset Turnover Ratio meningkat
    passed = (cm['asset_turnover'] is not None and pm['asset_turnover'] is not None
              and cm['asset_turnover'] > pm['asset_turnover'])
    criteria.append({
        'id': 9,
        'name': 'Asset Turnover Meningkat',
        'category': 'Efisiensi Operasional',
        'description': f"Asset Turnover: {_ratio(cm['asset_turnover'])} vs {_ratio(pm['asset_turnover'])} (tahun lalu). Harus meningkat.",
        'passed': passed
    })
    total_score += int(passed)

    
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
        'max_score': 9,
        'strength': strength,
        'strength_color': strength_color,
        'current_year': current['year'],
        'previous_year': previous['year'],
        'criteria': criteria,
        'score_type': 'standard',
        'score_label': 'Piotroski F-Score',
    }


    # NIM with Average Total Assets (proxy for Avg Earning Assets)
    curr_ii = cr.get('interest_income')
    curr_ie = cr.get('interest_expense') or 0
    prev_ii = pr.get('interest_income')
    prev_ie = pr.get('interest_expense') or 0
    nim_avg = (curr_ii - curr_ie) / avg_assets_curr if (curr_ii is not None and avg_assets_curr) else None
    nim_avg_prev = (prev_ii - prev_ie) / avg_assets_prev if (prev_ii is not None and avg_assets_prev) else None
    # ── 1. ROA Positif ──────────────────────────────────────────────────────
    # Standar PSAK: ROA = Net Income / Rata-rata Total Aset
    passed = roa_avg is not None and roa_avg > 0
    criteria.append({
        'id': 1,
        'name': 'ROA Positif',
        'category': 'Profitabilitas',
        'description': f"ROA (avg assets) = {_pct(roa_avg)}. Harus positif.",
        'passed': passed
    })
    total_score += int(passed)
    # ── 2. CASA Ratio Meningkat ──────────────────────────────────────────────
    passed_2 = False
    desc_2 = "Data CASA tidak tersedia."
    if ojk_ratios and ojk_ratios.get('casa') is not None:
        # ✅ Real CASA ratio from OJK/annual report
        casa_val = ojk_ratios['casa']
        if casa_val >= 0.50:  # CASA ≥ 50% = healthy
            passed_2 = True
            desc_2 = f"CASA: {_pct(casa_val)}. Sehat (≥ 50%). [Sumber: {ojk_ratios.get('source', 'OJK')}]"
        else:
            desc_2 = f"CASA: {_pct(casa_val)}. Rendah (< 50%). [Sumber: {ojk_ratios.get('source', 'OJK')}]"
    else:
        # Fallback: proxy via Cost of Funds
        cof_curr = cm.get('cost_of_funds')
        cof_prev = pm.get('cost_of_funds')
        if cof_curr is not None:
            if cof_prev is not None:
                if cof_curr < cof_prev:
                    passed_2 = True
                    desc_2 = f"CoF (proxy CASA): {_pct(cof_curr)} vs {_pct(cof_prev)}. Membaik (turun → CASA naik)."
                elif cof_curr <= 0.025:
                    passed_2 = True
                    desc_2 = f"CoF (proxy CASA): {_pct(cof_curr)}. Stabil rendah (< 2.5% → CASA tinggi)."
                else:
                    desc_2 = f"CoF (proxy CASA): {_pct(cof_curr)} vs {_pct(cof_prev)}. Memburuk (CASA turun)."
            else:
                if cof_curr <= 0.03:
                    passed_2 = True
                    desc_2 = f"CoF (proxy CASA): {_pct(cof_curr)}. Sehat (< 3%)."
                else:
                    desc_2 = f"CoF (proxy CASA): {_pct(cof_curr)}. > 3% (butuh pembanding)."
    criteria.append({
        'id': 2,
        'name': 'CASA Ratio Meningkat',
        'category': 'Efisiensi Pendanaan',
        'description': desc_2,
        'passed': passed_2
    })
    total_score += int(passed_2)
    # ── 3. ROA Meningkat ────────────────────────────────────────────────────
    # Bandingkan ROA (avg assets) periode ini vs periode lalu
    passed = (roa_avg is not None and roa_avg_prev is not None and roa_avg > roa_avg_prev)
    criteria.append({
        'id': 3,
        'name': 'ROA Meningkat',
        'category': 'Profitabilitas',
        'description': f"ROA (avg assets): {_pct(roa_avg)} vs {_pct(roa_avg_prev)} (tahun lalu). Harus meningkat.",
        'passed': passed
    })
    total_score += int(passed)
    # ── 4. NPL Gross < 5% (atau Menurun) ───────────────────────────────────
    passed_4 = False
    desc_4 = "Data NPL tidak tersedia."
    if ojk_ratios and ojk_ratios.get('npl') is not None:
        # ✅ Real NPL from OJK/annual report
        npl_val = ojk_ratios['npl']
        if npl_val < 0.05:
            passed_4 = True
            desc_4 = f"NPL Gross: {_pct(npl_val)}. Sehat (< 5%). [Sumber: {ojk_ratios.get('source', 'OJK')}]"
        else:
            desc_4 = f"NPL Gross: {_pct(npl_val)}. Tinggi (≥ 5%). [Sumber: {ojk_ratios.get('source', 'OJK')}]"
    else:
        # Fallback: proxy via CoC
        coc_curr = cm.get('coc')
        coc_prev = pm.get('coc')
        if coc_curr is not None:
            if coc_curr < 0.05:
                passed_4 = True
                desc_4 = f"CoC (proxy NPL): {_pct(coc_curr)}. Sehat (< 5%)."
                if coc_prev is not None:
                    if coc_curr < coc_prev:
                        desc_4 = f"CoC (proxy NPL): {_pct(coc_curr)} vs {_pct(coc_prev)}. Sehat & Menurun."
                    else:
                        desc_4 = f"CoC (proxy NPL): {_pct(coc_curr)} vs {_pct(coc_prev)}. Sehat tapi Naik."
            elif coc_prev is not None and coc_curr < coc_prev:
                passed_4 = True
                desc_4 = f"CoC (proxy NPL): {_pct(coc_curr)} vs {_pct(coc_prev)}. ≥ 5% tapi Menurun."
            else:
                desc_4 = f"CoC (proxy NPL): {_pct(coc_curr)}. ≥ 5% & Tidak menurun."
    criteria.append({
        'id': 4,
        'name': 'NPL Gross < 5% (atau Menurun)',
        'category': 'Kualitas Aset',
        'description': desc_4,
        'passed': passed_4
    })
    total_score += int(passed_4)
    # ── 5. CAR (Capital Adequacy) Kuat ──────────────────────────────────────
    passed_5 = False
    desc_5 = "Data CAR tidak tersedia."
    if ojk_ratios and ojk_ratios.get('car') is not None:
        # ✅ Real CAR from OJK/annual report
        car_val = ojk_ratios['car']
        if car_val >= 0.12:  # CAR ≥ 12% = well-capitalized (OJK minimum ~8%)
            passed_5 = True
            desc_5 = f"CAR: {_pct(car_val)}. Kuat (≥ 12%). [Sumber: {ojk_ratios.get('source', 'OJK')}]"
        else:
            desc_5 = f"CAR: {_pct(car_val)}. Rendah (< 12%). [Sumber: {ojk_ratios.get('source', 'OJK')}]"
    else:
        # Fallback: proxy via Equity/Assets
        eq_ast_curr = cr.get('total_equity') / cr.get('total_assets') if (cr.get('total_equity') and cr.get('total_assets')) else None
        eq_ast_prev = pr.get('total_equity') / pr.get('total_assets') if (pr.get('total_equity') and pr.get('total_assets')) else None
        if eq_ast_curr is not None:
            if eq_ast_curr >= 0.12:
                passed_5 = True
                desc_5 = f"Equity/Assets (proxy CAR): {_pct(eq_ast_curr)}. Kuat (≥ 12%)."
                if eq_ast_prev is not None:
                    trend = "Meningkat" if eq_ast_curr > eq_ast_prev else "Menurun" if eq_ast_curr < eq_ast_prev else "Stabil"
                    desc_5 = f"Equity/Assets (proxy CAR): {_pct(eq_ast_curr)} vs {_pct(eq_ast_prev)}. Kuat, {trend}."
            elif eq_ast_prev is not None and eq_ast_curr > eq_ast_prev:
                passed_5 = True
                desc_5 = f"Equity/Assets (proxy CAR): {_pct(eq_ast_curr)} vs {_pct(eq_ast_prev)}. Meningkat."
            else:
                desc_5 = f"Equity/Assets (proxy CAR): {_pct(eq_ast_curr)}. < 12%."
    criteria.append({
        'id': 5,
        'name': 'CAR (Capital Adequacy) Kuat',
        'category': 'Solvabilitas',
        'description': desc_5,
        'passed': passed_5
    })
    total_score += int(passed_5)
    # ── 6. NIM Meningkat / Stabil ───────────────────────────────────────────
    # Standar PSAK: NIM = NII / Rata-rata Aset Produktif
    # Proxy: gunakan Rata-rata Total Aset (Yahoo tidak punya Earning Assets)
    passed_6 = False
    desc_6 = f"NIM (avg assets): {_pct(nim_avg)} vs {_pct(nim_avg_prev)}."
    if nim_avg is not None and nim_avg_prev is not None:
        nim_diff = nim_avg - nim_avg_prev
        if nim_avg > nim_avg_prev:
            passed_6 = True
            desc_6 = f"NIM (avg assets): {_pct(nim_avg)} vs {_pct(nim_avg_prev)}. Meningkat (+{_pct(nim_diff)})."
        elif abs(nim_diff) <= 0.005:  # Stabil jika perubahan < 0.5pp
            passed_6 = True
            desc_6 = f"NIM (avg assets): {_pct(nim_avg)} vs {_pct(nim_avg_prev)}. Stabil (Δ {_pct(nim_diff)})."
        else:
            desc_6 = f"NIM (avg assets): {_pct(nim_avg)} vs {_pct(nim_avg_prev)}. Menurun ({_pct(nim_diff)})."
    elif nim_avg is not None:
        desc_6 = f"NIM (avg assets): {_pct(nim_avg)} (data tahun lalu tidak tersedia)."
    criteria.append({
        'id': 6,
        'name': 'NIM Meningkat / Stabil',
        'category': 'Profitabilitas Bank',
        'description': desc_6,
        'passed': passed_6
    })
    total_score += int(passed_6)
    # ── 7. LDR (Likuiditas) Sehat ───────────────────────────────────────────
    passed_7 = False
    desc_7 = "Data LDR tidak tersedia."
    if ojk_ratios and ojk_ratios.get('ldr') is not None:
        # ✅ Real LDR from OJK/annual report
        ldr_val = ojk_ratios['ldr']
        if ldr_val <= 0.92:  # LDR ≤ 92% = sehat (OJK target 78-92%)
            passed_7 = True
            desc_7 = f"LDR: {_pct(ldr_val)}. Sehat (≤ 92%). [Sumber: {ojk_ratios.get('source', 'OJK')}]"
        elif ldr_val <= 0.98:  # 92-98% = marginal
            desc_7 = f"LDR: {_pct(ldr_val)}. Marginal (> 92%). [Sumber: {ojk_ratios.get('source', 'OJK')}]"
        else:
            desc_7 = f"LDR: {_pct(ldr_val)}. Tinggi (≥ 98%). [Sumber: {ojk_ratios.get('source', 'OJK')}]"
    else:
        # Fallback: proxy via pseudo-LDR
        cash = cr.get('cash_financial')
        assets = cr.get('total_assets')
        liab = cr.get('total_liabilities')
        if cash is not None and assets is not None and assets > 0:
            pseudo_ldr = (assets - cash) / assets
            if pseudo_ldr < 0.95:
                passed_7 = True
                desc_7 = f"Pseudo-LDR: {_pct(pseudo_ldr)}. Sehat (< 95%)."
            elif pseudo_ldr < 0.98:
                prev_cash = pr.get('cash_financial')
                prev_assets_7 = pr.get('total_assets')
                if prev_cash and prev_assets_7:
                    prev_ldr = (prev_assets_7 - prev_cash) / prev_assets_7
                    if pseudo_ldr < prev_ldr:
                        passed_7 = True
                        desc_7 = f"Pseudo-LDR: {_pct(pseudo_ldr)} vs {_pct(prev_ldr)}. Marginal tapi Membaik."
                    else:
                        desc_7 = f"Pseudo-LDR: {_pct(pseudo_ldr)} vs {_pct(prev_ldr)}. Marginal & Memburuk."
                else:
                    desc_7 = f"Pseudo-LDR: {_pct(pseudo_ldr)}. Marginal (95-98%)."
            else:
                desc_7 = f"Pseudo-LDR: {_pct(pseudo_ldr)}. Tinggi (≥ 98%)."
        elif cash is not None and liab is not None and liab > 0:
            cash_ratio = cash / liab
            if cash_ratio >= 0.05:
                passed_7 = True
                desc_7 = f"Cash Ratio: {_pct(cash_ratio)}. Sehat (≥ 5%)."
            else:
                desc_7 = f"Cash Ratio: {_pct(cash_ratio)}. Rendah (< 5%)."
    criteria.append({
        'id': 7,
        'name': 'LDR (Likuiditas) Sehat',
        'category': 'Likuiditas',
        'description': desc_7,
        'passed': passed_7
    })
    total_score += int(passed_7)
    # ── 8. BOPO Menurun ─────────────────────────────────────────────────────
    passed = (cm.get('bopo') is not None and pm.get('bopo') is not None
              and cm['bopo'] < pm['bopo'])  # Lower BOPO = more efficient
    criteria.append({
        'id': 8,
        'name': 'BOPO Menurun',
        'category': 'Efisiensi Operasional',
        'description': f"BOPO: {_pct(cm.get('bopo'))} vs {_pct(pm.get('bopo'))} (tahun lalu). Harus menurun (semakin efisien).",
        'passed': passed
    })
    total_score += int(passed)
    # ── 9. Coverage Ratio (CKPN) > 100% ────────────────────────────────────
    passed_9 = False
    desc_9 = "Data Coverage Ratio tidak tersedia."
    if ojk_ratios and ojk_ratios.get('coverage') is not None:
        # ✅ Real Coverage Ratio from OJK/annual report
        cov_val = ojk_ratios['coverage']
        if cov_val >= 1.0:  # Coverage > 100%
            passed_9 = True
            desc_9 = f"Coverage Ratio: {cov_val*100:.0f}%. Sehat (> 100%). [Sumber: {ojk_ratios.get('source', 'OJK')}]"
        else:
            desc_9 = f"Coverage Ratio: {cov_val*100:.0f}%. Rendah (< 100%). [Sumber: {ojk_ratios.get('source', 'OJK')}]"
    else:
        # Fallback: proxy via Retained Earnings Growth
        re_curr = cr.get('retained_earnings')
        re_prev = pr.get('retained_earnings')
        if re_curr is not None and re_prev is not None:
            if re_prev != 0:
                re_growth = (re_curr - re_prev) / abs(re_prev)
            else:
                re_growth = 1.0 if re_curr > 0 else 0.0
            if re_curr > re_prev:
                passed_9 = True
                desc_9 = f"RE Growth: +{_pct(re_growth)}. Cadangan modal meningkat (proxy CKPN sehat)."
            else:
                desc_9 = f"RE Growth: {_pct(re_growth)}. Cadangan modal menurun (proxy CKPN lemah)."
    criteria.append({
        'id': 9,
        'name': 'Coverage Ratio (CKPN) > 100%',
        'category': 'Solvabilitas',
        'description': desc_9,
        'passed': passed_9
    })
    total_score += int(passed_9)
    # ── 10. CoC Baik / Stabil ───────────────────────────────────────────────
    passed_10 = False
    desc_10 = "Data CoC tidak tersedia."
    if ojk_ratios and ojk_ratios.get('coc') is not None:
        # ✅ Real CoC from OJK/annual report
        coc_real = ojk_ratios['coc']
        if coc_real <= 0.02:  # CoC ≤ 2% = baik
            passed_10 = True
            desc_10 = f"CoC: {_pct(coc_real)}. Baik (≤ 2%). [Sumber: {ojk_ratios.get('source', 'OJK')}]"
        else:
            desc_10 = f"CoC: {_pct(coc_real)}. Tinggi (> 2%). [Sumber: {ojk_ratios.get('source', 'OJK')}]"
    else:
        # Fallback: proxy via Yahoo Write Off / Total Assets
        coc_10_curr = cm.get('coc')
        coc_10_prev = pm.get('coc')
        if coc_10_curr is not None:
            if coc_10_prev is not None:
                if coc_10_curr <= coc_10_prev:
                    passed_10 = True
                    if coc_10_curr < coc_10_prev:
                        desc_10 = f"CoC: {_pct(coc_10_curr)} vs {_pct(coc_10_prev)}. Membaik (turun)."
                    else:
                        desc_10 = f"CoC: {_pct(coc_10_curr)}. Stabil."
                else:
                    desc_10 = f"CoC: {_pct(coc_10_curr)} vs {_pct(coc_10_prev)}. Memburuk (naik)."
            else:
                if coc_10_curr <= 0.01:
                    passed_10 = True
                    desc_10 = f"CoC: {_pct(coc_10_curr)}. Baik (< 1%)."
                else:
                    desc_10 = f"CoC: {_pct(coc_10_curr)}. > 1% (butuh pembanding)."
    criteria.append({
        'id': 10,
        'name': 'CoC Baik / Stabil',
        'category': 'Kualitas Aset',
        'description': desc_10,
        'passed': passed_10
    })
    total_score += int(passed_10)
    # Determine strength label (10-point scale)
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
