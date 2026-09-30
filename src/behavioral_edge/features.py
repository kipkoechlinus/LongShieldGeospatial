"""Microstructure features that separate emotion from noise."""

from __future__ import annotations

import numpy as np
import pandas as pd


def closing_location_value(df: pd.DataFrame) -> pd.Series:
    """
    Where the close sits in the bar's range.
    1 = closed on the high (buyers in control), 0 = closed on the low.
    Humans leave fingerprints here after panic and FOMO.
    """
    high = df["high"]
    low = df["low"]
    span = (high - low).replace(0, np.nan)
    return ((df["close"] - low) / span).clip(0, 1).fillna(0.5)


def realized_vol(close: pd.Series, window: int = 20) -> pd.Series:
    return close.pct_change().rolling(window).std(ddof=0) * np.sqrt(252)


def herd_intensity(df: pd.DataFrame, window: int = 20) -> pd.Series:
    """
    Composite: |return| * volume z-score.
    Spikes when the crowd is moving together — our hunting ground.
    """
    ret = df["close"].pct_change().abs()
    vol = df["volume"]
    vol_mean = vol.rolling(window).mean()
    vol_std = vol.rolling(window).std(ddof=0).replace(0, np.nan)
    vol_z = (vol - vol_mean) / vol_std
    return (ret * vol_z.clip(lower=0)).fillna(0.0)


def trend_slope(close: pd.Series, window: int = 20) -> pd.Series:
    """Normalized slope of close vs rolling mean — regime direction."""
    ma = close.rolling(window).mean()
    return ((close - ma) / ma.replace(0, np.nan)).fillna(0.0)


def range_quality(df: pd.DataFrame, window: int = 20) -> pd.Series:
    """
    Today's range vs recent average. Extremely wide bars = emotion.
    Extremely tight bars after emotion = coiled continuation / trap setups.
    """
    rng = (df["high"] - df["low"]) / df["close"].replace(0, np.nan)
    avg = rng.rolling(window).mean().replace(0, np.nan)
    return (rng / avg).fillna(1.0)
