"""Real-market OHLCV loaders (yfinance)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd


def fetch_ohlcv(
    symbol: str,
    *,
    start: str | datetime,
    end: str | datetime | None = None,
) -> pd.DataFrame:
    """Download daily OHLCV and normalize columns to open/high/low/close/volume."""
    import yfinance as yf

    df = yf.download(
        symbol,
        start=pd.Timestamp(start).strftime("%Y-%m-%d"),
        end=None if end is None else pd.Timestamp(end).strftime("%Y-%m-%d"),
        progress=False,
        auto_adjust=True,
        threads=False,
    )
    if df.empty:
        raise RuntimeError(f"no data for {symbol}")

    # yfinance may return MultiIndex columns
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0].lower() for c in df.columns]
    else:
        df.columns = [str(c).lower() for c in df.columns]

    need = ["open", "high", "low", "close", "volume"]
    missing = [c for c in need if c not in df.columns]
    if missing:
        raise RuntimeError(f"{symbol} missing columns {missing}: got {list(df.columns)}")

    out = df[need].copy()
    out = out.dropna()
    out.index = pd.to_datetime(out.index).tz_localize(None)
    return out


def last_n_months_window(
    months: int = 4,
    *,
    as_of: datetime | None = None,
    warmup_days: int = 90,
) -> tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp]:
    """
    Return (fetch_start, score_start, end).

    fetch_start includes warmup so indicators aren't cold on day 1 of the
    scored window.
    """
    end = pd.Timestamp(as_of or datetime.utcnow()).normalize()
    score_start = (end - pd.DateOffset(months=months)).normalize()
    fetch_start = score_start - timedelta(days=warmup_days)
    return fetch_start, score_start, end
