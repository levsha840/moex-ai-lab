import { useQuery } from '@tanstack/react-query'
import { fetchStatus, fetchActivity, fetchReports } from '../api/client'
import type { LabStatus, ActivityEvent, ReportSummary } from '../api/client'
import { Loader, Center, ScrollArea } from '@mantine/core'
import {
  IconActivity, IconFlask, IconDatabase, IconTrophy,
  IconAlertTriangle, IconCheck, IconX, IconMinus,
} from '@tabler/icons-react'
import StatusBadge from '../components/shared/StatusBadge'

/* ── Row helpers ─────────────────────────────────────────── */
function KpiRow({ status }: { status: LabStatus }) {
  const budget = status.research_budget
  const pct = budget.total > 0 ? budget.used / budget.total : 0

  return (
    <div className="t-kpi-grid" style={{ gridTemplateColumns: 'repeat(7, 1fr)' }}>
      {[
        { label: 'Hypotheses', val: status.hypotheses.registered, sub: `${status.hypotheses.tested} tested`, col: 'var(--t-cyan)' },
        { label: 'Alpha Passed', val: status.hypotheses.passed_alpha_gate, sub: `${status.hypotheses.failed} failed`, col: status.hypotheses.passed_alpha_gate > 0 ? 'var(--t-green)' : 'var(--t-text-2)' },
        { label: 'Sessions', val: status.research.sessions, sub: `${status.research.total_findings} findings`, col: 'var(--t-text)' },
        { label: 'Datasets', val: status.datasets.total, sub: 'P1 Universe', col: 'var(--t-text)' },
        { label: 'VB Reports', val: status.research.visual_backtest_reports, sub: 'Visual Backtests', col: 'var(--t-accent)' },
        { label: 'Budget Used', val: `${budget.used}/${budget.total}`, sub: `${budget.remaining} remaining`, col: pct > 0.8 ? 'var(--t-red)' : pct > 0.5 ? 'var(--t-amber)' : 'var(--t-text)' },
        { label: 'Paper Status', val: status.paper_trading.enabled ? 'ACTIVE' : 'STANDBY', sub: 'No positions yet', col: status.paper_trading.enabled ? 'var(--t-green)' : 'var(--t-amber)' },
      ].map(k => (
        <div key={k.label} className="t-kpi-cell">
          <div className="t-kpi-label">{k.label}</div>
          <div className="t-kpi-val" style={{ color: k.col }}>{k.val}</div>
          <div className="t-kpi-sub">{k.sub}</div>
        </div>
      ))}
    </div>
  )
}

function AlphaPipeline({ status }: { status: LabStatus }) {
  const stages = [
    { label: 'Registry',     count: status.hypotheses.registered, cls: 'cyan' },
    { label: 'In Research',  count: status.hypotheses.tested,     cls: 'blue' },
    { label: 'Alpha Gate',   count: status.hypotheses.tested,     cls: 'amber' },
    { label: 'Passed',       count: status.hypotheses.passed_alpha_gate, cls: 'green' },
    { label: 'Paper',        count: status.candidates.approved_for_paper, cls: status.candidates.approved_for_paper > 0 ? 'green' : 'gray' },
  ]
  return (
    <div style={{ display: 'flex', gap: 0, flex: 1 }}>
      {stages.map((s, i) => (
        <div key={s.label} style={{ display: 'flex', alignItems: 'center', flex: 1 }}>
          <div style={{
            flex: 1, background: 'var(--t-elevated)', border: '1px solid var(--t-border)',
            padding: '8px 12px', textAlign: 'center',
          }}>
            <div style={{ fontSize: 9, color: 'var(--t-text-3)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 3 }}>{s.label}</div>
            <div style={{ fontSize: 20, fontWeight: 700, color: `var(--t-${s.cls})`, fontFamily: 'var(--t-font-mono)' }}>{s.count}</div>
          </div>
          {i < stages.length - 1 && (
            <div style={{ fontSize: 16, color: 'var(--t-text-3)', padding: '0 2px', flexShrink: 0 }}>▶</div>
          )}
        </div>
      ))}
    </div>
  )
}

function BestStrategies({ reports }: { reports: ReportSummary[] }) {
  const sorted = [...reports].sort((a, b) => b.total_return_pct - a.total_return_pct).slice(0, 3)
  return (
    <div>
      {sorted.length === 0 && (
        <div style={{ color: 'var(--t-text-3)', fontSize: 11, padding: '10px 12px' }}>Run visual backtests to see top strategies</div>
      )}
      {sorted.map((r, i) => (
        <div key={r.report_id} style={{ padding: '8px 12px', borderBottom: '1px solid var(--t-border-dim)', display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: 13, fontWeight: 700, color: i === 0 ? 'var(--t-amber)' : 'var(--t-text-3)', minWidth: 16 }}>#{i + 1}</span>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 11, color: 'var(--t-text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {r.hypothesis_id}
            </div>
            <div style={{ fontSize: 10, color: 'var(--t-text-2)' }}>{r.ticker} · {r.period} · {r.timeframe}</div>
          </div>
          <div style={{ textAlign: 'right', flexShrink: 0 }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: r.total_return_pct >= 0 ? 'var(--t-green)' : 'var(--t-red)', fontFamily: 'var(--t-font-mono)' }}>
              {r.total_return_pct >= 0 ? '+' : ''}{r.total_return_pct.toFixed(2)}%
            </div>
            <div style={{ fontSize: 10, color: 'var(--t-text-2)', fontFamily: 'var(--t-font-mono)' }}>
              PF {r.profit_factor === Infinity ? '∞' : r.profit_factor.toFixed(2)} · WR {(r.win_rate * 100).toFixed(0)}%
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

function SystemHealth() {
  const rows = [
    { name: 'Research Service',    ok: true,  tag: 'ONLINE' },
    { name: 'Visual Backtest',     ok: true,  tag: 'ONLINE' },
    { name: 'Campaign Runner',     ok: true,  tag: 'ONLINE' },
    { name: 'Knowledge Base',      ok: true,  tag: 'ONLINE' },
    { name: 'Hypothesis Registry', ok: true,  tag: 'ONLINE' },
    { name: 'Paper Trading',       ok: null,  tag: 'STANDBY' },
    { name: 'T-Invest API',        ok: false, tag: 'BLOCKED' },
    { name: 'Real Trading',        ok: false, tag: 'BLOCKED' },
  ]
  return (
    <>
      {rows.map(r => (
        <div key={r.name} className="t-metric">
          <span className="t-metric-label">{r.name}</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            {r.ok === true && <><span className="t-dot green pulse" /><span style={{ fontSize: 10, color: 'var(--t-green)' }}>{r.tag}</span></>}
            {r.ok === null && <><span className="t-dot amber" /><span style={{ fontSize: 10, color: 'var(--t-amber)' }}>{r.tag}</span></>}
            {r.ok === false && <><span className="t-dot red" /><span style={{ fontSize: 10, color: 'var(--t-red)' }}>{r.tag}</span></>}
          </div>
        </div>
      ))}
    </>
  )
}

function ActivityFeed({ events }: { events: ActivityEvent[] }) {
  const icon = (type: string, status: string) => {
    if (status === 'pass' || status === 'completed') return <IconCheck size={10} color="var(--t-green)" />
    if (status === 'fail') return <IconX size={10} color="var(--t-red)" />
    return <IconMinus size={10} color="var(--t-text-3)" />
  }
  return (
    <ScrollArea h="100%" scrollbarSize={3}>
      {events.slice(0, 40).map((e, i) => (
        <div key={i} style={{ display: 'flex', gap: 8, padding: '6px 10px', borderBottom: '1px solid var(--t-border-dim)', alignItems: 'flex-start' }}>
          <span style={{ marginTop: 1, flexShrink: 0 }}>{icon(e.type, e.status)}</span>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 11, color: 'var(--t-text)', lineHeight: 1.3 }}>{e.title}</div>
            <div style={{ fontSize: 10, color: 'var(--t-text-2)', marginTop: 1 }}>{e.detail}</div>
          </div>
          <div style={{ fontSize: 10, color: 'var(--t-text-3)', whiteSpace: 'nowrap', flexShrink: 0 }}>
            {e.timestamp ? new Date(e.timestamp).toLocaleDateString('ru-RU', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : ''}
          </div>
        </div>
      ))}
    </ScrollArea>
  )
}

export default function Dashboard() {
  const { data: status, isLoading: ls } = useQuery({ queryKey: ['status'], queryFn: fetchStatus, refetchInterval: 60_000 })
  const { data: activity = [], isLoading: la } = useQuery({ queryKey: ['activity'], queryFn: fetchActivity, refetchInterval: 60_000 })
  const { data: reports = [] } = useQuery({ queryKey: ['reports'], queryFn: fetchReports })

  if (ls) return <Center h="100%"><Loader /></Center>
  if (!status) return null

  const budget = status.research_budget
  const budgetPct = budget.total > 0 ? budget.used / budget.total : 0

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden', background: 'var(--t-bg)' }}>
      {/* KPI row */}
      <KpiRow status={status} />

      {/* Main grid */}
      <div style={{ flex: 1, display: 'grid', gridTemplateColumns: '1fr 1fr 260px', gridTemplateRows: 'auto 1fr', gap: 1, background: 'var(--t-border)', overflow: 'hidden', marginTop: 1 }}>

        {/* Alpha Pipeline */}
        <div style={{ background: 'var(--t-bg)', gridColumn: '1 / 3', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div className="t-section-title">⬡ Alpha Pipeline</div>
          <div style={{ padding: 10, flex: 1 }}>
            <AlphaPipeline status={status} />
          </div>
        </div>

        {/* System Health */}
        <div style={{ background: 'var(--t-bg)', gridRow: '1 / 3', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div className="t-section-title">⬡ System Status</div>
          <SystemHealth />
          <div className="t-section-title" style={{ marginTop: 0 }}>⬡ Research Budget</div>
          <div style={{ padding: '10px 12px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
              <span style={{ fontSize: 10, color: 'var(--t-text-2)' }}>Used</span>
              <span style={{ fontSize: 11, color: 'var(--t-text)', fontFamily: 'var(--t-font-mono)' }}>{budget.used} / {budget.total}</span>
            </div>
            <div style={{ height: 4, background: 'var(--t-elevated)', borderRadius: 2, overflow: 'hidden' }}>
              <div style={{
                height: '100%', width: `${budgetPct * 100}%`,
                background: budgetPct > 0.8 ? 'var(--t-red)' : budgetPct > 0.5 ? 'var(--t-amber)' : 'var(--t-accent)',
                borderRadius: 2, transition: 'width 0.3s',
              }} />
            </div>
            <div style={{ fontSize: 10, color: 'var(--t-text-3)', marginTop: 4 }}>{budget.remaining} runs remaining</div>
          </div>
        </div>

        {/* Best Strategies */}
        <div style={{ background: 'var(--t-bg)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div className="t-section-title">⬡ Top Strategies (VB)</div>
          <BestStrategies reports={reports} />
        </div>

        {/* Activity */}
        <div style={{ background: 'var(--t-bg)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div className="t-section-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span>⬡ Activity Log</span>
            {la && <span style={{ fontSize: 9, color: 'var(--t-text-3)' }}>loading...</span>}
          </div>
          <div style={{ flex: 1, overflow: 'hidden' }}>
            <ActivityFeed events={activity} />
          </div>
        </div>
      </div>
    </div>
  )
}
