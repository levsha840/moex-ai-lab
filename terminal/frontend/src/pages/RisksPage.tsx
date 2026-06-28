import { useMemo } from 'react'
import { IconShield } from '@tabler/icons-react'
import ReactECharts from 'echarts-for-react'
import { useTerminal } from '../context/TerminalContext'
import { metricsFromReport, metricsFromPaper, equityFromReport } from '../utils/portfolio'
import type { JournalEntry, ReportSummary, Report } from '../api/client'
import type { PortfolioMetrics } from '../utils/portfolio'

// ── Risk helpers ────────────────────────────────────────────────────────────────
function losingStreak(trades: JournalEntry[]): number {
  let max = 0, cur = 0
  for (const t of trades) {
    if (t.is_winner === false) { cur++; max = Math.max(max, cur) }
    else cur = 0
  }
  return max
}

function winningStreak(trades: JournalEntry[]): number {
  let max = 0, cur = 0
  for (const t of trades) {
    if (t.is_winner === true) { cur++; max = Math.max(max, cur) }
    else cur = 0
  }
  return max
}

// ── Styling helpers ─────────────────────────────────────────────────────────────
const TH: React.CSSProperties = {
  padding: '6px 10px', color: 'var(--t-text-3)', fontWeight: 600, letterSpacing: 0.5,
  fontSize: 9, textAlign: 'left', background: 'var(--t-panel)',
  borderBottom: '1px solid var(--t-border)', fontFamily: 'var(--t-font-mono)',
  position: 'sticky', top: 0, zIndex: 1,
}
const TD: React.CSSProperties = {
  padding: '7px 10px', fontSize: 10, fontFamily: 'var(--t-font-mono)',
}

function RiskCard({ label, value, color, sub }: { label: string; value: string; color?: string; sub?: string }) {
  return (
    <div style={{ padding: '10px 12px', background: 'var(--t-elevated)', borderRadius: 4, border: '1px solid var(--t-border)', display: 'flex', flexDirection: 'column', gap: 4 }}>
      <span style={{ fontSize: 8, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)', letterSpacing: 0.5, fontWeight: 700 }}>{label}</span>
      <span style={{ fontSize: 14, fontWeight: 700, fontFamily: 'var(--t-font-mono)', color: color ?? 'var(--t-text)' }}>{value}</span>
      {sub && <span style={{ fontSize: 8, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)' }}>{sub}</span>}
    </div>
  )
}

function SH({ label }: { label: string }) {
  return (
    <div style={{ fontSize: 9, letterSpacing: 0.8, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)', fontWeight: 700, padding: '12px 0 8px' }}>
      {label}
    </div>
  )
}

function noData(label: string) {
  return <span style={{ color: 'var(--t-text-3)' }}>Нет данных</span>
}

function fmtF(n: number | null | undefined, dec = 2): string {
  if (n == null || isNaN(n)) return '—'
  return n.toFixed(dec)
}

// ── Drawdown chart ──────────────────────────────────────────────────────────────
function DrawdownChart({ equity }: { equity: { time: number; value: number }[] }) {
  if (equity.length < 2) return null
  // Compute drawdown series
  let peak = equity[0].value
  const ddData = equity.map(p => {
    if (p.value > peak) peak = p.value
    return peak > 0 ? ((p.value - peak) / peak) * 100 : 0
  })
  const times = equity.map(p => {
    const d = new Date(p.time * 1000)
    return `${d.getDate().toString().padStart(2,'0')}.${(d.getMonth()+1).toString().padStart(2,'0')}`
  })

  return (
    <ReactECharts
      style={{ height: 140 }}
      option={{
        backgroundColor: 'transparent',
        grid: { top: 8, right: 12, bottom: 24, left: 46 },
        xAxis: { type: 'category', data: times, axisLine: { lineStyle: { color: '#2a2e39' } }, axisLabel: { color: '#6c7282', fontSize: 8 }, splitLine: { show: false } },
        yAxis: {
          type: 'value', splitLine: { lineStyle: { color: '#1e222d', type: 'dashed' } },
          axisLabel: { color: '#6c7282', fontSize: 8, formatter: (v: number) => `${v.toFixed(1)}%` },
        },
        series: [{
          type: 'line', data: ddData, smooth: false, symbol: 'none',
          lineStyle: { color: '#f23645', width: 1 },
          areaStyle: { color: 'rgba(242,54,69,0.15)' },
        }],
        tooltip: { trigger: 'axis', backgroundColor: '#1e222d', borderColor: '#2a2e39', textStyle: { color: '#d1d4dc', fontSize: 9 }, formatter: (p: any) => `DD: ${p[0].value.toFixed(2)}%` },
      }}
      notMerge
    />
  )
}

// ── Rolling Sharpe chart ───────────────────────────────────────────────────────
function RollingSharpeChart({ trades: tds }: { trades: JournalEntry[] }) {
  if (tds.length < 10) return null
  const WINDOW = 20
  const returns = tds.map(t => t.pnl_pct ?? 0)
  const rolling: number[] = []
  for (let i = WINDOW; i <= returns.length; i++) {
    const w = returns.slice(i - WINDOW, i)
    const mean = w.reduce((s, v) => s + v, 0) / WINDOW
    const std  = Math.sqrt(w.reduce((s, v) => s + (v - mean) ** 2, 0) / WINDOW)
    rolling.push(std > 0 ? (mean / std) * Math.sqrt(252) : 0)
  }
  return (
    <ReactECharts
      style={{ height: 120 }}
      option={{
        backgroundColor: 'transparent',
        grid: { top: 8, right: 12, bottom: 24, left: 46 },
        xAxis: { type: 'category', data: rolling.map((_, i) => String(WINDOW + i)), axisLine: { lineStyle: { color: '#2a2e39' } }, axisLabel: { color: '#6c7282', fontSize: 8 }, splitLine: { show: false } },
        yAxis: {
          type: 'value', splitLine: { lineStyle: { color: '#1e222d', type: 'dashed' } },
          axisLabel: { color: '#6c7282', fontSize: 8, formatter: (v: number) => v.toFixed(1) },
        },
        series: [{
          type: 'line', data: rolling, smooth: true, symbol: 'none',
          lineStyle: { color: '#2962ff', width: 1 },
          areaStyle: { color: 'rgba(41,98,255,0.08)' },
          markLine: { data: [{ yAxis: 0, lineStyle: { color: '#434651', type: 'dashed', width: 1 } }], label: { show: false }, symbol: 'none' },
        }],
        tooltip: { trigger: 'axis', backgroundColor: '#1e222d', borderColor: '#2a2e39', textStyle: { color: '#d1d4dc', fontSize: 9 }, formatter: (p: any) => `Sharpe: ${p[0].value.toFixed(2)}` },
      }}
      notMerge
    />
  )
}

// ── Main component ──────────────────────────────────────────────────────────────
export default function RisksPage() {
  const { fullReport, allFullReports, reports, trades, paper, candles, setSelectedIdx, setActiveTab } = useTerminal()

  const currentMetrics = useMemo(() => {
    if (fullReport) { try { return metricsFromReport(fullReport) } catch { return null } }
    if (paper) { try { return metricsFromPaper(paper) } catch { return null } }
    return null
  }, [fullReport, paper])

  const allMetrics = useMemo(() =>
    allFullReports.map(r => { try { return metricsFromReport(r) } catch { return null } })
  , [allFullReports])

  const worstTrade = useMemo(() => {
    if (!trades.length) return null
    return trades.reduce((w, t) => (t.pnl_pct ?? 0) < (w.pnl_pct ?? 0) ? t : w)
  }, [trades])

  const bestTrade = useMemo(() => {
    if (!trades.length) return null
    return trades.reduce((b, t) => (t.pnl_pct ?? 0) > (b.pnl_pct ?? 0) ? t : b)
  }, [trades])

  const lStreak = useMemo(() => losingStreak(trades), [trades])
  const wStreak = useMemo(() => winningStreak(trades), [trades])

  const equityData = useMemo(() => {
    if (fullReport && candles.length) {
      try { return equityFromReport(fullReport, candles) } catch { return [] }
    }
    return []
  }, [fullReport, candles])

  if (!currentMetrics && allFullReports.length === 0) {
    return (
      <div style={{ height: '100%', display: 'flex', flexDirection: 'column', background: 'var(--t-bg)', overflow: 'hidden' }}>
        <div style={{ height: 44, flexShrink: 0, display: 'flex', alignItems: 'center', padding: '0 16px', background: 'var(--t-panel)', borderBottom: '1px solid var(--t-border)', gap: 10 }}>
          <IconShield size={13} color="var(--t-text-3)" />
          <span style={{ fontSize: 11, fontWeight: 700, fontFamily: 'var(--t-font-mono)', color: 'var(--t-text)', letterSpacing: 1 }}>РИСКИ</span>
        </div>
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 12, color: 'var(--t-text-3)' }}>
          <IconShield size={40} style={{ opacity: 0.15 }} />
          <div style={{ fontSize: 12, fontFamily: 'var(--t-font-mono)' }}>Нет данных</div>
          <div style={{ fontSize: 10, lineHeight: 1.6 }}>Запустите бэктест для получения риск-метрик</div>
        </div>
      </div>
    )
  }

  const stratLabel = currentMetrics?.strategyLabel ?? 'Текущая стратегия'

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', background: 'var(--t-bg)', overflow: 'hidden' }}>
      {/* Header */}
      <div style={{ height: 44, flexShrink: 0, display: 'flex', alignItems: 'center', padding: '0 16px', background: 'var(--t-panel)', borderBottom: '1px solid var(--t-border)', gap: 10 }}>
        <IconShield size={13} color="var(--t-text-3)" />
        <span style={{ fontSize: 11, fontWeight: 700, fontFamily: 'var(--t-font-mono)', color: 'var(--t-text)', letterSpacing: 1 }}>РИСК-МЕТРИКИ</span>
        {currentMetrics && (
          <span style={{ fontSize: 9, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)' }}>
            · {stratLabel}
          </span>
        )}
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: 16 }}>
        {currentMetrics ? (
          <>
            {/* Main risk metrics */}
            <SH label="КЛЮЧЕВЫЕ РИСКИ" />
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8, marginBottom: 8 }}>
              <RiskCard label="MAX DRAWDOWN"  value={`${fmtF(currentMetrics.maxDrawdown)}%`}     color="var(--t-red)" />
              <RiskCard label="ТЕКУЩИЙ DD"    value={`${fmtF(currentMetrics.currentDrawdown)}%`} color={currentMetrics.currentDrawdown > 5 ? 'var(--t-red)' : 'var(--t-text)'} />
              <RiskCard label="VaR 95%"       value={`${fmtF(currentMetrics.var95)}%`}           color="var(--t-red)" sub="1-дневный" />
              <RiskCard label="ЭКСПОЗИЦИЯ"    value={`${fmtF(currentMetrics.usedPct, 1)}%`}      sub="% времени в позиции" />
            </div>

            <SH label="КОЭФФИЦИЕНТЫ" />
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8, marginBottom: 8 }}>
              <RiskCard label="SHARPE"  value={fmtF(currentMetrics.sharpe)}  color={currentMetrics.sharpe > 1 ? 'var(--t-green)' : currentMetrics.sharpe < 0 ? 'var(--t-red)' : undefined} />
              <RiskCard label="SORTINO" value={fmtF(currentMetrics.sortino)} color={currentMetrics.sortino > 1 ? 'var(--t-green)' : undefined} />
              <RiskCard label="CALMAR"  value={fmtF(currentMetrics.calmar)}  color={currentMetrics.calmar > 1 ? 'var(--t-green)' : undefined} />
              <RiskCard label="PROFIT FACTOR" value={fmtF(currentMetrics.profitFactor)} color={currentMetrics.profitFactor >= 1.5 ? 'var(--t-green)' : currentMetrics.profitFactor < 1 ? 'var(--t-red)' : undefined} />
            </div>

            <SH label="ТОРГОВАЯ СТАТИСТИКА" />
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8, marginBottom: 12 }}>
              <RiskCard label="WIN RATE"        value={`${fmtF(currentMetrics.winRate, 1)}%`} color={currentMetrics.winRate >= 50 ? 'var(--t-green)' : 'var(--t-red)'} />
              <RiskCard label="СЕРИЯ УБЫТКОВ"   value={`${lStreak} подряд`} color={lStreak >= 5 ? 'var(--t-red)' : lStreak >= 3 ? 'var(--t-amber)' : undefined} />
              <RiskCard label="СЕРИЯ ПРИБЫЛЕЙ"  value={`${wStreak} подряд`} color={wStreak >= 5 ? 'var(--t-green)' : undefined} />
              <RiskCard label="ВСЕГО СДЕЛОК"    value={String(currentMetrics.numTrades)} />
            </div>

            {/* Drawdown chart */}
            {equityData.length > 1 && (
              <>
                <SH label="ПРОСАДКА (DRAWDOWN)" />
                <div style={{ background: 'var(--t-elevated)', borderRadius: 4, border: '1px solid var(--t-border)', padding: '8px', marginBottom: 8 }}>
                  <DrawdownChart equity={equityData} />
                </div>
              </>
            )}

            {/* Rolling Sharpe */}
            {trades.length >= 10 && (
              <>
                <SH label={`ROLLING SHARPE (окно 20 сделок)`} />
                <div style={{ background: 'var(--t-elevated)', borderRadius: 4, border: '1px solid var(--t-border)', padding: '8px', marginBottom: 8 }}>
                  <RollingSharpeChart trades={trades} />
                </div>
              </>
            )}

            {/* Worst / Best trade */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 16 }}>
              {worstTrade && (
                <div style={{ padding: '10px 12px', background: 'rgba(242,54,69,0.07)', borderRadius: 4, border: '1px solid rgba(242,54,69,0.2)' }}>
                  <div style={{ fontSize: 8, color: 'var(--t-red)', fontFamily: 'var(--t-font-mono)', fontWeight: 700, letterSpacing: 0.5, marginBottom: 4 }}>ХУДШАЯ СДЕЛКА</div>
                  <div style={{ fontSize: 14, fontWeight: 700, fontFamily: 'var(--t-font-mono)', color: 'var(--t-red)' }}>
                    {fmtF(worstTrade.pnl_pct ?? 0)}%
                  </div>
                  <div style={{ fontSize: 9, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)', marginTop: 2 }}>
                    {Math.round(worstTrade.pnl ?? 0).toLocaleString('ru-RU')} ₽
                  </div>
                </div>
              )}
              {bestTrade && (
                <div style={{ padding: '10px 12px', background: 'rgba(8,153,129,0.07)', borderRadius: 4, border: '1px solid rgba(8,153,129,0.2)' }}>
                  <div style={{ fontSize: 8, color: 'var(--t-green)', fontFamily: 'var(--t-font-mono)', fontWeight: 700, letterSpacing: 0.5, marginBottom: 4 }}>ЛУЧШАЯ СДЕЛКА</div>
                  <div style={{ fontSize: 14, fontWeight: 700, fontFamily: 'var(--t-font-mono)', color: 'var(--t-green)' }}>
                    +{fmtF(bestTrade.pnl_pct ?? 0)}%
                  </div>
                  <div style={{ fontSize: 9, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)', marginTop: 2 }}>
                    +{Math.round(bestTrade.pnl ?? 0).toLocaleString('ru-RU')} ₽
                  </div>
                </div>
              )}
            </div>
          </>
        ) : (
          <div style={{ padding: '12px', color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)', fontSize: 10 }}>
            Нет данных по текущей стратегии
          </div>
        )}

        {/* Cross-strategy risk table */}
        {allFullReports.length > 1 && (
          <>
            <SH label={`РИСК ПО СТРАТЕГИЯМ (${allFullReports.length})`} />
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr>
                    {['Стратегия', 'Инструмент', 'Max DD', 'Sharpe', 'Calmar', 'Win Rate', 'Сделок'].map(h => (
                      <th key={h} style={TH}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {reports.map((r, i) => {
                    const m = allMetrics[i]
                    const name = r.hypothesis_id.replace('tmpl_h_', '').replace(/_/g, ' ')
                    return (
                      <tr
                        key={r.report_id}
                        onClick={() => { setSelectedIdx(i); setActiveTab('terminal') }}
                        style={{ borderBottom: '1px solid rgba(255,255,255,0.04)', cursor: 'pointer' }}
                        onMouseEnter={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.03)')}
                        onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                      >
                        <td style={{ ...TD, color: 'var(--t-text)' }}>{name}</td>
                        <td style={{ ...TD, color: 'var(--t-text-3)' }}>{r.ticker}</td>
                        <td style={{ ...TD, color: m ? 'var(--t-red)' : 'var(--t-text-3)' }}>
                          {m ? `${fmtF(m.maxDrawdown)}%` : '—'}
                        </td>
                        <td style={{ ...TD, color: m ? (m.sharpe > 0 ? 'var(--t-green)' : 'var(--t-red)') : 'var(--t-text-3)' }}>
                          {m ? fmtF(m.sharpe) : '—'}
                        </td>
                        <td style={{ ...TD, color: 'var(--t-text-2)' }}>
                          {m ? fmtF(m.calmar) : '—'}
                        </td>
                        <td style={{ ...TD, color: m ? (m.winRate >= 50 ? 'var(--t-green)' : 'var(--t-red)') : 'var(--t-text-3)' }}>
                          {m ? `${fmtF(m.winRate, 0)}%` : '—'}
                        </td>
                        <td style={{ ...TD, color: 'var(--t-text-3)' }}>
                          {m?.numTrades ?? r.num_trades ?? '—'}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
