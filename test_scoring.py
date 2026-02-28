"""Test financial sub-sector detection, new metrics, and SCORING."""
import sys
sys.path.insert(0, '.')
from scraper import get_financials

TICKERS = ['BBCA.JK', 'TUGU.JK', 'BSDE.JK']
lines = []

for ticker in TICKERS:
    lines.append(f"\n{'='*60}")
    lines.append(f"TESTING: {ticker}")
    lines.append(f"{'='*60}")
    
    result = get_financials(ticker)
    
    if not result.get('success'):
        lines.append(f"  ERROR: {result.get('error')}")
        continue
    
    company = result['company']
    lines.append(f"  Sector: {company['sector']}")
    lines.append(f"  Industry: {company['industry']}")
    lines.append(f"  Subsector: {result.get('financial_subsector')}")
    
    # Check Score
    piotroski = result.get('piotroski')
    if piotroski:
        score_type = piotroski.get('score_type', 'Standard Piotroski')
        score_label = piotroski.get('score_label', 'Piotroski F-Score')
        lines.append(f"  Score Type: {score_type}")
        lines.append(f"  Score Label: {score_label}")
        lines.append(f"  Total Score: {piotroski['score']} / {piotroski['max_score']}")
        
        lines.append("  Criteria:")
        for c in piotroski.get('criteria', []):
            status = "PASS" if c['passed'] else "FAIL"
            lines.append(f"    {c['id']}. {c['name']} [{status}]")
            
    else:
        lines.append("  Piotroski: Not available")

output = "\n".join(lines)
print(output)

with open("test_scoring.log", "w", encoding="utf-8") as f:
    f.write(output)
print("\nDone - see test_scoring.log")
