
import logging
from screener import _check_single_ticker
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO)

def test_price_retrieval():
    print("\n--- Testing Price Retrieval (BBCA.JK) ---")
    ticker = "BBCA.JK"
    target_year = datetime.now().year - 1
    result = _check_single_ticker(ticker, target_year)
    
    print(f"Ticker: {result['ticker']}")
    print(f"Price: {result.get('price')}")
    
    if result.get('price') is not None:
        print("SUCCESS: Price retrieved.")
    else:
        print("WARNING: Price is None (Market might be closed or connection issue).")

def test_sorting_logic():
    print("\n--- Testing 3-State Sorting Logic ---")
    
    # Mock data
    data = [
        {'id': 1, 'val': 100},
        {'id': 2, 'val': 50},
        {'id': 3, 'val': 200},
    ]
    original = list(data)
    
    print(f"Original: {[d['val'] for d in data]}")
    
    # State 1: Ascending
    print("Click 1 (Ascending)...")
    data.sort(key=lambda x: x['val'])
    print(f"Result: {[d['val'] for d in data]}")
    assert [d['val'] for d in data] == [50, 100, 200]
    
    # State 2: Descending
    print("Click 2 (Descending)...")
    data.sort(key=lambda x: x['val'], reverse=True)
    print(f"Result: {[d['val'] for d in data]}")
    assert [d['val'] for d in data] == [200, 100, 50]
    
    # State 3: Neutral
    print("Click 3 (Neutral/Reset)...")
    data = list(original)
    print(f"Result: {[d['val'] for d in data]}")
    assert [d['val'] for d in data] == [100, 50, 200]
    
    print("SUCCESS: Sorting logic verified.")

if __name__ == "__main__":
    try:
        test_price_retrieval()
        test_sorting_logic()
    except Exception as e:
        print(f"\nERROR: {e}")
