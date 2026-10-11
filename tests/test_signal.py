"""Self-test offline (tanpa network / requests).

Menguji indikator dan engine dengan data sintetis supaya logika inti
terverifikasi di lingkungan tanpa akses internet.

Jalankan dari root repo:  python tests/test_signal.py
"""
import math
import os
import sys

# Pastikan root repo ada di sys.path saat dijalankan langsung.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Impor langsung modul yang tak butuh network.
from btcsignal import indicators as ind
from btcsignal.engine import analyze
from btcsignal.data import Candle  # dataclass saja, impor requests di top module


def make_candles(prices):
    return [
        Candle(open_time=i * 3600000, open=p, high=p * 1.01,
               low=p * 0.99, close=p, volume=1.0)
        for i, p in enumerate(prices)
    ]


def test_sma():
    assert ind.sma([1, 2, 3, 4], 2)[-1] == 3.5
    assert ind.sma([1, 2, 3], 5)[-1] is None
    print("  [ok] SMA")


def test_ema_rsi_macd_shapes():
    px = [math.sin(i / 5) * 10 + 100 for i in range(100)]
    assert len(ind.ema(px, 12)) == 100
    assert any(v is not None for v in ind.rsi(px, 14))
    m, s, h = ind.macd(px)
    assert len(m) == len(s) == len(h) == 100
    print("  [ok] EMA/RSI/MACD")


def test_rsi_bounds():
    rising = list(range(1, 60))
    r = [v for v in ind.rsi([float(x) for x in rising], 14) if v is not None]
    assert max(r) <= 100.0 and min(r) >= 0.0
    assert r[-1] > 90  # harga naik terus -> RSI tinggi
    print("  [ok] RSI bounds")


def test_engine_uptrend():
    # Tren naik kuat -> harusnya BELI.
    prices = [100 + i * 1.5 for i in range(120)]
    sig = analyze(make_candles(prices))
    assert sig.action == "BELI", sig.action
    assert sig.confidence > 0
    print(f"  [ok] Engine uptrend -> {sig.action} ({sig.confidence}%)")


def test_engine_downtrend():
    prices = [300 - i * 1.5 for i in range(120)]
    sig = analyze(make_candles(prices))
    assert sig.action == "JUAL", sig.action
    print(f"  [ok] Engine downtrend -> {sig.action} ({sig.confidence}%)")


def test_engine_flat():
    prices = [200 + math.sin(i / 3) * 0.5 for i in range(120)]
    sig = analyze(make_candles(prices))
    print(f"  [info] Engine flat -> {sig.action} ({sig.confidence}%)")
    assert sig.action in {"BELI", "JUAL", "TAHAN"}


def main():
    tests = [
        test_sma, test_ema_rsi_macd_shapes, test_rsi_bounds,
        test_engine_uptrend, test_engine_downtrend, test_engine_flat,
    ]
    print("Menjalankan self-test offline...")
    for t in tests:
        t()
    print("\nSEMUA TEST LULUS ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
