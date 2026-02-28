import time
import yfinance as yf

tickers = ['WOOD.JK', 'PBID.JK', 'MARK.JK', 'CLEO.JK', 'EKAD.JK']

def test_info():
    start = time.time()
    print("--- Testing .info (Slow) ---")
    for t in tickers:
        s = time.time()
        tick = yf.Ticker(t)
        _ = tick.info.get('marketCap')
        _ = tick.info.get('numberOfAnalystOpinions')
        print(f"{t}: {time.time() - s:.2f}s")
    print(f"Total .info: {time.time() - start:.2f}s\n")

def test_fast_info():
    start = time.time()
    print("--- Testing .fast_info (Fast) ---")
    for t in tickers:
        s = time.time()
        tick = yf.Ticker(t)
        _ = tick.fast_info.get('market_cap')
        # Analyst count is not in fast_info, so we skip it here to see the difference
        print(f"{t}: {time.time() - s:.2f}s")
    print(f"Total .fast_info: {time.time() - start:.2f}s")

if __name__ == "__main__":
    test_info()
    test_fast_info()
