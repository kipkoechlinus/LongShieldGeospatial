"""Real-market OHLCV loaders (yfinance) + local CSV cache."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

DEFAULT_CACHE_DIR = Path("data/ohlcv_4mo")


def fetch_ohlcv(
    symbol: str,
    *,
    start: str | datetime,
    end: str | datetime | None = None,
    cache_dir: str | Path | None = None,
    prefer_cache: bool = True,
) -> pd.DataFrame:
    """
    Download daily OHLCV and normalize columns to open/high/low/close/volume.

    When prefer_cache is True and a CSV exists under cache_dir, load that
    slice instead of hitting the network (reproducible live receipts).
    """
    cache = Path(cache_dir) if cache_dir is not None else DEFAULT_CACHE_DIR
    cached = cache / f"{symbol}.csv"
    if prefer_cache and cached.exists():
        return load_cached_ohlcv(cached, start=start, end=end)

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


def load_cached_ohlcv(
    path: str | Path,
    *,
    start: str | datetime | None = None,
    end: str | datetime | None = None,
) -> pd.DataFrame:
    """Read a cached OHLCV CSV and optionally slice by [start, end)."""
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    df.columns = [str(c).lower() for c in df.columns]
    need = ["open", "high", "low", "close", "volume"]
    missing = [c for c in need if c not in df.columns]
    if missing:
        raise RuntimeError(f"{path} missing columns {missing}")
    out = df[need].dropna().copy()
    out.index = pd.to_datetime(out.index).tz_localize(None)
    if start is not None:
        out = out.loc[out.index >= pd.Timestamp(start)]
    if end is not None:
        out = out.loc[out.index < pd.Timestamp(end)]
    if out.empty:
        raise RuntimeError(f"no rows in cache {path} for requested window")
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


def fetch_and_cache_window(
    symbols: tuple[str, ...] | list[str],
    *,
    months: int = 4,
    as_of: datetime | None = None,
    cache_dir: str | Path = DEFAULT_CACHE_DIR,
) -> dict:
    """Download the warm-up + scored window for each symbol; write CSVs + manifest."""
    fetch_start, score_start, end = last_n_months_window(months, as_of=as_of)
    out_dir = Path(cache_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    meta: dict = {
        "months": months,
        "fetch_start": str(fetch_start.date()),
        "score_start": str(score_start.date()),
        "end": str(end.date()),
        "symbols": {},
    }
    for sym in symbols:
        df = fetch_ohlcv(
            sym,
            start=fetch_start,
            end=end + pd.Timedelta(days=1),
            prefer_cache=False,
        )
        path = out_dir / f"{sym}.csv"
        df.to_csv(path)
        scored = df.loc[df.index >= score_start]
        meta["symbols"][sym] = {
            "bars_total": int(len(df)),
            "bars_scored": int(len(scored)),
            "first": str(df.index.min().date()),
            "last": str(df.index.max().date()),
            "path": str(path),
        }
    (out_dir / "manifest.json").write_text(json.dumps(meta, indent=2) + "\n")
    return meta
