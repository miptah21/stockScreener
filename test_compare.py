import sys
import os
import json

# Add project root to sys path
sys.path.insert(0, os.path.abspath('.'))

from services.compare_service import compare_stocks

def test_compare():
    # Test 1: Recent stock that might have NaN in initial history (e.g. recent IPO)
    # GOTO.JK went IPO in 2022, but we'll test 1y history. Let's test standard ones first.
    # BBCA has solid history, GOTO has negative PE and negative DER
    print("Running compare_stocks for BBCA.JK and GOTO.JK...")
    result = compare_stocks(["BBCA.JK", "GOTO.JK"])
    
    if not result.get('success'):
        print(f"Error: {result.get('error')}")
        return
        
    print("\n--- Tickers Data ---")
    for td in result['tickers_data']:
        print(f"{td['ticker']}:")
        print(f"  P/E: {td['pe_ratio']}")
        print(f"  Div Yield: {td['dividend_yield']}")
        
    print("\n--- Price Performance (1y, first 5 points) ---")
    perf = result['price_performance']
    labels = perf['labels']
    for ds in perf['datasets']:
        valid_points = [p for p in ds['data'] if p is not None]
        print(f"{ds['label']}: total points={len(ds['data'])}, valid={len(valid_points)}")
        if valid_points:
            print(f"  First valid: {valid_points[0]} at index {ds['data'].index(valid_points[0])}")
            
    print("\n--- Comparison Table (Best/Worst Check) ---")
    table = result['comparison_table']
    for row in table:
        if row['key'] in ['pe_ratio', 'dividend_yield', 'der']:
            print(f"{row['label']} ({row['key']}) [Format: {row['format']}, Higher is better: {row['higher_is_better']}]:")
            for t, v in row['values'].items():
                print(f"  {t}: {v}")
            print(f"  ** Best: {row['best']} | Worst: {row['worst']} **\n")

if __name__ == "__main__":
    test_compare()
