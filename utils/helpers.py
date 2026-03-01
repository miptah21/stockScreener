"""
Shared Financial Helpers Module
Canonical implementations of formatting, math, and Piotroski F-Score.
Used by both scraper.py and fallback_scraper.py to eliminate duplication.
"""


# ─── Safe Math ────────────────────────────────────────────────────────

def safe_divide(numerator, denominator):
    """Safely divide two numbers. Returns None if inputs are invalid."""
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


# ─── Formatting ───────────────────────────────────────────────────────

def format_number(value):
    """Format a number for JSON output (2 decimal places)."""
    if value is None:
        return None
    return round(float(value), 2)


def format_ratio(value):
    """Format a ratio for JSON output (6 decimal places)."""
    if value is None:
        return None
    return round(float(value), 6)


def format_percent(value):
    """Format as percentage string, e.g. '12.34%'."""
    return f"{value * 100:.2f}%" if value is not None else 'N/A'


def format_ratio_str(value):
    """Format as ratio string, e.g. '1.2345'."""
    return f"{value:.4f}" if value is not None else 'N/A'


def format_big_number(value):
    """Format large numbers with T/B/M suffixes."""
    if value is None:
        return 'N/A'
    a = abs(value)
    s = '-' if value < 0 else ''
    if a >= 1e12:
        return f"{s}{a / 1e12:.2f}T"
    if a >= 1e9:
        return f"{s}{a / 1e9:.2f}B"
    if a >= 1e6:
        return f"{s}{a / 1e6:.2f}M"
    return f"{s}{a:,.0f}"


# ─── Piotroski F-Score (Standard / Non-Bank) ─────────────────────────

def calculate_piotroski_standard(data: list) -> dict:
    """
    Calculate standard Piotroski F-Score from financial data.
    Expects list of dicts with 'year', 'raw', and 'metrics' keys.
    Uses most recent 2 years (data[0] = current, data[1] = previous).

    Returns:
        dict with score, criteria breakdown, and classification
    """
    if len(data) < 2:
        return {'available': False, 'reason': 'Butuh minimal 2 tahun data.'}

    c, p = data[0], data[1]
    cm, pm = c['metrics'], p['metrics']
    cr, pr = c['raw'], p['raw']
    criteria = []
    score = 0

    def add(id_, name, cat, desc, passed):
        nonlocal score
        criteria.append({
            'id': id_, 'name': name, 'category': cat,
            'description': desc, 'passed': passed,
        })
        score += int(passed)

    # Profitability
    add(1, 'ROA Positif', 'Profitabilitas',
        f"ROA = {format_percent(cm['roa'])}. Harus positif.",
        cm['roa'] is not None and cm['roa'] > 0)

    add(2, 'Cash Flow Operasi Positif', 'Profitabilitas',
        f"OCF = {format_big_number(cm['cash_flow'])}. Harus positif.",
        cm['cash_flow'] is not None and cm['cash_flow'] > 0)

    add(3, 'ROA Meningkat', 'Profitabilitas',
        f"ROA: {format_percent(cm['roa'])} vs {format_percent(pm['roa'])}. Harus naik.",
        cm['roa'] is not None and pm['roa'] is not None and cm['roa'] > pm['roa'])

    add(4, 'Kualitas Laba (Accrual)', 'Profitabilitas',
        f"Accrual = {format_percent(cm['accrual'])}. Harus negatif.",
        cm['accrual'] is not None and cm['accrual'] < 0)

    # Leverage
    add(5, 'Rasio Utang Jangka Panjang Menurun', 'Leverage',
        f"LT Debt: {format_percent(cm['lt_debt_ratio'])} vs {format_percent(pm['lt_debt_ratio'])}. Harus turun.",
        cm['lt_debt_ratio'] is not None and pm['lt_debt_ratio'] is not None
        and cm['lt_debt_ratio'] < pm['lt_debt_ratio'])

    add(6, 'Current Ratio Meningkat', 'Leverage',
        f"CR: {format_ratio_str(cm['current_ratio'])} vs {format_ratio_str(pm['current_ratio'])}. Harus naik.",
        cm['current_ratio'] is not None and pm['current_ratio'] is not None
        and cm['current_ratio'] > pm['current_ratio'])

    cs = cr.get('shares_outstanding')
    ps = pr.get('shares_outstanding')
    if cs is not None and ps is not None:
        add(7, 'Tidak Menerbitkan Saham Baru', 'Leverage',
            f"Shares: {format_big_number(cs)} vs {format_big_number(ps)}. Tidak boleh bertambah.",
            cs <= ps)
    else:
        add(7, 'Tidak Menerbitkan Saham Baru', 'Leverage',
            "Data saham beredar tidak tersedia. Diasumsikan tidak ada penerbitan baru.", True)

    # Operational Efficiency
    add(8, 'Gross Margin Membaik', 'Efisiensi Operasional',
        f"GM: {format_percent(cm['gross_margin'])} vs {format_percent(pm['gross_margin'])}. Harus naik.",
        cm['gross_margin'] is not None and pm['gross_margin'] is not None
        and cm['gross_margin'] > pm['gross_margin'])

    add(9, 'Asset Turnover Meningkat', 'Efisiensi Operasional',
        f"AT: {format_ratio_str(cm['asset_turnover'])} vs {format_ratio_str(pm['asset_turnover'])}. Harus naik.",
        cm['asset_turnover'] is not None and pm['asset_turnover'] is not None
        and cm['asset_turnover'] > pm['asset_turnover'])

    # Classification
    if score >= 8:
        strength, color = 'Sangat Kuat', 'emerald'
    elif score >= 6:
        strength, color = 'Kuat', 'blue'
    elif score >= 4:
        strength, color = 'Moderat', 'amber'
    else:
        strength, color = 'Lemah', 'rose'

    return {
        'available': True,
        'score': score,
        'max_score': 9,
        'strength': strength,
        'strength_color': color,
        'current_year': c['year'],
        'previous_year': p['year'],
        'criteria': criteria,
        'score_type': 'standard',
        'score_label': 'Piotroski F-Score',
    }


# ─── Metrics Info (shared metadata) ──────────────────────────────────

METRICS_INFO = {
    'roa': {
        'name': 'Return on Assets (ROA)',
        'formula': 'Net Income / Total Assets',
        'description': 'Mengukur efisiensi perusahaan dalam menggunakan asetnya untuk menghasilkan laba.',
        'good_direction': 'higher',
    },
    'cash_flow': {
        'name': 'Operating Cash Flow',
        'formula': 'Direct from Cash Flow Statement',
        'description': 'Arus kas dari aktivitas operasional utama.',
        'good_direction': 'higher',
    },
    'net_income': {
        'name': 'Net Income',
        'formula': 'Direct from Income Statement',
        'description': 'Laba bersih setelah dikurangi semua biaya.',
        'good_direction': 'higher',
    },
    'accrual': {
        'name': 'Kualitas Laba (Accrual)',
        'formula': '(Net Income - OCF) / Total Assets',
        'description': 'Mengukur kualitas laba. Negatif = lebih baik.',
        'good_direction': 'lower',
    },
    'lt_debt_ratio': {
        'name': 'Rasio Utang Jangka Panjang',
        'formula': 'LT Debt / Total Assets',
        'description': 'Proporsi aset yang dibiayai utang jangka panjang.',
        'good_direction': 'lower',
    },
    'current_ratio': {
        'name': 'Current Ratio',
        'formula': 'Current Assets / Current Liabilities',
        'description': 'Kemampuan membayar kewajiban jangka pendek.',
        'good_direction': 'higher',
    },
    'gross_margin': {
        'name': 'Gross Margin',
        'formula': 'Gross Profit / Revenue × 100%',
        'description': 'Persentase pendapatan setelah HPP.',
        'good_direction': 'higher',
    },
    'asset_turnover': {
        'name': 'Asset Turnover',
        'formula': 'Revenue / Total Assets',
        'description': 'Efisiensi penggunaan aset untuk pendapatan.',
        'good_direction': 'higher',
    },
    'roce': {
        'name': 'Return on Capital Employed (ROCE)',
        'formula': 'EBIT / Capital Employed',
        'description': 'Efisiensi penggunaan modal.',
        'good_direction': 'higher',
    },
    'roic': {
        'name': 'Return on Invested Capital (ROIC)',
        'formula': 'NOPAT / Invested Capital',
        'description': 'Pengembalian modal.',
        'good_direction': 'higher',
    },
    'dso': {
        'name': 'Days Sales Outstanding (DSO)',
        'formula': 'AR / (Rev/365)',
        'description': 'Hari penagihan piutang.',
        'good_direction': 'lower',
    },
    'dsi': {
        'name': 'Days Sales of Inventory (DSI)',
        'formula': 'Inv / (COGS/365)',
        'description': 'Hari penjualan persediaan.',
        'good_direction': 'lower',
    },
    'dpo': {
        'name': 'Days Payable Outstanding (DPO)',
        'formula': 'AP / (COGS/365)',
        'description': 'Hari pembayaran utang.',
        'good_direction': 'higher',
    },
    'ccc': {
        'name': 'Cash Conversion Cycle (CCC)',
        'formula': 'DSO + DSI - DPO',
        'description': 'Siklus konversi kas.',
        'good_direction': 'lower',
    },
    'receivables_turnover': {
        'name': 'Receivables Turnover',
        'formula': 'Revenue / AR',
        'description': 'Perputaran piutang.',
        'good_direction': 'higher',
    },
    'inventory_turnover': {
        'name': 'Inventory Turnover',
        'formula': 'COGS / Inv',
        'description': 'Perputaran persediaan.',
        'good_direction': 'higher',
    },
}
