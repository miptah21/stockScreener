from screener import screen_stocks
import sys
import time

def test_screener_small():
    print("Testing screen_stocks('custom', tickers=['BBCA.JK', 'ASII.JK', 'TLKM.JK']) ...")
    start = time.time()
    try:
        result = screen_stocks('custom', ['BBCA.JK', 'ASII.JK', 'TLKM.JK'])
        if result['success']:
            print(f"Success! Time: {time.time() - start:.2f}s")
            print(f"Results: {result['results']}")
        else:
            print(f"Failed: {result.get('error')}")
    except Exception as e:
        print(f"CRASHED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_screener_small()
