"""
Hustle league — $/day fight vs Muse & Claude style stacks.

They claim ~$100/day. We measure pnl_per_day on the same dense tape
with sized-up rival baselines (not toy 0.5% risk).
"""

from __future__ import annotations

from behavioral_edge.backtest import run_backtest, run_naive_rsi_baseline
from behavioral_edge.data import make_behavioral_tape
from behavioral_edge.engine import BehavioralEdgeEngine
from behavioral_edge.profiles import HUSTLE, TradeProfile
from behavioral_edge.risk import RiskConfig
from behavioral_edge.rivals import rival_grok_sma_rsi, rival_muse_macd_bb


DAILY_BAR = 100.0  # the brag we're here to clear


def run_hustle(
    *,
    bars: int = 320,
    seed: int = 42,
    equity: float = 100_000.0,
    profile: TradeProfile | None = None,
    daily_bar: float = DAILY_BAR,
) -> dict:
    """Rank fighters by pnl_per_day. Default profile = hustle."""
    prof = profile or HUSTLE
    df = make_behavioral_tape(n=bars, seed=seed)

    ours = run_backtest(
        df,
        engine=BehavioralEdgeEngine(
            risk=RiskConfig(account_equity=equity),
            profile=prof,
        ),
        label=f"behavioral_edge:{prof.name}",
    )
    # Pressed rivals — risk set so their "$100/day" claim is the fair fight,
    # not god-mode spam on a mean-reversion tape.
    muse = rival_muse_macd_bb(
        df, equity=equity, risk_frac=0.012, stop_pct=0.02, target_pct=0.045
    )
    muse.label = "muse_macd_bb_pressed"
    claude = run_naive_rsi_baseline(df, equity=equity, risk_frac=0.012)
    claude.label = "claude_rsi_pressed"
    grok = rival_grok_sma_rsi(df, equity=equity, risk_frac=0.012)
    grok.label = "grok_sma_rsi_pressed"

    rows = []
    for r in (ours, muse, claude, grok):
        s = r.summary()
        rows.append(s)
    rows.sort(key=lambda x: float(x["pnl_per_day"]), reverse=True)

    our = next(r for r in rows if str(r["label"]).startswith("behavioral_edge"))
    return {
        "seed": seed,
        "bars": bars,
        "profile": prof.name,
        "daily_bar": daily_bar,
        "ranking": rows,
        "winner": rows[0]["label"],
        "we_win": str(rows[0]["label"]).startswith("behavioral_edge"),
        "our_pnl_per_day": our["pnl_per_day"],
        "clears_100_day": float(our["pnl_per_day"]) >= daily_bar,
        "margin_vs_second_per_day": round(
            float(rows[0]["pnl_per_day"]) - float(rows[1]["pnl_per_day"]), 2
        )
        if len(rows) > 1
        else 0.0,
    }


def run_hustle_stress(
    *,
    seeds: tuple[int, ...] = (7, 21, 42, 99, 256, 512, 777, 1024),
    bars: int = 320,
    equity: float = 100_000.0,
    profile: TradeProfile | None = None,
    daily_bar: float = DAILY_BAR,
) -> dict:
    prof = profile or HUSTLE
    details = []
    for seed in seeds:
        report = run_hustle(
            bars=bars, seed=seed, equity=equity, profile=prof, daily_bar=daily_bar
        )
        details.append(
            {
                "seed": seed,
                "we_win": report["we_win"],
                "clears_100_day": report["clears_100_day"],
                "our_pnl_per_day": report["our_pnl_per_day"],
                "winner": report["winner"],
            }
        )
    n = len(details) or 1
    return {
        "profile": prof.name,
        "bars": bars,
        "daily_bar": daily_bar,
        "seeds": list(seeds),
        "wins": sum(1 for d in details if d["we_win"]),
        "win_pct": round(sum(1 for d in details if d["we_win"]) / n, 3),
        "clears_100": sum(1 for d in details if d["clears_100_day"]),
        "clears_100_pct": round(sum(1 for d in details if d["clears_100_day"]) / n, 3),
        "avg_pnl_per_day": round(
            sum(float(d["our_pnl_per_day"]) for d in details) / n, 2
        ),
        "detail": details,
    }
