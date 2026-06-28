import { ScrollArea } from '@mantine/core'
import ReactECharts from 'echarts-for-react'
import { useTerminal } from '../../context/TerminalContext'
import { calcRiskMetrics } from '../../utils/indicators'
import type { Strategy, Decision, Report, ReportSummary } from '../../api/client'

// ── Вспомогательные функции ───────────────────────────────────────────────────

function fmt(n: number | null | undefined, dec = 2): string {
  if (n === null || n === undefined) return '—'
  return n.toLocaleString('ru-RU', { minimumFractionDigits: dec, maximumFractionDigits: dec })
}
function fmtM(n: number | null | undefined): string {
  if (n === null || n === undefined) return '—'
  if (Math.abs(n) >= 1_000_000) return `${(n / 1_000_000).toFixed(3)} М₽`
  if (Math.abs(n) >= 1_000) return `${(n / 1_000).toFixed(1)} к₽`
  return `${n.toFixed(0)} ₽`
}
function shortHyp(h: string): string {
  return h.replace('tmpl_h_', '').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

function SectionHeader({ label }: { label: string }) {
  return <div className="t-section-title" style={{ fontSize: 9 }}>{label}</div>
}

function KpiRow({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 5 }}>
      <span style={{ fontSize: 10, color: 'var(--t-text-2)' }}>{label}</span>
      <span style={{ fontSize: 11, fontFamily: 'var(--t-font-mono)', color: color ?? 'var(--t-text)' }}>{value}</span>
    </div>
  )
}

// ── Спарклайн (SVG) ───────────────────────────────────────────────────────────

function Sparkline({ capitals, color = '#089981' }: { capitals: number[]; color?: string }) {
  if (capitals.length < 2) return (
    <div style={{ height: 50, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <span style={{ fontSize: 10, color: 'var(--t-text-3)' }}>Нет сделок</span>
    </div>
  )
  const min = Math.min(...capitals)
  const max = Math.max(...capitals)
  const rng = max - min || 1
  const W = 270, H = 50
  const pts = capitals.map((v, i) => ({
    x: (i / (capitals.length - 1)) * W,
    y: H - ((v - min) / rng) * (H - 4) - 2,
  }))
  const line = pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ')
  const area = `${line} L${W} ${H} L0 ${H} Z`
  return (
    <svg width="100%" height={H} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" style={{ display: 'block' }}>
      <path d={area} fill={`${color}18`} />
      <path d={line} stroke={color} strokeWidth="1.5" fill="none" />
    </svg>
  )
}

// Маленький спарклайн для «Активность стратегий»
function MiniSparkline({ capitals, color }: { capitals: number[]; color: string }) {
  if (capitals.length < 2) return <div style={{ width: 60, height: 24, background: 'var(--t-elevated)', borderRadius: 2 }} />
  const min = Math.min(...capitals)
  const max = Math.max(...capitals)
  const rng = max - min || 1
  const W = 60, H = 24
  const pts = capitals.map((v, i) => ({
    x: (i / (capitals.length - 1)) * W,
    y: H - ((v - min) / rng) * (H - 3) - 1,
  }))
  const line = pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ')
  return (
    <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none">
      <path d={line} stroke={color} strokeWidth="1.5" fill="none" />
    </svg>
  )
}

// ── Портфель ──────────────────────────────────────────────────────────────────

function PortfolioSection() {
  const { paper, currentSummary, trades } = useTerminal()

  if (paper) {
    const pnlColor = paper.total_pnl >= 0 ? 'var(--t-green)' : 'var(--t-red)'
    return (
      <div style={{ padding: '8px 10px 10px' }}>
        <KpiRow label="Нач. капитал"        value={fmtM(paper.initial_capital)} />
        <KpiRow label="Тек. капитал"        value={fmtM(paper.current_capital)} />
        <KpiRow label="Прибыль/убыток"      value={`${paper.total_pnl >= 0 ? '+' : ''}${fmtM(paper.total_pnl)}`} color={pnlColor} />
        <KpiRow label="Доходность"          value={`${paper.total_return_pct >= 0 ? '+' : ''}${fmt(paper.total_return_pct)}%`} color={pnlColor} />
        <KpiRow label="Свободные средства"  value={fmtM(paper.current_capital * (1 - paper.exposure_pct / 100))} />
        <KpiRow label="Использовано"        value={`${fmt(paper.exposure_pct)}%`} color="var(--t-cyan)" />
        <KpiRow label="Позиции"             value={String(paper.open_positions)} />
        <KpiRow label="Доля прибыльных"     value={`${fmt(paper.win_rate * 100)}%`} color={paper.win_rate >= 0.5 ? 'var(--t-green)' : 'var(--t-red)'} />
        {paper.note && (
          <div style={{ marginTop: 6, padding: '4px 6px', background: 'var(--t-amber-soft)', borderRadius: 3, fontSize: 9, color: 'var(--t-amber)', lineHeight: 1.4 }}>
            {paper.note}
          </div>
        )}
      </div>
    )
  }

  const r = currentSummary
  if (!r) return <div style={{ padding: '10px', fontSize: 10, color: 'var(--t-text-3)' }}>Выберите инструмент</div>
  const initCap = (r.metrics as any)?.initial_capital ?? 1_000_000
  const finalCap = trades.length > 0 ? (trades[trades.length - 1]?.capital_after ?? initCap) : initCap
  const pnl = finalCap - initCap
  const retPct = ((finalCap - initCap) / initCap) * 100
  const pnlColor = pnl >= 0 ? 'var(--t-green)' : 'var(--t-red)'
  return (
    <div style={{ padding: '8px 10px 10px' }}>
      <div style={{ fontSize: 9, color: 'var(--t-amber)', marginBottom: 6, fontFamily: 'var(--t-font-mono)' }}>БУМАЖНЫЙ ТОРГОВЛЯ: STANDBY</div>
      <KpiRow label="Нач. капитал"        value={fmtM(initCap)} />
      <KpiRow label="Итоговый капитал"    value={fmtM(finalCap)} />
      <KpiRow label="Прибыль/убыток"      value={`${pnl >= 0 ? '+' : ''}${fmtM(pnl)}`}     color={pnlColor} />
      <KpiRow label="Доходность"          value={`${retPct >= 0 ? '+' : ''}${fmt(retPct)}%`} color={pnlColor} />
      <KpiRow label="Свободные средства"  value={fmtM(initCap)} />
      <KpiRow label="Использовано"        value="0%" />
      <KpiRow label="Сделок"              value={String(r.num_trades)} />
      <KpiRow label="Доля прибыльных"     value={`${(r.win_rate * 100).toFixed(1)}%`}        color={r.win_rate >= 0.5 ? 'var(--t-green)' : 'var(--t-red)'} />
      <KpiRow label="Профит-фактор"       value={r.profit_factor === Infinity ? '∞' : fmt(r.profit_factor)} />
      <KpiRow label="Макс. просадка"      value={`-${fmt(r.max_drawdown_pct)}%`}              color="var(--t-red)" />
    </div>
  )
}

// ── Риск-метрики ──────────────────────────────────────────────────────────────

function RiskSection() {
  const { trades, currentSummary } = useTerminal()
  const initCap = (currentSummary?.metrics as any)?.initial_capital ?? 1_000_000
  const risk = calcRiskMetrics(trades, initCap)
  return (
    <div style={{ padding: '8px 10px 10px' }}>
      <KpiRow label="Макс. просадка" value={`-${risk.maxDD}%`}              color="var(--t-red)" />
      <KpiRow label="Тек. просадка"  value={risk.currentDD > 0 ? `-${risk.currentDD}%` : '0.00%'} color={risk.currentDD > 5 ? 'var(--t-amber)' : 'var(--t-text)'} />
      <KpiRow label="Шарп"           value={String(risk.sharpe)}             color={risk.sharpe >= 1 ? 'var(--t-green)' : 'var(--t-text)'} />
      <KpiRow label="Сортино"        value={String(risk.sortino)}            color={risk.sortino >= 1 ? 'var(--t-green)' : 'var(--t-text)'} />
      <KpiRow label="Кальмар"        value={String(risk.calmar)}             color={risk.calmar >= 0.5 ? 'var(--t-green)' : 'var(--t-text)'} />
      <KpiRow label="VaR 95%"        value={`-${risk.var95}%`}              color="var(--t-red)" />
    </div>
  )
}

// ── Распределение капитала (круговая диаграмма) ───────────────────────────────

const ALLOC_COLORS = ['#089981', '#2962ff', '#ffb800', '#f23645', '#00b0ff']

function AllocationSection() {
  const { reports, allFullReports } = useTerminal()

  const data = reports.map((r, i) => {
    const fullR = allFullReports[i]
    const trades = (fullR as any)?.trade_journal ?? []
    const initCap = (r.metrics as any)?.initial_capital ?? 1_000_000
    const finalCap = trades.length > 0 ? (trades[trades.length - 1]?.capital_after ?? initCap) : initCap
    return {
      name: shortHyp(r.hypothesis_id),
      value: Math.max(Math.abs(r.total_return_pct), 1),
      color: ALLOC_COLORS[i % ALLOC_COLORS.length],
    }
  })

  if (data.length === 0) {
    return <div style={{ padding: '10px', fontSize: 10, color: 'var(--t-text-3)' }}>Нет данных</div>
  }

  const option = {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'item', formatter: '{b}: {d}%', textStyle: { fontSize: 10 } },
    series: [{
      type: 'pie',
      radius: ['48%', '76%'],
      center: ['38%', '50%'],
      label: { show: false },
      itemStyle: { borderColor: '#131722', borderWidth: 2 },
      data: data.map(d => ({ value: d.value, name: d.name, itemStyle: { color: d.color } })),
    }],
  }

  const total = data.reduce((s, d) => s + d.value, 0)

  return (
    <div style={{ padding: '6px 10px 10px', display: 'flex', gap: 8, alignItems: 'center' }}>
      <div style={{ flexShrink: 0, width: 100 }}>
        <ReactECharts option={option} style={{ width: 100, height: 100 }} notMerge />
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        {data.map(d => (
          <div key={d.name} style={{ display: 'flex', alignItems: 'center', gap: 5, marginBottom: 4 }}>
            <div style={{ width: 8, height: 8, borderRadius: 2, background: d.color, flexShrink: 0 }} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 9, color: 'var(--t-text-2)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {d.name}
              </div>
            </div>
            <span style={{ fontSize: 9, fontFamily: 'var(--t-font-mono)', color: 'var(--t-text-3)', flexShrink: 0 }}>
              {(d.value / total * 100).toFixed(0)}%
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Активность стратегий ──────────────────────────────────────────────────────

function StrategyActivitySection() {
  const { reports, allFullReports } = useTerminal()

  if (reports.length === 0) {
    return <div style={{ padding: '10px', fontSize: 10, color: 'var(--t-text-3)' }}>Нет стратегий</div>
  }

  return (
    <div style={{ padding: '6px 10px 10px' }}>
      {reports.map((r, i) => {
        const full = allFullReports[i]
        const jrnl = (full as any)?.trade_journal ?? []
        const caps: number[] = jrnl.map((t: any) => t.capital_after)
        const color = r.total_return_pct >= 0 ? '#089981' : '#f23645'
        return (
          <div key={r.report_id} style={{
            display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6,
            padding: '4px 6px', background: 'var(--t-elevated)', borderRadius: 3,
          }}>
            <div style={{ width: 4, height: 32, background: color, borderRadius: 2, flexShrink: 0 }} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 9, color: 'var(--t-text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontFamily: 'var(--t-font-mono)' }}>
                {shortHyp(r.hypothesis_id)}
              </div>
              <div style={{ fontSize: 8, color: 'var(--t-text-3)', marginTop: 1 }}>
                {r.ticker} · {r.num_trades} сделок
              </div>
            </div>
            <MiniSparkline capitals={caps} color={color} />
            <span style={{
              fontSize: 10, fontFamily: 'var(--t-font-mono)', fontWeight: 700,
              color, flexShrink: 0, minWidth: 48, textAlign: 'right',
            }}>
              {r.total_return_pct >= 0 ? '+' : ''}{r.total_return_pct.toFixed(1)}%
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
  const { currentSummary, decisions, status } = useTerminal()
  const d = decisions[0]
  const color = (t: string) => t === 'APPROVE' ? 'var(--t-green)' : t === 'REJECT' || t === 'ARCHIVE' ? 'var(--t-red)' : 'var(--t-amber)'
  const next = (t: string) => ({
    APPROVE: '→ Переводим в бумажный',
    REJECT: '→ Архивировать',
    ARCHIVE: '→ Завершить',
    REQUEST_MORE_EVIDENCE: '→ Собрать данные',
    MONITOR: '→ Наблюдение',
  }[t] ?? '→ Ожидание')

  return (
    <div style={{ padding: '8px 10px 10px' }}>
      {[
        { label: 'Гипотеза',    value: currentSummary?.hypothesis_id ? shortHyp(currentSummary.hypothesis_id) : '—' },
        { label: 'Режим рынка', value: currentSummary ? inferRegime(currentSummary.hypothesis_id) : '—' },
        { label: 'Уверенность', value: currentSummary?.win_rate != null ? `${(currentSummary.win_rate * 100).toFixed(1)}%` : '—' },
        { label: 'Инструмент',  value: currentSummary ? `${currentSummary.ticker} · ${currentSummary.timeframe.toUpperCase()}` : '—' },
        { label: 'Агенты',      value: status ? 'ResEng · ChiefSci' : '—' },
      ].map(r => <KpiRow key={r.label} label={r.label} value={r.value} />)}

      {d && (
        <>
          <div style={{ height: 1, background: 'var(--t-border)', margin: '6px 0 4px' }} />
          <div style={{ fontSize: 9, color: 'var(--t-text-3)', marginBottom: 3 }}>ПОСЛЕДНЕЕ РЕШЕНИЕ УЧЁНОГО</div>
          <div style={{ fontSize: 10, fontWeight: 700, color: color(d.type), fontFamily: 'var(--t-font-mono)', marginBottom: 2 }}>
            {d.type}
          </div>
          <div style={{ fontSize: 9, color: 'var(--t-text-3)', marginBottom: 4, lineHeight: 1.4, overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' }}>
            {d.rationale}
          </div>
          <div style={{ fontSize: 9, color: 'var(--t-accent)', fontFamily: 'var(--t-font-mono)' }}>
            {next(d.type)}
          </div>
        </>
      )}
    </div>
  )
}

// ── Прогресс исследования ─────────────────────────────────────────────────────

function ResearchSection() {
  const { status } = useTerminal()
  if (!status) return <div style={{ padding: '10px', fontSize: 10, color: 'var(--t-text-3)' }}>Загрузка…</div>
  const b = status.research_budget
  const pct = b.total > 0 ? (b.used / b.total) * 100 : 0
  const stage = status.candidates.approved_for_paper > 0 ? 'Бумажная торговля'
    : status.research.visual_backtest_reports > 0 ? 'Валидация'
    : status.research.sessions > 0 ? 'Исследование'
    : 'Обнаружение'
  return (
    <div style={{ padding: '8px 10px 10px' }}>
      <KpiRow label="Кампания"   value="v1 · Активна" />
      <KpiRow label="Этап"       value={stage}                                    color="var(--t-cyan)" />
      <KpiRow label="Сессии"     value={String(status.research.sessions)} />
      <KpiRow label="Находки"    value={String(status.research.total_findings)} />
      <KpiRow label="База знаний" value={`${status.knowledge_base.snapshots} снимков`} />
      <div style={{ marginTop: 5 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
          <span style={{ fontSize: 9, color: 'var(--t-text-3)' }}>Бюджет</span>
          <span style={{ fontSize: 9, fontFamily: 'var(--t-font-mono)', color: 'var(--t-text-2)' }}>{b.used} / {b.total}</span>
        </div>
        <div style={{ height: 4, background: 'var(--t-elevated)', borderRadius: 2 }}>
          <div style={{ height: '100%', borderRadius: 2, width: `${Math.min(pct, 100)}%`, background: pct > 80 ? 'var(--t-red)' : pct > 50 ? 'var(--t-amber)' : 'var(--t-accent)' }} />
        </div>
      </div>
    </div>
  )
}

// ── Pipeline стратегии ────────────────────────────────────────────────────────

const STAGES_RU = ['Реестр', 'Исследование', 'Знания', 'Валидация', 'Бумажный', 'Sandbox', 'Live']

function PipelineSection() {
  const { status } = useTerminal()
  const stage = !status ? 0
    : status.candidates.approved_for_paper > 0 ? 4
    : status.research.visual_backtest_reports > 0 ? 3
    : status.research.sessions > 0 ? 2
    : status.hypotheses.tested > 0 ? 1 : 0

  return (
    <div style={{ padding: '8px 10px 10px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'nowrap', overflowX: 'auto' }}>
        {STAGES_RU.map((s, i) => {
          const isActive = i === stage
          const isDone   = i < stage
          return (
            <div key={s} style={{ display: 'flex', alignItems: 'center', flexShrink: 0 }}>
              <div style={{
                padding: '2px 4px', borderRadius: 2, fontSize: 7, fontFamily: 'var(--t-font-mono)', fontWeight: 700,
                background: isActive ? 'var(--t-accent-soft)' : isDone ? 'var(--t-green-soft)' : 'var(--t-elevated)',
                color: isActive ? 'var(--t-accent)' : isDone ? 'var(--t-green)' : 'var(--t-text-3)',
                border: `1px solid ${isActive ? 'var(--t-accent)' : isDone ? 'var(--t-green)' : 'var(--t-border)'}`,
                whiteSpace: 'nowrap',
              }}>
                {isDone && '✓ '}{s}
              </div>
              {i < STAGES_RU.length - 1 && (
                <div style={{ fontSize: 7, color: 'var(--t-text-3)', margin: '0 1px' }}>▶</div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ── Карточка стратегии ────────────────────────────────────────────────────────

function StrategyCard({ s }: { s: Strategy }) {
  const statusLabel: Record<string, string> = {
    RESEARCH_PASS: 'ПРОШЛА', RESEARCH_FAIL: 'НЕ ПРОШЛА', VISUAL_BACKTEST: 'ТЕСТ',
  }
  const statusColor = s.status === 'RESEARCH_PASS' ? 'var(--t-green)' : s.status === 'RESEARCH_FAIL' ? 'var(--t-red)' : 'var(--t-accent)'
  return (
    <div style={{ margin: '0 8px 6px', padding: '8px', background: 'var(--t-elevated)', borderRadius: 4, border: '1px solid var(--t-border)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
        <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--t-text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1, marginRight: 6 }}>
          {s.strategy_name ?? s.template_id}
        </span>
        <span style={{ fontSize: 9, fontFamily: 'var(--t-font-mono)', color: statusColor, whiteSpace: 'nowrap' }}>
          {statusLabel[s.status] ?? s.status}
        </span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2px 8px' }}>
        {[
          { k: 'Оценка', v: s.research_score != null ? fmt(s.research_score, 0) : '—' },
          { k: 'Win Rate', v: s.win_rate != null ? `${(s.win_rate * 100).toFixed(0)}%` : '—' },
          { k: 'Проф. фактор', v: s.profit_factor != null ? fmt(s.profit_factor) : '—' },
          { k: 'Доходность', v: s.total_return_pct != null ? `${s.total_return_pct >= 0 ? '+' : ''}${fmt(s.total_return_pct)}%` : '—' },
        ].map(r => (
          <div key={r.k} style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ fontSize: 9, color: 'var(--t-text-3)' }}>{r.k}</span>
            <span style={{ fontSize: 9, fontFamily: 'var(--t-font-mono)', color: 'var(--t-text-2)' }}>{r.v}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Решение учёного ────────────────────────────────────────────────────────────

function DecisionItem({ d }: { d: Decision }) {
  const color = d.type === 'APPROVE' ? 'var(--t-green)' : d.type === 'REJECT' || d.type === 'ARCHIVE' ? 'var(--t-red)' : 'var(--t-amber)'
  const label: Record<string, string> = {
    APPROVE: 'ОДОБРЕНО', REJECT: 'ОТКЛОНЕНО', ARCHIVE: 'В АРХИВ',
    REQUEST_MORE_EVIDENCE: 'НУЖНО БОЛЬШЕ ДАННЫХ', MONITOR: 'НАБЛЮДЕНИЕ',
  }
  return (
    <div style={{ margin: '0 8px 6px', padding: '8px', background: 'var(--t-elevated)', borderRadius: 4, borderLeft: `3px solid ${color}` }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
        <span style={{ fontSize: 10, fontWeight: 700, color, fontFamily: 'var(--t-font-mono)' }}>{label[d.type] ?? d.type}</span>
        <span style={{ fontSize: 9, color: 'var(--t-text-3)' }}>{new Date(d.timestamp).toLocaleDateString('ru')}</span>
      </div>
      <div style={{ fontSize: 9, color: 'var(--t-text-2)', marginBottom: 3, fontFamily: 'var(--t-font-mono)' }}>{d.hypothesis_title}</div>
      <div style={{ fontSize: 9, color: 'var(--t-text-3)', lineHeight: 1.4, overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' }}>
        {d.rationale}
      </div>
    </div>
  )
}

// ── Корневой компонент ────────────────────────────────────────────────────────

export default function RightPanel() {
  const { activeTab, trades, strategies, decisions, knowledgeGraph, selectedNode } = useTerminal()
  const capitals = trades.map(t => t.capital_after)

  if (activeTab === 'strategy') {
    return (
      <div style={{ height: '100%', background: 'var(--t-bg)', borderLeft: '1px solid var(--t-border)', display: 'flex', flexDirection: 'column' }}>
        <SectionHeader label="СТРАТЕГИИ" />
        <ScrollArea style={{ flex: 1 }} scrollbarSize={3}>
          {strategies.length === 0 && <div style={{ padding: '12px 10px', fontSize: 10, color: 'var(--t-text-3)' }}>Стратегии не найдены</div>}
          {strategies.map(s => <StrategyCard key={s.id} s={s} />)}
        </ScrollArea>
      </div>
    )
  }

  if (activeTab === 'scientist') {
    return (
      <div style={{ height: '100%', background: 'var(--t-bg)', borderLeft: '1px solid var(--t-border)', display: 'flex', flexDirection: 'column' }}>
        <SectionHeader label="ГЛАВНЫЙ УЧЁНЫЙ" />
        <ScrollArea style={{ flex: 1 }} scrollbarSize={3}>
          {decisions.length === 0 && <div style={{ padding: '12px 10px', fontSize: 10, color: 'var(--t-text-3)' }}>Решений нет</div>}
          {decisions.map(d => <DecisionItem key={d.id} d={d} />)}
        </ScrollArea>
      </div>
    )
  }

  if (activeTab === 'knowledge') {
    const node = knowledgeGraph?.nodes.find(n => n.id === selectedNode)
    return (
      <div style={{ height: '100%', background: 'var(--t-bg)', borderLeft: '1px solid var(--t-border)', display: 'flex', flexDirection: 'column' }}>
        <SectionHeader label="УЗЕЛ ЗНАНИЙ" />
        {node ? (
          <div style={{ padding: '10px' }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--t-text)', marginBottom: 6 }}>{node.label}</div>
            <span className="t-chip" style={{ fontSize: 8, marginBottom: 8, display: 'inline-block' }}>{node.type}</span>
            <div style={{ fontSize: 10, color: 'var(--t-text-2)', lineHeight: 1.5, marginTop: 6 }}>{node.description}</div>
          </div>
        ) : (
          <div style={{ padding: '12px 10px', fontSize: 10, color: 'var(--t-text-3)' }}>Нажмите на узел графа для просмотра деталей</div>
        )}
      </div>
    )
  }

  return (
    <div style={{ height: '100%', background: 'var(--t-bg)', borderLeft: '1px solid var(--t-border)', display: 'flex', flexDirection: 'column' }}>
      <ScrollArea style={{ flex: 1 }} scrollbarSize={3}>
        <SectionHeader label="⬡ ПОРТФЕЛЬ" />
        <PortfolioSection />

        <SectionHeader label="⬡ КРИВАЯ КАПИТАЛА" />
        <div style={{ padding: '4px 10px 8px' }}>
          <Sparkline capitals={capitals} color={capitals.length > 0 && capitals[capitals.length - 1] >= capitals[0] ? '#089981' : '#f23645'} />
        </div>

        <SectionHeader label="⬡ РИСК-МЕТРИКИ" />
        <RiskSection />

        <SectionHeader label="⬡ РАСПРЕДЕЛЕНИЕ" />
        <AllocationSection />

        <SectionHeader label="⬡ АКТИВНОСТЬ СТРАТЕГИЙ" />
        <StrategyActivitySection />

        <SectionHeader label="⬡ AI BRAIN" />
        <AIBrainSection />

        <SectionHeader label="⬡ ПРОГРЕСС ИССЛЕДОВАНИЯ" />
        <ResearchSection />

        <SectionHeader label="⬡ PIPELINE" />
        <PipelineSection />
      </ScrollArea>
    </div>
  )
}
