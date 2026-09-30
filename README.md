# Behavioral Edge

Rules-based trading system that **harvests human behavioral bugs**, then beats Muse/Grok-class indicator stacks in a measured arena.

> Not financial advice. Synthetic demo tape. Live trading can lose money.

## Why we win the arena

Typical AI starters ship indicators (RSI fade, MACD+BB, SMA+RSI). We ship:

1. **Bias detectors** — panic / FOMO / disposition / anchoring  
2. **Regime + confluence** — weather + microstructure must agree  
3. **Meta-labeler** — vol sweet-spot, ATR stops, **anti-rival fade** (boost when Muse/Grok momentum is crowded the wrong way)  
4. **Vol-targeted risk** — shrink size when realized vol explodes  
5. **Predator / high_win exits** — bank early, BE trail, never time-stop a loser  

```bash
python3 -m pip install -e ".[dev]"
python3 -m behavioral_edge.cli arena --profile predator
python3 -m behavioral_edge.cli demo --profile predator
python3 -m behavioral_edge.cli demo --profile high_win
python3 -m pytest -q
```

## Profiles

| Profile | Job |
|---------|-----|
| **`predator`** (default) | Arena mode — meta + ATR + anti-rival |
| **`high_win`** | Max hit-rate scalps |
| **`balanced`** | Larger R multiples |

## Arena fighters

- `behavioral_edge:*` — us  
- `muse_macd_bb` — MACD cross + Bollinger touch  
- `grok_sma_rsi` — SMA50 trend + RSI pullback  
- `naive_rsi_fade` — classic 30/70 fade  

## Disclaimer

Markets adapt. Edges decay. Research skeleton only.
