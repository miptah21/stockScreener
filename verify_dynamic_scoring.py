from scraper import get_financials

def verify_dynamic_scoring():
    ticker = 'BBCA.JK'
    
    print(f"--- Fetching default (Latest) for {ticker} ---")
    r1 = get_financials(ticker)
    p1 = r1.get('piotroski')
    print(f"Year: {p1.get('current_year')}")
    print(f"Score: {p1.get('score')}")
    print(f"Ref Year: {p1.get('previous_year')}")
    
    print(f"\n--- Fetching Target Year 2023 for {ticker} ---")
    r2 = get_financials(ticker, target_year=2023)
    p2 = r2.get('piotroski')
    print(f"Year: {p2.get('current_year')}")
    print(f"Score: {p2.get('score')}")
    print(f"Ref Year: {p2.get('previous_year')}")
    
    if p1.get('current_year') == p2.get('current_year'):
        print("\n[FAIL] Year did not change!")
    else:
        print("\n[PASS] Year changed successfully.")
        
    if str(p2.get('current_year')) == '2023':
        print("[PASS] Target Year matches requested 2023.")
    else:
        print(f"[FAIL] Target Year {p2.get('current_year')} != 2023")

    # Verify data filtering
    data_years = [str(d.get('year')) for d in r2['data']]
    print(f"Data Years: {data_years}")
    
    if data_years[0] == '2023':
        print("[PASS] Data correctly starts from 2023.")
    else:
        print(f"[FAIL] Data starts from {data_years[0]} instead of 2023.")
        
    # Verify all_years preservation
    all_years = [str(y) for y in r2.get('all_years', [])]
    print(f"All Years: {all_years}")
    
    if '2024' in all_years:
        print("[PASS] All Years still contains 2024 (preserved).")
    else:
        print("[FAIL] All Years missing 2024!")
        
    # Verify full_data preservation
    full_data_years = [str(d.get('year')) for d in r2.get('full_data', [])]
    print(f"Full Data Years: {full_data_years}")
    
    if '2024' in full_data_years:
        print("[PASS] Full Data still contains 2024 (preserved).")
    else:
        print("[FAIL] Full Data missing 2024!")

if __name__ == "__main__":
    verify_dynamic_scoring()
