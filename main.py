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

from btcsignal.data import get_candles
from btcsignal.engine import analyze
from btcsignal.notify import format_message, send_telegram

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

    # Cetak ke terminal / log.
    print("=" * 48)
    print(f"  AKSI       : {sig.action}")
    print(f"  Harga      : ${sig.price:,.2f}")
    print(f"  Keyakinan  : {sig.confidence}%  (skor {sig.score:+.2f})")
    print(f"  Timeframe  : {args.interval}")
    print("  Indikator  :", json.dumps(sig.details, ensure_ascii=False))
    print("  Alasan     :")
    for r in sig.reasons:
        print(f"    - {r}")
    print("=" * 48)

    # Tentukan apakah perlu kirim notifikasi.
    should_notify = not args.no_notify
    last_action = _load_last_action()

    if args.notify_only and sig.action != args.notify_only:
        should_notify = False
    if args.only_on_change and last_action == sig.action:
        should_notify = False
        print(f"[main] Aksi sama dengan sebelumnya ({sig.action}) — lewati notif.")

    if should_notify:
        send_telegram(format_message(sig, args.interval))

    _save_last_action(sig.action)

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
