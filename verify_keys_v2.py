import requests
import os
from dotenv import load_dotenv
import time

load_dotenv(override=True)

def check_internet():
    print("Checking internet connectivity...")
    try:
        requests.get("https://www.google.com", timeout=5)
        print("Internet: OK")
        return True
    except Exception as e:
        print(f"Internet: FAILED ({e})")
        return False

def test_key(name, key_env_var):
    key = os.getenv(key_env_var)
    mask = f"{key[:4]}...{key[-4:]}" if key else "None"
    print(f"\nTesting {name} ({mask})")
    
    if not key:
        print(f"  -> No key found in environment variable {key_env_var}")
        return

    url = f"https://api.goapi.io/stock/idx/BBCA/broker_summary?api_key={key}&date=2024-10-30"
    
    try:
        print(f"  -> Requesting: {url}")
        response = requests.get(url, timeout=10)
        print(f"  -> Status Code: {response.status_code}")
        
        try:
            data = response.json()
            print(f"  -> Response JSON status: {data.get('status')}")
            if data.get('data'):
                print(f"  -> Data found: Yes")
            elif data.get('message'):
                 print(f"  -> Message: {data.get('message')}")
        except:
             print(f"  -> Response Text: {response.text[:100]}...")
             
    except Exception as e:
        print(f"  -> Error: {e}")

if check_internet():
    test_key("Primary Key", "GOAPI_API_KEY")
    test_key("Secondary Key", "GOAPI_API_KEY_2")
else:
    print("Skipping key tests due to no internet.")
