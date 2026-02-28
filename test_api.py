"""Test Piotroski F-Score calculation."""
import requests

r = requests.get('http://127.0.0.1:5000/api/scrape?ticker=AAPL')
data = r.json()

print('Success:', data.get('success'))
print('Company:', data.get('company', {}).get('name'))
print()

p = data.get('piotroski', {})
if p.get('available'):
    print(f"===== PIOTROSKI F-SCORE: {p['score']}/{p['max_score']} =====")
    print(f"Strength: {p['strength']} ({p['strength_color']})")
    print(f"Comparing: {p['current_year']} vs {p['previous_year']}")
    print()
    for c in p['criteria']:
        status = 'PASS' if c['passed'] else 'FAIL'
        print(f"  [{status}] {c['id']}. {c['name']}")
        print(f"         {c['description']}")
        print()
else:
    print('Piotroski not available:', p.get('reason'))
