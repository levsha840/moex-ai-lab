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

function SH({ label }: { label: string }) {
  return <div className="t-section-title" style={{ fontSize: 9, letterSpacing: 1 }}>{label}</div>
}

// ── KPI row ───────────────────────────────────────────────────────────────────

function KRow({ label, value, color, small }: { label: string; value: string; color?: string; small?: boolean }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 5 }}>
      <span style={{ fontSize: small ? 9 : 10, color: 'var(--t-text-3)' }}>{label}</span>
      <span style={{ fontSize: small ? 10 : 11, fontFamily: 'var(--t-font-mono)', color: color ?? 'var(--t-text)', fontWeight: color ? 600 : 400 }}>
        {value}
      </span>
    </div>
  )
}

function Div() {
  return <div style={{ height: 1, background: 'var(--t-border)', margin: '6px 0' }} />
}

// ── Портфель: единый источник данных ─────────────────────────────────────────

function PortfolioSection() {
  const { fullReport, paper, currentSummary, isLoadingReport } = useTerminal()

  if (isLoadingReport) {
    return <div style={{ padding: '10px', fontSize: 10, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)' }}>Загрузка…</div>
  }
  if (!currentSummary) {
    return <div style={{ padding: '10px', fontSize: 10, color: 'var(--t-text-3)' }}>Выберите стратегию</div>
  }

  // === BACKTEST — единственный источник: fullReport ===
  if (fullReport) {
    const m = metricsFromReport(fullReport)
    return (
      <div style={{ padding: '8px 10px 10px' }}>
        <div style={{ fontSize: 8, color: 'var(--t-cyan)', fontFamily: 'var(--t-font-mono)', marginBottom: 6, letterSpacing: 0.5 }}>
          ВИЗУАЛЬНЫЙ БЭКТЕСТ · {m.ticker}
        </div>
        <KRow label="Нач. капитал"    value={fmtM(m.initialCapital)} />
        <KRow label="Итог. капитал"   value={fmtM(m.currentCapital)} />
        <KRow label="PnL"             value={`${m.pnl >= 0 ? '+' : ''}${fmtM(m.pnl)}`}  color={pnlColor(m.pnl)} />
        <KRow label="Доходность"      value={fmtPct(m.pnlPct, true)}                     color={pnlColor(m.pnlPct)} />
        <Div />
        <KRow label="Итог. кэш"       value={fmtM(m.freeCash)} />
        <KRow label="Время в позиции" value={fmtPct(m.usedPct)}                           color="var(--t-cyan)" />
        <KRow label="Сделок"          value={String(m.numTrades)} />
        <KRow label="Win Rate"        value={fmtPct(m.winRate)}                            color={m.winRate >= 50 ? 'var(--t-green)' : 'var(--t-red)'} />
        <KRow label="Проф. фактор"    value={isFinite(m.profitFactor) ? m.profitFactor.toFixed(2) : '∞'} />
      </div>
    )
  }

  // === PAPER MODE ===
  if (paper) {
    const m = metricsFromPaper(paper)
    return (
      <div style={{ padding: '8px 10px 10px' }}>
        <div style={{ fontSize: 8, color: 'var(--t-amber)', fontFamily: 'var(--t-font-mono)', marginBottom: 6, letterSpacing: 0.5 }}>
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
          <div style={{ marginTop: 6, padding: '4px 6px', background: 'var(--t-amber-soft)', borderRadius: 3, fontSize: 9, color: 'var(--t-amber)', lineHeight: 1.4 }}>
            {paper.note}
          </div>
        )}
      </div>
    )
  }

  return <div style={{ padding: '10px', fontSize: 10, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)' }}>Ожидание данных…</div>
}

// ── Риск-метрики: из того же fullReport ───────────────────────────────────────

function RiskSection() {
  const { fullReport, paper, currentSummary, isLoadingReport } = useTerminal()
  if (isLoadingReport || !currentSummary) return null

  if (fullReport) {
    const m = metricsFromReport(fullReport)
    return (
      <div style={{ padding: '8px 10px 10px' }}>
        <KRow label="Макс. просадка" value={`-${m.maxDrawdown.toFixed(2)}%`}    color="var(--t-red)" />
        <KRow label="Тек. просадка"  value={`-${m.currentDrawdown.toFixed(2)}%`} color={m.currentDrawdown > 5 ? 'var(--t-amber)' : 'var(--t-text)'} />
        <KRow label="Sharpe"         value={m.sharpe.toFixed(2)}                 color={m.sharpe >= 1 ? 'var(--t-green)' : m.sharpe >= 0 ? 'var(--t-text)' : 'var(--t-red)'} />
        <KRow label="Sortino"        value={m.sortino.toFixed(2)}                color={m.sortino >= 1 ? 'var(--t-green)' : 'var(--t-text)'} />
        <KRow label="Calmar"         value={m.calmar.toFixed(2)}                 color={m.calmar >= 0.5 ? 'var(--t-green)' : 'var(--t-text)'} />
        <KRow label="VaR 95%"        value={`-${m.var95.toFixed(2)}%`}           color="var(--t-red)" />
      </div>
    )
  }
  if (paper) {
    const m = metricsFromPaper(paper)
    return (
      <div style={{ padding: '8px 10px 10px' }}>
        <KRow label="Макс. просадка" value={`-${m.maxDrawdown.toFixed(2)}%`} color="var(--t-red)" />
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginTop: 4, padding: '4px 6px', background: 'var(--t-elevated)', borderRadius: 3 }}>
          <IconAlertTriangle size={10} color="var(--t-amber)" />
          <span style={{ fontSize: 9, color: 'var(--t-text-3)', lineHeight: 1.3 }}>
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
        {fullReport ? 'Стратегия ещё не имеет сделок' : 'Нет данных бэктеста'}
      </div>
    )
  }

  return (
    <div style={{ padding: '0 0 4px' }}>
      <EquityChart
        primaryData={primaryData}
        primaryLabel={primaryLabel}
        compareData={compareData}
        height={160}
        compact
        onOpenFull={() => setEquityExpanded(true)}
      />
    </div>
  )
}

// ── Распределение капитала (ECharts donut) ────────────────────────────────────

function AllocationSection() {
  const { allFullReports, selectedIdx } = useTerminal()
  if (!allFullReports.length) return <div style={{ padding: '8px 10px', fontSize: 10, color: 'var(--t-text-3)' }}>Нет стратегий</div>

  const data = allFullReports.map((r, i) => ({
    name: r?.ticker ?? '?',
    value: Math.max(Math.abs(r?.metrics?.total_return_pct ?? 1), 1),
    color: i === selectedIdx ? '#089981' : COMPARE_COLORS[i % COMPARE_COLORS.length],
    ret: r?.metrics?.total_return_pct ?? 0,
  }))
  const total = data.reduce((s, d) => s + d.value, 0)

  const option = {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'item', formatter: '{b}: {d}%', textStyle: { fontSize: 10, color: '#e0e3ea' }, backgroundColor: '#1e222d', borderColor: '#2a2e39' },
    series: [{
      type: 'pie',
      radius: ['48%', '76%'],
      center: ['36%', '50%'],
      label: { show: false },
      itemStyle: { borderColor: '#131722', borderWidth: 2 },
      data: data.map(d => ({ value: d.value, name: d.name, itemStyle: { color: d.color } })),
    }],
  }

  return (
    <div style={{ padding: '4px 10px 10px', display: 'flex', gap: 8, alignItems: 'center' }}>
      <div style={{ flexShrink: 0, width: 96 }}>
        <ReactECharts option={option} style={{ width: 96, height: 96 }} notMerge />
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

// ── Активность стратегий (мини-спарклайны) ────────────────────────────────────

function MiniSpark({ data, color }: { data: { value: number }[]; color: string }) {
  if (data.length < 2) return <div style={{ width: 60, height: 24, background: 'var(--t-elevated)', borderRadius: 2 }} />
  const vals = data.map(d => d.value)
  const min = Math.min(...vals), max = Math.max(...vals), rng = max - min || 1
  const W = 60, H = 24
  const pts = data.map((d, i) => ({
    x: (i / (data.length - 1)) * W,
    y: H - ((d.value - min) / rng) * (H - 3) - 1,
  }))
  const line = pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ')
  return (
    <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none">
      <path d={line} stroke={color} strokeWidth="1.5" fill="none" />
    </svg>
  )
}

function StrategyActivitySection() {
  const { reports, allFullReports, candles, selectedIdx } = useTerminal()
  if (!reports.length) return <div style={{ padding: '8px 10px', fontSize: 10, color: 'var(--t-text-3)' }}>Нет стратегий</div>

  return (
    <div style={{ padding: '6px 10px 10px' }}>
      {reports.map((r, i) => {
        const full = allFullReports[i]
        const eq = full && candles.length ? equityFromReport(full, candles) : []
        const color = (r.total_return_pct ?? 0) >= 0 ? '#089981' : '#f23645'
        const isActive = i === selectedIdx
        return (
          <div key={r.report_id} style={{
            display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6,
            padding: '4px 6px',
            background: isActive ? 'rgba(8,153,129,0.08)' : 'var(--t-elevated)',
            borderRadius: 3,
            border: `1px solid ${isActive ? '#08998140' : 'transparent'}`,
          }}>
            <div style={{ width: 3, height: 30, background: color, borderRadius: 2, flexShrink: 0 }} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 10, color: isActive ? 'var(--t-text)' : 'var(--t-text-2)', fontFamily: 'var(--t-font-mono)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {r.ticker}
              </div>
              <div style={{ fontSize: 8, color: 'var(--t-text-3)' }}>{r.num_trades} сделок</div>
            </div>
            <MiniSpark data={eq} color={color} />
            <span style={{ fontSize: 10, fontFamily: 'var(--t-font-mono)', fontWeight: 700, color, flexShrink: 0, minWidth: 50, textAlign: 'right' }}>
              {(r.total_return_pct ?? 0) >= 0 ? '+' : ''}{(r.total_return_pct ?? 0).toFixed(1)}%
            </span>
          </div>
        )
      })}
    </div>
  )
}

// ── AI Brain ──────────────────────────────────────────────────────────────────

const REGIME_MAP: Record<string, string> = {
  bb: 'Флэт / Консолидация', squeeze: 'Флэт / Консолидация',
  dual_ma: 'Тренд / Импульс', trend: 'Тренд / Импульс',
  rsi: 'Откат / Mean-Rev', oversold: 'Откат / Mean-Rev',
}
function inferRegime(h: string) {
  const id = h.toLowerCase()
  for (const [k, v] of Object.entries(REGIME_MAP)) if (id.includes(k)) return v
  return 'Неизвестно'
}

function AIBrainSection() {
  const { currentSummary, decisions, status, fullReport } = useTerminal()
  const d = decisions[0]
  const color = (t: string) => t === 'APPROVE' ? 'var(--t-green)' : (t === 'REJECT' || t === 'ARCHIVE') ? 'var(--t-red)' : 'var(--t-amber)'
  const next = (t: string) => ({ APPROVE: '→ Переводим в бумажный', REJECT: '→ Архивировать', ARCHIVE: '→ Завершить', REQUEST_MORE_EVIDENCE: '→ Собрать данные', MONITOR: '→ Наблюдение' }[t] ?? '→ Ожидание')
  const winRate = fullReport ? (fullReport.metrics.win_rate * 100).toFixed(1) : '—'

  return (
    <div style={{ padding: '8px 10px 10px' }}>
      {[
        { label: 'Инструмент',  value: currentSummary ? `${currentSummary.ticker} · ${currentSummary.timeframe.toUpperCase()}` : '—' },
        { label: 'Режим рынка', value: currentSummary ? inferRegime(currentSummary.hypothesis_id) : '—' },
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

// ── Research ──────────────────────────────────────────────────────────────────

function ResearchSection() {
  const { status } = useTerminal()
  if (!status) return <div style={{ padding: '8px 10px', fontSize: 10, color: 'var(--t-text-3)' }}>Загрузка…</div>
  const b = status.research_budget
  const pct = b.total > 0 ? (b.used / b.total) * 100 : 0
  const stage = status.candidates.approved_for_paper > 0 ? 'Бумажная торговля'
    : status.research.visual_backtest_reports > 0 ? 'Валидация'
    : status.research.sessions > 0 ? 'Исследование' : 'Обнаружение'
  return (
    <div style={{ padding: '8px 10px 10px' }}>
      <KRow label="Этап"    value={stage} color="var(--t-cyan)" small />
      <KRow label="Сессии"  value={String(status.research.sessions)} small />
      <KRow label="Находки" value={String(status.research.total_findings)} small />
      <div style={{ marginTop: 4 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
          <span style={{ fontSize: 9, color: 'var(--t-text-3)' }}>Бюджет</span>
          <span style={{ fontSize: 9, fontFamily: 'var(--t-font-mono)', color: 'var(--t-text-2)' }}>{b.used}/{b.total}</span>
        </div>
        <div style={{ height: 4, background: 'var(--t-elevated)', borderRadius: 2 }}>
          <div style={{ height: '100%', borderRadius: 2, width: `${Math.min(pct, 100)}%`, background: pct > 80 ? 'var(--t-red)' : pct > 50 ? 'var(--t-amber)' : 'var(--t-accent)' }} />
        </div>
      </div>
    </div>
  )
}

function PipelineSection() {
  const { status } = useTerminal()
  const STAGES = ['Реестр', 'Исследование', 'Знания', 'Валидация', 'Бумажный', 'Sandbox', 'Live']
  const stage = !status ? 0
    : status.candidates.approved_for_paper > 0 ? 4
    : status.research.visual_backtest_reports > 0 ? 3
    : status.research.sessions > 0 ? 2
    : status.hypotheses.tested > 0 ? 1 : 0
  return (
    <div style={{ padding: '8px 10px 10px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'nowrap', overflowX: 'auto' }}>
        {STAGES.map((s, i) => {
          const isActive = i === stage, isDone = i < stage
          return (
            <div key={s} style={{ display: 'flex', alignItems: 'center', flexShrink: 0 }}>
              <div style={{ padding: '2px 4px', borderRadius: 2, fontSize: 7, fontFamily: 'var(--t-font-mono)', fontWeight: 700, background: isActive ? 'var(--t-accent-soft)' : isDone ? 'var(--t-green-soft)' : 'var(--t-elevated)', color: isActive ? 'var(--t-accent)' : isDone ? 'var(--t-green)' : 'var(--t-text-3)', border: `1px solid ${isActive ? 'var(--t-accent)' : isDone ? 'var(--t-green)' : 'var(--t-border)'}`, whiteSpace: 'nowrap' }}>
                {isDone && '✓ '}{s}
              </div>
              {i < STAGES.length - 1 && <div style={{ fontSize: 7, color: 'var(--t-text-3)', margin: '0 1px' }}>▶</div>}
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ── Strategy / Scientist / Knowledge tabs ─────────────────────────────────────

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

  if (activeTab === 'scientist') {
    return (
      <div style={{ height: '100%', background: 'var(--t-bg)', borderLeft: '1px solid var(--t-border)', display: 'flex', flexDirection: 'column' }}>
        <SH label="ГЛАВНЫЙ УЧЁНЫЙ" />
        <ScrollArea style={{ flex: 1 }} scrollbarSize={3}>
          {decisions.length === 0
            ? <div style={{ padding: '12px 10px', fontSize: 10, color: 'var(--t-text-3)' }}>Решений нет</div>
            : decisions.map(d => <DecisionItem key={d.id} d={d} />)}
        </ScrollArea>
      </div>
    )
  }

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

  return (
    <div style={{ height: '100%', background: 'var(--t-bg)', borderLeft: '1px solid var(--t-border)', display: 'flex', flexDirection: 'column' }}>
      <ScrollArea style={{ flex: 1 }} scrollbarSize={3}>
        <SH label="⬡ ПОРТФЕЛЬ" />
        <PortfolioSection />
        <SH label="⬡ КРИВАЯ КАПИТАЛА" />
        <EquitySection />
        <SH label="⬡ РИСК-МЕТРИКИ" />
        <RiskSection />
        <SH label="⬡ РАСПРЕДЕЛЕНИЕ" />
        <AllocationSection />
        <SH label="⬡ АКТИВНОСТЬ СТРАТЕГИЙ" />
        <StrategyActivitySection />
        <SH label="⬡ AI BRAIN" />
        <AIBrainSection />
        <SH label="⬡ ПРОГРЕСС" />
        <ResearchSection />
        <SH label="⬡ PIPELINE" />
        <PipelineSection />
      </ScrollArea>
    </div>
  )
}
