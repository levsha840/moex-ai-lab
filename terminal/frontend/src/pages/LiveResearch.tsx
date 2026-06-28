import { useState, useMemo } from 'react'
import { Select, Loader, Center, ScrollArea } from '@mantine/core'
import { useQuery } from '@tanstack/react-query'
import { fetchReports, fetchReport, fetchCandles, fetchDatasets } from '../api/client'
import type { ReportSummary, JournalEntry } from '../api/client'
import CandleChart from '../components/charts/CandleChart'
import EquityLineChart from '../components/charts/EquityLineChart'
import MetricCard from '../components/shared/MetricCard'

/* ── Price ticker in top toolbar ── */
function PriceTicker({ candles }: { candles: any[] }) {
  if (candles.length < 2) return null
  const last = candles[candles.length - 1]
  const prev = candles[candles.length - 2]
  const chg = last.close - prev.close
  const chgPct = (chg / prev.close) * 100
  const up = chg >= 0
  return (
    <div className="t-pricetag">
      <span className="t-pricetag-price">{last.close.toFixed(2)}</span>
      <span className={`t-pricetag-change ${up ? 'up' : 'down'}`}>
        {up ? '+' : ''}{chg.toFixed(2)} ({up ? '+' : ''}{chgPct.toFixed(2)}%)
      </span>
    </div>
  )
}

/* ── Trade journal table ── */
function TradeJournal({ trades }: { trades: JournalEntry[] }) {
  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <div className="t-section-title" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <span>⬡ Trade Journal</span>
        <span style={{ color: 'var(--t-text-2)', fontSize: 10 }}>{trades.length} trades</span>
      </div>
      <ScrollArea style={{ flex: 1 }} scrollbarSize={3}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead style={{ position: 'sticky', top: 0, zIndex: 5 }}>
            <tr>
              {['#', 'Entry', 'Exit', 'Entry ₽', 'Exit ₽', 'PnL %', 'PnL ₽', 'Capital', 'Reason', 'W/L'].map(h => (
                <th key={h} className="mantine-Table-th" style={{ textAlign: h === '#' ? 'center' : 'left' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {[...trades].reverse().map((t, i) => (
              <tr key={t.trade_id} style={{ cursor: 'default' }}
                onMouseEnter={e => (e.currentTarget.style.background = 'var(--t-hover)')}
                onMouseLeave={e => (e.currentTarget.style.background = '')}>
                <td style={{ textAlign: 'center', color: 'var(--t-text-3)', fontSize: 10, padding: '4px 6px', borderBottom: '1px solid var(--t-border-dim)' }}>
                  {trades.length - i}
                </td>
                {[
                  { v: t.entry_timestamp?.slice(5, 16) ?? '—', c: 'var(--t-text-2)' },
                  { v: t.exit_timestamp?.slice(5, 16) ?? '—',  c: 'var(--t-text-2)' },
                  { v: t.entry_price.toFixed(2), c: 'var(--t-text)' },
                  { v: t.exit_price.toFixed(2),  c: 'var(--t-text)' },
                  { v: `${t.pnl_pct >= 0 ? '+' : ''}${t.pnl_pct.toFixed(3)}%`, c: t.pnl_pct >= 0 ? 'var(--t-green)' : 'var(--t-red)' },
                  { v: `${t.pnl >= 0 ? '+' : ''}${Math.round(t.pnl).toLocaleString('ru-RU')}`, c: t.pnl >= 0 ? 'var(--t-green)' : 'var(--t-red)' },
                  { v: Math.round(t.capital_after).toLocaleString('ru-RU'), c: 'var(--t-cyan)' },
                  { v: t.exit_reason, c: 'var(--t-text-3)' },
                  { v: t.is_winner ? 'W' : 'L', c: t.is_winner ? 'var(--t-green)' : 'var(--t-red)' },
                ].map((cell, ci) => (
                  <td key={ci} className="mantine-Table-td"
                    style={{ color: cell.c, fontFamily: 'var(--t-font-mono)', borderBottom: '1px solid var(--t-border-dim)' }}>
                    {cell.v}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </ScrollArea>
    </div>
  )
}

/* ── Right metrics panel ── */
function MetricsPanel({ report, ticker, period, timeframe, hypothesisId }: {
  report: any; ticker: string; period: string; timeframe: string; hypothesisId: string
}) {
  const m = report?.metrics
  const pf = m?.profit_factor
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', borderLeft: '1px solid var(--t-border)', background: 'var(--t-bg)', minWidth: 200, maxWidth: 230 }}>
      {/* Hypothesis info */}
      <div className="t-section-title">⬡ Strategy</div>
      <div style={{ padding: '8px 10px', borderBottom: '1px solid var(--t-border)' }}>
        <div style={{ fontSize: 10, color: 'var(--t-cyan)', fontWeight: 600, marginBottom: 2 }}>{hypothesisId || '—'}</div>
        <div style={{ fontSize: 10, color: 'var(--t-text-2)' }}>
          <span style={{ color: 'var(--t-amber)' }}>{ticker}</span> · {period} · {timeframe.toUpperCase()}
        </div>
      </div>

      <div className="t-section-title">⬡ Performance</div>

      <div style={{ flex: 1, overflowY: 'auto' }}>
        <MetricCard
          label="Capital"
          value={m ? `₽ ${Math.round(m.final_capital).toLocaleString('ru-RU')}` : '—'}
          cls="cyan"
        />
        <MetricCard
          label="Total Return"
          value={m ? `${m.total_return_pct >= 0 ? '+' : ''}${m.total_return_pct.toFixed(2)}%` : '—'}
          cls={m ? (m.total_return_pct >= 0 ? 'up' : 'down') : 'dim'}
        />
        <MetricCard
          label="Max Drawdown"
          value={m ? `${m.max_drawdown_pct.toFixed(2)}%` : '—'}
          cls="down"
        />
        <MetricCard
          label="Win Rate"
          value={m ? `${(m.win_rate * 100).toFixed(1)}%` : '—'}
          cls={m && m.win_rate >= 0.5 ? 'up' : 'dim'}
        />
        <MetricCard
          label="Profit Factor"
          value={m ? (pf === Infinity ? '∞' : pf.toFixed(2)) : '—'}
          cls={m && pf > 1 ? 'up' : 'down'}
        />
        <MetricCard
          label="Trades"
          value={m?.num_trades ?? 0}
          cls="dim"
        />
        <MetricCard
          label="Exposure"
          value={m ? `${m.exposure_time_pct.toFixed(1)}%` : '—'}
          cls="dim"
        />
        <MetricCard
          label="Avg Trade"
          value={m ? `${m.avg_trade_pnl_pct >= 0 ? '+' : ''}${m.avg_trade_pnl_pct.toFixed(3)}%` : '—'}
          cls={m && m.avg_trade_pnl_pct >= 0 ? 'up' : 'down'}
        />
        <MetricCard
          label="Initial Capital"
          value={m ? `₽ ${Math.round(m.initial_capital).toLocaleString('ru-RU')}` : '—'}
          cls="dim"
        />
      </div>
    </div>
  )
}

/* ── Main page ── */
export default function LiveResearch() {
  const { data: reports = [], isLoading: loadingReports } = useQuery({ queryKey: ['reports'], queryFn: fetchReports })
  const [selectedIdx, setSelectedIdx] = useState(0)

  const current: ReportSummary | undefined = reports[selectedIdx]

  const { data: report, isLoading: loadingReport } = useQuery({
    queryKey: ['report', current?.hypothesis_id, current?.ticker, current?.period, current?.timeframe],
    queryFn: () => fetchReport(current!.hypothesis_id, current!.ticker, current!.period, current!.timeframe),
    enabled: !!current,
  })

  const { data: candles = [], isLoading: loadingCandles } = useQuery({
    queryKey: ['candles', current?.dataset_id],
    queryFn: () => fetchCandles(current!.dataset_id),
    enabled: !!current,
  })

  const trades = report?.trade_journal ?? []
  const capital = report?.metrics?.initial_capital ?? 1_000_000
  const loading = loadingReport || loadingCandles

  const reportOptions = reports.map((r, i) => ({
    value: String(i),
    label: `${r.hypothesis_id}  |  ${r.ticker} · ${r.period} · ${r.timeframe}`,
  }))

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden', background: 'var(--t-bg)' }}>

      {/* ── Toolbar ── */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 12,
        height: 38, padding: '0 12px', flexShrink: 0,
        background: 'var(--t-panel)', borderBottom: '1px solid var(--t-border)',
      }}>
        <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--t-text-2)', textTransform: 'uppercase', letterSpacing: 1, whiteSpace: 'nowrap' }}>
          LIVE RESEARCH
        </span>
        <div style={{ width: 1, height: 16, background: 'var(--t-border)' }} />

        <Select
          size="xs"
          placeholder={loadingReports ? 'Loading...' : 'Select backtest report...'}
          data={reportOptions}
          value={String(selectedIdx)}
          onChange={v => setSelectedIdx(Number(v ?? '0'))}
          style={{ width: 440, flexShrink: 0 }}
        />

        <div style={{ width: 1, height: 16, background: 'var(--t-border)' }} />

        {candles.length > 0 && <PriceTicker candles={candles} />}

        <div style={{ flex: 1 }} />

        {candles.length > 0 && (
          <span style={{ fontSize: 10, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)' }}>
            {candles.length.toLocaleString()} bars
            {candles[0] && ` · ${candles[0].ts?.slice(0, 10)}`}
            {candles[candles.length - 1] && ` → ${candles[candles.length - 1].ts?.slice(0, 10)}`}
          </span>
        )}
      </div>

      {/* ── Main area: chart + right panel ── */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minHeight: 0 }}>
        <div style={{ flex: '0 0 55%', display: 'flex', minHeight: 0, borderBottom: '1px solid var(--t-border)' }}>
          {/* Candle chart */}
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, overflow: 'hidden' }}>
            <div style={{ flex: 1, minHeight: 0 }}>
              {loading ? (
                <Center h="100%"><Loader /></Center>
              ) : (
                <CandleChart candles={candles} trades={trades} height={undefined} fillContainer />
              )}
            </div>
          </div>
          {/* Metrics panel */}
          <MetricsPanel
            report={report}
            ticker={current?.ticker ?? '—'}
            period={current?.period ?? '—'}
            timeframe={current?.timeframe ?? '1h'}
            hypothesisId={current?.hypothesis_id ?? '—'}
          />
        </div>

        {/* ── Equity curve ── */}
        <div style={{ flex: '0 0 20%', display: 'flex', borderBottom: '1px solid var(--t-border)', minHeight: 0 }}>
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, overflow: 'hidden' }}>
            <div className="t-section-title">⬡ Equity Curve</div>
            <div style={{ flex: 1, minHeight: 0 }}>
              {candles.length > 0 && (
                <EquityLineChart candles={candles} trades={trades} initialCapital={capital} fillContainer />
              )}
            </div>
          </div>
          <div style={{ width: 230, borderLeft: '1px solid var(--t-border)', minWidth: 0 }} />
        </div>

        {/* ── Trade journal ── */}
        <div style={{ flex: '0 0 25%', minHeight: 0, overflow: 'hidden' }}>
          <TradeJournal trades={trades} />
        </div>
      </div>
    </div>
  )
}
