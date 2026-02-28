import sys
import os
sys.path.append(os.getcwd())

from scraper import get_financials

def test_ticker(ticker):
    print(f"\n--- Testing {ticker} ---")
    result = get_financials(ticker)
    print(f"Success: {result.get('success')}")
    print(f"Source: {result.get('data_source')}")
    if result.get('success'):
        print(f"Completeness: {result.get('data_completeness')}")
        years = result.get('years', [])
        print(f"Years: {years[:3]}")
        if years:
            data = result.get('data', [{}])[0]
            print(f"Revenue ({years[0]}): {data.get('raw', {}).get('total_revenue')}")
    else:
        print(f"Error: {result.get('error')}")

if __name__ == "__main__":
    # Test US ticker (should use Yahoo or fallback to FMP)
    test_ticker("AAPL")
    
    # Test IDX ticker (should fail if Yahoo fails, as no fallback supports it)
    # We expect Yahoo to work for BBCA usually, but let's see.
    test_ticker("BBCA.JK")

    print("\n--- Testing Direct Fallback (FMP) for AAPL ---")
    from fallback_scraper import scrape_fallback_financials
    fmp_result = scrape_fallback_financials("AAPL")
    print(f"Success: {fmp_result.get('success')}")
    print(f"Source: {fmp_result.get('data_source')}")
    if fmp_result.get('success'):
        print(f"Revenue (first year): {fmp_result.get('data', [{}])[0].get('raw', {}).get('total_revenue')}")
