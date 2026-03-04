"""
Shared utility functions for financial data processing.
Extracted from yahoo.py for modularity.
"""

import pandas as pd


def _get_financial_subsector(sector: str, industry: str) -> str:
    """
    Detect financial sub-sector from Yahoo Finance sector/industry.
    Returns: 'bank', 'insurance', 'leasing', 'securities', 'real_estate', or None.
    """
    if not sector:
        return None
    s = sector.lower()
    i = (industry or '').lower()
    # Real Estate is its own sector in Yahoo Finance
    if 'real estate' in s:
        return 'real_estate'
    # Bank detection: Financial Services sector + Bank industry
    if 'bank' in i:
        return 'bank'
    # Insurance detection
    if 'insurance' in i:
        return 'insurance'
    # Leasing / Credit Services / Multifinance
    if any(k in i for k in ['credit', 'leasing', 'financing', 'consumer lending', 'multifinance']):
        return 'leasing'
    # Securities / Broker-Dealer / Capital Markets
    if any(k in i for k in ['capital markets', 'brokerage', 'securities', 'investment banking', 'asset management']):
        return 'securities'
    # Generic financial (holding, etc.)
    if 'financial' in s or 'finansial' in s:
        return 'bank'  # Default financial to bank metrics
    return None


def _is_financial_sector(sector: str, industry: str = '') -> bool:
    """Check if the sector should use financial-style metrics (bank, insurance, leasing, securities — NOT real estate)."""
    subsector = _get_financial_subsector(sector, industry)
    return subsector in ('bank', 'insurance', 'leasing', 'securities')

def _get_metrics_info(subsector: str = None) -> dict:

    """Return metrics_info dict, with sub-sector-specific entries if applicable."""
    base = {
        'roa': {
            'name': 'Return on Assets (ROA)',
            'formula': 'Net Income / Total Assets',
            'description': 'Mengukur efisiensi perusahaan dalam menggunakan asetnya untuk menghasilkan laba.',
            'good_direction': 'higher',
        },
        'cash_flow': {
            'name': 'Operating Cash Flow',
            'formula': 'Direct from Cash Flow Statement',
            'description': 'Arus kas dari aktivitas operasional utama perusahaan.',
            'good_direction': 'higher',
        },
        'net_income': {
            'name': 'Net Income',
            'formula': 'Direct from Income Statement',
            'description': 'Laba bersih perusahaan setelah dikurangi semua biaya.',
            'good_direction': 'higher',
        },
        'accrual': {
            'name': 'Kualitas Laba (Accrual Ratio)',
            'formula': '(Net Income - Operating Cash Flow) / Total Assets',
            'description': 'Mengukur seberapa besar laba didukung oleh arus kas. Nilai negatif menunjukkan kualitas laba yang lebih baik.',
            'good_direction': 'lower',
        },
        'lt_debt_ratio': {
            'name': 'Rasio Utang Jangka Panjang',
            'formula': 'Long Term Debt / Total Assets',
            'description': 'Mengukur proporsi aset yang dibiayai oleh utang jangka panjang.',
            'good_direction': 'lower',
        },
        'roce': {
            'name': 'Return on Capital Employed (ROCE)',
            'formula': 'EBIT / (Total Assets - Current Liabilities)',
            'description': 'Mengukur efisiensi penggunaan modal yang diinvestasikan (termasuk utang) untuk menghasilkan laba operasional.',
            'good_direction': 'higher',
        },
        'roic': {
            'name': 'Return on Invested Capital (ROIC)',
            'formula': 'NOPAT / Invested Capital',
            'description': 'Mengukur pengembalian atas modal yang secara spesifik diinvestasikan dalam bisnis (ekuitas + utang berbunga).',
            'good_direction': 'higher',
        },
        'dso': {
            'name': 'Days Sales Outstanding (DSO)',
            'formula': 'Average Receivables / (Revenue / 365)',
            'description': 'Rata-rata jumlah hari yang dibutuhkan perusahaan untuk menagih piutang setelah penjualan.',
            'good_direction': 'lower',
        },
        'dsi': {
            'name': 'Days Sales of Inventory (DSI)',
            'formula': 'Average Inventory / (COGS / 365)',
            'description': 'Rata-rata jumlah hari yang dibutuhkan perusahaan untuk mengubah persediaan menjadi penjualan.',
            'good_direction': 'lower',
        },
        'dpo': {
            'name': 'Days Payable Outstanding (DPO)',
            'formula': 'Average Payables / (COGS / 365)',
            'description': 'Rata-rata jumlah hari yang dibutuhkan perusahaan untuk membayar utang usahanya.',
            'good_direction': 'higher',
        },
        'ccc': {
            'name': 'Cash Conversion Cycle (CCC)',
            'formula': 'DSO + DSI - DPO',
            'description': 'Lama waktu (dalam hari) siklus pengurutan kas dari investasi persediaan kembali menjadi kas.',
            'good_direction': 'lower',
        },
        'receivables_turnover': {
            'name': 'Receivables Turnover',
            'formula': 'Revenue / Accounts Receivable',
            'description': 'Efisiensi perusahaan dalam mengumpulkan piutangnya dari pelanggan.',
            'good_direction': 'higher',
        },
        'inventory_turnover': {
            'name': 'Inventory Turnover',
            'formula': 'COGS / Inventory',
            'description': 'Seberapa sering persediaan dijual atau digunakan selama periode tertentu.',
            'good_direction': 'higher',
        },
    }

    
    if subsector == 'bank':
        base.update({
            'nim': {
                'name': 'Net Interest Margin (NIM)',
                'formula': '(Interest Income - Interest Expense) / Total Assets',
                'description': 'Mengukur selisih pendapatan bunga dan beban bunga relatif terhadap total aset. Metrik utama profitabilitas bank.',
                'good_direction': 'higher',
            },
            'roe': {
                'name': 'Return on Equity (ROE)',
                'formula': 'Net Income / Total Equity',
                'description': 'Mengukur kemampuan bank menghasilkan laba dari ekuitas pemegang saham. Metrik valuasi kunci untuk bank.',
                'good_direction': 'higher',
            },
            'bopo': {
                'name': 'BOPO (Cost-to-Income)',
                'formula': 'Total Operating Expense / Operating Income',
                'description': 'Mengukur efisiensi operasional bank. Semakin rendah semakin efisien. Standar sehat: < 85%.',
                'good_direction': 'lower',
            },
        })
        # Bank-specific: Cost of Credit
        base['coc'] = {
            'name': 'Cost of Credit (CoC)',
            'formula': '|Write Off| / Total Assets',
            'description': 'Proxy biaya pencadangan kredit. Semakin rendah, kualitas kredit semakin baik. Idealnya < 1%.',
            'good_direction': 'lower',
        }
        base['cost_of_funds'] = {
            'name': 'Cost of Funds (CoF)',
            'formula': 'Interest Expense / Total Liabilities',
            'description': 'Biaya dana. Semakin rendah indikasi CASA tinggi.',
            'good_direction': 'lower',
        }
        # New standard bank metrics (from OJK/Annual Reports)
        base['npl'] = {
            'name': 'Non-Performing Loan (NPL)',
            'formula': 'NPL Gross (OJK/Laporan Tahunan)',
            'description': 'Rasio kredit bermasalah. Semakin rendah semakin baik (sehat < 5%).',
            'good_direction': 'lower',
        }
        base['car'] = {
            'name': 'Capital Adequacy Ratio (CAR)',
            'formula': 'Modal / ATMR',
            'description': 'Rasio kecukupan modal. Semakin tinggi semakin kuat (min 8-10%).',
            'good_direction': 'higher',
        }
        base['ldr'] = {
            'name': 'Loan to Deposit Ratio (LDR)',
            'formula': 'Total Kredit / DPK',
            'description': 'Rasio likuiditas. Idealnya rentang 78% - 92%.',
            'good_direction': 'optimal',
        }
        base['casa'] = {
            'name': 'CASA Ratio',
            'formula': '(Giro + Tabungan) / Total DPK',
            'description': 'Rasio dana murah. Semakin tinggi semakin efisien.',
            'good_direction': 'higher',
        }
        base['coverage_ratio'] = {
            'name': 'Coverage Ratio (CKPN)',
            'formula': 'Cadangan Kerugian / NPL',
            'description': 'Rasio pencadangan. Semakin tinggi semakin aman (>100% sangat baik).',
            'good_direction': 'higher',
        }
    elif subsector == 'insurance':
        # Insurance: Replace generic base metrics with insurance-relevant ones
        del base['accrual']
        del base['lt_debt_ratio']
        base.update({
            'roe': {
                'name': 'Return on Equity (ROE)',
                'formula': 'Net Income / Total Equity',
                'description': 'Mengukur kemampuan perusahaan menghasilkan laba dari ekuitas.',
                'good_direction': 'higher',
            },
            'net_margin': {
                'name': 'Net Profit Margin',
                'formula': 'Net Income / Total Revenue',
                'description': 'Persentase laba bersih dari total pendapatan premi.',
                'good_direction': 'higher',
            },
            'expense_ratio': {
                'name': 'Expense Ratio',
                'formula': 'Total Operating Expense / Total Revenue',
                'description': 'Rasio beban operasional terhadap pendapatan. Semakin rendah semakin efisien.',
                'good_direction': 'lower',
            },
            'der': {
                'name': 'Debt to Equity Ratio (DER)',
                'formula': 'Total Liabilities / Total Equity',
                'description': 'Rasio utang terhadap ekuitas. Stabilitas untuk perusahaan asuransi.',
                'good_direction': 'lower',
            },
            'loss_ratio': {
                'name': 'Loss Ratio (Proxy Combined Ratio)',
                'formula': 'Net Policyholder Benefits & Claims / Total Revenue',
                'description': 'Mengukur proporsi klaim terhadap pendapatan premi. < 100% berarti underwriting profit.',
                'good_direction': 'lower',
            },
        })
    elif subsector in ('leasing', 'securities'):
        # Leasing/Securities: Replace base with industry-relevant metrics
        # Remove generic Piotroski metrics (Accrual, LT Debt) — not relevant
        del base['accrual']
        del base['lt_debt_ratio']
        # Add common financial metrics
        base.update({
            'roe': {
                'name': 'Return on Equity (ROE)',
                'formula': 'Net Income / Total Equity',
                'description': 'Mengukur kemampuan perusahaan menghasilkan laba dari ekuitas.',
                'good_direction': 'higher',
            },
            'net_margin': {
                'name': 'Net Profit Margin',
                'formula': 'Net Income / Total Revenue',
                'description': 'Persentase laba bersih dari total pendapatan. Semakin tinggi semakin efisien.',
                'good_direction': 'higher',
            },
            'expense_ratio': {
                'name': 'Expense Ratio',
                'formula': 'Total Operating Expense / Total Revenue',
                'description': 'Rasio beban operasional terhadap pendapatan. Semakin rendah semakin efisien.',
                'good_direction': 'lower',
            },
            'der': {
                'name': 'Debt to Equity Ratio (DER)',
                'formula': 'Total Liabilities / Total Equity',
                'description': 'Rasio utang terhadap ekuitas. Stabilitas penting untuk industri financial.',
                'good_direction': 'lower',
            },
        })
        # Leasing-specific
        if subsector == 'leasing':
            base['npf_proxy'] = {
                'name': 'NPF Proxy (WriteOff/Loans)',
                'formula': '|Write Off| / Net Loans',
                'description': 'Proxy Non Performing Financing. Semakin rendah semakin baik. Sehat < 5%.',
                'good_direction': 'lower',
            }
            base['coc'] = {
                'name': 'Cost of Credit (CoC)',
                'formula': '|Write Off| / Total Assets',
                'description': 'Proxy biaya pencadangan kredit. Semakin rendah, kualitas kredit semakin baik.',
                'good_direction': 'lower',
            }
        # Securities-specific
        if subsector == 'securities':
            base['mkbd_proxy'] = {
                'name': 'MKBD Proxy (Equity/Assets)',
                'formula': 'Total Equity / Total Assets',
                'description': 'Proxy Modal Kerja Bersih Disesuaikan. Semakin tinggi semakin aman.',
                'good_direction': 'higher',
            }
    else:
        base.update({
            'current_ratio': {
                'name': 'Current Ratio',
                'formula': 'Current Assets / Current Liabilities',
                'description': 'Mengukur kemampuan perusahaan membayar kewajiban jangka pendek.',
                'good_direction': 'higher',
            },
            'gross_margin': {
                'name': 'Gross Margin',
                'formula': 'Gross Profit / Total Revenue × 100%',
                'description': 'Mengukur persentase pendapatan yang tersisa setelah dikurangi harga pokok penjualan.',
                'good_direction': 'higher',
            },
            'asset_turnover': {
                'name': 'Asset Turnover Ratio',
                'formula': 'Total Revenue / Total Assets',
                'description': 'Mengukur efisiensi perusahaan dalam menggunakan asetnya untuk menghasilkan pendapatan.',
                'good_direction': 'higher',
            },
        })

    
    return base
def _pct(val):

    """Format a ratio as percentage string for display."""
    if val is None:
        return 'N/A'
    return f"{val * 100:.2f}%"


def _ratio(val):

    """Format a ratio value for display."""
    if val is None:
        return 'N/A'
    return f"{val:.4f}"


def _fmt(val):

    """Format a number for display."""
    if val is None:
        return 'N/A'
    abs_v = abs(val)
    sign = '-' if val < 0 else ''
    if abs_v >= 1e12:
        return f"{sign}{abs_v/1e12:.2f}T"
    if abs_v >= 1e9:
        return f"{sign}{abs_v/1e9:.2f}B"
    if abs_v >= 1e6:
        return f"{sign}{abs_v/1e6:.2f}M"
    return f"{sign}{abs_v:,.0f}"


def _find_matching_col(df: pd.DataFrame, target_col):

    """Find the matching or closest column in a DataFrame by date."""
    if df is None or df.empty:
        return None
    if target_col in df.columns:
        return target_col
    # Try to find the closest date column
    if hasattr(target_col, 'year'):
        for c in df.columns:
            if hasattr(c, 'year') and c.year == target_col.year:
                return c
    return None


def _safe_get(df: pd.DataFrame, col, keys: list):

    """Safely retrieve a value from a DataFrame by trying multiple key names."""
    if df is None or df.empty or col is None:
        return None
    for key in keys:
        if key in df.index:
            try:
                val = df.loc[key, col]
                if pd.notna(val):
                    return float(val)
            except (KeyError, TypeError):
                continue
    return None


def _safe_divide(numerator, denominator):

    """Safely divide two numbers."""
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def _format_number(value):

    """Format a number for JSON output."""
    if value is None:
        return None
    return round(float(value), 2)


def _format_ratio(value):

    """Format a ratio for JSON output."""
    if value is None:
        return None
    return round(float(value), 6)
