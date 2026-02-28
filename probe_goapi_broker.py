import requests
import json
from datetime import datetime, timedelta

API_KEY = "98a39c67-695a-50a7-15a9-e0aafaea"
SYMBOL = "BBCA"
# Use a recent date, likely a weekday. Today is Tue 2026-02-17. Let's try Mon 2026-02-16.
# If api data is delayed/historical, maybe 2024-10-30 as seen in search result example.
DATE = "2024-10-30" 

endpoints = [
    f"https://api.goapi.io/stock/idx/broker_summary?api_key={API_KEY}&symbol={SYMBOL}&date={DATE}",
    f"https://api.goapi.io/stock/idx/{SYMBOL}/broker_summary?api_key={API_KEY}&date={DATE}",
    f"https://api.goapi.io/stock/idx/broker?api_key={API_KEY}&symbol={SYMBOL}&date={DATE}",
    f"https://api.goapi.io/stock/idx/analysis/broker_summary?api_key={API_KEY}&symbol={SYMBOL}&date={DATE}",
    f"https://api.goapi.io/stock/idx/indicators?api_key={API_KEY}&symbol={SYMBOL}&date={DATE}",
]

print(f"Testing endpoints for {SYMBOL} on {DATE}")

for url in endpoints:
    print(f"Testing: {url}")
    try:
        response = requests.get(url)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            try:
                data = response.json()
                print("Success! Data preview:")
                print(json.dumps(data, indent=2)[:500])
                break
            except:
                print("Response is not JSON")
                print(response.text[:200])
        else:
            print("Failed.")
            # print(response.text[:200])
    except Exception as e:
        print(f"Error: {e}")
    print("-" * 20)
