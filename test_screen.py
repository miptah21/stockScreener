"""Test all sector lists are available."""
import requests

r = requests.get('http://127.0.0.1:5000/api/stock-lists')
d = r.json()

print(f"Total lists: {len(d['lists'])}\n")

idx_lists = {k: v for k, v in d['lists'].items() if v['market'] == 'IDX'}
other_lists = {k: v for k, v in d['lists'].items() if v['market'] != 'IDX'}

print(f"=== IDX Indonesia ({len(idx_lists)} sektor) ===")
for key, info in idx_lists.items():
    print(f"  {key:25} {info['name']:35} ({info['count']} saham)")

print(f"\n=== International ({len(other_lists)}) ===")
for key, info in other_lists.items():
    print(f"  {key:25} {info['name']:35} ({info['count']} saham)")
