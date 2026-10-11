"""Kirim notifikasi sinyal ke Telegram.

Butuh 2 environment variable (disetel sebagai GitHub Secrets):
  - TELEGRAM_BOT_TOKEN : token dari @BotFather
  - TELEGRAM_CHAT_ID   : chat/channel ID tujuan

Kalau salah satu tidak ada, notifikasi dilewati (tidak error) — berguna saat
menjalankan lokal hanya untuk melihat output di terminal.
"""

from __future__ import annotations

import os

try:
    import requests
except ImportError:
    requests = None  # type: ignore

from .engine import Signal

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"

_EMOJI = {"BELI": "🟢📈", "JUAL": "🔴📉", "TAHAN": "🟡✋"}


def format_message(sig: Signal, interval: str) -> str:
    emoji = _EMOJI.get(sig.action, "")
    lines = [
        f"{emoji} *BTC SIGNAL — {sig.action}*",
        "",
        f"💰 Harga: *${sig.price:,.2f}*",
        f"🎯 Keyakinan: *{sig.confidence}%*  (skor {sig.score:+.2f})",
        f"🕒 Timeframe: `{interval}`",
        "",
        "*Alasan:*",
    ]
    for r in sig.reasons:
        lines.append(f"• {r}")
    lines.append("")
    lines.append("_⚠️ Bukan nasihat finansial. Sinyal bisa salah._")
    return "\n".join(lines)


def send_telegram(text: str) -> bool:
    """Kirim pesan. Return True kalau terkirim, False kalau dilewati/gagal."""
    if requests is None:
        print("[notify] Library 'requests' belum terinstall — lewati notifikasi.")
        return False
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("[notify] TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID tidak diset — "
              "lewati notifikasi.")
        return False

    try:
        resp = requests.post(
            TELEGRAM_API.format(token=token),
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True,
            },
            timeout=15,
        )
        resp.raise_for_status()
        print("[notify] Notifikasi Telegram terkirim.")
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"[notify] Gagal kirim Telegram: {exc}")
        return False
