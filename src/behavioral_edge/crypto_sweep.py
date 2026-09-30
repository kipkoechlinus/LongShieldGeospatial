"""
Crypto subset sweep — pick the optimal battle roster on a live window.

Brute-forces non-empty subsets of a candidate universe under a profile and
ranks by avg $/day, desk $/day (sum of per-symbol $/day), and sum PnL.
"""

from __future__ import annotations

import itertools
from datetime import datetime
from typing import Iterable

import pandas as pd

from behavioral_edge.backtest import run_backtest
from behavioral_edge.engine import BehavioralEdgeEngine
from behavioral_edge.market_data import fetch_ohlcv, last_n_months_window
from behavioral_edge.profiles import CRYPTO, HUSTLE, TradeProfile
from behavioral_edge.risk import RiskConfig

# Liquid candidates scanned for the bake-off
SWEEP_CANDIDATES: tuple[str, ...] = (
    "BTC-USD",
    "ETH-USD",
    "SOL-USD",
    "XRP-USD",
    "BNB-USD",
    "DOGE-USD",
    "AVAX-USD",
    "LINK-USD",
    "ADA-USD",
    "DOT-USD",
    "LTC-USD",
    "ATOM-USD",
    "NEAR-USD",
)

# Battle roster from the 4mo sweep: all-positive, k∈[3,5], max avg $/day.
# hustle · DOT + LTC + ATOM · ~$66/day avg · ~$24.4k sum · ~92% WR
BATTLE_CRYPTO_UNIVERSE: tuple[str, ...] = (
    "DOT-USD",
    "LTC-USD",
    "ATOM-USD",
)
BATTLE_CRYPTO_PROFILE = "hustle"


def _symbol_stats(
    symbol: str,
    *,
    profile: TradeProfile,
    months: int,
    as_of: datetime | None,
    equity: float,
) -> dict:
    fetch_start, score_start, end = last_n_months_window(months, as_of=as_of)
    df = fetch_ohlcv(symbol, start=fetch_start, end=end + pd.Timedelta(days=1))
    eng = BehavioralEdgeEngine(
        risk=RiskConfig(account_equity=equity),
        profile=profile,
    )
    full = run_backtest(df, engine=eng, label=f"{profile.name}:{symbol}")
    trades = [
        t
        for t in full.trades
        if t.entry_time is not None and pd.Timestamp(t.entry_time) >= score_start
    ]
    pnl = float(sum(t.pnl or 0.0 for t in trades))
    bars = int((df.index >= score_start).sum())
    scratches = sum(1 for t in trades if abs(t.pnl or 0.0) < 1e-9)
    decided = len(trades) - scratches
    wins = sum(1 for t in trades if (t.pnl or 0.0) > 0)
    return {
        "symbol": symbol,
        "trades": len(trades),
        "wr": round(wins / decided, 3) if decided else 0.0,
        "pnl": round(pnl, 2),
        "per_day": round(pnl / max(1, bars), 2),
        "bars": bars,
    }


def _combo_rec(combo: Iterable[dict]) -> dict:
    rows = list(combo)
    k = len(rows)
    avg_day = sum(s["per_day"] for s in rows) / k
    sum_pnl = sum(s["pnl"] for s in rows)
    desk = sum(s["per_day"] for s in rows)
    avg_wr = sum(s["wr"] for s in rows) / k
    return {
        "k": k,
        "symbols": [s["symbol"] for s in rows],
        "avg_day": round(avg_day, 2),
        "sum_pnl": round(sum_pnl, 2),
        "desk_day": round(desk, 2),
        "avg_wr": round(avg_wr, 3),
        "all_positive": all(s["per_day"] > 0 for s in rows),
    }


def run_crypto_subset_sweep(
    *,
    candidates: tuple[str, ...] = SWEEP_CANDIDATES,
    months: int = 4,
    as_of: datetime | None = None,
    equity: float = 100_000.0,
    profiles: dict[str, TradeProfile] | None = None,
    battle_k_min: int = 3,
    battle_k_max: int = 5,
) -> dict:
    """
    Sweep all subset sizes.

    Battle roster rule: all-positive names, k in [battle_k_min, battle_k_max],
    maximize avg $/day (then sum PnL). Single-name champion is reported separately.
    """
    profs = profiles or {"crypto": CRYPTO, "hustle": HUSTLE}
    fetch_start, score_start, end = last_n_months_window(months, as_of=as_of)
    out_profiles: dict = {}

    for pname, prof in profs.items():
        rows = []
        errors = []
        for sym in candidates:
            try:
                rows.append(
                    _symbol_stats(
                        sym,
                        profile=prof,
                        months=months,
                        as_of=as_of,
                        equity=equity,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                errors.append({"symbol": sym, "error": str(exc)})

        by_k: dict = {}
        best_avg = best_desk = best_sum = None
        for r in range(1, len(rows) + 1):
            ka = kd = ks = None
            for combo in itertools.combinations(rows, r):
                rec = _combo_rec(combo)
                if ka is None or (rec["avg_day"], rec["sum_pnl"]) > (
                    ka["avg_day"],
                    ka["sum_pnl"],
                ):
                    ka = rec
                if kd is None or (rec["desk_day"], rec["sum_pnl"]) > (
                    kd["desk_day"],
                    kd["sum_pnl"],
                ):
                    kd = rec
                if ks is None or (rec["sum_pnl"], rec["avg_day"]) > (
                    ks["sum_pnl"],
                    ks["avg_day"],
                ):
                    ks = rec
            by_k[str(r)] = {
                "best_avg_day": ka,
                "best_desk_day": kd,
                "best_sum_pnl": ks,
            }
            if best_avg is None or (ka["avg_day"], ka["sum_pnl"]) > (
                best_avg["avg_day"],
                best_avg["sum_pnl"],
            ):
                best_avg = ka
            if best_desk is None or (kd["desk_day"], kd["sum_pnl"]) > (
                best_desk["desk_day"],
                best_desk["sum_pnl"],
            ):
                best_desk = kd
            if best_sum is None or (ks["sum_pnl"], ks["avg_day"]) > (
                best_sum["sum_pnl"],
                best_sum["avg_day"],
            ):
                best_sum = ks

        battle = None
        for r in range(battle_k_min, min(battle_k_max, len(rows)) + 1):
            for combo in itertools.combinations(rows, r):
                rec = _combo_rec(combo)
                if not rec["all_positive"]:
                    continue
                rec = {
                    **rec,
                    "rule": f"all_positive_k{battle_k_min}to{battle_k_max}_max_avg_day",
                }
                if battle is None or (rec["avg_day"], rec["sum_pnl"]) > (
                    battle["avg_day"],
                    battle["sum_pnl"],
                ):
                    battle = rec

        pos = sorted([s for s in rows if s["per_day"] > 0], key=lambda s: -s["per_day"])
        out_profiles[pname] = {
            "per_symbol": {s["symbol"]: s for s in rows},
            "errors": errors,
            "by_k": by_k,
            "global_best_avg_day": best_avg,
            "global_best_desk_day": best_desk,
            "global_best_sum_pnl": best_sum,
            "positive_only": _combo_rec(pos) if pos else None,
            "battle_roster": battle,
        }

    # Cross-profile battle winner
    winner_name = None
    winner_rec = None
    for pname, block in out_profiles.items():
        br = block.get("battle_roster")
        if br is None:
            continue
        if winner_rec is None or (br["avg_day"], br["sum_pnl"]) > (
            winner_rec["avg_day"],
            winner_rec["sum_pnl"],
        ):
            winner_name = pname
            winner_rec = br

    return {
        "months": months,
        "score_start": str(score_start.date()),
        "score_end": str(end.date()),
        "fetch_start": str(fetch_start.date()),
        "equity_per_symbol": equity,
        "candidates": list(candidates),
        "objective": (
            "Per k: best subset by avg $/day, desk $/day, sum PnL. "
            f"Battle roster = all-positive, k∈[{battle_k_min},{battle_k_max}], max avg $/day."
        ),
        "profiles": out_profiles,
        "battle_winner": (
            None
            if winner_rec is None
            else {"profile": winner_name, **winner_rec}
        ),
        "champion_single": {
            pname: block["global_best_avg_day"]
            for pname, block in out_profiles.items()
        },
        "disclaimer": (
            "REAL MARKET DATA research backtest. Subset selection is in-sample on "
            "this window — rivals can challenge out-of-sample. Not broker PnL."
        ),
    }
