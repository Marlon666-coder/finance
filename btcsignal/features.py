"""Membuat 'fitur' (bahan belajar AI) dari data candle BTC.

AI tidak bisa belajar langsung dari harga mentah. Kita ubah dulu jadi angka-angka
bermakna: return, posisi relatif terhadap MA, RSI, MACD, volatilitas, dll.
Semua dihitung dari indikator yang sudah ada — transparan.
"""

from __future__ import annotations

from typing import List, Tuple

from .data import Candle
from .indicators import atr, ema, macd, rsi, sma


def _safe(v, default=0.0):
    return default if v is None else v


def build_feature_matrix(
    candles: List[Candle],
    horizon: int = 1,
) -> Tuple[List[List[float]], List[int], List[str]]:
    """Ubah candle menjadi (X, y, nama_fitur).

    X        : list baris fitur (tiap baris = kondisi pasar pada satu candle)
    y        : label 1 kalau harga `horizon` candle ke depan NAIK, else 0
    nama     : nama tiap kolom fitur (untuk interpretasi)

    Baris terakhir yang belum punya "masa depan" dibuang dari data latih.
    """
    closes = [c.close for c in candles]
    highs = [c.high for c in candles]
    lows = [c.low for c in candles]
    n = len(closes)

    sma20 = sma(closes, 20)
    sma50 = sma(closes, 50)
    ema200 = ema(closes, 200) if n >= 200 else ema(closes, 100)
    rsi14 = rsi(closes, 14)
    macd_line, signal_line, hist = macd(closes)
    atr14 = atr(highs, lows, closes, 14)

    feature_names = [
        "ret_1",        # perubahan harga 1 candle terakhir (%)
        "ret_3",        # perubahan harga 3 candle (%)
        "ret_5",        # perubahan harga 5 candle (%)
        "px_vs_sma20",  # posisi harga vs SMA20 (%)
        "px_vs_sma50",  # posisi harga vs SMA50 (%)
        "sma20_vs_50",  # SMA20 vs SMA50 (%)
        "px_vs_ema_long",
        "rsi",          # RSI dinormalisasi 0..1
        "macd_hist",    # histogram MACD dinormalisasi oleh harga
        "atr_pct",      # volatilitas relatif (%)
    ]

    X: List[List[float]] = []
    y: List[int] = []

    start = 50  # mulai setelah indikator panjang valid
    for i in range(start, n - horizon):
        px = closes[i]
        if px <= 0:
            continue
        ret_1 = (closes[i] - closes[i - 1]) / closes[i - 1] * 100
        ret_3 = (closes[i] - closes[i - 3]) / closes[i - 3] * 100
        ret_5 = (closes[i] - closes[i - 5]) / closes[i - 5] * 100
        s20 = _safe(sma20[i], px)
        s50 = _safe(sma50[i], px)
        el = _safe(ema200[i], px)
        row = [
            ret_1,
            ret_3,
            ret_5,
            (px - s20) / s20 * 100,
            (px - s50) / s50 * 100,
            (s20 - s50) / s50 * 100,
            (px - el) / el * 100,
            _safe(rsi14[i], 50) / 100.0,
            _safe(hist[i], 0.0) / px * 100,
            _safe(atr14[i], px * 0.01) / px * 100,
        ]
        # Label: naik (1) kalau harga horizon candle ke depan > harga sekarang.
        future = closes[i + horizon]
        y.append(1 if future > px else 0)
        X.append(row)

    return X, y, feature_names


def latest_feature_row(candles: List[Candle]) -> List[float]:
    """Ambil 1 baris fitur untuk candle PALING BARU (untuk prediksi live)."""
    X, _, _ = build_feature_matrix(candles, horizon=1)
    # build_feature_matrix membuang `horizon` candle terakhir; untuk prediksi
    # live kita butuh baris candle terakhir, jadi hitung ulang tanpa membuang.
    closes = [c.close for c in candles]
    highs = [c.high for c in candles]
    lows = [c.low for c in candles]
    n = len(closes)
    i = n - 1
    px = closes[i]
    sma20 = sma(closes, 20)
    sma50 = sma(closes, 50)
    ema200 = ema(closes, 200) if n >= 200 else ema(closes, 100)
    rsi14 = rsi(closes, 14)
    _, _, hist = macd(closes)
    atr14 = atr(highs, lows, closes, 14)
    s20 = _safe(sma20[i], px)
    s50 = _safe(sma50[i], px)
    el = _safe(ema200[i], px)
    return [
        (closes[i] - closes[i - 1]) / closes[i - 1] * 100,
        (closes[i] - closes[i - 3]) / closes[i - 3] * 100,
        (closes[i] - closes[i - 5]) / closes[i - 5] * 100,
        (px - s20) / s20 * 100,
        (px - s50) / s50 * 100,
        (s20 - s50) / s50 * 100,
        (px - el) / el * 100,
        _safe(rsi14[i], 50) / 100.0,
        _safe(hist[i], 0.0) / px * 100,
        _safe(atr14[i], px * 0.01) / px * 100,
    ]
