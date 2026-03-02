# 📊 Stock Screener — Dokumentasi Metrik & Strategi

Dokumentasi lengkap setiap metrik, rasio, dan data yang disajikan pada tiap fitur aplikasi, beserta strategi penggunaannya.

---

## Daftar Fitur

| # | Fitur | Halaman | Fokus |
|---|-------|---------|-------|
| 1 | [Dashboard Fundamental](#1-dashboard-fundamental) | `/` | Piotroski F-Score, Rasio Keuangan |
| 2 | [Stock Report Screener](#2-stock-report-screener) | `/screening` | Deteksi Laporan Keuangan Tahunan |
| 3 | [Average Price (FCA)](#3-average-price-fca) | `/avg-price` | Harga Rata-rata 6 Bulan |
| 4 | [Ownership Summary](#4-ownership-summary) | `/ownership` | Struktur Kepemilikan Saham |
| 5 | [Technical Screener](#5-technical-screener-full) | `/technical-screening` | 7 Indikator + Confluence Score |
| 6 | [Simple Screener](#6-simple-rsi--macd-screener) | `/simple-screening` | RSI + MACD Composite Signal |

---

## 1. Dashboard Fundamental

### 1.1 Data Perusahaan

| Data | Sumber | Deskripsi |
|------|--------|-----------|
| Company Name | Yahoo Finance `info` | Nama lengkap perusahaan |
| Sector / Industry | Yahoo Finance `info` | Sektor dan industri (menentukan jenis scoring) |
| Market Cap | Yahoo Finance `info` | Kapitalisasi pasar |
| Current Price | Yahoo Finance `info` | Harga saham terkini |
| Currency | Yahoo Finance `info` | Mata uang (IDR/USD) |
| PBV | Yahoo Finance `info` | Price to Book Value (khusus sektor finansial) |

### 1.2 Rasio & Metrik Fundamental (Umum / Non-Finansial)

| Metrik | Formula | Deskripsi | Arah Baik |
|--------|---------|-----------|-----------|
| **ROA** | Net Income / Average Total Assets | Efisiensi penggunaan aset untuk menghasilkan laba | ↑ Higher |
| **Operating Cash Flow** | Langsung dari Cash Flow Statement | Arus kas dari aktivitas operasional utama | ↑ Higher |
| **Net Income** | Langsung dari Income Statement | Laba bersih setelah semua biaya | ↑ Higher |
| **Accrual Ratio** | (Net Income − Operating Cash Flow) / Total Assets | Kualitas laba — negatif = laba didukung kas riil | ↓ Lower |
| **LT Debt Ratio** | Long Term Debt / Total Assets | Proporsi aset dibiayai utang jangka panjang | ↓ Lower |
| **Current Ratio** | Current Assets / Current Liabilities | Kemampuan membayar kewajiban jangka pendek | ↑ Higher |
| **Gross Margin** | Gross Profit / Total Revenue × 100% | % pendapatan setelah HPP | ↑ Higher |
| **Asset Turnover** | Total Revenue / Total Assets | Efisiensi aset menghasilkan pendapatan | ↑ Higher |

### 1.3 Metrik Management Effectiveness

| Metrik | Formula | Deskripsi | Arah Baik |
|--------|---------|-----------|-----------|
| **ROCE** | EBIT / (Total Assets − Current Liabilities) | Efisiensi modal yang diinvestasikan (termasuk utang) | ↑ Higher |
| **ROIC** | NOPAT / Invested Capital | Pengembalian atas modal spesifik (ekuitas + utang berbunga) | ↑ Higher |
| **DSO** | (Accounts Receivable / Revenue) × 365 | Rata-rata hari menagih piutang | ↓ Lower |
| **DSI** | (Inventory / COGS) × 365 | Rata-rata hari mengubah persediaan jadi penjualan | ↓ Lower |
| **DPO** | (Accounts Payable / COGS) × 365 | Rata-rata hari membayar utang usaha | ↑ Higher |
| **CCC** | DSO + DSI − DPO | Cash Conversion Cycle — siklus kas | ↓ Lower |
| **Receivables Turnover** | Revenue / Accounts Receivable | Efisiensi penagihan piutang | ↑ Higher |
| **Inventory Turnover** | COGS / Inventory | Frekuensi persediaan terjual per periode | ↑ Higher |

> [!NOTE]
> DSO/DSI/DPO/CCC/Inventory Turnover **tidak ditampilkan** untuk sektor finansial (bank, asuransi, leasing, sekuritas) karena tidak relevan.

### 1.4 Metrik Khusus Bank

| Metrik | Formula | Deskripsi | Arah Baik | Threshold |
|--------|---------|-----------|-----------|-----------|
| **NIM** | (Interest Income − Interest Expense) / Total Assets | Selisih pendapatan & beban bunga relatif terhadap aset | ↑ Higher | — |
| **ROE** | Net Income / Total Equity | Kemampuan menghasilkan laba dari ekuitas | ↑ Higher | >10% |
| **BOPO** | Total Operating Expense / Operating Income | Efisiensi operasional (Cost-to-Income) | ↓ Lower | <85% sehat |
| **Cost of Funds** | Interest Expense / Total Liabilities | Biaya dana — rendah = CASA tinggi | ↓ Lower | <3% |
| **Cost of Credit** | \|Write Off\| / Total Assets | Proxy biaya pencadangan kredit | ↓ Lower | <1% ideal |
| **NPL** | NPL Gross (sumber OJK) | Rasio kredit bermasalah | ↓ Lower | <5% sehat |
| **CAR** | Modal / ATMR (sumber OJK) | Kecukupan modal | ↑ Higher | ≥12% kuat |
| **LDR** | Total Kredit / DPK (sumber OJK) | Likuiditas — idealnya 78-92% | ⚖ Optimal | 78-92% |
| **CASA** | (Giro + Tabungan) / Total DPK (sumber OJK) | Rasio dana murah | ↑ Higher | ≥50% |
| **Coverage** | Cadangan Kerugian / NPL (sumber OJK) | Rasio pencadangan | ↑ Higher | >100% |

### 1.5 Metrik Khusus Asuransi

| Metrik | Formula | Deskripsi | Arah Baik |
|--------|---------|-----------|-----------|
| **ROE** | Net Income / Total Equity | Kemampuan menghasilkan laba dari ekuitas | ↑ Higher |
| **Net Margin** | Net Income / Total Revenue | % laba bersih dari total pendapatan premi | ↑ Higher |
| **Expense Ratio** | Total OpEx / Total Revenue | Efisiensi beban operasional | ↓ Lower |
| **DER** | Total Liabilities / Total Equity | Stabilitas keuangan | ↓ Lower |
| **Loss Ratio** | Net Claims / Total Revenue | Proporsi klaim terhadap premi — <100% = underwriting profit | ↓ Lower |

### 1.6 Metrik Khusus Leasing

Sama seperti asuransi (ROE, Net Margin, Expense Ratio, DER), ditambah:

| Metrik | Formula | Deskripsi | Arah Baik |
|--------|---------|-----------|-----------|
| **NPF Proxy** | \|Write Off\| / Net Loans | Proxy Non Performing Financing | ↓ Lower (<5%) |
| **Cost of Credit** | \|Write Off\| / Total Assets | Proxy biaya kredit bermasalah | ↓ Lower |

### 1.7 Metrik Khusus Sekuritas

Sama seperti asuransi (ROE, Net Margin, Expense Ratio, DER), ditambah:

| Metrik | Formula | Deskripsi | Arah Baik |
|--------|---------|-----------|-----------|
| **MKBD Proxy** | Total Equity / Total Assets | Proxy Modal Kerja Bersih Disesuaikan | ↑ Higher |

---

### 1.8 Piotroski F-Score (Perusahaan Umum)

Skor 0-9 yang mengukur kekuatan fundamental. Membandingkan **tahun terakhir vs tahun sebelumnya**.

| # | Kriteria | Kategori | Lulus Jika |
|---|---------|----------|------------|
| 1 | ROA Positif | Profitabilitas | ROA > 0 |
| 2 | Cash Flow Operasi Positif | Profitabilitas | OCF > 0 |
| 3 | ROA Meningkat | Profitabilitas | ROA↑ vs tahun lalu |
| 4 | Kualitas Laba (Accrual) | Profitabilitas | Accrual < 0 (CFO > Net Income) |
| 5 | LT Debt Ratio Menurun | Leverage | LT Debt Ratio↓ vs tahun lalu |
| 6 | Current Ratio Meningkat | Leverage | Current Ratio↑ vs tahun lalu |
| 7 | Tidak Menerbitkan Saham Baru | Leverage | Shares Outstanding ≤ tahun lalu |
| 8 | Gross Margin Membaik | Efisiensi | Gross Margin↑ vs tahun lalu |
| 9 | Asset Turnover Meningkat | Efisiensi | Asset Turnover↑ vs tahun lalu |

**Interpretasi:**
- **8-9**: 🟢 Sangat Kuat — Saham value berkualitas tinggi
- **6-7**: 🔵 Kuat — Fundamental solid
- **4-5**: 🟡 Moderat — Perlu perhatian lebih
- **0-3**: 🔴 Lemah — Sinyal peringatan

> [!TIP]
> **Strategi Piotroski**: Skor ≥7 cocok untuk value investing jangka panjang. Kombinasikan dengan PBV rendah untuk menemukan saham undervalued berkualitas. Perhatikan tren: skor yang meningkat dari tahun ke tahun menunjukkan perbaikan fundamental.

### 1.9 Bank Quality Score (10 Kriteria)

| # | Kriteria | Kategori | Lulus Jika |
|---|---------|----------|------------|
| 1 | ROA Positif | Profitabilitas | ROA (avg assets) > 0 |
| 2 | CASA Ratio Meningkat | Efisiensi Pendanaan | CASA ≥50% (OJK) atau CoF menurun |
| 3 | ROA Meningkat | Profitabilitas | ROA↑ vs tahun lalu |
| 4 | NPL < 5% | Kualitas Aset | NPL Gross <5% (OJK) atau CoC proxy |
| 5 | CAR Kuat | Solvabilitas | CAR ≥12% (OJK) atau Equity/Assets proxy |
| 6 | NIM Meningkat/Stabil | Profitabilitas Bank | NIM↑ atau Δ ≤0.5pp |
| 7 | LDR Sehat | Likuiditas | LDR ≤92% (OJK) atau pseudo-LDR |
| 8 | BOPO Menurun | Efisiensi | BOPO↓ vs tahun lalu |
| 9 | Coverage > 100% | Solvabilitas | CKPN/NPL >100% (OJK) |
| 10 | CoC Baik/Stabil | Kualitas Aset | CoC ≤2% atau stabil/menurun |

> [!IMPORTANT]
> Data OJK (NPL, CAR, LDR, CASA, Coverage, CoC) memiliki prioritas tertinggi. Jika tidak tersedia, sistem menggunakan proxy dari data Yahoo Finance.

### 1.10 Insurance / Leasing / Securities Quality Score (11 Kriteria)

**9 Kriteria Dasar** (sama untuk ketiganya):
1. ROA > 0  
2. Net Income Growth YoY > 0  
3. Operating Cash Flow > 0  
4. Equity Growth > 0  
5. DER tidak naik signifikan (>10%)  
6. Asset Growth positif  
7. ROE > 10%  
8. Net Margin stabil/naik  
9. Expense Ratio membaik  

**+2 Kriteria Spesifik:**

| Sektor | #10 | #11 |
|--------|-----|-----|
| **Asuransi** | RBC Proxy (Equity/Liabilities ≥33%) | Combined Ratio Proxy (UW Margin > 0) |
| **Leasing** | NPF Proxy (WriteOff/Loans <5%) | Coverage Ratio (RE/WriteOff ≥1x) |
| **Sekuritas** | AUM Growth Proxy (Revenue YoY Growth) | MKBD Proxy (Equity/Assets ≥30%) |

### 1.11 Financial Valuation (PBV vs ROE)

Untuk semua sektor finansial, sistem menghitung valuasi berdasarkan **PBV relatif terhadap ROE** (Residual Income Model sederhana):

| Kondisi | Valuasi |
|---------|---------|
| PBV < justified PBV | **Undervalued** |
| PBV ≈ justified PBV | **Fair Value** |
| PBV > justified PBV | **Overvalued** |

---

## 2. Stock Report Screener

### Data yang Disajikan

| Data | Deskripsi |
|------|-----------|
| **Ticker** | Kode saham |
| **Status** | ✅ Sudah rilis / ❌ Belum rilis laporan tahunan FY sebelumnya |
| **Latest Report Year** | Tahun laporan terbaru yang tersedia di Yahoo Finance |
| **Market Cap** | Kapitalisasi pasar |
| **Sector** | Sektor perusahaan |

> [!TIP]
> **Strategi**: Gunakan screener ini di awal tahun (Januari-April) untuk mendeteksi saham yang sudah merilis laporan tahunan lebih awal — ini sering menandakan transparansi manajemen yang baik. Saham yang cepat rilis laporan dan memiliki Piotroski Score tinggi adalah kandidat Value Investing terbaik.

---

## 3. Average Price (FCA)

### Metrik yang Disajikan

| Metrik | Formula | Deskripsi |
|--------|---------|-----------|
| **Average Price** | Mean dari seluruh closing price 6 bulan | Harga rata-rata FCA (Full Cost Average) |
| **Median Price** | Median closing price 6 bulan | Titik tengah distribusi harga |
| **High Price** | Max closing price 6 bulan | Harga tertinggi dalam periode |
| **Low Price** | Min closing price 6 bulan | Harga terendah dalam periode |
| **Current Price** | Harga terkini dari Yahoo Finance | Harga pasar saat ini |
| **Premium/Discount %** | (Current − Average) / Average × 100% | Posisi harga saat ini vs rata-rata |
| **Price Chart** | Grafik visual harga 6 bulan | Tren pergerakan harga |

> [!TIP]
> **Strategi DCA (Dollar Cost Averaging)**: 
> - Jika **Current < Average** (discount) → harga saat ini lebih murah dari rata-rata belinya, potensial entry
> - Jika **Current > Average** (premium) → harga sudah naik, pertimbangkan dollar cost averaging untuk average down
> - **Median** lebih tahan terhadap outlier dibandingkan Average — jika Median < Average, berarti distribusi *right-skewed* (ada spike harga tinggi sesaat)

---

## 4. Ownership Summary

### Data yang Disajikan

| Data | Sumber | Deskripsi |
|------|--------|-----------|
| **Insider %** | Yahoo Finance `heldPercentInsiders` | % saham dimiliki insider (direksi, komisaris) |
| **Institution %** | Yahoo Finance `heldPercentInstitutions` | % saham dimiliki institusi |
| **Float Shares** | Yahoo Finance `floatShares` | Jumlah saham yang beredar bebas |
| **Shares Outstanding** | Yahoo Finance `sharesOutstanding` | Total saham beredar |
| **Institutional Holders** | Yahoo Finance `institutional_holders` | Daftar pemegang saham institusional + jumlah & % kepemilikan |
| **Mutual Fund Holders** | Yahoo Finance `mutualfund_holders` | Daftar reksadana yang memiliki saham + % perubahan |
| **Insider Purchases** | Yahoo Finance `insider_purchases` | Ringkasan pembelian insider (jumlah transaksi & saham) |

> [!TIP]
> **Strategi Ownership Analysis**:
> - **Insider buying yang meningkat** → Sinyal positif — manajemen percaya harga undervalued
> - **Institutional ownership tinggi (>60%)** → Saham sudah well-researched, potensi volatilitas rendah
> - **Institutional ownership meningkat** → Smart money masuk
> - **Float kecil** → Potensi volatilitas tinggi, hati-hati liquidity risk

---

## 5. Technical Screener (Full)

Screener teknikal lengkap dengan **7 indikator** dan **Confluence Score 0-100**.

### 5.1 RSI (Relative Strength Index)

| Parameter | Nilai |
|-----------|-------|
| Period | 14 hari |
| Metode | Wilder's Smoothing (EMA) |

| Zone | Rentang RSI | Label | Interpretasi |
|------|-------------|-------|-------------|
| Overbought | ≥70 | 🔴 Sell | Harga terlalu tinggi, potensi koreksi |
| Bullish | 60-69 | 🟢 Bullish | Momentum positif, uptrend |
| Neutral | 41-59 | ⚪ Neutral | Tidak ada sinyal kuat |
| Neutral Low | 31-40 | ⚪ Neutral Low | Area wash-out, bisa jadi bottoming |
| Emerging Bullish | 31-40 (sebelumnya ≤30) | 🟡 Emerging | Baru keluar dari oversold — early signal |
| Oversold | ≤30 | 🟢 Buy | Harga terlalu rendah, potensi rebound |

> [!TIP]
> **Strategi RSI**:
> - **Oversold + Emerging Bullish** = Entry terbaik (mean-reversion)
> - RSI di zona **oversold** bukan berarti langsung beli — tunggu konfirmasi dari MACD crossover atau volume spike
> - Di **uptrend kuat**, RSI sering bertahan di 40-80 tanpa menyentuh 30

### 5.2 MACD (Moving Average Convergence Divergence)

| Parameter | Nilai |
|-----------|-------|
| Fast EMA | 12 hari |
| Slow EMA | 26 hari |
| Signal | 9 hari |
| Lookback crossover | 3 hari |

| Sinyal | Kondisi | Interpretasi |
|--------|---------|-------------|
| **Bullish Cross** | MACD line cross ↑ di atas Signal line | 🟢 Momentum berubah jadi positif |
| **Bearish Cross** | MACD line cross ↓ di bawah Signal line | 🔴 Momentum berubah jadi negatif |
| **Above Signal** | MACD > Signal (tanpa crossover baru) | 🟡 Momentum positif berlanjut |
| **Below Signal** | MACD < Signal (tanpa crossover baru) | 🟡 Momentum negatif berlanjut |

| Data | Deskripsi |
|------|-----------|
| MACD Line | EMA(12) − EMA(26) — selisih trend cepat vs lambat |
| Signal Line | EMA(9) dari MACD Line — trigger crossover |
| Histogram | MACD Line − Signal Line — visualisasi jarak |

> [!TIP]
> **Strategi MACD**:
> - **Bullish Cross di bawah garis nol** = Sinyal paling kuat (reversal dari downtrend)
> - **Histogram makin membesar** = Momentum menguat
> - Kombinasikan **Bullish Cross + RSI Oversold** = High-conviction buy signal

### 5.3 EMA Trend (50 & 200)

| Kondisi | Label | Interpretasi |
|---------|-------|-------------|
| Price > EMA50 > EMA200 | **Strong Uptrend** | 🟢 Golden alignment — trend sangat bullish |
| Price > EMA50, EMA50 ≤ EMA200 | **Uptrend** | 🟢 Trend positif tapi belum golden cross |
| Price > EMA200 | **Sideways** | ⚪ Masih di atas support utama |
| Price < EMA50 < EMA200 | **Strong Downtrend** | 🔴 Death cross alignment — hindari |
| Price < EMA50 | **Downtrend** | 🔴 Di bawah resistance — bearish |

> [!TIP]
> **Strategi Trend**:
> - **Golden Cross** (EMA50 cross ↑ EMA200) = Sinyal bullish jangka menengah
> - **Hanya beli saham dalam Strong Uptrend** untuk swing trading
> - EMA200 adalah **support kunci** — jika harga break di bawah EMA200, tren bisa jadi bearish

### 5.4 Volume Analysis

| Parameter | Nilai |
|-----------|-------|
| Period | 20 hari |

| Sinyal | Kondisi | Interpretasi |
|--------|---------|-------------|
| **Spike** | Volume Ratio ≥ 1.5× | 🟢 Volume surge — konfirmasi pergerakan |
| **Above Avg** | 1.0× ≤ Ratio < 1.5× | 🟡 Volume di atas rata-rata |
| **Normal** | 0.7× ≤ Ratio < 1.0× | ⚪ Volume normal |
| **Low** | Ratio < 0.7× | 🔴 Volume kering — jangan entry |

> [!TIP]
> **Strategi Volume**:
> - **Volume Spike + Bullish MACD Cross** = Setup terkuat
> - **Breakout tanpa volume** = Likely false breakout (jebakan)
> - Volume kering (low) saat konsolidasi → bisa menandakan **akumulasi** jika harga sideways

### 5.5 ATR (Average True Range)

| Parameter | Nilai |
|-----------|-------|
| Period | 14 hari |
| Metode | Wilder's Smoothing |

| Data | Formula | Kegunaan |
|------|---------|----------|
| **ATR** | Max(H−L, \|H−Prev Close\|, \|L−Prev Close\|) smoothed | Ukuran volatilitas absolut |
| **ATR %** | (ATR / Price) × 100% | Volatilitas relatif terhadap harga |
| **Stop Loss** | Price − 2 × ATR | Level stop loss berbasis volatilitas |

| Sinyal | Kondisi ATR% | Interpretasi |
|--------|-------------|-------------|
| **Extreme** | > 5% | 🔴 Volatilitas ekstrem — risiko tinggi |
| **Healthy** | 1-5% | 🟢 Volatilitas sehat — ideal untuk trading |
| **Low** | < 1% | ⚪ Volatilitas rendah — potensi breakout/breakdown |

> [!TIP]
> **Strategi ATR & Stop Loss**:
> - **Stop Loss = Price − 2×ATR** → Memberikan ruang bernapas untuk volatilitas normal
> - **R/R Ratio**: Target profit minimal 2×ATR di atas entry (minimal 1:1 risk-reward)
> - ATR rendah + Bollinger Bands menyempit = **Squeeze** → siap breakout

### 5.6 Bollinger Bands

| Parameter | Nilai |
|-----------|-------|
| Period | 20 hari |
| Std Dev | 2.0 |

| Data | Formula | Deskripsi |
|------|---------|-----------|
| **Upper Band** | SMA(20) + 2σ | Batas atas — resistance dinamis |
| **Middle Band** | SMA(20) | Rata-rata bergerak — baseline |
| **Lower Band** | SMA(20) − 2σ | Batas bawah — support dinamis |
| **%B** | (Price − Lower) / (Upper − Lower) | Posisi harga relatif terhadap band |
| **Bandwidth** | (Upper − Lower) / Middle | Lebar band — indikator volatilitas |

| Sinyal | Kondisi %B | Interpretasi |
|--------|-----------|-------------|
| **Overbought** | > 1.0 | 🔴 Harga di atas upper band |
| **Near Upper** | > 0.8 | 🟡 Mendekati resistance |
| **Neutral** | 0.2 - 0.8 | ⚪ Dalam range normal |
| **Near Lower** | < 0.2 | 🟡 Mendekati support |
| **Oversold** | < 0.0 | 🟢 Harga di bawah lower band |

> [!TIP]
> **Strategi Bollinger Bands**:
> - **Bollinger Squeeze** (bandwidth rendah) → Siap **breakout** — perhatikan arah breakoutnya!
> - Harga menyentuh **Lower Band + RSI Oversold** = Double confirmation buy
> - Harga bertahan di **Upper Band** dalam uptrend kuat → Bukan sell signal, ini "walking the band"

### 5.7 ADX (Average Directional Index)

| Parameter | Nilai |
|-----------|-------|
| Period | 14 hari |

| Data | Formula | Deskripsi |
|------|---------|-----------|
| **ADX** | Smoothed DX | Kekuatan trend (terlepas arah) |
| **DI+** | Smoothed +DM / ATR × 100 | Kekuatan pergerakan naik |
| **DI−** | Smoothed −DM / ATR × 100 | Kekuatan pergerakan turun |

| Sinyal | Kondisi | Interpretasi |
|--------|---------|-------------|
| **Trending** | ADX ≥ 25 | 🔵 Trend kuat — gunakan trend-following strategy |
| **Weak** | 20 ≤ ADX < 25 | ⚪ Trend lemah |
| **No Trend** | ADX < 20 | 🔴 Tidak ada trend — gunakan mean-reversion strategy |

> [!TIP]
> **Strategi ADX**:
> - **ADX > 25 + DI+ > DI−** = Uptrend kuat → ikuti trend
> - **ADX > 25 + DI− > DI+** = Downtrend kuat → hindari beli
> - **ADX rising dari bawah 20** = Trend baru sedang terbentuk

### 5.8 RSI Divergence

| Tipe | Kondisi | Interpretasi |
|------|---------|-------------|
| **Bullish Divergence** | Price: lower low, RSI: higher low | 🟢 Potensi reversal ke atas |
| **Bearish Divergence** | Price: higher high, RSI: lower high | 🔴 Potensi reversal ke bawah |
| **None** | Tidak ada divergence | ⚪ Tidak ada sinyal |

> [!TIP]
> **Strategi Divergence**:
> - Divergence adalah **leading signal** — muncul sebelum harga berubah arah
> - **Bullish Divergence + RSI Oversold + Volume Spike** = Setup reversal terkuat
> - Perlu konfirmasi — divergence tanpa breakout bisa menjadi false signal

### 5.9 Confluence Score (0-100)

Skor gabungan dari semua 7 indikator, dibobot sebagai berikut:

| Komponen | Max Poin | Bobot |
|----------|----------|-------|
| RSI | 20 | 20% |
| MACD | 20 | 20% |
| Volume | 20 | 20% |
| EMA Trend | 20 | 20% |
| ATR | 10 | 10% |
| Bonus (BB/ADX/Divergence) | 10 | 10% |

| Skor | Sinyal | Aksi |
|------|--------|------|
| **80-100** | 🟢 Strong Buy | Entry agresif, multiple indicators aligned |
| **60-79** | 🟢 Buy | Entry normal, mayoritas bullish |
| **40-59** | ⚪ Neutral | Wait & see, sinyal mixed |
| **20-39** | 🔴 Sell | Hindari beli, pertimbangkan exit |
| **0-19** | 🔴 Strong Sell | Exit segera, multiple indicators bearish |

**Confidence Count**: Menunjukkan berapa dari 6 indikator utama yang bullish (format: `X/6`).

> [!IMPORTANT]
> **Strategi Confluence**:
> - **Score ≥80 + Confidence 5/6 atau 6/6** = High-conviction trade
> - **Score 60-79** = Boleh entry tapi dengan position sizing yang lebih konservatif
> - **Jangan entry pada Score < 40** — tunggu perbaikan sinyal
> - Gunakan **Stop Loss dari ATR** untuk setiap entry apapun scorenya

---

## 6. Simple RSI & MACD Screener

Versi ringkas dari Technical Screener — hanya menggunakan **RSI(14)** dan **MACD(12,26,9)**.

### Composite Signal (-4 to +4)

| Skor | Sinyal | Deskripsi |
|------|--------|-----------|
| **+3 to +4** | 🟢 Strong Buy | RSI oversold/emerging + MACD bullish cross |
| **+1 to +2** | 🟢 Buy | Sinyal bullish dari salah satu indikator |
| **−1 to 0** | ⚪ Neutral | Tidak ada sinyal kuat |
| **−2** | 🔴 Sell | Sinyal bearish dari salah satu indikator |
| **−3 to −4** | 🔴 Strong Sell | RSI overbought + MACD bearish cross |

**Scoring Detail:**

| Komponen | Kondisi | Poin |
|----------|---------|------|
| RSI Oversold | ≤30 | +2 |
| RSI Emerging Bullish | 31-40 (recovery dari oversold) | +1 |
| RSI Bullish | 60-69 | +1 |
| RSI Neutral | 41-59 | 0 |
| RSI Overbought | ≥70 | −2 |
| MACD Bullish Cross | MACD cross ↑ Signal | +2 |
| MACD Above Signal | MACD > Signal | +1 |
| MACD Below Signal | MACD < Signal | −1 |
| MACD Bearish Cross | MACD cross ↓ Signal | −2 |

> [!TIP]
> **Kapan Menggunakan Simple vs Full Screener?**
> - **Simple Screener**: Cepat, untuk screening awal saham-saham di oversold zone
> - **Full Screener**: Untuk validasi dan mendapatkan confidence lebih tinggi sebelum entry
> - Workflow ideal: Simple Screener → filter Strong Buy → validasi di Full Screener → cek Fundamental Dashboard

---

## 7. Bandarmology (Broker Flow Analysis)

Fitur analisis arus transaksi broker pada saham IDX, menggunakan data GoAPI.

### Data yang Disajikan

| Data | Deskripsi |
|------|-----------|
| **Top 5 Buyers** | 5 broker dengan net buy terbesar (kode, nama, value, lot, avg price) |
| **Top 5 Sellers** | 5 broker dengan net sell terbesar |
| **Net Buy/Sell Value** | Value (Rp) transaksi per broker |
| **Net Lot** | Jumlah lot bersih (1 lot = 100 saham) |
| **Avg Price** | Harga rata-rata akumulasi/distribusi per broker |

### Status Bandarmology

| Status | Kondisi | Interpretasi |
|--------|---------|-------------|
| **Big Accumulation** | Top 1 buyer > 1.5× Top 1 seller | 🟢 Bandar besar masuk agresif |
| **Accumulation** | Top 3 buy > Top 3 sell | 🟢 Net akumulasi oleh broker besar |
| **Big Distribution** | Top 1 seller > 1.5× Top 1 buyer | 🔴 Bandar besar keluar agresif |
| **Distribution** | Top 3 sell > Top 3 buy | 🔴 Net distribusi oleh broker besar |
| **Neutral** | Seimbang | ⚪ Tidak ada dominasi |

### Summary Metrics

| Metrik | Formula | Deskripsi |
|--------|---------|-----------|
| **Top 1 Net** | Buy₁ − Sell₁ | Net flow broker terbesar |
| **Top 3 Net** | Σ(Buy 1-3) − Σ(Sell 1-3) | Net flow 3 broker terbesar |
| **Top 5 Net** | Σ(Buy 1-5) − Σ(Sell 1-5) | Net flow 5 broker terbesar |

> [!TIP]
> **Strategi Bandarmology**:
> - **Big Accumulation + Technical Confluence ≥60** = Setup terkuat — bandar + teknikal selaras
> - Perhatikan broker tertentu (YP, MS, GI, CC, DS) yang sering menjadi proxy untuk institusi besar
> - **Multi-day analysis** (rentang tanggal) lebih reliable daripada single-day
> - **Avg Price broker** bisa jadi support/resistance psikologis

---

## 📋 Strategi Terintegrasi (Multi-Feature)

### Value Investing Workflow
```
1. Report Screener → filter saham yang sudah rilis laporan
2. Dashboard → Piotroski Score ≥7 + metrik fundamental solid
3. Avg Price → cek apakah harga saat ini < Average (discount)
4. Ownership → insider buying meningkat → konfirmasi tambahan
```

### Technical Trading Workflow
```
1. Simple Screener → filter Strong Buy / Buy
2. Technical Screener → validasi Confluence Score ≥60
3. Bandarmology → konfirmasi akumulasi oleh broker besar
4. Set Stop Loss = Price − 2×ATR
5. Target = Price + (2 × Risk) → minimum R/R ratio 1:2
```

### Screening Prioritas (Quick Filter)
```
Fundamental:  Piotroski ≥7 + ROA↑ + Cash Flow positif
Technical:    RSI <40 + MACD Bullish Cross + Volume Spike
Smart Money:  Insider Buying↑ + Big Accumulation (Bandarmology)
Fair Value:   Current Price < Average Price (6M)
```

> [!CAUTION]
> Semua metrik dan sinyal pada aplikasi ini adalah **alat bantu analisis**, bukan rekomendasi investasi. Selalu lakukan riset mandiri (DYOR) dan pertimbangkan risk management sebelum mengambil keputusan investasi.
