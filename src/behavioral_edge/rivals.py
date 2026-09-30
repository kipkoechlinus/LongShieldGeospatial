"""
Rival baselines — what Muse/Grok-class algos usually ship first.

We don't trash-talk; we measure. Arena ranks us against these stacks
on the same tape with the same composite score.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from behavioral_edge.backtest import BacktestResult, Trade
from behavioral_edge.signals import Signal, SignalKind


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _run_rule_system(
    df: pd.DataFrame,
    side_at,
    *,
    label: str,
    equity: float = 100_000.0,
    risk_frac: float = 0.005,
    stop_pct: float = 0.02,
    target_pct: float = 0.04,
    time_stop: int = 8,
) -> BacktestResult:
    """Generic next-open entry / stop-target-time exit for rival rules."""
    result = BacktestResult(label=label)
    cash = equity
    result.equity_curve.append(cash)
    open_trade: Trade | None = None
    entry_bar: int | None = None
    pending_side: str | None = None

    for i in range(len(df)):
        if pending_side and open_trade is None:
            px = float(df["open"].iloc[i])
            shares = (equity * risk_frac) / (px * stop_pct)
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
                    reason=label,
                    stop_pct=stop_pct,
                    target_pct=target_pct,
                    bar_index=max(0, i - 1),
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
                open_trade.entry * (1 - stop_pct)
                if open_trade.side == "long"
                else open_trade.entry * (1 + stop_pct)
            )
            target = (
                open_trade.entry * (1 + target_pct)
                if open_trade.side == "long"
                else open_trade.entry * (1 - target_pct)
            )
            exit_px = reason = None
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
            if exit_px is None and i - entry_bar >= time_stop:
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
            side = side_at(i)
            if side in {"long", "short"}:
                pending_side = side

    return result


def rival_muse_macd_bb(
    df: pd.DataFrame,
    *,
    equity: float = 100_000.0,
    risk_frac: float = 0.005,
    stop_pct: float = 0.02,
    target_pct: float = 0.04,
) -> BacktestResult:
    """
    Muse-class starter: MACD cross + Bollinger touch.
    Long when MACD crosses up near lower band; short near upper band cross down.
    """
    close = df["close"]
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    mid = close.rolling(20).mean()
    std = close.rolling(20).std(ddof=0)
    upper = mid + 2 * std
    lower = mid - 2 * std

    def side_at(i: int) -> str | None:
        if i < 26:
            return None
        cross_up = macd.iloc[i - 1] <= signal.iloc[i - 1] and macd.iloc[i] > signal.iloc[i]
        cross_dn = macd.iloc[i - 1] >= signal.iloc[i - 1] and macd.iloc[i] < signal.iloc[i]
        if cross_up and close.iloc[i] <= lower.iloc[i] * 1.01:
            return "long"
        if cross_dn and close.iloc[i] >= upper.iloc[i] * 0.99:
            return "short"
        return None

    return _run_rule_system(
        df,
        side_at,
        label="muse_macd_bb",
        equity=equity,
        risk_frac=risk_frac,
        stop_pct=stop_pct,
        target_pct=target_pct,
    )


def rival_grok_sma_rsi(
    df: pd.DataFrame,
    *,
    equity: float = 100_000.0,
    risk_frac: float = 0.005,
    stop_pct: float = 0.025,
    target_pct: float = 0.05,
) -> BacktestResult:
    """
    Grok-class starter: SMA trend filter + RSI pullback entry.
    Long above SMA50 when RSI dips < 40; short below SMA50 when RSI > 60.
    """
    close = df["close"]
    sma50 = close.rolling(50).mean()
    rsi = _rsi(close, 14)

    def side_at(i: int) -> str | None:
        if i < 50 or np.isnan(sma50.iloc[i]) or np.isnan(rsi.iloc[i]):
            return None
        if close.iloc[i] > sma50.iloc[i] and rsi.iloc[i] < 40:
            return "long"
        if close.iloc[i] < sma50.iloc[i] and rsi.iloc[i] > 60:
            return "short"
        return None

    return _run_rule_system(
        df,
        side_at,
        label="grok_sma_rsi",
        equity=equity,
        risk_frac=risk_frac,
        stop_pct=stop_pct,
        target_pct=target_pct,
    )


def rival_classic_rsi(
    df: pd.DataFrame, *, equity: float = 100_000.0
) -> BacktestResult:
    """Classic LLM tutorial: fade RSI 30/70."""
    from behavioral_edge.backtest import run_naive_rsi_baseline

    return run_naive_rsi_baseline(df, equity=equity)
