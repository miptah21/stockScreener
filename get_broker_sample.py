import requests
import json

API_KEY = "98a39c67-695a-50a7-15a9-e0aafaea"
SYMBOL = "BBCA"
DATE = "2024-10-30" 

endpoints = [
    f"https://api.goapi.io/stock/idx/broker_summary?api_key={API_KEY}&symbol={SYMBOL}&date={DATE}",
    f"https://api.goapi.io/stock/idx/{SYMBOL}/broker_summary?api_key={API_KEY}&date={DATE}",
    f"https://api.goapi.io/stock/idx/broker?api_key={API_KEY}&symbol={SYMBOL}&date={DATE}",
    f"https://api.goapi.io/stock/idx/analysis/broker_summary?api_key={API_KEY}&symbol={SYMBOL}&date={DATE}",
    f"https://api.goapi.io/stock/idx/indicators?api_key={API_KEY}&symbol={SYMBOL}&date={DATE}",
]

for url in endpoints:
    print(f"Trying: {url}")
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success' or data.get('data'):
                print(f"Success with URL: {url}")
                with open("broker_sample.json", "w") as f:
                    json.dump(data, f, indent=2)
                print("Saved to broker_sample.json")
                break
            else:
                print(f"Status 200 but data indicates error: {data.get('message')}")
        else:
            print(f"Failed: {response.status_code}")
    except Exception as e:
        print(f"Error: {e}")
