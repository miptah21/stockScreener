
import requests
import json
from datetime import datetime

# Setup session
s = requests.Session()
s.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'Accept-Language': 'en-US,en;q=0.9,id;q=0.8',
    'Referer': 'https://www.idx.co.id/id/perusahaan-tercatat/laporan-keuangan-dan-tahunan',
    'X-Requested-With': 'XMLHttpRequest',
    'Origin': 'https://www.idx.co.id',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-origin',
})

# 1. Visit main page to get cookies
print("Visiting main page...")
try:
    r = s.get("https://www.idx.co.id/id/perusahaan-tercatat/laporan-keuangan-dan-tahunan", timeout=15)
    print(f"Main page status: {r.status_code}")
except Exception as e:
    print(f"Main page error: {e}")

# 2. Query API
ticker = "NIKL"
year = datetime.now().year - 1 # 2025? (prev year)
url = f"https://www.idx.co.id/primary/ListedCompany/GetFinancialReport?indexFrom=1&pageSize=12&year={year}&reportType=rdf&kodeEmiten={ticker}"

print(f"Querying API: {url}")
try:
    r = s.get(url, timeout=15)
    print(f"API status: {r.status_code}")
    if r.status_code == 200:
        print(r.json())
    else:
        print(r.text[:500])
except Exception as e:
    print(f"API error: {e}")
