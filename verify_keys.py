import requests
import os
from dotenv import load_dotenv

# Force reload of .env
load_dotenv(override=True)

KEY1 = os.getenv("GOAPI_API_KEY")
KEY2 = os.getenv("GOAPI_API_KEY_2")

print(f"Key 1: {KEY1}")
print(f"Key 2: {KEY2}")

def test_key(name, key):
    if not key:
        print(f"[{name}] No key found.")
        return
        
    url = f"https://api.goapi.io/stock/idx/BBCA/broker_summary?api_key={key}&date=2024-10-30"
    print(f"[{name}] Testing...")
    try:
        response = requests.get(url, timeout=10)
        print(f"[{name}] Status: {response.status_code}")
        if response.status_code == 200:
            print(f"[{name}] Success!")
        elif response.status_code == 429:
            print(f"[{name}] Rate Limit Exceeded!")
        else:
            print(f"[{name}] Failed: {response.text}")
    except Exception as e:
        print(f"[{name}] Error: {e}")

test_key("KEY1", KEY1)
test_key("KEY2", KEY2)
