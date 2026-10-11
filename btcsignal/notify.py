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


def money(value_usd: float, currency: str = "usd", rate: float = 1.0,
          decimals: int | None = None) -> str:
    """Format angka USD ke mata uang pilihan (usd / idr).

    currency : "usd" atau "idr"
    rate     : kurs 1 USD = berapa IDR (dipakai kalau currency=idr)
    """
    cur = (currency or "usd").lower()
    if cur == "idr":
        val = value_usd * rate
        dec = 0 if decimals is None else decimals
        return f"Rp{val:,.{dec}f}"
    # default USD
    dec = 2 if decimals is None else decimals
    return f"${value_usd:,.{dec}f}"


def format_message(sig: Signal, interval: str,
                   currency: str = "usd", rate: float = 1.0) -> str:
    emoji = _EMOJI.get(sig.action, "")
    lines = [
        f"{emoji} *BTC SIGNAL — {sig.action}*",
        "",
        f"💰 Harga: *{money(sig.price, currency, rate)}*",
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


_POS_EMOJI = {"LONG": "🟢⬆️ LONG", "SHORT": "🔴⬇️ SHORT", "NO-TRADE": "⚪⏸️ NO-TRADE"}


def format_futures_message(plan, interval: str,
                           currency: str = "usd", rate: float = 1.0) -> str:
    """Format pesan untuk rencana FUTURES."""
    head = _POS_EMOJI.get(plan.position, plan.position)
    lines = [
        f"⚡ *BTC FUTURES — {head}*",
        "",
        f"💰 Entry: *{money(plan.entry, currency, rate)}*",
        f"🎯 Keyakinan: *{plan.confidence}%*",
        f"🕒 Timeframe: `{interval}`  |  ⚖️ Leverage: *{plan.leverage}x*",
    ]

    if plan.position != "NO-TRADE":
        lines += [
            "",
            f"🛑 Stop Loss : *{money(plan.stop_loss, currency, rate)}*",
            f"✅ Take Profit: *{money(plan.take_profit, currency, rate)}*",
            f"📊 Risk:Reward: *1:{plan.risk_reward}*",
            f"💀 Est. Likuidasi: *{money(plan.liquidation, currency, rate)}*",
        ]
        if plan.position_size_usd:
            lines.append(
                f"📦 Ukuran posisi: *{money(plan.position_size_usd, currency, rate, 0)}* "
                f"({plan.position_size_btc} BTC)"
            )

    if plan.notes:
        lines.append("")
        lines.append("*Catatan:*")
        for n in plan.notes:
            lines.append(f"• {n}")

    lines += [
        "",
        "_☠️ FUTURES SANGAT BERISIKO — bisa likuidasi (modal habis)._",
        "_Bukan nasihat finansial. Pakai leverage kecil & SL selalu._",
    ]
    return "\n".join(lines)


def format_combined_message(sig: Signal, plan, interval: str,
                            currency: str = "usd", rate: float = 1.0) -> str:
    """Satu pesan berisi SPOT + FUTURES sekaligus."""
    spot_emoji = _EMOJI.get(sig.action, "")
    pos = _POS_EMOJI.get(plan.position, plan.position)

    lines = [
        "📊 *BTC — SPOT & FUTURES*",
        f"💰 Harga: *{money(sig.price, currency, rate)}*   |   🕒 `{interval}`",
        "",
        "──────────────",
        f"🏦 *SPOT:* {spot_emoji} *{sig.action}*  ({sig.confidence}%)",
    ]
    for r in sig.reasons:
        lines.append(f"  • {r}")

    lines += [
        "",
        "──────────────",
        f"⚡ *FUTURES:* {pos}  ({plan.confidence}%, {plan.leverage}x)",
    ]
    if plan.position != "NO-TRADE":
        lines += [
            f"  🛑 SL: *{money(plan.stop_loss, currency, rate)}*",
            f"  ✅ TP: *{money(plan.take_profit, currency, rate)}*  (R:R 1:{plan.risk_reward})",
            f"  💀 Likuidasi: *{money(plan.liquidation, currency, rate)}*",
        ]
        if plan.position_size_usd:
            lines.append(
                f"  📦 Posisi: *{money(plan.position_size_usd, currency, rate, 0)}* "
                f"({plan.position_size_btc} BTC)"
            )
    else:
        lines.append("  (tidak buka posisi — sinyal lemah/netral)")

    lines += [
        "",
        "_⚠️ Bukan nasihat finansial. Futures bisa likuidasi (modal habis)._",
    ]
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
