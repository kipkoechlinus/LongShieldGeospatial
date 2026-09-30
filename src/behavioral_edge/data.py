"""Synthetic OHLCV with planted behavioral regimes for demos / tests."""

from __future__ import annotations

import numpy as np
import pandas as pd


def _regime_shock(t: int, rng: np.random.Generator) -> tuple[float, float]:
    """Map local bar index (0..cycle) → (shock, volume)."""
    # ~70-bar cycle — denser emotion for $/day frequency
    c = t % 70
    if 8 <= c < 16:
        return 0.028 + abs(rng.normal(0, 0.003)), 2_400_000 + abs(rng.normal(0, 150_000))
    if c == 16:
        return 0.045, 4_500_000.0
    if 17 <= c <= 20:
        return -0.018 - abs(rng.normal(0, 0.003)), 2_800_000.0
    if 35 <= c < 40:
        return -0.035 - abs(rng.normal(0, 0.004)), 3_200_000 + abs(rng.normal(0, 200_000))
    if c == 40:
        return -0.055, 5_500_000.0
    if 41 <= c <= 45:
        return 0.016 + abs(rng.normal(0, 0.003)), 2_000_000.0
    if 50 <= c < 58:
        return 0.007 + rng.normal(0, 0.0015), 1_100_000.0
    if 58 <= c < 62:
        return -0.011 + rng.normal(0, 0.0015), 680_000.0
    if c == 62:
        return -0.01, 650_000.0
    if 63 <= c <= 66:
        return 0.01 + abs(rng.normal(0, 0.002)), 900_000.0
    if c in {25, 55}:
        return 0.01 + abs(rng.normal(0, 0.001)), 2_200_000.0
    if c in {26, 56}:
        return -0.018 - abs(rng.normal(0, 0.002)), 2_400_000.0
    if c in {30, 60}:
        return -0.01 - abs(rng.normal(0, 0.001)), 2_100_000.0
    if c in {31, 61}:
        return 0.017 + abs(rng.normal(0, 0.002)), 2_300_000.0
    return rng.normal(0.0004, 0.0045), 1_000_000 * (1 + abs(rng.normal(0, 0.12)))


def _carve_trap(
    high, low, open_, close, volumes, spike: int, fail: int, direction: str
) -> None:
    n = len(close)
    if fail >= n:
        return
    # Punch volume above the local mean so z-score clears the detector
    local = float(np.mean(volumes[max(0, spike - 20) : spike]) or 1_000_000)
    volumes[spike] = max(volumes[spike], local * 2.8, 3_500_000)
    volumes[fail] = max(volumes[fail], local * 2.5, 3_200_000)
    if direction == "bull":
        # Failed breakout: pierce high, close back inside near the lows (low CLV)
        prior = float(high[max(0, spike - 20) : spike].max())
        high[spike] = prior * 1.014
        open_[spike] = prior * 1.001
        close[spike] = prior * 0.994
        low[spike] = close[spike] * 0.996
        open_[fail] = close[spike]
        close[fail] = close[spike] * 0.978
        high[fail] = max(open_[fail], close[fail]) * 1.001
        low[fail] = close[fail] * 0.996
    else:
        # Failed breakdown: pierce low, close back inside near the highs (high CLV)
        prior = float(low[max(0, spike - 20) : spike].min())
        low[spike] = prior * 0.986
        open_[spike] = prior * 0.999
        close[spike] = prior * 1.006
        high[spike] = close[spike] * 1.004
        open_[fail] = close[spike]
        close[fail] = close[spike] * 1.022
        low[fail] = min(open_[fail], close[fail]) * 0.998
        high[fail] = close[fail] * 1.002


def make_behavioral_tape(
    n: int = 220,
    seed: int = 42,
    start_price: float = 100.0,
) -> pd.DataFrame:
    """
    Build a price path with repeating behavioral cycles so hustle mode
    has enough frequency to compete on $/day — not just one FOMO and done.
    """
    rng = np.random.default_rng(seed)
    closes = [start_price]
    volumes = [1_000_000.0]

    for t in range(1, n):
        shock, vol = _regime_shock(t, rng)
        closes.append(max(1.0, closes[-1] * (1 + shock)))
        volumes.append(float(vol))

    close = np.array(closes, dtype=float)
    noise = np.abs(rng.normal(0.0035, 0.0015, size=n))
    high = close * (1 + noise)
    low = close * (1 - noise)
    open_ = np.r_[close[0], close[:-1]]

    # Carve traps + climax geometry in every cycle
    cycle = 70
    for base in range(0, n, cycle):
        for spike, fail, direction in [
            (base + 25, base + 26, "bull"),
            (base + 55, base + 56, "bull"),
            (base + 30, base + 31, "bear"),
            (base + 60, base + 61, "bear"),
        ]:
            _carve_trap(high, low, open_, close, volumes, spike, fail, direction)

        # FOMO climax at local 16
        c16 = base + 16
        if c16 + 4 < n and c16 > 0:
            high[c16] = close[c16] * 1.01
            low[c16] = close[c16 - 1] * 0.995
            open_[c16] = close[c16 - 1]
            for j in range(c16 + 1, min(c16 + 5, n)):
                open_[j] = close[j - 1]
                high[j] = max(open_[j], close[j]) * 1.002
                low[j] = min(open_[j], close[j]) * 0.998

        # Panic climax at local 40
        c40 = base + 40
        if c40 + 5 < n and c40 > 0:
            open_[c40] = close[c40 - 1]
            low[c40] = close[c40] * 0.99
            high[c40] = open_[c40] * 1.002
            for j in range(c40 + 1, min(c40 + 6, n)):
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
