"""Pengambilan data harga (candlestick) BTC.

Sumber data (dicoba berurutan sampai salah satu berhasil):
  1. Binance market-data host `data-api.binance.vision` (TIDAK diblokir geo,
     cocok untuk server cloud seperti GitHub Actions).
  2. Binance host alternatif (api-gcp / api1..3) sebagai cadangan.
  3. CoinGecko `market_chart` -> diagregasi jadi candle (fallback terakhir).

Semuanya tanpa API key.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import List

try:
    import requests
except ImportError:  # requests dibutuhkan hanya saat mengambil data online.
    requests = None  # type: ignore

# Host Binance (urutan prioritas). data-api.binance.vision adalah host khusus
# data pasar publik yang umumnya tidak kena geo-block di IP datacenter.
_BINANCE_HOSTS = [
    "https://data-api.binance.vision",
    "https://api-gcp.binance.com",
    "https://api1.binance.com",
    "https://api.binance.com",
]

COINGECKO_CHART = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart"

# Berapa hari data CoinGecko diminta + ukuran bucket (detik) per interval,
# supaya hasil agregasi menghasilkan cukup banyak candle (>= 60).
_CG_PLAN = {
    "1h": (30, 3600),      # 30 hari, bucket 1 jam  -> ~720 candle
    "4h": (90, 14400),     # 90 hari, bucket 4 jam  -> ~540 candle
    "1d": (365, 86400),    # 365 hari, bucket harian -> ~365 candle
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
            resp = requests.get(
                url,
                params=params,
                timeout=timeout,
                headers={"User-Agent": "btc-signal/1.0 (+github-actions)"},
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:  # noqa: BLE001 - sengaja luas, lalu retry
            last_exc = exc
            time.sleep(1.5 * (attempt + 1))
    raise DataError(f"Gagal GET {url}: {last_exc}")


def _from_binance(symbol: str, interval: str, limit: int) -> List[Candle]:
    last_exc: Exception | None = None
    for host in _BINANCE_HOSTS:
        url = f"{host}/api/v3/klines"
        try:
            raw = _get_json(
                url,
                {"symbol": symbol, "interval": interval, "limit": limit},
                retries=1,
            )
            candles = [
                Candle(
                    open_time=int(k[0]),
                    open=float(k[1]),
                    high=float(k[2]),
                    low=float(k[3]),
                    close=float(k[4]),
                    volume=float(k[5]),
                )
                for k in raw
            ]
            if candles:
                print(f"[data] Sumber: Binance ({host}) — {len(candles)} candle.")
                return candles
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            print(f"[data] Binance {host} gagal: {exc}")
    raise DataError(f"Semua host Binance gagal: {last_exc}")


def _from_coingecko(interval: str, limit: int) -> List[Candle]:
    days, bucket_s = _CG_PLAN.get(interval, (90, 14400))
    data = _get_json(
        COINGECKO_CHART,
        {"vs_currency": "usd", "days": days},
    )
    prices = data.get("prices", [])  # [[ts_ms, price], ...]
    volumes = {int(ts): v for ts, v in data.get("total_volumes", [])}
    if not prices:
        raise DataError("CoinGecko tidak mengembalikan data harga.")

    # Agregasi titik-titik harga ke dalam bucket waktu -> candle OHLC.
    bucket_ms = bucket_s * 1000
    buckets: dict[int, list] = {}
    order: List[int] = []
    for ts, price in prices:
        ts = int(ts)
        key = ts - (ts % bucket_ms)
        if key not in buckets:
            buckets[key] = [price, price, price, price]  # o, h, l, c
            order.append(key)
        else:
            b = buckets[key]
            b[1] = max(b[1], price)  # high
            b[2] = min(b[2], price)  # low
            b[3] = price             # close (terakhir menang)

    candles = [
        Candle(
            open_time=key,
            open=buckets[key][0],
            high=buckets[key][1],
            low=buckets[key][2],
            close=buckets[key][3],
            volume=float(volumes.get(key, 0.0)),
        )
        for key in order
    ]
    print(f"[data] Sumber: CoinGecko (fallback) — {len(candles)} candle.")
    return candles[-limit:]


def get_candles(
    symbol: str = "BTCUSDT",
    interval: str = "1h",
    limit: int = 300,
) -> List[Candle]:
    """Ambil candlestick BTC. Coba Binance (beberapa host) lalu CoinGecko."""
    try:
        candles = _from_binance(symbol, interval, limit)
        if candles:
            return candles
    except DataError as exc:
        print(f"[data] Binance tidak tersedia, pakai fallback. ({exc})")

    candles = _from_coingecko(interval, limit)
    if not candles:
        raise DataError("Gagal mengambil data dari semua sumber.")
    return candles


def closes(candles: List[Candle]) -> List[float]:
    return [c.close for c in candles]
