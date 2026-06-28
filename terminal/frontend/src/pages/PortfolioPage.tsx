import { useMemo } from 'react'
import { IconBriefcase, IconAlertTriangle } from '@tabler/icons-react'
import { useTerminal } from '../context/TerminalContext'
import { metricsFromReport, metricsFromPaper } from '../utils/portfolio'
import type { ReportSummary, Report } from '../api/client'
import type { PortfolioMetrics } from '../utils/portfolio'

// ── Helpers ────────────────────────────────────────────────────────────────────
function fmtRub(n: number) {
  return `${n >= 0 ? '+' : ''}${Math.round(n).toLocaleString('ru-RU')} ₽`
}
function fmtPct(n: number) { return `${n >= 0 ? '+' : ''}${n.toFixed(2)}%` }
function fmtFmt(n: number, d = 2) { return n.toFixed(d) }
function pnlCol(n: number) { return n >= 0 ? 'var(--t-green)' : 'var(--t-red)' }

function PageHeader({ badge }: { badge?: React.ReactNode }) {
  return (
    <div style={{ height: 44, flexShrink: 0, display: 'flex', alignItems: 'center', padding: '0 16px', background: 'var(--t-panel)', borderBottom: '1px solid var(--t-border)', gap: 10 }}>
      <IconBriefcase size={13} color="var(--t-text-3)" />
      <span style={{ fontSize: 11, fontWeight: 700, fontFamily: 'var(--t-font-mono)', color: 'var(--t-text)', letterSpacing: 1 }}>ПОРТФЕЛЬ</span>
      {badge}
    </div>
  )
}

function Badge({ text, color }: { text: string; color: string }) {
  return (
    <span style={{ fontSize: 9, padding: '2px 7px', borderRadius: 2, fontFamily: 'var(--t-font-mono)', fontWeight: 700, letterSpacing: 0.5, background: color + '22', color, border: `1px solid ${color}44` }}>
      {text}
    </span>
  )
}

function MetricCard({ label, value, color }: { label: string; value: React.ReactNode; color?: string }) {
  return (
    <div style={{ padding: '10px 12px', background: 'var(--t-elevated)', borderRadius: 4, border: '1px solid var(--t-border)', display: 'flex', flexDirection: 'column', gap: 5 }}>
      <span style={{ fontSize: 8, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)', letterSpacing: 0.5, fontWeight: 700 }}>{label}</span>
      <span style={{ fontSize: 14, fontWeight: 700, fontFamily: 'var(--t-font-mono)', color: color ?? 'var(--t-text)' }}>{value}</span>
    </div>
  )
}

function MetricsGrid({ m }: { m: PortfolioMetrics }) {
  return (
    <>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8, marginBottom: 10 }}>
        <MetricCard label="НАЧАЛЬНЫЙ КАПИТАЛ" value={`${Math.round(m.initialCapital).toLocaleString('ru-RU')} ₽`} />
        <MetricCard label="ТЕКУЩИЙ КАПИТАЛ"   value={`${Math.round(m.currentCapital).toLocaleString('ru-RU')} ₽`} />
        <MetricCard label="PnL"               value={fmtRub(m.pnl)}    color={pnlCol(m.pnl)} />
        <MetricCard label="ДОХОДНОСТЬ"         value={fmtPct(m.pnlPct)} color={pnlCol(m.pnlPct)} />
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8, marginBottom: 16 }}>
        <MetricCard label="MAX DRAWDOWN"  value={`${fmtFmt(m.maxDrawdown)}%`}   color="var(--t-red)" />
        <MetricCard label="WIN RATE"      value={`${fmtFmt(m.winRate, 1)}%`} />
        <MetricCard label="СДЕЛОК"        value={String(m.numTrades)} />
        <MetricCard label="ЭКСПОЗИЦИЯ"    value={`${fmtFmt(m.usedPct, 1)}%`} />
      </div>
    </>
  )
}

function StrategyRow({ r, m, onClick }: { r: ReportSummary; m: PortfolioMetrics | null; onClick: () => void }) {
  const name = r.hypothesis_id.replace('tmpl_h_', '').replace(/_/g, ' ')
  return (
    <tr
      onClick={onClick}
      style={{ borderBottom: '1px solid rgba(255,255,255,0.04)', cursor: 'pointer' }}
      onMouseEnter={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.03)')}
      onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
    >
      <td style={{ padding: '7px 10px', color: 'var(--t-text)', fontSize: 10, fontFamily: 'var(--t-font-mono)' }}>{name}</td>
      <td style={{ padding: '7px 10px', color: 'var(--t-text-2)', fontSize: 10, fontFamily: 'var(--t-font-mono)' }}>{r.ticker}</td>
      <td style={{ padding: '7px 10px', fontSize: 10, fontFamily: 'var(--t-font-mono)', color: pnlCol(r.total_return_pct) }}>{fmtPct(r.total_return_pct)}</td>
      <td style={{ padding: '7px 10px', color: 'var(--t-red)', fontSize: 10, fontFamily: 'var(--t-font-mono)' }}>{m ? `${m.maxDrawdown.toFixed(1)}%` : '—'}</td>
      <td style={{ padding: '7px 10px', color: 'var(--t-text-2)', fontSize: 10, fontFamily: 'var(--t-font-mono)' }}>{m ? `${m.winRate.toFixed(0)}%` : '—'}</td>
      <td style={{ padding: '7px 10px', color: 'var(--t-text-2)', fontSize: 10, fontFamily: 'var(--t-font-mono)' }}>{m?.numTrades ?? r.num_trades ?? '—'}</td>
    </tr>
  )
}

const TH_STYLE: React.CSSProperties = {
  padding: '6px 10px', color: 'var(--t-text-3)', fontWeight: 600, letterSpacing: 0.5,
  fontSize: 9, textAlign: 'left', background: 'var(--t-elevated)',
  borderBottom: '1px solid var(--t-border)', fontFamily: 'var(--t-font-mono)',
  position: 'sticky', top: 0, zIndex: 1,
}

function StrategyTable({ reports, allFullReports, setSelectedIdx, setActiveTab }: {
  reports: ReportSummary[]
  allFullReports: Report[]
  setSelectedIdx: (i: number) => void
  setActiveTab: (t: any) => void
}) {
  const metrics = useMemo(() =>
    allFullReports.map(r => { try { return metricsFromReport(r) } catch { return null } })
  , [allFullReports])

  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            {['Стратегия', 'Инструмент', 'Доходность', 'Max DD', 'Win Rate', 'Сделок'].map(h => (
              <th key={h} style={TH_STYLE}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {reports.map((r, i) => (
            <StrategyRow
              key={r.report_id}
              r={r}
              m={metrics[i] ?? null}
              onClick={() => { setSelectedIdx(i); setActiveTab('terminal') }}
            />
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ── Main component ─────────────────────────────────────────────────────────────
export default function PortfolioPage() {
  const { paper, allFullReports, reports, setSelectedIdx, setActiveTab } = useTerminal()

  const hasReports = allFullReports.length > 0
  const hasPaper   = !!paper

  const paperMetrics  = useMemo(() => paper ? metricsFromPaper(paper) : null, [paper])
  const allMetrics    = useMemo(() =>
    allFullReports.map(r => { try { return metricsFromReport(r) } catch { return null } })
  , [allFullReports])

  // ── State 1: no data ────────────────────────────────────────────────────────
  if (!hasReports && !hasPaper) {
    return (
      <div style={{ height: '100%', display: 'flex', flexDirection: 'column', background: 'var(--t-bg)', overflow: 'hidden' }}>
        <PageHeader />
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 12, color: 'var(--t-text-3)' }}>
          <IconBriefcase size={40} style={{ opacity: 0.15 }} />
          <div style={{ fontSize: 12, fontFamily: 'var(--t-font-mono)' }}>Ожидает стратегий для Paper Trading</div>
          <div style={{ fontSize: 10, color: 'var(--t-text-3)', textAlign: 'center', maxWidth: 340, lineHeight: 1.7 }}>
            Запустите бэктест и отправьте кандидата на бумажную торговлю
          </div>
        </div>
      </div>
    )
  }

  // ── State 2: paper trading active ───────────────────────────────────────────
  if (hasPaper && paperMetrics) {
    return (
      <div style={{ height: '100%', display: 'flex', flexDirection: 'column', background: 'var(--t-bg)', overflow: 'hidden' }}>
        <PageHeader badge={<Badge text="PAPER TRADING" color="var(--t-green)" />} />
        <div style={{ flex: 1, overflowY: 'auto', padding: 16 }}>
          <MetricsGrid m={paperMetrics} />
          {paper.note && (
            <div style={{ marginBottom: 16, padding: '8px 12px', background: 'var(--t-elevated)', borderRadius: 4, fontSize: 9, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)', lineHeight: 1.6 }}>
              {paper.note}
            </div>
          )}
          {reports.length > 0 && (
            <>
              <div style={{ fontSize: 9, letterSpacing: 0.8, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)', fontWeight: 700, padding: '6px 0 8px' }}>
                СТРАТЕГИИ В ПОРТФЕЛЕ
              </div>
              <StrategyTable reports={reports} allFullReports={allFullReports} setSelectedIdx={setSelectedIdx} setActiveTab={setActiveTab} />
            </>
          )}
        </div>
      </div>
    )
  }

  // ── State 3: backtest only ───────────────────────────────────────────────────
  const validMetrics = allMetrics.filter(Boolean) as PortfolioMetrics[]
  const totalInitial = validMetrics.reduce((s, m) => s + m.initialCapital, 0)
  const totalFinal   = validMetrics.reduce((s, m) => s + m.currentCapital, 0)
  const avgReturn    = validMetrics.length > 0 ? validMetrics.reduce((s, m) => s + m.pnlPct, 0) / validMetrics.length : 0
  const bestReturn   = validMetrics.length > 0 ? Math.max(...validMetrics.map(m => m.pnlPct)) : 0

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', background: 'var(--t-bg)', overflow: 'hidden' }}>
      <PageHeader badge={<Badge text="БЭКТЕСТ · НЕ PAPER TRADING" color="var(--t-amber)" />} />
      <div style={{ flex: 1, overflowY: 'auto', padding: 16 }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8, marginBottom: 10 }}>
          <MetricCard label="СУММАРНЫЙ КАПИТАЛ"    value={`${Math.round(totalFinal).toLocaleString('ru-RU')} ₽`} />
          <MetricCard label="СУММАРНЫЙ PnL"        value={fmtRub(totalFinal - totalInitial)} color={pnlCol(totalFinal - totalInitial)} />
          <MetricCard label="СРЕДНЯЯ ДОХОДНОСТЬ"   value={fmtPct(avgReturn)}  color={pnlCol(avgReturn)} />
          <MetricCard label="ЛУЧШИЙ РЕЗУЛЬТАТ"     value={fmtPct(bestReturn)} color={pnlCol(bestReturn)} />
        </div>

        <div style={{ marginBottom: 14, padding: '8px 12px', background: 'rgba(255,184,0,0.07)', borderRadius: 4, border: '1px solid rgba(255,184,0,0.2)', display: 'flex', gap: 8, alignItems: 'center' }}>
          <IconAlertTriangle size={12} color="var(--t-amber)" />
          <span style={{ fontSize: 9, color: 'var(--t-amber)', fontFamily: 'var(--t-font-mono)' }}>
            Paper Trading не запущен — данные из бэктестов, не из реальных сделок
          </span>
        </div>

        <div style={{ fontSize: 9, letterSpacing: 0.8, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)', fontWeight: 700, padding: '4px 0 8px' }}>
          БЭКТЕСТ-СТРАТЕГИИ ({reports.length})
        </div>
        <StrategyTable reports={reports} allFullReports={allFullReports} setSelectedIdx={setSelectedIdx} setActiveTab={setActiveTab} />
      </div>
    </div>
  )
}
