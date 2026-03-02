# 📊 Stock Screener & Financial Data Analyzer

A comprehensive **Flask-based financial analysis platform** for Indonesian and global stock markets. Features real-time data scraping, multi-indicator technical screening, fundamental analysis with bank quality scoring, ownership insights, and bandarmology (institutional flow) analysis.

---

## 🎬 Feature Demos

<details>
<summary><b>🔍 Financial Dashboard</b> — Fundamental analysis with Bank Quality Score</summary>

![Financial Dashboard Demo](docs/demos/demo_dashboard.webp)

</details>

<details>
<summary><b>📈 Technical Screener</b> — 7-indicator confluence scoring (0-100)</summary>

![Technical Screener Demo](docs/demos/demo_technical_screener.webp)

</details>

<details>
<summary><b>📊 Report Screener</b> — Annual report publication scanner</summary>

![Report Screener Demo](docs/demos/demo_report_screener.webp)

</details>

<details>
<summary><b>💰 Average Price Calculator</b> — 6-month FCA with premium/discount</summary>

![Average Price Demo](docs/demos/demo_avg_price.webp)

</details>

<details>
<summary><b>👥 Ownership Summary</b> — Institutional & insider holder analysis</summary>

![Ownership Summary Demo](docs/demos/demo_ownership.webp)

</details>

<details>
<summary><b>🏦 Bandarmology</b> — Broker flow & accumulation/distribution analysis</summary>

![Bandarmology Demo](docs/demos/demo_bandarmology.webp)

</details>

---

## ✨ Features

### 🔍 Financial Data Dashboard
- **Real-time fundamental data** scraped from Yahoo Finance with WSJ Markets as fallback
- **Bank Quality Score** — proprietary scoring system for Indonesian banking stocks using ROA, NIM, NPL, CAR, and LDR
- **Industry-specific metrics** for Banking, Insurance, Leasing, and Securities sectors
- **OJK (Financial Services Authority)** data integration for regulatory metrics
- **Historical comparison** tables with year-over-year financial data
- **Interactive price charts** with configurable time periods (1M, 3M, 6M, 1Y, 5Y)
- **Data completeness** indicator for transparency

### 📈 Stock Screeners

#### Report Screener
- Scans stock lists to identify which companies have published **annual financial reports**
- Cross-references Yahoo Finance data and IDX official API
- Supports predefined lists (LQ45, IDX30, etc.) and custom ticker input

#### Simple RSI-MACD Screener
- **RSI(14)** zone classification: Oversold, Emerging Bullish, Neutral, Bullish, Overbought
- **MACD(12,26,9)** crossover detection with bar-ago tracking
- **Composite scoring** system (-4 to +4) mapped to Strong Buy/Sell signals
- Market cap filtering support

#### Multi-Indicator Technical Screener
- **7 technical indicators** with confluence scoring (0–100):
  - RSI(14) — momentum oscillator
  - MACD(12,26,9) — trend momentum
  - Volume Analysis (20-day) — volume spike detection
  - EMA Trend (50/200) — trend direction and Golden/Death Cross
  - ATR(14) — volatility measurement
  - Bollinger Bands (20,2) — price channel analysis
  - ADX(14) — trend strength measurement
- **RSI Divergence** detection (bullish/bearish)
- **Risk management** integration: stop-loss levels, risk/reward ratios
- **Market cap presets**: Micro, Small, Mid, Large, Mega Cap

### 💰 Average Price Calculator (FCA)
- Calculates **Fair Current Average** over the last 6 months
- Statistics: mean, median, high, low, standard deviation
- Premium/discount percentage relative to current price
- Interactive historical price chart

### 👥 Ownership Summary
- Institutional vs insider ownership breakdown
- **Management effectiveness** metrics (ROE, ROA, Profit Margin)
- Top institutional and mutual fund holders
- Major insider transactions

### 🏦 Bandarmology Analysis
- **Broker-level transaction analysis** using GoAPI data
- Accumulation vs distribution phase detection
- Date range selection for custom analysis periods
- Net buy/sell by broker breakdown

---

## 🏗️ Project Architecture

```
finance/
├── app.py                    # Flask application factory & API routes
├── config.py                 # Centralized configuration & logging
├── wsgi.py                   # Production WSGI entry point (Waitress)
├── requirements.txt          # Python dependencies
├── .env                      # Environment variables (not in repo)
│
├── docs/                     # Project documentation
│   ├── METRICS.md            # Comprehensive metrics, ratios & strategies guide
│   └── LESSONS_LEARNED.md    # Development postmortems & prevention rules
│
├── scrapers/                 # Data acquisition layer
│   ├── yahoo.py              # Yahoo Finance scraper (primary)
│   ├── fallback.py           # Multi-source fallback scraper
│   ├── ojk.py                # OJK regulatory data scraper
│   └── bandarmology.py       # Broker flow analysis (GoAPI)
│
├── screeners/                # Stock screening engines
│   ├── report_screener.py    # Annual report publication checker
│   ├── simple_screener.py    # RSI + MACD composite screener
│   ├── technical_screener.py # 7-indicator confluence screener
│   └── stock_lists.py        # Predefined stock lists (LQ45, IDX30, etc.)
│
├── services/                 # Business logic layer
│   ├── scraping_service.py   # Scraping orchestration
│   └── screening_service.py  # Screening orchestration
│
├── utils/                    # Shared utilities
│   ├── indicators.py         # RSI, MACD calculation & classification
│   ├── helpers.py            # Data formatting & validation helpers
│   └── cache.py              # In-memory TTL cache (cachetools)
│
└── templates/                # Jinja2 HTML templates
    ├── index.html            # Main financial dashboard
    ├── screening.html        # Report screener UI
    ├── simple_screening.html # Simple RSI-MACD screener UI
    ├── technical_screening.html # Multi-indicator screener UI
    ├── avg_price.html        # Average price calculator UI
    └── ownership.html        # Ownership summary UI
```

---

## 🚀 Getting Started

### Prerequisites
- **Python 3.10+**
- **pip** (Python package manager)

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/miptah21/stockScreener.git
cd stockScreener

# 2. Create a virtual environment
python -m venv .venv

# 3. Activate the virtual environment
# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Create .env file (see Environment Variables below)
copy .env.example .env   # Windows
# cp .env.example .env   # Linux/Mac
```

### Environment Variables

Create a `.env` file in the project root:

```env
# Flask
FLASK_DEBUG=true
SECRET_KEY=your-secret-key

# API Keys (optional — enables additional features)
GOAPI_API_KEY=your-goapi-key          # Bandarmology feature
GOAPI_API_KEY_2=your-goapi-key-2      # Fallback API key
SECTORS_API_KEY=your-sectors-key      # Sector data

# Server
HOST=0.0.0.0
PORT=5000

# Cache
CACHE_TTL=300
CACHE_MAX_SIZE=64

# Rate Limiting
RATE_LIMIT=60/minute
RATE_LIMIT_SCRAPE=20/minute
```

### Running the Application

```bash
# Development mode (with auto-reload)
python app.py

# Production mode (with Waitress)
python wsgi.py

# Production with Gunicorn (Linux/Mac)
gunicorn wsgi:app -w 4 -b 0.0.0.0:5000
```

Open your browser and navigate to `http://localhost:5000`.

---

## 📡 API Reference

### Pages

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Main financial dashboard |
| GET | `/screening` | Report screener page |
| GET | `/simple-screening` | Simple RSI-MACD screener page |
| GET | `/technical-screening` | Multi-indicator screener page |
| GET | `/avg-price` | Average price calculator page |
| GET | `/ownership` | Ownership summary page |

### Data APIs

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/scrape?ticker=BBCA.JK&year=2024` | Scrape fundamental financial data |
| GET | `/api/history?ticker=BBCA.JK&period=6mo` | Get historical price data |
| GET | `/api/avg-price?ticker=BBCA.JK` | Calculate 6-month average price |
| GET | `/api/ownership?ticker=BBCA.JK` | Get ownership summary data |
| GET | `/api/stock-lists` | Get available stock lists |
| GET | `/api/market-date` | Get last trading date |
| GET | `/api/bandarmology?ticker=BBCA&start_date=2024-01-01&end_date=2024-01-31` | Broker flow analysis |

### Screening APIs

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET/POST | `/api/screen?list=idx_lq45` | Run report screener |
| POST | `/api/technical-screen` | Run multi-indicator technical screener |
| POST | `/api/simple-screen` | Run simple RSI-MACD screener |

#### POST Body Example (Screeners)

```json
{
  "list": "idx_lq45",
  "market_cap_preset": "large"
}
```

Or with custom tickers:

```json
{
  "list": "custom",
  "tickers": ["BBCA.JK", "BBRI.JK", "BMRI.JK"]
}
```

---

## 🎨 UI Design

The application features a **premium dark glassmorphism** design with:
- Dark gradient backgrounds
- Frosted glass card effects
- Smooth micro-animations and hover effects
- Responsive layout for all screen sizes
- Color-coded signal indicators (buy/sell/neutral)
- Interactive data tables with sorting

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|------------|
| **Backend** | Flask 3.1, Python 3.10+ |
| **Data Source** | Yahoo Finance (yfinance), OJK, GoAPI |
| **Fallback** | WSJ Markets (cloudscraper + BeautifulSoup4) |
| **Caching** | cachetools (in-memory TTL cache) |
| **Rate Limiting** | Flask-Limiter |
| **Production Server** | Waitress / Gunicorn |
| **Compression** | Flask-Compress |
| **Frontend** | HTML5, Vanilla CSS, JavaScript |
| **Data Processing** | Pandas, NumPy |

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [METRICS.md](docs/METRICS.md) | Comprehensive guide to all financial metrics, ratios, technical indicators, scoring systems, and integrated trading/investing strategies used across all features |
| [LESSONS_LEARNED.md](docs/LESSONS_LEARNED.md) | Development postmortems documenting bugs, root causes, fixes, and prevention rules to avoid repeating mistakes |

---

## 📄 License

This project is for educational and personal use.

---

## 👤 Author

**miptah21** — [GitHub](https://github.com/miptah21)
