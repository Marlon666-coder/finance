"""Rencana trading untuk BTC FUTURES.

Mengubah sinyal arah (dari engine) menjadi rencana futures yang lebih lengkap:
  - Posisi: LONG / SHORT / NO-TRADE
  - Entry, Stop Loss (SL), Take Profit (TP) berbasis volatilitas (ATR)
  - Saran ukuran posisi berdasarkan modal & % risiko
  - Estimasi harga likuidasi sesuai leverage + peringatan

PERINGATAN KERAS: Futures = SANGAT berisiko. Leverage memperbesar untung DAN
rugi; posisi bisa dilikuidasi (modal habis) dalam hitungan menit. Ini BUKAN
nasihat finansial. Gunakan leverage kecil & coba di testnet dulu.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .data import Candle
from .engine import Signal
from .indicators import atr

# Pengali ATR untuk jarak Stop Loss & Take Profit.
SL_ATR_MULT = 1.5   # SL = 1.5x ATR dari entry
TP_ATR_MULT = 3.0   # TP = 3.0x ATR dari entry (risk:reward 1:2)

# Jangan buka posisi kalau keyakinan sinyal di bawah ambang ini (hindari noise).
MIN_CONFIDENCE = 35


@dataclass
class FuturesPlan:
    position: str  # "LONG" | "SHORT" | "NO-TRADE"
    confidence: int
    entry: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    risk_reward: Optional[float] = None
    liquidation: Optional[float] = None
    leverage: int = 1
    position_size_usd: Optional[float] = None
    position_size_btc: Optional[float] = None
    notes: List[str] = field(default_factory=list)


def _last_valid(series):
    for v in reversed(series):
        if v is not None:
            return v
    return None


def build_plan(
    sig: Signal,
    candles: List[Candle],
    leverage: int = 3,
    capital_usd: float = 0.0,
    risk_pct: float = 1.0,
) -> FuturesPlan:
    """Bangun rencana futures dari sinyal + data candle.

    leverage    : pengali posisi (mis. 3 = 3x). Hati-hati makin tinggi makin bahaya.
    capital_usd : modal yang kamu alokasikan (USD). 0 = lewati saran ukuran posisi.
    risk_pct    : berapa % modal yang rela kamu risikokan per trade (default 1%).
    """
    highs = [c.high for c in candles]
    lows = [c.low for c in candles]
    closes = [c.close for c in candles]
    entry = closes[-1]

    atr_val = _last_valid(atr(highs, lows, closes, 14)) or (entry * 0.01)

    notes: List[str] = []

    # Peta arah: BELI->LONG, JUAL->SHORT, TAHAN->NO-TRADE.
    if sig.action == "BELI":
        position = "LONG"
    elif sig.action == "JUAL":
        position = "SHORT"
    else:
        position = "NO-TRADE"

    # Filter keyakinan rendah.
    if position != "NO-TRADE" and sig.confidence < MIN_CONFIDENCE:
        notes.append(
            f"Keyakinan {sig.confidence}% < {MIN_CONFIDENCE}% → lebih baik TIDAK "
            f"buka posisi (sinyal lemah/rawan palsu)."
        )
        position = "NO-TRADE"

    plan = FuturesPlan(
        position=position,
        confidence=sig.confidence,
        entry=round(entry, 2),
        leverage=leverage,
    )

    if position == "NO-TRADE":
        notes.insert(0, "Pasar belum jelas / sinyal lemah. Tunggu setup lebih baik.")
        plan.notes = notes
        return plan

    # --- Stop Loss & Take Profit berbasis ATR ---
    sl_dist = SL_ATR_MULT * atr_val
    tp_dist = TP_ATR_MULT * atr_val
    if position == "LONG":
        sl = entry - sl_dist
        tp = entry + tp_dist
    else:  # SHORT
        sl = entry + sl_dist
        tp = entry - tp_dist

    plan.stop_loss = round(sl, 2)
    plan.take_profit = round(tp, 2)
    plan.risk_reward = round(tp_dist / sl_dist, 2) if sl_dist else None

    # --- Estimasi harga likuidasi (perkiraan kasar, cross/isolated beda2) ---
    # Pendekatan sederhana: likuidasi kira-kira saat kerugian = 100%/leverage.
    liq_move = entry / leverage
    if position == "LONG":
        plan.liquidation = round(entry - liq_move, 2)
    else:
        plan.liquidation = round(entry + liq_move, 2)

    # --- Saran ukuran posisi berdasarkan risiko ---
    if capital_usd > 0:
        risk_amount = capital_usd * (risk_pct / 100.0)  # USD yang direlakan hilang
        stop_distance = abs(entry - sl)
        if stop_distance > 0:
            # Ukuran posisi (BTC) agar kerugian di SL = risk_amount.
            size_btc = risk_amount / stop_distance
            size_usd = size_btc * entry
            plan.position_size_btc = round(size_btc, 6)
            plan.position_size_usd = round(size_usd, 2)
            notes.append(
                f"Dengan modal ${capital_usd:,.0f} & risiko {risk_pct}% "
                f"(${risk_amount:,.2f}), ukuran posisi ≈ ${size_usd:,.0f} "
                f"({size_btc:.4f} BTC). Margin ≈ ${size_usd / leverage:,.0f} "
                f"pada {leverage}x."
            )

    # Peringatan likuidasi vs SL.
    if plan.liquidation is not None and plan.stop_loss is not None:
        if position == "LONG" and plan.liquidation >= plan.stop_loss:
            notes.append(
                "⚠️ BAHAYA: harga likuidasi lebih dekat daripada Stop Loss! "
                "Leverage terlalu tinggi — turunkan leverage."
            )
        if position == "SHORT" and plan.liquidation <= plan.stop_loss:
            notes.append(
                "⚠️ BAHAYA: harga likuidasi lebih dekat daripada Stop Loss! "
                "Leverage terlalu tinggi — turunkan leverage."
            )

    notes.append(
        f"ATR(14) ≈ ${atr_val:,.0f} → SL {SL_ATR_MULT}x ATR, TP {TP_ATR_MULT}x ATR "
        f"(risk:reward 1:{plan.risk_reward})."
    )
    plan.notes = notes
    return plan
