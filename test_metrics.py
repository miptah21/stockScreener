from scraper import scrape_financials

for ticker, expected_type in [('ADMF.JK', 'leasing'), ('TRIM.JK', 'securities'), ('PNIN.JK', 'insurance'), ('BBCA.JK', 'bank')]:
    print(f"\n{'='*60}")
    print(f"Testing {ticker} (expected: {expected_type})")
    print('='*60)
    r = scrape_financials(ticker)
    
    sub = r.get('financial_subsector')
    print(f"Subsector: {sub}")
    
    # Metrics Info (what cards/history show)
    mi = r.get('metrics_info', {})
    print(f"\nMetrik Keuangan Utama ({len(mi)} metrics):")
    for k, v in mi.items():
        print(f"  {k}: {v['name']}")
    
    # Metric values - current year
    d = r['data'][0]['metrics']
    print(f"\nMetric Values (current year):")
    for k in mi.keys():
        val = d.get(k)
        if val is not None:
            if isinstance(val, float) and abs(val) < 10:
                print(f"  {k}: {val*100:.2f}%")
            else:
                print(f"  {k}: {val:,.0f}")
        else:
            print(f"  {k}: N/A")
    
    # Score
    p = r.get('piotroski', {})
    print(f"\nScore: {p.get('score')}/{p.get('max_score')} ({p.get('strength')})")
    
    # Historical values (all years) for 1st metric
    first_key = list(mi.keys())[0]
    print(f"\nHistorical [{mi[first_key]['name']}]:")
    for i, yd in enumerate(r['data']):
        yr = r['years'][i]
        val = yd['metrics'].get(first_key)
        if val is not None and isinstance(val, float) and abs(val) < 10:
            print(f"  {yr}: {val*100:.2f}%")
        elif val is not None:
            print(f"  {yr}: {val:,.0f}")
        else:
            print(f"  {yr}: N/A")
