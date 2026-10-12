#!/usr/bin/env python3
"""Latih model AI untuk deteksi arah BTC.

Jalankan di komputermu (butuh internet untuk ambil data historis):
    python train_ai.py                 # default 1500 candle 1h
    python train_ai.py --interval 4h --limit 1000
    python train_ai.py --horizon 3     # prediksi 3 candle ke depan

Alur:
  1. Ambil ribuan candle BTC historis
  2. Ubah jadi fitur (indikator)
  3. Bagi data: 80% latih, 20% uji (data uji TIDAK dipakai saat latih)
  4. Latih model, lalu uji di data yang belum dilihat → akurasi JUJUR
  5. Simpan model ke file

⚠️ Akurasi 50-60% itu normal. Pasar mendekati acak. Bukan nasihat finansial.
"""

from __future__ import annotations

import argparse
import sys

from btcsignal.data import get_candles
from btcsignal.features import build_feature_matrix
from btcsignal.ml_model import Model, evaluate


def main() -> int:
    ap = argparse.ArgumentParser(description="Latih AI deteksi arah BTC.")
    ap.add_argument("--symbol", default="BTCUSDT")
    ap.add_argument("--interval", default="1h")
    ap.add_argument("--limit", type=int, default=1500,
                    help="Jumlah candle historis (makin banyak makin baik).")
    ap.add_argument("--horizon", type=int, default=1,
                    help="Prediksi berapa candle ke depan (default 1).")
    args = ap.parse_args()

    print(f"==> Ambil {args.limit} candle {args.symbol} ({args.interval})...")
    candles = get_candles(args.symbol, args.interval, args.limit)
    print(f"    Dapat {len(candles)} candle.")

    print("==> Buat fitur...")
    X, y, names = build_feature_matrix(candles, horizon=args.horizon)
    print(f"    {len(X)} sampel, {len(names)} fitur.")
    if len(X) < 100:
        print("    [!] Data terlalu sedikit untuk latih AI yang berarti.")
        return 1

    # Split kronologis (bukan acak!) — latih di masa lalu, uji di masa setelahnya.
    # Ini mencegah "kebocoran masa depan" yang bikin akurasi palsu.
    split = int(len(X) * 0.8)
    Xtr, ytr = X[:split], y[:split]
    Xte, yte = X[split:], y[split:]
    print(f"==> Latih di {len(Xtr)} sampel, uji di {len(Xte)} sampel (kronologis).")

    model = Model.train(Xtr, ytr, names)
    print(f"    Jenis model: {model.kind}")

    train_metrics = evaluate(model, Xtr, ytr)
    test_metrics = evaluate(model, Xte, yte)

    print("\n================ HASIL ================")
    print(f"  Akurasi di data LATIH : {train_metrics['accuracy']*100:.1f}%")
    print(f"  Akurasi di data UJI   : {test_metrics['accuracy']*100:.1f}%  "
          f"(ini yang JUJUR, {test_metrics['n']} sampel)")
    print(f"  Baseline (asal tebak) : {max(test_metrics['up_rate_actual'], 1-test_metrics['up_rate_actual'])*100:.1f}%")
    print("  Confusion (uji): "
          f"benar-naik={test_metrics['tp']} benar-turun={test_metrics['tn']} "
          f"salah-naik={test_metrics['fp']} salah-turun={test_metrics['fn']}")
    print("=======================================")

    acc = test_metrics["accuracy"]
    base = max(test_metrics["up_rate_actual"], 1 - test_metrics["up_rate_actual"])
    if acc <= base + 0.01:
        print("  [!] Model TIDAK lebih baik dari tebak asal. Jangan diandalkan.")
    else:
        print(f"  [ok] Model sedikit lebih baik dari baseline (+{(acc-base)*100:.1f}%).")

    path = model.save()
    print(f"\n==> Model disimpan ke: {path}")
    print("    Pakai di sinyal dengan:  python main.py --ai")
    return 0


if __name__ == "__main__":
    sys.exit(main())
