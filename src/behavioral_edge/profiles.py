"""Trade profiles — choose expectancy shape. High-win takes profit early."""

from __future__ import annotations

from dataclasses import dataclass, replace

from behavioral_edge.signals import Signal, SignalKind


@dataclass(frozen=True)
class TradeProfile:
    """
    Shapes how signals are traded.

    high_win: small targets, early scalp, wider stops, never time-stop a loser —
              leave meat on the table to stack wins.
    balanced: larger R multiple hunt.
    """

    name: str
    stop_scale: float = 1.0
    target_scale: float = 1.0
    min_strength: float = 0.55
    min_edge: float = 0.55
    min_confluence: float = 0.0
    time_stop_bars: int = 8
    scalp_r: float | None = None
    trail_after_r: float = 1.0
    allowed_kinds: frozenset[SignalKind] | None = None
    require_confirmation: bool = True
    # If True, time stop only banks green trades (never crystallizes a loser)
    time_stop_winners_only: bool = False
    # Bank this fraction at scalp; leave runner with BE stop (0 = full scalp exit)
    scale_out_frac: float = 0.0
    # Bars to cool down after a full stop-out
    cooldown_bars: int = 0
    # Min bars between entries
    min_signal_gap: int = 0


BALANCED = TradeProfile(
    name="balanced",
    stop_scale=1.0,
    target_scale=1.0,
    min_strength=0.55,
    min_edge=0.55,
    min_confluence=0.0,
    time_stop_bars=8,
    scalp_r=None,
    trail_after_r=1.0,
    time_stop_winners_only=False,
)

HIGH_WIN = TradeProfile(
    name="high_win",
    # Wider stop (survive noise) + tiny target (bank the bounce)
    stop_scale=1.25,
    target_scale=0.30,
    min_strength=0.55,
    min_edge=0.58,
    min_confluence=0.15,
    time_stop_bars=3,
    scalp_r=0.55,  # bank at +0.55R
    trail_after_r=0.30,
    allowed_kinds=frozenset(
        {
            SignalKind.PANIC_CAPITULATION,
            SignalKind.DISPOSITION_CONTINUATION,
            SignalKind.ANCHOR_REJECTION,
            SignalKind.FOMO_EXHAUSTION,
        }
    ),
    require_confirmation=True,
    time_stop_winners_only=True,
)

# Predator: hardened for rival stress — scale-out + cooldown + gap
PREDATOR = TradeProfile(
    name="predator",
    stop_scale=1.0,  # meta ATR overwrites stops; keep scale neutral
    target_scale=0.55,
    min_strength=0.58,
    min_edge=0.62,
    min_confluence=0.20,
    time_stop_bars=4,
    scalp_r=0.55,
    trail_after_r=0.30,
    allowed_kinds=frozenset(
        {
            # Disposition dips kept out of predator — higher variance vs rivals
            SignalKind.PANIC_CAPITULATION,
            SignalKind.ANCHOR_REJECTION,
            SignalKind.FOMO_EXHAUSTION,
        }
    ),
    require_confirmation=True,
    time_stop_winners_only=True,
    scale_out_frac=0.60,  # bank 60% early; runner hunts remainder
    cooldown_bars=2,
    min_signal_gap=3,
)

PROFILES: dict[str, TradeProfile] = {
    BALANCED.name: BALANCED,
    HIGH_WIN.name: HIGH_WIN,
    PREDATOR.name: PREDATOR,
}


def apply_profile(signal: Signal, profile: TradeProfile) -> Signal | None:
    """Resize stop/target and filter by profile gates. None = skip."""
    if profile.allowed_kinds is not None and signal.kind not in profile.allowed_kinds:
        return None
    if signal.strength < profile.min_strength:
        return None
    if (signal.edge_score or signal.strength) < profile.min_edge:
        return None
    if signal.confluence < profile.min_confluence:
        return None

    stop = signal.stop_pct * profile.stop_scale
    target = signal.target_pct * profile.target_scale
    if profile.scalp_r is not None:
        target = min(target, stop * profile.scalp_r)
    target = max(target, stop * 0.45)
    if profile.name in {"high_win", "predator"}:
        target = min(target, stop * (0.65 if profile.name == "high_win" else 0.70))
    if target <= 0 or stop <= 0:
        return None
    return replace(signal, stop_pct=stop, target_pct=target)
