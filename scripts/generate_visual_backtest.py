"""CLI: Generate visual backtest reports.

Usage examples:
    # Single hypothesis × ticker × period
    python scripts/generate_visual_backtest.py \\
        --hypothesis tmpl_h_bb_squeeze \\
        --ticker SBER \\
        --period 2023

    # All registered hypotheses, all P1 Universe, all periods
    python scripts/generate_visual_backtest.py --all --capital 1000000

    # Specific campaign (reads all candidate datasets)
    python scripts/generate_visual_backtest.py --campaign tmpl_h_bb_squeeze \\
        --instruments SBER,GAZP,LKOH --periods 2023

Safety: no broker API calls, no T-Invest, no real trading, no git push.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from services.visual_backtest.reporter import VisualBacktestReporter
from services.research.campaign import P1_INSTRUMENTS, P1_PERIODS
from services.research.hypothesis_registry import HypothesisTemplateRegistry


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Generate visual backtest charts for MOEX AI LAB hypotheses.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Target selection (mutually exclusive)
    target = p.add_mutually_exclusive_group(required=True)
    target.add_argument("--hypothesis", metavar="TMPL_ID",
                        help="Single hypothesis template ID (e.g. tmpl_h_bb_squeeze).")
    target.add_argument("--campaign", metavar="TMPL_ID",
                        help="Run for a hypothesis across multiple instruments/periods.")
    target.add_argument("--all", action="store_true",
                        help="Run for all registered hypotheses.")

    # Dataset selection
    p.add_argument("--ticker", default="SBER",
                   help="Ticker (for --hypothesis mode). Default: SBER.")
    p.add_argument("--period", default="2023",
                   help="Year period (for --hypothesis mode). Default: 2023.")
    p.add_argument("--timeframe", default="1h",
                   help="Candle timeframe. Default: 1h.")
    p.add_argument("--instruments", metavar="CSV",
                   help="Comma-separated ticker list (for --campaign/--all). "
                        "Default: P1 Universe (14 tickers).")
    p.add_argument("--periods", metavar="CSV",
                   help="Comma-separated year-period list (for --campaign/--all). "
                        "Default: 2019,2021,2023.")

    # Financial / output
    p.add_argument("--capital", type=float, default=1_000_000.0,
                   help="Initial capital in RUB. Default: 1,000,000.")
    p.add_argument("--data-dir", default="data", metavar="PATH",
                   help="OHLCV dataset directory. Default: data/.")
    p.add_argument("--output-dir", default="reports/visual_backtest", metavar="PATH",
                   help="Output directory. Default: reports/visual_backtest/.")
    p.add_argument("--no-chart", action="store_true",
                   help="Skip chart rendering (JSON report only).")
    p.add_argument("--quiet", action="store_true",
                   help="Suppress verbose output.")

    return p.parse_args()


def _build_reporter(args: argparse.Namespace) -> VisualBacktestReporter:
    return VisualBacktestReporter(
        data_dir=Path(args.data_dir),
        output_dir=Path(args.output_dir),
        render_chart=not args.no_chart,
        verbose=not args.quiet,
    )


def _run_single(args: argparse.Namespace) -> None:
    reporter = _build_reporter(args)
    report = reporter.run(
        hypothesis_id=args.hypothesis,
        ticker=args.ticker,
        period=args.period,
        timeframe=args.timeframe,
        initial_capital=args.capital,
    )
    print(f"\n--- Visual Backtest Report ---")
    print(f"Hypothesis   : {report.hypothesis_id}")
    print(f"Dataset      : {report.dataset_id}")
    print(f"Trades       : {report.metrics.num_trades}")
    print(f"Total return : {report.metrics.total_return_pct:+.2f}%")
    print(f"Max drawdown : {report.metrics.max_drawdown_pct:.2f}%")
    print(f"Win rate     : {report.metrics.win_rate*100:.1f}%")
    import math
    pf = report.metrics.profit_factor
    print(f"Profit factor: {'inf' if math.isinf(pf) else f'{pf:.2f}'}")
    print(f"Exposure     : {report.metrics.exposure_time_pct:.1f}%")
    if report.chart_path:
        print(f"Chart        : {report.chart_path}")
    print(f"Report JSON  : {report.report_json_path}")


def _run_campaign(args: argparse.Namespace) -> None:
    hypothesis_id = args.campaign
    instruments = (
        [t.strip() for t in args.instruments.split(",")]
        if args.instruments else P1_INSTRUMENTS
    )
    periods = (
        [p.strip() for p in args.periods.split(",")]
        if args.periods else P1_PERIODS
    )
    reporter = _build_reporter(args)
    total = len(instruments) * len(periods)
    success = 0
    failures: list[str] = []

    print(f"\n[Campaign] {hypothesis_id}")
    print(f"Instruments: {len(instruments)}, Periods: {len(periods)}, Total: {total}")

    for period in periods:
        for ticker in instruments:
            try:
                report = reporter.run(
                    hypothesis_id=hypothesis_id,
                    ticker=ticker,
                    period=period,
                    timeframe=args.timeframe,
                    initial_capital=args.capital,
                )
                success += 1
            except FileNotFoundError:
                failures.append(f"{ticker}/{period}: dataset not found")
            except Exception as exc:
                failures.append(f"{ticker}/{period}: {exc}")

    print(f"\nDone: {success}/{total} succeeded, {len(failures)} failed.")
    for f in failures:
        print(f"  SKIP: {f}")


def _run_all(args: argparse.Namespace) -> None:
    registry = HypothesisTemplateRegistry()
    templates = registry.list()
    instruments = (
        [t.strip() for t in args.instruments.split(",")]
        if args.instruments else P1_INSTRUMENTS
    )
    periods = (
        [p.strip() for p in args.periods.split(",")]
        if args.periods else P1_PERIODS
    )
    print(f"\n[All Hypotheses] {len(templates)} templates")
    for template in templates:
        print(f"\n--- {template.template_id} ---")
        args.campaign = template.template_id
        args.instruments = ",".join(instruments)
        args.periods = ",".join(periods)
        _run_campaign(args)


def main() -> None:
    args = _parse_args()
    if args.hypothesis:
        _run_single(args)
    elif args.campaign:
        _run_campaign(args)
    elif args.all:
        _run_all(args)


if __name__ == "__main__":
    main()
