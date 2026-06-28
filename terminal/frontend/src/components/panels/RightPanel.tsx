import { ScrollArea } from '@mantine/core'
import { useTerminal } from '../../context/TerminalContext'
import { calcRiskMetrics } from '../../utils/indicators'
import type { Strategy, Decision } from '../../api/client'

// ── Helpers ─────────────────────────────────────────────────────────────────

function fmt(n: number | null | undefined, dec = 2): string {
  if (n === null || n === undefined) return '—'
  return n.toLocaleString('ru-RU', { minimumFractionDigits: dec, maximumFractionDigits: dec })
}
function fmtM(n: number | null | undefined): string {
  if (n === null || n === undefined) return '—'
  if (Math.abs(n) >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`
  if (Math.abs(n) >= 1_000) return `${(n / 1_000).toFixed(1)}k`
  return n.toFixed(2)
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

// ── Mini equity sparkline ────────────────────────────────────────────────────

function Sparkline({ capitals }: { capitals: number[] }) {
  if (capitals.length < 2) return <div style={{ height: 60, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
    <span style={{ fontSize: 10, color: 'var(--t-text-3)' }}>No trades</span>
  </div>
  const min = Math.min(...capitals)
  const max = Math.max(...capitals)
  const range = max - min || 1
  const W = 260, H = 60
  const pts = capitals.map((v, i) => ({
    x: (i / (capitals.length - 1)) * W,
    y: H - ((v - min) / range) * (H - 4) - 2,
  }))
  const line = pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ')
  const area = `${line} L${W} ${H} L0 ${H} Z`
  const last = capitals[capitals.length - 1]
  const first = capitals[0]
  const color = last >= first ? '#089981' : '#f23645'
  return (
    <svg width="100%" height={H} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" style={{ display: 'block' }}>
      <path d={area} fill={`${color}20`} />
      <path d={line} stroke={color} strokeWidth="1.5" fill="none" />
    </svg>
  )
}

// ── Strategy Pipeline ────────────────────────────────────────────────────────

const PIPELINE_STAGES = ['Registry', 'Research', 'Knowledge', 'Validation', 'Paper', 'Sandbox', 'Live']

function StrategyPipeline() {
  const { status } = useTerminal()
  const stage = !status ? 0
    : status.candidates.approved_for_paper > 0 ? 4
    : status.research.visual_backtest_reports > 0 ? 3
    : status.research.sessions > 0 ? 2
    : status.hypotheses.tested > 0 ? 1 : 0

  return (
    <div style={{ padding: '8px 10px 10px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'nowrap', overflowX: 'auto' }}>
        {PIPELINE_STAGES.map((s, i) => {
          const isActive = i === stage
          const isDone   = i < stage
          return (
            <div key={s} style={{ display: 'flex', alignItems: 'center', flexShrink: 0 }}>
              <div style={{
                padding: '2px 5px',
                borderRadius: 2,
                fontSize: 8,
                fontFamily: 'var(--t-font-mono)',
                fontWeight: 700,
                letterSpacing: 0.5,
                background: isActive ? 'var(--t-accent-soft)' : isDone ? 'var(--t-green-soft)' : 'var(--t-elevated)',
                color: isActive ? 'var(--t-accent)' : isDone ? 'var(--t-green)' : 'var(--t-text-3)',
                border: `1px solid ${isActive ? 'var(--t-accent)' : isDone ? 'var(--t-green)' : 'var(--t-border)'}`,
                whiteSpace: 'nowrap',
              }}>
                {isDone && '✓ '}{s}
              </div>
              {i < PIPELINE_STAGES.length - 1 && (
                <div style={{ fontSize: 8, color: 'var(--t-text-3)', margin: '0 1px' }}>▶</div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ── AI Brain ─────────────────────────────────────────────────────────────────

const REGIME_MAP: Record<string, string> = {
  bb: 'Ranging / Consolidation',
  squeeze: 'Ranging / Consolidation',
  dual_ma: 'Trending / Momentum',
  trend: 'Trending / Momentum',
  rsi: 'Mean-Reversion',
  oversold: 'Mean-Reversion',
  breakout: 'Breakout',
}

function inferRegime(hypId: string): string {
  const id = hypId.toLowerCase()
  for (const [key, val] of Object.entries(REGIME_MAP)) {
    if (id.includes(key)) return val
  }
  return 'Unknown'
}

function AIBrainSection() {
  const { currentSummary, decisions, status } = useTerminal()
  const lastDecision = decisions[0]
  const hyp = currentSummary?.hypothesis_id ?? '—'
  const regime = currentSummary ? inferRegime(currentSummary.hypothesis_id) : '—'
  const confidence = currentSummary?.win_rate != null ? `${(currentSummary.win_rate * 100).toFixed(1)}%` : '—'
  const instrument = currentSummary ? `${currentSummary.ticker} · ${currentSummary.period} · ${currentSummary.timeframe.toUpperCase()}` : '—'

  const decColor = (type: string) => {
    switch (type) {
      case 'APPROVE': return 'var(--t-green)'
      case 'REJECT':
      case 'ARCHIVE': return 'var(--t-red)'
      case 'REQUEST_MORE_EVIDENCE': return 'var(--t-amber)'
      default: return 'var(--t-text-2)'
    }
  }

  const nextAction = (type: string) => {
    switch (type) {
      case 'APPROVE': return '→ Deploy to Paper Trading'
      case 'REJECT': return '→ Archive and close'
      case 'ARCHIVE': return '→ Finalize archive'
      case 'REQUEST_MORE_EVIDENCE': return '→ Collect more data'
      case 'MONITOR': return '→ Continue monitoring'
      default: return '→ Awaiting decision'
    }
  }

  return (
    <div style={{ padding: '8px 10px 10px' }}>
      {[
        { label: 'Hypothesis', value: hyp.length > 20 ? `${hyp.slice(0, 18)}…` : hyp },
        { label: 'Regime', value: regime },
        { label: 'Confidence', value: confidence },
        { label: 'Instrument', value: instrument },
        { label: 'Active Agents', value: status ? 'Research Engine · Chief Sci' : '—' },
      ].map(r => <KpiRow key={r.label} label={r.label} value={r.value} />)}

      {lastDecision && (
        <>
          <div style={{ marginTop: 6, marginBottom: 4, height: 1, background: 'var(--t-border)' }} />
          <div style={{ fontSize: 9, color: 'var(--t-text-3)', marginBottom: 3 }}>LAST CHIEF SCIENTIST DECISION</div>
          <div style={{ fontSize: 10, fontWeight: 700, color: decColor(lastDecision.type), fontFamily: 'var(--t-font-mono)', marginBottom: 2 }}>
            {lastDecision.type}
          </div>
          <div style={{ fontSize: 9, color: 'var(--t-text-3)', marginBottom: 5, lineHeight: 1.4, overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' }}>
            {lastDecision.rationale}
          </div>
          <div style={{ fontSize: 9, color: 'var(--t-accent)', fontFamily: 'var(--t-font-mono)' }}>
            {nextAction(lastDecision.type)}
          </div>
        </>
      )}
    </div>
  )
}

// ── Research Progress ─────────────────────────────────────────────────────────

function ResearchProgressSection() {
  const { status } = useTerminal()
  if (!status) return <div style={{ padding: '8px 10px', fontSize: 10, color: 'var(--t-text-3)' }}>Loading…</div>
  const b = status.research_budget
  const pct = b.total > 0 ? (b.used / b.total) * 100 : 0
  const stage = status.candidates.approved_for_paper > 0 ? 'Paper Trading'
    : status.research.visual_backtest_reports > 0 ? 'Validation'
    : status.research.sessions > 0 ? 'Research'
    : 'Discovery'

  return (
    <div style={{ padding: '8px 10px 10px' }}>
      <KpiRow label="Campaign" value="v1 · Active" />
      <KpiRow label="Stage" value={stage} color="var(--t-cyan)" />
      <KpiRow label="Sessions" value={String(status.research.sessions)} />
      <KpiRow label="Findings" value={String(status.research.total_findings)} />
      <KpiRow label="Knowledge Facts" value={`${status.knowledge_base.snapshots} snapshots`} />
      <div style={{ marginTop: 6, marginBottom: 3 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
          <span style={{ fontSize: 9, color: 'var(--t-text-3)' }}>BUDGET USED</span>
          <span style={{ fontSize: 9, color: 'var(--t-text-2)', fontFamily: 'var(--t-font-mono)' }}>
            {b.used} / {b.total}
          </span>
        </div>
        <div style={{ height: 4, background: 'var(--t-elevated)', borderRadius: 2 }}>
          <div style={{
            height: '100%', borderRadius: 2,
            width: `${Math.min(pct, 100)}%`,
            background: pct > 80 ? 'var(--t-red)' : pct > 50 ? 'var(--t-amber)' : 'var(--t-accent)',
          }} />
        </div>
      </div>
    </div>
  )
}

// ── Portfolio section ─────────────────────────────────────────────────────────

function PortfolioSection() {
  const { paper, currentSummary, trades } = useTerminal()

  if (paper) {
    const pnlColor = paper.total_pnl >= 0 ? 'var(--t-green)' : 'var(--t-red)'
    return (
      <div style={{ padding: '8px 10px 10px' }}>
        <KpiRow label="Initial Capital" value={`₽ ${fmtM(paper.initial_capital)}`} />
        <KpiRow label="Current Capital" value={`₽ ${fmtM(paper.current_capital)}`} color="var(--t-text)" />
        <KpiRow label="Total PnL" value={`${paper.total_pnl >= 0 ? '+' : ''}₽ ${fmtM(paper.total_pnl)}`} color={pnlColor} />
        <KpiRow label="Return" value={`${paper.total_return_pct >= 0 ? '+' : ''}${fmt(paper.total_return_pct)}%`} color={pnlColor} />
        <KpiRow label="Free Cash" value={`₽ ${fmtM(paper.current_capital * (1 - paper.exposure_pct / 100))}`} />
        <KpiRow label="Exposure" value={`${fmt(paper.exposure_pct)}%`} color="var(--t-cyan)" />
        <KpiRow label="Positions" value={String(paper.open_positions)} />
        <KpiRow label="Win Rate" value={`${fmt(paper.win_rate * 100)}%`} color={paper.win_rate >= 0.5 ? 'var(--t-green)' : 'var(--t-red)'} />
        {paper.note && (
          <div style={{ marginTop: 6, padding: '4px 6px', background: 'var(--t-amber-soft)', borderRadius: 3, fontSize: 9, color: 'var(--t-amber)', lineHeight: 1.4 }}>
            {paper.note}
          </div>
        )}
      </div>
    )
  }

  // Fallback: show backtest report metrics
  const r = currentSummary
  if (!r) return <div style={{ padding: '8px 10px', fontSize: 10, color: 'var(--t-text-3)' }}>Select a report</div>
  const initCap = (r.metrics as any)?.initial_capital ?? 1_000_000
  const finalCap = trades.length > 0 ? (trades[trades.length - 1]?.capital_after ?? initCap) : initCap
  const pnl = finalCap - initCap
  const retPct = ((finalCap - initCap) / initCap) * 100
  const pnlColor = pnl >= 0 ? 'var(--t-green)' : 'var(--t-red)'
  return (
    <div style={{ padding: '8px 10px 10px' }}>
      <div style={{ fontSize: 9, color: 'var(--t-amber)', marginBottom: 6, fontFamily: 'var(--t-font-mono)' }}>PAPER STANDBY — BACKTEST DATA</div>
      <KpiRow label="Initial Capital" value={`₽ ${fmtM(initCap)}`} />
      <KpiRow label="Final Capital" value={`₽ ${fmtM(finalCap)}`} color="var(--t-text)" />
      <KpiRow label="Total PnL" value={`${pnl >= 0 ? '+' : ''}₽ ${fmtM(pnl)}`} color={pnlColor} />
      <KpiRow label="Return" value={`${retPct >= 0 ? '+' : ''}${fmt(retPct)}%`} color={pnlColor} />
      <KpiRow label="Trades" value={String(r.num_trades)} />
      <KpiRow label="Win Rate" value={`${(r.win_rate * 100).toFixed(1)}%`} color={r.win_rate >= 0.5 ? 'var(--t-green)' : 'var(--t-red)'} />
      <KpiRow label="Profit Factor" value={r.profit_factor === Infinity ? '∞' : fmt(r.profit_factor)} />
      <KpiRow label="Max Drawdown" value={`-${fmt(r.max_drawdown_pct)}%`} color="var(--t-red)" />
    </div>
  )
}

// ── Risk Metrics section ──────────────────────────────────────────────────────

function RiskMetricsSection() {
  const { trades, currentSummary } = useTerminal()
  const initCap = (currentSummary?.metrics as any)?.initial_capital ?? 1_000_000
  const risk = calcRiskMetrics(trades, initCap)
  return (
    <div style={{ padding: '8px 10px 10px' }}>
      <KpiRow label="Max DD" value={`-${risk.maxDD}%`} color="var(--t-red)" />
      <KpiRow label="Current DD" value={risk.currentDD > 0 ? `-${risk.currentDD}%` : '0.00%'} color={risk.currentDD > 5 ? 'var(--t-amber)' : 'var(--t-text)'} />
      <KpiRow label="Sharpe" value={String(risk.sharpe)} color={risk.sharpe >= 1 ? 'var(--t-green)' : 'var(--t-text)'} />
      <KpiRow label="Sortino" value={String(risk.sortino)} color={risk.sortino >= 1 ? 'var(--t-green)' : 'var(--t-text)'} />
      <KpiRow label="Calmar" value={String(risk.calmar)} color={risk.calmar >= 0.5 ? 'var(--t-green)' : 'var(--t-text)'} />
      <KpiRow label="VaR 95%" value={`-${risk.var95}%`} color="var(--t-red)" />
    </div>
  )
}

// ── Strategy cards (for strategy tab) ────────────────────────────────────────

function StrategyCard({ s }: { s: Strategy }) {
  const statusColor = s.status === 'RESEARCH_PASS' ? 'var(--t-green)' : s.status === 'RESEARCH_FAIL' ? 'var(--t-red)' : 'var(--t-accent)'
  return (
    <div style={{ margin: '0 8px 6px', padding: '8px', background: 'var(--t-elevated)', borderRadius: 4, border: '1px solid var(--t-border)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
        <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--t-text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1, marginRight: 6 }}>
          {s.strategy_name ?? s.template_id}
        </span>
        <span style={{ fontSize: 9, fontFamily: 'var(--t-font-mono)', color: statusColor, whiteSpace: 'nowrap' }}>
          {s.status}
        </span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2px 8px' }}>
        {[
          { k: 'Score', v: s.research_score != null ? fmt(s.research_score, 0) : '—' },
          { k: 'WR', v: s.win_rate != null ? `${(s.win_rate * 100).toFixed(0)}%` : '—' },
          { k: 'PF', v: s.profit_factor != null ? fmt(s.profit_factor) : '—' },
          { k: 'Return', v: s.total_return_pct != null ? `${s.total_return_pct >= 0 ? '+' : ''}${fmt(s.total_return_pct)}%` : '—' },
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

// ── Decision card (for scientist tab) ────────────────────────────────────────

function DecisionItem({ d }: { d: Decision }) {
  const color = d.type === 'APPROVE' ? 'var(--t-green)' : d.type === 'REJECT' || d.type === 'ARCHIVE' ? 'var(--t-red)' : 'var(--t-amber)'
  return (
    <div style={{ margin: '0 8px 6px', padding: '8px', background: 'var(--t-elevated)', borderRadius: 4, borderLeft: `3px solid ${color}` }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
        <span style={{ fontSize: 10, fontWeight: 700, color, fontFamily: 'var(--t-font-mono)' }}>{d.type}</span>
        <span style={{ fontSize: 9, color: 'var(--t-text-3)' }}>{new Date(d.timestamp).toLocaleDateString('ru')}</span>
      </div>
      <div style={{ fontSize: 9, color: 'var(--t-text-2)', marginBottom: 3, fontFamily: 'var(--t-font-mono)' }}>
        {d.hypothesis_title}
      </div>
      <div style={{ fontSize: 9, color: 'var(--t-text-3)', lineHeight: 1.4, overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' }}>
        {d.rationale}
      </div>
    </div>
  )
}

// ── Root RightPanel ───────────────────────────────────────────────────────────

export default function RightPanel() {
  const { activeTab, trades, strategies, decisions, knowledgeGraph, selectedNode } = useTerminal()

  const capitals = trades.map(t => t.capital_after)

  if (activeTab === 'strategy') {
    return (
      <div style={{ height: '100%', background: 'var(--t-bg)', borderLeft: '1px solid var(--t-border)', display: 'flex', flexDirection: 'column' }}>
        <SectionHeader label="⬡ STRATEGY VAULT" />
        <ScrollArea style={{ flex: 1 }} scrollbarSize={3}>
          {strategies.length === 0 && (
            <div style={{ padding: '12px 10px', fontSize: 10, color: 'var(--t-text-3)' }}>No strategies indexed.</div>
          )}
          {strategies.map(s => <StrategyCard key={s.id} s={s} />)}
        </ScrollArea>
      </div>
    )
  }

  if (activeTab === 'scientist') {
    return (
      <div style={{ height: '100%', background: 'var(--t-bg)', borderLeft: '1px solid var(--t-border)', display: 'flex', flexDirection: 'column' }}>
        <SectionHeader label="⬡ CHIEF SCIENTIST" />
        <ScrollArea style={{ flex: 1 }} scrollbarSize={3}>
          {decisions.length === 0 && (
            <div style={{ padding: '12px 10px', fontSize: 10, color: 'var(--t-text-3)' }}>No decisions recorded.</div>
          )}
          {decisions.map(d => <DecisionItem key={d.id} d={d} />)}
        </ScrollArea>
      </div>
    )
  }

  if (activeTab === 'knowledge') {
    const node = knowledgeGraph?.nodes.find(n => n.id === selectedNode)
    return (
      <div style={{ height: '100%', background: 'var(--t-bg)', borderLeft: '1px solid var(--t-border)', display: 'flex', flexDirection: 'column' }}>
        <SectionHeader label="⬡ KNOWLEDGE NODE" />
        {node ? (
          <div style={{ padding: '10px' }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--t-text)', marginBottom: 6 }}>{node.label}</div>
            <div style={{ marginBottom: 4 }}>
              <span className="t-chip" style={{ fontSize: 8 }}>{node.type}</span>
            </div>
            <div style={{ fontSize: 10, color: 'var(--t-text-2)', lineHeight: 1.5 }}>{node.description}</div>
          </div>
        ) : (
          <div style={{ padding: '12px 10px', fontSize: 10, color: 'var(--t-text-3)' }}>
            Click a node on the graph to see details.
          </div>
        )}
      </div>
    )
  }

  // Default: terminal tab — full portfolio/risk/AI Brain/pipeline
  return (
    <div style={{ height: '100%', background: 'var(--t-bg)', borderLeft: '1px solid var(--t-border)', display: 'flex', flexDirection: 'column' }}>
      <ScrollArea style={{ flex: 1 }} scrollbarSize={3}>
        <SectionHeader label="⬡ PAPER PORTFOLIO" />
        <PortfolioSection />

        <SectionHeader label="⬡ EQUITY CURVE" />
        <div style={{ padding: '4px 10px 8px' }}>
          <Sparkline capitals={capitals} />
        </div>

        <SectionHeader label="⬡ RISK METRICS" />
        <RiskMetricsSection />

        <SectionHeader label="⬡ AI BRAIN" />
        <AIBrainSection />

        <SectionHeader label="⬡ RESEARCH PROGRESS" />
        <ResearchProgressSection />

        <SectionHeader label="⬡ STRATEGY PIPELINE" />
        <StrategyPipeline />
      </ScrollArea>
    </div>
  )
}
