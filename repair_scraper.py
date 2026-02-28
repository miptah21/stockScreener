
import os

# The correct code to append
append_code = """
def _calculate_bank_valuation(pbv: float, roe_current: float, roe_prev: float, cost_of_equity: float = 0.10) -> dict:
    \"\"\"
    Calculate Bank Valuation based on Residual Income Model (PBV vs ROE).
    
    Logic:
    - Fair PBV ≈ ROE / Cost of Equity.
    - If PBV < Fair PBV and ROE > Cost of Equity: Undervalued (Good).
    - If PBV > Fair PBV and ROE < Cost of Equity: Overvalued (Bad).
    
    Args:
        pbv: Price to Book Value ratio.
        roe_current: Return on Equity (current year).
        roe_prev: Return on Equity (previous year).
        cost_of_equity: Assumed Cost of Equity (default 10%).
        
    Returns:
        dict with valuation analysis.
    \"\"\"
    if pbv is None or roe_current is None:
        return {
            'available': False,
            'reason': 'Data PBV atau ROE tidak tersedia.'
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
            
    # Verdict logic
    # "Layak Beli" jika Undervalued DAN ROE > COE (Profitable)
    verdict = "Hold / Neutral"
    verdict_desc = "Valuasi wajar sesuai dengan profitabilitas saat ini."
    
    if status == "Undervalued" and roe_current > cost_of_equity:
        verdict = "BUY / Accumulate"
        verdict_desc = f"Saham ini dihargai MURAH (PBV {pbv:.2f}x) padahal profitabilitas TINGGI (ROE {roe_current:.1%}). Potensi upside ke Fair PBV {fair_pbv:.2f}x."
    elif status == "Overvalued" and roe_current < cost_of_equity:
        verdict = "SELL / Avoid"
        verdict_desc = f"Saham ini dihargai MAHAL (PBV {pbv:.2f}x) padahal profitabilitas RENDAH (ROE {roe_current:.1%}). Risiko downside tinggi."
    elif status == "Undervalued" and roe_current < cost_of_equity:
        verdict = "Value Tramp Risk"
        verdict_desc = "PBV rendah, tapi ROE juga rendah. Hati-hati jebakan valuasi (profitabilitas buruk)."
    elif status == "Overvalued" and roe_current > cost_of_equity:
        verdict = "Premium Quality"
        verdict_desc = "Harga premium wajar untuk bank dengan profitabilitas superior."
        
    return {
        'available': True,
        'pbv': pbv,
        'fair_pbv': fair_pbv,
        'roe_current': roe_current,
        'roe_prev': roe_prev,
        'roe_trend': roe_trend,
        'cost_of_equity': cost_of_equity,
        'status': status,
        'status_color': color,
        'verdict': verdict,
        'description': verdict_desc
    }
"""

try:
    with open('scraper.py', 'rb') as f:
        content_bytes = f.read()

    # Try to decode as utf-8, ignoring errors to salvage valid parts
    content_str = content_bytes.decode('utf-8', errors='ignore')
    
    # Find the end of the valid file (before my append attempt)
    # The last valid function was _format_ratio
    marker = "def _format_ratio(value):"
    idx = content_str.rfind(marker)
    
    if idx == -1:
        print("Could not find marker function!")
        exit(1)
        
    # Find the end of that function (it's short)
    # It ends with "return round(float(value), 6)"
    end_marker = "return round(float(value), 6)"
    end_idx = content_str.find(end_marker, idx)
    
    if end_idx == -1:
        print("Could not find end of marker function!")
        exit(1)
        
    # Cut off after the end marker (plus newline)
    clean_content = content_str[:end_idx + len(end_marker)] + "\n\n"
    
    # Append the correct code
    final_content = clean_content + append_code
    
    # Write back as valid UTF-8
    with open('scraper.py', 'w', encoding='utf-8') as f:
        f.write(final_content)
        
    print("Successfully repaired scraper.py")

except Exception as e:
    print(f"Error repairing file: {e}")
