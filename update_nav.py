import os, glob

html_files = glob.glob('templates/*.html')

new_nav = '''        <div class="nav__links">
            <a href="/" class="nav__link {% if active_page == 'dashboard' %}nav__link--active{% else %}nav__link--default{% endif %}">Dashboard</a>
            
            <!-- Screener Dropdown -->
            <div class="nav__dropdown">
                <div class="nav__link {% if active_page in ['screening', 'technical', 'simple'] %}nav__link--active{% else %}nav__link--default{% endif %} nav__dropdown-toggle">
                    🔍 Screeners <span class="nav__dropdown-arrow">▼</span>
                </div>
                <div class="nav__dropdown-menu">
                    <a href="/screening" class="nav__dropdown-item {% if active_page == 'screening' %}nav__dropdown-item--active{% endif %}">Fundamental Scrn</a>
                    <a href="/technical-screening" class="nav__dropdown-item {% if active_page == 'technical' %}nav__dropdown-item--active{% endif %}">Technical Scrn</a>
                    <a href="/simple-screening" class="nav__dropdown-item {% if active_page == 'simple' %}nav__dropdown-item--active{% endif %}">RSI & MACD</a>
                </div>
            </div>

            <!-- Data Dropdown -->
            <div class="nav__dropdown">
                <div class="nav__link {% if active_page in ['avg-price', 'ownership', 'market'] %}nav__link--active{% else %}nav__link--default{% endif %} nav__dropdown-toggle">
                    📊 Data <span class="nav__dropdown-arrow">▼</span>
                </div>
                <div class="nav__dropdown-menu">
                    <a href="/avg-price" class="nav__dropdown-item {% if active_page == 'avg-price' %}nav__dropdown-item--active{% endif %}">Rata-Rata Harga</a>
                    <a href="/ownership" class="nav__dropdown-item {% if active_page == 'ownership' %}nav__dropdown-item--active{% endif %}">Ownership</a>
                    <a href="/market-overview" class="nav__dropdown-item {% if active_page == 'market' %}nav__dropdown-item--active{% endif %}">Market Overview</a>
                </div>
            </div>

            <a href="/backtest" class="nav__link {% if active_page == 'backtest' %}nav__link--active{% else %}nav__link--default{% endif %}">🔬 Backtest</a>
            <a href="/watchlist" class="nav__link {% if active_page == 'watchlist' %}nav__link--active{% else %}nav__link--default{% endif %}">⭐ Watchlist</a>
            <a href="/sentiment" class="nav__link {% if active_page == 'sentiment' %}nav__link--active{% else %}nav__link--default{% endif %} nav__link--highlight">🧠 Sentimen</a>
        </div>'''

for f in html_files:
    if f.endswith('base.html') or f.endswith('sentiment.html') or f.endswith('market_overview.html'): 
        continue
    with open(f, 'r', encoding='utf-8') as file:
        content = file.read()
    
    start_str = '<div class="nav__links">'
    end_str = '</nav>'
    
    start_idx = content.find(start_str)
    if start_idx != -1:
        end_idx = content.find(end_str, start_idx)
        if end_idx != -1:
            new_content = content[:start_idx] + new_nav + '\n        ' + content[end_idx:]
            with open(f, 'w', encoding='utf-8') as file:
                file.write(new_content)
            print(f'Successfully updated {f}')
        else:
            print(f'No </nav> found after link div in {f}')
    else:
        print(f'No link div found in {f}')

print("DONE_PROCESSING")
