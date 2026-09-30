"""Orchestrates detectors + profiles + meta-labeler + conflict veto + risk."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from behavioral_edge.detectors import scan_bar
from behavioral_edge.meta import meta_label
from behavioral_edge.profiles import HIGH_WIN, TradeProfile, apply_profile
from behavioral_edge.risk import PositionPlan, RiskConfig, size_position
from behavioral_edge.signals import Signal


@dataclass
class BehavioralEdgeEngine:
    risk: RiskConfig = field(default_factory=RiskConfig)
    profile: TradeProfile = field(default_factory=lambda: HIGH_WIN)
    use_meta: bool = True

    def __post_init__(self) -> None:
        p = self.profile
        target_vol = self.risk.target_vol
        if p.disable_vol_targeting:
            target_vol = None
        elif p.target_vol is not None:
            target_vol = p.target_vol
        self.risk = RiskConfig(
            account_equity=self.risk.account_equity,
            risk_per_trade=(
                p.risk_per_trade
                if p.risk_per_trade is not None
                else self.risk.risk_per_trade
            ),
            max_open_risk=(
                p.max_open_risk
                if p.max_open_risk is not None
                else self.risk.max_open_risk
            ),
            min_strength=p.min_strength,
            min_edge=p.min_edge,
            max_positions=self.risk.max_positions,
            target_vol=target_vol,
        )

    def signals_at(self, df: pd.DataFrame, i: int | None = None) -> list[Signal]:
        idx = len(df) - 1 if i is None else i
        raw = scan_bar(df, idx)
        out: list[Signal] = []
        for s in raw:
            shaped = apply_profile(s, self.profile)
            if shaped is None:
                continue
            if self.use_meta:
                shaped = meta_label(
                    df,
                    shaped,
                    strict_anchors=self.profile.name not in {"hustle", "crypto"},
                    min_edge=0.55 if self.profile.name in {"hustle", "crypto"} else 0.62,
                )
                if shaped is None:
                    continue
            out.append(shaped)
        out.sort(key=lambda s: (s.edge_score or s.strength), reverse=True)

        # Conflict veto: long+short both firing with close edges → sit out
        longs = [s for s in out if s.side == "long"]
        shorts = [s for s in out if s.side == "short"]
        if longs and shorts:
            best_l = longs[0].edge_score or longs[0].strength
            best_s = shorts[0].edge_score or shorts[0].strength
            if abs(best_l - best_s) < 0.12:
                return []
            # Keep only the clearly stronger side
            out = longs if best_l > best_s else shorts
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
        if signal is None:
            signals = self.signals_at(df, i)
            if not signals:
                return None
            sig = signals[0]
        else:
            sig = signal
        idx = len(df) - 1 if i is None else i
        price = float(df["close"].iloc[idx])
        from behavioral_edge.features import realized_vol

        rv = float(realized_vol(df["close"], 20).iloc[idx])
        return size_position(
            sig,
            price,
            self.risk,
            open_risk_dollars=open_risk_dollars,
            open_positions=open_positions,
            realized_vol=rv if rv == rv else None,
        )

    def scan_history(self, df: pd.DataFrame) -> list[Signal]:
        found: list[Signal] = []
        for i in range(len(df)):
            found.extend(self.signals_at(df, i))
        return found
