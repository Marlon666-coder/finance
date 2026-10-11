"""Pengambilan data harga (candlestick) BTC.

Sumber utama: Binance public API (tanpa API key).
Fallback: CoinGecko (kalau Binance diblokir di suatu region/CI).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import List

try:
    import requests
except ImportError:  # requests dibutuhkan hanya saat mengambil data online.
    requests = None  # type: ignore

BINANCE_KLINES = "https://api.binance.com/api/v3/klines"
COINGECKO_OHLC = "https://api.coingecko.com/api/v3/coins/bitcoin/ohlc"

# Pemetaan interval -> parameter CoinGecko (days) sebagai fallback kasar.
_CG_DAYS_BY_INTERVAL = {
    "1h": 7,
    "4h": 30,
    "1d": 90,
}


@dataclass
class Candle:
    """Satu lilin (candlestick)."""

    open_time: int  # epoch ms
    open: float
    high: float
    low: float
    close: float
    volume: float


class DataError(RuntimeError):
    """Gagal mengambil data harga dari semua sumber."""


def _get_json(url: str, params: dict, retries: int = 3, timeout: int = 15):
    if requests is None:
        raise DataError(
            "Library 'requests' belum terinstall. Jalankan: pip install -r requirements.txt"
        )
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:  # noqa: BLE001 - sengaja luas, lalu retry
            last_exc = exc
            time.sleep(1.5 * (attempt + 1))
    raise DataError(f"Gagal GET {url}: {last_exc}")


def _from_binance(symbol: str, interval: str, limit: int) -> List[Candle]:
    raw = _get_json(
        BINANCE_KLINES,
        {"symbol": symbol, "interval": interval, "limit": limit},
    )
    candles = []
    for k in raw:
        candles.append(
            Candle(
                open_time=int(k[0]),
                open=float(k[1]),
                high=float(k[2]),
                low=float(k[3]),
                close=float(k[4]),
                volume=float(k[5]),
            )
        )
    return candles


def _from_coingecko(interval: str, limit: int) -> List[Candle]:
    days = _CG_DAYS_BY_INTERVAL.get(interval, 30)
    raw = _get_json(
        COINGECKO_OHLC,
        {"vs_currency": "usd", "days": days},
    )
    # CoinGecko OHLC tidak menyediakan volume -> isi 0.0.
    candles = [
        Candle(
            open_time=int(row[0]),
            open=float(row[1]),
            high=float(row[2]),
            low=float(row[3]),
            close=float(row[4]),
            volume=0.0,
        )
        for row in raw
    ]
    return candles[-limit:]


def get_candles(
    symbol: str = "BTCUSDT",
    interval: str = "1h",
    limit: int = 300,
) -> List[Candle]:
    """Ambil candlestick BTC. Coba Binance dulu, lalu CoinGecko."""
    try:
        candles = _from_binance(symbol, interval, limit)
        if candles:
            return candles
    except DataError:
        pass
    # Fallback.
    return _from_coingecko(interval, limit)


def closes(candles: List[Candle]) -> List[float]:
    return [c.close for c in candles]
