"""
Financial Data Scraper Module
Fetches financial data from Yahoo Finance with WSJ Markets as fallback.
Calculates key financial metrics and Piotroski F-Score.

Note: Scoring functions have been extracted to sub-modules for modularity:
- scrapers/scoring/utils.py      — Utility functions, sector detection, metrics info
- scrapers/scoring/piotroski.py  — Standard Piotroski F-Score
- scrapers/scoring/sector_scores.py — Bank, insurance, leasing, securities scoring + valuation
These functions are still defined in this file for backward compatibility.
New code should import from scrapers.scoring instead.
"""

import copy
import logging
import traceback

import yfinance as yf
import pandas as pd
from cachetools import TTLCache, cached

from config import Config

try:
    from scrapers.ojk import get_bank_ratios
except ImportError:
    get_bank_ratios = None

logger = logging.getLogger(__name__)

# TTL cache: results expire after CACHE_TTL seconds (default 5 min)
_scrape_cache = TTLCache(maxsize=Config.CACHE_MAX_SIZE, ttl=Config.CACHE_TTL)


# ─── Unified entry point with fallback ──────────────────────────────────────────


def _calc_completeness(result: dict) -> float:

    """
    Calculate data completeness as a ratio (0.0 to 1.0).
    Checks how many raw data fields are non-None across all years.
    For banks/financial sector, excludes fields that are intentionally N/A
    (gross_profit, current_assets, current_liabilities).
    """
    if not result.get('success') or not result.get('data'):
        return 0.0

    
    raw_keys = ['net_income', 'total_revenue', 'gross_profit', 'total_assets',
                'current_assets', 'current_liabilities', 'long_term_debt',
                'operating_cashflow', 'interest_income', 'interest_expense',
                'total_equity', 'total_operating_expense', 'operating_income']

    
    # For banks, exclude fields that are intentionally set to None
    is_bank = result.get('is_bank', False)
    sector = result.get('company', {}).get('sector', '')
    if is_bank or _is_financial_sector(sector, result.get('company', {}).get('industry', '')):
        bank_excluded = {'gross_profit', 'current_assets', 'current_liabilities'}
        raw_keys = [k for k in raw_keys if k not in bank_excluded]
    total_fields = 0
    filled_fields = 0
    for year_data in result['data']:
        raw = year_data.get('raw', {})
        for key in raw_keys:
            total_fields += 1
            if raw.get(key) is not None:
                filled_fields += 1

    
    return filled_fields / total_fields if total_fields > 0 else 0.0


def _merge_results(yahoo: dict, wsj: dict) -> dict:

    """
    Merge Yahoo and WSJ results: use Yahoo as base, fill N/A fields from WSJ.
    """
    merged = dict(yahoo)  # shallow copy
    merged['data'] = []

    
    # Build a year→index map for WSJ data
    wsj_year_map = {}
    for idx, yd in enumerate(wsj.get('data', [])):
        wsj_year_map[yd['year']] = idx

    
    raw_keys = ['net_income', 'total_revenue', 'gross_profit', 'total_assets',
                'current_assets', 'current_liabilities', 'long_term_debt',
                'operating_cashflow', 'shares_outstanding', 'interest_income',
                'interest_expense', 'total_equity', 'total_operating_expense',
                'operating_income']

    
    for yahoo_yd in yahoo.get('data', []):
        merged_yd = {
            'year': yahoo_yd['year'],
            'date': yahoo_yd['date'],
            'raw': dict(yahoo_yd['raw']),
            'metrics': dict(yahoo_yd['metrics']),
        }

        
        # Find matching WSJ year
        wsj_idx = wsj_year_map.get(yahoo_yd['year'])
        if wsj_idx is not None:
            wsj_yd = wsj['data'][wsj_idx]
            wsj_raw = wsj_yd.get('raw', {})

            
            # Fill None values from WSJ
            for key in raw_keys:
                if merged_yd['raw'].get(key) is None and wsj_raw.get(key) is not None:
                    merged_yd['raw'][key] = wsj_raw[key]

            
            # Recalculate metrics with merged raw data
            raw = merged_yd['raw']
            roa = _safe_divide(raw.get('net_income'), raw.get('total_assets'))
            current_ratio = _safe_divide(raw.get('current_assets'), raw.get('current_liabilities'))
            gross_margin = _safe_divide(raw.get('gross_profit'), raw.get('total_revenue'))
            asset_turnover = _safe_divide(raw.get('total_revenue'), raw.get('total_assets'))
            lt_debt_ratio = _safe_divide(raw.get('long_term_debt'), raw.get('total_assets'))

            
            accrual = None
            ni = raw.get('net_income')
            ocf = raw.get('operating_cashflow')
            ta = raw.get('total_assets')
            if ni is not None and ocf is not None and ta is not None and ta != 0:
                accrual = (ni - ocf) / ta

            
            # Bank-specific metrics
            ii = raw.get('interest_income')
            ie = raw.get('interest_expense')
            nim = None
            if ii is not None and ie is not None and ta is not None and ta != 0:
                nim = (ii - ie) / ta
            roe = _safe_divide(raw.get('net_income'), raw.get('total_equity'))
            bopo = _safe_divide(raw.get('total_operating_expense'), raw.get('operating_income'))

            
            merged_yd['metrics'] = {
                'roa': _format_ratio(roa),
                'cash_flow': _format_number(raw.get('operating_cashflow')),
                'net_income': _format_number(raw.get('net_income')),
                'accrual': _format_ratio(accrual),
                'lt_debt_ratio': _format_ratio(lt_debt_ratio),
                'current_ratio': _format_ratio(current_ratio),
                'gross_margin': _format_ratio(gross_margin),
                'asset_turnover': _format_ratio(asset_turnover),
                'nim': _format_ratio(nim),
                'roe': _format_ratio(roe),
                'bopo': _format_ratio(bopo),
            }

        
        merged['data'].append(merged_yd)

    
    # Recalculate Piotroski with merged data
    merged_sector = merged.get('company', {}).get('sector', 'N/A')
    merged_ticker = merged.get('company', {}).get('ticker', '')
    merged['piotroski'] = _calculate_piotroski(merged['data'], merged_sector, ticker=merged_ticker)

    
    return merged


@cached(cache=_scrape_cache)
def scrape_financials(ticker_symbol: str) -> dict:

    """
    Scrape financial data from Yahoo Finance and calculate key metrics.

    
    Metrics calculated:
    - ROA (Return on Assets)
    - Cash Flow (Operating Cash Flow)
    - Net Income
    - Kualitas Laba / Accrual Ratio
    - Rasio Utang Jangka Panjang (Long-term Debt Ratio)
    - Current Ratio
    - Gross Margin
    - Asset Turnover Ratio

    
    Args:
        ticker_symbol: Stock ticker (e.g., 'AAPL', 'BBCA.JK')

    
    Returns:
        dict with company info, yearly metrics, and metadata
    """
    try:
        ticker = yf.Ticker(ticker_symbol)

        
        # Get company info (wrapped in try/except as it can fail)
        company_name = ticker_symbol
        sector = 'N/A'
        industry = 'N/A'
        currency = 'USD'
        market_cap = None
        current_price = None

        
        try:
            info = ticker.info
            if info:
                company_name = info.get('longName', info.get('shortName', ticker_symbol))
                sector = info.get('sector', 'N/A')
                industry = info.get('industry', 'N/A')
                currency = info.get('currency', 'USD')
                market_cap = info.get('marketCap', None)
                current_price = info.get('currentPrice', info.get('regularMarketPrice', None))
        except Exception:
            pass  # Continue with defaults if info fetch fails

        
        # Fetch financial statements (annual)
        income_stmt = ticker.income_stmt
        balance_sheet = ticker.balance_sheet
        cashflow = ticker.cashflow

        
        if income_stmt is None or income_stmt.empty:
            return {
                'success': False,
                'error': f'No financial data available for ticker: {ticker_symbol}'
            }

        
        # Handle cases where balance_sheet or cashflow might be empty
        if balance_sheet is None:
            balance_sheet = pd.DataFrame()
        if cashflow is None:
            cashflow = pd.DataFrame()

        
        # Get available years (columns are dates)
        years = []
        yearly_data = []

        
        # Use the columns (dates) from income statement as reference
        for col in income_stmt.columns:
            year_label = str(col.year) if hasattr(col, 'year') else str(col)

            
            # Find matching column in balance_sheet/cashflow (may not be exact same timestamp)
            bs_col = _find_matching_col(balance_sheet, col)
            cf_col = _find_matching_col(cashflow, col)

            
            # Extract raw values safely
            net_income = _safe_get(income_stmt, col, [
                'Net Income', 'Net Income Common Stockholders'
            ])
            total_revenue = _safe_get(income_stmt, col, [
                'Total Revenue', 'Operating Revenue'
            ])
            gross_profit = _safe_get(income_stmt, col, [
                'Gross Profit'
            ])

            
            total_assets = _safe_get(balance_sheet, bs_col, [
                'Total Assets'
            ])
            current_assets = _safe_get(balance_sheet, bs_col, [
                'Current Assets'
            ])
            current_liabilities = _safe_get(balance_sheet, bs_col, [
                'Current Liabilities'
            ])
            long_term_debt = _safe_get(balance_sheet, bs_col, [
                'Long Term Debt', 'Long Term Debt And Capital Lease Obligation'
            ])
            total_liabilities = _safe_get(balance_sheet, bs_col, [
                'Total Liabilities Net Minority Interest', 'Total Liabilities'
            ])

            
            operating_cashflow = _safe_get(cashflow, cf_col, [
                'Operating Cash Flow', 'Cash Flow From Continuing Operating Activities',
                'Cash Flowsfromusedin Operating Activities Direct',
            ])
            # Cash & Equivalents
            cash_financial = _safe_get(balance_sheet, bs_col, [
                'Cash And Cash Equivalents', 'Cash Cash Equivalents And Short Term Investments',
                'Cash Financial', 'Cash'
            ])
            # Retained Earnings
            retained_earnings = _safe_get(balance_sheet, bs_col, [
                'Retained Earnings', 'Retained Earnings Accumulated Deficit'
            ])

            
            # Shares outstanding (for Piotroski criterion #7)
            shares_outstanding = _safe_get(balance_sheet, bs_col, [
                'Ordinary Shares Number', 'Share Issued',
                'Common Stock Shares Outstanding'
            ])

            
            # Bank-specific raw data
            interest_income = _safe_get(income_stmt, col, [
                'Net Interest Income', 'Interest Income',
            ])
            interest_expense = _safe_get(income_stmt, col, [
                'Interest Expense', 'Interest Expense Non Operating',
            ])
            total_equity = _safe_get(balance_sheet, bs_col, [
                'Stockholders Equity', 'Total Equity Gross Minority Interest',
                'Common Stock Equity',
            ])
            total_operating_expense = _safe_get(income_stmt, col, [
                'Total Expenses', 'Operating Expense',
                'Selling General And Administration',
            ])
            operating_income = _safe_get(income_stmt, col, [
                'Operating Income', 'Operating Revenue',
                'Total Revenue',
            ])
            # Bank: Write Off (proxy for Cost of Credit / provision for loan losses)
            write_off = _safe_get(income_stmt, col, [
                'Write Off', 'Provision For Doubtful Accounts',
            ])
            # Insurance: Net Policyholder Benefits & Claims
            net_policyholder_claims = _safe_get(income_stmt, col, [
                'Net Policyholder Benefits And Claims',
                'Policyholder Benefits Ceded',
            ])
            # Bank Details
            total_loans = _safe_get(balance_sheet, bs_col, [
                'Net Loan', 'Net Loans', 'Loans Net', 'Total Loans'
            ])
            total_deposits = _safe_get(balance_sheet, bs_col, [
                'Total Deposits', 'Deposits'
            ])
            # Management Effectiveness raw data
            ebit = _safe_get(income_stmt, col, ['EBIT', 'Operating Income'])
            cost_of_revenue = _safe_get(income_stmt, col, ['Cost Of Revenue', 'Reconciled Cost Of Revenue'])
            accounts_receivable = _safe_get(balance_sheet, bs_col, ['Accounts Receivable', 'Receivables'])
            inventory = _safe_get(balance_sheet, bs_col, ['Inventory'])
            accounts_payable = _safe_get(balance_sheet, bs_col, ['Accounts Payable', 'Payables'])
            invested_capital = _safe_get(balance_sheet, bs_col, ['Invested Capital'])
            tax_provision = _safe_get(income_stmt, col, ['Tax Provision'])
            pretax_income = _safe_get(income_stmt, col, ['Pretax Income'])

            
            # Calculate metrics
            # ROA using Average Assets (more accurate)
            avg_assets = total_assets
            if total_assets is not None and hasattr(col, 'year'):
                target_year = col.year - 1
                prev_assets = None
                # Look for previous year column in balance_sheet
                if balance_sheet is not None:
                    for c in balance_sheet.columns:
                        if hasattr(c, 'year') and c.year == target_year:
                             prev_assets = _safe_get(balance_sheet, c, ['Total Assets'])
                             break
                if prev_assets:
                     avg_assets = (total_assets + prev_assets) / 2
            roa = _safe_divide(net_income, avg_assets)
            current_ratio = _safe_divide(current_assets, current_liabilities)
            gross_margin = _safe_divide(gross_profit, total_revenue)
            asset_turnover = _safe_divide(total_revenue, total_assets)
            lt_debt_ratio = _safe_divide(long_term_debt, total_assets)

            
            # Accrual (Earnings Quality) = (Net Income - Operating Cash Flow) / Total Assets
            accrual = None
            if net_income is not None and operating_cashflow is not None and total_assets is not None and total_assets != 0:
                accrual = (net_income - operating_cashflow) / total_assets

            
            # Bank-specific metrics
            nim = None
            if interest_income is not None and interest_expense is not None and total_assets is not None and total_assets != 0:
                nim = (interest_income - (interest_expense if interest_expense else 0)) / total_assets
            roe = _safe_divide(net_income, total_equity)
            bopo = _safe_divide(total_operating_expense, operating_income)
            # Cost of Funds (CoF) = Interest Expense / Total Liabilities
            # Proxy for CASA (low cost funds).
            cost_of_funds = None
            if interest_expense is not None and total_liabilities is not None and total_liabilities != 0:
                cost_of_funds = interest_expense / total_liabilities
            elif interest_expense is not None and total_assets and total_equity:
                # Fallback: Liab = Assets - Equity
                implied_liab = total_assets - total_equity
                if implied_liab != 0:
                   cost_of_funds = interest_expense / implied_liab
            # Cost of Credit (Bank): Write Off / Total Assets
            coc = None
            if write_off is not None and total_assets is not None and total_assets != 0:
                coc = abs(write_off) / total_assets  # write_off is usually negative
            # Loss Ratio (Insurance): Claims / Revenue
            loss_ratio = None
            if net_policyholder_claims is not None and total_revenue is not None and total_revenue != 0:
                loss_ratio = net_policyholder_claims / total_revenue
            # Leasing/Securities/Insurance metrics
            net_margin = _safe_divide(net_income, total_revenue)
            expense_ratio = _safe_divide(total_operating_expense, total_revenue)
            # DER = Total Liabilities / Total Equity (fallback: liab = assets - equity)
            _liab = total_liabilities if total_liabilities is not None else (
                (total_assets - total_equity) if (total_assets is not None and total_equity is not None) else None
            )
            der = _safe_divide(_liab, total_equity)
            # NPF Proxy: |Write Off| / Net Loans
            npf_proxy = _safe_divide(abs(write_off) if write_off else None, total_loans)
            # MKBD Proxy: Equity / Total Assets
            mkbd_proxy = _safe_divide(total_equity, total_assets)
            # ── Management Effectiveness Metrics ──
            # ROCE = EBIT / Capital Employed (Total Assets - Current Liabilities)
            capital_employed = None
            if total_assets is not None and current_liabilities is not None:
                capital_employed = total_assets - current_liabilities
            roce = _safe_divide(ebit, capital_employed)
            # ROIC = NOPAT / Invested Capital
            # NOPAT = EBIT × (1 - Tax Rate)
            roic = None
            if ebit is not None and invested_capital is not None and invested_capital != 0:
                tax_rate = 0.0
                if tax_provision is not None and pretax_income is not None and pretax_income != 0:
                    tax_rate = max(0, min(1, tax_provision / pretax_income))  # clamp 0-1
                nopat = ebit * (1 - tax_rate)
                roic = nopat / invested_capital
            # DSO = (Accounts Receivable / Revenue) × 365
            dso = None
            if accounts_receivable is not None and total_revenue is not None and total_revenue != 0:
                dso = (accounts_receivable / total_revenue) * 365
            # DSI = (Inventory / COGS) × 365
            dsi = None
            if inventory is not None and cost_of_revenue is not None and cost_of_revenue != 0:
                dsi = (inventory / cost_of_revenue) * 365
            # DPO = (Accounts Payable / COGS) × 365
            dpo = None
            if accounts_payable is not None and cost_of_revenue is not None and cost_of_revenue != 0:
                dpo = (accounts_payable / cost_of_revenue) * 365
            # CCC = DSO + DSI - DPO
            ccc = None
            if dso is not None and dsi is not None and dpo is not None:
                ccc = dso + dsi - dpo
            # Receivables Turnover = Revenue / Accounts Receivable
            receivables_turnover = _safe_divide(total_revenue, accounts_receivable)
            # Inventory Turnover = COGS / Inventory
            inventory_turnover = _safe_divide(cost_of_revenue, inventory)
            # Bank Cleanup: specific metrics should be None for banks to avoid confusion
            if _is_financial_sector(sector, industry):
                gross_profit = None
                current_assets = None
                current_liabilities = None
                # Inventory-related metrics not applicable for financials
                dsi = None
                dpo = None
                ccc = None
                inventory_turnover = None
                dso = None
                receivables_turnover = None
            year_data = {
                'year': year_label,
                'date': str(col.strftime('%Y-%m-%d')) if hasattr(col, 'strftime') else str(col),
                'raw': {
                    'net_income': _format_number(net_income),
                    'total_revenue': _format_number(total_revenue),
                    'gross_profit': _format_number(gross_profit),
                    'total_assets': _format_number(total_assets),
                    'current_assets': _format_number(current_assets),
                    'current_liabilities': _format_number(current_liabilities),
                    'long_term_debt': _format_number(long_term_debt),
                    'operating_cashflow': _format_number(operating_cashflow),
                    'shares_outstanding': _format_number(shares_outstanding),
                    'interest_income': _format_number(interest_income),
                    'interest_expense': _format_number(interest_expense),
                    'total_equity': _format_number(total_equity),
                    'total_operating_expense': _format_number(total_operating_expense),
                    'operating_income': _format_number(operating_income),
                    'write_off': _format_number(write_off),
                    'net_policyholder_claims': _format_number(net_policyholder_claims),
                    'total_liabilities': _format_number(total_liabilities),
                    'retained_earnings': _format_number(retained_earnings),
                    'cash_financial': _format_number(cash_financial),
                    'total_loans': _format_number(total_loans),
                    'total_deposits': _format_number(total_deposits),
                    'ebit': _format_number(ebit),
                    'cost_of_revenue': _format_number(cost_of_revenue),
                    'accounts_receivable': _format_number(accounts_receivable),
                    'inventory': _format_number(inventory),
                    'accounts_payable': _format_number(accounts_payable),
                    'invested_capital': _format_number(invested_capital),
                    'tax_provision': _format_number(tax_provision),
                    'pretax_income': _format_number(pretax_income),
                },
                'metrics': {
                    'roa': _format_ratio(roa),
                    'cash_flow': _format_number(operating_cashflow),
                    'net_income': _format_number(net_income),
                    'accrual': _format_ratio(accrual),
                    'lt_debt_ratio': _format_ratio(lt_debt_ratio),
                    'current_ratio': _format_ratio(current_ratio),
                    'gross_margin': _format_ratio(gross_margin),
                    'asset_turnover': _format_ratio(asset_turnover),
                    'nim': _format_ratio(nim),
                    'roe': _format_ratio(roe),
                    'bopo': _format_ratio(bopo),
                    'cost_of_funds': _format_ratio(cost_of_funds),
                    'coc': _format_ratio(coc),
                    'loss_ratio': _format_ratio(loss_ratio),
                    'net_margin': _format_ratio(net_margin),
                    'expense_ratio': _format_ratio(expense_ratio),
                    'der': _format_ratio(der),
                    'npf_proxy': _format_ratio(npf_proxy),
                    'mkbd_proxy': _format_ratio(mkbd_proxy),
                    'roce': _format_ratio(roce),
                    'roic': _format_ratio(roic),
                    'dso': _format_ratio(dso),
                    'dsi': _format_ratio(dsi),
                    'dpo': _format_ratio(dpo),
                    'ccc': _format_ratio(ccc),
                    'receivables_turnover': _format_ratio(receivables_turnover),
                    'inventory_turnover': _format_ratio(inventory_turnover),
                }
            }

            
            # Skip ghost year columns where core data is all None
            # Yahoo Finance sometimes creates placeholder columns with no actual data
            if net_income is None and total_revenue is None and total_assets is None:
                continue
            yearly_data.append(year_data)
            years.append(year_label)

        
        # Inject Real OJK Data for Banks (Historical & Latest)
        # Note: ojk_scraper now supports multi-year data. yearly_data usually has years in descending order.
        if _get_financial_subsector(sector, industry) == 'bank' and get_bank_ratios and yearly_data:
            try:
                for item in yearly_data:
                    # Parse year from item
                    year_val = item.get('year')
                    target_year = None
                    if isinstance(year_val, int):
                        target_year = year_val
                    elif isinstance(year_val, str) and year_val.isdigit():
                         target_year = int(year_val)
                    elif year_val in ['TTM', 'Current']:
                         # If TTM, we ask for latest (year=None)
                         target_year = None
                    # Fetch specific year data
                    # If target_year is None (TTM), get_bank_ratios returns latest.
                    # If target_year is 2024, it returns 2024 data (if cached).
                    ojk_data = get_bank_ratios(ticker_symbol, year=target_year)
                    if ojk_data:
                         # Verify if the returned data year matches the target year (if specified)
                         data_year = ojk_data.get('year')
                         if target_year and data_year != target_year:
                             continue # mismatch, e.g. asked for 2023 but got None? 
                             # Actually ojk_scraper returns None if year mismatch, so this check is redundant but safe.
                         metrics = item['metrics']
                         for k in ['npl', 'car', 'ldr', 'casa', 'nim', 'bopo', 'coc']:
                             if k in ojk_data: metrics[k] = _format_ratio(ojk_data[k])
                         if 'coverage' in ojk_data:
                             metrics['coverage_ratio'] = _format_ratio(ojk_data['coverage'])
                             metrics['coverage'] = _format_ratio(ojk_data['coverage'])
            except Exception as e:
                # Silently fail if OJK injection fails
                pass
        # Calculate Piotroski F-Score (auto-detect bank sector)
        piotroski = _calculate_piotroski(yearly_data, sector, industry, ticker=ticker_symbol)

        
        # Calculate Financial Valuation (Residual Income Model / PBV vs ROE)
        # Applies to all financial subsectors: bank, insurance, leasing, securities
        financial_valuation = None
        fin_subsector = _get_financial_subsector(sector, industry)
        if _is_financial_sector(sector, industry):
            # Try to get PBV from info, or calculate it
            pbv = info.get('priceToBook')
            if pbv is None and current_price and yearly_data:
                # Fallback: Price / (Equity / Shares) using most recent year
                latest = yearly_data[0]['raw']
                eq = latest.get('total_equity')
                sh = latest.get('shares_outstanding')
                if eq and sh and sh > 0:
                    bps = eq / sh
                    pbv = current_price / bps

            
            # Get ROE history
            roe_current = yearly_data[0]['metrics']['roe'] if yearly_data else None
            roe_prev = yearly_data[1]['metrics']['roe'] if len(yearly_data) > 1 else None

            
            financial_valuation = _calculate_financial_valuation(pbv, roe_current, roe_prev, subsector=fin_subsector)


        final_result = {
            'success': True,
            'ticker': ticker_symbol.upper(),
            'company': {
                'name': company_name,
                'sector': sector,
                'industry': industry,
                'currency': currency,
                'market_cap': _format_number(market_cap),
                'current_price': current_price,
                'pbv': _format_ratio(pbv) if _is_financial_sector(sector, industry) else None,
            },
            'years': years,
            'data': yearly_data,
            'piotroski': piotroski,
            'bank_valuation': financial_valuation,  # backward compat
            'financial_valuation': financial_valuation,
            'is_bank': _is_financial_sector(sector, industry),
            'financial_subsector': _get_financial_subsector(sector, industry),
            'metrics_info': _get_metrics_info(_get_financial_subsector(sector, industry)),
        }
        # Calculate data completeness
        final_result['data_completeness'] = round(_calc_completeness(final_result), 4)
        return final_result

    
    except Exception as e:
        return {
            'success': False,
            'error': f'Error fetching data for {ticker_symbol}: {str(e)}',
            'traceback': traceback.format_exc()
        }


@cached(cache=_scrape_cache)
def scrape_financials_quarterly(ticker_symbol: str) -> dict:
    """
    Scrape QUARTERLY financial data from Yahoo Finance.
    Identical logic to scrape_financials() but uses quarterly statements.
    Labels periods as 'Q1 2024', 'Q2 2024', etc.
    """
    try:
        ticker = yf.Ticker(ticker_symbol)
        # Get company info
        company_name = ticker_symbol
        sector = 'N/A'
        industry = 'N/A'
        currency = 'USD'
        market_cap = None
        current_price = None
        try:
            info = ticker.info
            if info:
                company_name = info.get('longName', info.get('shortName', ticker_symbol))
                sector = info.get('sector', 'N/A')
                industry = info.get('industry', 'N/A')
                currency = info.get('currency', 'USD')
                market_cap = info.get('marketCap', None)
                current_price = info.get('currentPrice', info.get('regularMarketPrice', None))
        except Exception:
            pass
        # Fetch QUARTERLY financial statements
        income_stmt = ticker.quarterly_income_stmt
        balance_sheet = ticker.quarterly_balance_sheet
        cashflow = ticker.quarterly_cashflow
        if income_stmt is None or income_stmt.empty:
            return {
                'success': False,
                'error': f'No quarterly financial data available for ticker: {ticker_symbol}'
            }
        if balance_sheet is None:
            balance_sheet = pd.DataFrame()
        if cashflow is None:
            cashflow = pd.DataFrame()
        years = []
        quarterly_data = []
        for col in income_stmt.columns:
            # Quarter label: Q1 2024, Q2 2024, etc.
            if hasattr(col, 'month'):
                month = col.month
                year = col.year
                if month <= 3:
                    q = 'Q1'
                elif month <= 6:
                    q = 'Q2'
                elif month <= 9:
                    q = 'Q3'
                else:
                    q = 'Q4'
                quarter_label = f'{q} {year}'
            else:
                quarter_label = str(col)
            bs_col = _find_matching_col(balance_sheet, col)
            cf_col = _find_matching_col(cashflow, col)
            # Extract raw values (same logic as annual)
            net_income = _safe_get(income_stmt, col, ['Net Income', 'Net Income Common Stockholders'])
            total_revenue = _safe_get(income_stmt, col, ['Total Revenue', 'Operating Revenue'])
            gross_profit = _safe_get(income_stmt, col, ['Gross Profit'])
            total_assets = _safe_get(balance_sheet, bs_col, ['Total Assets'])
            current_assets = _safe_get(balance_sheet, bs_col, ['Current Assets'])
            current_liabilities = _safe_get(balance_sheet, bs_col, ['Current Liabilities'])
            long_term_debt = _safe_get(balance_sheet, bs_col, ['Long Term Debt', 'Long Term Debt And Capital Lease Obligation'])
            total_liabilities = _safe_get(balance_sheet, bs_col, ['Total Liabilities Net Minority Interest', 'Total Liabilities'])
            operating_cashflow = _safe_get(cashflow, cf_col, [
                'Operating Cash Flow', 'Cash Flow From Continuing Operating Activities',
                'Cash Flowsfromusedin Operating Activities Direct',
            ])
            cash_financial = _safe_get(balance_sheet, bs_col, [
                'Cash And Cash Equivalents', 'Cash Cash Equivalents And Short Term Investments',
                'Cash Financial', 'Cash'
            ])
            retained_earnings = _safe_get(balance_sheet, bs_col, [
                'Retained Earnings', 'Retained Earnings Accumulated Deficit'
            ])
            shares_outstanding = _safe_get(balance_sheet, bs_col, [
                'Ordinary Shares Number', 'Share Issued', 'Common Stock Shares Outstanding'
            ])
            # Bank-specific raw data
            interest_income = _safe_get(income_stmt, col, ['Net Interest Income', 'Interest Income'])
            interest_expense = _safe_get(income_stmt, col, ['Interest Expense', 'Interest Expense Non Operating'])
            total_equity = _safe_get(balance_sheet, bs_col, [
                'Stockholders Equity', 'Total Equity Gross Minority Interest', 'Common Stock Equity',
            ])
            total_operating_expense = _safe_get(income_stmt, col, [
                'Total Expenses', 'Operating Expense', 'Selling General And Administration',
            ])
            operating_income = _safe_get(income_stmt, col, [
                'Operating Income', 'Operating Revenue', 'Total Revenue',
            ])
            write_off = _safe_get(income_stmt, col, ['Write Off', 'Provision For Doubtful Accounts'])
            net_policyholder_claims = _safe_get(income_stmt, col, [
                'Net Policyholder Benefits And Claims', 'Policyholder Benefits Ceded',
            ])
            total_loans = _safe_get(balance_sheet, bs_col, ['Net Loan', 'Net Loans', 'Loans Net', 'Total Loans'])
            total_deposits = _safe_get(balance_sheet, bs_col, ['Total Deposits', 'Deposits'])
            # Management Effectiveness raw data
            ebit = _safe_get(income_stmt, col, ['EBIT', 'Operating Income'])
            cost_of_revenue = _safe_get(income_stmt, col, ['Cost Of Revenue', 'Reconciled Cost Of Revenue'])
            accounts_receivable = _safe_get(balance_sheet, bs_col, ['Accounts Receivable', 'Receivables'])
            inventory = _safe_get(balance_sheet, bs_col, ['Inventory'])
            accounts_payable = _safe_get(balance_sheet, bs_col, ['Accounts Payable', 'Payables'])
            invested_capital = _safe_get(balance_sheet, bs_col, ['Invested Capital'])
            tax_provision = _safe_get(income_stmt, col, ['Tax Provision'])
            pretax_income = _safe_get(income_stmt, col, ['Pretax Income'])
            # Calculate metrics
            roa = _safe_divide(net_income, total_assets)
            current_ratio = _safe_divide(current_assets, current_liabilities)
            gross_margin = _safe_divide(gross_profit, total_revenue)
            asset_turnover = _safe_divide(total_revenue, total_assets)
            lt_debt_ratio = _safe_divide(long_term_debt, total_assets)
            accrual = None
            if net_income is not None and operating_cashflow is not None and total_assets is not None and total_assets != 0:
                accrual = (net_income - operating_cashflow) / total_assets
            nim = None
            if interest_income is not None and interest_expense is not None and total_assets is not None and total_assets != 0:
                nim = (interest_income - (interest_expense if interest_expense else 0)) / total_assets
            roe = _safe_divide(net_income, total_equity)
            bopo = _safe_divide(total_operating_expense, operating_income)
            cost_of_funds = None
            if interest_expense is not None and total_liabilities is not None and total_liabilities != 0:
                cost_of_funds = interest_expense / total_liabilities
            coc = None
            if write_off is not None and total_assets is not None and total_assets != 0:
                coc = abs(write_off) / total_assets
            loss_ratio = None
            if net_policyholder_claims is not None and total_revenue is not None and total_revenue != 0:
                loss_ratio = net_policyholder_claims / total_revenue
            net_margin = _safe_divide(net_income, total_revenue)
            expense_ratio = _safe_divide(total_operating_expense, total_revenue)
            _liab = total_liabilities if total_liabilities is not None else (
                (total_assets - total_equity) if (total_assets is not None and total_equity is not None) else None
            )
            der = _safe_divide(_liab, total_equity)
            npf_proxy = _safe_divide(abs(write_off) if write_off else None, total_loans)
            mkbd_proxy = _safe_divide(total_equity, total_assets)
            # ── Management Effectiveness Metrics ──
            capital_employed = None
            if total_assets is not None and current_liabilities is not None:
                capital_employed = total_assets - current_liabilities
            roce = _safe_divide(ebit, capital_employed)
            roic = None
            if ebit is not None and invested_capital is not None and invested_capital != 0:
                tax_rate = 0.0
                if tax_provision is not None and pretax_income is not None and pretax_income != 0:
                    tax_rate = max(0, min(1, tax_provision / pretax_income))
                nopat = ebit * (1 - tax_rate)
                roic = nopat / invested_capital
            # For quarterly: use × 90 days instead of 365
            dso = None
            if accounts_receivable is not None and total_revenue is not None and total_revenue != 0:
                dso = (accounts_receivable / total_revenue) * 90
            dsi = None
            if inventory is not None and cost_of_revenue is not None and cost_of_revenue != 0:
                dsi = (inventory / cost_of_revenue) * 90
            dpo = None
            if accounts_payable is not None and cost_of_revenue is not None and cost_of_revenue != 0:
                dpo = (accounts_payable / cost_of_revenue) * 90
            ccc_val = None
            if dso is not None and dsi is not None and dpo is not None:
                ccc_val = dso + dsi - dpo
            receivables_turnover = _safe_divide(total_revenue, accounts_receivable)
            inventory_turnover = _safe_divide(cost_of_revenue, inventory)
            if _is_financial_sector(sector, industry):
                gross_profit = None
                current_assets = None
                current_liabilities = None
                dsi = None
                dpo = None
                ccc_val = None
                inventory_turnover = None
                dso = None
                receivables_turnover = None
            q_data = {
                'year': quarter_label,
                'date': str(col.strftime('%Y-%m-%d')) if hasattr(col, 'strftime') else str(col),
                'raw': {
                    'net_income': _format_number(net_income),
                    'total_revenue': _format_number(total_revenue),
                    'gross_profit': _format_number(gross_profit),
                    'total_assets': _format_number(total_assets),
                    'current_assets': _format_number(current_assets),
                    'current_liabilities': _format_number(current_liabilities),
                    'long_term_debt': _format_number(long_term_debt),
                    'operating_cashflow': _format_number(operating_cashflow),
                    'shares_outstanding': _format_number(shares_outstanding),
                    'interest_income': _format_number(interest_income),
                    'interest_expense': _format_number(interest_expense),
                    'total_equity': _format_number(total_equity),
                    'total_operating_expense': _format_number(total_operating_expense),
                    'operating_income': _format_number(operating_income),
                    'write_off': _format_number(write_off),
                    'net_policyholder_claims': _format_number(net_policyholder_claims),
                    'total_liabilities': _format_number(total_liabilities),
                    'retained_earnings': _format_number(retained_earnings),
                    'cash_financial': _format_number(cash_financial),
                    'total_loans': _format_number(total_loans),
                    'total_deposits': _format_number(total_deposits),
                    'ebit': _format_number(ebit),
                    'cost_of_revenue': _format_number(cost_of_revenue),
                    'accounts_receivable': _format_number(accounts_receivable),
                    'inventory': _format_number(inventory),
                    'accounts_payable': _format_number(accounts_payable),
                    'invested_capital': _format_number(invested_capital),
                    'tax_provision': _format_number(tax_provision),
                    'pretax_income': _format_number(pretax_income),
                },
                'metrics': {
                    'roa': _format_ratio(roa),
                    'cash_flow': _format_number(operating_cashflow),
                    'net_income': _format_number(net_income),
                    'accrual': _format_ratio(accrual),
                    'lt_debt_ratio': _format_ratio(lt_debt_ratio),
                    'current_ratio': _format_ratio(current_ratio),
                    'gross_margin': _format_ratio(gross_margin),
                    'asset_turnover': _format_ratio(asset_turnover),
                    'nim': _format_ratio(nim),
                    'roe': _format_ratio(roe),
                    'bopo': _format_ratio(bopo),
                    'cost_of_funds': _format_ratio(cost_of_funds),
                    'coc': _format_ratio(coc),
                    'loss_ratio': _format_ratio(loss_ratio),
                    'net_margin': _format_ratio(net_margin),
                    'expense_ratio': _format_ratio(expense_ratio),
                    'der': _format_ratio(der),
                    'npf_proxy': _format_ratio(npf_proxy),
                    'mkbd_proxy': _format_ratio(mkbd_proxy),
                    'roce': _format_ratio(roce),
                    'roic': _format_ratio(roic),
                    'dso': _format_ratio(dso),
                    'dsi': _format_ratio(dsi),
                    'dpo': _format_ratio(dpo),
                    'ccc': _format_ratio(ccc_val),
                    'receivables_turnover': _format_ratio(receivables_turnover),
                    'inventory_turnover': _format_ratio(inventory_turnover),
                }
            }
            # Skip ghost columns
            if net_income is None and total_revenue is None and total_assets is None:
                continue
            quarterly_data.append(q_data)
            years.append(quarter_label)
        if not quarterly_data:
            return {
                'success': False,
                'error': f'No quarterly financial data available for ticker: {ticker_symbol}'
            }
        final_result = {
            'success': True,
            'ticker': ticker_symbol.upper(),
            'freq': 'quarterly',
            'company': {
                'name': company_name,
                'sector': sector,
                'industry': industry,
                'currency': currency,
                'market_cap': _format_number(market_cap),
                'current_price': current_price,
                'pbv': None,
            },
            'years': years,
            'data': quarterly_data,
            'piotroski': None,  # Not applicable for quarterly
            'bank_valuation': None,
            'financial_valuation': {'available': False, 'reason': 'Not applicable for quarterly data'},
            'is_bank': _is_financial_sector(sector, industry),
            'financial_subsector': _get_financial_subsector(sector, industry),
            'metrics_info': _get_metrics_info(_get_financial_subsector(sector, industry)),
        }
        final_result['data_completeness'] = round(_calc_completeness(final_result), 4)
        return final_result
    except Exception as e:
        return {
            'success': False,
            'error': f'Error fetching quarterly data for {ticker_symbol}: {str(e)}',
            'traceback': traceback.format_exc()
        }


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


def get_financials(ticker_symbol: str, target_year: int = None, freq: str = 'annual') -> dict:
    """
    Get financial data with automatic fallback.
    Args:
        ticker_symbol: Stock ticker symbol
        target_year: Target fiscal year for scoring (annual mode only)
        freq: 'annual' or 'quarterly'
    Strategy (annual mode):
    1. Try Yahoo Finance first
    2. If Yahoo fails or data completeness < 50%, try alternative sources (FMP -> Macrotrends -> Alpha Vantage)
    3. If both have data, merge (fill Yahoo's N/A with alternative values)
    4. Return best result with data_source indicator
    """
    # ---- QUARTERLY MODE: simple path, no fallback/scoring ----
    if freq == 'quarterly':
        result = copy.deepcopy(scrape_financials_quarterly(ticker_symbol))
        if result.get('success'):
            result['data_source'] = 'yahoo'
            result['full_data'] = list(result.get('data', []))
        return result
    # ---- ANNUAL MODE (original logic) ----
    # Step 1: Try Yahoo Finance
    # Use cached result to prevent re-scraping and hitting rate limits
    yahoo_result = copy.deepcopy(scrape_financials(ticker_symbol))
    # Note: scrape_financials doesn't actively filter by year, it returns full history.
    # We filter for scoring later below.
    yahoo_ok = yahoo_result.get('success', False)
    yahoo_completeness = _calc_completeness(yahoo_result) if yahoo_ok else 0.0
    logger.info("Yahoo Finance: success=%s, completeness=%.1f%%", yahoo_ok, yahoo_completeness * 100)
    result = yahoo_result # Default
    # Step 2: Try alternative sources (FMP -> Macrotrends -> Alpha Vantage)
    if not (yahoo_ok and yahoo_completeness >= 0.5):
         try:
            from fallback_scraper import scrape_fallback_financials
            alt_result = scrape_fallback_financials(ticker_symbol)
            alt_ok = alt_result.get('success', False)
            alt_completeness = _calc_completeness(alt_result) if alt_ok else 0.0
            alt_source = alt_result.get('data_source', 'alternative')
            logger.info("Alternative (%s): success=%s, completeness=%.1f%%", alt_source, alt_ok, alt_completeness * 100)
            if yahoo_ok and alt_ok:
                merged = _merge_results(yahoo_result, alt_result)
                merged['data_source'] = f'yahoo+{alt_source}'
                merged['data_completeness'] = round(_calc_completeness(merged), 4)
                result = merged
            elif alt_ok:
                alt_result['data_completeness'] = round(alt_completeness, 4)
                result = alt_result
            elif yahoo_ok:
                 yahoo_result['data_source'] = 'yahoo'
                 yahoo_result['data_completeness'] = round(yahoo_completeness, 4)
                 result = yahoo_result
            else:
                 error_msg = yahoo_result.get('error', 'Yahoo Finance failed')
                 if alt_result: error_msg += f" | {alt_result.get('error', 'Alternative sources also failed')}"
                 return {'success': False, 'error': error_msg, 'data_source': 'none'}
         except Exception as e:
            logger.warning("Alternative sources failed: %s", e)
            if not yahoo_ok:
                return {'success': False, 'error': str(e), 'data_source': 'none'}
            result = yahoo_result # Fallback to Yahoo even if incomplete
    # --- RE-CALCULATE SCORING ---
    if result.get('success') and result.get('data'):
        sector = result.get('company', {}).get('sector', 'N/A')
        industry = result.get('company', {}).get('industry', 'N/A')
        # [NEW] Inject OJK Bank Data
        fin_subsector = _get_financial_subsector(sector, industry)
        if fin_subsector == 'bank' and get_bank_ratios:
            logger.info("Checking OJK data for %s", ticker_symbol)
            for year_data in result['data']:
                y_val = year_data.get('year')
                if y_val:
                    try:
                        # Convert year to int if it's a string
                        y_int = int(y_val)
                        ojk_data = get_bank_ratios(ticker_symbol, year=y_int)
                        if ojk_data:
                            # Inject OJK ratios into metrics (key-by-key, not update())
                            # Avoid polluting metrics with non-metric keys like 'source', 'year'
                            metrics = year_data['metrics']
                            for k in ['npl', 'car', 'ldr', 'casa', 'nim', 'bopo', 'coc']:
                                if k in ojk_data:
                                    metrics[k] = ojk_data[k]
                            if 'coverage' in ojk_data:
                                metrics['coverage_ratio'] = ojk_data['coverage']
                                metrics['coverage'] = ojk_data['coverage']
                            logger.info("Injected OJK data for %s FY%s", ticker_symbol, y_val)
                    except Exception as e:
                        logger.error("Error fetching/injecting OJK data: %s", e)
        # [NEW] Filter Data based on Target Year (Time Machine Mode)
        # We preserve 'all_years' for the UI dropdown to allow switching back.
        if 'years' in result:
            result['all_years'] = list(result['years']) # Backup full list
        # Always preserve full dataset for Historical Comparison
        result['full_data'] = list(result['data'])
        scoring_data = result['data']
        if target_year:
            # Find index where year matches target_year
            idx = next((i for i, d in enumerate(result['data']) if str(d.get('year')) == str(target_year)), -1)
            if idx != -1:
                # Update GLOBAL result data to start from target_year
                # This ensures renderCards and renderRawTable (default) see target_year.
                # But renderHistoryTable will be updated to use full_data.
                result['data'] = result['data'][idx:] 
                if 'years' in result:
                     result['years'] = result['years'][idx:]
                scoring_data = result['data'] # Now scoring_data IS result['data']
                logger.info("Time Machine: Analysis Year %s (Index %d)", target_year, idx)
            else:
                logger.info("Target year %s not found. Using latest available data.", target_year)
        # 1. Piotroski / Bank Score
        result['piotroski'] = _calculate_piotroski(scoring_data, sector, industry, ticker=ticker_symbol)
        # 2. Financial Valuation
        fin_subsector = _get_financial_subsector(sector, industry)
        if _is_financial_sector(sector, industry) and scoring_data:
            # ... (rest is same, scoring_data is now result['data'])
            curr_price = result.get('company', {}).get('current_price')
            # Use scoring_data[0] (target year)
            roe_curr = scoring_data[0]['metrics'].get('roe')
            roe_prev = scoring_data[1]['metrics'].get('roe') if len(scoring_data) > 1 else None
            # Let's look at `pbv` passed.
            # This `pbv` is typically the *current* PBV from company info.
            pbv = result.get('company', {}).get('pbv')
            # If target_year is specified and filtered, we should check if it matches the latest year.
            # If not the latest year, the current PBV is invalid for historical valuation.
            is_latest = (scoring_data[0]['year'] == result['data'][0]['year']) if result['data'] else True
            if not is_latest:
                # If doing historical analysis, Current PBV is invalid for that year's valuation.
                # We can't easily calculate historical PBV without historical price.
                # Pass None for PBV to disable valuation or show N/A.
                # _calculate_financial_valuation handles None PBV by returning available=False.
                pbv = None 
            result['financial_valuation'] = _calculate_financial_valuation(
                pbv=pbv, 
                roe_current=roe_curr,
                roe_prev=roe_prev,
                subsector=fin_subsector
            )
            result['bank_valuation'] = result['financial_valuation']
        else:
            result['financial_valuation'] = {'available': False, 'reason': 'Not financial sector or no data'}


    return result
