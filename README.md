# Behavioral Edge

Rules-based trading system that **exploits predictable human behavior** — panic, FOMO, premature profit-taking, and anchoring — instead of pretending to forecast the future.

> Not financial advice. Demo uses a synthetic tape with planted behavioral regimes so you can see the logic fire. Live trading can lose money. Size small, stay mechanical.

## The edge (human bugs we harvest)

| Bias | What humans do | What the algo does |
|------|----------------|--------------------|
| **Loss aversion / panic** | Hold losers until forced to dump together | `panic_capitulation` — fade washouts after volume climax + RSI crush |
| **FOMO / herding** | Chase vertical moves late | `fomo_exhaustion` — short blow-off tops with euphoric volume |
| **Disposition effect** | Sell winners too early in trends | `disposition_continuation` — buy shallow dry-volume pullbacks in uptrends |
| **Anchoring** | Treat prior highs/lows as “truth” | `anchor_rejection` — fade failed breakouts/breakdowns (bull/bear traps) |

Risk module is the anti-human layer: fixed fractional risk, conviction-scaled but capped, hard max open risk, no revenge sizing.

## Quick start

```bash
python -m pip install -e ".[dev]"
behavioral-edge scan
behavioral-edge demo
behavioral-edge demo --json
pytest -q
```

## Layout

```
src/behavioral_edge/
  detectors.py   # bias → signal
  risk.py        # mechanical sizing
  engine.py      # scan + plan
  backtest.py    # next-open entry, stop/target/time exit
  data.py        # synthetic behavioral tape
  cli.py         # demo / scan
```

## Playbook (how to use this like a killer)

1. **One thesis per trade** — strongest signal only; no stacking narratives.
2. **Define pain first** — stop % comes from the signal; size from the stop.
3. **Never negotiate with emotion** — if strength < threshold or risk caps bind, skip.
4. **Journal the bias** — tag every trade with which human mistake you harvested.
5. **Promote to live only after** you swap the synthetic tape for real OHLCV and validate out-of-sample.

## Disclaimer

Markets adapt. Edges decay. This repo is a research skeleton for behavioral microstructure ideas — not a guaranteed money printer.
