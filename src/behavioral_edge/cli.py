"""CLI: scan, demo, and head-to-head duel vs naive LLM-style baseline."""

from __future__ import annotations

import argparse
import json

from behavioral_edge.backtest import head_to_head, run_backtest
from behavioral_edge.data import make_behavioral_tape
from behavioral_edge.engine import BehavioralEdgeEngine
from behavioral_edge.profiles import HIGH_WIN, PROFILES
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
    demo.add_argument(
        "--profile",
        choices=sorted(PROFILES),
        default="high_win",
        help="high_win banks early for higher hit-rate; balanced hunts larger R",
    )
    demo.add_argument("--json", action="store_true")

    scan = sub.add_parser("scan", help="List signals on the synthetic demo tape")
    scan.add_argument("--bars", type=int, default=180)
    scan.add_argument("--profile", choices=sorted(PROFILES), default="high_win")

    duel = sub.add_parser(
        "duel",
        help="Head-to-head: behavioral edge vs naive RSI fade",
    )
    duel.add_argument("--bars", type=int, default=180)
    duel.add_argument("--equity", type=float, default=100_000)
    duel.add_argument("--profile", choices=sorted(PROFILES), default="high_win")
    duel.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    profile = PROFILES[getattr(args, "profile", "high_win")]
    risk = RiskConfig(account_equity=getattr(args, "equity", 100_000))
    engine = BehavioralEdgeEngine(risk=risk, profile=profile)
    df = make_behavioral_tape(n=args.bars)

    if args.cmd == "scan":
        signals = engine.scan_history(df)
        for s in signals:
            ts = df.index[s.bar_index]
            print(
                f"{ts.date()}  {s.kind.value:28}  {s.side:5}  "
                f"str={s.strength:.2f} edge={s.edge_score:.2f} conf={s.confluence:.2f}  "
                f"stop={s.stop_pct:.2%} tgt={s.target_pct:.2%}  {s.reason}"
            )
        print(f"\n{len(signals)} signals  profile={profile.name}")
        return 0

    if args.cmd == "demo":
        signals = engine.scan_history(df)
        result = run_backtest(df, engine=engine)
        summary = result.summary()
        payload = {
            **summary,
            "profile": profile.name,
            "signals": len(signals),
            "attribution": result.attribution(),
            "trade_log": [
                {
                    "side": t.side,
                    "kind": t.signal.kind.value,
                    "entry": round(t.entry, 2),
                    "exit": round(t.exit or 0, 2),
                    "pnl": round(t.pnl or 0, 2),
                    "exit_reason": t.exit_reason,
                    "edge": round(t.signal.edge_score, 2),
                    "thesis": t.signal.reason,
                }
                for t in result.trades
            ],
        }
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(f"BEHAVIORAL EDGE — profile={profile.name}")
            print("=" * 56)
            if profile.name == HIGH_WIN.name:
                print("Mode: HIGH WIN — bank early, leave meat, stack hits")
            print(f"Signals fired : {payload['signals']}")
            print(f"Trades taken  : {payload['trades']}")
            print(f"Win rate      : {payload['win_rate']:.1%}  (excl. {payload.get('scratches', 0)} scratches)")
            print(f"Expectancy    : ${payload['expectancy']:,.2f}")
            print(f"Profit factor : {payload['profit_factor']}")
            print(f"Max drawdown  : {payload['max_drawdown']:.2%}")
            print(f"Sharpe-like   : {payload['sharpe_like']}")
            print(f"Total PnL     : ${payload['total_pnl']:,.2f}")
            print(f"Final equity  : ${payload['final_equity']:,.2f}")
            if payload["trade_log"]:
                print("\nTrades:")
                for t in payload["trade_log"]:
                    print(
                        f"  {t['side']:5} {t['kind']:28} "
                        f"edge={t['edge']:.2f}  PnL=${t['pnl']:>8,.2f}  ({t['exit_reason']})"
                    )
        return 0

    if args.cmd == "duel":
        report = head_to_head(df, equity=args.equity, profile=profile)
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            us = report["behavioral_edge"]
            them = report["naive_rsi_fade"]
            print(f"DUEL — profile={report['profile']} vs Naive RSI Fade")
            print("=" * 56)
            print(f"{'metric':<16} {'us':>14} {'naive RSI':>14}")
            for key in (
                "trades",
                "win_rate",
                "expectancy",
                "profit_factor",
                "max_drawdown",
                "sharpe_like",
                "total_pnl",
                "final_equity",
            ):
                print(f"{key:<16} {str(us[key]):>14} {str(them[key]):>14}")
            print("-" * 56)
            us_key = us["label"]
            print(
                f"Composite score  {report['composite_scores'][us_key]:>14} "
                f"{report['composite_scores']['naive_rsi_fade']:>14}"
            )
            print(f"Winner: {report['winner']}  (PnL delta ${report['pnl_edge']:,.2f})")
            if report["attribution"]:
                print("\nOur edge attribution by bias:")
                for kind, stats in report["attribution"].items():
                    print(
                        f"  {kind:28} trades={int(stats['trades'])}  "
                        f"pnl=${stats['pnl']:,.2f}  wr={stats['win_rate']:.0%}"
                    )
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
