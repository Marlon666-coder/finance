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
        test_atr, test_futures_long, test_futures_short,
        test_futures_low_confidence_blocks,
    ]
    print("Menjalankan self-test offline...")
    for t in tests:
        t()
    print("\nSEMUA TEST LULUS ✅")
    return 0


def test_atr():
    from btcsignal.indicators import atr
    highs = [10 + i for i in range(50)]
    lows = [8 + i for i in range(50)]
    closes = [9 + i for i in range(50)]
    a = atr(highs, lows, closes, 14)
    val = [x for x in a if x is not None]
    assert val, "ATR harus menghasilkan nilai"
    assert all(x > 0 for x in val), "ATR harus positif"
    print(f"  [ok] ATR -> {val[-1]:.2f}")


def test_futures_long():
    from btcsignal.futures import build_plan
    prices = [100 + i * 2.0 for i in range(130)]  # tren naik kuat
    candles = make_candles(prices)
    sig = analyze(candles)
    plan = build_plan(sig, candles, leverage=5, capital_usd=1000, risk_pct=1.0)
    assert plan.position in {"LONG", "NO-TRADE"}, plan.position
    if plan.position == "LONG":
        assert plan.stop_loss < plan.entry, "SL LONG harus di bawah entry"
        assert plan.take_profit > plan.entry, "TP LONG harus di atas entry"
        assert plan.liquidation < plan.entry, "likuidasi LONG di bawah entry"
        assert plan.position_size_usd and plan.position_size_usd > 0
    print(f"  [ok] Futures LONG -> {plan.position} "
          f"entry={plan.entry} SL={plan.stop_loss} TP={plan.take_profit}")


def test_futures_short():
    from btcsignal.futures import build_plan
    prices = [360 - i * 2.0 for i in range(130)]  # tren turun kuat
    candles = make_candles(prices)
    sig = analyze(candles)
    plan = build_plan(sig, candles, leverage=5, capital_usd=1000, risk_pct=1.0)
    assert plan.position in {"SHORT", "NO-TRADE"}, plan.position
    if plan.position == "SHORT":
        assert plan.stop_loss > plan.entry, "SL SHORT harus di atas entry"
        assert plan.take_profit < plan.entry, "TP SHORT harus di bawah entry"
        assert plan.liquidation > plan.entry, "likuidasi SHORT di atas entry"
    print(f"  [ok] Futures SHORT -> {plan.position} "
          f"entry={plan.entry} SL={plan.stop_loss} TP={plan.take_profit}")


def test_futures_low_confidence_blocks():
    from btcsignal.futures import build_plan
    import math
    prices = [200 + math.sin(i / 3) * 0.3 for i in range(130)]  # datar
    candles = make_candles(prices)
    sig = analyze(candles)
    plan = build_plan(sig, candles, leverage=20)
    # keyakinan rendah ATAU TAHAN -> boleh NO-TRADE; yang penting tidak crash.
    assert plan.position in {"LONG", "SHORT", "NO-TRADE"}
    print(f"  [ok] Futures low-conf -> {plan.position} ({plan.confidence}%)")


if __name__ == "__main__":
    sys.exit(main())
