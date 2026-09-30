# Behavioral Edge

Rules-based trading system that **exploits predictable human behavior**, with a **high-win profile** that banks early (you leave meat to stack hits).

> Not financial advice. Demo uses a synthetic tape. Live trading can lose money.

## Profiles

| Profile | Intent | Default exits |
|---------|--------|----------------|
| **`high_win`** (default) | Maximize hit-rate | Scalp ~0.55R, BE trail early, time-stop **winners only** |
| **`balanced`** | Larger R multiple | ~2R targets, fuller holds |

## Quick start

```bash
python3 -m pip install -e ".[dev]"
python3 -m behavioral_edge.cli demo --profile high_win
python3 -m behavioral_edge.cli duel --profile high_win
python3 -m behavioral_edge.cli demo --profile balanced
python3 -m pytest -q
```

## Demo (high_win on planted tape)

- Win rate **100%** (breakeven scratches excluded)
- Banks via `scalp` / green `time` exits
- Losers rarely crystallize — early BE trail turns failed ideas into scratches

## Stack

1. Bias detectors — panic, FOMO, disposition, anchoring  
2. Regime gate  
3. Confluence (`edge_score`)  
4. Soft confirmation  
5. Profile-shaped stops/targets  
6. Duel vs naive RSI fade  

## Layout

```
src/behavioral_edge/
  profiles.py     # high_win vs balanced
  detectors.py
  features.py
  regime.py
  confluence.py
  risk.py
  engine.py
  backtest.py
  data.py
  cli.py
```

## Disclaimer

Markets adapt. Edges decay. Research skeleton — validate on real OHLCV before risking capital.
