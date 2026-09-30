"""Orchestrates detectors + risk into actionable trade plans."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from behavioral_edge.detectors import scan_bar
from behavioral_edge.risk import PositionPlan, RiskConfig, size_position
from behavioral_edge.signals import Signal


@dataclass
class BehavioralEdgeEngine:
    risk: RiskConfig = RiskConfig()

    def signals_at(self, df: pd.DataFrame, i: int | None = None) -> list[Signal]:
        idx = len(df) - 1 if i is None else i
        return scan_bar(df, idx)

    def plan_trade(
        self,
        df: pd.DataFrame,
        i: int | None = None,
        *,
        open_risk_dollars: float = 0.0,
        open_positions: int = 0,
    ) -> PositionPlan | None:
        signals = self.signals_at(df, i)
        if not signals:
            return None
        idx = len(df) - 1 if i is None else i
        price = float(df["close"].iloc[idx])
        # Take the strongest behavioral read only — no kitchen-sink stacking
        return size_position(
            signals[0],
            price,
            self.risk,
            open_risk_dollars=open_risk_dollars,
            open_positions=open_positions,
        )

    def scan_history(self, df: pd.DataFrame) -> list[Signal]:
        found: list[Signal] = []
        for i in range(len(df)):
            found.extend(scan_bar(df, i))
        return found
