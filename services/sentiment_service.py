"""
Sentiment Analysis Service — Aggregates news from 6 sources and analyzes
sentiment using LLMs (Claude → Gemini → VADER fallback).
"""

import json
import logging
import re
import hashlib
from datetime import datetime, timedelta

import requests
import yfinance as yf
from cachetools import TTLCache

from config import Config

logger = logging.getLogger(__name__)

# ─── Cache (15 min TTL) ─────────────────────────────────────────────
_sentiment_cache = TTLCache(maxsize=32, ttl=900)

# ─── VADER Setup ─────────────────────────────────────────────────────
_vader_analyzer = None


def _get_vader():
    """Lazy-load VADER analyzer."""
    global _vader_analyzer
    if _vader_analyzer is None:
        try:
            import nltk
            try:
                nltk.data.find('sentiment/vader_lexicon.zip')
            except LookupError:
                nltk.download('vader_lexicon', quiet=True)
            from nltk.sentiment.vader import SentimentIntensityAnalyzer
            _vader_analyzer = SentimentIntensityAnalyzer()
        except Exception as e:
            logger.error(f"Failed to load VADER: {e}")
    return _vader_analyzer


# ─── Text Preprocessing ─────────────────────────────────────────────

def _preprocess(text):
    """Clean and normalize text for sentiment analysis."""
    if not text:
        return ''
    # Strip HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Decode HTML entities
    text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    text = text.replace('&#39;', "'").replace('&quot;', '"')
    # Remove boilerplate patterns
    for pattern in ['Baca Juga:', 'Baca juga:', 'BACA JUGA:', 'Simak juga:',
                    'Foto:', 'ADVERTISEMENT', 'Sponsored']:
        text = text.split(pattern)[0]
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    # Truncate for LLM (max 500 chars)
    if len(text) > 500:
        text = text[:500] + '...'
    return text


def _title_hash(title):
    """Create a normalized hash for deduplication."""
    normalized = re.sub(r'[^a-z0-9\s]', '', title.lower().strip())
    normalized = re.sub(r'\s+', ' ', normalized)
    return hashlib.md5(normalized.encode()).hexdigest()


def _deduplicate(articles):
    """Remove duplicate articles based on title similarity."""
    seen = set()
    unique = []
    for art in articles:
        h = _title_hash(art.get('title', ''))
        if h not in seen:
            seen.add(h)
            unique.append(art)
    return unique


# ─── News Fetchers ───────────────────────────────────────────────────

def _fetch_yfinance_news(ticker):
    """Fetch news from yfinance ticker.news."""
    articles = []
    try:
        stock = yf.Ticker(ticker)
        news = stock.news or []
        for item in news[:10]:
            content = item.get('content', {}) if isinstance(item.get('content'), dict) else {}
            title = content.get('title', '') or item.get('title', '')
            pub_date = content.get('pubDate', '') or item.get('published', '')
            provider = content.get('provider', {})
            source_name = provider.get('displayName', 'Yahoo Finance') if isinstance(provider, dict) else 'Yahoo Finance'
            link = content.get('canonicalUrl', {}).get('url', '') or item.get('link', '')

            # Try thumbnail
            thumbnail = ''
            thumb_data = content.get('thumbnail', {})
            if isinstance(thumb_data, dict):
                resolutions = thumb_data.get('resolutions', [])
                if resolutions and isinstance(resolutions, list):
                    thumbnail = resolutions[0].get('url', '')

            if title:
                articles.append({
                    'title': _preprocess(title),
                    'snippet': _preprocess(content.get('summary', '')),
                    'source': source_name,
                    'url': link,
                    'published': str(pub_date)[:19] if pub_date else '',
                    'thumbnail': thumbnail,
                })
    except Exception as e:
        logger.warning(f"yfinance news error: {e}")
    return articles


def _fetch_gnews(query, max_results=10):
    """Fetch news from Google News via gnews package."""
    articles = []
    try:
        from gnews import GNews
        gn = GNews(language='id', country='ID', max_results=max_results)
        results = gn.get_news(query) or []
        for item in results:
            articles.append({
                'title': _preprocess(item.get('title', '')),
                'snippet': _preprocess(item.get('description', '')),
                'source': item.get('publisher', {}).get('title', 'Google News')
                    if isinstance(item.get('publisher'), dict)
                    else 'Google News',
                'url': item.get('url', ''),
                'published': str(item.get('published date', ''))[:19],
                'thumbnail': '',
            })
    except Exception as e:
        logger.warning(f"GNews error: {e}")
    return articles


def _fetch_marketaux(ticker_clean):
    """Fetch news from Marketaux API with built-in sentiment."""
    articles = []
    api_key = Config.MARKETAUX_API_KEY
    if not api_key:
        return articles
    try:
        # Marketaux supports .JK tickers for IDX
        url = 'https://api.marketaux.com/v1/news/all'
        params = {
            'symbols': ticker_clean,
            'filter_entities': 'true',
            'language': 'en,id',
            'api_token': api_key,
            'limit': 3,  # Free tier: max 3 per request
        }
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            for item in data.get('data', []):
                # Marketaux provides pre-computed sentiment
                entities = item.get('entities', [])
                mx_sentiment = None
                if entities:
                    mx_sentiment = entities[0].get('sentiment_score')

                articles.append({
                    'title': _preprocess(item.get('title', '')),
                    'snippet': _preprocess(item.get('description', '')),
                    'source': item.get('source', 'Marketaux'),
                    'url': item.get('url', ''),
                    'published': str(item.get('published_at', ''))[:19],
                    'thumbnail': item.get('image_url', ''),
                    '_mx_sentiment': mx_sentiment,  # Pre-scored
                })
        else:
            logger.warning(f"Marketaux API returned {resp.status_code}")
    except Exception as e:
        logger.warning(f"Marketaux error: {e}")
    return articles


def _fetch_finnhub(ticker_clean):
    """Fetch company news from Finnhub API."""
    articles = []
    api_key = Config.FINNHUB_API_KEY
    if not api_key:
        return articles
    try:
        today = datetime.now().strftime('%Y-%m-%d')
        from_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        url = 'https://finnhub.io/api/v1/company-news'
        params = {
            'symbol': ticker_clean,
            'from': from_date,
            'to': today,
            'token': api_key,
        }
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            for item in (data or [])[:10]:
                pub_ts = item.get('datetime')
                pub_str = datetime.fromtimestamp(pub_ts).strftime('%Y-%m-%d %H:%M') if pub_ts else ''
                articles.append({
                    'title': _preprocess(item.get('headline', '')),
                    'snippet': _preprocess(item.get('summary', '')),
                    'source': item.get('source', 'Finnhub'),
                    'url': item.get('url', ''),
                    'published': pub_str,
                    'thumbnail': item.get('image', ''),
                })
        else:
            logger.warning(f"Finnhub API returned {resp.status_code}")
    except Exception as e:
        logger.warning(f"Finnhub error: {e}")
    return articles


def _fetch_newsapi_ai(query, max_results=10):
    """Fetch news from newsapi.ai via eventregistry SDK."""
    articles = []
    api_key = Config.NEWSAPI_AI_KEY
    if not api_key:
        return articles
    try:
        from eventregistry import EventRegistry, QueryArticlesIter, QueryItems
        er = EventRegistry(apiKey=api_key)
        q = QueryArticlesIter(
            keywords=query,
            lang=['eng', 'ind'],
            dateStart=(datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'),
            dateEnd=datetime.now().strftime('%Y-%m-%d'),
        )
        for item in q.execQuery(er, sortBy='date', maxItems=max_results):
            articles.append({
                'title': _preprocess(item.get('title', '')),
                'snippet': _preprocess(item.get('body', '')[:300] if item.get('body') else ''),
                'source': item.get('source', {}).get('title', 'NewsAPI.ai')
                    if isinstance(item.get('source'), dict)
                    else 'NewsAPI.ai',
                'url': item.get('url', ''),
                'published': str(item.get('dateTime', ''))[:19],
                'thumbnail': item.get('image', ''),
            })
    except Exception as e:
        logger.warning(f"newsapi.ai error: {e}")
    return articles


def _fetch_scraped_news(query, max_per_source=5):
    """Fetch news from Indonesian financial news scrapers."""
    try:
        from scrapers.news_scraper import scrape_all_sources
        return scrape_all_sources(query, max_per_source)
    except Exception as e:
        logger.warning(f"News scraper error: {e}")
        return []


# ─── Sentiment Analyzers (Cascading Fallback) ───────────────────────

_LLM_PROMPT = """Analyze the sentiment of each news headline/snippet below for stock market context.
For each item, classify as: Bullish (positive for stock), Bearish (negative for stock), or Neutral.
Provide a score from -1.0 (most bearish) to 1.0 (most bullish), and confidence 0-100.

Headlines:
{headlines}

Respond ONLY with valid JSON array, no other text. Example format:
[{{"sentiment": "Bullish", "score": 0.7, "confidence": 85, "reasoning": "Record profit indicates growth"}}]
"""


def _analyze_claude(texts):
    """Analyze sentiment using Claude API."""
    api_key = Config.ANTHROPIC_API_KEY
    if not api_key:
        return None
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        headlines = '\n'.join(f'{i+1}. {t}' for i, t in enumerate(texts))
        prompt = _LLM_PROMPT.format(headlines=headlines)

        message = client.messages.create(
            model='claude-3-haiku-20240307',
            max_tokens=2000,
            messages=[{'role': 'user', 'content': prompt}],
        )
        content = message.content[0].text
        # Extract JSON from response
        json_match = re.search(r'\[.*\]', content, re.DOTALL)
        if json_match:
            results = json.loads(json_match.group())
            logger.info("Claude sentiment analysis successful")
            return results, 'Claude Haiku'
    except Exception as e:
        logger.warning(f"Claude analysis failed: {e}")
    return None


def _analyze_gemini(texts):
    """Analyze sentiment using Google Gemini API."""
    api_key = Config.GEMINI_API_KEY
    if not api_key:
        return None
    try:
        from google import genai

        client = genai.Client(api_key=api_key)

        headlines = '\n'.join(f'{i+1}. {t}' for i, t in enumerate(texts))
        prompt = _LLM_PROMPT.format(headlines=headlines)

        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt,
        )
        content = response.text
        # Extract JSON from response
        json_match = re.search(r'\[.*\]', content, re.DOTALL)
        if json_match:
            results = json.loads(json_match.group())
            logger.info("Gemini sentiment analysis successful")
            return results, 'Gemini Flash'
    except Exception as e:
        logger.warning(f"Gemini analysis failed: {e}")
    return None


def _analyze_groq(texts):
    """Analyze sentiment using Moonshot AI via Groq API."""
    api_key = Config.GROQ_API_KEY
    if not api_key:
        return None
    try:
        from groq import Groq
        
        client = Groq(api_key=api_key)
        
        headlines = '\n'.join(f'{i+1}. {t}' for i, t in enumerate(texts))
        prompt = _LLM_PROMPT.format(headlines=headlines)
        
        response = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model="moonshotai/kimi-k2-instruct-0905",
            temperature=0.0
        )
        content = response.choices[0].message.content
        # Extract JSON from response
        json_match = re.search(r'\[.*\]', content, re.DOTALL)
        if json_match:
            results = json.loads(json_match.group())
            logger.info("Groq (Moonshot AI) sentiment analysis successful")
            return results, 'Moonshot AI'
    except Exception as e:
        logger.warning(f"Groq analysis failed: {e}")
    return None



def _analyze_vader(texts):
    """Analyze sentiment using VADER (offline fallback)."""
    vader = _get_vader()
    if not vader:
        return None

    results = []
    for text in texts:
        scores = vader.polarity_scores(text)
        compound = scores['compound']
        if compound >= 0.15:
            label = 'Bullish'
        elif compound <= -0.15:
            label = 'Bearish'
        else:
            label = 'Neutral'

        results.append({
            'sentiment': label,
            'score': round(compound, 3),
            'confidence': min(round(abs(compound) * 100, 0), 100),
            'reasoning': f"VADER compound={compound:.3f}",
        })

    logger.info("VADER sentiment analysis successful")
    return results, 'VADER'


def _run_sentiment_analysis(texts):
    """
    Run sentiment analysis with cascading fallback:
    Claude → Gemini → VADER
    """
    # Tier 1: Claude
    result = _analyze_claude(texts)
    if result:
        return result

    # Tier 2: Gemini
    result = _analyze_gemini(texts)
    if result:
        return result

    # Tier 3: Groq (Moonshot AI)
    result = _analyze_groq(texts)
    if result:
        return result

    # Tier 4: VADER (always available)
    result = _analyze_vader(texts)
    if result:
        return result

    # Should never reach here, but fallback
    return [{'sentiment': 'Neutral', 'score': 0, 'confidence': 0,
             'reasoning': 'No analyzer available'}] * len(texts), 'None'


# ─── Main Orchestrator ──────────────────────────────────────────────

def _get_company_name(ticker):
    """Get company name from yfinance for better search queries."""
    try:
        info = yf.Ticker(ticker).info or {}
        name = info.get('shortName') or info.get('longName', '')
        # Remove common suffixes for better search
        for suffix in ['Tbk', 'PT', 'Ltd', 'Inc', 'Corp', '.', 'Tbk.']:
            name = name.replace(suffix, '')
        return name.strip()
    except Exception:
        return ticker.replace('.JK', '')


def get_sentiment_analysis(ticker):
    """
    Main entry point: aggregate news from all sources, analyze sentiment.

    Args:
        ticker: Stock ticker (e.g., 'BBCA.JK', 'AAPL')

    Returns:
        dict with success, articles, sentiment_summary, model_used
    """
    # Check cache
    cache_key = f"sentiment_{ticker}"
    if cache_key in _sentiment_cache:
        return _sentiment_cache[cache_key]

    try:
        # Get company name for search queries
        company_name = _get_company_name(ticker)
        ticker_clean = ticker.replace('.JK', '')

        logger.info(f"Fetching sentiment for {ticker} (name: {company_name})")

        # ── Fetch from all sources ──
        all_articles = []

        # 1. yfinance news
        all_articles.extend(_fetch_yfinance_news(ticker))

        # 2. GNews (Google News Indonesia)
        search_query = f"{ticker_clean} saham" if ticker.endswith('.JK') else ticker_clean
        all_articles.extend(_fetch_gnews(search_query, max_results=8))

        # 3. Marketaux
        all_articles.extend(_fetch_marketaux(ticker))

        # 4. Finnhub (works best with US tickers)
        finnhub_ticker = ticker_clean if ticker.endswith('.JK') else ticker
        all_articles.extend(_fetch_finnhub(finnhub_ticker))

        # 5. newsapi.ai
        newsapi_query = company_name if company_name else ticker_clean
        all_articles.extend(_fetch_newsapi_ai(newsapi_query, max_results=8))

        # 6. Web scrapers (only for IDX stocks)
        if ticker.endswith('.JK') or not '.' in ticker:
            scrape_query = company_name if company_name else ticker_clean
            all_articles.extend(_fetch_scraped_news(scrape_query, max_per_source=3))

        # ── Deduplicate ──
        unique_articles = _deduplicate(all_articles)

        if not unique_articles:
            result = {
                'success': True,
                'ticker': ticker,
                'company_name': company_name,
                'total_articles': 0,
                'model_used': 'N/A',
                'sentiment_summary': {
                    'overall_score': 0,
                    'overall_label': 'Neutral',
                    'bullish_count': 0,
                    'bearish_count': 0,
                    'neutral_count': 0,
                    'bullish_pct': 0,
                    'bearish_pct': 0,
                    'neutral_pct': 0,
                },
                'articles': [],
                'source_breakdown': {},
                'message': 'Tidak ada berita ditemukan untuk ticker ini.',
            }
            _sentiment_cache[cache_key] = result
            return result

        # ── Run Sentiment Analysis ──
        texts = [
            f"{a['title']}. {a.get('snippet', '')}" if a.get('snippet') else a['title']
            for a in unique_articles
        ]
        analysis_results, model_used = _run_sentiment_analysis(texts)

        # ── Merge results into articles ──
        analyzed_articles = []
        for i, article in enumerate(unique_articles):
            sentiment_data = analysis_results[i] if i < len(analysis_results) else {
                'sentiment': 'Neutral', 'score': 0, 'confidence': 0, 'reasoning': ''
            }

            # Check for pre-scored Marketaux sentiment
            mx_score = article.pop('_mx_sentiment', None)

            analyzed_articles.append({
                'title': article['title'],
                'snippet': article.get('snippet', ''),
                'source': article.get('source', 'Unknown'),
                'url': article.get('url', ''),
                'published': article.get('published', ''),
                'thumbnail': article.get('thumbnail', ''),
                'sentiment_label': sentiment_data.get('sentiment', 'Neutral'),
                'sentiment_score': round(float(sentiment_data.get('score', 0)), 3),
                'confidence': int(sentiment_data.get('confidence', 0)),
                'reasoning': sentiment_data.get('reasoning', ''),
                'mx_sentiment': round(float(mx_score), 3) if mx_score is not None else None,
            })

        # ── Compute Summary ──
        scores = [a['sentiment_score'] for a in analyzed_articles]
        overall_score = round(sum(scores) / len(scores), 3) if scores else 0

        bullish = sum(1 for a in analyzed_articles if a['sentiment_label'] == 'Bullish')
        bearish = sum(1 for a in analyzed_articles if a['sentiment_label'] == 'Bearish')
        neutral = sum(1 for a in analyzed_articles if a['sentiment_label'] == 'Neutral')
        total = len(analyzed_articles)

        if overall_score >= 0.1:
            overall_label = 'Bullish'
        elif overall_score <= -0.1:
            overall_label = 'Bearish'
        else:
            overall_label = 'Neutral'

        # Source breakdown
        source_counts = {}
        for a in analyzed_articles:
            src = a['source']
            source_counts[src] = source_counts.get(src, 0) + 1

        result = {
            'success': True,
            'ticker': ticker,
            'company_name': company_name,
            'total_articles': total,
            'model_used': model_used,
            'sentiment_summary': {
                'overall_score': overall_score,
                'overall_label': overall_label,
                'bullish_count': bullish,
                'bearish_count': bearish,
                'neutral_count': neutral,
                'bullish_pct': round(bullish / total * 100, 1) if total else 0,
                'bearish_pct': round(bearish / total * 100, 1) if total else 0,
                'neutral_pct': round(neutral / total * 100, 1) if total else 0,
            },
            'articles': analyzed_articles,
            'source_breakdown': source_counts,
        }

        _sentiment_cache[cache_key] = result
        return result

    except Exception as e:
        logger.exception(f"Sentiment analysis error for {ticker}")
        return {'success': False, 'error': str(e)}
