"""Tiny event-driven backtest for behavioral signals."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from behavioral_edge.engine import BehavioralEdgeEngine
from behavioral_edge.risk import RiskConfig
from behavioral_edge.signals import Signal


@dataclass
class Trade:
    entry_time: object
    exit_time: object | None
    side: str
    entry: float
    exit: float | None
    shares: float
    pnl: float | None
    signal: Signal
    exit_reason: str | None = None


@dataclass
class BacktestResult:
    trades: list[Trade] = field(default_factory=list)
    equity_curve: list[float] = field(default_factory=list)

    @property
    def total_pnl(self) -> float:
        return sum(t.pnl or 0.0 for t in self.trades)

    @property
    def win_rate(self) -> float:
        closed = [t for t in self.trades if t.pnl is not None]
        if not closed:
            return 0.0
        wins = sum(1 for t in closed if t.pnl > 0)
        return wins / len(closed)


def run_backtest(
    df: pd.DataFrame,
    *,
    risk: RiskConfig | None = None,
    engine: BehavioralEdgeEngine | None = None,
) -> BacktestResult:
    """
    Enter next open after signal; exit on stop, target, or time stop (8 bars).
    One position at a time — clarity over complexity.
    """
    eng = engine or BehavioralEdgeEngine(risk=risk or RiskConfig())
    result = BacktestResult()
    equity = eng.risk.account_equity
    result.equity_curve.append(equity)

    open_trade: Trade | None = None
    pending_signal: Signal | None = None
    entry_bar: int | None = None

    for i in range(len(df)):
        # Fill pending entry at this open
        if pending_signal is not None and open_trade is None:
            px = float(df["open"].iloc[i])
            plan = eng.plan_trade(
                df,
                pending_signal.bar_index,
                open_positions=0,
            )
            if plan is not None:
                open_trade = Trade(
                    entry_time=df.index[i],
                    exit_time=None,
                    side=plan.side,
                    entry=px,
                    exit=None,
                    shares=plan.shares,
                    pnl=None,
                    signal=pending_signal,
                )
                entry_bar = i
            pending_signal = None

        # Manage open trade
        if open_trade is not None and entry_bar is not None and i > entry_bar:
            high = float(df["high"].iloc[i])
            low = float(df["low"].iloc[i])
            close = float(df["close"].iloc[i])
            stop = (
                open_trade.entry * (1 - open_trade.signal.stop_pct)
                if open_trade.side == "long"
                else open_trade.entry * (1 + open_trade.signal.stop_pct)
            )
            target = (
                open_trade.entry * (1 + open_trade.signal.target_pct)
                if open_trade.side == "long"
                else open_trade.entry * (1 - open_trade.signal.target_pct)
            )
            exit_px = None
            reason = None
            if open_trade.side == "long":
                if low <= stop:
                    exit_px, reason = stop, "stop"
                elif high >= target:
                    exit_px, reason = target, "target"
            else:
                if high >= stop:
                    exit_px, reason = stop, "stop"
                elif low <= target:
                    exit_px, reason = target, "target"
            if exit_px is None and i - entry_bar >= 8:
                exit_px, reason = close, "time"

            if exit_px is not None:
                signed = 1 if open_trade.side == "long" else -1
                pnl = signed * (exit_px - open_trade.entry) * open_trade.shares
                open_trade.exit = exit_px
                open_trade.exit_time = df.index[i]
                open_trade.pnl = pnl
                open_trade.exit_reason = reason
                equity += pnl
                result.trades.append(open_trade)
                open_trade = None
                entry_bar = None

        result.equity_curve.append(equity)

        # New signal only when flat
        if open_trade is None and pending_signal is None and i < len(df) - 1:
            sigs = eng.signals_at(df, i)
            if sigs and sigs[0].strength >= eng.risk.min_strength:
                pending_signal = sigs[0]

    return result
