import { ScrollArea, Loader, Center } from '@mantine/core'
import { useQuery } from '@tanstack/react-query'
import { IconCheck, IconX, IconHelp, IconArchive } from '@tabler/icons-react'
import { fetchDecisions, fetchScientistStats } from '../api/client'
import StatusBadge from '../components/shared/StatusBadge'

const DECISION_META: Record<string, { cls: string; icon: typeof IconCheck }> = {
  APPROVE:               { cls: 'green', icon: IconCheck   },
  REJECT:                { cls: 'red',   icon: IconX       },
  REQUEST_MORE_EVIDENCE: { cls: 'amber', icon: IconHelp    },
  ARCHIVE:               { cls: 'gray',  icon: IconArchive },
  MONITOR:               { cls: 'blue',  icon: IconHelp    },
}

export default function ChiefScientist() {
  const { data: decisions = [], isLoading } = useQuery({ queryKey: ['decisions'], queryFn: fetchDecisions })
  const { data: stats } = useQuery({ queryKey: ['scientist-stats'], queryFn: fetchScientistStats })

  const byType = (decisions as any[]).reduce((acc: Record<string, number>, d: any) => {
    acc[d.type] = (acc[d.type] ?? 0) + 1
    return acc
  }, {})

  if (isLoading) return <Center h="100%"><Loader /></Center>

  const COLOR_VAR: Record<string, string> = {
    green: 'var(--t-green)', red: 'var(--t-red)', amber: 'var(--t-amber)',
    blue: 'var(--t-accent)', gray: 'var(--t-text-3)',
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden', background: 'var(--t-bg)' }}>
      {/* Toolbar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, height: 38, padding: '0 12px', background: 'var(--t-panel)', borderBottom: '1px solid var(--t-border)', flexShrink: 0 }}>
        <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--t-text-2)', textTransform: 'uppercase', letterSpacing: 1 }}>CHIEF SCIENTIST</span>
        <div style={{ width: 1, height: 16, background: 'var(--t-border)' }} />
        <span style={{ fontSize: 11, fontFamily: 'var(--t-font-mono)', color: 'var(--t-text)' }}>{decisions.length} decisions</span>
        <div style={{ flex: 1 }} />
        {Object.entries(DECISION_META).map(([type, meta]) => {
          const count = byType[type] ?? 0
          if (!count) return null
          return <span key={type} className={`t-chip ${meta.cls}`}>{type.replace(/_/g, ' ')} {count}</span>
        })}
      </div>

      {/* Two-panel layout */}
      <div style={{ flex: 1, display: 'grid', gridTemplateColumns: '220px 1fr', gap: 1, background: 'var(--t-border)', overflow: 'hidden' }}>
        {/* Left: summary */}
        <div style={{ background: 'var(--t-bg)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div className="t-section-title">⬡ Decision Summary</div>
          {Object.entries(DECISION_META).map(([type, meta]) => {
            const count = byType[type] ?? 0
            const total = decisions.length || 1
            const pct = count / total * 100
            return (
              <div key={type} style={{ padding: '8px 12px', borderBottom: '1px solid var(--t-border-dim)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                  <span style={{ fontSize: 10, color: 'var(--t-text-2)' }}>{type.replace(/_/g, ' ')}</span>
                  <span style={{ fontSize: 11, fontFamily: 'var(--t-font-mono)', color: COLOR_VAR[meta.cls] ?? 'var(--t-text)' }}>{count}</span>
                </div>
                <div style={{ height: 3, background: 'var(--t-elevated)', borderRadius: 2 }}>
                  <div style={{ height: '100%', width: `${pct}%`, background: COLOR_VAR[meta.cls] ?? 'var(--t-accent)', borderRadius: 2 }} />
                </div>
              </div>
            )
          })}

          <div className="t-section-title" style={{ marginTop: 8 }}>⬡ AI Persona</div>
          <div style={{ padding: '10px 12px', fontSize: 11, color: 'var(--t-text-2)', lineHeight: 1.6 }}>
            Chief Scientist evaluates research findings against Alpha Library criteria.
            Hypotheses with pass_rate ≥ 40% proceed to Visual Backtest.
            Decisions are final — no human override.
          </div>
        </div>

        {/* Right: decision log */}
        <div style={{ background: 'var(--t-bg)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div className="t-section-title">⬡ Decision Log</div>
          <ScrollArea style={{ flex: 1 }} scrollbarSize={3}>
            {decisions.length === 0 && (
              <Center h={200} style={{ color: 'var(--t-text-3)', fontSize: 11 }}>
                No decisions yet — run a research campaign
              </Center>
            )}
            {(decisions as any[]).map((d, i) => {
              const meta = DECISION_META[d.type] ?? DECISION_META['MONITOR']
              const Icon = meta.icon
              const accentColor = COLOR_VAR[meta.cls] ?? 'var(--t-text-2)'
              return (
                <div key={i} style={{ padding: '10px 12px', borderBottom: '1px solid var(--t-border-dim)', borderLeft: `3px solid ${accentColor}`, marginLeft: 0 }}
                  onMouseEnter={e => (e.currentTarget.style.background = 'var(--t-hover)')}
                  onMouseLeave={e => (e.currentTarget.style.background = '')}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                    <Icon size={11} color={accentColor} />
                    <StatusBadge status={d.type} />
                    <span style={{ fontSize: 11, color: 'var(--t-text)', fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 400 }}>
                      {d.hypothesis_title || d.hypothesis_id}
                    </span>
                    <div style={{ flex: 1 }} />
                    <span style={{ fontSize: 10, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)', whiteSpace: 'nowrap' }}>
                      {d.timestamp ? new Date(d.timestamp).toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' }) : ''}
                    </span>
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--t-text-2)', lineHeight: 1.5 }}>{d.rationale}</div>
                  {d.stats?.pass_rate !== null && d.stats?.pass_rate !== undefined && (
                    <div style={{ marginTop: 6, display: 'flex', gap: 12 }}>
                      <span style={{ fontSize: 10, color: 'var(--t-text-3)' }}>
                        pass_rate: <span style={{ color: 'var(--t-cyan)', fontFamily: 'var(--t-font-mono)' }}>{(d.stats.pass_rate * 100).toFixed(1)}%</span>
                      </span>
                      {d.stats.windows_total && (
                        <span style={{ fontSize: 10, color: 'var(--t-text-3)' }}>
                          windows: <span style={{ fontFamily: 'var(--t-font-mono)', color: 'var(--t-text-2)' }}>{d.stats.windows_total}</span>
                        </span>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </ScrollArea>
        </div>
      </div>
    </div>
  )
}
