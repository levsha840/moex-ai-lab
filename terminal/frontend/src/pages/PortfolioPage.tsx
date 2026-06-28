import { useMemo, useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { IconBriefcase, IconAlertTriangle } from '@tabler/icons-react'
import { useTerminal } from '../context/TerminalContext'
import {
  metricsFromReport, metricsFromPaper,
  equityFromReport, equityFromPaperTrades,
} from '../utils/portfolio'
import { fetchPaperTrades, fetchPaperPositions } from '../api/client'
import EquityChart from '../components/chart/EquityChart'
import type { ReportSummary, Report, Trade, Position } from '../api/client'
import type { PortfolioMetrics, EquityPoint } from '../utils/portfolio'
import { TH, TD, fmtRub, fmtPct, fmtF, pnlColor } from '../styles/tokens'

// ─── Card ─────────────────────────────────────────────────────────────────────

function Card({ label, value, color, wide }: {
  label: string
  value: React.ReactNode
  color?: string
  wide?: boolean
}) {
  return (
    <div style={{
      padding: '10px 12px',
      background: 'var(--t-elevated)',
      borderRadius: 4,
      border: '1px solid var(--t-border)',
      display: 'flex', flexDirection: 'column', gap: 4,
      gridColumn: wide ? 'span 2' : undefined,
    }}>
      <span style={{ fontSize: 8, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)', fontWeight: 700, letterSpacing: 0.6, textTransform: 'uppercase' }}>
        {label}
      </span>
      <span style={{ fontSize: 14, fontWeight: 700, fontFamily: 'var(--t-font-mono)', color: color ?? 'var(--t-text)' }}>
        {value}
      </span>
    </div>
  )
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ fontSize: 9, letterSpacing: 0.8, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)', fontWeight: 700, padding: '12px 0 6px', textTransform: 'uppercase' }}>
      {children}
    </div>
  )
}

// ─── Mode switcher (only shown when both modes are available) ─────────────────

function ModeTabs({ mode, hasPaper, hasBacktest, onChange }: {
  mode: 'paper' | 'backtest'
  hasPaper: boolean
  hasBacktest: boolean
  onChange: (m: 'paper' | 'backtest') => void
}) {
  const btn = (m: 'paper' | 'backtest', label: string, available: boolean) => {
    const active = mode === m
    const col  = m === 'paper' ? 'var(--t-green)' : 'var(--t-amber)'
    const bg   = m === 'paper' ? 'rgba(0,200,83,0.12)' : 'rgba(255,184,0,0.12)'
    const bdr  = m === 'paper' ? 'rgba(0,200,83,0.3)'  : 'rgba(255,184,0,0.3)'
    return (
      <button
        key={m} disabled={!available} onClick={() => onChange(m)}
        style={{
          padding: '3px 14px', borderRadius: 3,
          cursor: available ? 'pointer' : 'not-allowed',
          fontSize: 9, fontFamily: 'var(--t-font-mono)', fontWeight: 700,
          background: active ? bg : 'var(--t-elevated)',
          color: active ? col : available ? 'var(--t-text-2)' : 'var(--t-text-3)',
          border: active ? `1px solid ${bdr}` : '1px solid var(--t-border)',
          opacity: available ? 1 : 0.4,
        }}
      >
        {label}
      </button>
    )
  }
  return (
    <div style={{ flexShrink: 0, padding: '5px 14px', borderBottom: '1px solid var(--t-border)', display: 'flex', gap: 6, alignItems: 'center' }}>
      {btn('paper',    'Paper Trading',      hasPaper)}
      {btn('backtest', 'Backtest Portfolio', hasBacktest)}
    </div>
  )
}

// ─── BACKTEST panel ───────────────────────────────────────────────────────────

const STRAT_TH: React.CSSProperties = {
  padding: '5px 10px', color: 'var(--t-text-3)', fontWeight: 600,
  fontSize: 9, textAlign: 'left', background: 'var(--t-elevated)',
  borderBottom: '1px solid var(--t-border)', fontFamily: 'var(--t-font-mono)',
  position: 'sticky', top: 0, zIndex: 1,
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
      <td style={{ padding: '6px 10px', color: 'var(--t-text)', fontSize: 10, fontFamily: 'var(--t-font-mono)', maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{name}</td>
      <td style={{ padding: '6px 10px', color: 'var(--t-text-2)', fontSize: 10, fontFamily: 'var(--t-font-mono)' }}>{r.ticker}</td>
      <td style={{ padding: '6px 10px', fontSize: 10, fontFamily: 'var(--t-font-mono)', color: pnlColor(r.total_return_pct), fontWeight: 600 }}>{fmtPct(r.total_return_pct)}</td>
      <td style={{ padding: '6px 10px', color: 'var(--t-red)', fontSize: 10, fontFamily: 'var(--t-font-mono)' }}>{m ? `${m.maxDrawdown.toFixed(1)}%` : '—'}</td>
      <td style={{ padding: '6px 10px', color: 'var(--t-text-2)', fontSize: 10, fontFamily: 'var(--t-font-mono)' }}>{m ? `${m.winRate.toFixed(0)}%` : '—'}</td>
      <td style={{ padding: '6px 10px', color: m ? (m.profitFactor >= 1.5 ? 'var(--t-green)' : m.profitFactor < 1 ? 'var(--t-red)' : 'var(--t-text-2)') : 'var(--t-text-3)', fontSize: 10, fontFamily: 'var(--t-font-mono)' }}>{m ? m.profitFactor.toFixed(2) : '—'}</td>
      <td style={{ padding: '6px 10px', color: 'var(--t-text-3)', fontSize: 10, fontFamily: 'var(--t-font-mono)' }}>{m?.numTrades ?? r.num_trades ?? '—'}</td>
    </tr>
  )
}

function BacktestPanel({ reports, allFullReports, fullReport, candles, setSelectedIdx, setActiveTab }: {
  reports: ReportSummary[]
  allFullReports: Report[]
  fullReport: Report | undefined
  candles: import('../api/client').Candle[]
  setSelectedIdx: (i: number) => void
  setActiveTab: (t: string) => void
}) {
  const allMetrics = useMemo(() =>
    allFullReports.map(r => { try { return metricsFromReport(r) } catch { return null } }),
    [allFullReports],
  )

  const equity = useMemo<EquityPoint[]>(() => {
    if (!fullReport || !candles.length) return []
    try { return equityFromReport(fullReport, candles) } catch { return [] }
  }, [fullReport, candles])

  // Metrics for currently selected strategy
  const cur = fullReport
    ? (() => { try { return metricsFromReport(fullReport) } catch { return null } })()
    : null

  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: '12px 16px' }}>

      {/* Subtitle */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 14, padding: '6px 10px', background: 'rgba(255,184,0,0.06)', borderRadius: 4, border: '1px solid rgba(255,184,0,0.18)' }}>
        <IconAlertTriangle size={11} color="var(--t-amber)" />
        <span style={{ fontSize: 9, color: 'var(--t-amber)', fontFamily: 'var(--t-font-mono)' }}>
          Историческая симуляция, не Paper Trading
        </span>
      </div>

      {/* Current strategy metrics */}
      {cur ? (
        <>
          <SectionTitle>{cur.ticker} · {cur.strategyLabel}</SectionTitle>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 6, marginBottom: 10 }}>
            <Card label="Начальный капитал" value={`${Math.round(cur.initialCapital).toLocaleString('ru-RU')} ₽`} />
            <Card label="Итоговый капитал"  value={`${Math.round(cur.currentCapital).toLocaleString('ru-RU')} ₽`} />
            <Card label="PnL"               value={fmtRub(cur.pnl)}          color={pnlColor(cur.pnl)} />
            <Card label="Доходность"         value={fmtPct(cur.pnlPct)}       color={pnlColor(cur.pnlPct)} />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 6, marginBottom: 14 }}>
            <Card label="Max Drawdown"   value={`${fmtF(cur.maxDrawdown)}%`}  color="var(--t-red)" />
            <Card label="Win Rate"       value={`${fmtF(cur.winRate, 1)}%`} />
            <Card label="Profit Factor"  value={fmtF(cur.profitFactor)}        color={cur.profitFactor >= 1.5 ? 'var(--t-green)' : cur.profitFactor < 1 ? 'var(--t-red)' : undefined} />
            <Card label="Сделок"         value={String(cur.numTrades)} />
          </div>
        </>
      ) : (
        allFullReports.length > 0 && (() => {
          const valid = allMetrics.filter(Boolean) as PortfolioMetrics[]
          const totalFinal = valid.reduce((s, m) => s + m.currentCapital, 0)
          const totalInit  = valid.reduce((s, m) => s + m.initialCapital, 0)
          const avgReturn  = valid.length ? valid.reduce((s, m) => s + m.pnlPct, 0) / valid.length : 0
          const bestReturn = valid.length ? Math.max(...valid.map(m => m.pnlPct)) : 0
          const worstDD    = valid.length ? Math.max(...valid.map(m => m.maxDrawdown)) : 0
          const avgWR      = valid.length ? valid.reduce((s, m) => s + m.winRate, 0) / valid.length : 0
          return (
            <>
              <SectionTitle>Сводка по всем стратегиям</SectionTitle>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 6, marginBottom: 14 }}>
                <Card label="Суммарный капитал"  value={`${Math.round(totalFinal).toLocaleString('ru-RU')} ₽`} />
                <Card label="Суммарный PnL"       value={fmtRub(totalFinal - totalInit)} color={pnlColor(totalFinal - totalInit)} />
                <Card label="Средняя доходность"  value={fmtPct(avgReturn)}  color={pnlColor(avgReturn)} />
                <Card label="Лучший результат"    value={fmtPct(bestReturn)} color={pnlColor(bestReturn)} />
                <Card label="Max Drawdown (макс.)" value={`${fmtF(worstDD)}%`} color="var(--t-red)" />
                <Card label="Win Rate (средний)"  value={`${fmtF(avgWR, 1)}%`} />
              </div>
            </>
          )
        })()
      )}

      {/* Equity curve */}
      {equity.length > 1 && (
        <>
          <SectionTitle>Кривая капитала{fullReport ? ` — ${fullReport.ticker}` : ''}</SectionTitle>
          <div style={{ marginBottom: 16, background: 'var(--t-elevated)', borderRadius: 4, border: '1px solid var(--t-border)', padding: 4 }}>
            <EquityChart primaryData={equity} primaryLabel={fullReport?.ticker ?? ''} height={200} compact />
          </div>
        </>
      )}

      {/* Strategy list */}
      {reports.length > 0 && (
        <>
          <SectionTitle>Стратегии ({reports.length})</SectionTitle>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  {['Стратегия','Инструмент','Доходность','Max DD','Win Rate','Profit Factor','Сделок'].map(h => (
                    <th key={h} style={STRAT_TH}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {reports.map((r, i) => (
                  <StrategyRow
                    key={r.report_id}
                    r={r}
                    m={allMetrics[i] ?? null}
                    onClick={() => { setSelectedIdx(i); setActiveTab('terminal') }}
                  />
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}

// ─── PAPER panel ──────────────────────────────────────────────────────────────

function PositionsTable({ positions }: { positions: Position[] }) {
  if (!positions.length)
    return <div style={{ padding: '8px 0', fontSize: 10, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)' }}>Нет открытых позиций</div>
  return (
    <div style={{ overflowX: 'auto', marginBottom: 4 }}>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead><tr>{['Тикер','Вход ₽','Текущая ₽','PnL ₽'].map(h => <th key={h} style={TH}>{h}</th>)}</tr></thead>
        <tbody>
          {positions.map(p => (
            <tr key={p.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
              <td style={{ ...TD }}>{p.ticker}</td>
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

function TradesTable({ trades }: { trades: Trade[] }) {
  if (!trades.length)
    return <div style={{ padding: '8px 0', fontSize: 10, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)' }}>Нет Paper-сделок</div>
  const sorted = [...trades].sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())
  const fmt = (s: string) => {
    try {
      const d = new Date(s)
      return `${String(d.getDate()).padStart(2,'0')}.${String(d.getMonth()+1).padStart(2,'0')}.${String(d.getFullYear()).slice(2)}`
    } catch { return s.slice(0, 10) }
  }
  return (
    <div style={{ overflowX: 'auto', marginBottom: 4 }}>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead><tr>{['Дата','Тикер','Вход ₽','Выход ₽','PnL ₽'].map(h => <th key={h} style={TH}>{h}</th>)}</tr></thead>
        <tbody>
          {sorted.map(t => (
            <tr key={t.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
              <td style={{ ...TD, color: 'var(--t-text-3)' }}>{fmt(t.date)}</td>
              <td style={{ ...TD }}>{t.ticker}</td>
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

function PaperPanel({ initialCapital, metrics }: { initialCapital: number; metrics: PortfolioMetrics }) {
  const { data: paperTrades    = [] } = useQuery({ queryKey: ['paper-trades'],    queryFn: fetchPaperTrades })
  const { data: paperPositions = [] } = useQuery({ queryKey: ['paper-positions'], queryFn: fetchPaperPositions })

  const equity = useMemo<EquityPoint[]>(
    () => equityFromPaperTrades(paperTrades, initialCapital),
    [paperTrades, initialCapital],
  )

  const noTrades = paperTrades.length === 0

  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: '12px 16px' }}>

      {/* Capital metrics */}
      <SectionTitle>Капитал</SectionTitle>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 6, marginBottom: 10 }}>
        <Card label="Начальный капитал" value={`${Math.round(initialCapital).toLocaleString('ru-RU')} ₽`} />
        <Card label="Текущий капитал"   value={`${Math.round(metrics.currentCapital).toLocaleString('ru-RU')} ₽`} />
        <Card label="PnL"               value={fmtRub(metrics.pnl)}     color={pnlColor(metrics.pnl)} />
        <Card label="Доходность"         value={fmtPct(metrics.pnlPct)}  color={pnlColor(metrics.pnlPct)} />
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 6, marginBottom: 14 }}>
        <Card label="Win Rate"   value={`${fmtF(metrics.winRate, 1)}%`} />
        <Card label="Сделок"     value={String(metrics.numTrades)} />
        <Card label="Позиции"    value={String(paperPositions.length)} />
        <Card label="Экспозиция" value={`${fmtF(metrics.usedPct, 1)}%`} />
      </div>

      {/* Equity */}
      <SectionTitle>Кривая капитала</SectionTitle>
      {noTrades && (
        <div style={{ marginBottom: 6, padding: '5px 10px', background: 'rgba(255,255,255,0.04)', borderRadius: 3, fontSize: 9, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)' }}>
          Нет Paper-сделок — кривая горизонтальна на уровне начального капитала
        </div>
      )}
      <div style={{ marginBottom: 16, background: 'var(--t-elevated)', borderRadius: 4, border: '1px solid var(--t-border)', padding: 4 }}>
        <EquityChart primaryData={equity} primaryLabel="Paper" height={200} compact />
      </div>

      {/* Open positions */}
      <SectionTitle>Открытые позиции ({paperPositions.length})</SectionTitle>
      <PositionsTable positions={paperPositions} />

      {/* Closed trades */}
      <SectionTitle>Сделки ({paperTrades.length})</SectionTitle>
      <TradesTable trades={paperTrades} />
    </div>
  )
}

// ─── Main ─────────────────────────────────────────────────────────────────────

export default function PortfolioPage() {
  const { paper, allFullReports, reports, setSelectedIdx, setActiveTab, fullReport, candles } = useTerminal()

  const hasPaper    = paper?.enabled === true
  const hasBacktest = allFullReports.length > 0

  const defaultMode: 'paper' | 'backtest' | 'empty' =
    hasPaper ? 'paper' : hasBacktest ? 'backtest' : 'empty'

  const [manualMode, setManualMode] = useState<'paper' | 'backtest' | null>(null)

  const mode: 'paper' | 'backtest' | 'empty' =
    manualMode !== null && (manualMode === 'paper' ? hasPaper : hasBacktest)
      ? manualMode
      : defaultMode

  const paperMetrics = useMemo(
    () => (mode === 'paper' && paper)
      ? (() => { try { return metricsFromPaper(paper) } catch { return null } })()
      : null,
    [mode, paper],
  )

  // Dev-only console diagnostics (never shown in UI)
  useEffect(() => {
    console.debug('[Portfolio] mode=%s hasPaper=%s hasBacktest=%s paper.enabled=%s reports=%d',
      mode, hasPaper, hasBacktest, paper?.enabled, allFullReports.length)
  }, [mode, hasPaper, hasBacktest, paper, allFullReports.length])

  const pageTitle =
    mode === 'paper'    ? 'Портфель — Paper Trading' :
    mode === 'backtest' ? 'Портфель — бэктест'       : 'Портфель'

  // ── Header shared across all modes ─────────────────────────────────────────
  const header = (
    <div style={{ height: 42, flexShrink: 0, display: 'flex', alignItems: 'center', padding: '0 16px', background: 'var(--t-panel)', borderBottom: '1px solid var(--t-border)', gap: 8 }}>
      <IconBriefcase size={13} color="var(--t-text-3)" />
      <span style={{ fontSize: 12, fontWeight: 700, fontFamily: 'var(--t-font-mono)', color: 'var(--t-text)', letterSpacing: 0.5 }}>
        {pageTitle}
      </span>
    </div>
  )

  // ── Empty ──────────────────────────────────────────────────────────────────
  if (mode === 'empty') {
    return (
      <div style={{ height: '100%', display: 'flex', flexDirection: 'column', background: 'var(--t-bg)', overflow: 'hidden' }}>
        {header}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 12 }}>
          <IconBriefcase size={40} style={{ opacity: 0.12 }} color="var(--t-text-3)" />
          <div style={{ fontSize: 13, fontFamily: 'var(--t-font-mono)', color: 'var(--t-text-2)' }}>Нет данных портфеля</div>
          <div style={{ fontSize: 10, color: 'var(--t-text-3)', textAlign: 'center', maxWidth: 340, lineHeight: 1.8 }}>
            Запустите бэктест чтобы увидеть результаты стратегий,<br />
            или включите Paper Trading для реального мониторинга.
          </div>
        </div>
      </div>
    )
  }

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', background: 'var(--t-bg)', overflow: 'hidden' }}>
      {header}

      {/* Mode tabs — shown only when BOTH modes have data */}
      {hasPaper && hasBacktest && (
        <ModeTabs
          mode={mode as 'paper' | 'backtest'}
          hasPaper={hasPaper}
          hasBacktest={hasBacktest}
          onChange={setManualMode}
        />
      )}

      {/* Paper note from backend */}
      {mode === 'paper' && paper?.note && (
        <div style={{ flexShrink: 0, padding: '4px 16px', fontSize: 9, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)', background: 'var(--t-panel)', borderBottom: '1px solid var(--t-border)' }}>
          {paper.note}
        </div>
      )}

      {/* ── Backtest content ─────────────────────────────────────────────── */}
      {mode === 'backtest' && (
        <BacktestPanel
          reports={reports}
          allFullReports={allFullReports}
          fullReport={fullReport}
          candles={candles}
          setSelectedIdx={setSelectedIdx}
          setActiveTab={setActiveTab as (t: string) => void}
        />
      )}

      {/* ── Paper content ────────────────────────────────────────────────── */}
      {mode === 'paper' && paper && paperMetrics && (
        <PaperPanel initialCapital={paper.initial_capital} metrics={paperMetrics} />
      )}

      {mode === 'paper' && (!paper || !paperMetrics) && (
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <span style={{ fontSize: 10, color: 'var(--t-red)', fontFamily: 'var(--t-font-mono)' }}>
            Ошибка загрузки данных Paper Trading
          </span>
        </div>
      )}
    </div>
  )
}
