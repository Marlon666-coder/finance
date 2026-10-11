"""Indikator teknikal (dihitung manual, tanpa dependency berat).

Semua fungsi menerima list harga penutupan (closes) dan mengembalikan list/nilai.
Transparan supaya kamu bisa lihat persis bagaimana sinyal dihitung.
"""

from __future__ import annotations

from typing import List, Optional


def sma(values: List[float], period: int) -> List[Optional[float]]:
    """Simple Moving Average. Elemen awal (belum cukup data) = None."""
    out: List[Optional[float]] = []
    running = 0.0
    for i, v in enumerate(values):
        running += v
        if i >= period:
            running -= values[i - period]
        if i >= period - 1:
            out.append(running / period)
        else:
            out.append(None)
    return out


def ema(values: List[float], period: int) -> List[Optional[float]]:
    """Exponential Moving Average."""
    out: List[Optional[float]] = [None] * len(values)
    if len(values) < period:
        return out
    k = 2 / (period + 1)
    # Seed EMA dengan SMA periode pertama.
    seed = sum(values[:period]) / period
    out[period - 1] = seed
    prev = seed
    for i in range(period, len(values)):
        prev = values[i] * k + prev * (1 - k)
        out[i] = prev
    return out


def rsi(values: List[float], period: int = 14) -> List[Optional[float]]:
    """Relative Strength Index (metode Wilder)."""
    out: List[Optional[float]] = [None] * len(values)
    if len(values) <= period:
        return out

    gains = 0.0
    losses = 0.0
    for i in range(1, period + 1):
        delta = values[i] - values[i - 1]
        if delta >= 0:
            gains += delta
        else:
            losses -= delta
    avg_gain = gains / period
    avg_loss = losses / period
    out[period] = _rsi_from(avg_gain, avg_loss)

    for i in range(period + 1, len(values)):
        delta = values[i] - values[i - 1]
        gain = max(delta, 0.0)
        loss = max(-delta, 0.0)
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        out[i] = _rsi_from(avg_gain, avg_loss)
    return out


def _rsi_from(avg_gain: float, avg_loss: float) -> float:
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def macd(
    values: List[float],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
):
    """MACD. Mengembalikan (macd_line, signal_line, histogram)."""
    ema_fast = ema(values, fast)
    ema_slow = ema(values, slow)
    macd_line: List[Optional[float]] = []
    for f, s in zip(ema_fast, ema_slow):
        if f is None or s is None:
            macd_line.append(None)
        else:
            macd_line.append(f - s)

    # EMA dari macd_line (hanya bagian yang valid).
    valid = [m for m in macd_line if m is not None]
    sig_valid = ema(valid, signal)

    # Petakan kembali signal ke indeks aslinya.
    signal_line: List[Optional[float]] = [None] * len(values)
    histogram: List[Optional[float]] = [None] * len(values)
    offset = len(values) - len(valid)
    for idx, sv in enumerate(sig_valid):
        real_idx = offset + idx
        signal_line[real_idx] = sv
        if sv is not None and macd_line[real_idx] is not None:
            histogram[real_idx] = macd_line[real_idx] - sv
    return macd_line, signal_line, histogram
