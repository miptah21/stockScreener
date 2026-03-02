# 📝 Lessons Learned — Stock Screener Development

Dokumentasi kesalahan dan pelajaran selama proses pengembangan, agar tidak mengulangi kesalahan yang sama di proyek ini maupun proyek lain.

---

## Daftar Isi

1. [Parameter Mismatch di Service Layer](#1-parameter-mismatch-di-service-layer)
2. [Vercel Deployment Trial-and-Error](#2-vercel-deployment-trial-and-error)
3. [yfinance MultiIndex Columns Bug](#3-yfinance-multiindex-columns-bug)
4. [Styling Regression saat Konsolidasi Fitur](#4-styling-regression-saat-konsolidasi-fitur)
5. [Data Source Reliability & Fallback Design](#5-data-source-reliability--fallback-design)
6. [OJK Data: Hardcode vs API Trade-off](#6-ojk-data-hardcode-vs-api-trade-off)
7. [Batch Processing vs Per-Ticker: Performance Lesson](#7-batch-processing-vs-per-ticker-performance-lesson)
8. [Feature Consolidation Complexity](#8-feature-consolidation-complexity)
9. [Ghost Columns di Yahoo Finance](#9-ghost-columns-di-yahoo-finance)
10. [ROA Calculation Discrepancy](#10-roa-calculation-discrepancy)

---

## 1. Parameter Mismatch di Service Layer

**Commit terkait**: Conversation *"Fixing Screener Parameter Mismatch"*

### 🔴 Apa yang salah
`TypeError` pada technical dan simple screener karena `market_cap_preset` diteruskan langsung ke fungsi screener yang hanya menerima `min_market_cap` dan `max_market_cap`.

### 🟡 Root Cause
Service layer (`screening_service.py`) awalnya hanya meneruskan parameter tanpa resolusi. API layer mengirim `market_cap_preset="large"`, tapi fungsi screener mengharapkan `min_market_cap=50e12, max_market_cap=200e12`.

**Intinya**: Ada 3 layer (Frontend → API → Service → Screener) dan tiap layer punya "bahasa" parameter yang berbeda. Tidak ada satu tempat yang bertanggung jawab untuk translasi.

### 🟢 Fix
Menambahkan resolusi preset di `screening_service.py` sebelum memanggil fungsi screener. Juga ditambahkan resolusi di `app.py` sebagai safety net.

### 💡 Pelajaran
> **Rule**: Setiap abstraction layer harus memiliki **satu titik translasi parameter** yang jelas. Jangan asumsikan layer di bawah akan menerima format parameter yang sama dengan layer di atas.

**Checklist untuk fitur baru:**
- [ ] Definisikan parameter contract di setiap layer
- [ ] Service layer bertanggung jawab untuk translasi semua "high-level" parameter (preset, enum) ke "low-level" parameter (nilai numerik)
- [ ] Tulis docstring yang eksplisit tentang parameter yang diterima

---

## 2. Vercel Deployment Trial-and-Error

**Commit terkait**: 4 commit berturut-turut (6819b57 → bd801bc → d8ebd32 → 24e87a5)

### 🔴 Apa yang salah
Deployment ke Vercel gagal **4 kali berturut-turut** sebelum berhasil. Setiap kali fix satu masalah, muncul masalah baru di `vercel.json`.

### 🟡 Root Cause
Tidak membaca dokumentasi Vercel secara menyeluruh sebelum deploy. Langsung trial-and-error:
1. `builds` property konflik dengan `functions` → hapus builds
2. `excludeFiles` tidak valid → hapus
3. `runtime` property tidak dikenali → hapus, biarkan auto-detect
4. Routing masih salah → ganti `routes` dengan `rewrites`

### 🟢 Fix
Menyederhanakan `vercel.json` menjadi minimal config yang hanya berisi `rewrites`.

### 💡 Pelajaran
> **Rule**: **RTFM sebelum deploy**. Jangan trial-and-error di production/deployment config. Baca dokumentasi platform deployment **sekali dengan lengkap**, buat config yang benar dari awal.

**Checklist deployment:**
- [ ] Baca docs platform deployment end-to-end
- [ ] Cek contoh project serupa (Flask on Vercel) di GitHub
- [ ] Test config secara lokal dulu jika memungkinkan (vercel dev)
- [ ] Satu commit deployment, bukan 4 commit fix

---

## 3. yfinance MultiIndex Columns Bug

**Commit terkait**: e402958 *"fix: handle yfinance MultiIndex columns in batch download"*

### 🔴 Apa yang salah
`yf.download()` untuk batch download mengembalikan DataFrame dengan **MultiIndex columns** `(Price, Ticker)` ketika download multiple tickers, tapi **single-level columns** `(Price)` ketika download 1 ticker atau custom list.

### 🟡 Root Cause
Library `yfinance` memiliki perilaku **inkonsisten**: format output berubah tergantung jumlah ticker yang di-download. Ini tidak didokumentasikan dengan jelas. Kode awal hanya menghandle satu format.

### 🟢 Fix
Menambahkan deteksi otomatis apakah columns adalah MultiIndex atau single-level, lalu melakukan flatten yang sesuai sebelum memproses data.

### 💡 Pelajaran
> **Rule**: Jangan pernah asumsikan output format library eksternal akan konsisten. **Selalu tulis defensive code** yang menghandle variasi format, terutama untuk library yang berurusan dengan data dari API pihak ketiga.

**Checklist saat pakai library data eksternal:**
- [ ] Test dengan 1 item, dan juga dengan multiple items
- [ ] Test dengan custom input (bukan hanya predefined list)  
- [ ] Tambahkan type checking / shape checking sebelum memproses DataFrame
- [ ] Log format yang diterima untuk debugging

---

## 4. Styling Regression saat Konsolidasi Fitur

**Commit terkait**: a779c3d *"fix(UI): Restore exact historical layout for Simple RSI-MACD mode"*  
**Conversation**: *"Simple Screener Styling"* dan *"Consolidating Stock Screeners"*

### 🔴 Apa yang salah
Saat mengkonsolidasikan Simple Screener ke dalam Technical Screener (view toggle), styling RSI Zone badges dan MACD Cross badges **tidak match** dengan desain asli. Warna, class CSS, dan layout berubah.

### 🟡 Root Cause
1. Copy-paste dari template lama tapi styling context berbeda (CSS class berbeda di template baru)
2. Tidak melakukan **visual diff** antara tampilan lama dan baru
3. Asumsi bahwa "fungsi sama = tampilan sama" — padahal CSS scope berbeda

### 🟢 Fix
Membuka desain asli dari git history (commit awal), screenshot, lalu merestorasi class CSS dan badge logic satu per satu agar pixel-perfect match.

### 💡 Pelajaran
> **Rule**: Saat konsolidasi/refactor UI, **selalu screenshot tampilan sebelum dan sesudah**. Lakukan visual diff. Jangan percaya bahwa kode yang terlihat sama akan menghasilkan tampilan yang sama — CSS context matters.

**Checklist refactor UI:**
- [ ] Screenshot tampilan asli SEBELUM refactor
- [ ] Screenshot tampilan baru SETELAH refactor
- [ ] Visual diff side-by-side
- [ ] Test semua state/variant (badges warna, empty state, loading state)
- [ ] Cek CSS specificity — class yang sama bisa render beda jika parent berbeda

---

## 5. Data Source Reliability & Fallback Design

### 🔴 Apa yang salah
Yahoo Finance sering memberikan data **tidak lengkap** untuk saham Indonesia (field None, ghost columns, missing balance sheet data). Awalnya aplikasi crash atau menunjukkan N/A di mana-mana.

### 🟡 Root Cause
Terlalu bergantung pada satu data source. Yahoo Finance bukan official source untuk IDX — datanya di-scrape dari berbagai sumber dengan kualitas bervariasi.

### 🟢 Fix
1. Dibangun **fallback chain** (FMP → SimFin → Macrotrends → Alpha Vantage) untuk saham US
2. Dibangun **data merge** antara Yahoo dan WSJ untuk meningkatkan completeness
3. Ditambahkan **data_completeness score** (0.0 - 1.0) agar user tahu seberapa lengkap datanya
4. Setiap metrik dihitung dengan null-safe functions (`_safe_divide`, null checks)

### 💡 Pelajaran
> **Rule**: Untuk aplikasi yang bergantung pada data eksternal, **SELALU desain dengan asumsi data bisa incomplete**. Implementasikan:
> 1. Fallback sources
> 2. Null-safe calculations di semua tempat
> 3. Transparency indicator (data completeness)
> 4. Graceful degradation — tampilkan apa yang ada, jangan crash

**Anti-pattern yang harus dihindari:**
```python
# ❌ BAD: Langsung akses tanpa null check
roa = net_income / total_assets

# ✅ GOOD: Null-safe wrapper
roa = _safe_divide(net_income, total_assets)  # Returns None if divisor is 0 or None
```

---

## 6. OJK Data: Hardcode vs API Trade-off

### 🔴 Apa yang salah
Awalnya mencoba scraping data OJK dan sectors.app API secara real-time, tapi sering gagal karena rate limiting, API key issues, dan data format yang tidak stabil.

### 🟡 Root Cause
Data regulasi OJK (NPL, CAR, LDR, CASA) tidak tersedia secara gratis via API yang reliable. Free tier sectors.app terbatas. Data OJK berubah infrequently (quarterly/yearly).

### 🟢 Fix
Keputusan desain: **hardcode data OJK** dari laporan tahunan ke dalam `CACHED_RATIOS` dict di `ojk.py`, dengan fallback ke API jika available. Data di-update manual saat laporan tahunan baru terbit.

### 💡 Pelajaran
> **Rule**: Tidak semua data harus real-time. Untuk data yang **jarang berubah** (quarterly/yearly regulatory data), hardcoding dengan update manual bisa lebih reliable daripada API yang flaky. Trade-off ini harus **didokumentasikan** agar maintainer tahu kapan harus update.

**Kapan hardcode acceptable:**
- Data berubah ≤ 4x/tahun (quarterly)
- Tidak ada free API yang reliable
- Data digunakan sebagai fallback, bukan primary source
- Ada sumber resmi yang bisa di-cross-check manual

---

## 7. Batch Processing vs Per-Ticker: Performance Lesson

**Commit terkait**: 8555114 *"feat: batch yf.download + chunked API"*

### 🔴 Apa yang salah
Screener awalnya memanggil `yf.Ticker(symbol).history()` **per ticker** secara sequential. Untuk 45 saham LQ45, ini memakan waktu **~2-3 menit** dan selalu timeout di Vercel (30s limit).

### 🟡 Root Cause
Setiap `yf.Ticker().history()` membuat HTTP request terpisah. 45 ticker = 45 requests sequential + 45 `ticker.info` requests = ~90 HTTP calls.

### 🟢 Fix
1. Refactor ke `yf.download(tickers, period='1y')` — satu batch request untuk semua OHLCV data
2. Parallel `ticker.info` fetch menggunakan `ThreadPoolExecutor`
3. Chunked API response (offset/limit) agar frontend bisa menampilkan progress incremental
4. Frontend progress bar yang update per chunk

### 💡 Pelajaran
> **Rule**: **Selalu batch API calls jika memungkinkan**. N sequential HTTP requests adalah anti-pattern. Gunakan batch endpoints, parallel execution, atau chunking.

**Performance checklist:**
- [ ] Berapa HTTP request yang dibuat? Bisa di-batch?
- [ ] Ada timeout constraint dari platform? (Vercel: 30s, Lambda: 15min)
- [ ] Bisa parallel? Gunakan ThreadPoolExecutor / asyncio
- [ ] User experience saat loading lama? Tampilkan progress, jangan blank screen

---

## 8. Feature Consolidation Complexity

**Conversation**: *"Consolidating Stock Screeners"*

### 🔴 Apa yang salah
Mencoba menggabungkan Simple Screener (RSI+MACD) ke dalam Technical Screener (7 indicator) ternyata **lebih kompleks dari perkiraan awal**. Yang tadinya diperkirakan "simple merge" jadi melibatkan:
- Backend route aliasing
- Frontend view toggle (Full/Simple)
- Layout matching pixel-perfect
- State management di JavaScript
- URL routing (2 halaman → 1 halaman dengan toggle)

### 🟡 Root Cause
Underestimating scope. "Merge 2 fitur jadi 1" terdengar simple, tapi setiap fitur punya: UI state, CSS scope, data structure, API contract, dan user expectations yang berbeda.

### 🟢 Fix
Memilih pendekatan **backward-compatible**: Simple screener tetap ada sebagai halaman terpisah, tapi backend-nya aliased ke technical screener API. Technical screener mendapat view toggle. Jadi user lama tetap bisa mengakses Simple view langsung.

### 💡 Pelajaran
> **Rule**: **Konsolidasi fitur ≠ menghapus salah satu**. Selalu pertahankan backward compatibility. Lebih baik "kedua fitur tetap accessible, tapi share backend" daripada "hapus fitur lama, pindahkan user ke fitur baru".

**Estimasi effort consolidation:**
- Simple merge (same data structure): **1x effort**
- Different UI but same data: **2-3x effort**
- Different UI + different data + backward compat: **5x effort** ← ini yang terjadi

---

## 9. Ghost Columns di Yahoo Finance

### 🔴 Apa yang salah
Yahoo Finance kadang mengembalikan **kolom tahun placeholder** di financial statements yang berisi semua None/NaN. Ini menyebabkan Piotroski Score terhitung salah (membandingkan tahun valid dengan tahun ghost).

### 🟡 Root Cause
Yahoo Finance internal caching/preprocessing kadang membuat kolom untuk tahun fiskal yang belum ada datanya. Tidak ada dokumentasi resmi tentang perilaku ini.

### 🟢 Fix
Menambahkan filter: skip kolom jika `net_income`, `total_revenue`, DAN `total_assets` semuanya None.

```python
# Skip ghost year columns
if net_income is None and total_revenue is None and total_assets is None:
    continue
```

### 💡 Pelajaran
> **Rule**: **Selalu validasi data sebelum diproses**. Jangan asumsikan bahwa semua kolom/baris dari data source berisi data valid. Tambahkan guard clause di awal loop processing.

---

## 10. ROA Calculation Discrepancy

**Conversation**: *"Refining ROA Calculation"*

### 🔴 Apa yang salah
ROA yang ditampilkan di tabel historis **berbeda** dengan ROA yang digunakan dalam Bank Quality Score. User menemukan inkonsistensi ini saat cross-checking.

### 🟡 Root Cause
Ada **dua cara menghitung ROA**:
- ROA sederhana: `Net Income / Total Assets` (end of period)
- ROA PSAK: `Net Income / Average Total Assets` (rata-rata awal & akhir periode)

Tabel historis menggunakan ROA sederhana, tapi Bank Quality Score menggunakan Average Assets. Keduanya valid, tapi inkonsisten membingungkan user.

### 🟢 Fix
Menyeragamkan semua kalkulasi ROA untuk menggunakan **Average Total Assets** secara konsisten.

### 💡 Pelajaran
> **Rule**: **Satu metrik = satu formula di seluruh aplikasi**. Jika ada variasi (ROA simple vs ROA average), pilih satu dan gunakan konsisten. Jika harus menampilkan keduanya, beri label yang jelas (e.g., "ROA (avg assets)" vs "ROA (end period)").

---

## 📋 Summary of Prevention Rules

| # | Rule | Kategori |
|---|------|----------|
| 1 | Setiap layer harus punya satu titik translasi parameter | Architecture |
| 2 | RTFM sebelum deploy — baca docs platform secara lengkap | Deployment |
| 3 | Jangan asumsikan output library eksternal konsisten | Data Handling |
| 4 | Screenshot sebelum & sesudah refactor UI | UI/UX |
| 5 | Desain dengan asumsi data bisa incomplete | Data Handling |
| 6 | Data infrequent boleh di-hardcode, tapi dokumentasikan | Architecture |
| 7 | Selalu batch API calls jika memungkinkan | Performance |
| 8 | Konsolidasi fitur ≠ menghapus salah satu | Product |
| 9 | Validasi data sebelum diproses, filter ghost data | Data Handling |
| 10 | Satu metrik = satu formula di seluruh aplikasi | Consistency |

---

*Dokumen ini akan terus diupdate seiring berkembangnya proyek.*
