"""Orchestrates detectors + profiles + risk into actionable trade plans."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from behavioral_edge.detectors import scan_bar
from behavioral_edge.profiles import BALANCED, TradeProfile, apply_profile
from behavioral_edge.risk import PositionPlan, RiskConfig, size_position
from behavioral_edge.signals import Signal


@dataclass
class BehavioralEdgeEngine:
    risk: RiskConfig = field(default_factory=RiskConfig)
    profile: TradeProfile = field(default_factory=lambda: BALANCED)

    def __post_init__(self) -> None:
        self.risk = RiskConfig(
            account_equity=self.risk.account_equity,
            risk_per_trade=self.risk.risk_per_trade,
            max_open_risk=self.risk.max_open_risk,
            min_strength=self.profile.min_strength,
            min_edge=self.profile.min_edge,
            max_positions=self.risk.max_positions,
        )

    def signals_at(self, df: pd.DataFrame, i: int | None = None) -> list[Signal]:
        idx = len(df) - 1 if i is None else i
        raw = scan_bar(df, idx)
        out: list[Signal] = []
        for s in raw:
            shaped = apply_profile(s, self.profile)
            if shaped is not None:
                out.append(shaped)
        out.sort(key=lambda s: (s.edge_score or s.strength), reverse=True)
        return out

    def plan_trade(
        self,
        df: pd.DataFrame,
        i: int | None = None,
        *,
        open_risk_dollars: float = 0.0,
        open_positions: int = 0,
        signal: Signal | None = None,
    ) -> PositionPlan | None:
        # If caller passes a signal, trust it (already profile-shaped by signals_at).
        if signal is None:
            signals = self.signals_at(df, i)
            if not signals:
                return None
            sig = signals[0]
        else:
            sig = signal
        idx = len(df) - 1 if i is None else i
        price = float(df["close"].iloc[idx])
        return size_position(
            sig,
            price,
            self.risk,
            open_risk_dollars=open_risk_dollars,
            open_positions=open_positions,
        )

    def scan_history(self, df: pd.DataFrame) -> list[Signal]:
        found: list[Signal] = []
        for i in range(len(df)):
            found.extend(self.signals_at(df, i))
        return found
