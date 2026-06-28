"""VisualBacktestReporter — orchestrator for the visual backtest pipeline.

Pipeline:
  1. Load OHLCV dataset (via DatasetLoader)
  2. Load hypothesis factory (via HypothesisTemplateRegistry)
  3. Generate trade journal (TradeJournalGenerator)
  4. Compute equity curve + metrics (equity.py)
  5. Render chart (renderer.py)
  6. Save JSON report

Output directory convention:
  {output_dir}/{hypothesis_id}/{ticker}_{period}_{timeframe}/
    chart.png
    report.json

Safety: no broker API calls, no T-Invest, no real trading, no git ops.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from core.walkforward.models import WalkForwardConfig
from services.visual_backtest.equity import build_equity_curve, compute_metrics
from services.visual_backtest.journal import TradeJournalGenerator
from services.visual_backtest.models import VisualBacktestReport
from services.visual_backtest.renderer import render_chart
from services.research.dataset import DatasetLoader
from services.research.hypothesis_registry import HypothesisTemplateRegistry


def _report_dir(
    output_base: Path,
    hypothesis_id: str,
    ticker: str,
    period: str,
    timeframe: str,
) -> Path:
    """Canonical output directory for one hypothesis × dataset combination."""
    slug = f"{ticker.lower()}_{period}_{timeframe.lower()}"
    return output_base / hypothesis_id / slug


class VisualBacktestReporter:
    """Generates visual backtest reports for hypothesis × dataset combinations.

    Usage:
        reporter = VisualBacktestReporter(
            data_dir=Path("data"),
            output_dir=Path("reports/visual_backtest"),
        )
        report = reporter.run(
            hypothesis_id="tmpl_h_bb_squeeze",
            ticker="SBER",
            period="2023",
            timeframe="1h",
            initial_capital=1_000_000.0,
        )
        print(report.chart_path)
        print(report.metrics)
    """

    def __init__(
        self,
        data_dir: Path | None = None,
        output_dir: Path | None = None,
        train_size: int = 60,
        test_size: int = 20,
        step_size: int = 20,
        render_chart: bool = True,
        verbose: bool = True,
    ) -> None:
        self._data_dir    = Path(data_dir) if data_dir else Path("data")
        self._output_dir  = Path(output_dir) if output_dir else Path("reports/visual_backtest")
        self._wf_config   = WalkForwardConfig(
            train_size=train_size,
            test_size=test_size,
            step_size=step_size,
        )
        self._render_chart = render_chart
        self._verbose      = verbose
        self._registry     = HypothesisTemplateRegistry()
        self._loader       = DatasetLoader()
        self._generator    = TradeJournalGenerator()

    def run(
        self,
        hypothesis_id: str,
        ticker: str,
        period: str,
        timeframe: str = "1h",
        initial_capital: float = 1_000_000.0,
    ) -> VisualBacktestReport:
        """Generate a full visual backtest report for one hypothesis × dataset.

        Args:
            hypothesis_id:   Template ID from the Hypothesis Registry.
            ticker:          Instrument ticker (e.g. "SBER").
            period:          Year period (e.g. "2023").
            timeframe:       Candle timeframe (default "1h").
            initial_capital: Simulation starting capital in RUB.

        Returns:
            VisualBacktestReport with trade journal, equity curve, metrics, chart path.
        """
        dataset_id = f"{ticker.lower()}_{timeframe}_{period}_main"

        if self._verbose:
            print(f"[VisualBacktest] {hypothesis_id} | {dataset_id}")

        # ── 1. Load dataset ────────────────────────────────────────────────────
        dataset = self._loader.load(dataset_id, self._data_dir)
        candles = list(dataset.candles)
        if self._verbose:
            print(f"  Dataset: {len(candles)} bars")

        # ── 2. Resolve factory ─────────────────────────────────────────────────
        factory = self._registry.get_provider_factory(hypothesis_id)

        # ── 3. Generate trade journal ──────────────────────────────────────────
        trades = self._generator.generate(
            candles=candles,
            factory=factory,
            wf_config=self._wf_config,
            initial_capital=initial_capital,
        )
        if self._verbose:
            print(f"  Trades generated: {len(trades)}")

        # ── 4. Build equity curve + metrics ────────────────────────────────────
        equity_curve = build_equity_curve(candles, trades, initial_capital)
        metrics      = compute_metrics(trades, equity_curve, initial_capital)

        if self._verbose:
            print(f"  Total return: {metrics.total_return_pct:+.2f}%  "
                  f"MaxDD: {metrics.max_drawdown_pct:.2f}%  "
                  f"WinRate: {metrics.win_rate*100:.1f}%")

        # ── 5. Set up output directory ─────────────────────────────────────────
        report_id  = uuid4().hex[:12]
        report_dir = _report_dir(self._output_dir, hypothesis_id, ticker, period, timeframe)
        report_dir.mkdir(parents=True, exist_ok=True)

        # ── 6. Render chart ────────────────────────────────────────────────────
        chart_path: Path | None = None
        if self._render_chart:
            chart_path = report_dir / "chart.png"
            template = self._registry.get(hypothesis_id)
            title = f"{template.name} | {ticker} {period} {timeframe.upper()}"
            render_chart(
                candles=candles,
                trades=trades,
                equity_curve=equity_curve,
                metrics=metrics,
                output_path=chart_path,
                title=title,
            )
            if self._verbose:
                print(f"  Chart: {chart_path}")

        # ── 7. Save JSON report ────────────────────────────────────────────────
        report_json_path = report_dir / "report.json"
        report = VisualBacktestReport(
            report_id=report_id,
            hypothesis_id=hypothesis_id,
            ticker=ticker,
            period=period,
            timeframe=timeframe,
            dataset_id=dataset_id,
            initial_capital=initial_capital,
            trade_journal=trades,
            equity_curve=equity_curve,
            metrics=metrics,
            chart_path=chart_path,
            report_json_path=report_json_path,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
        with open(report_json_path, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)

        if self._verbose:
            print(f"  Report: {report_json_path}")

        return report
