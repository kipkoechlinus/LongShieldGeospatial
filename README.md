# Behavioral Edge

Harvest human behavioral bugs. Hardened to beat Muse/Grok-class indicator stacks across many seeds — not just one lucky tape.

> Not financial advice. Synthetic demos. Live trading can lose money.

## v5 Predator (hardened)

- Cleaner trap detector (pierce + CLV + volume)
- Meta-labeler: climax-aware vol bands, Muse+Grok crowding fade, weak-anchor veto
- Scale-out (bank 60%, runner with BE)
- Conflict veto, cooldown, signal gap
- **Stress CLI** — multi-seed arena

```bash
python3 -m pip install -e ".[dev]"
python3 -m behavioral_edge.cli arena --profile predator
python3 -m behavioral_edge.cli stress --profile predator
python3 -m pytest -q
```

### Stress snapshot (10 seeds)

| Metric | Result |
|--------|--------|
| Arena #1 wins | **7/10 (70%)** |
| Beat Muse+Grok | **8/10 (80%)** |
| Avg win rate | **~91%** |
| Avg PnL | **positive** |

Muse = MACD+BB · Grok = SMA50+RSI · also ranked vs classic RSI fade.

## Profiles

| Profile | Job |
|---------|-----|
| `predator` | Default — arena / rival-hardened |
| `high_win` | Max hit-rate scalps |
| `balanced` | Larger R (includes disposition dips) |

## Disclaimer

Edges decay. Validate on real OHLCV before risking capital.
