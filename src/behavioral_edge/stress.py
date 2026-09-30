"""Multi-seed stress — prove we don't only win on seed=42."""

from __future__ import annotations

from behavioral_edge.arena import run_arena
from behavioral_edge.data import make_behavioral_tape
from behavioral_edge.profiles import PREDATOR, TradeProfile


DEFAULT_SEEDS = (7, 21, 42, 99, 123, 256, 512, 777, 1024, 2026)


def run_stress(
    *,
    seeds: tuple[int, ...] = DEFAULT_SEEDS,
    bars: int = 220,
    equity: float = 100_000.0,
    profile: TradeProfile | None = None,
) -> dict:
    """
    Run the Muse/Grok arena across many synthetic seeds.
    Reports win-rate of #1 finishes, median composite, worst rank.
    """
    prof = profile or PREDATOR
    rows = []
    for seed in seeds:
        df = make_behavioral_tape(n=bars, seed=seed)
        report = run_arena(df, equity=equity, profile=prof)
        our = next(r for r in report["ranking"] if r["label"].startswith("behavioral_edge"))
        rows.append(
            {
                "seed": seed,
                "winner": report["winner"],
                "we_win": report["we_win"],
                "beats_muse_grok": report["beats_muse_grok"],
                "our_rank": report["our_rank"],
                "our_composite": our["composite"],
                "our_win_rate": our["win_rate"],
                "our_pnl": our["total_pnl"],
                "margin_vs_second": report["margin_vs_second"],
            }
        )

    wins = sum(1 for r in rows if r["we_win"])
    ai_wins = sum(1 for r in rows if r["beats_muse_grok"])
    composites = sorted(r["our_composite"] for r in rows)
    mid = len(composites) // 2
    median_comp = (
        composites[mid]
        if len(composites) % 2 == 1
        else (composites[mid - 1] + composites[mid]) / 2
    )
    return {
        "profile": prof.name,
        "seeds": list(seeds),
        "arenas": len(rows),
        "wins": wins,
        "win_pct": round(wins / len(rows), 3) if rows else 0.0,
        "beats_muse_grok": ai_wins,
        "beats_muse_grok_pct": round(ai_wins / len(rows), 3) if rows else 0.0,
        "median_composite": round(median_comp, 3),
        "worst_rank": max(r["our_rank"] for r in rows) if rows else None,
        "best_rank": min(r["our_rank"] for r in rows) if rows else None,
        "avg_pnl": round(sum(r["our_pnl"] for r in rows) / len(rows), 2) if rows else 0.0,
        "avg_win_rate": round(
            sum(r["our_win_rate"] for r in rows) / len(rows), 3
        )
        if rows
        else 0.0,
        "detail": rows,
    }
