"""
Behavioral detectors.

Thesis: retail and many discretionary traders repeat the same mistakes.
We don't predict the future — we fade or ride the predictable emotional residue.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from behavioral_edge.signals import Signal, SignalKind


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _zscore(series: pd.Series, window: int) -> pd.Series:
    mean = series.rolling(window).mean()
    std = series.rolling(window).std(ddof=0)
    return (series - mean) / std.replace(0, np.nan)


def detect_panic_capitulation(df: pd.DataFrame, i: int) -> Signal | None:
    """
    Exploit loss aversion + forced liquidation.

    Humans hold losers until pain becomes unbearable, then dump together.
    Capitulation = sharp down move + volume climax + washed-out RSI.
    We fade the panic once selling pressure peaks (not mid-waterfall).
    """
    if i < 20:
        return None

    close = df["close"]
    volume = df["volume"]
    ret_1 = close.pct_change()
    vol_z = _zscore(volume, 20)
    rsi = _rsi(close, 14)

    recent_low = close.iloc[max(0, i - 5) : i + 1].min()
    # Only fade the climax print — not every down day in the waterfall
    climax = vol_z.iloc[i] >= vol_z.iloc[max(0, i - 3) : i].max()
    if (
        ret_1.iloc[i] <= -0.03
        and vol_z.iloc[i] >= 2.0
        and rsi.iloc[i] <= 25
        and close.iloc[i] <= recent_low * 1.002
        and climax
    ):
        # Next bar entry bias: long the washout
        strength = float(
            min(
                1.0,
                0.45
                + min(abs(ret_1.iloc[i]) / 0.08, 0.35)
                + min(vol_z.iloc[i] / 6.0, 0.2),
            )
        )
        return Signal(
            kind=SignalKind.PANIC_CAPITULATION,
            side="long",
            strength=strength,
            reason=(
                f"Panic dump: {ret_1.iloc[i]:.1%} day, volume z={vol_z.iloc[i]:.1f}, "
                f"RSI={rsi.iloc[i]:.0f}. Forced sellers are done; mean-reversion edge."
            ),
            stop_pct=0.025,
            target_pct=0.05,
            bar_index=i,
        )
    return None


def detect_fomo_exhaustion(df: pd.DataFrame, i: int) -> Signal | None:
    """
    Exploit FOMO / herding at the end of a vertical move.

    Late buyers chase after large green streaks + euphoric volume.
    Blow-off tops reverse hard. We short exhaustion, not healthy trends.
    """
    if i < 20:
        return None

    close = df["close"]
    volume = df["volume"]
    ret_1 = close.pct_change()
    up_streak = 0
    j = i
    while j > 0 and close.iloc[j] > close.iloc[j - 1]:
        up_streak += 1
        j -= 1

    vol_z = _zscore(volume, 20)
    rsi = _rsi(close, 14)
    ret_5 = close.pct_change(5).iloc[i]

    if (
        up_streak >= 4
        and ret_1.iloc[i] >= 0.025
        and ret_5 >= 0.08
        and vol_z.iloc[i] >= 2.0
        and rsi.iloc[i] >= 75
    ):
        strength = float(
            min(
                1.0,
                0.4
                + min(up_streak / 10.0, 0.25)
                + min(ret_5 / 0.15, 0.2)
                + min(vol_z.iloc[i] / 6.0, 0.15),
            )
        )
        return Signal(
            kind=SignalKind.FOMO_EXHAUSTION,
            side="short",
            strength=strength,
            reason=(
                f"FOMO climax: {up_streak} up days, 5d={ret_5:.1%}, "
                f"RSI={rsi.iloc[i]:.0f}, vol z={vol_z.iloc[i]:.1f}. "
                "Late herd is long; distribution likely."
            ),
            stop_pct=0.03,
            target_pct=0.06,
            bar_index=i,
        )
    return None


def detect_disposition_continuation(df: pd.DataFrame, i: int) -> Signal | None:
    """
    Exploit the disposition effect in an established trend.

    Traders sell winners too early (lock in gains) and create shallow pullbacks.
    Institutions keep buying. We buy the dip in a confirmed uptrend —
    harvesting the premature profit-taking of weak hands.
    """
    if i < 50:
        return None

    close = df["close"]
    volume = df["volume"]
    ma20 = close.rolling(20).mean()
    ma50 = close.rolling(50).mean()
    pullback = (close.iloc[i] / close.iloc[i - 10 : i].max()) - 1.0
    vol_dry = volume.iloc[i] < volume.iloc[i - 20 : i].mean() * 0.85
    trend_up = ma20.iloc[i] > ma50.iloc[i] and close.iloc[i] > ma50.iloc[i]
    bounce = close.iloc[i] > close.iloc[i - 1]

    if trend_up and -0.06 <= pullback <= -0.02 and vol_dry and bounce:
        strength = float(min(1.0, 0.5 + abs(pullback) / 0.12))
        return Signal(
            kind=SignalKind.DISPOSITION_CONTINUATION,
            side="long",
            strength=strength,
            reason=(
                f"Disposition dip: pullback {pullback:.1%} under dry volume in uptrend. "
                "Weak hands took profits early; trend continuation favored."
            ),
            stop_pct=0.02,
            target_pct=0.045,
            bar_index=i,
        )
    return None


def detect_anchor_rejection(df: pd.DataFrame, i: int) -> Signal | None:
    """
    Exploit anchoring to prior extremes and round psychological levels.

    Humans treat recent highs/lows and round numbers as 'fair value'.
    Failed breaks of those anchors often reverse sharply as trapped traders unwind.
    """
    if i < 30:
        return None

    close = df["close"]
    high = df["high"]
    low = df["low"]
    prior_high = high.iloc[i - 20 : i].max()
    prior_low = low.iloc[i - 20 : i].min()

    # Failed breakout above prior high (bull trap)
    broke_high = high.iloc[i] > prior_high * 1.002
    closed_back = close.iloc[i] < prior_high
    # Failed breakdown below prior low (bear trap)
    broke_low = low.iloc[i] < prior_low * 0.998
    closed_back_up = close.iloc[i] > prior_low

    if broke_high and closed_back:
        return Signal(
            kind=SignalKind.ANCHOR_REJECTION,
            side="short",
            strength=0.65,
            reason=(
                f"Bull trap at anchor high {prior_high:.2f}. "
                "Breakout chasers trapped; fade the failed break."
            ),
            stop_pct=0.02,
            target_pct=0.04,
            bar_index=i,
        )
    if broke_low and closed_back_up:
        return Signal(
            kind=SignalKind.ANCHOR_REJECTION,
            side="long",
            strength=0.65,
            reason=(
                f"Bear trap at anchor low {prior_low:.2f}. "
                "Panic sellers trapped; fade the failed breakdown."
            ),
            stop_pct=0.02,
            target_pct=0.04,
            bar_index=i,
        )
    return None


DETECTORS = (
    detect_panic_capitulation,
    detect_fomo_exhaustion,
    detect_disposition_continuation,
    detect_anchor_rejection,
)


def scan_bar(df: pd.DataFrame, i: int, *, apply_confluence: bool = True) -> list[Signal]:
    """Run detectors, optionally re-score with confluence + regime gate."""
    from behavioral_edge.confluence import score_confluence

    out: list[Signal] = []
    for detector in DETECTORS:
        sig = detector(df, i)
        if sig is None:
            continue
        if apply_confluence:
            sig = score_confluence(df, sig)
        sig.validate()
        out.append(sig)
    # Rank by edge_score when present, else raw strength
    out.sort(key=lambda s: (s.edge_score or s.strength), reverse=True)
    return out
