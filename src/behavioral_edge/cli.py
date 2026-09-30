"""CLI: scan, demo, duel, and Muse/Grok arena."""

from __future__ import annotations

import argparse
import json

from behavioral_edge.arena import run_arena
from behavioral_edge.backtest import head_to_head, run_backtest
from behavioral_edge.data import make_behavioral_tape
from behavioral_edge.engine import BehavioralEdgeEngine
from behavioral_edge.hustle import run_hustle, run_hustle_stress
from behavioral_edge.profiles import HIGH_WIN, HUSTLE, PREDATOR, PROFILES
from behavioral_edge.receipts import (
    compare_receipts,
    issue_hustle_receipt,
    load_receipt,
    verify_seal,
    write_receipt,
)
from behavioral_edge.risk import RiskConfig
from behavioral_edge.stress import run_stress


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="behavioral-edge",
        description="Exploit predictable human market behavior with mechanical rules.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    demo = sub.add_parser("demo", help="Run synthetic-tape demo + backtest")
    demo.add_argument("--bars", type=int, default=220)
    demo.add_argument("--equity", type=float, default=100_000)
    demo.add_argument(
        "--profile",
        choices=sorted(PROFILES),
        default="hustle",
        help="hustle=$/day mode; predator=arena; high_win=hit-rate; balanced=larger R",
    )
    demo.add_argument("--json", action="store_true")

    scan = sub.add_parser("scan", help="List signals on the synthetic demo tape")
    scan.add_argument("--bars", type=int, default=220)
    scan.add_argument("--profile", choices=sorted(PROFILES), default="predator")

    duel = sub.add_parser("duel", help="vs naive RSI fade")
    duel.add_argument("--bars", type=int, default=220)
    duel.add_argument("--equity", type=float, default=100_000)
    duel.add_argument("--profile", choices=sorted(PROFILES), default="predator")
    duel.add_argument("--json", action="store_true")

    arena = sub.add_parser(
        "arena",
        help="Rank us vs Muse (MACD+BB), Grok (SMA+RSI), and classic RSI",
    )
    arena.add_argument("--bars", type=int, default=220)
    arena.add_argument("--equity", type=float, default=100_000)
    arena.add_argument("--profile", choices=sorted(PROFILES), default="predator")
    arena.add_argument("--json", action="store_true")

    stress = sub.add_parser(
        "stress",
        help="Multi-seed arena stress — prove we don't only win on lucky tape",
    )
    stress.add_argument("--bars", type=int, default=220)
    stress.add_argument("--equity", type=float, default=100_000)
    stress.add_argument("--profile", choices=sorted(PROFILES), default="predator")
    stress.add_argument("--json", action="store_true")

    hustle = sub.add_parser(
        "hustle",
        help="$/day league vs pressed Muse/Claude/Grok stacks (clear the $100/day bar)",
    )
    hustle.add_argument("--bars", type=int, default=320)
    hustle.add_argument("--equity", type=float, default=100_000)
    hustle.add_argument("--seed", type=int, default=42)
    hustle.add_argument("--profile", choices=sorted(PROFILES), default="hustle")
    hustle.add_argument("--stress", action="store_true", help="multi-seed $/day stress")
    hustle.add_argument("--json", action="store_true")

    receipt = sub.add_parser(
        "receipt",
        help="Issue a sealed, reproducible hustle receipt (reputation-grade)",
    )
    receipt.add_argument("--bars", type=int, default=320)
    receipt.add_argument("--equity", type=float, default=100_000)
    receipt.add_argument("--seed", type=int, default=42)
    receipt.add_argument("--profile", choices=sorted(PROFILES), default="hustle")
    receipt.add_argument(
        "--out",
        default="receipts/hustle-receipt.json",
        help="output path for sealed receipt JSON",
    )
    receipt.add_argument("--no-stress", action="store_true")
    receipt.add_argument("--json", action="store_true")

    compare = sub.add_parser(
        "compare",
        help="Bake-off: our sealed receipt vs their receipt JSON",
    )
    compare.add_argument("--ours", required=True, help="path to our sealed receipt")
    compare.add_argument(
        "--theirs",
        required=True,
        help="path to rival receipt JSON (full or simple {name,pnl_per_day,win_rate})",
    )
    compare.add_argument("--metric", default="pnl_per_day")
    compare.add_argument("--json", action="store_true")

    live = sub.add_parser(
        "live",
        help="Backtest on last N months of real yfinance data (warm-up + scored window)",
    )
    live.add_argument("--months", type=int, default=4)
    live.add_argument("--equity", type=float, default=100_000)
    live.add_argument(
        "--profile",
        choices=sorted(PROFILES),
        default="hustle",
    )
    live.add_argument(
        "--symbols",
        default="SPY,QQQ,IWM,AAPL,NVDA",
        help="comma-separated tickers (ignored when --crypto is set)",
    )
    live.add_argument(
        "--crypto",
        action="store_true",
        help="use the built-in 6-name crypto universe (BTC/ETH/LTC/ATOM/DOT/AVAX)",
    )
    live.add_argument(
        "--champion",
        action="store_true",
        help="run only the most profitable live asset (ATOM-USD)",
    )
    live.add_argument(
        "--battle",
        action="store_true",
        help="optimal crypto battle roster from subset sweep (DOT/LTC/ATOM)",
    )
    live.add_argument("--json", action="store_true")
    live.add_argument(
        "--out",
        default="",
        help="optional path to write JSON results",
    )

    sweep = sub.add_parser(
        "sweep",
        help="Brute-force crypto subset sizes; pick battle roster (max avg $/day)",
    )
    sweep.add_argument("--months", type=int, default=4)
    sweep.add_argument("--equity", type=float, default=100_000)
    sweep.add_argument("--json", action="store_true")
    sweep.add_argument(
        "--out",
        default="receipts/crypto-subset-sweep.json",
        help="write full sweep JSON here",
    )

    fetch = sub.add_parser(
        "fetch",
        help="Download last N months of OHLCV (warm-up included) into data/ohlcv_4mo",
    )
    fetch.add_argument("--months", type=int, default=4)
    fetch.add_argument(
        "--symbols",
        default="",
        help="comma-separated tickers (default: equities + crypto six + majors contrast)",
    )
    fetch.add_argument("--crypto", action="store_true", help="crypto six only")
    fetch.add_argument(
        "--out-dir",
        default="data/ohlcv_4mo",
        help="cache directory for CSVs + manifest.json",
    )
    fetch.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    profile = PROFILES.get(getattr(args, "profile", None) or "hustle", HUSTLE)
    risk = RiskConfig(account_equity=getattr(args, "equity", 100_000))
    engine = BehavioralEdgeEngine(risk=risk, profile=profile)
    df = None
    if args.cmd in {"scan", "demo", "duel", "arena", "stress", "hustle"}:
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
            if profile.name == PREDATOR.name:
                print("Mode: PREDATOR — meta-label + ATR + anti-rival fade")
            if profile.name == HUSTLE.name:
                print("Mode: HUSTLE — sized up to clear the $100/day bar")
            print(f"Signals fired : {payload['signals']}")
            print(f"Trades taken  : {payload['trades']}")
            print(
                f"Win rate      : {payload['win_rate']:.1%}  "
                f"(excl. {payload.get('scratches', 0)} scratches)"
            )
            print(f"Expectancy    : ${payload['expectancy']:,.2f}")
            print(f"Profit factor : {payload['profit_factor']}")
            print(f"Max drawdown  : {payload['max_drawdown']:.2%}")
            print(f"Sharpe-like   : {payload['sharpe_like']}")
            print(f"PnL / day     : ${payload.get('pnl_per_day', 0):,.2f}")
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
        return 0

    if args.cmd == "arena":
        report = run_arena(df, equity=args.equity, profile=profile)
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print(f"ARENA — us vs Muse / Grok / classic RSI  (profile={report['profile']})")
            print("=" * 72)
            print(
                f"{'rank':<5} {'fighter':<28} {'WR':>7} {'PF':>8} "
                f"{'DD':>8} {'PnL':>10} {'comp':>8}"
            )
            for i, row in enumerate(report["ranking"], 1):
                mark = " ←" if i == 1 else ""
                print(
                    f"{i:<5} {row['label']:<28} {row['win_rate']:>7.1%} "
                    f"{str(row['profit_factor']):>8} {row['max_drawdown']:>8.2%} "
                    f"${row['total_pnl']:>9,.0f} {row['composite']:>8}{mark}"
                )
            print("-" * 72)
            print(
                f"Winner: {report['winner']}  | our rank #{report['our_rank']}  "
                f"| margin vs #2: {report['margin_vs_second']}"
            )
            print(
                f"vs Muse/Grok   : "
                f"{'BEATS BOTH' if report['beats_muse_grok'] else 'behind an AI rival'}"
            )
            if report["we_win"]:
                print("Status: BEHAVIORAL EDGE TAKES THE ARENA.")
            elif report["beats_muse_grok"]:
                print("Status: Beat Muse+Grok stacks; classic RSI still farming mean-reversion.")
            else:
                print("Status: rivals ahead — keep hardening.")
        return 0

    if args.cmd == "stress":
        report = run_stress(
            bars=args.bars,
            equity=args.equity,
            profile=profile,
        )
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print(f"STRESS — {report['arenas']} seeds  profile={report['profile']}")
            print("=" * 64)
            print(
                f"Arena #1 wins  : {report['wins']}/{report['arenas']} "
                f"({report['win_pct']:.0%})"
            )
            print(
                f"Beat Muse+Grok : {report['beats_muse_grok']}/{report['arenas']} "
                f"({report['beats_muse_grok_pct']:.0%})"
            )
            print(f"Median comp    : {report['median_composite']}")
            print(f"Best / worst # : {report['best_rank']} / {report['worst_rank']}")
            print(f"Avg win rate   : {report['avg_win_rate']:.1%}")
            print(f"Avg PnL        : ${report['avg_pnl']:,.2f}")
            print("\nPer seed:")
            for row in report["detail"]:
                if row["we_win"]:
                    flag = "WIN"
                elif row["beats_muse_grok"]:
                    flag = "AI✓"
                else:
                    flag = f"#{row['our_rank']}"
                print(
                    f"  seed={row['seed']:<5} {flag:<4}  "
                    f"comp={row['our_composite']:<7}  "
                    f"WR={row['our_win_rate']:.0%}  "
                    f"PnL=${row['our_pnl']:,.0f}"
                )
        return 0

    if args.cmd == "hustle":
        if args.stress:
            report = run_hustle_stress(
                bars=args.bars,
                equity=args.equity,
                profile=profile,
            )
            if args.json:
                print(json.dumps(report, indent=2))
            else:
                print(f"HUSTLE STRESS — {len(report['seeds'])} seeds  profile={report['profile']}")
                print("=" * 64)
                print(
                    f"League wins    : {report['wins']}/{len(report['seeds'])} "
                    f"({report['win_pct']:.0%})"
                )
                print(
                    f"Clears $100/d  : {report['clears_100']}/{len(report['seeds'])} "
                    f"({report['clears_100_pct']:.0%})"
                )
                print(f"Avg $/day      : ${report['avg_pnl_per_day']:,.2f}")
                print("\nPer seed:")
                for row in report["detail"]:
                    flag = "WIN" if row["we_win"] else "LOSS"
                    bar = "✓$100" if row["clears_100_day"] else "under"
                    print(
                        f"  seed={row['seed']:<5} {flag:<4} {bar:<6}  "
                        f"${row['our_pnl_per_day']:>8,.2f}/day  "
                        f"(top={row['winner']})"
                    )
            return 0

        report = run_hustle(
            bars=args.bars,
            seed=args.seed,
            equity=args.equity,
            profile=profile,
        )
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print(
                f"HUSTLE LEAGUE — $/day vs pressed Muse/Claude/Grok  "
                f"(profile={report['profile']}, seed={report['seed']})"
            )
            print("=" * 72)
            print(
                f"{'rank':<5} {'fighter':<28} {'WR':>7} {'$/day':>10} "
                f"{'PnL':>12} {'DD':>8}"
            )
            for i, row in enumerate(report["ranking"], 1):
                mark = " ←" if i == 1 else ""
                print(
                    f"{i:<5} {row['label']:<28} {row['win_rate']:>7.1%} "
                    f"${row['pnl_per_day']:>9,.2f} "
                    f"${row['total_pnl']:>11,.0f} "
                    f"{row['max_drawdown']:>8.2%}{mark}"
                )
            print("-" * 72)
            print(
                f"Winner: {report['winner']}  | our $/day ${report['our_pnl_per_day']:,.2f}  "
                f"| margin/day ${report['margin_vs_second_per_day']:,.2f}"
            )
            if report["clears_100_day"]:
                print(f"Status: CLEARS THE ${report['daily_bar']:.0f}/DAY BAR.")
            else:
                print(f"Status: under ${report['daily_bar']:.0f}/day — keep pressing.")
            if report["we_win"]:
                print("Status: BEATS pressed Muse/Claude/Grok on $/day.")
        return 0

    if args.cmd == "receipt":
        sealed = issue_hustle_receipt(
            bars=args.bars,
            seed=args.seed,
            equity=args.equity,
            profile=profile,
            include_stress=not args.no_stress,
        )
        out = write_receipt(sealed, args.out)
        if args.json:
            print(json.dumps(sealed, indent=2))
        else:
            claims = sealed["claims"]
            print("SEALED RECEIPT ISSUED")
            print("=" * 56)
            print(f"Wrote         : {out}")
            print(f"Version       : {sealed['version']}")
            print(f"Git SHA       : {sealed['git_sha'][:12]}")
            print(f"Seal          : {sealed['seal']['digest'][:16]}…")
            print(f"Seal valid    : {verify_seal(sealed)}")
            print(f"$/day         : ${claims['our_pnl_per_day']:,.2f}")
            print(f"Clears $100/d : {claims['clears_100_day']}")
            print(f"Beats rivals  : {claims['beats_pressed_rivals_on_seed']}")
            if claims.get("stress_avg_pnl_per_day") is not None:
                print(
                    f"Stress avg $/d: ${claims['stress_avg_pnl_per_day']:,.2f} "
                    f"(clears {claims['stress_clears_100_pct']:.0%})"
                )
            print(f"Market        : {sealed['methodology']['market']}")
            print(f"Disclaimer    : {sealed['methodology']['disclaimer']}")
        return 0

    if args.cmd == "compare":
        ours = load_receipt(args.ours)
        theirs = load_receipt(args.theirs)
        report = compare_receipts(ours, theirs, metric=args.metric)
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print("RECEIPT BAKE-OFF")
            print("=" * 56)
            print(f"Metric        : {report['metric']}")
            print(
                f"Ours          : {report['ours']['name']} = {report['ours']['value']} "
                f"(WR={report['ours']['win_rate']}, seal_ok={report['ours']['seal_ok']})"
            )
            print(
                f"Theirs        : {report['theirs']['name']} = {report['theirs']['value']} "
                f"(WR={report['theirs']['win_rate']}, seal_ok={report['theirs']['seal_ok']})"
            )
            print(f"Delta         : {report['delta']}")
            print(f"Winner        : {report['winner']}")
            print(f"Fair fight    : {report['fair_fight']}")
            if report["methodology_flags"]:
                print("Flags:")
                for flag in report["methodology_flags"]:
                    print(f"  • {flag}")
            print(report["note"])
        return 0

    if args.cmd == "fetch":
        from behavioral_edge.live_test import CRYPTO_UNIVERSE, DEFAULT_UNIVERSE
        from behavioral_edge.market_data import fetch_and_cache_window

        if args.symbols.strip():
            symbols = tuple(s.strip().upper() for s in args.symbols.split(",") if s.strip())
        elif args.crypto:
            symbols = CRYPTO_UNIVERSE
        else:
            symbols = DEFAULT_UNIVERSE + CRYPTO_UNIVERSE + (
                "SOL-USD",
                "XRP-USD",
                "BNB-USD",
                "DOGE-USD",
            )
        meta = fetch_and_cache_window(
            symbols,
            months=args.months,
            cache_dir=args.out_dir,
        )
        if args.json:
            print(json.dumps(meta, indent=2))
        else:
            print(
                f"FETCHED {meta['months']}mo window  "
                f"{meta['fetch_start']} → {meta['end']}  "
                f"(score from {meta['score_start']})"
            )
            print(f"Cache dir : {args.out_dir}")
            for sym, info in meta["symbols"].items():
                print(
                    f"  {sym:<10} bars={info['bars_total']:>4} "
                    f"scored={info['bars_scored']:>4}  "
                    f"{info['first']} → {info['last']}"
                )
            print(f"Manifest  : {args.out_dir}/manifest.json")
        return 0

    if args.cmd == "sweep":
        from pathlib import Path

        from behavioral_edge.crypto_sweep import run_crypto_subset_sweep

        report = run_crypto_subset_sweep(months=args.months, equity=args.equity)
        if args.out:
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.out).write_text(json.dumps(report, indent=2) + "\n")
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            bw = report["battle_winner"]
            print("CRYPTO SUBSET SWEEP")
            print("=" * 72)
            print(f"Score window : {report['score_start']} → {report['score_end']}")
            print(f"Candidates   : {len(report['candidates'])}")
            print(report["objective"])
            print("-" * 72)
            if bw:
                print(
                    f"BATTLE ROSTER k={bw['k']}  profile={bw['profile']}  "
                    f"avg $/day=${bw['avg_day']:,.2f}  sum PnL=${bw['sum_pnl']:,.0f}  "
                    f"WR={bw['avg_wr']:.0%}"
                )
                print(f"  symbols    : {', '.join(bw['symbols'])}")
                print(f"  desk $/day : ${bw['desk_day']:,.2f} (sum across books)")
            for pname, block in report["profiles"].items():
                champ = block["global_best_avg_day"]
                print(
                    f"Champion[{pname}]: {champ['symbols'][0]}  "
                    f"${champ['avg_day']:,.2f}/day  PnL ${champ['sum_pnl']:,.0f}"
                )
                print(f"{pname} best avg $/day by k:")
                for r in range(1, min(8, len(report["candidates"])) + 1):
                    b = block["by_k"][str(r)]["best_avg_day"]
                    print(
                        f"  k={r}  ${b['avg_day']:>7.2f}/day  "
                        f"sum ${b['sum_pnl']:>9,.0f}  {b['symbols']}"
                    )
            print(report["disclaimer"])
            if args.out:
                print(f"Wrote {args.out}")
        return 0

    if args.cmd == "live":
        from behavioral_edge.live_test import (
            BATTLE_CRYPTO_UNIVERSE,
            CHAMPION_ASSET,
            CRYPTO_UNIVERSE,
            run_live_window,
        )
        from behavioral_edge.profiles import CRYPTO as CRYPTO_PROFILE

        cli_args = argv if argv is not None else __import__("sys").argv[1:]
        profile_explicit = any(
            a == "--profile" or a.startswith("--profile=") for a in cli_args
        )

        if args.battle:
            symbols = BATTLE_CRYPTO_UNIVERSE
            if not profile_explicit:
                profile = HUSTLE  # sweep winner profile
        elif args.champion:
            symbols = (CHAMPION_ASSET,)
            if not profile_explicit:
                profile = CRYPTO_PROFILE
        elif args.crypto:
            symbols = CRYPTO_UNIVERSE
            if not profile_explicit:
                profile = CRYPTO_PROFILE
        else:
            symbols = tuple(
                s.strip().upper() for s in args.symbols.split(",") if s.strip()
            )
        report = run_live_window(
            symbols=symbols,
            months=args.months,
            equity=args.equity,
            profile=profile,
        )
        if args.out:
            from pathlib import Path

            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.out).write_text(json.dumps(report, indent=2) + "\n")
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print(
                f"LIVE WINDOW — last {report['months']} months  "
                f"profile={report['profile']}"
            )
            print("=" * 72)
            print(f"Score window  : {report['score_start']} → {report['score_end']}")
            print(f"Warm-up from  : {report['fetch_start']}")
            print(
                f"{'sym':<6} {'trades':>7} {'WR':>7} {'$/day':>10} "
                f"{'PnL':>12} {'DD':>8}"
            )
            for row in report["per_symbol"]:
                print(
                    f"{row['symbol']:<6} {row['trades']:>7} {row['win_rate']:>7.1%} "
                    f"${row['pnl_per_day']:>9,.2f} ${row['total_pnl']:>11,.0f} "
                    f"{row['max_drawdown']:>8.2%}"
                )
            agg = report["aggregate"]
            print("-" * 72)
            print(
                f"Avg $/day     : ${agg['avg_pnl_per_day']:,.2f}  "
                f"| sum PnL ${agg['sum_total_pnl']:,.0f}  "
                f"| avg WR {agg['avg_win_rate']:.1%}"
            )
            print(
                f"Clears $100/d : {agg['clears_100_day_avg']}  "
                f"(avg across symbols)"
            )
            if report["errors"]:
                print("Errors:")
                for err in report["errors"]:
                    print(f"  • {err['symbol']}: {err['error']}")
            print(report["disclaimer"])
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
