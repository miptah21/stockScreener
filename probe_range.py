import requests
import json

API_KEY = "98a39c67-695a-50a7-15a9-e0aafaea"
SYMBOL = "BBCA"
FROM_DATE = "2024-10-30"
TO_DATE = "2024-11-01"

# Potential patterns for date range
endpoints = [
    f"https://api.goapi.io/stock/idx/{SYMBOL}/broker_summary?api_key={API_KEY}&from={FROM_DATE}&to={TO_DATE}",
    f"https://api.goapi.io/stock/idx/{SYMBOL}/broker_summary?api_key={API_KEY}&start_date={FROM_DATE}&end_date={TO_DATE}",
    f"https://api.goapi.io/stock/idx/broker_summary?api_key={API_KEY}&symbol={SYMBOL}&from={FROM_DATE}&to={TO_DATE}",
    f"https://api.goapi.io/stock/idx/broker_summary?api_key={API_KEY}&symbol={SYMBOL}&date_from={FROM_DATE}&date_to={TO_DATE}",
]

for url in endpoints:
    print(f"Testing: {url}")
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            # Check if we got data for multiple dates or just one (default)
            # If it returns a list of daily summaries or aggregated?
            print("Response preview:", json.dumps(data, indent=2)[:300])
        else:
            print(f"Failed: {response.status_code}")
    except Exception as e:
        print(f"Error: {e}")
    print("-" * 20)
