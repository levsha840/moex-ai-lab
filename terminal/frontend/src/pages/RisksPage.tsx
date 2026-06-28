import { useMemo, useState } from 'react'
import { IconShield } from '@tabler/icons-react'
import ReactECharts from 'echarts-for-react'
import { useTerminal } from '../context/TerminalContext'
import { metricsFromReport, metricsFromPaper, equityFromReport } from '../utils/portfolio'
import { TH, TD, TR_HOVER, SH_STYLE, CARD, CARD_LABEL, CARD_VALUE, echartsBase, fmtF, fmtPct, pnlColor, sortIcon } from '../styles/tokens'
import type { JournalEntry } from '../api/client'
import type { PortfolioMetrics } from '../utils/portfolio'

function losingStreak(trades: JournalEntry[]): number {
  let max = 0, cur = 0
  for (const t of trades) {
    if (t.is_winner === false) { cur++; max = Math.max(max, cur) } else cur = 0
  }
  return max
}

function winningStreak(trades: JournalEntry[]): number {
  let max = 0, cur = 0
  for (const t of trades) {
    if (t.is_winner === true) { cur++; max = Math.max(max, cur) } else cur = 0
  }
  return max
}

function RiskCard({ label, value, color, sub }: { label: string; value: string; color?: string; sub?: string }) {
  return (
    <div style={CARD}>
      <span style={CARD_LABEL}>{label}</span>
      <span style={{ ...CARD_VALUE, fontSize: 13, color: color ?? 'var(--t-text)' }}>{value}</span>
      {sub && <span style={{ fontSize: 8, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)' }}>{sub}</span>}
    </div>
  )
}

function SH({ label }: { label: string }) {
  return <div style={SH_STYLE}>{label}</div>
}

// ── Drawdown Chart (ECharts) ─────────────────────────────────────────────────
function DrawdownChart({ equity }: { equity: { time: number; value: number }[] }) {
  if (equity.length < 2) return null
  let peak = equity[0].value
  const ddData = equity.map(p => {
    if (p.value > peak) peak = p.value
    return peak > 0 ? +((p.value - peak) / peak * 100).toFixed(3) : 0
  })
  const times = equity.map(p => {
    const d = new Date(p.time * 1000)
    return `${d.getDate().toString().padStart(2,'0')}.${(d.getMonth()+1).toString().padStart(2,'0')}`
  })
  const minDD = Math.min(...ddData)

  const option = {
    ...echartsBase(),
    xAxis: { ...(echartsBase() as any).xAxis, data: times },
    yAxis: {
      ...(echartsBase() as any).yAxis,
      min: Math.floor(minDD * 1.1),
      max: 0,
      axisLabel: { color: '#6c7282', fontSize: 8, formatter: (v: number) => `${v.toFixed(1)}%` },
    },
    series: [{
      type: 'line', data: ddData, smooth: false, symbol: 'none',
      lineStyle: { color: '#f23645', width: 1 },
      areaStyle: { color: 'rgba(242,54,69,0.12)' },
    }],
    tooltip: {
      ...(echartsBase() as any).tooltip,
      formatter: (p: any) => `Drawdown: <b>${p[0].value.toFixed(2)}%</b>`,
    },
  }
  return <ReactECharts style={{ height: 160 }} option={option} notMerge />
}

// ── Rolling Sharpe ───────────────────────────────────────────────────────────
function RollingSharpeChart({ trades: tds }: { trades: JournalEntry[] }) {
  if (tds.length < 15) return null
  const WINDOW = Math.min(20, Math.floor(tds.length / 3))
  const returns = tds.map(t => t.pnl_pct ?? 0)
  const rolling: number[] = []
  const labels: string[] = []
  for (let i = WINDOW; i <= returns.length; i++) {
    const w = returns.slice(i - WINDOW, i)
    const mean = w.reduce((s, v) => s + v, 0) / WINDOW
    const std  = Math.sqrt(w.reduce((s, v) => s + (v - mean) ** 2, 0) / WINDOW)
    rolling.push(std > 0 ? +(mean / std * Math.sqrt(252)).toFixed(3) : 0)
    labels.push(`${i}`)
  }
  const option = {
    ...echartsBase(),
    xAxis: { ...(echartsBase() as any).xAxis, data: labels, axisLabel: { color: '#6c7282', fontSize: 8, interval: Math.floor(labels.length / 5) } },
    yAxis: { ...(echartsBase() as any).yAxis, axisLabel: { color: '#6c7282', fontSize: 8, formatter: (v: number) => v.toFixed(1) } },
    series: [{
      type: 'line', data: rolling, smooth: true, symbol: 'none',
      lineStyle: { color: '#2962ff', width: 1 },
      areaStyle: { color: 'rgba(41,98,255,0.07)' },
      markLine: {
        data: [{ yAxis: 0, lineStyle: { color: '#434651', type: 'dashed' as any, width: 1 } }],
        label: { show: false }, symbol: 'none',
      },
    }],
    tooltip: {
      ...(echartsBase() as any).tooltip,
      formatter: (p: any) => `Rolling Sharpe: <b>${p[0].value.toFixed(2)}</b>`,
    },
  }
  return <ReactECharts style={{ height: 140 }} option={option} notMerge />
}

// ── PnL Distribution ─────────────────────────────────────────────────────────
function PnlDistribution({ trades: tds }: { trades: JournalEntry[] }) {
  if (tds.length < 5) return null
  const BINS = 15
  const pcts = tds.map(t => t.pnl_pct ?? 0)
  const min = Math.min(...pcts), max = Math.max(...pcts)
  const step = (max - min) / BINS || 1
  const bins = Array.from({ length: BINS }, (_, i) => ({ label: `${(min + i * step).toFixed(1)}%`, count: 0, win: 0 }))
  pcts.forEach((v, idx) => {
    const i = Math.min(Math.floor((v - min) / step), BINS - 1)
    bins[i].count++
    if (tds[idx].is_winner !== false) bins[i].win++
  })
  const option = {
    ...echartsBase({ grid: { top: 28, right: 12, bottom: 28, left: 46 } }),
    xAxis: {
      type: 'category', data: bins.map(b => b.label),
      axisLine: { lineStyle: { color: '#2a2e39' } },
      axisLabel: { color: '#6c7282', fontSize: 7, rotate: 30 },
    },
    yAxis: { type: 'value', axisLabel: { color: '#6c7282', fontSize: 8 }, splitLine: { lineStyle: { color: '#1e222d', type: 'dashed' as any } } },
    series: [{
      type: 'bar',
      data: bins.map(b => ({
        value: b.count,
        itemStyle: { color: b.win / (b.count || 1) >= 0.5 ? '#08998133' : '#f2364533', borderColor: b.win / (b.count || 1) >= 0.5 ? '#089981' : '#f23645', borderWidth: 1 },
      })),
    }],
    tooltip: {
      ...(echartsBase() as any).tooltip,
      formatter: (p: any) => `${bins[p.dataIndex].label}: ${p.value} сделок`,
    },
  }
  return <ReactECharts style={{ height: 130 }} option={option} notMerge />
}

// ── Cross-strategy table ──────────────────────────────────────────────────────
type CSort = 'name' | 'dd' | 'sharpe' | 'calmar' | 'wr' | 'trades'

function CrossStratTable() {
  const { allFullReports, reports, setSelectedIdx, setActiveTab } = useTerminal()
  const [sortKey, setSortKey] = useState<CSort>('sharpe')
  const [sortDir, setSortDir] = useState<1|-1>(-1)

  const allMetrics = useMemo(() =>
    allFullReports.map(r => { try { return metricsFromReport(r) } catch { return null } })
  , [allFullReports])

  if (allFullReports.length <= 1) return null

  const toggleSort = (k: CSort) => {
    if (sortKey === k) setSortDir(d => d === 1 ? -1 : 1); else { setSortKey(k); setSortDir(-1) }
  }
  const si = (k: CSort) => sortIcon(sortKey === k, sortDir)

  const rows = reports.map((r, i) => ({ r, m: allMetrics[i], i })).sort((a, b) => {
    if (sortKey === 'name') return sortDir * (a.r.hypothesis_id ?? '').localeCompare(b.r.hypothesis_id ?? '')
    const vals: Record<CSort, [number, number]> = {
      name:   [0,0],
      dd:     [a.m?.maxDrawdown  ?? 0, b.m?.maxDrawdown  ?? 0],
      sharpe: [a.m?.sharpe       ?? -999, b.m?.sharpe    ?? -999],
      calmar: [a.m?.calmar       ?? -999, b.m?.calmar    ?? -999],
      wr:     [a.m?.winRate      ?? 0, b.m?.winRate      ?? 0],
      trades: [a.m?.numTrades    ?? 0, b.m?.numTrades    ?? 0],
    }
    return (vals[sortKey][0] - vals[sortKey][1]) * sortDir
  })

  const thStyle = (k: CSort): React.CSSProperties => ({
    ...TH, cursor: 'pointer',
    color: sortKey === k ? 'var(--t-accent)' : 'var(--t-text-3)',
  })

  return (
    <>
      <SH label={`СРАВНЕНИЕ СТРАТЕГИЙ (${allFullReports.length})`} />
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <th style={thStyle('name')} onClick={() => toggleSort('name')}>Стратегия{si('name')}</th>
              <th style={TH}>Инструмент</th>
              <th style={{ ...thStyle('dd'),     textAlign: 'right' }} onClick={() => toggleSort('dd')}>Max DD{si('dd')}</th>
              <th style={{ ...thStyle('sharpe'), textAlign: 'right' }} onClick={() => toggleSort('sharpe')}>Sharpe{si('sharpe')}</th>
              <th style={{ ...thStyle('calmar'), textAlign: 'right' }} onClick={() => toggleSort('calmar')}>Calmar{si('calmar')}</th>
              <th style={{ ...thStyle('wr'),     textAlign: 'right' }} onClick={() => toggleSort('wr')}>Win Rate{si('wr')}</th>
              <th style={{ ...thStyle('trades'), textAlign: 'right' }} onClick={() => toggleSort('trades')}>Сделок{si('trades')}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ r, m, i }) => {
              const name = r.hypothesis_id.replace('tmpl_h_', '').replace(/_/g, ' ')
              return (
                <tr
                  key={r.report_id}
                  onClick={() => { setSelectedIdx(i); setActiveTab('terminal') }}
                  style={TR_HOVER}
                  onMouseEnter={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.03)')}
                  onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                >
                  <td style={{ ...TD, color: 'var(--t-text)' }}>{name}</td>
                  <td style={{ ...TD, color: 'var(--t-text-3)' }}>{r.ticker}</td>
                  <td style={{ ...TD, color: 'var(--t-red)', textAlign: 'right' }}>{m ? `${fmtF(m.maxDrawdown)}%` : '—'}</td>
                  <td style={{ ...TD, textAlign: 'right', color: m ? (m.sharpe > 1 ? 'var(--t-green)' : m.sharpe < 0 ? 'var(--t-red)' : 'var(--t-text-2)') : 'var(--t-text-3)' }}>
                    {m ? fmtF(m.sharpe) : '—'}
                  </td>
                  <td style={{ ...TD, textAlign: 'right', color: m ? (m.calmar > 1 ? 'var(--t-green)' : 'var(--t-text-2)') : 'var(--t-text-3)' }}>
                    {m ? fmtF(m.calmar) : '—'}
                  </td>
                  <td style={{ ...TD, textAlign: 'right', color: m ? (m.winRate >= 50 ? 'var(--t-green)' : 'var(--t-red)') : 'var(--t-text-3)' }}>
                    {m ? `${fmtF(m.winRate, 0)}%` : '—'}
                  </td>
                  <td style={{ ...TD, textAlign: 'right', color: 'var(--t-text-3)' }}>{m?.numTrades ?? r.num_trades ?? '—'}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </>
  )
}

// ── Main ─────────────────────────────────────────────────────────────────────
export default function RisksPage() {
  const { fullReport, allFullReports, trades, paper, candles } = useTerminal()

  const currentMetrics = useMemo(() => {
    if (fullReport) { try { return metricsFromReport(fullReport) } catch { return null } }
    if (paper)      { try { return metricsFromPaper(paper)       } catch { return null } }
    return null
  }, [fullReport, paper])

  const worstTrade = useMemo(() => trades.length ? trades.reduce((w, t) => (t.pnl_pct ?? 0) < (w.pnl_pct ?? 0) ? t : w) : null, [trades])
  const bestTrade  = useMemo(() => trades.length ? trades.reduce((b, t) => (t.pnl_pct ?? 0) > (b.pnl_pct ?? 0) ? t : b) : null, [trades])
  const lStreak = useMemo(() => losingStreak(trades), [trades])
  const wStreak = useMemo(() => winningStreak(trades), [trades])

  const equityData = useMemo(() => {
    if (fullReport && candles.length) { try { return equityFromReport(fullReport, candles) } catch { return [] } }
    return []
  }, [fullReport, candles])

  if (!currentMetrics && allFullReports.length === 0) {
    return (
      <div style={{ height: '100%', display: 'flex', flexDirection: 'column', background: 'var(--t-bg)', overflow: 'hidden' }}>
        <Header />
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 12, color: 'var(--t-text-3)' }}>
          <IconShield size={40} style={{ opacity: 0.15 }} />
          <div style={{ fontSize: 12, fontFamily: 'var(--t-font-mono)' }}>Нет данных</div>
          <div style={{ fontSize: 10 }}>Запустите бэктест для получения риск-метрик</div>
        </div>
      </div>
    )
  }

  const m = currentMetrics

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', background: 'var(--t-bg)', overflow: 'hidden' }}>
      <Header label={m?.strategyLabel} />

      <div style={{ flex: 1, overflowY: 'auto', padding: '10px 14px' }}>
        {m ? (
          <>
            {/* Row 1: drawdown/var/exposure */}
            <SH label="КЛЮЧЕВЫЕ РИСКИ" />
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 6, marginBottom: 6 }}>
              <RiskCard label="MAX DRAWDOWN"    value={`${fmtF(m.maxDrawdown)}%`}       color="var(--t-red)" />
              <RiskCard label="ТЕКУЩИЙ DD"      value={`${fmtF(m.currentDrawdown)}%`}   color={m.currentDrawdown > 5 ? 'var(--t-red)' : 'var(--t-text)'} />
              <RiskCard label="VaR 95%"         value={`${fmtF(m.var95)}%`}             color="var(--t-red)" sub="1-дневный" />
              <RiskCard label="ЭКСПОЗИЦИЯ"      value={`${fmtF(m.usedPct, 1)}%`}       sub="% времени в позиции" />
              <RiskCard label="СДЕЛОК"          value={String(m.numTrades)} />
            </div>

            {/* Row 2: ratios */}
            <SH label="КОЭФФИЦИЕНТЫ" />
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 6, marginBottom: 6 }}>
              <RiskCard label="SHARPE"          value={fmtF(m.sharpe)}   color={m.sharpe > 1 ? 'var(--t-green)' : m.sharpe < 0 ? 'var(--t-red)' : undefined} />
              <RiskCard label="SORTINO"         value={fmtF(m.sortino)}  color={m.sortino > 1 ? 'var(--t-green)' : undefined} />
              <RiskCard label="CALMAR"          value={fmtF(m.calmar)}   color={m.calmar > 1 ? 'var(--t-green)' : undefined} />
              <RiskCard label="PROFIT FACTOR"   value={fmtF(m.profitFactor)} color={m.profitFactor >= 1.5 ? 'var(--t-green)' : m.profitFactor < 1 ? 'var(--t-red)' : undefined} />
              <RiskCard label="WIN RATE"        value={`${fmtF(m.winRate, 1)}%`} color={m.winRate >= 50 ? 'var(--t-green)' : 'var(--t-red)'} />
            </div>

            {/* Row 3: streaks + worst/best */}
            <SH label="ТОРГОВАЯ СТАТИСТИКА" />
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 6, marginBottom: 8 }}>
              <RiskCard label="СЕРИЯ УБЫТКОВ"   value={`${lStreak} подряд`} color={lStreak >= 5 ? 'var(--t-red)' : lStreak >= 3 ? 'var(--t-amber)' : undefined} />
              <RiskCard label="СЕРИЯ ПРИБЫЛЕЙ"  value={`${wStreak} подряд`} color={wStreak >= 5 ? 'var(--t-green)' : undefined} />
              {worstTrade && <RiskCard label="ХУДШАЯ СДЕЛКА"  value={`${fmtF(worstTrade.pnl_pct ?? 0)}%`} color="var(--t-red)"   sub={`${Math.round(worstTrade.pnl ?? 0).toLocaleString('ru-RU')} ₽`} />}
              {bestTrade  && <RiskCard label="ЛУЧШАЯ СДЕЛКА"  value={`+${fmtF(bestTrade.pnl_pct ?? 0)}%`} color="var(--t-green)" sub={`+${Math.round(bestTrade.pnl ?? 0).toLocaleString('ru-RU')} ₽`} />}
            </div>

            {/* Charts — 2-column layout */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 8 }}>
              {equityData.length > 1 && (
                <div>
                  <SH label="ПРОСАДКА" />
                  <div style={{ background: 'var(--t-elevated)', borderRadius: 4, border: '1px solid var(--t-border)', padding: '4px' }}>
                    <DrawdownChart equity={equityData} />
                  </div>
                </div>
              )}
              {trades.length >= 15 && (
                <div>
                  <SH label="ROLLING SHARPE (окно 20)" />
                  <div style={{ background: 'var(--t-elevated)', borderRadius: 4, border: '1px solid var(--t-border)', padding: '4px' }}>
                    <RollingSharpeChart trades={trades} />
                  </div>
                </div>
              )}
              {trades.length >= 5 && (
                <div>
                  <SH label="РАСПРЕДЕЛЕНИЕ PnL" />
                  <div style={{ background: 'var(--t-elevated)', borderRadius: 4, border: '1px solid var(--t-border)', padding: '4px' }}>
                    <PnlDistribution trades={trades} />
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

        {/* Cross-strategy comparison */}
        <CrossStratTable />
      </div>
    </div>
  )
}

function Header({ label }: { label?: string }) {
  return (
    <div style={{ height: 40, flexShrink: 0, display: 'flex', alignItems: 'center', padding: '0 12px', background: 'var(--t-panel)', borderBottom: '1px solid var(--t-border)', gap: 8 }}>
      <IconShield size={12} color="var(--t-text-3)" />
      <span style={{ fontSize: 11, fontWeight: 700, fontFamily: 'var(--t-font-mono)', color: 'var(--t-text)', letterSpacing: 1 }}>РИСК-МЕТРИКИ</span>
      {label && <span style={{ fontSize: 9, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)' }}>· {label}</span>}
    </div>
  )
}
