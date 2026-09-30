"""Arena — rank Behavioral Edge vs Muse/Grok-class rival stacks."""

from __future__ import annotations

from behavioral_edge.backtest import BacktestResult, _composite_score, run_backtest
from behavioral_edge.engine import BehavioralEdgeEngine
from behavioral_edge.profiles import HIGH_WIN, TradeProfile
from behavioral_edge.risk import RiskConfig
from behavioral_edge.rivals import (
    rival_classic_rsi,
    rival_grok_sma_rsi,
    rival_muse_macd_bb,
)


def run_arena(
    df,
    *,
    equity: float = 100_000.0,
    profile: TradeProfile | None = None,
) -> dict:
    """
    Multi-fighter ranking on one tape.
    Winner = highest risk-adjusted composite.
    Also reports whether we beat both Muse- and Grok-class stacks.
    """
    prof = profile or HIGH_WIN
    ours = run_backtest(
        df,
        engine=BehavioralEdgeEngine(
            risk=RiskConfig(account_equity=equity),
            profile=prof,
        ),
        label=f"behavioral_edge:{prof.name}",
    )
    fighters: list[BacktestResult] = [
        ours,
        rival_muse_macd_bb(df, equity=equity),
        rival_grok_sma_rsi(df, equity=equity),
        rival_classic_rsi(df, equity=equity),
    ]

    scored = []
    for f in fighters:
        s = f.summary()
        scored.append({**s, "composite": round(_composite_score(s), 3)})
    scored.sort(key=lambda r: r["composite"], reverse=True)
    winner = scored[0]["label"]
    our_row = next(r for r in scored if r["label"].startswith("behavioral_edge"))
    our_comp = our_row["composite"]
    muse = next(r for r in scored if r["label"] == "muse_macd_bb")
    grok = next(r for r in scored if r["label"] == "grok_sma_rsi")
    beats_ai = our_comp > muse["composite"] and our_comp > grok["composite"]

    return {
        "ranking": scored,
        "winner": winner,
        "we_win": winner.startswith("behavioral_edge"),
        "beats_muse_grok": beats_ai,
        "our_rank": next(
            i + 1
            for i, r in enumerate(scored)
            if r["label"].startswith("behavioral_edge")
        ),
        "margin_vs_second": round(
            scored[0]["composite"] - scored[1]["composite"], 3
        )
        if len(scored) > 1
        else 0.0,
        "attribution": ours.attribution(),
        "profile": prof.name,
        "our_win_rate": our_row["win_rate"],
    }
