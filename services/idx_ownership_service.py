"""
IDX Ownership Service — Load, cache, and query IDX/KSEI shareholder CSV data.

Supports two datasets:
  - Pemegang Saham ≥1% (KSEI): 12-column format
  - Kepemilikan Efek ≥5% berdasarkan SID: 18-column format with daily changes
"""

import os
import glob
import logging
import pandas as pd

logger = logging.getLogger(__name__)

# Base data directory and specific sub-directories
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DIR_1PERSEN = os.path.join(DATA_DIR, "1persen")
DIR_5PERSEN = os.path.join(DATA_DIR, "5persen")

# ─── In-memory cache ─────────────────────────────────────────────────
_cache_1persen = None
_cache_5persen = None
_cache_1persen_path = None
_cache_5persen_path = None


def _find_latest_csv(pattern, directory):
    """Find the latest CSV file matching the given glob pattern in the specified directory."""
    files = glob.glob(os.path.join(directory, pattern))
    if not files:
        return None
    # Sort by filename (date prefix YYYYMMDD ensures correct order)
    files.sort(reverse=True)
    return files[0]


def get_available_dates(dataset_type='5%'):
    """
    Get a list of available dates from the dataset filenames.
    Returns structurally sorted YYYY-MM-DD format strings.
    """
    if dataset_type == '5%':
        pattern = "*Kepemilikan_Efek_5persen_SID.csv"
        directory = DIR_5PERSEN
    else:
        pattern = "*Pemegang_Saham_1persen_KSEI.csv"
        directory = DIR_1PERSEN
        
    files = glob.glob(os.path.join(directory, pattern))
    dates = []
    for f in files:
        basename = os.path.basename(f)
        try:
            # Assumes filename starts with YYYYMMDD
            date_str = basename.split('_')[0]
            if len(date_str) == 8 and date_str.isdigit():
                formatted_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
                if formatted_date not in dates:
                    dates.append(formatted_date)
        except Exception:
            continue
            
    dates.sort(reverse=True)
    return dates


def _parse_id_number(val):
    """Parse Indonesian-formatted number (e.g., '3.200.142.830' or '41,10') 
    or US-formatted number ('25,786,900') to float."""
    if pd.isna(val) or val is None or val == '' or val == 'None' or val == 'nan':
        return None
    s = str(val).strip()
    if not s or s.lower() == 'nan':
        return None
        
    s = s.replace(' ', '')
    
    # Check if number contains both commas and dots
    if ',' in s and '.' in s:
        last_comma = s.rfind(',')
        last_dot = s.rfind('.')
        if last_comma > last_dot:
            # Format: 1.234,56 (Indonesian)
            s = s.replace('.', '').replace(',', '.')
        else:
            # Format: 1,234.56 (US)
            s = s.replace(',', '')
    elif ',' in s:
        if s.count(',') > 1:
            # Format: 1,234,567 (US thousands)
            s = s.replace(',', '')
        else:
            parts = s.split(',')
            # If the part after the comma does not have exactly 3 digits, it's a decimal (e.g., '41,10')
            if len(parts[1]) != 3:
                s = s.replace(',', '.')
            else:
                s = s.replace(',', '')
    
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def load_1persen_data(force_reload=False):
    """
    Load the latest Pemegang Saham ≥1% KSEI CSV into a DataFrame.
    Results are cached in memory.
    """
    global _cache_1persen, _cache_1persen_path

    csv_path = _find_latest_csv("*Pemegang_Saham_1persen_KSEI.csv", DIR_1PERSEN)
    if csv_path is None:
        logger.warning("No 1%% KSEI CSV file found in %s", DIR_1PERSEN)
        return None

    if not force_reload and _cache_1persen is not None and _cache_1persen_path == csv_path:
        return _cache_1persen

    logger.info("Loading 1%% KSEI data from %s", csv_path)
    df = pd.read_csv(csv_path, dtype=str)

    # Normalize column names
    df.columns = [c.strip() for c in df.columns]

    # Parse numeric columns
    df['TOTAL_SHARES'] = df['TOTAL_HOLDING_SHARES'].apply(_parse_id_number)
    df['PCT'] = df['PERCENTAGE'].apply(_parse_id_number)

    # Replace all NaN values with None after columns are created (prevents 'NaN' in JSON response)
    df = df.replace({float('nan'): None, pd.NA: None})
    df = df.where(pd.notna(df), None)

    _cache_1persen = df
    _cache_1persen_path = csv_path
    logger.info("Loaded 1%% data: %d rows", len(df))
    return df


def load_5persen_data(date=None, force_reload=False):
    """
    Load the Kepemilikan Efek ≥5% SID CSV matching the date (or latest) into a DataFrame.
    Results are cached in memory.
    Args:
        date: YYYY-MM-DD string. If None, uses the latest available data.
    """
    global _cache_5persen, _cache_5persen_path

    if date:
        date_prefix = date.replace("-", "")
        pattern = f"{date_prefix}_Kepemilikan_Efek_5persen_SID.csv"
        csv_path = os.path.join(DIR_5PERSEN, pattern)
        if not os.path.exists(csv_path):
            logger.warning("No 5%% SID CSV file found for date %s in %s", date, DIR_5PERSEN)
            return None
    else:
        csv_path = _find_latest_csv("*Kepemilikan_Efek_5persen_SID.csv", DIR_5PERSEN)
        if csv_path is None:
            logger.warning("No 5%% SID CSV file found in %s", DIR_5PERSEN)
            return None

    if not force_reload and _cache_5persen is not None and _cache_5persen_path == csv_path:
        return _cache_5persen

    logger.info("Loading 5%% SID data from %s", csv_path)
    df = pd.read_csv(csv_path, dtype=str)
    df.columns = [c.strip() for c in df.columns]

    # Parse the 'Perubahan' column
    if 'Perubahan' in df.columns:
        df['CHANGE'] = df['Perubahan'].apply(_parse_id_number).fillna(0)
        
    # Replace all NaN values with None
    df = df.replace({float('nan'): None, pd.NA: None})
    df = df.where(pd.notna(df), None)

    _cache_5persen = df
    _cache_5persen_path = csv_path
    logger.info("Loaded 5%% data: %d rows", len(df))
    return df


def get_shareholders(ticker):
    """
    Return all shareholders ≥1% for a given ticker code from KSEI data.

    Args:
        ticker: Stock code (e.g., 'BBCA', 'AADI')

    Returns:
        dict with 'shareholders' list and 'summary' stats, or None if no data.
    """
    df = load_1persen_data()
    if df is None:
        return None

    ticker = ticker.upper().replace('.JK', '')
    filtered = df[df['SHARE_CODE'] == ticker].copy()

    if filtered.empty:
        return None

    # Get emiten name from first row
    issuer_name = filtered.iloc[0].get('ISSUER_NAME', ticker)
    report_date = filtered.iloc[0].get('DATE', 'N/A')

    # Build shareholder list
    shareholders = []
    for _, row in filtered.iterrows():
        shareholders.append({
            'investor_name': row.get('INVESTOR_NAME', ''),
            'investor_type': row.get('INVESTOR_TYPE', ''),
            'local_foreign': row.get('LOCAL_FOREIGN', ''),
            'nationality': row.get('NATIONALITY', ''),
            'domicile': row.get('DOMICILE', ''),
            'total_shares': row.get('TOTAL_SHARES'),
            'percentage': row.get('PCT'),
        })

    # Sort by percentage descending
    shareholders.sort(key=lambda x: x['percentage'] or 0, reverse=True)

    # Summary stats
    total_shareholders = len(shareholders)
    local_holders = [s for s in shareholders if s['local_foreign'] == 'L']
    foreign_holders = [s for s in shareholders if s['local_foreign'] == 'A']
    local_pct = sum(s['percentage'] or 0 for s in local_holders)
    foreign_pct = sum(s['percentage'] or 0 for s in foreign_holders)

    # Investor type breakdown
    type_map = {
        'CP': 'Corporate',
        'ID': 'Individual',
        'IS': 'Insurance',
        'IB': 'Investment Bank',
        'MF': 'Mutual Fund',
        'PF': 'Pension Fund',
        'FD': 'Foundation',
        'SC': 'Securities Company',
        'OT': 'Other',
    }
    type_breakdown = {}
    for s in shareholders:
        t = s['investor_type']
        label = type_map.get(t, t or 'Unknown')
        if label not in type_breakdown:
            type_breakdown[label] = {'count': 0, 'pct': 0}
        type_breakdown[label]['count'] += 1
        type_breakdown[label]['pct'] += s['percentage'] or 0

    # Round percentages
    for v in type_breakdown.values():
        v['pct'] = round(v['pct'], 2)

    # Top 5 concentration
    top5_pct = sum(s['percentage'] or 0 for s in shareholders[:5])

    return {
        'ticker': ticker,
        'issuer_name': issuer_name,
        'report_date': report_date,
        'total_shareholders': total_shareholders,
        'local_pct': round(local_pct, 2),
        'foreign_pct': round(foreign_pct, 2),
        'top5_concentration': round(top5_pct, 2),
        'type_breakdown': type_breakdown,
        'shareholders': shareholders,
    }


def get_ownership_changes(ticker=None, min_change=0, date=None):
    """
    Return ownership changes from the 5% SID dataset.

    Args:
        ticker: Optional ticker filter
        min_change: Minimum absolute change to include (default 0 = all non-zero)
        date: Optional YYYY-MM-DD string to get data for a specific date

    Returns:
        List of dicts with change data.
    """
    df = load_5persen_data(date=date)
    if df is None:
        return []

    # Only keep "summary" rows (those with a 'No' value — these are per-investor aggregates)
    summary = df[df['No'].notna() & (df['No'] != '') & (df['No'] != 'None')].copy()

    if ticker:
        ticker = ticker.upper().replace('.JK', '')
        summary = summary[summary['Kode Efek'] == ticker]

    if summary.empty:
        return []

    # Find percentage columns and total share columns dynamically
    pct_cols = [c for c in summary.columns if 'Persentase' in c]
    saham_cols = [c for c in summary.columns if 'Saham Gabungan Per Investor' in c]

    results = []
    for _, row in summary.iterrows():
        change_val = _parse_id_number(row.get('Perubahan', 0)) or 0

        # Recalculate from Saham Gabungan if Perubahan is reported as 0 but there's an actual change
        if change_val == 0 and len(saham_cols) >= 2:
            try:
                t1_shares = _parse_id_number(row.get(saham_cols[0])) or 0
                # Use the last column in case there are >2
                t2_shares = _parse_id_number(row.get(saham_cols[-1])) or 0
                calc_change = t2_shares - t1_shares
                if calc_change != 0:
                    change_val = calc_change
            except Exception:
                pass

        if change_val == 0:
            continue

        if min_change > 0 and abs(change_val) < min_change:
            continue

        entry = {
            'kode_efek': row.get('Kode Efek', ''),
            'nama_emiten': row.get('Nama Emiten', ''),
            'nama_investor': row.get('Nama Pemegang Saham', ''),
            'perubahan': change_val,
        }

        # Add percentage columns dynamically
        for i, col in enumerate(pct_cols):
            val = _parse_id_number(row.get(col))
            entry[f'pct_{i+1}'] = val

        results.append(entry)

    # Sort by absolute change descending
    results.sort(key=lambda x: abs(x.get('perubahan', 0)), reverse=True)

    return results


def search_investor(query, limit=50):
    """
    Search for an investor name across all tickers in the 1% dataset.

    Args:
        query: Search string (case-insensitive partial match)
        limit: Max results to return

    Returns:
        List of dicts with investor holdings across different tickers.
    """
    df = load_1persen_data()
    if df is None:
        return []

    query_upper = query.upper().strip()
    if not query_upper:
        return []

    mask = df['INVESTOR_NAME'].str.upper().str.contains(query_upper, na=False)
    matched = df[mask].head(limit)

    results = []
    for _, row in matched.iterrows():
        results.append({
            'share_code': row.get('SHARE_CODE', ''),
            'issuer_name': row.get('ISSUER_NAME', ''),
            'investor_name': row.get('INVESTOR_NAME', ''),
            'investor_type': row.get('INVESTOR_TYPE', ''),
            'local_foreign': row.get('LOCAL_FOREIGN', ''),
            'total_shares': row.get('TOTAL_SHARES'),
            'percentage': row.get('PCT'),
        })

    return results


def get_available_tickers():
    """Return list of all ticker codes available in the 1% dataset."""
    df = load_1persen_data()
    if df is None:
        return []
    tickers = df['SHARE_CODE'].dropna().unique().tolist()
    tickers.sort()
    return tickers
