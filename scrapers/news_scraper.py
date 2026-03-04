"""
News Scraper — Scrapes latest stock-related articles from Indonesian financial news sites.
Sources: CNBC Indonesia, Bisnis.com, Kontan.co.id
"""

import logging
import re
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Shared headers to mimic browser
_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7',
}

_TIMEOUT = 10


def _clean_text(text):
    """Clean scraped text: strip whitespace, remove excessive spaces."""
    if not text:
        return ''
    text = re.sub(r'\s+', ' ', text).strip()
    # Remove common boilerplate
    for pattern in ['Baca Juga:', 'Baca juga:', 'BACA JUGA:', 'Simak juga:', 'Foto:']:
        text = text.split(pattern)[0]
    return text.strip()


def scrape_cnbc_indonesia(query, max_articles=5):
    """
    Scrape news from CNBC Indonesia search.
    URL: https://www.cnbcindonesia.com/search?query=...
    """
    articles = []
    try:
        url = f'https://www.cnbcindonesia.com/search?query={query}&kanal=&tipe=artikel'
        resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        if resp.status_code != 200:
            logger.warning(f"CNBC Indonesia returned {resp.status_code}")
            return articles

        soup = BeautifulSoup(resp.text, 'html.parser')
        items = soup.select('article, .list-content article, .media_rows .media')

        if not items:
            # Fallback: try common list selectors
            items = soup.select('ul.list li, .result-list li, .latest-news li')

        for item in items[:max_articles]:
            try:
                link_el = item.find('a', href=True)
                title_el = item.find(['h2', 'h3', 'h4', 'a'])
                if not link_el or not title_el:
                    continue

                title = _clean_text(title_el.get_text())
                href = link_el['href']
                if not href.startswith('http'):
                    href = f'https://www.cnbcindonesia.com{href}'

                snippet_el = item.find(['p', '.description', '.summary'])
                snippet = _clean_text(snippet_el.get_text()) if snippet_el else ''

                date_el = item.find(['time', '.date', 'span.text-xs'])
                pub_date = date_el.get_text().strip() if date_el else ''

                if title and len(title) > 10:
                    articles.append({
                        'title': title,
                        'snippet': snippet[:300],
                        'source': 'CNBC Indonesia',
                        'url': href,
                        'published': pub_date,
                    })
            except Exception:
                continue

    except Exception as e:
        logger.warning(f"Error scraping CNBC Indonesia: {e}")

    return articles


def scrape_bisnis(query, max_articles=5):
    """
    Scrape news from Bisnis.com search.
    URL: https://www.bisnis.com/index?q=...
    """
    articles = []
    try:
        url = f'https://www.bisnis.com/index?q={query}&per_page=10'
        resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        if resp.status_code != 200:
            logger.warning(f"Bisnis.com returned {resp.status_code}")
            return articles

        soup = BeautifulSoup(resp.text, 'html.parser')
        items = soup.select('.list-news .media, .list-news li, article.media')

        if not items:
            items = soup.select('.searchResults li, .item-list article')

        for item in items[:max_articles]:
            try:
                link_el = item.find('a', href=True)
                title_el = item.find(['h2', 'h3', 'h4', 'a'])
                if not link_el or not title_el:
                    continue

                title = _clean_text(title_el.get_text())
                href = link_el['href']
                if not href.startswith('http'):
                    href = f'https://www.bisnis.com{href}'

                snippet_el = item.find(['p', '.description'])
                snippet = _clean_text(snippet_el.get_text()) if snippet_el else ''

                date_el = item.find(['time', '.date', '.waktu'])
                pub_date = date_el.get_text().strip() if date_el else ''

                if title and len(title) > 10:
                    articles.append({
                        'title': title,
                        'snippet': snippet[:300],
                        'source': 'Bisnis.com',
                        'url': href,
                        'published': pub_date,
                    })
            except Exception:
                continue

    except Exception as e:
        logger.warning(f"Error scraping Bisnis.com: {e}")

    return articles


def scrape_kontan(query, max_articles=5):
    """
    Scrape news from Kontan.co.id search.
    URL: https://www.kontan.co.id/search/?search=...
    """
    articles = []
    try:
        url = f'https://www.kontan.co.id/search/?search={query}'
        resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        if resp.status_code != 200:
            logger.warning(f"Kontan.co.id returned {resp.status_code}")
            return articles

        soup = BeautifulSoup(resp.text, 'html.parser')
        items = soup.select('.list-berita li, .list-news li, article')

        if not items:
            items = soup.select('.search-result li, .news-list li')

        for item in items[:max_articles]:
            try:
                link_el = item.find('a', href=True)
                title_el = item.find(['h2', 'h3', 'h4', 'a'])
                if not link_el or not title_el:
                    continue

                title = _clean_text(title_el.get_text())
                href = link_el['href']
                if not href.startswith('http'):
                    href = f'https://www.kontan.co.id{href}'

                snippet_el = item.find(['p', '.description'])
                snippet = _clean_text(snippet_el.get_text()) if snippet_el else ''

                date_el = item.find(['time', '.date', 'span.font-gray'])
                pub_date = date_el.get_text().strip() if date_el else ''

                if title and len(title) > 10:
                    articles.append({
                        'title': title,
                        'snippet': snippet[:300],
                        'source': 'Kontan.co.id',
                        'url': href,
                        'published': pub_date,
                    })
            except Exception:
                continue

    except Exception as e:
        logger.warning(f"Error scraping Kontan.co.id: {e}")

    return articles


def scrape_all_sources(query, max_per_source=5):
    """
    Scrape news from all Indonesian financial news sources.

    Args:
        query: Search query (e.g. company name or ticker)
        max_per_source: Max articles per source

    Returns:
        list of article dicts
    """
    all_articles = []
    all_articles.extend(scrape_cnbc_indonesia(query, max_per_source))
    all_articles.extend(scrape_bisnis(query, max_per_source))
    all_articles.extend(scrape_kontan(query, max_per_source))

    logger.info(f"Scraped {len(all_articles)} articles for query '{query}' "
                f"(CNBC: {sum(1 for a in all_articles if a['source']=='CNBC Indonesia')}, "
                f"Bisnis: {sum(1 for a in all_articles if a['source']=='Bisnis.com')}, "
                f"Kontan: {sum(1 for a in all_articles if a['source']=='Kontan.co.id')})")

    return all_articles
