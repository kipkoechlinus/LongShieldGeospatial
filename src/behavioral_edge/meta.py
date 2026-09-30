"""
Meta-labeler + anti-rival edge.

Primary detectors find human bias. Meta decides whether the trade is
*worth taking* given volatility regime and whether rival momentum stacks
are about to donate flow (crowded chase we can fade).
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd

from behavioral_edge.features import herd_intensity, realized_vol
from behavioral_edge.signals import Signal, SignalKind


def _atr_pct(df: pd.DataFrame, i: int, window: int = 14) -> float:
    high = df["high"]
    low = df["low"]
    close = df["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            (high - low),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr = tr.rolling(window).mean().iloc[i]
    px = float(close.iloc[i])
    if px <= 0 or np.isnan(atr):
        return 0.02
    return float(atr / px)


def _rival_momentum_side(df: pd.DataFrame, i: int) -> str | None:
    """Approximate what SMA/RSI rivals want right now."""
    if i < 50:
        return None
    close = df["close"]
    sma = close.rolling(50).mean().iloc[i]
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean().iloc[i]
    loss = (-delta.clip(upper=0)).rolling(14).mean().iloc[i]
    if loss == 0 or np.isnan(loss) or np.isnan(gain) or np.isnan(sma):
        return None
    rsi = 100 - (100 / (1 + gain / loss))
    px = close.iloc[i]
    if px > sma and rsi > 55:
        return "long"
    if px < sma and rsi < 45:
        return "short"
    return None


def meta_label(df: pd.DataFrame, signal: Signal) -> Signal | None:
    """
    Upgrade or veto a signal.

    Boost when we fade crowded rival momentum (they are the liquidity).
    Veto when vol is dead (nothing to harvest) or insane (stops get run).
    ATR-normalize stops/targets so we aren't using toy fixed percentages.
    """
    i = signal.bar_index
    if i < 50:
        return None

    vol = float(realized_vol(df["close"], 20).iloc[i])
    vol_med = float(
        realized_vol(df["close"], 20).iloc[max(0, i - 60) : i + 1].median()
    )
    if vol_med <= 0 or np.isnan(vol) or np.isnan(vol_med):
        return None

    vol_ratio = vol / vol_med
    # Sweet spot: emotion present, not nuclear
    if vol_ratio < 0.65 or vol_ratio > 2.4:
        return None

    herd = float(herd_intensity(df).iloc[i])
    rival = _rival_momentum_side(df, i)
    anti_rival = 0.0
    note = []

    # Fade setups that harvest rival chase / dump
    if signal.kind in {
        SignalKind.FOMO_EXHAUSTION,
        SignalKind.ANCHOR_REJECTION,
    } and signal.side == "short" and rival == "long":
        anti_rival = 0.15
        note.append("fade-muse/grok-longs")
    if signal.kind in {
        SignalKind.PANIC_CAPITULATION,
        SignalKind.ANCHOR_REJECTION,
    } and signal.side == "long" and rival == "short":
        anti_rival = 0.15
        note.append("fade-muse/grok-shorts")

    # Disposition rides WITH trend rivals — slight boost if aligned
    if signal.kind == SignalKind.DISPOSITION_CONTINUATION and rival == signal.side:
        anti_rival = 0.08
        note.append("trend-align")

    atrp = _atr_pct(df, i)
    # ATR stops: ~1.2 ATR stop, target from signal R structure
    stop = max(0.008, min(0.05, atrp * 1.2))
    rr = signal.target_pct / signal.stop_pct if signal.stop_pct > 0 else 1.5
    rr = max(0.5, min(rr, 2.5))
    target = stop * rr

    edge = min(
        1.0,
        (signal.edge_score or signal.strength)
        + anti_rival
        + min(0.1, herd * 0.8)
        + (0.05 if 0.9 <= vol_ratio <= 1.6 else 0.0),
    )
    if edge < 0.6:
        return None

    reason = signal.reason
    if note:
        reason += " | meta: " + ", ".join(note)
    reason += f" | atr_stop={stop:.2%} vol_x={vol_ratio:.2f}"

    return replace(
        signal,
        stop_pct=stop,
        target_pct=target,
        edge_score=edge,
        reason=reason,
    )
