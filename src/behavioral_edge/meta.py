"""
Meta-labeler + anti-rival edge (hardened).

Primary detectors find human bias. Meta decides whether the trade is
worth taking given volatility, rival crowding, and bar quality.
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd

from behavioral_edge.features import closing_location_value, herd_intensity, realized_vol
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
    """Approximate what SMA/RSI (Grok-class) rivals want."""
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


def _rival_macd_side(df: pd.DataFrame, i: int) -> str | None:
    """Approximate what MACD+BB (Muse-class) rivals want."""
    if i < 26:
        return None
    close = df["close"]
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    sig = macd.ewm(span=9, adjust=False).mean()
    mid = close.rolling(20).mean()
    std = close.rolling(20).std(ddof=0)
    if any(np.isnan(x.iloc[i]) for x in (macd, sig, mid, std)):
        return None
    upper = mid.iloc[i] + 2 * std.iloc[i]
    lower = mid.iloc[i] - 2 * std.iloc[i]
    cross_up = macd.iloc[i - 1] <= sig.iloc[i - 1] and macd.iloc[i] > sig.iloc[i]
    cross_dn = macd.iloc[i - 1] >= sig.iloc[i - 1] and macd.iloc[i] < sig.iloc[i]
    if cross_up and close.iloc[i] <= lower * 1.02:
        return "long"
    if cross_dn and close.iloc[i] >= upper * 0.98:
        return "short"
    return None


def meta_label(
    df: pd.DataFrame,
    signal: Signal,
    *,
    strict_anchors: bool = True,
    min_edge: float = 0.62,
) -> Signal | None:
    """
    Upgrade or veto a signal.

    Boost when we fade crowded rival momentum (they are the liquidity).
    Veto dead/insane vol and poor closing location for the thesis.
    ATR-normalize stops/targets.
    """
    i = signal.bar_index
    if i < 30:
        return None

    vol = float(realized_vol(df["close"], 20).iloc[i])
    vol_med = float(
        realized_vol(df["close"], 20).iloc[max(0, i - 60) : i + 1].median()
    )
    if vol_med <= 0 or np.isnan(vol) or np.isnan(vol_med):
        return None

    vol_ratio = vol / vol_med
    # Climax biases (panic/FOMO) naturally print extreme vol — allow wider band
    climax = signal.kind in {
        SignalKind.PANIC_CAPITULATION,
        SignalKind.FOMO_EXHAUSTION,
    }
    vol_hi = 4.5 if climax else 2.6
    vol_lo = 0.50 if climax else 0.55
    if vol_ratio < vol_lo or vol_ratio > vol_hi:
        return None

    herd = float(herd_intensity(df).iloc[i])
    clv = float(closing_location_value(df).iloc[i])
    rival_m = _rival_momentum_side(df, i)
    rival_macd = _rival_macd_side(df, i)
    anti_rival = 0.0
    note: list[str] = []

    rivals_long = {rival_m, rival_macd} & {"long"}
    rivals_short = {rival_m, rival_macd} & {"short"}

    if signal.side == "short" and rivals_long:
        anti_rival += 0.12 + 0.05 * (len(rivals_long) - 1)
        note.append("fade-crowded-longs")
    if signal.side == "long" and rivals_short:
        anti_rival += 0.12 + 0.05 * (len(rivals_short) - 1)
        note.append("fade-crowded-shorts")

    if signal.kind == SignalKind.DISPOSITION_CONTINUATION and rival_m == signal.side:
        anti_rival += 0.08
        note.append("trend-align")

    # CLV veto only for trap fades — climax bars are supposed to close at extremes
    if not climax:
        if signal.side == "long" and clv < 0.25:
            return None
        if signal.side == "short" and clv > 0.75:
            return None

    atrp = _atr_pct(df, i)
    stop = max(0.008, min(0.045, atrp * 1.15))
    rr = signal.target_pct / signal.stop_pct if signal.stop_pct > 0 else 1.5
    rr = max(0.5, min(rr, 2.2))
    target = stop * rr

    edge = min(
        1.0,
        (signal.edge_score or signal.strength)
        + anti_rival
        + min(0.12, herd * 0.9)
        + (0.05 if 0.85 <= vol_ratio <= 1.7 or climax else 0.0),
    )
    if edge < min_edge:
        return None

    # Anchors without rival crowding are often noise — demand higher conviction
    # (hustle relaxes this for frequency / $/day)
    if (
        strict_anchors
        and signal.kind == SignalKind.ANCHOR_REJECTION
        and anti_rival <= 0
        and edge < 0.88
    ):
        return None

    reason = signal.reason
    if note:
        reason += " | meta: " + ", ".join(note)
    reason += f" | atr_stop={stop:.2%} vol_x={vol_ratio:.2f} clv={clv:.2f}"

    return replace(
        signal,
        stop_pct=stop,
        target_pct=target,
        edge_score=edge,
        reason=reason,
    )
