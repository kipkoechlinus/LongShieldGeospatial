# Behavioral Edge

Harvest human behavioral bugs. **Hustle mode** clears and beats the $100/day bar vs pressed Muse/Claude/Grok stacks.

> Not financial advice. Synthetic demos. Live trading can lose money.

## Hustle league ($/day)

```bash
python3 -m pip install -e ".[dev]"
python3 -m behavioral_edge.cli hustle
python3 -m behavioral_edge.cli hustle --stress
python3 -m pytest -q
```

### Snapshot (seed 42, $100k)

| Fighter | WR | $/day |
|---------|----|-------|
| **behavioral_edge:hustle** | **91.7%** | **~$168** |
| claude_rsi_pressed | 50% | ~$120 |
| grok_sma_rsi_pressed | 47% | ~$22 |
| muse_macd_bb_pressed | 0% | $0 |

**Stress:** 8/8 seeds clear $100/day · 8/8 league wins · avg **~$179/day**

## Profiles

| Profile | Job |
|---------|-----|
| **`hustle`** | Default — $/day mode (4.5% risk, denser tape) |
| `predator` | Rival-hardened quality |
| `high_win` | Max hit-rate scalps |
| `balanced` | Larger R |

## Disclaimer

Edges decay. Validate on real OHLCV before risking capital.
