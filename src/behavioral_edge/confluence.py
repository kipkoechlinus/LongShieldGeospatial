"""
Confluence scorer — the gap between 'Claude vibes' and a real edge stack.

A raw detector hit is cheap. We only trade when microstructure + regime agree
with the behavioral thesis (CLV, herd intensity, range quality).
Raw detector strength is preserved; tradeability lives in edge_score.
"""

from __future__ import annotations

from dataclasses import replace

import pandas as pd

from behavioral_edge.features import (
    closing_location_value,
    herd_intensity,
    range_quality,
)
from behavioral_edge.regime import classify_regime, regime_allows
from behavioral_edge.signals import Signal, SignalKind


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def score_confluence(df: pd.DataFrame, signal: Signal) -> Signal:
    """Attach confluence + edge_score; veto via edge_score=0 when regime is wrong."""
    i = signal.bar_index
    clv = float(closing_location_value(df).iloc[i])
    herd = float(herd_intensity(df).iloc[i])
    rq = float(range_quality(df).iloc[i])
    state = classify_regime(df, i)

    if not regime_allows(signal.kind, state):
        return replace(
            signal,
            confluence=0.0,
            edge_score=0.0,
            reason=signal.reason + f" [REGIME VETO:{state.regime.value}]",
        )

    confirm = 0.0
    notes: list[str] = []

    if signal.kind == SignalKind.PANIC_CAPITULATION:
        # Climax itself is evidence; microstructure adds conviction
        confirm += 0.2
        notes.append("climax print")
        if clv >= 0.3:
            confirm += 0.2
            notes.append("CLV recovery")
        if herd >= 0.03:
            confirm += 0.25
            notes.append("herd climax")
        if rq >= 1.3:
            confirm += 0.15
            notes.append("wide emotional range")

    elif signal.kind == SignalKind.FOMO_EXHAUSTION:
        confirm += 0.2
        notes.append("vertical chase")
        if clv <= 0.7:
            confirm += 0.2
            notes.append("close off highs")
        if herd >= 0.03:
            confirm += 0.25
            notes.append("herd climax")
        if rq >= 1.2:
            confirm += 0.15
            notes.append("blow-off range")

    elif signal.kind == SignalKind.DISPOSITION_CONTINUATION:
        confirm += 0.25
        notes.append("trend dip")
        if herd <= 0.025:
            confirm += 0.2
            notes.append("dry herd")
        if clv >= 0.5:
            confirm += 0.2
            notes.append("buyers reclaim")
        if rq <= 1.15:
            confirm += 0.15
            notes.append("controlled range")

    elif signal.kind == SignalKind.ANCHOR_REJECTION:
        # Failed break IS the trap — base credit, then grade the close
        confirm += 0.35
        notes.append("failed break")
        if signal.side == "short" and clv <= 0.45:
            confirm += 0.25
            notes.append("reject high")
        elif signal.side == "long" and clv >= 0.55:
            confirm += 0.25
            notes.append("reject low")
        if rq >= 1.15:
            confirm += 0.15
            notes.append("trap range")

    rr = signal.target_pct / signal.stop_pct
    rr_boost = _clamp((rr - 1.0) / 2.0, 0.0, 0.15)
    confluence = _clamp(confirm)
    # Tradeability: respect raw behavioral read, require microstructure agreement
    edge = _clamp(0.5 * signal.strength + 0.4 * confluence + rr_boost)

    suffix = ""
    if notes:
        suffix = " | conf: " + ", ".join(notes)
    if state is not None:
        suffix += f" | regime={state.regime.value}"

    return replace(
        signal,
        confluence=confluence,
        edge_score=edge,
        reason=signal.reason + suffix,
    )
