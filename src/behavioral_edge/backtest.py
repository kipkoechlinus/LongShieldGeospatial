"""Event-driven backtest + naive baseline for head-to-head proof."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from behavioral_edge.engine import BehavioralEdgeEngine
from behavioral_edge.profiles import HIGH_WIN, TradeProfile
from behavioral_edge.risk import RiskConfig
from behavioral_edge.signals import Signal, SignalKind


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
    label: str = "behavioral_edge"

    @property
    def total_pnl(self) -> float:
        return sum(t.pnl or 0.0 for t in self.trades)

    @property
    def win_rate(self) -> float:
        """Wins / decided trades. Breakeven scratches are excluded (not losses)."""
        decided = [
            t for t in self.trades if t.pnl is not None and abs(t.pnl) > 1e-9
        ]
        if not decided:
            # All scratches → treat as perfect defense
            return 1.0 if self.trades else 0.0
        return sum(1 for t in decided if (t.pnl or 0) > 0) / len(decided)

    @property
    def scratch_count(self) -> int:
        return sum(1 for t in self.trades if t.pnl is not None and abs(t.pnl) <= 1e-9)

    @property
    def expectancy(self) -> float:
        closed = [t.pnl for t in self.trades if t.pnl is not None]
        return float(np.mean(closed)) if closed else 0.0

    @property
    def profit_factor(self) -> float:
        wins = sum(t.pnl for t in self.trades if t.pnl and t.pnl > 0)
        losses = sum(-t.pnl for t in self.trades if t.pnl and t.pnl < 0)
        if losses <= 0:
            return float("inf") if wins > 0 else 0.0
        return wins / losses

    @property
    def max_drawdown(self) -> float:
        if not self.equity_curve:
            return 0.0
        eq = np.array(self.equity_curve, dtype=float)
        peak = np.maximum.accumulate(eq)
        dd = (eq - peak) / peak
        return float(dd.min())

    @property
    def sharpe_like(self) -> float:
        pnls = np.array([t.pnl for t in self.trades if t.pnl is not None], dtype=float)
        if len(pnls) < 2:
            return 0.0
        std = pnls.std(ddof=0)
        return float(pnls.mean() / std) if std > 0 else 0.0

    def attribution(self) -> dict[str, dict[str, float]]:
        buckets: dict[str, list[float]] = defaultdict(list)
        for t in self.trades:
            if t.pnl is not None:
                buckets[t.signal.kind.value].append(t.pnl)
        out: dict[str, dict[str, float]] = {}
        for kind, pnls in buckets.items():
            arr = np.array(pnls, dtype=float)
            out[kind] = {
                "trades": float(len(arr)),
                "pnl": float(arr.sum()),
                "win_rate": float((arr > 0).mean()),
                "expectancy": float(arr.mean()),
            }
        return out

    def summary(self) -> dict[str, float | int | str]:
        return {
            "label": self.label,
            "trades": len(self.trades),
            "win_rate": round(self.win_rate, 3),
            "scratches": self.scratch_count,
            "total_pnl": round(self.total_pnl, 2),
            "expectancy": round(self.expectancy, 2),
            "profit_factor": round(self.profit_factor, 3)
            if self.profit_factor != float("inf")
            else "inf",
            "max_drawdown": round(self.max_drawdown, 4),
            "sharpe_like": round(self.sharpe_like, 3),
            "final_equity": round(self.equity_curve[-1], 2) if self.equity_curve else 0.0,
        }


def _confirm_entry(df: pd.DataFrame, signal: Signal, i: int) -> bool:
    o = float(df["open"].iloc[i])
    c = float(df["close"].iloc[i])
    ret = (c - o) / o if o else 0.0
    if signal.side == "long" and ret <= -0.006:
        return False
    if signal.side == "short" and ret >= 0.006:
        return False
    return True


def run_backtest(
    df: pd.DataFrame,
    *,
    risk: RiskConfig | None = None,
    engine: BehavioralEdgeEngine | None = None,
    profile: TradeProfile | None = None,
    require_confirmation: bool | None = None,
    label: str | None = None,
) -> BacktestResult:
    """
    Signal on bar i → soft confirmation on bar i+1 → enter bar i+2 open.
    Exits: stop, target/scalp, breakeven trail, or profile time stop.
    """
    if engine is None:
        eng = BehavioralEdgeEngine(
            risk=risk or RiskConfig(),
            profile=profile or HIGH_WIN,
        )
    else:
        eng = engine
    prof = eng.profile
    confirm = (
        prof.require_confirmation
        if require_confirmation is None
        else require_confirmation
    )
    result = BacktestResult(label=label or f"behavioral_edge:{prof.name}")
    equity = eng.risk.account_equity
    result.equity_curve.append(equity)

    open_trade: Trade | None = None
    pending_signal: Signal | None = None
    pending_from: int | None = None
    entry_bar: int | None = None

    for i in range(len(df)):
        if pending_signal is not None and open_trade is None and pending_from is not None:
            if confirm:
                if i == pending_from + 1:
                    if not _confirm_entry(df, pending_signal, i):
                        pending_signal = None
                        pending_from = None
                elif i == pending_from + 2:
                    px = float(df["open"].iloc[i])
                    plan = eng.plan_trade(
                        df,
                        pending_signal.bar_index,
                        open_positions=0,
                        signal=pending_signal,
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
                    pending_from = None
            else:
                if i == pending_from + 1:
                    px = float(df["open"].iloc[i])
                    plan = eng.plan_trade(
                        df,
                        pending_signal.bar_index,
                        open_positions=0,
                        signal=pending_signal,
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
                    pending_from = None

        if open_trade is not None and entry_bar is not None and i > entry_bar:
            high = float(df["high"].iloc[i])
            low = float(df["low"].iloc[i])
            close = float(df["close"].iloc[i])
            stop_dist = open_trade.signal.stop_pct
            stop = (
                open_trade.entry * (1 - stop_dist)
                if open_trade.side == "long"
                else open_trade.entry * (1 + stop_dist)
            )
            target = (
                open_trade.entry * (1 + open_trade.signal.target_pct)
                if open_trade.side == "long"
                else open_trade.entry * (1 - open_trade.signal.target_pct)
            )
            # Optional scalp level (high_win banks early)
            scalp = None
            if prof.scalp_r is not None:
                scalp_pct = stop_dist * prof.scalp_r
                scalp = (
                    open_trade.entry * (1 + scalp_pct)
                    if open_trade.side == "long"
                    else open_trade.entry * (1 - scalp_pct)
                )

            signed_fav = (
                (high - open_trade.entry) / open_trade.entry
                if open_trade.side == "long"
                else (open_trade.entry - low) / open_trade.entry
            )
            if signed_fav >= stop_dist * prof.trail_after_r:
                if open_trade.side == "long":
                    stop = max(stop, open_trade.entry)
                else:
                    stop = min(stop, open_trade.entry)

            exit_px = None
            reason = None
            if open_trade.side == "long":
                if low <= stop:
                    exit_px, reason = stop, "stop"
                elif scalp is not None and high >= scalp:
                    exit_px, reason = scalp, "scalp"
                elif high >= target:
                    exit_px, reason = target, "target"
            else:
                if high >= stop:
                    exit_px, reason = stop, "stop"
                elif scalp is not None and low <= scalp:
                    exit_px, reason = scalp, "scalp"
                elif low <= target:
                    exit_px, reason = target, "target"
            if exit_px is None and i - entry_bar >= prof.time_stop_bars:
                signed = 1 if open_trade.side == "long" else -1
                unreal = signed * (close - open_trade.entry) / open_trade.entry
                if prof.time_stop_winners_only:
                    if unreal > 0:
                        exit_px, reason = close, "time"
                    # else hold for stop/target — don't donate a loser to the clock
                else:
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

        lookahead = 2 if confirm else 1
        if (
            open_trade is None
            and pending_signal is None
            and i < len(df) - lookahead
        ):
            sigs = eng.signals_at(df, i)
            if sigs:
                pending_signal = sigs[0]
                pending_from = i

    return result


def run_naive_rsi_baseline(
    df: pd.DataFrame,
    *,
    equity: float = 100_000.0,
    risk_frac: float = 0.005,
) -> BacktestResult:
    """Generic LLM starter pack: fade RSI extremes, fixed 2% stop / 4% target."""
    close = df["close"]
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))

    result = BacktestResult(label="naive_rsi_fade")
    cash = equity
    result.equity_curve.append(cash)
    open_trade: Trade | None = None
    entry_bar: int | None = None
    pending_side: str | None = None

    for i in range(len(df)):
        if pending_side and open_trade is None:
            px = float(df["open"].iloc[i])
            stop_pct = 0.02
            risk_dollars = equity * risk_frac
            shares = risk_dollars / (px * stop_pct)
            open_trade = Trade(
                entry_time=df.index[i],
                exit_time=None,
                side=pending_side,
                entry=px,
                exit=None,
                shares=shares,
                pnl=None,
                signal=Signal(
                    kind=SignalKind.ANCHOR_REJECTION,
                    side=pending_side,
                    strength=0.5,
                    reason="naive RSI fade",
                    stop_pct=stop_pct,
                    target_pct=0.04,
                    bar_index=i - 1,
                    edge_score=0.5,
                ),
            )
            entry_bar = i
            pending_side = None

        if open_trade is not None and entry_bar is not None and i > entry_bar:
            high = float(df["high"].iloc[i])
            low = float(df["low"].iloc[i])
            c = float(df["close"].iloc[i])
            stop = (
                open_trade.entry * 0.98
                if open_trade.side == "long"
                else open_trade.entry * 1.02
            )
            target = (
                open_trade.entry * 1.04
                if open_trade.side == "long"
                else open_trade.entry * 0.96
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
                exit_px, reason = c, "time"
            if exit_px is not None:
                signed = 1 if open_trade.side == "long" else -1
                pnl = signed * (exit_px - open_trade.entry) * open_trade.shares
                open_trade.exit = exit_px
                open_trade.exit_time = df.index[i]
                open_trade.pnl = pnl
                open_trade.exit_reason = reason
                cash += pnl
                result.trades.append(open_trade)
                open_trade = None
                entry_bar = None

        result.equity_curve.append(cash)

        if open_trade is None and pending_side is None and i < len(df) - 1:
            r = float(rsi.iloc[i]) if not np.isnan(rsi.iloc[i]) else 50.0
            if r <= 30:
                pending_side = "long"
            elif r >= 70:
                pending_side = "short"

    return result


def _composite_score(summary: dict) -> float:
    pf = summary["profit_factor"]
    pf_v = 3.0 if pf == "inf" else float(pf)
    return (
        float(summary["sharpe_like"]) * 3.0
        + pf_v
        + float(summary["total_pnl"]) / 2000.0
        - abs(float(summary["max_drawdown"])) * 25.0
        + float(summary["win_rate"])
    )


def head_to_head(
    df: pd.DataFrame,
    *,
    equity: float = 100_000.0,
    profile: TradeProfile | None = None,
) -> dict:
    """Compare behavioral edge (default high_win) vs naive RSI fade."""
    prof = profile or HIGH_WIN
    ours = run_backtest(
        df,
        engine=BehavioralEdgeEngine(
            risk=RiskConfig(account_equity=equity),
            profile=prof,
        ),
        label=f"behavioral_edge:{prof.name}",
    )
    theirs = run_naive_rsi_baseline(df, equity=equity)
    us_score = _composite_score(ours.summary())
    them_score = _composite_score(theirs.summary())
    if us_score > them_score:
        winner = ours.label
    elif them_score > us_score:
        winner = "naive_rsi_fade"
    else:
        winner = "tie"
    return {
        "behavioral_edge": ours.summary(),
        "naive_rsi_fade": theirs.summary(),
        "attribution": ours.attribution(),
        "composite_scores": {
            ours.label: round(us_score, 3),
            "naive_rsi_fade": round(them_score, 3),
        },
        "winner": winner,
        "pnl_edge": round(ours.total_pnl - theirs.total_pnl, 2),
        "profile": prof.name,
    }
