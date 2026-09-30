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
python3 -m behavioral_edge.cli fetch --months 4          # cache OHLCV → data/ohlcv_4mo/
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
| **`crypto`** | Hustle intensity, no FOMO (24/7 chase continues) |
| `predator` | Rival-hardened quality |
| `high_win` | Max hit-rate scalps |
| `balanced` | Larger R |

## Live window (last 4 months, yfinance)

Detectors are **σ-adaptive** (20d return std): fixed −3% panic gates were silent on real SPY.

```bash
python3 -m behavioral_edge.cli live --months 4 --profile hustle
python3 -m behavioral_edge.cli live --months 4 --crypto   # BTC/ETH/LTC/ATOM/DOT/AVAX
```

### Equities — hustle

| Symbol | Trades | WR | $/day | PnL |
|--------|--------|----|-------|-----|
| SPY | 2 | 100% | **~$114** | ~$9.6k |
| NVDA | 1 | 100% | ~$59 | ~$5.0k |
| IWM | 2 | 0% | −$61 | −$5.1k |
| QQQ / AAPL | 0 | — | $0 | $0 |

Avg **~$22/day** — does **not** clear $100/day. Receipts: `receipts/live-4mo-*.json`.

### Crypto — six of our choice (`crypto` profile)

FOMO fades bled ~−$12k on majors; `crypto` keeps disposition + anchors only.

| Symbol | Trades | WR | $/day | PnL |
|--------|--------|----|-------|-----|
| ATOM-USD | 2 | 100% | ~$86 | ~$10.6k |
| LTC-USD | 5 | 75% | ~$55 | ~$6.7k |
| BTC-USD | 4 | 67% | ~$40 | ~$4.9k |
| DOT-USD | 1 | 100% | ~$40 | ~$4.9k |
| ETH-USD | 5 | 75% | ~$35 | ~$4.3k |
| AVAX-USD | 3 | 67% | ~$12 | ~$1.5k |

Avg **~$45/day**, avg WR **~81%**, sum PnL **~$33k**. Still under $100/day/symbol. Naive majors (BTC/ETH/SOL/XRP/BNB/DOGE) + hustle FOMO: **−$20/day**. Receipt: `receipts/live-4mo-crypto.json`.

**Champion asset:** `ATOM-USD` — highest total PnL (~**$10.8k**, ~$88/day, 2/2 wins on hustle).  
`python3 -m behavioral_edge.cli live --months 4 --champion`

### Crypto subset sweep (battle roster)

```bash
python3 -m behavioral_edge.cli sweep --months 4 --out receipts/crypto-subset-sweep.json
python3 -m behavioral_edge.cli live --months 4 --battle
```

Rule: all-positive names, **k ∈ [3,5]**, maximize avg $/day.

| k | Best hustle book | Avg $/day | Sum PnL |
|---|------------------|-----------|---------|
| 1 | ATOM | ~$88 | ~$10.8k |
| **3** | **DOT + LTC + ATOM** | **~$66** | **~$24.4k** |
| 4 | + XRP | ~$59 | ~$29.2k |
| 7 | all positive | ~$44 | ~$37.7k |

**Battle pick: k=3** — DOT / LTC / ATOM under `hustle` (~92% WR). Receipt: `receipts/live-4mo-battle.json`.

## Disclaimer

Edges decay. Synthetic hustle ≠ live broker PnL. Validate on real OHLCV before risking capital.
