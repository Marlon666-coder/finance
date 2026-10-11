# 📊 BTC Signal — Deteksi Arah Pergerakan Pasar BTC

Software sederhana untuk **mendeteksi arah pergerakan pasar Bitcoin** berbasis
indikator teknikal, lalu mengirim sinyal **BELI / JUAL / TAHAN** ke **Telegram**.
Bisa jalan **otomatis & gratis** lewat **GitHub Actions** (tanpa komputermu nyala).

> ## ⚠️ BUKAN NASIHAT FINANSIAL
> Prediksi arah harga crypto **tidak akan pernah akurat**. Software ini hanya
> menghitung indikator teknikal dan memberi sinyal **probabilistik** yang
> **sering salah**. Jangan jadikan dasar keputusan keuangan tanpa paham
> risikonya. Kamu bisa kehilangan uang. Gunakan untuk belajar/eksperimen.

---

## 🧠 Cara kerja

Software mengambil data harga BTC, lalu menghitung 4 indikator teknikal klasik
dan menggabungkannya jadi satu skor berbobot (-1 bearish … +1 bullish):

| Indikator | Bobot | Apa yang diukur |
|-----------|:-----:|-----------------|
| **MA Crossover** (SMA20 vs SMA50) | 35% | Arah tren |
| **MACD** (histogram) | 30% | Momentum |
| **RSI** (14) | 20% | Overbought / oversold |
| **Tren panjang** (harga vs EMA200) | 15% | Bias jangka menengah |

Skor dipetakan ke aksi:

- Skor **≥ +0.25** → 🟢 **BELI**
- Skor **≤ −0.25** → 🔴 **JUAL**
- Di antaranya → 🟡 **TAHAN**

Keyakinan (%) = seberapa kuat skornya. Semua indikator dihitung manual di
[`btcsignal/indicators.py`](btcsignal/indicators.py) — transparan, tanpa library black-box.

---

## 🚀 Cara pakai (lokal)

```bash
pip install -r requirements.txt

python main.py                 # timeframe 1 jam (default)
python main.py --interval 4h   # ganti ke 4 jam
python main.py --interval 1d   # harian
python main.py --no-notify     # cuma cetak di terminal, tanpa Telegram
```

Contoh output:

```
================================================
  AKSI       : BELI
  Harga      : $64,250.00
  Keyakinan  : 46%  (skor +0.46)
  Timeframe  : 1h
  Indikator  : {"sma20": 63800.0, "sma50": 62100.0, "rsi": 58.3, ...}
  Alasan     :
    - SMA20 (63.800) di atas SMA50 (62.100) → tren naik
    - MACD di atas garis sinyal → momentum bullish
    - RSI 58 → netral
    - Harga di atas EMA panjang → bias bullish jangka menengah
================================================
```

---

## 📱 Setup notifikasi Telegram

1. Buka Telegram, chat **[@BotFather](https://t.me/BotFather)** → kirim `/newbot`
   → ikuti instruksi → kamu dapat **token bot** (contoh: `123456:ABC-DEF...`).
2. Kirim satu pesan apa saja ke bot barumu (biar dia bisa membalas).
3. Dapatkan **chat ID** kamu: chat **[@userinfobot](https://t.me/userinfobot)** →
   dia akan membalas dengan ID numerikmu.
4. Set kedua nilai itu sebagai environment variable (lokal) atau GitHub Secrets
   (untuk otomatis — lihat bawah).

Coba lokal:

```bash
export TELEGRAM_BOT_TOKEN="token-dari-botfather"
export TELEGRAM_CHAT_ID="chat-id-kamu"
python main.py
```

---

## 🤖 Jalan otomatis di GitHub Actions (gratis)

Workflow [`.github/workflows/btc-signal.yml`](.github/workflows/btc-signal.yml)
sudah disiapkan untuk jalan **setiap jam** dan hanya mengirim Telegram **jika
sinyal berubah** (pakai flag `--only-on-change`, biar tidak spam).

**Langkah setup:**

1. Push repo ini ke GitHub (sudah dilakukan jika kamu membacanya di GitHub).
2. Di repo GitHub → **Settings → Secrets and variables → Actions → New repository secret**,
   tambahkan 2 secret:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
3. Buka tab **Actions** → aktifkan workflow bila diminta.
4. Selesai! Workflow jalan tiap jam. Kamu juga bisa menjalankannya manual lewat
   tombol **"Run workflow"** (workflow_dispatch) untuk tes langsung.

**Ubah jadwal:** edit baris `cron` di workflow. Contoh:

```yaml
- cron: "5 * * * *"      # tiap jam (default)
- cron: "0 */4 * * *"    # tiap 4 jam
- cron: "0 0 * * *"      # sekali sehari (00:00 UTC)
```

> Catatan: jadwal GitHub Actions pakai **waktu UTC** dan kadang terlambat
> beberapa menit saat server sibuk — itu normal.

---

## 🔁 Mode WATCH — notifikasi tiap menit (jalan di komputer sendiri)

GitHub Actions tidak bisa benar-benar tiap menit (minimal 5 menit & sering telat).
Kalau mau cek **tiap menit**, pakai **mode watch** yang jalan terus di komputermu.

### ▶️ Cara MENYALAKAN

Buka terminal di folder project ini, lalu:

```bash
# (sekali saja) set kredensial Telegram
export TELEGRAM_BOT_TOKEN="token-dari-botfather"
export TELEGRAM_CHAT_ID="6210337488"

# nyalakan — cek tiap 60 detik (tiap menit)
python main.py --watch

# atau tiap 30 detik
python main.py --watch --every 30

# atau tiap menit TAPI hanya kirim saat sinyal berubah (anti-spam)
python main.py --watch --every 60 --only-on-change
```

Program akan terus berjalan dan mencetak hasil tiap siklus. Selama terminal ini
terbuka & komputer nyala, notifikasi akan masuk sesuai jadwal.

> 💡 **Windows:** ganti `export X="..."` menjadi `set X=...` (tanpa tanda kutip),
> atau di PowerShell: `$env:X="..."`.

### ⏹️ Cara MEMATIKAN

Di terminal yang sedang menjalankannya, tekan:

```
Ctrl + C
```

Program langsung berhenti. Untuk menyalakan lagi, cukup jalankan perintah
`python main.py --watch` tadi sekali lagi.

> ⚠️ **Kelemahan mode watch:** hanya jalan selama terminal terbuka & komputer
> nyala. Kalau komputer dimatikan / terminal ditutup, ia berhenti — tinggal
> nyalakan lagi. Untuk 24 jam nonstop tanpa komputer nyala, pakai GitHub Actions
> (tiap jam) atau sewa VPS murah.

> 📌 **Catatan penting:** sinyal pakai candle 1 jam, jadi dalam 1 jam nilainya
> hampir selalu sama. Cek tiap menit **tidak** membuat sinyal berubah tiap menit.
> Kalau tidak mau pesan berulang, tambahkan `--only-on-change`.

---

## ⚡ Mode FUTURES (LONG / SHORT + Stop Loss, Take Profit, likuidasi)

> ## ☠️ PERINGATAN KERAS
> **Futures SANGAT berisiko.** Leverage memperbesar untung **dan** rugi — posisi
> bisa **dilikuidasi (modal habis total)** dalam hitungan menit. Ini **bukan
> nasihat finansial**. Kalau baru belajar: **jangan pakai uang asli dulu**,
> coba di **testnet/demo**, dan gunakan **leverage kecil**.

Mode ini mengubah sinyal arah menjadi rencana futures:
- Posisi **LONG** (saat BELI) / **SHORT** (saat JUAL) / **NO-TRADE** (saat TAHAN atau sinyal lemah)
- **Stop Loss** & **Take Profit** otomatis berbasis volatilitas (ATR), risk:reward 1:2
- **Estimasi harga likuidasi** sesuai leverage + peringatan kalau leverage terlalu tinggi
- **Saran ukuran posisi** berdasarkan modal & % risiko

### Cara pakai

```bash
# Futures saja — leverage 3x (default)
python main.py --futures

# Atur leverage
python main.py --futures --leverage 5

# Dengan saran ukuran posisi: modal $500, risiko 2% per trade
python main.py --futures --leverage 5 --capital 500 --risk 2

# Futures + watch tiap menit
python main.py --futures --leverage 3 --watch
```

### 📊 Mode SPOT + FUTURES sekaligus (`--both`)

Mau lihat **crypto biasa (spot) DAN futures bersamaan** dalam satu pesan? Pakai `--both`:

```bash
# Spot + futures sekaligus
python main.py --both --leverage 3

# Spot + futures, dengan ukuran posisi, tiap menit
python main.py --both --leverage 5 --capital 500 --risk 2 --watch
```

Satu pesan Telegram akan berisi dua bagian:
```
📊 BTC — SPOT & FUTURES
💰 Harga: $70,320   |   🕒 1h
──────────────
🏦 SPOT: 🟢📈 BELI (46%)
  • SMA20 di atas SMA50 → tren naik
  ...
──────────────
⚡ FUTURES: 🟢⬆️ LONG (46%, 5x)
  🛑 SL: $68,241   ✅ TP: $74,476 (R:R 1:2)
  💀 Likuidasi: $56,256
  📦 Posisi: $338 (0.0048 BTC)
```

> GitHub Actions (tiap 5 menit) sekarang otomatis pakai mode `--both`, jadi notif
> terjadwal sudah berisi spot + futures.

Contoh output Telegram:

```
⚡ BTC FUTURES — 🟢⬆️ LONG
💰 Entry: $70,320.00
🎯 Keyakinan: 46%
🕒 Timeframe: 1h  |  ⚖️ Leverage: 5x

🛑 Stop Loss : $68,241.60
✅ Take Profit: $74,476.81
📊 Risk:Reward: 1:2.0
💀 Est. Likuidasi: $56,256.00
📦 Ukuran posisi: $338 (0.0048 BTC)
```

**Catatan penting:**
- Harga likuidasi di atas hanya **perkiraan kasar** — exchange (mode cross/isolated,
  funding fee, dll) bisa berbeda. **Selalu cek di exchange kamu.**
- Software **tidak** mengeksekusi order di futures — kamu tetap buka posisi
  **manual** di exchange (mis. Binance Futures). Software hanya kasih rencana.
- Kalau muncul peringatan "likuidasi lebih dekat daripada Stop Loss" →
  **turunkan leverage**, itu tanda posisi terlalu berisiko.

---

## 🔁 Auto-trading (eksekusi jual-beli otomatis)?

Versi ini **sengaja TIDAK** mengeksekusi jual-beli sungguhan — ia hanya
**memberi sinyal**. Auto-trading dengan uang asli sangat berisiko: sinyal
teknikal sering salah, dan bug kecil bisa menghabiskan dana dengan cepat.
Mulailah dari notifikasi (kamu yang eksekusi manual). Kalau nanti sudah paham
dan benar-benar ingin auto-trade, lakukan dulu di **akun testnet/paper trading**.

---

## 🧪 Test

```bash
python tests/test_signal.py
```

Menguji indikator & logika sinyal secara **offline** (tanpa network).

---

## 📁 Struktur

```
finance/
├── btcsignal/
│   ├── data.py         # ambil candle BTC (Binance → fallback CoinGecko)
│   ├── indicators.py   # SMA, EMA, RSI, MACD (dihitung manual)
│   ├── engine.py       # gabungkan indikator → sinyal BELI/JUAL/TAHAN
│   └── notify.py       # kirim ke Telegram
├── tests/test_signal.py
├── .github/workflows/btc-signal.yml   # otomatisasi terjadwal
├── main.py             # entry point
└── requirements.txt
```
