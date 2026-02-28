
import requests
import os
import yfinance as yf

FMP_KEY = "q42utrrWCv6W8O5Kcx4BOE24edqeyGUm" # From .env
SIMFIN_KEY = "62d39764-bde2-4c30-b504-16654393bd51" # From .env
TICKER ="NIKL"

def check_fmp():
    print(f"\nChecking FMP for {TICKER}.JK...")
    url = f"https://financialmodelingprep.com/api/v3/income-statement/{TICKER}.JK?period=annual&apikey={FMP_KEY}"
    try:
        r = requests.get(url, timeout=10)
        data = r.json()
        if isinstance(data, list) and len(data) > 0:
            print(f"Top result: Date={data[0].get('date')}, CalendarYear={data[0].get('calendarYear')}, AcceptedDate={data[0].get('acceptedDate')}")
        else:
            print("No data or empty list from FMP")
            print(str(data)[:200])
    except Exception as e:
        print(f"FMP Error: {e}")

def check_simfin():
    print(f"\nChecking SimFin for {TICKER}...")
    # SimFin usually needs ID first, but lets try ticker search
    url = f"https://simfin.com/api/v3/companies/id/{TICKER}?api-key={SIMFIN_KEY}" 
    # This might be wrong endpoint for SimFin v3, usually they use a different structure.
    # SimFin usually focuses on US/EU. Might not have IDX.
    print("SimFin coverage for IDX is often limited/paid. Skipping detailed probe for now unless FMP fails.")

if __name__ == "__main__":
    check_fmp()
    # check_simfin()
