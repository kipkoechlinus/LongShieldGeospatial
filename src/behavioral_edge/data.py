"""Synthetic OHLCV with planted behavioral regimes for demos / tests."""

from __future__ import annotations

import numpy as np
import pandas as pd


def make_behavioral_tape(
    n: int = 220,
    seed: int = 42,
    start_price: float = 100.0,
) -> pd.DataFrame:
    """
    Build a price path that includes behavioral regimes AND the short
    mean-reversion follow-through that high-win scalps are designed to bank.
    """
    rng = np.random.default_rng(seed)
    closes = [start_price]
    volumes = [1_000_000.0]
    # Keep caller length; trap bookmarks simply no-op if out of range

    for t in range(1, n):
        if 40 <= t < 48:
            shock = 0.028 + abs(rng.normal(0, 0.003))
            vol = 2_400_000 + abs(rng.normal(0, 150_000))
        elif t == 48:
            shock = 0.045
            vol = 4_500_000
        elif 49 <= t <= 52:
            # FOMO unwind — early short scalps get paid
            shock = -0.018 - abs(rng.normal(0, 0.003))
            vol = 2_800_000
        elif 90 <= t < 95:
            shock = -0.035 - abs(rng.normal(0, 0.004))
            vol = 3_200_000 + abs(rng.normal(0, 200_000))
        elif t == 95:
            shock = -0.055
            vol = 5_500_000
        elif 96 <= t <= 100:
            # Capitulation bounce — long scalp gets paid
            shock = 0.016 + abs(rng.normal(0, 0.003))
            vol = 2_000_000
        elif 120 <= t < 130:
            shock = 0.007 + rng.normal(0, 0.0015)
            vol = 1_100_000
        elif 130 <= t < 134:
            shock = -0.011 + rng.normal(0, 0.0015)
            vol = 680_000
        elif t == 134:
            shock = -0.01
            vol = 650_000
        elif 135 <= t <= 138:
            # Disposition reclaim
            shock = 0.01 + abs(rng.normal(0, 0.002))
            vol = 900_000
        elif t in {70, 110, 160}:
            # Fewer, cleaner bull-trap days
            shock = 0.01 + abs(rng.normal(0, 0.001))
            vol = 2_200_000
        elif t in {71, 111, 161}:
            shock = -0.018 - abs(rng.normal(0, 0.002))
            vol = 2_400_000
        elif t in {85, 145}:
            # Cleaner bear-trap days
            shock = -0.01 - abs(rng.normal(0, 0.001))
            vol = 2_100_000
        elif t in {86, 146}:
            shock = 0.017 + abs(rng.normal(0, 0.002))
            vol = 2_300_000
        else:
            shock = rng.normal(0.0004, 0.0045)
            vol = 1_000_000 * (1 + abs(rng.normal(0, 0.12)))


        closes.append(max(1.0, closes[-1] * (1 + shock)))
        volumes.append(float(vol))

    close = np.array(closes, dtype=float)
    noise = np.abs(rng.normal(0.0035, 0.0015, size=n))
    high = close * (1 + noise)
    low = close * (1 - noise)
    open_ = np.r_[close[0], close[:-1]]

    # Carve clean OHLC for trap pairs — decisive rejection + follow-through
    for spike, fail, direction in [
        (70, 71, "bull"),
        (110, 111, "bull"),
        (160, 161, "bull"),
        (85, 86, "bear"),
        (145, 146, "bear"),
    ]:
        if fail >= n:
            continue
        volumes[spike] = max(volumes[spike], 2_200_000)
        volumes[fail] = max(volumes[fail], 2_300_000)
        if direction == "bull":
            prior = high[max(0, spike - 20) : spike].max()
            high[spike] = prior * 1.014
            open_[spike] = prior * 0.999
            close[spike] = prior * 0.995  # close firmly back inside
            low[spike] = min(low[spike], close[spike] * 0.992)
            open_[fail] = close[spike]
            close[fail] = close[spike] * 0.980
            high[fail] = max(open_[fail], close[fail]) * 1.001
            low[fail] = close[fail] * 0.996
        else:
            prior = low[max(0, spike - 20) : spike].min()
            low[spike] = prior * 0.986
            open_[spike] = prior * 1.001
            close[spike] = prior * 1.005
            high[spike] = max(high[spike], close[spike] * 1.006)
            open_[fail] = close[spike]
            close[fail] = close[spike] * 1.020
            low[fail] = min(open_[fail], close[fail]) * 0.998
            high[fail] = close[fail] * 1.002

    # FOMO climax bar geometry
    if n > 52:
        high[48] = close[48] * 1.01
        low[48] = close[47] * 0.995
        open_[48] = close[47]
        for j in range(49, 53):
            open_[j] = close[j - 1]
            high[j] = max(open_[j], close[j]) * 1.002
            low[j] = min(open_[j], close[j]) * 0.998

    # Panic climax + bounce geometry
    if n > 100:
        open_[95] = close[94]
        low[95] = close[95] * 0.99
        high[95] = open_[95] * 1.002
        for j in range(96, 101):
            open_[j] = close[j - 1]
            high[j] = max(open_[j], close[j]) * 1.003
            low[j] = min(open_[j], close[j]) * 0.998

    idx = pd.bdate_range("2024-01-02", periods=n)
    return pd.DataFrame(
        {
            "open": open_,
            "high": np.maximum(high, np.maximum(open_, close)),
            "low": np.minimum(low, np.minimum(open_, close)),
            "close": close,
            "volume": volumes,
        },
        index=idx,
    )
