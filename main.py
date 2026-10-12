#!/usr/bin/env python3
"""BTC Signal — entry point.

Jalankan sekali (untuk GitHub Actions / manual):
    python main.py                      # timeframe default 1h
    python main.py --interval 4h        # ganti timeframe
    python main.py --only-on-change     # kirim Telegram hanya jika sinyal berubah
    python main.py --notify-only JUAL   # kirim Telegram hanya untuk aksi tertentu

Mode WATCH (loop terus di komputermu sendiri, cek tiap N detik):
    python main.py --watch              # cek tiap 60 detik (default)
    python main.py --watch --every 30   # cek tiap 30 detik
    python main.py --watch --every 60 --only-on-change
    (hentikan dengan menekan  Ctrl + C )

Environment (opsional, untuk Telegram):
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime

from btcsignal.data import get_candles, get_usd_to_idr
from btcsignal.engine import analyze
from btcsignal.features import latest_feature_row
from btcsignal.futures import build_plan
from btcsignal.ml_model import Model
from btcsignal.notify import (
    format_combined_message,
    format_futures_message,
    format_message,
    money,
    send_telegram,
)

STATE_FILE = ".last_signal.json"


def _load_last_action() -> str | None:
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh).get("action")
    except (OSError, ValueError):
        return None


def _save_last_action(action: str) -> None:
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as fh:
            json.dump({"action": action}, fh)
    except OSError:
        pass


def run_once(args) -> int:
    """Satu kali: ambil data, analisa, cetak, (opsional) kirim notif."""
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"==> [{stamp}] Mengambil data {args.symbol} ({args.interval})...")
    try:
        candles = get_candles(args.symbol, args.interval, args.limit)
        sig = analyze(candles)
    except Exception as exc:  # noqa: BLE001
        # Jangan hentikan program hanya karena sumber data lagi bermasalah.
        print(f"[main] GAGAL mengambil/menganalisa data: {exc}")
        print("[main] Lewati siklus ini. Akan dicoba lagi berikutnya.")
        return 0

    # Prediksi AI (opsional). Memberi "pendapat kedua" berupa probabilitas NAIK.
    ai_prob = None
    if args.ai:
        model = Model.load()
        if model is None:
            print("[ai] Model belum ada. Latih dulu: python train_ai.py")
        else:
            try:
                ai_prob = model.predict_proba_up(latest_feature_row(candles))
                print(f"[ai] Model {model.kind} — prob NAIK candle berikutnya: "
                      f"{ai_prob*100:.1f}%")
            except Exception as exc:  # noqa: BLE001
                print(f"[ai] Gagal prediksi: {exc}")

    # Mata uang tampilan: usd (default) atau idr.
    currency = (args.currency or "usd").lower()
    rate = 1.0
    if currency == "idr":
        rate = get_usd_to_idr()

    def m(v, dec=None):
        return money(v, currency, rate, dec)

    # Mode: spot saja, futures saja, atau keduanya (--both).
    want_futures = args.futures or args.both
    want_spot = (not args.futures) or args.both  # spot tampil kecuali futures-only

    # Mode FUTURES: bangun rencana (LONG/SHORT, SL, TP, likuidasi, ukuran posisi).
    plan = None
    if want_futures:
        plan = build_plan(
            sig,
            candles,
            leverage=args.leverage,
            capital_usd=args.capital,
            risk_pct=args.risk,
        )

    # Cetak ke terminal / log.
    print("=" * 48)
    if want_spot:
        print(f"  🏦 SPOT     : {sig.action}  ({sig.confidence}%)")
        print(f"     Harga    : {m(sig.price)}  |  TF {args.interval}")
        for r in sig.reasons:
            print(f"       - {r}")
        if plan is not None:
            print("  " + "-" * 44)
    if plan is not None:
        print(f"  ⚡ FUTURES  : {plan.position}  (leverage {plan.leverage}x)")
        print(f"     Entry    : {m(plan.entry)}  ({plan.confidence}%)")
        if plan.position != "NO-TRADE":
            print(f"     Stop Loss: {m(plan.stop_loss)}")
            print(f"     Take Prof: {m(plan.take_profit)}  (R:R 1:{plan.risk_reward})")
            print(f"     Likuidasi: {m(plan.liquidation)} (perkiraan)")
            if plan.position_size_usd:
                print(f"     Ukuran   : {m(plan.position_size_usd, 0)} "
                      f"({plan.position_size_btc} BTC)")
        print("     Catatan  :")
        for n in plan.notes:
            print(f"       - {n}")
    if ai_prob is not None:
        arah = "NAIK 📈" if ai_prob >= 0.5 else "TURUN 📉"
        print("  " + "-" * 44)
        print(f"  🤖 AI       : {arah}  (prob naik {ai_prob*100:.1f}%)")
    print("=" * 48)

    # Tentukan apakah perlu kirim notifikasi.
    should_notify = not args.no_notify
    last_action = _load_last_action()

    # "Perubahan" dilihat dari gabungan spot(aksi) + futures(posisi).
    if args.both and plan is not None:
        current_state = f"{sig.action}|{plan.position}"
    elif plan is not None:
        current_state = plan.position
    else:
        current_state = sig.action

    if args.notify_only and sig.action != args.notify_only:
        should_notify = False
    if args.only_on_change and last_action == current_state:
        should_notify = False
        print(f"[main] Sama dengan sebelumnya ({current_state}) — lewati notif.")

    if should_notify:
        if args.both and plan is not None:
            send_telegram(format_combined_message(sig, plan, args.interval, currency, rate, ai_prob))
        elif plan is not None:
            send_telegram(format_futures_message(plan, args.interval, currency, rate, ai_prob))
        else:
            send_telegram(format_message(sig, args.interval, currency, rate, ai_prob))

    _save_last_action(current_state)

    # Expose hasil ke GitHub Actions step berikutnya (bila ada).
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a", encoding="utf-8") as fh:
            fh.write(f"action={sig.action}\n")
            fh.write(f"confidence={sig.confidence}\n")
            fh.write(f"price={sig.price}\n")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Deteksi arah pasar BTC.")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--interval", default="1h", help="1h, 4h, atau 1d")
    parser.add_argument("--limit", type=int, default=300)
    parser.add_argument(
        "--currency",
        choices=["usd", "idr"],
        default="usd",
        help="Mata uang tampilan harga: usd (default) atau idr (Rupiah).",
    )
    parser.add_argument(
        "--only-on-change",
        action="store_true",
        help="Kirim Telegram hanya jika aksi berbeda dari sebelumnya.",
    )
    parser.add_argument(
        "--notify-only",
        choices=["BELI", "JUAL", "TAHAN"],
        help="Kirim Telegram hanya untuk aksi ini.",
    )
    parser.add_argument(
        "--no-notify",
        action="store_true",
        help="Jangan kirim Telegram (hanya cetak ke terminal).",
    )
    parser.add_argument(
        "--futures",
        action="store_true",
        help="Mode FUTURES saja: sinyal LONG/SHORT + Stop Loss, Take Profit, likuidasi.",
    )
    parser.add_argument(
        "--both",
        action="store_true",
        help="Tampilkan SPOT + FUTURES sekaligus dalam satu pesan.",
    )
    parser.add_argument(
        "--ai",
        action="store_true",
        help="Tambahkan prediksi AI (butuh model; latih dulu: python train_ai.py).",
    )
    parser.add_argument(
        "--leverage",
        type=int,
        default=3,
        help="Leverage untuk mode futures (default 3x). Makin tinggi makin bahaya!",
    )
    parser.add_argument(
        "--capital",
        type=float,
        default=0.0,
        help="Modal (USD) untuk saran ukuran posisi futures. 0 = lewati.",
    )
    parser.add_argument(
        "--risk",
        type=float,
        default=1.0,
        help="Persen modal yang dirisikokan per trade (default 1%%).",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Mode loop: cek terus-menerus tiap N detik (lihat --every).",
    )
    parser.add_argument(
        "--every",
        type=int,
        default=60,
        help="Jeda antar cek dalam DETIK saat --watch (default 60 = tiap menit).",
    )
    args = parser.parse_args()

    if not args.watch:
        return run_once(args)

    # --- MODE WATCH: loop tiap N detik ---
    print(f"🔁 Mode WATCH aktif — cek tiap {args.every} detik. Tekan Ctrl+C untuk berhenti.\n")
    try:
        while True:
            run_once(args)
            print(f"... tidur {args.every} detik ...\n")
            time.sleep(args.every)
    except KeyboardInterrupt:
        print("\n⏹️  Dihentikan. Sampai jumpa!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
