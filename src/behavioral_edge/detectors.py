"""
Behavioral detectors.

Thesis: retail and many discretionary traders repeat the same mistakes.
We don't predict the future — we fade or ride the predictable emotional residue.

Thresholds are σ-adaptive: absolute % gates tuned on synthetic crash tapes
never fire on quiet SPY/QQQ sessions. Each bar's 20d return std sets the
local "emotion" scale so the same behavioral thesis travels across names.
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


def _daily_sigma(close: pd.Series, window: int = 20) -> pd.Series:
    """Rolling daily return std — local emotion scale."""
    return close.pct_change().rolling(window).std(ddof=0)


def _sigma_at(close: pd.Series, i: int, window: int = 20) -> float | None:
    if i < window:
        return None
    s = float(_daily_sigma(close, window).iloc[i])
    if s != s or s <= 1e-6:
        return None
    return s


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
    sigma = _sigma_at(close, i)
    if sigma is None:
        return None

    ret_1 = close.pct_change()
    vol_z = _zscore(volume, 20)
    rsi = _rsi(close, 14)

    # ~2σ dump, floored for quiet indices, capped so high-vol synthetic still fires
    dump_thr = -max(0.012, min(0.03, 2.0 * sigma))
    recent_low = close.iloc[max(0, i - 5) : i + 1].min()
    climax = vol_z.iloc[i] >= vol_z.iloc[max(0, i - 3) : i].max()
    if (
        ret_1.iloc[i] <= dump_thr
        and vol_z.iloc[i] >= 1.75
        and rsi.iloc[i] <= 30
        and close.iloc[i] <= recent_low * 1.002
        and climax
    ):
        strength = float(
            min(
                1.0,
                0.45
                + min(abs(ret_1.iloc[i]) / max(0.04, 4.0 * sigma), 0.35)
                + min(vol_z.iloc[i] / 6.0, 0.2),
            )
        )
        stop = max(0.015, min(0.04, 2.2 * sigma))
        return Signal(
            kind=SignalKind.PANIC_CAPITULATION,
            side="long",
            strength=strength,
            reason=(
                f"Panic dump: {ret_1.iloc[i]:.1%} day ({ret_1.iloc[i]/sigma:.1f}σ), "
                f"volume z={vol_z.iloc[i]:.1f}, RSI={rsi.iloc[i]:.0f}. "
                "Forced sellers are done; mean-reversion edge."
            ),
            stop_pct=stop,
            target_pct=stop * 2.0,
            bar_index=i,
        )
    return None


def detect_fomo_exhaustion(df: pd.DataFrame, i: int) -> Signal | None:
    """
    Exploit FOMO / herding at the end of a vertical move.

    Late buyers chase after large green streaks + euphoric volume.
    Blow-off tops reverse hard. We short exhaustion, not healthy trends.
    RSI absolute 75 rarely prints in grind-up regimes — use 68 + σ stretch.
    """
    if i < 20:
        return None

    close = df["close"]
    volume = df["volume"]
    sigma = _sigma_at(close, i)
    if sigma is None:
        return None

    ret_1 = close.pct_change()
    up_streak = 0
    j = i
    while j > 0 and close.iloc[j] > close.iloc[j - 1]:
        up_streak += 1
        j -= 1

    vol_z = _zscore(volume, 20)
    rsi = _rsi(close, 14)
    ret_5 = close.pct_change(5).iloc[i]
    day_thr = max(0.012, min(0.025, 1.5 * sigma))
    stretch_thr = max(0.035, min(0.08, 3.25 * sigma))

    if (
        up_streak >= 4
        and ret_1.iloc[i] >= day_thr
        and ret_5 >= stretch_thr
        and vol_z.iloc[i] >= 1.5
        and rsi.iloc[i] >= 68
    ):
        strength = float(
            min(
                1.0,
                0.4
                + min(up_streak / 10.0, 0.25)
                + min(ret_5 / max(0.10, 5.0 * sigma), 0.2)
                + min(vol_z.iloc[i] / 6.0, 0.15),
            )
        )
        stop = max(0.018, min(0.045, 2.5 * sigma))
        return Signal(
            kind=SignalKind.FOMO_EXHAUSTION,
            side="short",
            strength=strength,
            reason=(
                f"FOMO climax: {up_streak} up days, 5d={ret_5:.1%} "
                f"({ret_5 / sigma:.1f}σ), RSI={rsi.iloc[i]:.0f}, "
                f"vol z={vol_z.iloc[i]:.1f}. Late herd is long; distribution likely."
            ),
            stop_pct=stop,
            target_pct=stop * 2.0,
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
    sigma = _sigma_at(close, i)
    if sigma is None:
        return None

    ma20 = close.rolling(20).mean()
    ma50 = close.rolling(50).mean()
    pullback = (close.iloc[i] / close.iloc[i - 10 : i].max()) - 1.0
    vol_dry = volume.iloc[i] < volume.iloc[i - 20 : i].mean() * 0.95
    trend_up = ma20.iloc[i] > ma50.iloc[i] and close.iloc[i] > ma50.iloc[i]
    bounce = close.iloc[i] > close.iloc[i - 1]
    # Shallow dip in σ space — fixed -2%/-6% missed grind-up indices
    lo = -max(0.050, min(0.10, 5.0 * sigma))
    hi = -max(0.010, min(0.02, 1.35 * sigma))

    if trend_up and lo <= pullback <= hi and vol_dry and bounce:
        strength = float(min(1.0, 0.5 + abs(pullback) / max(0.08, 6.0 * sigma)))
        stop = max(0.010, min(0.035, 2.0 * sigma))
        return Signal(
            kind=SignalKind.DISPOSITION_CONTINUATION,
            side="long",
            strength=strength,
            reason=(
                f"Disposition dip: pullback {pullback:.1%} "
                f"({pullback / sigma:.1f}σ) under dry volume in uptrend. "
                "Weak hands took profits early; trend continuation favored."
            ),
            stop_pct=stop,
            target_pct=stop * 2.25,
            bar_index=i,
        )
    return None


def detect_anchor_rejection(df: pd.DataFrame, i: int) -> Signal | None:
    """
    Exploit anchoring to prior extremes.

    Only the clean traps: meaningful pierce, decisive reclaim, volume interest.
    Noisy wicks without volume are rival bait — we skip them.
    """
    if i < 30:
        return None

    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]
    sigma = _sigma_at(close, i)
    if sigma is None:
        return None

    prior_high = high.iloc[i - 20 : i].max()
    prior_low = low.iloc[i - 20 : i].min()
    vol_z = _zscore(volume, 20).iloc[i]
    span = high.iloc[i] - low.iloc[i]
    if span <= 0 or np.isnan(vol_z):
        return None
    clv = (close.iloc[i] - low.iloc[i]) / span

    pierce_thr = max(0.0012, min(0.003, 0.28 * sigma))
    # Failed breakout above prior high (bull trap)
    pierce_hi = (high.iloc[i] / prior_high) - 1.0
    broke_high = pierce_hi >= pierce_thr
    closed_back = close.iloc[i] < prior_high * 0.999
    # Failed breakdown below prior low (bear trap)
    pierce_lo = 1.0 - (low.iloc[i] / prior_low)
    broke_low = pierce_lo >= pierce_thr
    closed_back_up = close.iloc[i] > prior_low * 1.001

    stop = max(0.010, min(0.035, 2.0 * sigma))

    if broke_high and closed_back and clv <= 0.42 and vol_z >= 0.75:
        strength = float(
            min(1.0, 0.6 + min(pierce_hi / max(0.015, 2.0 * sigma), 0.25) + min(vol_z / 8, 0.15))
        )
        return Signal(
            kind=SignalKind.ANCHOR_REJECTION,
            side="short",
            strength=strength,
            reason=(
                f"Bull trap at anchor high {prior_high:.2f} "
                f"(pierce {pierce_hi:.1%} / {pierce_hi / sigma:.1f}σ, "
                f"CLV={clv:.2f}, vol z={vol_z:.1f}). "
                "Breakout chasers trapped; fade the failed break."
            ),
            stop_pct=stop,
            target_pct=stop * 2.0,
            bar_index=i,
        )
    if broke_low and closed_back_up and clv >= 0.58 and vol_z >= 0.75:
        strength = float(
            min(1.0, 0.6 + min(pierce_lo / max(0.015, 2.0 * sigma), 0.25) + min(vol_z / 8, 0.15))
        )
        return Signal(
            kind=SignalKind.ANCHOR_REJECTION,
            side="long",
            strength=strength,
            reason=(
                f"Bear trap at anchor low {prior_low:.2f} "
                f"(pierce {pierce_lo:.1%} / {pierce_lo / sigma:.1f}σ, "
                f"CLV={clv:.2f}, vol z={vol_z:.1f}). "
                "Panic sellers trapped; fade the failed breakdown."
            ),
            stop_pct=stop,
            target_pct=stop * 2.0,
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
