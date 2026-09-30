# Behavioral Edge

Rules-based trading system that **exploits predictable human behavior** — panic, FOMO, premature profit-taking, and anchoring — then filters with **regime + confluence + confirmation** so vibes-only algos get smoked.

> Not financial advice. Demo uses a synthetic tape with planted behavioral regimes. Live trading can lose money.

## Why this beats a generic Claude starter pack

Most LLM algos ship: *“fade RSI, fixed stop, pray.”*  
We ship a stack:

1. **Bias detectors** — map each trade to a documented human failure mode  
2. **Regime gate** — don’t run mean-reversion logic in the wrong weather  
3. **Confluence** — CLV + herd intensity + range quality must agree  
4. **Confirmation entry** — no blind next-open fills  
5. **Edge-scaled risk** — size from `edge_score`, not ego  
6. **Head-to-head duel** — `behavioral-edge duel` vs naive RSI fade on the same tape

## Biases harvested

| Bias | What humans do | What the algo does |
|------|----------------|--------------------|
| **Loss aversion / panic** | Dump together | Fade **volume climax** washouts |
| **FOMO / herding** | Chase late | Short **blow-off tops** |
| **Disposition effect** | Sell winners early | Buy **dry-volume dips** in uptrends |
| **Anchoring** | Worship prior highs/lows | Fade **failed breaks** |

## Quick start

```bash
python3 -m pip install -e ".[dev]"
python3 -m behavioral_edge.cli scan
python3 -m behavioral_edge.cli demo
python3 -m behavioral_edge.cli duel
python3 -m pytest -q
```

## Layout

```
src/behavioral_edge/
  detectors.py    # bias → raw signal
  features.py     # CLV, herd intensity, vol, range quality
  regime.py       # weather filter
  confluence.py   # microstructure re-score → edge_score
  risk.py         # mechanical sizing
  engine.py       # scan + plan
  backtest.py     # confirmation entries + duel baseline
  data.py         # synthetic behavioral tape
  cli.py          # demo / scan / duel
```

## Disclaimer

Markets adapt. Edges decay. Research skeleton — not a money printer. Validate on real OHLCV before risking capital.
