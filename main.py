#!/usr/bin/env python3
"""BTC Signal — entry point.

Jalankan:
    python main.py                      # timeframe default 1h
    python main.py --interval 4h        # ganti timeframe
    python main.py --only-on-change     # kirim Telegram hanya jika sinyal berubah
    python main.py --notify-only JUAL   # kirim Telegram hanya untuk aksi tertentu

Environment (opsional, untuk Telegram):
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
"""

from __future__ import annotations

import argparse
import json
import os
import sys

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


def main() -> int:
    parser = argparse.ArgumentParser(description="Deteksi arah pasar BTC.")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--interval", default="1h", help="1h, 4h, atau 1d")
    parser.add_argument("--limit", type=int, default=300)
    parser.add_argument(
        "--only-on-change",
        action="store_true",
        help="Kirim Telegram hanya jika aksi berbeda dari jalan sebelumnya.",
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
    args = parser.parse_args()

    print(f"==> Mengambil data {args.symbol} ({args.interval})...")
    candles = get_candles(args.symbol, args.interval, args.limit)
    sig = analyze(candles)

    # Cetak ke terminal / log GitHub Actions.
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


if __name__ == "__main__":
    sys.exit(main())
