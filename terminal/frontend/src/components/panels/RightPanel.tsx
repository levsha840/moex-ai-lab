import { useMemo } from 'react'
import { ScrollArea } from '@mantine/core'
import ReactECharts from 'echarts-for-react'
import { useTerminal } from '../../context/TerminalContext'
import { metricsFromReport, metricsFromPaper, equityFromReport, COMPARE_COLORS } from '../../utils/portfolio'
import EquityChart from '../chart/EquityChart'
import type { Strategy, Decision } from '../../api/client'
import { IconAlertTriangle } from '@tabler/icons-react'

// ── Форматирование ────────────────────────────────────────────────────────────

function fmtM(n: number): string {
  if (Math.abs(n) >= 1_000_000) return `${(n / 1_000_000).toFixed(3)} М₽`
  if (Math.abs(n) >= 1_000) return `${(n / 1_000).toFixed(1)} к₽`
  return `${n.toFixed(0)} ₽`
}
function fmtPct(n: number, showSign = false): string {
  const s = showSign && n > 0 ? '+' : ''
  return `${s}${n.toFixed(2)}%`
}
function pnlColor(v: number) { return v >= 0 ? 'var(--t-green)' : 'var(--t-red)' }

// ── Section header ────────────────────────────────────────────────────────────

function SH({ label, accent }: { label: string; accent?: string }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 7,
      padding: '7px 10px 5px',
      borderBottom: '1px solid var(--t-border)',
      background: 'var(--t-panel)',
    }}>
      <div style={{ width: 2, height: 10, background: accent ?? 'var(--t-accent)', borderRadius: 1, flexShrink: 0 }} />
      <span style={{ fontSize: 9, letterSpacing: 0.8, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)', fontWeight: 700 }}>
        {label}
      </span>
    </div>
  )
}

// ── KPI row ───────────────────────────────────────────────────────────────────

function KRow({ label, value, color, small }: { label: string; value: string; color?: string; small?: boolean }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 4 }}>
      <span style={{ fontSize: small ? 9 : 10, color: 'var(--t-text-3)' }}>{label}</span>
      <span style={{ fontSize: small ? 10 : 11, fontFamily: 'var(--t-font-mono)', color: color ?? 'var(--t-text)', fontWeight: color ? 600 : 400 }}>
        {value}
      </span>
    </div>
  )
}

function Div() {
  return <div style={{ height: 1, background: 'var(--t-border)', margin: '5px 0' }} />
}

// ── Инспектор сделки ──────────────────────────────────────────────────────────

function TradeInspector() {
  const { selectedTradeId, setSelectedTradeId, trades, currentSummary, candles } = useTerminal()
  if (!selectedTradeId) return null

  const trade = trades.find(t => t.trade_id === selectedTradeId)
  if (!trade) return null

  const entryC = candles[trade.entry_bar]
  const exitC  = trade.exit_bar != null ? candles[trade.exit_bar] : null

  const holdLabel = (): string => {
    if (exitC && entryC) {
      const h = (exitC.time - entryC.time) / 3600
      return h < 48 ? `${Math.round(h)}ч` : `${(h / 24).toFixed(1)}д`
    }
    if (trade.exit_bar != null) {
      return `${trade.exit_bar - trade.entry_bar} баров`
    }
    return '—'
  }

  const fmtDate = (ts: number) =>
    new Date(ts * 1000).toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: '2-digit' })

  const entryDate = entryC ? fmtDate(entryC.time) : '—'
  const exitDate  = exitC  ? fmtDate(exitC.time)  : '—'
  const pnl  = trade.pnl ?? 0
  const pnlP = trade.pnl_pct ?? 0
  const capChange = (trade.capital_after ?? 0) - (trade.capital_before ?? 0)
  const dir = (trade as any).direction ?? 'LONG'

  return (
    <div style={{ borderBottom: '2px solid var(--t-border)' }}>
      {/* Заголовок */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '6px 10px 4px', background: 'var(--t-panel)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <div style={{ width: 3, height: 14, background: trade.is_winner ? 'var(--t-green)' : 'var(--t-red)', borderRadius: 2 }} />
          <span style={{ fontSize: 9, fontWeight: 700, color: 'var(--t-text)', fontFamily: 'var(--t-font-mono)', letterSpacing: 0.5 }}>
            ИНСПЕКТОР СДЕЛКИ
          </span>
          <span style={{
            fontSize: 8, padding: '1px 5px', borderRadius: 2, fontFamily: 'var(--t-font-mono)',
            background: trade.is_winner ? 'rgba(8,153,129,0.15)' : 'rgba(242,54,69,0.15)',
            color: trade.is_winner ? 'var(--t-green)' : 'var(--t-red)',
          }}>
            {trade.is_winner ? 'WIN' : 'LOSS'}
          </span>
        </div>
        <button
          onClick={() => setSelectedTradeId(null)}
          style={{ padding: '2px 7px', border: '1px solid var(--t-border)', background: 'var(--t-elevated)', color: 'var(--t-text-3)', borderRadius: 3, cursor: 'pointer', fontSize: 11, lineHeight: 1 }}
        >
          ×
        </button>
      </div>

      {/* Тело */}
      <div style={{ padding: '6px 10px 10px' }}>
        <KRow label="Инструмент" value={currentSummary?.ticker ?? '—'} />
        <KRow label="Стратегия"  value={currentSummary ? currentSummary.hypothesis_id.replace('tmpl_h_', '').replace(/_/g, ' ').slice(0, 16) : '—'} />
        <KRow
          label="Направление"
          value={dir}
          color={dir === 'SHORT' ? 'var(--t-red)' : 'var(--t-cyan)'}
        />
        <Div />
        <KRow label="Вход"       value={`${trade.entry_price.toFixed(2)} ₽ · ${entryDate}`} small />
        <KRow label="Выход"      value={trade.exit_price != null ? `${trade.exit_price.toFixed(2)} ₽ · ${exitDate}` : '—'} small />
        <KRow label="Удержание"  value={holdLabel()} small />
        <Div />
        <KRow label="Прибыль ₽"  value={`${pnl >= 0 ? '+' : ''}${pnl.toFixed(0)} ₽`}        color={pnlColor(pnl)} />
        <KRow label="Прибыль %"  value={`${pnlP >= 0 ? '+' : ''}${pnlP.toFixed(2)}%`}        color={pnlColor(pnlP)} />
        <KRow label="Изм. капит." value={`${capChange >= 0 ? '+' : ''}${fmtM(capChange)}`}  color={pnlColor(capChange)} />
        {trade.exit_reason && (
          <>
            <Div />
            <div style={{ fontSize: 9, color: 'var(--t-text-3)', marginBottom: 3 }}>Причина выхода</div>
            <div style={{ fontSize: 9, color: 'var(--t-text-2)', lineHeight: 1.5, background: 'var(--t-elevated)', borderRadius: 3, padding: '4px 7px', borderLeft: `2px solid ${trade.is_winner ? 'var(--t-green)' : 'var(--t-red)'}` }}>
              {trade.exit_reason}
            </div>
          </>
        )}
      </div>
    </div>
  )
}

// ── Портфель (единый источник) ────────────────────────────────────────────────

function PortfolioSection() {
  const { fullReport, paper, currentSummary, isLoadingReport } = useTerminal()

  if (isLoadingReport) {
    return <div style={{ padding: '10px', fontSize: 10, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)' }}>Загрузка…</div>
  }
  if (!currentSummary) {
    return <div style={{ padding: '10px', fontSize: 10, color: 'var(--t-text-3)' }}>Выберите стратегию</div>
  }

  if (fullReport) {
    const m = metricsFromReport(fullReport)
    return (
      <div style={{ padding: '6px 10px 10px' }}>
        <div style={{ fontSize: 8, color: 'var(--t-cyan)', fontFamily: 'var(--t-font-mono)', marginBottom: 5, letterSpacing: 0.5 }}>
          БЭКТЕСТ · {m.ticker}
        </div>
        <KRow label="Нач. капитал"   value={fmtM(m.initialCapital)} />
        <KRow label="Итог. капитал"  value={fmtM(m.currentCapital)} />
        <KRow label="PnL"            value={`${m.pnl >= 0 ? '+' : ''}${fmtM(m.pnl)}`}         color={pnlColor(m.pnl)} />
        <KRow label="Доходность"     value={fmtPct(m.pnlPct, true)}                            color={pnlColor(m.pnlPct)} />
        <Div />
        <KRow label="Итог. кэш"      value={fmtM(m.freeCash)} />
        <KRow label="Время в позиции" value={fmtPct(m.usedPct)}                               color="var(--t-cyan)" />
        <KRow label="Сделок"         value={String(m.numTrades)} />
        <KRow label="Win Rate"       value={fmtPct(m.winRate)}                                 color={m.winRate >= 50 ? 'var(--t-green)' : 'var(--t-red)'} />
        <KRow label="Проф. фактор"   value={isFinite(m.profitFactor) ? m.profitFactor.toFixed(2) : '∞'} />
      </div>
    )
  }

  if (paper) {
    const m = metricsFromPaper(paper)
    return (
      <div style={{ padding: '6px 10px 10px' }}>
        <div style={{ fontSize: 8, color: 'var(--t-amber)', fontFamily: 'var(--t-font-mono)', marginBottom: 5, letterSpacing: 0.5 }}>
          БУМАЖНЫЙ ПОРТФЕЛЬ
        </div>
        <KRow label="Нач. капитал"  value={fmtM(m.initialCapital)} />
        <KRow label="Тек. капитал"  value={fmtM(m.currentCapital)} />
        <KRow label="PnL"           value={`${m.pnl >= 0 ? '+' : ''}${fmtM(m.pnl)}`}  color={pnlColor(m.pnl)} />
        <KRow label="Доходность"    value={fmtPct(m.pnlPct, true)}                     color={pnlColor(m.pnlPct)} />
        <Div />
        <KRow label="Свободные"     value={fmtM(m.freeCash)} />
        <KRow label="Использовано"  value={fmtPct(m.usedPct)}                           color="var(--t-amber)" />
        <KRow label="Позиций"       value={String(paper.open_positions)} />
        <KRow label="Win Rate"      value={fmtPct(m.winRate)}                            color={m.winRate >= 50 ? 'var(--t-green)' : 'var(--t-red)'} />
        {paper.note && (
          <div style={{ marginTop: 5, padding: '4px 6px', background: 'rgba(255,184,0,0.08)', borderRadius: 3, fontSize: 9, color: 'var(--t-amber)', lineHeight: 1.4, borderLeft: '2px solid var(--t-amber)' }}>
            {paper.note}
          </div>
        )}
      </div>
    )
  }

  return <div style={{ padding: '10px', fontSize: 10, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)' }}>Ожидание данных…</div>
}

// ── Риск-метрики ──────────────────────────────────────────────────────────────

function RiskSection() {
  const { fullReport, paper, currentSummary, isLoadingReport } = useTerminal()
  if (isLoadingReport || !currentSummary) return null

  if (fullReport) {
    const m = metricsFromReport(fullReport)
    return (
      <div style={{ padding: '6px 10px 10px' }}>
        <KRow label="Макс. просадка" value={`-${m.maxDrawdown.toFixed(2)}%`}     color="var(--t-red)" />
        <KRow label="Тек. просадка"  value={`-${m.currentDrawdown.toFixed(2)}%`} color={m.currentDrawdown > 5 ? 'var(--t-amber)' : 'var(--t-text)'} />
        <Div />
        <KRow label="Sharpe"  value={m.sharpe.toFixed(2)}   color={m.sharpe >= 1 ? 'var(--t-green)' : m.sharpe >= 0 ? 'var(--t-text)' : 'var(--t-red)'} />
        <KRow label="Sortino" value={m.sortino.toFixed(2)}  color={m.sortino >= 1 ? 'var(--t-green)' : 'var(--t-text)'} />
        <KRow label="Calmar"  value={m.calmar.toFixed(2)}   color={m.calmar >= 0.5 ? 'var(--t-green)' : 'var(--t-text)'} />
        <KRow label="VaR 95%" value={`-${m.var95.toFixed(2)}%`} color="var(--t-red)" />
      </div>
    )
  }
  if (paper) {
    const m = metricsFromPaper(paper)
    return (
      <div style={{ padding: '6px 10px 10px' }}>
        <KRow label="Макс. просадка" value={`-${m.maxDrawdown.toFixed(2)}%`} color="var(--t-red)" />
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 5, marginTop: 5, padding: '4px 6px', background: 'var(--t-elevated)', borderRadius: 3 }}>
          <IconAlertTriangle size={10} color="var(--t-amber)" style={{ marginTop: 1, flexShrink: 0 }} />
          <span style={{ fontSize: 9, color: 'var(--t-text-3)', lineHeight: 1.4 }}>
            Sharpe/Sortino/Calmar/VaR — требуется история торговли
          </span>
        </div>
      </div>
    )
  }
  return null
}

// ── Кривая капитала ───────────────────────────────────────────────────────────

function EquitySection() {
  const { fullReport, candles, allFullReports, selectedIdx, reports, setEquityExpanded, isLoadingReport } = useTerminal()

  const primaryData = useMemo(() => {
    if (!fullReport || !candles.length) return []
    return equityFromReport(fullReport, candles)
  }, [fullReport, candles])

  const compareData = useMemo(() => {
    return allFullReports
      .filter((r, i) => i !== selectedIdx && r != null && candles.length > 0)
      .map((r, i) => ({
        label: r.hypothesis_id.replace('tmpl_h_', '').replace(/_/g, ' '),
        ticker: r.ticker,
        color: COMPARE_COLORS[(i + 1) % COMPARE_COLORS.length],
        data: equityFromReport(r, candles),
      }))
      .filter(cd => cd.data.length > 0)
  }, [allFullReports, candles, selectedIdx])

  const primaryLabel = reports[selectedIdx]?.ticker ?? 'Стратегия'

  if (isLoadingReport) return <div style={{ padding: '6px 10px', fontSize: 10, color: 'var(--t-text-3)' }}>Загрузка…</div>

  if (!primaryData.length) {
    return (
      <div style={{ padding: '6px 10px 10px', fontSize: 10, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)' }}>
        {fullReport ? 'Нет данных сделок' : 'Нет данных бэктеста'}
      </div>
    )
  }

  return (
    <div style={{ padding: '0 0 4px' }}>
      <EquityChart
        primaryData={primaryData}
        primaryLabel={primaryLabel}
        compareData={compareData}
        height={150}
        compact
        onOpenFull={() => setEquityExpanded(true)}
      />
    </div>
  )
}

// ── Распределение капитала ────────────────────────────────────────────────────

function AllocationSection() {
  const { allFullReports, selectedIdx } = useTerminal()
  if (!allFullReports.length) return <div style={{ padding: '8px 10px', fontSize: 10, color: 'var(--t-text-3)' }}>Нет стратегий</div>

  const data = allFullReports.map((r, i) => ({
    name: r?.ticker ?? '?',
    value: Math.max(Math.abs(r?.metrics?.total_return_pct ?? 1), 1),
    color: i === selectedIdx ? '#089981' : COMPARE_COLORS[i % COMPARE_COLORS.length],
    ret: r?.metrics?.total_return_pct ?? 0,
  }))

  const option = {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'item', formatter: '{b}: {d}%', textStyle: { fontSize: 10, color: '#e0e3ea' }, backgroundColor: '#1e222d', borderColor: '#2a2e39' },
    series: [{
      type: 'pie', radius: ['48%', '74%'], center: ['36%', '50%'],
      label: { show: false },
      itemStyle: { borderColor: '#131722', borderWidth: 2 },
      data: data.map(d => ({ value: d.value, name: d.name, itemStyle: { color: d.color } })),
    }],
  }

  return (
    <div style={{ padding: '4px 10px 10px', display: 'flex', gap: 8, alignItems: 'center' }}>
      <div style={{ flexShrink: 0, width: 90 }}>
        <ReactECharts option={option} style={{ width: 90, height: 90 }} notMerge />
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        {data.map(d => (
          <div key={d.name} style={{ display: 'flex', alignItems: 'center', gap: 5, marginBottom: 4 }}>
            <div style={{ width: 8, height: 8, borderRadius: 2, background: d.color, flexShrink: 0 }} />
            <span style={{ fontSize: 9, color: 'var(--t-text-2)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{d.name}</span>
            <span style={{ fontSize: 9, fontFamily: 'var(--t-font-mono)', color: d.ret >= 0 ? 'var(--t-green)' : 'var(--t-red)', flexShrink: 0 }}>
              {d.ret >= 0 ? '+' : ''}{d.ret.toFixed(1)}%
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Активность стратегий ──────────────────────────────────────────────────────

function MiniSpark({ data, color }: { data: { value: number }[]; color: string }) {
  if (data.length < 2) return <div style={{ width: 60, height: 24, background: 'var(--t-elevated)', borderRadius: 2 }} />
  const vals = data.map(d => d.value)
  const min = Math.min(...vals), max = Math.max(...vals), rng = max - min || 1
  const W = 60, H = 24
  const pts = data.map((d, i) => ({
    x: (i / (data.length - 1)) * W,
    y: H - ((d.value - min) / rng) * (H - 4) - 2,
  }))
  const line = pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ')
  return (
    <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none">
      <path d={line} stroke={color} strokeWidth="1.5" fill="none" />
    </svg>
  )
}

function StrategyActivitySection() {
  const { reports, allFullReports, candles, selectedIdx, setSelectedIdx } = useTerminal()
  if (!reports.length) return <div style={{ padding: '8px 10px', fontSize: 10, color: 'var(--t-text-3)' }}>Нет стратегий</div>

  return (
    <div style={{ padding: '5px 10px 10px' }}>
      {reports.map((r, i) => {
        const full = allFullReports[i]
        const eq = full && candles.length ? equityFromReport(full, candles) : []
        const color = (r.total_return_pct ?? 0) >= 0 ? '#089981' : '#f23645'
        const isActive = i === selectedIdx
        return (
          <div
            key={r.report_id}
            onClick={() => setSelectedIdx(i)}
            style={{
              display: 'flex', alignItems: 'center', gap: 8, marginBottom: 5,
              padding: '4px 6px',
              background: isActive ? 'rgba(8,153,129,0.08)' : 'var(--t-elevated)',
              borderRadius: 3,
              border: `1px solid ${isActive ? '#08998140' : 'transparent'}`,
              cursor: 'pointer',
            }}
          >
            <div style={{ width: 3, height: 28, background: color, borderRadius: 2, flexShrink: 0 }} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 10, color: isActive ? 'var(--t-text)' : 'var(--t-text-2)', fontFamily: 'var(--t-font-mono)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {r.ticker}
              </div>
              <div style={{ fontSize: 8, color: 'var(--t-text-3)' }}>{r.num_trades} сд.</div>
            </div>
            <MiniSpark data={eq} color={color} />
            <span style={{ fontSize: 10, fontFamily: 'var(--t-font-mono)', fontWeight: 700, color, flexShrink: 0, minWidth: 48, textAlign: 'right' }}>
              {(r.total_return_pct ?? 0) >= 0 ? '+' : ''}{(r.total_return_pct ?? 0).toFixed(1)}%
            </span>
          </div>
        )
      })}
    </div>
  )
}

// ── AI Brain ──────────────────────────────────────────────────────────────────

function AIBrainSection() {
  const { currentSummary, decisions, status, fullReport } = useTerminal()
  const d = decisions[0]
  const color = (t: string) => t === 'APPROVE' ? 'var(--t-green)' : (t === 'REJECT' || t === 'ARCHIVE') ? 'var(--t-red)' : 'var(--t-amber)'
  const next = (t: string) => ({ APPROVE: '→ Бумажная торговля', REJECT: '→ Архивировать', ARCHIVE: '→ Завершить', REQUEST_MORE_EVIDENCE: '→ Собрать данные', MONITOR: '→ Наблюдение' }[t] ?? '→ Ожидание')
  const winRate = fullReport ? (fullReport.metrics.win_rate * 100).toFixed(1) : '—'

  return (
    <div style={{ padding: '6px 10px 10px' }}>
      {[
        { label: 'Инструмент',  value: currentSummary ? `${currentSummary.ticker} · ${currentSummary.timeframe.toUpperCase()}` : '—' },
        { label: 'Win Rate',    value: winRate !== '—' ? `${winRate}%` : '—' },
        { label: 'Агенты',      value: status ? 'ResEng · ChiefSci' : '—' },
      ].map(r => <KRow key={r.label} label={r.label} value={r.value} small />)}
      {d && (
        <>
          <Div />
          <div style={{ fontSize: 8, color: 'var(--t-text-3)', marginBottom: 3, fontFamily: 'var(--t-font-mono)' }}>ПОСЛЕДНЕЕ РЕШЕНИЕ</div>
          <div style={{ fontSize: 10, fontWeight: 700, color: color(d.type), fontFamily: 'var(--t-font-mono)', marginBottom: 2 }}>{d.type}</div>
          <div style={{ fontSize: 9, color: 'var(--t-text-3)', marginBottom: 4, lineHeight: 1.4, overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' }}>
            {d.rationale}
          </div>
          <div style={{ fontSize: 9, color: 'var(--t-accent)', fontFamily: 'var(--t-font-mono)' }}>{next(d.type)}</div>
        </>
      )}
    </div>
  )
}

// ── Strategy / Reports tabs ───────────────────────────────────────────────────

function StrategyCard({ s }: { s: Strategy }) {
  const lMap: Record<string, string> = { RESEARCH_PASS: 'ПРОШЛА', RESEARCH_FAIL: 'НЕ ПРОШЛА', VISUAL_BACKTEST: 'ТЕСТ' }
  const c = s.status === 'RESEARCH_PASS' ? 'var(--t-green)' : s.status === 'RESEARCH_FAIL' ? 'var(--t-red)' : 'var(--t-accent)'
  return (
    <div style={{ margin: '0 8px 6px', padding: '8px', background: 'var(--t-elevated)', borderRadius: 4, border: '1px solid var(--t-border)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
        <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--t-text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1, marginRight: 6 }}>{s.strategy_name ?? s.template_id}</span>
        <span style={{ fontSize: 9, color: c, whiteSpace: 'nowrap', fontFamily: 'var(--t-font-mono)' }}>{lMap[s.status] ?? s.status}</span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2px 8px' }}>
        {[['Win Rate', s.win_rate != null ? fmtPct(s.win_rate * 100) : '—'], ['Проф. фактор', s.profit_factor?.toFixed(2) ?? '—'], ['Доходность', s.total_return_pct != null ? fmtPct(s.total_return_pct, true) : '—'], ['Оценка', s.research_score != null ? String(Math.round(s.research_score)) : '—']].map(([k, v]) => (
          <div key={k} style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ fontSize: 9, color: 'var(--t-text-3)' }}>{k}</span>
            <span style={{ fontSize: 9, fontFamily: 'var(--t-font-mono)', color: 'var(--t-text-2)' }}>{v}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function DecisionItem({ d }: { d: Decision }) {
  const color = d.type === 'APPROVE' ? 'var(--t-green)' : (d.type === 'REJECT' || d.type === 'ARCHIVE') ? 'var(--t-red)' : 'var(--t-amber)'
  const lbl: Record<string, string> = { APPROVE: 'ОДОБРЕНО', REJECT: 'ОТКЛОНЕНО', ARCHIVE: 'В АРХИВ', REQUEST_MORE_EVIDENCE: 'НУЖНО БОЛЬШЕ ДАННЫХ', MONITOR: 'НАБЛЮДЕНИЕ' }
  return (
    <div style={{ margin: '0 8px 6px', padding: '8px', background: 'var(--t-elevated)', borderRadius: 4, borderLeft: `3px solid ${color}` }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
        <span style={{ fontSize: 10, fontWeight: 700, color, fontFamily: 'var(--t-font-mono)' }}>{lbl[d.type] ?? d.type}</span>
        <span style={{ fontSize: 9, color: 'var(--t-text-3)' }}>{new Date(d.timestamp).toLocaleDateString('ru')}</span>
      </div>
      <div style={{ fontSize: 9, color: 'var(--t-text-2)', marginBottom: 3, fontFamily: 'var(--t-font-mono)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{d.hypothesis_title}</div>
      <div style={{ fontSize: 9, color: 'var(--t-text-3)', lineHeight: 1.4, overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' }}>{d.rationale}</div>
    </div>
  )
}

// ── Root ──────────────────────────────────────────────────────────────────────

export default function RightPanel() {
  const { activeTab, strategies, decisions, knowledgeGraph, selectedNode } = useTerminal()

  // Стратегии
  if (activeTab === 'strategy') {
    return (
      <div style={{ height: '100%', background: 'var(--t-bg)', borderLeft: '1px solid var(--t-border)', display: 'flex', flexDirection: 'column' }}>
        <SH label="СТРАТЕГИИ" />
        <ScrollArea style={{ flex: 1 }} scrollbarSize={3}>
          {strategies.length === 0
            ? <div style={{ padding: '12px 10px', fontSize: 10, color: 'var(--t-text-3)' }}>Стратегии не найдены</div>
            : strategies.map(s => <StrategyCard key={s.id} s={s} />)}
        </ScrollArea>
      </div>
    )
  }

  // Отчёты / Аналитика
  if (activeTab === 'reports' || activeTab === 'scientist') {
    return (
      <div style={{ height: '100%', background: 'var(--t-bg)', borderLeft: '1px solid var(--t-border)', display: 'flex', flexDirection: 'column' }}>
        <SH label="РЕШЕНИЯ AI" accent="var(--t-amber)" />
        <ScrollArea style={{ flex: 1 }} scrollbarSize={3}>
          {decisions.length === 0
            ? <div style={{ padding: '12px 10px', fontSize: 10, color: 'var(--t-text-3)' }}>Решений нет</div>
            : decisions.map(d => <DecisionItem key={d.id} d={d} />)}
        </ScrollArea>
      </div>
    )
  }

  // База знаний (legacy)
  if (activeTab === 'knowledge') {
    const node = knowledgeGraph?.nodes.find(n => n.id === selectedNode)
    return (
      <div style={{ height: '100%', background: 'var(--t-bg)', borderLeft: '1px solid var(--t-border)', display: 'flex', flexDirection: 'column' }}>
        <SH label="УЗЕЛ ЗНАНИЙ" />
        {node ? (
          <div style={{ padding: '10px' }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--t-text)', marginBottom: 6 }}>{node.label}</div>
            <span className="t-chip" style={{ fontSize: 8, display: 'inline-block', marginBottom: 8 }}>{node.type}</span>
            <div style={{ fontSize: 10, color: 'var(--t-text-2)', lineHeight: 1.5, marginTop: 6 }}>{node.description}</div>
          </div>
        ) : (
          <div style={{ padding: '12px 10px', fontSize: 10, color: 'var(--t-text-3)' }}>Нажмите на узел графа</div>
        )}
      </div>
    )
  }

  // Настройки
  if (activeTab === 'settings') {
    return (
      <div style={{ height: '100%', background: 'var(--t-bg)', borderLeft: '1px solid var(--t-border)', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
        <span style={{ fontSize: 10, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)' }}>Настройки</span>
      </div>
    )
  }

  // ── Терминал (terminal / history / backtests / portfolio / risks) ─────────
  return (
    <div style={{ height: '100%', background: 'var(--t-bg)', borderLeft: '1px solid var(--t-border)', display: 'flex', flexDirection: 'column' }}>
      <ScrollArea style={{ flex: 1 }} scrollbarSize={3}>
        {/* Инспектор сделки — появляется при клике на строку */}
        <TradeInspector />

        <SH label="ПОРТФЕЛЬ" />
        <PortfolioSection />

        <SH label="КРИВАЯ КАПИТАЛА" accent="var(--t-green)" />
        <EquitySection />

        <SH label="РИСК-МЕТРИКИ" accent="var(--t-red)" />
        <RiskSection />

        <SH label="РАСПРЕДЕЛЕНИЕ" />
        <AllocationSection />

        <SH label="АКТИВНОСТЬ СТРАТЕГИЙ" />
        <StrategyActivitySection />

        <SH label="AI BRAIN" accent="var(--t-amber)" />
        <AIBrainSection />
      </ScrollArea>
    </div>
  )
}
