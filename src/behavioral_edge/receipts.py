"""
Sealed receipts — reputation-grade, reproducible run evidence.

When rivals bring numbers, we compare methodology first, dollars second.
No vibes. No moving goalposts.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from behavioral_edge import __version__
from behavioral_edge.hustle import run_hustle, run_hustle_stress
from behavioral_edge.profiles import HUSTLE, TradeProfile


METHODOLOGY = {
    "market": "synthetic_behavioral_tape",
    "generator": "behavioral_edge.data.make_behavioral_tape",
    "fill_model": "next_open_after_soft_confirmation",
    "exits": "stop / scalp / scale-out runner / winners-only time stop",
    "costs": "none_modeled",
    "disclaimer": (
        "SYNTHETIC. Not live fills, not broker PnL. "
        "Compare only under matching assumptions (seed/bars/equity/costs)."
    ),
}


def _git_sha() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        return out
    except Exception:
        return "unknown"


def _seal(payload: dict[str, Any]) -> dict[str, Any]:
    """Attach sha256 over canonical JSON (excluding the seal itself)."""
    body = {k: v for k, v in payload.items() if k != "seal"}
    raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    digest = hashlib.sha256(raw).hexdigest()
    sealed = dict(payload)
    sealed["seal"] = {
        "alg": "sha256",
        "digest": digest,
        "sealed_at": datetime.now(timezone.utc).isoformat(),
    }
    return sealed


def verify_seal(receipt: dict[str, Any]) -> bool:
    seal = receipt.get("seal") or {}
    digest = seal.get("digest")
    if not digest:
        return False
    body = {k: v for k, v in receipt.items() if k != "seal"}
    raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest() == digest


def issue_hustle_receipt(
    *,
    bars: int = 320,
    seed: int = 42,
    equity: float = 100_000.0,
    profile: TradeProfile | None = None,
    include_stress: bool = True,
) -> dict[str, Any]:
    """Run hustle (+ optional stress) and return a sealed receipt."""
    prof = profile or HUSTLE
    league = run_hustle(bars=bars, seed=seed, equity=equity, profile=prof)
    stress = None
    if include_stress:
        stress = run_hustle_stress(bars=bars, equity=equity, profile=prof)

    payload: dict[str, Any] = {
        "receipt_type": "behavioral_edge.hustle",
        "version": __version__,
        "git_sha": _git_sha(),
        "methodology": METHODOLOGY,
        "config": {
            "profile": prof.name,
            "bars": bars,
            "seed": seed,
            "equity": equity,
            "risk_per_trade": prof.risk_per_trade,
            "max_open_risk": prof.max_open_risk,
        },
        "league": league,
        "stress": stress,
        "claims": {
            "clears_100_day": bool(league["clears_100_day"]),
            "beats_pressed_rivals_on_seed": bool(league["we_win"]),
            "our_pnl_per_day": league["our_pnl_per_day"],
            "stress_clears_100_pct": None
            if stress is None
            else stress["clears_100_pct"],
            "stress_avg_pnl_per_day": None
            if stress is None
            else stress["avg_pnl_per_day"],
        },
    }
    return _seal(payload)


def write_receipt(receipt: dict[str, Any], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return path


def load_receipt(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def compare_receipts(
    ours: dict[str, Any],
    theirs: dict[str, Any],
    *,
    metric: str = "pnl_per_day",
) -> dict[str, Any]:
    """
    Fair bake-off.

    `theirs` may be a full sealed receipt or a simple dict like:
      {"name": "muse", "pnl_per_day": 100, "win_rate": 0.55, "notes": "..."}
    """
    our_seal_ok = verify_seal(ours) if "seal" in ours else None
    their_seal_ok = verify_seal(theirs) if "seal" in theirs else None

    our_day = _extract_metric(ours, metric)
    their_day = _extract_metric(theirs, metric)
    our_wr = _extract_metric(ours, "win_rate")
    their_wr = _extract_metric(theirs, "win_rate")

    methodology_flags = []
    their_method = theirs.get("methodology") or {}
    our_method = ours.get("methodology") or METHODOLOGY
    if their_method:
        for key in ("market", "costs", "fill_model"):
            if key in their_method and their_method.get(key) != our_method.get(key):
                methodology_flags.append(
                    f"mismatch:{key}:ours={our_method.get(key)} theirs={their_method.get(key)}"
                )
    else:
        methodology_flags.append(
            "their_methodology_missing — cannot verify apples-to-apples"
        )

    if our_day is None or their_day is None:
        winner = "incomplete"
    elif float(our_day) > float(their_day):
        winner = "behavioral_edge"
    elif float(their_day) > float(our_day):
        winner = theirs.get("name") or theirs.get("receipt_type") or "rival"
    else:
        winner = "tie"

    return {
        "metric": metric,
        "ours": {
            "name": "behavioral_edge",
            "value": our_day,
            "win_rate": our_wr,
            "seal_ok": our_seal_ok,
            "version": ours.get("version"),
            "git_sha": ours.get("git_sha"),
        },
        "theirs": {
            "name": theirs.get("name")
            or theirs.get("receipt_type")
            or "rival",
            "value": their_day,
            "win_rate": their_wr,
            "seal_ok": their_seal_ok,
        },
        "delta": None
        if our_day is None or their_day is None
        else round(float(our_day) - float(their_day), 2),
        "winner": winner,
        "methodology_flags": methodology_flags,
        "fair_fight": len(methodology_flags) == 0,
        "note": (
            "If methodology_flags is non-empty, dollar comparison is informational only."
        ),
    }


def _extract_metric(receipt: dict[str, Any], metric: str) -> float | None:
    if metric in receipt and isinstance(receipt[metric], (int, float)):
        return float(receipt[metric])
    claims = receipt.get("claims") or {}
    if metric in claims and isinstance(claims[metric], (int, float)):
        return float(claims[metric])
    # common aliases
    if metric == "pnl_per_day":
        if "our_pnl_per_day" in claims:
            return float(claims["our_pnl_per_day"])
        league = receipt.get("league") or {}
        if "our_pnl_per_day" in league:
            return float(league["our_pnl_per_day"])
        ranking = league.get("ranking") or receipt.get("ranking") or []
        if ranking:
            return float(ranking[0].get("pnl_per_day"))
    if metric == "win_rate":
        league = receipt.get("league") or {}
        ranking = league.get("ranking") or receipt.get("ranking") or []
        if ranking:
            top = ranking[0]
            if str(top.get("label", "")).startswith("behavioral_edge"):
                return float(top.get("win_rate"))
            for row in ranking:
                if str(row.get("label", "")).startswith("behavioral_edge"):
                    return float(row.get("win_rate"))
    return None
