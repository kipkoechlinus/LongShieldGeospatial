"""Mechanical risk: anti-human + vol-targeted sizing."""

from __future__ import annotations

from dataclasses import dataclass

from behavioral_edge.signals import Signal


@dataclass(frozen=True)
class RiskConfig:
    account_equity: float = 100_000.0
    risk_per_trade: float = 0.005  # 0.5% account risk
    max_open_risk: float = 0.015  # 1.5% total open risk
    min_strength: float = 0.55
    min_edge: float = 0.55
    max_positions: int = 3
    # Annualized vol target; None disables vol targeting
    target_vol: float | None = 0.12


@dataclass(frozen=True)
class PositionPlan:
    side: str
    notional: float
    shares: float
    stop_pct: float
    target_pct: float
    risk_dollars: float
    signal: Signal


def size_position(
    signal: Signal,
    price: float,
    config: RiskConfig,
    open_risk_dollars: float = 0.0,
    open_positions: int = 0,
    realized_vol: float | None = None,
) -> PositionPlan | None:
    """
    Gate on edge_score, size from stop, optionally scale to target vol.
    Rivals use fixed fractional only — we adapt to the weather.
    """
    if price <= 0:
        raise ValueError("price must be positive")
    edge = signal.edge_score or signal.strength
    if signal.strength < config.min_strength or edge < config.min_edge:
        return None
    if open_positions >= config.max_positions:
        return None

    risk_budget = config.account_equity * config.risk_per_trade
    remaining = config.account_equity * config.max_open_risk - open_risk_dollars
    if remaining <= 0:
        return None

    risk_dollars = min(risk_budget, remaining)
    # Edge scales size; elite prints get a mild pyramid, hard-capped
    edge_mult = 0.80 + 0.45 * edge
    if edge >= 0.95:
        edge_mult *= 1.20
    risk_dollars *= edge_mult
    risk_dollars = min(risk_dollars, remaining, risk_budget * 1.35)

    # Vol targeting: shrink when realized vol >> target (rivals keep full size and die)
    if (
        config.target_vol is not None
        and realized_vol is not None
        and realized_vol > 0
    ):
        vol_scale = min(1.25, max(0.35, config.target_vol / realized_vol))
        risk_dollars *= vol_scale

    stop_distance = price * signal.stop_pct
    shares = risk_dollars / stop_distance
    notional = shares * price
    return PositionPlan(
        side=signal.side,
        notional=notional,
        shares=shares,
        stop_pct=signal.stop_pct,
        target_pct=signal.target_pct,
        risk_dollars=risk_dollars,
        signal=signal,
    )
