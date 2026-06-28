import type { Report, JournalEntry, PaperSummary, Candle, Trade } from '../api/client'
import { calcRiskMetrics } from './indicators'
import type { UTCTimestamp } from 'lightweight-charts'

export type DataSource = 'backtest' | 'paper' | 'none'

export interface PortfolioMetrics {
  source: DataSource
  initialCapital: number
  currentCapital: number
  pnl: number
  pnlPct: number
  freeCash: number
  usedPct: number         // for backtest: exposure_time_pct; for paper: exposure_pct
  maxDrawdown: number
  currentDrawdown: number
  sharpe: number
  sortino: number
  calmar: number
  var95: number
  winRate: number         // 0–100
  profitFactor: number
  numTrades: number
  ticker: string
  strategyLabel: string
}

export interface EquityPoint {
  time: UTCTimestamp
  value: number
}

/** Compute all portfolio metrics from a single backtest report. Never mixes sources. */
export function metricsFromReport(report: Report): PortfolioMetrics {
  const m = report.metrics
  const trades = report.trade_journal
  const initCap = report.initial_capital ?? m.initial_capital
  const finalCap = m.final_capital ?? (trades.length ? trades[trades.length - 1].capital_after : initCap)

  const risk = calcRiskMetrics(trades, initCap)

  return {
    source: 'backtest',
    initialCapital: initCap,
    currentCapital: finalCap,
    pnl: finalCap - initCap,
    pnlPct: m.total_return_pct,
    freeCash: finalCap,            // backtest complete — all in cash
    usedPct: m.exposure_time_pct,  // % of bars in position
    maxDrawdown: m.max_drawdown_pct,
    currentDrawdown: risk.currentDD,
    sharpe: risk.sharpe,
    sortino: risk.sortino,
    calmar: risk.calmar,
    var95: risk.var95,
    winRate: m.win_rate * 100,
    profitFactor: m.profit_factor,
    numTrades: m.num_trades,
    ticker: report.ticker,
    strategyLabel: report.hypothesis_id.replace('tmpl_h_', '').replace(/_/g, ' '),
  }
}

/** Build equity step-function from backtest trade journal + candles (for time axis). */
export function equityFromReport(report: Report, candles: Candle[]): EquityPoint[] {
  const trades = report.trade_journal
  const initCap = report.initial_capital ?? report.metrics.initial_capital
  if (!candles.length) return []

  const points: EquityPoint[] = []
  // Start point at first candle
  points.push({ time: candles[0].time as UTCTimestamp, value: initCap })

  for (const t of trades) {
    const bar = t.exit_bar
    if (bar >= 0 && bar < candles.length) {
      points.push({ time: candles[bar].time as UTCTimestamp, value: t.capital_after })
    }
  }

  // Deduplicate (same bar multiple exits: keep last)
  const map = new Map<number, number>()
  for (const p of points) map.set(p.time as number, p.value)
  return [...map.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([t, v]) => ({ time: t as UTCTimestamp, value: v }))
}

/** Compute portfolio metrics from PaperSummary. Never mixes with backtest data. */
export function metricsFromPaper(paper: PaperSummary): PortfolioMetrics {
  const freeCash = paper.current_capital * (1 - paper.exposure_pct / 100)
  return {
    source: 'paper',
    initialCapital: paper.initial_capital,
    currentCapital: paper.current_capital,
    pnl: paper.total_pnl,
    pnlPct: paper.total_return_pct,
    freeCash,
    usedPct: paper.exposure_pct,
    maxDrawdown: paper.max_drawdown_pct,
    currentDrawdown: 0,   // not in PaperSummary
    sharpe: 0,            // requires equity history
    sortino: 0,
    calmar: 0,
    var95: 0,
    winRate: paper.win_rate * 100,
    profitFactor: 0,
    numTrades: paper.total_trades,
    ticker: '—',
    strategyLabel: 'Бумажный портфель',
  }
}

/** Build equity curve from paper trade list + initial capital.
 *  If no trades: returns a flat horizontal line at initialCapital.
 *  Never touches Report, candles, or any backtest data. */
export function equityFromPaperTrades(trades: Trade[], initialCapital: number): EquityPoint[] {
  const nowSec = Math.floor(Date.now() / 1000)

  if (!trades.length) {
    // Flat line — 7 synthetic days so the chart renders
    return [
      { time: (nowSec - 7 * 86400) as UTCTimestamp, value: initialCapital },
      { time: nowSec as UTCTimestamp, value: initialCapital },
    ]
  }

  const sorted = [...trades].sort(
    (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()
  )

  const firstSec = Math.floor(new Date(sorted[0].date).getTime() / 1000)
  const points: EquityPoint[] = [
    { time: (firstSec - 86400) as UTCTimestamp, value: initialCapital },
  ]

  let capital = initialCapital
  for (const t of sorted) {
    capital += t.pnl
    points.push({
      time: Math.floor(new Date(t.date).getTime() / 1000) as UTCTimestamp,
      value: capital,
    })
  }

  // Deduplicate same-second points, keeping last
  const map = new Map<number, number>()
  for (const p of points) map.set(p.time as number, p.value)
  return [...map.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([t, v]) => ({ time: t as UTCTimestamp, value: v }))
}

/** Find nearest equity value at or before a given timestamp (binary search). */
export function findEquityValue(points: EquityPoint[], time: number): number | null {
  if (!points.length) return null
  let lo = 0, hi = points.length - 1
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1
    if ((points[mid].time as number) <= time) lo = mid
    else hi = mid - 1
  }
  return points[lo]?.value ?? null
}

export const COMPARE_COLORS = [
  '#2962ff', '#089981', '#f23645', '#ffb800', '#00b0ff',
  '#ab47bc', '#ff7043', '#26a69a', '#ec407a', '#42a5f5',
]
