"""Synthetic OHLCV with planted behavioral regimes for demos / tests."""

from __future__ import annotations

import numpy as np
import pandas as pd


def make_behavioral_tape(
    n: int = 180,
    seed: int = 42,
    start_price: float = 100.0,
) -> pd.DataFrame:
    """
    Build a price path that includes:
    - quiet grind
    - FOMO vertical + climax volume
    - panic capitulation
    - trend with disposition-style shallow pullback
    - failed breakout / breakdown around anchors
    """
    rng = np.random.default_rng(seed)
    closes = [start_price]
    volumes = [1_000_000.0]

    for t in range(1, n):
        # Regime bookmarks (deterministic story, mild noise)
        if 40 <= t < 48:
            # FOMO melt-up
            shock = 0.028 + abs(rng.normal(0, 0.004))
            vol = 2_400_000 + abs(rng.normal(0, 200_000))
        elif t == 48:
            shock = 0.045
            vol = 4_500_000
        elif 90 <= t < 95:
            # Panic waterfall
            shock = -0.035 - abs(rng.normal(0, 0.005))
            vol = 3_200_000 + abs(rng.normal(0, 250_000))
        elif t == 95:
            shock = -0.055
            vol = 5_500_000
        elif 120 <= t < 130:
            # Uptrend grind
            shock = 0.006 + rng.normal(0, 0.002)
            vol = 1_100_000
        elif 130 <= t < 135:
            # Disposition pullback on dry volume
            shock = -0.012 + rng.normal(0, 0.002)
            vol = 700_000
        elif t == 135:
            shock = 0.008
            vol = 750_000
        elif t == 150:
            # Spike above prior range then fail (bull trap)
            shock = 0.02
            vol = 2_000_000
        elif t == 151:
            shock = -0.025
            vol = 2_200_000
        else:
            shock = rng.normal(0.0005, 0.008)
            vol = 1_000_000 * (1 + abs(rng.normal(0, 0.15)))

        closes.append(closes[-1] * (1 + shock))
        volumes.append(float(vol))

    close = np.array(closes)
    # Build OHLC around close
    noise = np.abs(rng.normal(0.004, 0.002, size=n))
    high = close * (1 + noise)
    low = close * (1 - noise)
    open_ = np.r_[close[0], close[:-1]]
    # Force anchor bull-trap geometry around t=150
    if n > 151:
        window_high = high[130:150].max()
        high[150] = window_high * 1.01
        close[150] = window_high * 1.005
        open_[150] = window_high * 0.998
        high[151] = window_high * 1.002
        close[151] = window_high * 0.99
        low[151] = window_high * 0.985

    idx = pd.bdate_range("2024-01-02", periods=n)
    return pd.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volumes,
        },
        index=idx,
    )
