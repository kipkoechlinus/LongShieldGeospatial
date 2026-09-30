"""CLI: scan tape, print behavioral edge plans, run demo backtest."""

from __future__ import annotations

import argparse
import json

from behavioral_edge.backtest import run_backtest
from behavioral_edge.data import make_behavioral_tape
from behavioral_edge.engine import BehavioralEdgeEngine
from behavioral_edge.risk import RiskConfig


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="behavioral-edge",
        description="Exploit predictable human market behavior with mechanical rules.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    demo = sub.add_parser("demo", help="Run synthetic-tape demo + backtest")
    demo.add_argument("--bars", type=int, default=180)
    demo.add_argument("--equity", type=float, default=100_000)
    demo.add_argument("--json", action="store_true")

    scan = sub.add_parser("scan", help="List signals on the synthetic demo tape")
    scan.add_argument("--bars", type=int, default=180)

    args = parser.parse_args(argv)
    risk = RiskConfig(account_equity=getattr(args, "equity", 100_000))
    engine = BehavioralEdgeEngine(risk=risk)
    df = make_behavioral_tape(n=args.bars)

    if args.cmd == "scan":
        signals = engine.scan_history(df)
        for s in signals:
            ts = df.index[s.bar_index]
            print(
                f"{ts.date()}  {s.kind.value:28}  {s.side:5}  "
                f"str={s.strength:.2f}  {s.reason}"
            )
        print(f"\n{len(signals)} behavioral signals")
        return 0

    if args.cmd == "demo":
        signals = engine.scan_history(df)
        result = run_backtest(df, engine=engine)
        payload = {
            "signals": len(signals),
            "trades": len(result.trades),
            "win_rate": round(result.win_rate, 3),
            "total_pnl": round(result.total_pnl, 2),
            "final_equity": round(result.equity_curve[-1], 2),
            "sample_reasons": [s.reason for s in signals[:5]],
            "trade_log": [
                {
                    "side": t.side,
                    "kind": t.signal.kind.value,
                    "entry": round(t.entry, 2),
                    "exit": round(t.exit or 0, 2),
                    "pnl": round(t.pnl or 0, 2),
                    "exit_reason": t.exit_reason,
                    "thesis": t.signal.reason,
                }
                for t in result.trades
            ],
        }
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print("BEHAVIORAL EDGE — demo on synthetic human-bias tape")
            print("=" * 56)
            print(f"Signals fired : {payload['signals']}")
            print(f"Trades taken  : {payload['trades']}")
            print(f"Win rate      : {payload['win_rate']:.1%}")
            print(f"Total PnL     : ${payload['total_pnl']:,.2f}")
            print(f"Final equity  : ${payload['final_equity']:,.2f}")
            print("\nCore biases we harvest:")
            print("  • Panic capitulation  — fade forced sellers")
            print("  • FOMO exhaustion     — fade late herd")
            print("  • Disposition dips    — buy premature profit-taking")
            print("  • Anchor rejection    — fade failed breaks at magnets")
            if payload["trade_log"]:
                print("\nTrades:")
                for t in payload["trade_log"]:
                    print(
                        f"  {t['side']:5} {t['kind']:28} "
                        f"PnL=${t['pnl']:>8,.2f}  ({t['exit_reason']})"
                    )
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
