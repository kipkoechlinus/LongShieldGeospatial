# Behavioral Edge

Harvest human behavioral bugs. **Hustle mode** clears and beats the $100/day bar vs pressed Muse/Claude/Grok stacks.

> Not financial advice. Synthetic demos. Live trading can lose money.

## Hustle league ($/day)

```bash
python3 -m pip install -e ".[dev,live]"
python3 -m behavioral_edge.cli hustle
python3 -m behavioral_edge.cli hustle --stress
python3 -m behavioral_edge.cli receipt --out receipts/hustle-receipt.json
python3 -m behavioral_edge.cli compare --ours receipts/hustle-receipt.json --theirs receipts/RIVAL_RECEIPT_TEMPLATE.json
python3 -m behavioral_edge.cli live --months 4 --profile hustle --out receipts/live-4mo-hustle.json
python3 -m pytest -q
```

### Receipts (reputation mode)

When rivals bring numbers, don’t argue — **compare sealed receipts**.

1. We issue a sealed hustle receipt (`receipt`) with git SHA + sha256 seal + methodology  
2. They fill `receipts/RIVAL_RECEIPT_TEMPLATE.json` (or their full receipt)  
3. `compare` checks methodology first, dollars second  

**Our claims are SYNTHETIC-tape results.** Live broker PnL is a different sport — flags will say so.

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

## Live window (last 4 months, yfinance)

Detectors are **σ-adaptive** (20d return std): fixed −3% panic gates were silent on real SPY.

```bash
python3 -m behavioral_edge.cli live --months 4 --profile hustle
```

**Hustle snapshot** (score `2026-05-30` → `2026-09-30`, $100k/symbol, independent books):

| Symbol | Trades | WR | $/day | PnL |
|--------|--------|----|-------|-----|
| SPY | 2 | 100% | **~$114** | ~$9.6k |
| NVDA | 1 | 100% | ~$59 | ~$5.0k |
| IWM | 2 | 0% | −$61 | −$5.1k |
| QQQ / AAPL | 0 | — | $0 | $0 |

Avg across symbols **~$22/day** — does **not** clear $100/day on this real tape. Best single name (SPY) does. Receipts: `receipts/live-4mo-*.json`.

## Disclaimer

Edges decay. Synthetic hustle ≠ live broker PnL. Validate on real OHLCV before risking capital.
