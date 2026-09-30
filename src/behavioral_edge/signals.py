"""Signal types produced by behavioral detectors."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SignalKind(str, Enum):
    """Each signal maps to a documented human bias."""

    PANIC_CAPITULATION = "panic_capitulation"  # loss aversion → forced selling
    FOMO_EXHAUSTION = "fomo_exhaustion"  # late herding → blow-off top
    DISPOSITION_CONTINUATION = "disposition_continuation"  # sell winners early
    ANCHOR_REJECTION = "anchor_rejection"  # round-number / prior-extreme anchoring


@dataclass(frozen=True)
class Signal:
    kind: SignalKind
    side: str  # "long" | "short"
    strength: float  # 0..1
    reason: str
    stop_pct: float
    target_pct: float
    bar_index: int

    def validate(self) -> None:
        if self.side not in {"long", "short"}:
            raise ValueError(f"invalid side: {self.side}")
        if not 0.0 <= self.strength <= 1.0:
            raise ValueError(f"strength must be in [0, 1], got {self.strength}")
        if self.stop_pct <= 0 or self.target_pct <= 0:
            raise ValueError("stop_pct and target_pct must be positive")
