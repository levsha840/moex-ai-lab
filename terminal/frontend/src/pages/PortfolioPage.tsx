import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { IconBriefcase, IconAlertTriangle } from '@tabler/icons-react'
import { useTerminal } from '../context/TerminalContext'
import { metricsFromReport, metricsFromPaper, equityFromReport, equityFromPaperTrades } from '../utils/portfolio'
import { fetchPaperTrades, fetchPaperPositions } from '../api/client'
import EquityChart from '../components/chart/EquityChart'
import type { ReportSummary, Report, Trade, Position } from '../api/client'
import type { PortfolioMetrics, EquityPoint } from '../utils/portfolio'
import { TH, TD, fmtRub, fmtPct, fmtF, pnlColor } from '../styles/tokens'

// ── Shared primitives ─────────────────────────────────────────────────────────

function PageHeader({ badge }: { badge?: React.ReactNode }) {
  return (
    <div style={{ height: 40, flexShrink: 0, display: 'flex', alignItems: 'center', padding: '0 12px', background: 'var(--t-panel)', borderBottom: '1px solid var(--t-border)', gap: 8 }}>
      <IconBriefcase size={12} color="var(--t-text-3)" />
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

function Card({ label, value, color, sub }: { label: string; value: React.ReactNode; color?: string; sub?: string }) {
  return (
    <div style={{ padding: '8px 10px', background: 'var(--t-elevated)', borderRadius: 4, border: '1px solid var(--t-border)', display: 'flex', flexDirection: 'column', gap: 3 }}>
      <span style={{ fontSize: 8, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)', fontWeight: 700, letterSpacing: 0.5 }}>{label}</span>
      <span style={{ fontSize: 13, fontWeight: 700, fontFamily: 'var(--t-font-mono)', color: color ?? 'var(--t-text)' }}>{value}</span>
      {sub && <span style={{ fontSize: 8, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)' }}>{sub}</span>}
    </div>
  )
}

function SH({ label }: { label: string }) {
  return (
    <div style={{ fontSize: 9, letterSpacing: 0.8, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)', fontWeight: 700, padding: '10px 0 6px' }}>
      {label}
    </div>
  )
}

function EquitySection({ title, data, label }: { title: string; data: EquityPoint[]; label: string }) {
  return (
    <>
      <SH label={title} />
      <div style={{ marginBottom: 14, background: 'var(--t-elevated)', borderRadius: 4, border: '1px solid var(--t-border)', padding: 4 }}>
        <EquityChart primaryData={data} primaryLabel={label} height={200} compact />
      </div>
    </>
  )
}

// ── Paper Trading mode ────────────────────────────────────────────────────────
// Uses ONLY: paper (PaperSummary), paperTrades, paperPositions
// Does NOT use: fullReport, allFullReports, candles, reports (backtest)

function PaperPositionsTable({ positions }: { positions: Position[] }) {
  if (!positions.length) {
    return <div style={{ padding: '12px 0', fontSize: 10, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)' }}>Нет открытых позиций</div>
  }
  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            {['Тикер', 'Вход ₽', 'Тек. ₽', 'PnL ₽'].map(h => <th key={h} style={TH}>{h}</th>)}
          </tr>
        </thead>
        <tbody>
          {positions.map(p => (
            <tr key={p.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
              <td style={{ ...TD, color: 'var(--t-text)' }}>{p.ticker}</td>
              <td style={{ ...TD, color: 'var(--t-text-2)' }}>{p.entry_price.toFixed(2)}</td>
              <td style={{ ...TD, color: 'var(--t-text-2)' }}>{p.current_price.toFixed(2)}</td>
              <td style={{ ...TD, color: pnlColor(p.pnl), fontWeight: 600 }}>{fmtRub(p.pnl)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function PaperTradesTable({ trades }: { trades: Trade[] }) {
  if (!trades.length) {
    return <div style={{ padding: '12px 0', fontSize: 10, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)' }}>Нет закрытых сделок</div>
  }
  const sorted = [...trades].sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())
  const fmtDate = (s: string) => {
    try {
      const d = new Date(s)
      return `${String(d.getDate()).padStart(2,'0')}.${String(d.getMonth()+1).padStart(2,'0')}.${String(d.getFullYear()).slice(2)}`
    } catch { return s.slice(0, 10) }
  }
  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            {['Дата', 'Тикер', 'Вход ₽', 'Выход ₽', 'PnL ₽'].map(h => <th key={h} style={TH}>{h}</th>)}
          </tr>
        </thead>
        <tbody>
          {sorted.map(t => (
            <tr key={t.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
              <td style={{ ...TD, color: 'var(--t-text-3)' }}>{fmtDate(t.date)}</td>
              <td style={{ ...TD, color: 'var(--t-text)' }}>{t.ticker}</td>
              <td style={{ ...TD, color: 'var(--t-text-2)' }}>{t.entry_price.toFixed(2)}</td>
              <td style={{ ...TD, color: 'var(--t-text-2)' }}>{t.exit_price.toFixed(2)}</td>
              <td style={{ ...TD, color: pnlColor(t.pnl), fontWeight: 600 }}>{fmtRub(t.pnl)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function PaperPortfolio({ initialCapital, metrics }: { initialCapital: number; metrics: PortfolioMetrics }) {
  // Fetch ONLY paper-specific data. No backtest data used here.
  const { data: paperTrades = []    } = useQuery({ queryKey: ['paper-trades'],     queryFn: fetchPaperTrades })
  const { data: paperPositions = [] } = useQuery({ queryKey: ['paper-positions'],  queryFn: fetchPaperPositions })

  const paperEquity = useMemo(
    () => equityFromPaperTrades(paperTrades, initialCapital),
    [paperTrades, initialCapital]
  )

  const isFlat = paperTrades.length === 0

  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: '10px 14px' }}>

      {/* Paper metrics — source: PaperSummary only */}
      <SH label="КАПИТАЛ" />
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 6, marginBottom: 6 }}>
        <Card label="НАЧАЛЬНЫЙ"       value={`${Math.round(initialCapital).toLocaleString('ru-RU')} ₽`} />
        <Card label="ТЕКУЩИЙ"         value={`${Math.round(metrics.currentCapital).toLocaleString('ru-RU')} ₽`} />
        <Card label="PnL"             value={fmtRub(metrics.pnl)}      color={pnlColor(metrics.pnl)} />
        <Card label="ДОХОДНОСТЬ"      value={fmtPct(metrics.pnlPct)}   color={pnlColor(metrics.pnlPct)} />
        <Card label="MAX DRAWDOWN"    value={`${fmtF(metrics.maxDrawdown)}%`} color="var(--t-red)" />
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 6, marginBottom: 10 }}>
        <Card label="WIN RATE"        value={`${fmtF(metrics.winRate, 1)}%`} />
        <Card label="СДЕЛОК"          value={String(metrics.numTrades)} />
        <Card label="ПОЗИЦИИ (ОТКР.)" value={String(metrics.usedPct > 0 ? '—' : '0')} />
        <Card label="ЭКСПОЗИЦИЯ"      value={`${fmtF(metrics.usedPct, 1)}%`} />
      </div>

      {/* Paper Equity — source: paperTrades only */}
      <SH label={isFlat ? 'EQUITY PAPER — НЕТ СДЕЛОК (горизонталь на уровне начального капитала)' : 'EQUITY PAPER'} />
      <div style={{ marginBottom: 14, background: 'var(--t-elevated)', borderRadius: 4, border: '1px solid var(--t-border)', padding: 4 }}>
        <EquityChart primaryData={paperEquity} primaryLabel="Paper" height={200} compact />
      </div>

      {/* Positions — source: /paper/positions */}
      <SH label={`ПОЗИЦИИ (${paperPositions.length})`} />
      <PaperPositionsTable positions={paperPositions} />

      {/* Trades — source: /paper/trades */}
      <SH label={`ЗАКРЫТЫЕ СДЕЛКИ (${paperTrades.length})`} />
      <PaperTradesTable trades={paperTrades} />
    </div>
  )
}

// ── Backtest mode ─────────────────────────────────────────────────────────────
// Uses ONLY: fullReport, allFullReports, reports, candles
// Does NOT use: paper, PaperSummary, paperTrades, paperPositions

const TH_STYLE: React.CSSProperties = {
  padding: '5px 10px', color: 'var(--t-text-3)', fontWeight: 600, letterSpacing: 0.5,
  fontSize: 9, textAlign: 'left', background: 'var(--t-elevated)',
  borderBottom: '1px solid var(--t-border)', fontFamily: 'var(--t-font-mono)',
  position: 'sticky', top: 0, zIndex: 1,
}

function BacktestStratRow({ r, m, onClick }: { r: ReportSummary; m: PortfolioMetrics | null; onClick: () => void }) {
  const name = r.hypothesis_id.replace('tmpl_h_', '').replace(/_/g, ' ')
  return (
    <tr
      onClick={onClick}
      style={{ borderBottom: '1px solid rgba(255,255,255,0.04)', cursor: 'pointer' }}
      onMouseEnter={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.03)')}
      onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
    >
      <td style={{ padding: '6px 10px', color: 'var(--t-text)', fontSize: 10, fontFamily: 'var(--t-font-mono)' }}>{name}</td>
      <td style={{ padding: '6px 10px', color: 'var(--t-text-2)', fontSize: 10, fontFamily: 'var(--t-font-mono)' }}>{r.ticker}</td>
      <td style={{ padding: '6px 10px', fontSize: 10, fontFamily: 'var(--t-font-mono)', color: pnlColor(r.total_return_pct) }}>{fmtPct(r.total_return_pct)}</td>
      <td style={{ padding: '6px 10px', color: 'var(--t-red)', fontSize: 10, fontFamily: 'var(--t-font-mono)' }}>{m ? `${m.maxDrawdown.toFixed(1)}%` : '—'}</td>
      <td style={{ padding: '6px 10px', color: 'var(--t-text-2)', fontSize: 10, fontFamily: 'var(--t-font-mono)' }}>{m ? `${m.winRate.toFixed(0)}%` : '—'}</td>
      <td style={{ padding: '6px 10px', color: m ? (m.sharpe > 1 ? 'var(--t-green)' : 'var(--t-text-2)') : 'var(--t-text-3)', fontSize: 10, fontFamily: 'var(--t-font-mono)' }}>{m ? fmtF(m.sharpe) : '—'}</td>
      <td style={{ padding: '6px 10px', color: 'var(--t-text-3)', fontSize: 10, fontFamily: 'var(--t-font-mono)' }}>{m?.numTrades ?? r.num_trades ?? '—'}</td>
    </tr>
  )
}

function BacktestPortfolio({ reports, allFullReports, fullReport, candles, setSelectedIdx, setActiveTab }: {
  reports: ReportSummary[]
  allFullReports: Report[]
  fullReport: Report | undefined
  candles: import('../api/client').Candle[]
  setSelectedIdx: (i: number) => void
  setActiveTab: (t: any) => void
}) {
  // All metrics computed from Report only. No paper data touched.
  const allMetrics = useMemo(() =>
    allFullReports.map(r => { try { return metricsFromReport(r) } catch { return null } })
  , [allFullReports])

  const backtestEquity = useMemo(() => {
    if (!fullReport || !candles.length) return []
    try { return equityFromReport(fullReport, candles) } catch { return [] }
  }, [fullReport, candles])

  const validMetrics = allMetrics.filter(Boolean) as PortfolioMetrics[]
  const totalInitial = validMetrics.reduce((s, m) => s + m.initialCapital, 0)
  const totalFinal   = validMetrics.reduce((s, m) => s + m.currentCapital, 0)
  const avgReturn    = validMetrics.length ? validMetrics.reduce((s, m) => s + m.pnlPct, 0) / validMetrics.length : 0
  const bestReturn   = validMetrics.length ? Math.max(...validMetrics.map(m => m.pnlPct)) : 0
  const worstDD      = validMetrics.length ? Math.max(...validMetrics.map(m => m.maxDrawdown)) : 0
  const avgWR        = validMetrics.length ? validMetrics.reduce((s, m) => s + m.winRate, 0) / validMetrics.length : 0

  const currentMetrics = fullReport ? (() => { try { return metricsFromReport(fullReport) } catch { return null } })() : null

  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: '10px 14px' }}>

      {/* Portfolio summary — source: allFullReports only */}
      <SH label={`СВОДКА БЭКТЕСТОВ (${allFullReports.length} стратегий)`} />
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 6, marginBottom: 10 }}>
        <Card label="СУММАРНЫЙ КАПИТАЛ"  value={`${Math.round(totalFinal).toLocaleString('ru-RU')} ₽`} />
        <Card label="СУММАРНЫЙ PnL"      value={fmtRub(totalFinal - totalInitial)} color={pnlColor(totalFinal - totalInitial)} />
        <Card label="СРЕДНЯЯ ДОХОДНОСТЬ" value={fmtPct(avgReturn)}  color={pnlColor(avgReturn)} />
        <Card label="ЛУЧШИЙ РЕЗУЛЬТАТ"   value={fmtPct(bestReturn)} color={pnlColor(bestReturn)} />
        <Card label="MAX DRAWDOWN"        value={`${fmtF(worstDD)}%`} color="var(--t-red)" />
        <Card label="СРЕДНИЙ WIN RATE"   value={`${fmtF(avgWR, 1)}%`} />
      </div>

      {/* Current strategy equity — source: fullReport + candles only */}
      {currentMetrics && (
        <>
          <SH label={`ТЕКУЩАЯ СТРАТЕГИЯ — ${currentMetrics.strategyLabel} · ${currentMetrics.ticker}`} />
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 6, marginBottom: 10 }}>
            <Card label="ДОХОДНОСТЬ"    value={fmtPct(currentMetrics.pnlPct)}    color={pnlColor(currentMetrics.pnlPct)} />
            <Card label="PnL"           value={fmtRub(currentMetrics.pnl)}        color={pnlColor(currentMetrics.pnl)} />
            <Card label="MAX DRAWDOWN"  value={`${fmtF(currentMetrics.maxDrawdown)}%`} color="var(--t-red)" />
            <Card label="WIN RATE"      value={`${fmtF(currentMetrics.winRate, 1)}%`} />
            <Card label="SHARPE"        value={fmtF(currentMetrics.sharpe)}        color={currentMetrics.sharpe > 1 ? 'var(--t-green)' : undefined} />
          </div>
        </>
      )}

      {backtestEquity.length > 1 && (
        <EquitySection
          title={`EQUITY БЭКТЕСТ${fullReport ? ` — ${fullReport.ticker}` : ''}`}
          data={backtestEquity}
          label={fullReport?.ticker ?? ''}
        />
      )}

      {/* Warning — not paper trading */}
      <div style={{ marginBottom: 12, padding: '6px 10px', background: 'rgba(255,184,0,0.07)', borderRadius: 4, border: '1px solid rgba(255,184,0,0.2)', display: 'flex', gap: 8, alignItems: 'center' }}>
        <IconAlertTriangle size={11} color="var(--t-amber)" />
        <span style={{ fontSize: 9, color: 'var(--t-amber)', fontFamily: 'var(--t-font-mono)' }}>
          Paper Trading не запущен — все данные из бэктестов, не из реальных сделок
        </span>
      </div>

      {/* Strategy list — source: allFullReports + reports only */}
      <SH label={`БЭКТЕСТ-СТРАТЕГИИ (${reports.length})`} />
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              {['Стратегия', 'Инструмент', 'Доходность', 'Max DD', 'Win Rate', 'Sharpe', 'Сделок'].map(h => (
                <th key={h} style={TH_STYLE}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {reports.map((r, i) => (
              <BacktestStratRow
                key={r.report_id}
                r={r}
                m={allMetrics[i] ?? null}
                onClick={() => { setSelectedIdx(i); setActiveTab('terminal') }}
              />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── Main ─────────────────────────────────────────────────────────────────────

export default function PortfolioPage() {
  const { paper, allFullReports, reports, setSelectedIdx, setActiveTab, fullReport, candles } = useTerminal()

  const hasReports = allFullReports.length > 0
  const hasPaper   = !!paper

  // Mode selection — mutually exclusive
  const mode: 'paper' | 'backtest' | 'empty' =
    hasPaper ? 'paper' : hasReports ? 'backtest' : 'empty'

  // Paper metrics: computed ONLY when in paper mode
  const paperMetrics = useMemo(
    () => (mode === 'paper' && paper) ? metricsFromPaper(paper) : null,
    [mode, paper]
  )

  // ── Empty state ─────────────────────────────────────────────────────────────
  if (mode === 'empty') {
    return (
      <div style={{ height: '100%', display: 'flex', flexDirection: 'column', background: 'var(--t-bg)', overflow: 'hidden' }}>
        <PageHeader />
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 12, color: 'var(--t-text-3)' }}>
          <IconBriefcase size={40} style={{ opacity: 0.15 }} />
          <div style={{ fontSize: 12, fontFamily: 'var(--t-font-mono)' }}>Нет данных портфеля</div>
          <div style={{ fontSize: 10, color: 'var(--t-text-3)', textAlign: 'center', maxWidth: 340, lineHeight: 1.7 }}>
            Запустите бэктест или запустите Paper Trading для отображения портфеля
          </div>
        </div>
      </div>
    )
  }

  // ── Paper Trading mode ──────────────────────────────────────────────────────
  // ONLY paper data: PaperSummary + /paper/trades + /paper/positions
  // fullReport / allFullReports / candles are NOT used here
  if (mode === 'paper' && paper && paperMetrics) {
    return (
      <div style={{ height: '100%', display: 'flex', flexDirection: 'column', background: 'var(--t-bg)', overflow: 'hidden' }}>
        <PageHeader badge={<Badge text="PAPER TRADING" color="var(--t-green)" />} />
        {paper.note && (
          <div style={{ flexShrink: 0, padding: '4px 14px 0', fontSize: 9, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)', lineHeight: 1.6 }}>
            {paper.note}
          </div>
        )}
        <PaperPortfolio initialCapital={paper.initial_capital} metrics={paperMetrics} />
      </div>
    )
  }

  // ── Backtest mode ───────────────────────────────────────────────────────────
  // ONLY backtest data: fullReport + allFullReports + reports + candles
  // paper / PaperSummary are NOT used here
  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', background: 'var(--t-bg)', overflow: 'hidden' }}>
      <PageHeader badge={<Badge text="БЭКТЕСТ · НЕ PAPER TRADING" color="var(--t-amber)" />} />
      <BacktestPortfolio
        reports={reports}
        allFullReports={allFullReports}
        fullReport={fullReport}
        candles={candles}
        setSelectedIdx={setSelectedIdx}
        setActiveTab={setActiveTab}
      />
    </div>
  )
}
