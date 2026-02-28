
import requests
import json
from datetime import datetime

ticker = "NIKL"
current_year = datetime.now().year
years = [current_year, current_year - 1]

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Referer': 'https://www.idx.co.id/id/perusahaan-tercatat/laporan-keuangan-dan-tahunan',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'X-Requested-With': 'XMLHttpRequest'
}

endpoints = [
    f"https://www.idx.co.id/primary/ListedCompany/GetFinancialReport?indexFrom=1&pageSize=12&year={years[0]}&reportType=rdf&kodeEmiten={ticker}", # 2026? unlikely
    f"https://www.idx.co.id/primary/ListedCompany/GetFinancialReport?indexFrom=1&pageSize=12&year={years[1]}&reportType=rdf&kodeEmiten={ticker}", # 2025
    f"https://www.idx.co.id/primary/ListedCompany/GetFinancialReport?indexFrom=1&pageSize=12&year={years[1]-1}&reportType=rdf&kodeEmiten={ticker}", # 2024
]

print("Probing IDX endpoints...")

for url in endpoints:
    print(f"\nTrying: {url}")
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            try:
                data = response.json()
                print("Response JSON keys:", data.keys())
                if 'Results' in data:
                    print(f"Found {len(data['Results'])} results")
                    for item in data['Results']:
                        print(f" - Year: {item.get('Year')}, Period: {item.get('ReportType')}, File: {item.get('File_Name')}")
                else:
                    print("No 'Results' key in JSON")
                    print(str(data)[:200])
            except json.JSONDecodeError:
                print("Response is not JSON")
                print(response.text[:200])
        else:
            print("Failed to fetch")
    except Exception as e:
        print(f"Error: {e}")
