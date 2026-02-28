
import requests
import json
from datetime import datetime

# Setup session
s = requests.Session()
s.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'Referer': 'https://www.idx.co.id/id/berita/pengumuman', # Different referer
    'X-Requested-With': 'XMLHttpRequest',
})

# Search for announcements
# Endpoint: https://www.idx.co.id/primary/NewsAnnouncement/GetNewsAnnouncement?indexFrom=1&pageSize=12&year=2025&keyword=NIKL
ticker = "NIKL"
year = 2025
url = f"https://www.idx.co.id/primary/NewsAnnouncement/GetNewsAnnouncement?indexFrom=1&pageSize=100&year={year}&keyword={ticker}"

print(f"Querying Announcements: {url}")
try:
    r = s.get(url, timeout=15)
    print(f"Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        if 'Results' in data:
            print(f"Found {len(data['Results'])} announcements")
            for item in data['Results']:
                title = item.get('Title', '')
                date = item.get('PublishedDate', '')
                print(f" - {date}: {title}")
                if "Laporan Keuangan" in title or "Financial Statement" in title:
                    print("   ^^ POSSIBLE MATCH!")
        else:
            print("No 'Results' key")
    else:
        print(r.text[:500])
except Exception as e:
    print(f"Error: {e}")
