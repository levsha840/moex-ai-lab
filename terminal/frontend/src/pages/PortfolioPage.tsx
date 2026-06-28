import { useMemo, useState } from 'react'
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

// ─── primitives ───────────────────────────────────────────────────────────────

function Card({ label, value, color }: { label: string; value: React.ReactNode; color?: string }) {
  return (
    <div style={{ padding: '8px 10px', background: 'var(--t-elevated)', borderRadius: 4, border: '1px solid var(--t-border)', display: 'flex', flexDirection: 'column', gap: 3 }}>
      <span style={{ fontSize: 8, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)', fontWeight: 700, letterSpacing: 0.5 }}>{label}</span>
      <span style={{ fontSize: 13, fontWeight: 700, fontFamily: 'var(--t-font-mono)', color: color ?? 'var(--t-text)' }}>{value}</span>
    </div>
  )
}

function SH({ label }: { label: string }) {
  return (
    <div style={{ fontSize: 9, letterSpacing: 0.8, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)', fontWeight: 700, padding: '10px 0 5px' }}>
      {label}
    </div>
  )
}

// ─── Debug banner ─────────────────────────────────────────────────────────────

function DebugBanner({ mode, source }: { mode: string; source: string }) {
  const color =
    mode === 'paper'    ? 'var(--t-green)' :
    mode === 'backtest' ? 'var(--t-amber)' : 'var(--t-text-3)'
  const bg =
    mode === 'paper'    ? 'rgba(0,200,83,0.07)' :
    mode === 'backtest' ? 'rgba(255,184,0,0.07)' : 'rgba(255,255,255,0.03)'
  return (
    <div style={{ flexShrink: 0, padding: '3px 14px', background: bg, borderBottom: '1px solid var(--t-border)', display: 'flex', gap: 20, alignItems: 'center' }}>
      <span style={{ fontSize: 9, fontFamily: 'var(--t-font-mono)', fontWeight: 700, color }}>
        DATA_MODE: {mode.toUpperCase()}
      </span>
      <span style={{ fontSize: 9, fontFamily: 'var(--t-font-mono)', color: 'var(--t-text-3)' }}>
        SOURCE: {source}
      </span>
    </div>
  )
}

// ─── Mode tab switcher ────────────────────────────────────────────────────────

function ModeTabs({
  mode, hasPaper, hasBacktest, onChange,
}: {
  mode: 'paper' | 'backtest'
  hasPaper: boolean
  hasBacktest: boolean
  onChange: (m: 'paper' | 'backtest') => void
}) {
  const tab = (m: 'paper' | 'backtest', label: string, available: boolean) => {
    const active = mode === m
    const activeColor = m === 'paper' ? 'var(--t-green)' : 'var(--t-amber)'
    const activeBg    = m === 'paper' ? 'rgba(0,200,83,0.15)' : 'rgba(255,184,0,0.15)'
    const activeBorder = m === 'paper' ? 'rgba(0,200,83,0.3)' : 'rgba(255,184,0,0.3)'
    return (
      <button
        key={m}
        disabled={!available}
        onClick={() => onChange(m)}
        style={{
          padding: '3px 12px', borderRadius: 3,
          cursor: available ? 'pointer' : 'not-allowed',
          fontSize: 9, fontFamily: 'var(--t-font-mono)', fontWeight: 700, letterSpacing: 0.5,
          background: active ? activeBg : 'var(--t-elevated)',
          color: active ? activeColor : available ? 'var(--t-text-2)' : 'var(--t-text-3)',
          border: active ? `1px solid ${activeBorder}` : '1px solid var(--t-border)',
          opacity: available ? 1 : 0.4,
        }}
      >
        {label}
      </button>
    )
  }
  return (
    <div style={{ flexShrink: 0, padding: '6px 14px', borderBottom: '1px solid var(--t-border)', display: 'flex', gap: 6, alignItems: 'center' }}>
      <span style={{ fontSize: 8, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)', marginRight: 4 }}>РЕЖИМ</span>
      {tab('paper',    'PAPER TRADING',      hasPaper)}
      {tab('backtest', 'BACKTEST PORTFOLIO', hasBacktest)}
    </div>
  )
}

// ─── Paper Trading panel ──────────────────────────────────────────────────────
// SOURCE: PaperSummary + /paper/trades + /paper/positions
// NEVER reads: fullReport, allFullReports, candles, reports

function PaperPositionsTable({ positions }: { positions: Position[] }) {
  if (!positions.length)
    return <div style={{ padding: '10px 0', fontSize: 10, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)' }}>Нет открытых позиций</div>
  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead><tr>{['Тикер','Вход ₽','Тек. ₽','PnL ₽'].map(h => <th key={h} style={TH}>{h}</th>)}</tr></thead>
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

function PaperTradesTable({ trades }: { trades: Trade[] }) {
  if (!trades.length)
    return <div style={{ padding: '10px 0', fontSize: 10, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)' }}>Нет Paper-сделок</div>
  const sorted = [...trades].sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())
  const fmt = (s: string) => {
    try {
      const d = new Date(s)
      return `${String(d.getDate()).padStart(2,'0')}.${String(d.getMonth()+1).padStart(2,'0')}.${String(d.getFullYear()).slice(2)}`
    } catch { return s.slice(0, 10) }
  }
  return (
    <div style={{ overflowX: 'auto' }}>
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
  // Fetches ONLY paper-specific endpoints. Zero backtest state used.
  const { data: paperTrades    = [] } = useQuery({ queryKey: ['paper-trades'],    queryFn: fetchPaperTrades })
  const { data: paperPositions = [] } = useQuery({ queryKey: ['paper-positions'], queryFn: fetchPaperPositions })

  const paperEquity = useMemo<EquityPoint[]>(
    () => equityFromPaperTrades(paperTrades, initialCapital),
    [paperTrades, initialCapital],
  )

  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: '10px 14px' }}>

      {paperTrades.length === 0 && (
        <div style={{ marginBottom: 10, padding: '6px 10px', background: 'rgba(0,200,83,0.07)', borderRadius: 4, border: '1px solid rgba(0,200,83,0.2)' }}>
          <span style={{ fontSize: 9, color: 'var(--t-green)', fontFamily: 'var(--t-font-mono)' }}>
            Нет Paper-сделок — Equity горизонталь на уровне начального капитала
          </span>
        </div>
      )}

      <SH label="КАПИТАЛ · SOURCE: PaperSummary" />
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 6, marginBottom: 10 }}>
        <Card label="НАЧАЛЬНЫЙ"    value={`${Math.round(initialCapital).toLocaleString('ru-RU')} ₽`} />
        <Card label="ТЕКУЩИЙ"      value={`${Math.round(metrics.currentCapital).toLocaleString('ru-RU')} ₽`} />
        <Card label="PnL"          value={fmtRub(metrics.pnl)}           color={pnlColor(metrics.pnl)} />
        <Card label="ДОХОДНОСТЬ"   value={fmtPct(metrics.pnlPct)}        color={pnlColor(metrics.pnlPct)} />
        <Card label="MAX DRAWDOWN" value={`${fmtF(metrics.maxDrawdown)}%`} color="var(--t-red)" />
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 6, marginBottom: 10 }}>
        <Card label="WIN RATE"   value={`${fmtF(metrics.winRate, 1)}%`} />
        <Card label="СДЕЛОК"     value={String(metrics.numTrades)} />
        <Card label="ПОЗИЦИИ"    value={String(paperPositions.length)} />
        <Card label="ЭКСПОЗИЦИЯ" value={`${fmtF(metrics.usedPct, 1)}%`} />
      </div>

      <SH label={`EQUITY PAPER · SOURCE: /paper/trades (${paperTrades.length} сделок)`} />
      <div style={{ marginBottom: 14, background: 'var(--t-elevated)', borderRadius: 4, border: '1px solid var(--t-border)', padding: 4 }}>
        <EquityChart primaryData={paperEquity} primaryLabel="Paper" height={200} compact />
      </div>

      <SH label={`ПОЗИЦИИ · SOURCE: /paper/positions (${paperPositions.length})`} />
      <PaperPositionsTable positions={paperPositions} />

      <SH label={`СДЕЛКИ · SOURCE: /paper/trades (${paperTrades.length})`} />
      <PaperTradesTable trades={paperTrades} />
    </div>
  )
}

// ─── Backtest panel ───────────────────────────────────────────────────────────
// SOURCE: fullReport + allFullReports + reports + candles
// NEVER reads: paper, PaperSummary, /paper/trades, /paper/positions

const TH2: React.CSSProperties = {
  padding: '5px 10px', color: 'var(--t-text-3)', fontWeight: 600, letterSpacing: 0.5,
  fontSize: 9, textAlign: 'left', background: 'var(--t-elevated)',
  borderBottom: '1px solid var(--t-border)', fontFamily: 'var(--t-font-mono)',
  position: 'sticky', top: 0, zIndex: 1,
}

function BacktestStratRow({ r, m, onClick }: { r: ReportSummary; m: PortfolioMetrics | null; onClick: () => void }) {
  return (
    <tr
      onClick={onClick}
      style={{ borderBottom: '1px solid rgba(255,255,255,0.04)', cursor: 'pointer' }}
      onMouseEnter={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.03)')}
      onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
    >
      <td style={{ padding: '6px 10px', color: 'var(--t-text)', fontSize: 10, fontFamily: 'var(--t-font-mono)' }}>
        {r.hypothesis_id.replace('tmpl_h_', '').replace(/_/g, ' ')}
      </td>
      <td style={{ padding: '6px 10px', color: 'var(--t-text-2)', fontSize: 10, fontFamily: 'var(--t-font-mono)' }}>{r.ticker}</td>
      <td style={{ padding: '6px 10px', fontSize: 10, fontFamily: 'var(--t-font-mono)', color: pnlColor(r.total_return_pct) }}>{fmtPct(r.total_return_pct)}</td>
      <td style={{ padding: '6px 10px', color: 'var(--t-red)', fontSize: 10, fontFamily: 'var(--t-font-mono)' }}>{m ? `${m.maxDrawdown.toFixed(1)}%` : '—'}</td>
      <td style={{ padding: '6px 10px', color: 'var(--t-text-2)', fontSize: 10, fontFamily: 'var(--t-font-mono)' }}>{m ? `${m.winRate.toFixed(0)}%` : '—'}</td>
      <td style={{ padding: '6px 10px', color: m ? (m.sharpe > 1 ? 'var(--t-green)' : 'var(--t-text-2)') : 'var(--t-text-3)', fontSize: 10, fontFamily: 'var(--t-font-mono)' }}>{m ? fmtF(m.sharpe) : '—'}</td>
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

  const backtestEquity = useMemo<EquityPoint[]>(() => {
    if (!fullReport || !candles.length) return []
    try { return equityFromReport(fullReport, candles) } catch { return [] }
  }, [fullReport, candles])

  const valid = allMetrics.filter(Boolean) as PortfolioMetrics[]
  const totalFinal = valid.reduce((s, m) => s + m.currentCapital, 0)
  const totalInit  = valid.reduce((s, m) => s + m.initialCapital, 0)
  const avgReturn  = valid.length ? valid.reduce((s, m) => s + m.pnlPct, 0) / valid.length : 0
  const bestReturn = valid.length ? Math.max(...valid.map(m => m.pnlPct)) : 0
  const worstDD    = valid.length ? Math.max(...valid.map(m => m.maxDrawdown)) : 0
  const avgWR      = valid.length ? valid.reduce((s, m) => s + m.winRate, 0) / valid.length : 0

  const curMetrics = fullReport
    ? (() => { try { return metricsFromReport(fullReport) } catch { return null } })()
    : null

  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: '10px 14px' }}>

      <div style={{ marginBottom: 10, padding: '5px 10px', background: 'rgba(255,184,0,0.07)', borderRadius: 4, border: '1px solid rgba(255,184,0,0.2)', display: 'flex', gap: 8, alignItems: 'center' }}>
        <IconAlertTriangle size={11} color="var(--t-amber)" />
        <span style={{ fontSize: 9, color: 'var(--t-amber)', fontFamily: 'var(--t-font-mono)' }}>
          Бэктест — не Paper Trading. Данные из исторических симуляций.
        </span>
      </div>

      <SH label={`СВОДКА · SOURCE: VisualBacktestReport × ${allFullReports.length}`} />
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 6, marginBottom: 10 }}>
        <Card label="СУММАРНЫЙ КАПИТАЛ"  value={`${Math.round(totalFinal).toLocaleString('ru-RU')} ₽`} />
        <Card label="СУММАРНЫЙ PnL"      value={fmtRub(totalFinal - totalInit)} color={pnlColor(totalFinal - totalInit)} />
        <Card label="СРЕДНЯЯ ДОХОДНОСТЬ" value={fmtPct(avgReturn)}  color={pnlColor(avgReturn)} />
        <Card label="ЛУЧШИЙ РЕЗУЛЬТАТ"   value={fmtPct(bestReturn)} color={pnlColor(bestReturn)} />
        <Card label="MAX DRAWDOWN"        value={`${fmtF(worstDD)}%`} color="var(--t-red)" />
        <Card label="СРЕДНИЙ WIN RATE"   value={`${fmtF(avgWR, 1)}%`} />
      </div>

      {curMetrics && (
        <>
          <SH label={`ТЕКУЩАЯ СТРАТЕГИЯ · SOURCE: fullReport (${curMetrics.ticker})`} />
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 6, marginBottom: 10 }}>
            <Card label="ДОХОДНОСТЬ"   value={fmtPct(curMetrics.pnlPct)}         color={pnlColor(curMetrics.pnlPct)} />
            <Card label="PnL"          value={fmtRub(curMetrics.pnl)}             color={pnlColor(curMetrics.pnl)} />
            <Card label="MAX DRAWDOWN" value={`${fmtF(curMetrics.maxDrawdown)}%`} color="var(--t-red)" />
            <Card label="WIN RATE"     value={`${fmtF(curMetrics.winRate, 1)}%`} />
            <Card label="SHARPE"       value={fmtF(curMetrics.sharpe)}            color={curMetrics.sharpe > 1 ? 'var(--t-green)' : undefined} />
          </div>
        </>
      )}

      {backtestEquity.length > 1 && (
        <>
          <SH label={`EQUITY БЭКТЕСТ · SOURCE: fullReport + candles${fullReport ? ` (${fullReport.ticker})` : ''}`} />
          <div style={{ marginBottom: 14, background: 'var(--t-elevated)', borderRadius: 4, border: '1px solid var(--t-border)', padding: 4 }}>
            <EquityChart primaryData={backtestEquity} primaryLabel={fullReport?.ticker ?? ''} height={200} compact />
          </div>
        </>
      )}

      <SH label={`СТРАТЕГИИ · SOURCE: reports (${reports.length})`} />
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>{['Стратегия','Инструмент','Доходность','Max DD','Win Rate','Sharpe','Сделок'].map(h => (
              <th key={h} style={TH2}>{h}</th>
            ))}</tr>
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

// ─── Main ─────────────────────────────────────────────────────────────────────

export default function PortfolioPage() {
  const { paper, allFullReports, reports, setSelectedIdx, setActiveTab, fullReport, candles } = useTerminal()

  // KEY FIX: hasPaper is true ONLY when paper trading is ENABLED in the backend.
  // paper.enabled === false means engine exists but inactive → treat as backtest mode.
  const hasPaper    = paper?.enabled === true
  const hasBacktest = allFullReports.length > 0

  const defaultMode: 'paper' | 'backtest' | 'empty' =
    hasPaper ? 'paper' : hasBacktest ? 'backtest' : 'empty'

  // User can switch modes explicitly via tab buttons
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

  const debugSource =
    mode === 'paper'    ? 'PaperSummary + /paper/trades + /paper/positions' :
    mode === 'backtest' ? 'VisualBacktestReport + candles'                  : 'none'

  // ── Empty ──────────────────────────────────────────────────────────────────
  if (mode === 'empty') {
    return (
      <div style={{ height: '100%', display: 'flex', flexDirection: 'column', background: 'var(--t-bg)', overflow: 'hidden' }}>
        <div style={{ height: 40, flexShrink: 0, display: 'flex', alignItems: 'center', padding: '0 12px', background: 'var(--t-panel)', borderBottom: '1px solid var(--t-border)', gap: 8 }}>
          <IconBriefcase size={12} color="var(--t-text-3)" />
          <span style={{ fontSize: 11, fontWeight: 700, fontFamily: 'var(--t-font-mono)', color: 'var(--t-text)', letterSpacing: 1 }}>ПОРТФЕЛЬ</span>
        </div>
        <DebugBanner mode="empty" source="none" />
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 12, color: 'var(--t-text-3)' }}>
          <IconBriefcase size={40} style={{ opacity: 0.15 }} />
          <div style={{ fontSize: 12, fontFamily: 'var(--t-font-mono)' }}>Нет данных портфеля</div>
          <div style={{ fontSize: 10, color: 'var(--t-text-3)', textAlign: 'center', maxWidth: 340, lineHeight: 1.7 }}>
            Запустите бэктест или включите Paper Trading в настройках бэкенда.
          </div>
          <div style={{ fontSize: 9, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)', marginTop: 8 }}>
            paper.enabled={String(paper?.enabled ?? 'undefined')} · backtest_count={allFullReports.length}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', background: 'var(--t-bg)', overflow: 'hidden' }}>

      {/* Header */}
      <div style={{ height: 40, flexShrink: 0, display: 'flex', alignItems: 'center', padding: '0 12px', background: 'var(--t-panel)', borderBottom: '1px solid var(--t-border)', gap: 8 }}>
        <IconBriefcase size={12} color="var(--t-text-3)" />
        <span style={{ fontSize: 11, fontWeight: 700, fontFamily: 'var(--t-font-mono)', color: 'var(--t-text)', letterSpacing: 1 }}>ПОРТФЕЛЬ</span>
        {mode === 'paper' && (
          <span style={{ fontSize: 9, padding: '1px 6px', borderRadius: 2, background: 'rgba(0,200,83,0.15)', color: 'var(--t-green)', fontFamily: 'var(--t-font-mono)', fontWeight: 700, border: '1px solid rgba(0,200,83,0.3)' }}>
            PAPER TRADING
          </span>
        )}
        {mode === 'backtest' && (
          <span style={{ fontSize: 9, padding: '1px 6px', borderRadius: 2, background: 'rgba(255,184,0,0.15)', color: 'var(--t-amber)', fontFamily: 'var(--t-font-mono)', fontWeight: 700, border: '1px solid rgba(255,184,0,0.3)' }}>
            БЭКТЕСТ
          </span>
        )}
      </div>

      {/* Debug banner — exact mode + data source */}
      <DebugBanner mode={mode} source={debugSource} />

      {/* Mode tabs — visible when both paper and backtest are available */}
      {hasPaper && hasBacktest && (
        <ModeTabs
          mode={mode as 'paper' | 'backtest'}
          hasPaper={hasPaper}
          hasBacktest={hasBacktest}
          onChange={setManualMode}
        />
      )}

      {/* Paper note */}
      {mode === 'paper' && paper?.note && (
        <div style={{ flexShrink: 0, padding: '3px 14px', fontSize: 9, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)', background: 'var(--t-panel)', borderBottom: '1px solid var(--t-border)' }}>
          {paper.note}
        </div>
      )}

      {/* Paper content — ZERO backtest data */}
      {mode === 'paper' && paper && paperMetrics && (
        <PaperPanel initialCapital={paper.initial_capital} metrics={paperMetrics} />
      )}

      {mode === 'paper' && paper && !paperMetrics && (
        <div style={{ flex: 1, padding: 20, fontSize: 10, color: 'var(--t-red)', fontFamily: 'var(--t-font-mono)' }}>
          Ошибка вычисления метрик. Проверьте /api/paper/summary.
        </div>
      )}

      {/* Backtest content — ZERO paper data */}
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
    </div>
  )
}
