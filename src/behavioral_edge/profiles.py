"""Trade profiles — choose expectancy shape and cash intensity."""

from __future__ import annotations

from dataclasses import dataclass, replace

from behavioral_edge.signals import Signal, SignalKind


@dataclass(frozen=True)
class TradeProfile:
    """
    Shapes how signals are traded.

    high_win / predator: quality + hit-rate.
    hustle: size up + denser entries to clear a $/day bar (still mechanical).
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
    time_stop_winners_only: bool = False
    scale_out_frac: float = 0.0
    cooldown_bars: int = 0
    min_signal_gap: int = 0
    # Optional risk overrides (None = keep RiskConfig defaults)
    risk_per_trade: float | None = None
    max_open_risk: float | None = None
    target_vol: float | None = None
    disable_vol_targeting: bool = False


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
    stop_scale=1.25,
    target_scale=0.30,
    min_strength=0.55,
    min_edge=0.58,
    min_confluence=0.15,
    time_stop_bars=3,
    scalp_r=0.55,
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

PREDATOR = TradeProfile(
    name="predator",
    stop_scale=1.0,
    target_scale=0.55,
    min_strength=0.58,
    min_edge=0.62,
    min_confluence=0.20,
    time_stop_bars=4,
    scalp_r=0.55,
    trail_after_r=0.30,
    allowed_kinds=frozenset(
        {
            # Panic kept out — post-climax ATR stops eat the book on waterfall
            # retests; traps + FOMO carry the arena edge.
            SignalKind.ANCHOR_REJECTION,
            SignalKind.FOMO_EXHAUSTION,
        }
    ),
    require_confirmation=True,
    time_stop_winners_only=True,
    scale_out_frac=0.60,
    cooldown_bars=2,
    min_signal_gap=3,
)

# Hustle: clear / beat the $100/day brag with size + frequency
HUSTLE = TradeProfile(
    name="hustle",
    stop_scale=1.0,
    target_scale=0.90,
    min_strength=0.55,
    min_edge=0.56,
    min_confluence=0.10,
    time_stop_bars=5,
    scalp_r=0.90,
    trail_after_r=0.45,  # don't BE-trail so early we scratch winners
    allowed_kinds=frozenset(
        {
            # Panic kept out — waterfall entries were stopping out the book
            SignalKind.DISPOSITION_CONTINUATION,
            SignalKind.ANCHOR_REJECTION,
            SignalKind.FOMO_EXHAUSTION,
        }
    ),
    require_confirmation=True,
    time_stop_winners_only=True,
    scale_out_frac=0.40,
    cooldown_bars=0,
    min_signal_gap=1,
    risk_per_trade=0.045,
    max_open_risk=0.09,
    disable_vol_targeting=True,
)

# Crypto: same cash intensity as hustle, but FOMO fades are out —
# on 24/7 tape vertical chase often continues; disposition dips + anchor
# traps carry the book.
CRYPTO = TradeProfile(
    name="crypto",
    stop_scale=1.0,
    target_scale=0.90,
    min_strength=0.55,
    min_edge=0.56,
    min_confluence=0.10,
    time_stop_bars=5,
    scalp_r=0.90,
    trail_after_r=0.45,
    allowed_kinds=frozenset(
        {
            SignalKind.DISPOSITION_CONTINUATION,
            SignalKind.ANCHOR_REJECTION,
        }
    ),
    require_confirmation=True,
    time_stop_winners_only=True,
    scale_out_frac=0.40,
    cooldown_bars=0,
    min_signal_gap=1,
    risk_per_trade=0.045,
    max_open_risk=0.09,
    disable_vol_targeting=True,
)

# Killer: bake-off weapon. No FOMO, fat risk, slightly tight stops /
# stretch targets, let winners breathe. Built to clear $100/day on the
# battle crypto roster (DOT/LTC/ATOM) — higher variance by design.
KILLER = TradeProfile(
    name="killer",
    stop_scale=0.90,
    target_scale=1.05,
    min_strength=0.55,
    min_edge=0.54,
    min_confluence=0.05,
    time_stop_bars=6,
    scalp_r=0.95,
    trail_after_r=0.55,
    allowed_kinds=frozenset(
        {
            SignalKind.DISPOSITION_CONTINUATION,
            SignalKind.ANCHOR_REJECTION,
        }
    ),
    require_confirmation=True,
    time_stop_winners_only=True,
    scale_out_frac=0.35,
    cooldown_bars=0,
    min_signal_gap=1,
    risk_per_trade=0.09,
    max_open_risk=0.18,
    disable_vol_targeting=True,
)

PROFILES: dict[str, TradeProfile] = {
    BALANCED.name: BALANCED,
    HIGH_WIN.name: HIGH_WIN,
    PREDATOR.name: PREDATOR,
    HUSTLE.name: HUSTLE,
    CRYPTO.name: CRYPTO,
    KILLER.name: KILLER,
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
    if profile.name == "high_win":
        target = min(target, stop * 0.65)
    elif profile.name == "predator":
        target = min(target, stop * 0.70)
    elif profile.name in {"hustle", "crypto"}:
        target = min(target, stop * 0.90)
    elif profile.name == "killer":
        # Asymmetric: allow fuller R on the runner side of the scalp
        target = min(target, stop * 1.05)
    if target <= 0 or stop <= 0:
        return None
    return replace(signal, stop_pct=stop, target_pct=target)
