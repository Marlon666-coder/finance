"""Mesin sinyal: gabungkan beberapa indikator jadi satu keputusan.

Pendekatan: scoring. Tiap indikator memberi "suara" (-1 bearish .. +1 bullish)
dengan bobot tertentu. Skor total dinormalisasi jadi keyakinan 0-100%, lalu
dipetakan ke aksi BELI / JUAL / TAHAN.

Ini sederhana & transparan — BUKAN jaminan akurasi.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from .data import Candle, closes
from .indicators import ema, macd, rsi, sma


@dataclass
class Signal:
    action: str  # "BELI" | "JUAL" | "TAHAN"
    confidence: int  # 0-100
    price: float
    score: float  # -1.0 .. +1.0
    reasons: List[str] = field(default_factory=list)
    details: Dict[str, float] = field(default_factory=dict)


# Bobot tiap indikator (jumlah = 1.0).
WEIGHTS = {
    "ma_cross": 0.35,
    "macd": 0.30,
    "rsi": 0.20,
    "trend": 0.15,
}


def _last_valid(series):
    for v in reversed(series):
        if v is not None:
            return v
    return None


def analyze(candles: List[Candle]) -> Signal:
    px = closes(candles)
    if len(px) < 60:
        raise ValueError("Data terlalu sedikit untuk analisa (butuh >= 60 candle).")

    price = px[-1]
    reasons: List[str] = []
    details: Dict[str, float] = {}
    votes: Dict[str, float] = {}

    # --- 1. MA crossover (SMA cepat vs lambat) ---
    fast = sma(px, 20)
    slow = sma(px, 50)
    f, s = _last_valid(fast), _last_valid(slow)
    if f is not None and s is not None:
        details["sma20"] = round(f, 2)
        details["sma50"] = round(s, 2)
        if f > s:
            votes["ma_cross"] = 1.0
            reasons.append(f"SMA20 ({f:,.0f}) di atas SMA50 ({s:,.0f}) → tren naik")
        else:
            votes["ma_cross"] = -1.0
            reasons.append(f"SMA20 ({f:,.0f}) di bawah SMA50 ({s:,.0f}) → tren turun")

    # --- 2. MACD (histogram = momentum) ---
    macd_line, signal_line, hist = macd(px)
    h = _last_valid(hist)
    ml, sl = _last_valid(macd_line), _last_valid(signal_line)
    if h is not None:
        details["macd_hist"] = round(h, 2)
        strength = min(1.0, 0.5 + abs(h) / (abs(ml) + 1e-9))
        if h > 1e-9:
            votes["macd"] = strength
            reasons.append("MACD di atas garis sinyal → momentum bullish")
        elif h < -1e-9:
            votes["macd"] = -strength
            reasons.append("MACD di bawah garis sinyal → momentum bearish")
        else:
            votes["macd"] = 0.0  # histogram ~0 = momentum netral
            reasons.append("MACD ~ garis sinyal → momentum netral")

    # --- 3. RSI (overbought/oversold) ---
    # Catatan: RSI ekstrem TIDAK membalik tren. Saat searah tren naik, RSI
    # tinggi itu wajar — hanya jadi peringatan ringan koreksi, bukan sinyal jual.
    trend_up = votes.get("ma_cross", 0) > 0
    r = _last_valid(rsi(px, 14))
    if r is not None:
        details["rsi"] = round(r, 1)
        if r >= 70:
            votes["rsi"] = -0.2 if trend_up else -0.8
            note = "wajar dalam tren naik" if trend_up else "rawan koreksi turun"
            reasons.append(f"RSI {r:.0f} → overbought ({note})")
        elif r <= 30:
            votes["rsi"] = 0.2 if not trend_up else 0.8
            note = "wajar dalam tren turun" if not trend_up else "rawan pantulan naik"
            reasons.append(f"RSI {r:.0f} → oversold ({note})")
        else:
            # Netral; condong searah posisi relatif ke 50.
            votes["rsi"] = (r - 50) / 50 * 0.4
            reasons.append(f"RSI {r:.0f} → netral")

    # --- 4. Tren jangka panjang (harga vs EMA200) ---
    e200 = _last_valid(ema(px, 200)) if len(px) >= 200 else _last_valid(ema(px, 100))
    if e200 is not None:
        details["ema_long"] = round(e200, 2)
        if price > e200:
            votes["trend"] = 1.0
            reasons.append("Harga di atas EMA panjang → bias bullish jangka menengah")
        else:
            votes["trend"] = -1.0
            reasons.append("Harga di bawah EMA panjang → bias bearish jangka menengah")

    # --- Gabungkan jadi skor berbobot ---
    score = 0.0
    total_w = 0.0
    for key, weight in WEIGHTS.items():
        if key in votes:
            score += votes[key] * weight
            total_w += weight
    if total_w > 0:
        score /= total_w  # normalisasi ke -1..+1

    confidence = int(round(abs(score) * 100))

    if score >= 0.25:
        action = "BELI"
    elif score <= -0.25:
        action = "JUAL"
    else:
        action = "TAHAN"

    return Signal(
        action=action,
        confidence=confidence,
        price=round(price, 2),
        score=round(score, 3),
        reasons=reasons,
        details=details,
    )
