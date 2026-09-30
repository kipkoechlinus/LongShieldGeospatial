"""Regime gate — don't run mean-reversion logic in the wrong weather."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import pandas as pd

from behavioral_edge.features import realized_vol, trend_slope
from behavioral_edge.signals import SignalKind


class Regime(str, Enum):
    TREND_BULL = "trend_bull"
    TREND_BEAR = "trend_bear"
    CHAOS = "chaos"  # elevated vol, direction unclear
    MEAN_REVERT = "mean_revert"  # calm / range chop


@dataclass(frozen=True)
class RegimeState:
    regime: Regime
    vol: float
    slope: float


def classify_regime(df: pd.DataFrame, i: int) -> RegimeState | None:
    if i < 30:
        return None
    close = df["close"]
    vol = float(realized_vol(close, 20).iloc[i])
    slope = float(trend_slope(close, 20).iloc[i])
    vol_med = float(realized_vol(close, 20).iloc[max(0, i - 60) : i + 1].median())

    if vol > vol_med * 1.35 and abs(slope) < 0.03:
        regime = Regime.CHAOS
    elif slope >= 0.02:
        regime = Regime.TREND_BULL
    elif slope <= -0.02:
        regime = Regime.TREND_BEAR
    else:
        regime = Regime.MEAN_REVERT
    return RegimeState(regime=regime, vol=vol, slope=slope)


# Which biases are allowed to fire in which weather
_ALLOWED: dict[Regime, set[SignalKind]] = {
    Regime.TREND_BULL: {
        SignalKind.DISPOSITION_CONTINUATION,
        SignalKind.FOMO_EXHAUSTION,  # only exhaustion shorts still OK
        SignalKind.ANCHOR_REJECTION,
    },
    Regime.TREND_BEAR: {
        SignalKind.PANIC_CAPITULATION,
        SignalKind.ANCHOR_REJECTION,
        SignalKind.FOMO_EXHAUSTION,
    },
    Regime.CHAOS: {
        SignalKind.PANIC_CAPITULATION,
        SignalKind.FOMO_EXHAUSTION,
        SignalKind.ANCHOR_REJECTION,
    },
    Regime.MEAN_REVERT: {
        SignalKind.ANCHOR_REJECTION,
        SignalKind.DISPOSITION_CONTINUATION,
        SignalKind.PANIC_CAPITULATION,
    },
}


def regime_allows(kind: SignalKind, state: RegimeState | None) -> bool:
    if state is None:
        return True
    return kind in _ALLOWED[state.regime]
