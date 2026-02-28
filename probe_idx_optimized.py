
import requests
import json
import time

s = requests.Session()
s.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'Referer': 'https://www.idx.co.id/id/perusahaan-tercatat/laporan-keuangan-dan-tahunan',
    'Origin': 'https://www.idx.co.id',
    'X-Requested-With': 'XMLHttpRequest',
})

def probe(year, report_type):
    url = f"https://www.idx.co.id/primary/ListedCompany/GetFinancialReport?indexFrom=1&pageSize=12&year={year}&reportType={report_type}&kodeEmiten=NIKL"
    print(f"\nTesting Year={year} Type={report_type}")
    try:
        r = s.get(url, timeout=10)
        print(f"Status: {r.status_code}")
        if r.status_code == 200:
            try:
                data = r.json()
                count = data.get('ResultCount', 0)
                print(f"JSON Success! Count: {count}")
                if 'Results' in data:
                   for res in data['Results']:
                       print(f" - Found: {res.get('File_Name')}")
            except:
                print("Not JSON")
        else:
            print("HTTP Error")
    except Exception as e:
        print(f"Ex: {e}")

# Try 2023 (should exist) and 2024/2025
print("Visiting main page...")
try:
    s.get("https://www.idx.co.id/id/perusahaan-tercatat/laporan-keuangan-dan-tahunan")
    time.sleep(1)
except:
    pass

probe(2023, 'rdf')   # Annual Report
probe(2023, 'audit') # Financial Statement
probe(2024, 'rdf')
probe(2024, 'audit')
probe(2025, 'rdf')
