"""
Killer strategy — the bake-off weapon.

Thesis (mechanical, not vibes):
1. FOMO shorts on 24/7 crypto are death — vertical chase continues. Cut them.
2. Disposition dips + anchor traps are the only prints that paid on the live
   window; size those up hard (9% risk) with asymmetric targets.
3. Elite edge gets a sharper pyramid; stops sit slightly tight so losers die
   fast and winners are left alone (trail later, time-stop winners only).

Run on the battle roster (DOT / LTC / ATOM):
  python3 -m behavioral_edge.cli live --months 4 --battle
"""

from __future__ import annotations

from behavioral_edge.crypto_sweep import BATTLE_CRYPTO_UNIVERSE
from behavioral_edge.live_test import run_live_window
from behavioral_edge.profiles import KILLER


def run_killer_battle(*, months: int = 4, equity: float = 100_000.0) -> dict:
    """Killer profile on the locked battle crypto roster."""
    report = run_live_window(
        symbols=BATTLE_CRYPTO_UNIVERSE,
        months=months,
        equity=equity,
        profile=KILLER,
    )
    report["strategy"] = "killer"
    report["battle_roster"] = list(BATTLE_CRYPTO_UNIVERSE)
    report["clears_100_day_avg"] = bool(
        report.get("aggregate", {}).get("clears_100_day_avg")
    )
    return report
