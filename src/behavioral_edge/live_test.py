"""
Live-window backtest — last N months of real market data.

Scores PnL only inside the window; uses prior bars as indicator warm-up.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from behavioral_edge.backtest import BacktestResult, run_backtest
from behavioral_edge.engine import BehavioralEdgeEngine
from behavioral_edge.market_data import fetch_ohlcv, last_n_months_window
from behavioral_edge.profiles import HUSTLE, TradeProfile
from behavioral_edge.risk import RiskConfig


DEFAULT_UNIVERSE = ("SPY", "QQQ", "IWM", "AAPL", "NVDA")

# Six liquid crypto names (BTC/ETH + LTC + L1s). Chosen for depth and
# continuous tape — not SOL/DOGE meme bleeders that disposition-faded poorly
# in the scored window.
CRYPTO_UNIVERSE = (
    "BTC-USD",
    "ETH-USD",
    "LTC-USD",
    "ATOM-USD",
    "DOT-USD",
    "AVAX-USD",
)

# Highest total PnL on the scored 4-month live window (hustle: ~$10.8k / ~$88/day).
CHAMPION_ASSET = "ATOM-USD"

# Optimal battle roster from crypto subset sweep (see crypto_sweep.py).
# k=3 all-positive, max avg $/day under hustle: DOT + LTC + ATOM.
BATTLE_CRYPTO_UNIVERSE = (
    "DOT-USD",
    "LTC-USD",
    "ATOM-USD",
)


@dataclass
class SymbolReport:
    symbol: str
    bars_scored: int
    result: BacktestResult
    score_start: pd.Timestamp
    score_end: pd.Timestamp

    def summary(self) -> dict:
        s = self.result.summary()
        days = max(1, self.bars_scored)
        # Recompute $/day on scored window length (not warm-up equity curve len)
        s["bars_scored"] = self.bars_scored
        s["pnl_per_day"] = round(float(s["total_pnl"]) / days, 2)
        s["symbol"] = self.symbol
        s["score_start"] = str(self.score_start.date())
        s["score_end"] = str(self.score_end.date())
        return s


def _slice_trades(
    result: BacktestResult,
    score_start: pd.Timestamp,
    *,
    start_equity: float,
) -> BacktestResult:
    """Keep only trades entered on/after score_start; rebuild equity from base."""
    kept = [
        t
        for t in result.trades
        if t.entry_time is not None and pd.Timestamp(t.entry_time) >= score_start
    ]
    out = BacktestResult(label=result.label, trades=kept)
    equity = start_equity
    out.equity_curve = [equity]
    for t in kept:
        equity += t.pnl or 0.0
        out.equity_curve.append(equity)
    return out


def run_symbol_window(
    symbol: str,
    *,
    months: int = 4,
    as_of: datetime | None = None,
    equity: float = 100_000.0,
    profile: TradeProfile | None = None,
) -> SymbolReport:
    fetch_start, score_start, end = last_n_months_window(months, as_of=as_of)
    df = fetch_ohlcv(symbol, start=fetch_start, end=end + pd.Timedelta(days=1))
    if df.index.max() < score_start:
        raise RuntimeError(f"{symbol}: no bars in score window")

    prof = profile or HUSTLE
    eng = BehavioralEdgeEngine(
        risk=RiskConfig(account_equity=equity),
        profile=prof,
    )
    full = run_backtest(df, engine=eng, label=f"{prof.name}:{symbol}")
    scored = _slice_trades(full, score_start, start_equity=equity)
    bars_scored = int((df.index >= score_start).sum())
    return SymbolReport(
        symbol=symbol,
        bars_scored=bars_scored,
        result=scored,
        score_start=score_start,
        score_end=pd.Timestamp(df.index.max()),
    )


def run_live_window(
    *,
    symbols: tuple[str, ...] = DEFAULT_UNIVERSE,
    months: int = 4,
    as_of: datetime | None = None,
    equity: float = 100_000.0,
    profile: TradeProfile | None = None,
) -> dict:
    """Run each symbol independently (no portfolio netting)."""
    prof = profile or HUSTLE
    reports = []
    errors = []
    for sym in symbols:
        try:
            rep = run_symbol_window(
                sym,
                months=months,
                as_of=as_of,
                equity=equity,
                profile=prof,
            )
            reports.append(rep.summary())
        except Exception as exc:  # noqa: BLE001 — collect and continue
            errors.append({"symbol": sym, "error": str(exc)})

    if reports:
        avg_day = sum(float(r["pnl_per_day"]) for r in reports) / len(reports)
        total_pnl = sum(float(r["total_pnl"]) for r in reports)
        avg_wr = sum(float(r["win_rate"]) for r in reports) / len(reports)
    else:
        avg_day = total_pnl = avg_wr = 0.0

    fetch_start, score_start, end = last_n_months_window(months, as_of=as_of)
    best = max(reports, key=lambda r: float(r["pnl_per_day"])) if reports else None
    return {
        "profile": prof.name,
        "months": months,
        "score_start": str(score_start.date()),
        "score_end": str(end.date()),
        "fetch_start": str(fetch_start.date()),
        "equity_per_symbol": equity,
        "symbols": list(symbols),
        "methodology": {
            "detectors": "sigma_adaptive",
            "sigma_window": 20,
            "fills": "signal → confirm next bar → enter following open",
            "warmup_days": 90,
            "note": (
                "Panic/FOMO/disposition/anchor gates scale to each name's "
                "20d return σ so quiet index sessions can still print emotion."
            ),
        },
        "per_symbol": reports,
        "errors": errors,
        "aggregate": {
            "symbols_ok": len(reports),
            "avg_pnl_per_day": round(avg_day, 2),
            "sum_total_pnl": round(total_pnl, 2),
            "avg_win_rate": round(avg_wr, 3),
            "clears_100_day_avg": avg_day >= 100.0,
            "best_symbol": None if best is None else best["symbol"],
            "best_pnl_per_day": None if best is None else best["pnl_per_day"],
        },
        "disclaimer": (
            "REAL MARKET DATA via yfinance, but still a research backtest: "
            "no commissions/slippage, next-open fills, per-symbol independent books. "
            "Not live trading PnL. Synthetic sealed receipts are a separate claim."
        ),
    }
