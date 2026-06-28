import { useState, useMemo } from 'react'
import { IconFileText, IconBook, IconBulb, IconSearch } from '@tabler/icons-react'
import { useTerminal } from '../context/TerminalContext'
import { metricsFromReport } from '../utils/portfolio'
import type { Report, ActivityEvent, Decision } from '../api/client'
import { TH, TD, fmtF } from '../styles/tokens'

function fmtDt(s: string | undefined): string {
  if (!s) return '—'
  try {
    const d = new Date(s)
    return `${String(d.getDate()).padStart(2,'0')}.${String(d.getMonth()+1).padStart(2,'0')}.${String(d.getFullYear()).slice(2)} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`
  } catch { return s.slice(0, 10) }
}

function TabBtn({ active, onClick, icon, label }: { active: boolean; onClick: () => void; icon: React.ReactNode; label: string }) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: '0 14px', height: '100%', border: 'none', cursor: 'pointer',
        background: 'none', display: 'flex', alignItems: 'center', gap: 5,
        borderBottom: active ? '2px solid var(--t-accent)' : '2px solid transparent',
        color: active ? 'var(--t-accent)' : 'var(--t-text-3)',
        fontSize: 10, fontFamily: 'var(--t-font-mono)', fontWeight: active ? 700 : 400,
      }}
    >
      {icon}
      {label}
    </button>
  )
}

// ── Reports Tab ───────────────────────────────────────────────────────────────
function ReportsTab() {
  const { allFullReports, reports, setSelectedIdx, setActiveTab } = useTerminal()
  const [search, setSearch] = useState('')
  const [sortKey, setSortKey] = useState<'return' | 'dd' | 'wr' | 'pf' | 'trades'>('return')
  const [sortDir, setSortDir] = useState<1 | -1>(-1)

  const rows = useMemo(() => {
    return allFullReports.map((r, i) => {
      let m = null
      try { m = metricsFromReport(r) } catch {}
      return { report: r, summary: reports[i], metrics: m, idx: i }
    }).filter(row => {
      if (!search) return true
      const q = search.toLowerCase()
      return row.report.ticker?.toLowerCase().includes(q) ||
             row.report.hypothesis_id?.toLowerCase().includes(q)
    }).sort((a, b) => {
      const ma = a.metrics, mb = b.metrics
      if (!ma && !mb) return 0
      if (!ma) return 1
      if (!mb) return -1
      const vals: Record<string, [number, number]> = {
        return: [ma.pnlPct ?? 0, mb.pnlPct ?? 0],
        dd:     [ma.maxDrawdown  ?? 0, mb.maxDrawdown  ?? 0],
        wr:     [ma.winRate      ?? 0, mb.winRate      ?? 0],
        pf:     [ma.profitFactor ?? 0, mb.profitFactor ?? 0],
        trades: [ma.numTrades    ?? 0, mb.numTrades    ?? 0],
      }
      const [av, bv] = vals[sortKey]
      return (av - bv) * sortDir
    })
  }, [allFullReports, reports, search, sortKey, sortDir])

  function toggleSort(key: typeof sortKey) {
    if (sortKey === key) setSortDir(d => d === 1 ? -1 : 1)
    else { setSortKey(key); setSortDir(-1) }
  }

  function SortTH({ label, k }: { label: string; k: typeof sortKey }) {
    const active = sortKey === k
    return (
      <th
        onClick={() => toggleSort(k)}
        style={{ ...TH, textAlign: 'right', cursor: 'pointer', color: active ? 'var(--t-accent)' : 'var(--t-text-3)', userSelect: 'none' }}
      >
        {label} {active ? (sortDir === -1 ? '↓' : '↑') : ''}
      </th>
    )
  }

  if (allFullReports.length === 0) {
    return (
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 12, color: 'var(--t-text-3)' }}>
        <IconFileText size={40} style={{ opacity: 0.15 }} />
        <div style={{ fontSize: 12, fontFamily: 'var(--t-font-mono)' }}>Нет отчётов</div>
        <div style={{ fontSize: 10 }}>Запустите бэктест для генерации отчётов</div>
      </div>
    )
  }

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
      {/* Search */}
      <div style={{ padding: '8px 12px', borderBottom: '1px solid var(--t-border)', background: 'var(--t-panel)', display: 'flex', alignItems: 'center', gap: 8 }}>
        <IconSearch size={11} color="var(--t-text-3)" />
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Поиск по тикеру, стратегии..."
          style={{
            background: 'none', border: 'none', outline: 'none', flex: 1,
            color: 'var(--t-text)', fontSize: 10, fontFamily: 'var(--t-font-mono)',
          }}
        />
        {search && (
          <button onClick={() => setSearch('')} style={{ background: 'none', border: 'none', color: 'var(--t-text-3)', cursor: 'pointer', fontSize: 10 }}>✕</button>
        )}
        <span style={{ fontSize: 9, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)', flexShrink: 0 }}>
          {rows.length} / {allFullReports.length}
        </span>
      </div>

      <div style={{ flex: 1, overflowY: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <th style={TH}>Стратегия</th>
              <th style={TH}>Инструмент</th>
              <th style={TH}>Период</th>
              <th style={TH}>ТФ</th>
              <SortTH label="Доходность" k="return" />
              <SortTH label="Max DD" k="dd" />
              <SortTH label="Win Rate" k="wr" />
              <SortTH label="P/F" k="pf" />
              <SortTH label="Сделок" k="trades" />
              <th style={{ ...TH, textAlign: 'center' }}>Действия</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ report: r, summary: s, metrics: m, idx }) => {
              const name = r.hypothesis_id?.replace('tmpl_h_', '').replace(/_/g, ' ') ?? '—'
              return (
                <tr
                  key={r.report_id ?? idx}
                  style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}
                  onMouseEnter={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.02)')}
                  onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                >
                  <td style={{ ...TD, color: 'var(--t-text)', maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis' }}>{name}</td>
                  <td style={{ ...TD, color: 'var(--t-text)', fontWeight: 700 }}>{r.ticker ?? '—'}</td>
                  <td style={{ ...TD, color: 'var(--t-text-3)' }}>{s?.period ?? '—'}</td>
                  <td style={{ ...TD, color: 'var(--t-text-3)' }}>{s?.timeframe ?? '—'}</td>
                  <td style={{ ...TD, textAlign: 'right', color: m ? (m.pnlPct >= 0 ? 'var(--t-green)' : 'var(--t-red)') : 'var(--t-text-3)' }}>
                    {m ? `${m.pnlPct >= 0 ? '+' : ''}${fmtF(m.pnlPct, 1)}%` : '—'}
                  </td>
                  <td style={{ ...TD, textAlign: 'right', color: m ? 'var(--t-red)' : 'var(--t-text-3)' }}>
                    {m ? `${fmtF(m.maxDrawdown, 1)}%` : '—'}
                  </td>
                  <td style={{ ...TD, textAlign: 'right', color: m ? (m.winRate >= 50 ? 'var(--t-green)' : 'var(--t-text-2)') : 'var(--t-text-3)' }}>
                    {m ? `${fmtF(m.winRate, 1)}%` : '—'}
                  </td>
                  <td style={{ ...TD, textAlign: 'right', color: m ? (m.profitFactor >= 1.5 ? 'var(--t-green)' : m.profitFactor < 1 ? 'var(--t-red)' : 'var(--t-text-2)') : 'var(--t-text-3)' }}>
                    {m ? fmtF(m.profitFactor) : '—'}
                  </td>
                  <td style={{ ...TD, textAlign: 'right', color: 'var(--t-text-3)' }}>{m?.numTrades ?? '—'}</td>
                  <td style={{ ...TD, textAlign: 'center' }}>
                    <button
                      onClick={() => { setSelectedIdx(idx); setActiveTab('terminal') }}
                      style={{ padding: '2px 8px', borderRadius: 3, border: '1px solid var(--t-border)', background: 'var(--t-elevated)', color: 'var(--t-accent)', cursor: 'pointer', fontSize: 9, fontFamily: 'var(--t-font-mono)' }}
                    >
                      Открыть
                    </button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── Journal Tab ───────────────────────────────────────────────────────────────
function JournalTab() {
  const { activity } = useTerminal()

  const sorted = useMemo(() => [...activity].sort((a, b) => {
    const ta = new Date(a.timestamp ?? '').getTime()
    const tb = new Date(b.timestamp ?? '').getTime()
    return tb - ta
  }), [activity])

  if (!activity.length) {
    return (
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 12, color: 'var(--t-text-3)' }}>
        <IconBook size={40} style={{ opacity: 0.15 }} />
        <div style={{ fontSize: 12, fontFamily: 'var(--t-font-mono)' }}>Журнал пуст</div>
        <div style={{ fontSize: 10 }}>События исследовательской лаборатории появятся здесь</div>
      </div>
    )
  }

  const actColor = (type: string) => {
    const t = (type ?? '').toLowerCase()
    if (t.includes('error') || t.includes('fail')) return 'var(--t-red)'
    if (t.includes('pass') || t.includes('success') || t.includes('complet')) return 'var(--t-green)'
    if (t.includes('warn')) return 'var(--t-amber)'
    return 'var(--t-text-3)'
  }

  return (
    <div style={{ flex: 1, overflowY: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <th style={TH}>Время</th>
            <th style={TH}>Тип</th>
            <th style={TH}>Источник</th>
            <th style={TH}>Сообщение</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((ev, i) => (
            <tr key={i} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
              <td style={{ ...TD, color: 'var(--t-text-3)', flexShrink: 0 }}>{fmtDt((ev as any).timestamp)}</td>
              <td style={{ ...TD, color: actColor((ev as any).event_type ?? ''), fontWeight: 600 }}>
                {(ev as any).event_type ?? '—'}
              </td>
              <td style={{ ...TD, color: 'var(--t-text-3)', maxWidth: 140, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {(ev as any).source ?? (ev as any).agent_type ?? '—'}
              </td>
              <td style={{ ...TD, color: 'var(--t-text-2)', maxWidth: 400, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {(ev as any).message ?? (ev as any).description ?? JSON.stringify(ev).slice(0, 80)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ── Decisions Tab ─────────────────────────────────────────────────────────────
function DecisionsTab() {
  const { decisions } = useTerminal()

  if (!decisions.length) {
    return (
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 12, color: 'var(--t-text-3)' }}>
        <IconBulb size={40} style={{ opacity: 0.15 }} />
        <div style={{ fontSize: 12, fontFamily: 'var(--t-font-mono)' }}>Нет решений AI</div>
        <div style={{ fontSize: 10 }}>Решения Chief Scientist появятся здесь</div>
      </div>
    )
  }

  const decColor = (type: string) => {
    const t = (type ?? '').toUpperCase()
    if (t.includes('ARCHIVE')) return 'var(--t-red)'
    if (t.includes('CONTINUE') || t.includes('PASS') || t.includes('EXPAND')) return 'var(--t-green)'
    if (t.includes('REQUEST')) return 'var(--t-amber)'
    return 'var(--t-accent)'
  }

  return (
    <div style={{ flex: 1, overflowY: 'auto' }}>
      {decisions.map((d, i) => (
        <div
          key={(d as any).decision_id ?? i}
          style={{
            padding: '12px 16px', borderBottom: '1px solid rgba(255,255,255,0.04)',
            display: 'flex', flexDirection: 'column', gap: 6,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
            <span style={{
              padding: '1px 6px', borderRadius: 2, fontSize: 9, fontWeight: 700,
              fontFamily: 'var(--t-font-mono)', letterSpacing: 0.5,
              background: `${decColor((d as any).decision_type ?? '')}22`,
              color: decColor((d as any).decision_type ?? ''),
              border: `1px solid ${decColor((d as any).decision_type ?? '')}44`,
              flexShrink: 0,
            }}>
              {(d as any).decision_type ?? 'РЕШЕНИЕ'}
            </span>
            <span style={{ fontSize: 10, color: 'var(--t-text)', fontFamily: 'var(--t-font-mono)', flex: 1 }}>
              {(d as any).hypothesis_id ?? (d as any).plan_id ?? ''}
            </span>
            <span style={{ fontSize: 9, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)', flexShrink: 0 }}>
              {(d as any).confidence != null ? `${Math.round((d as any).confidence * 100)}%` : ''}
            </span>
          </div>

          {(d as any).reason?.description && (
            <div style={{ fontSize: 10, color: 'var(--t-text-2)', lineHeight: 1.5, paddingLeft: 6, borderLeft: '2px solid var(--t-border)' }}>
              {(d as any).reason.description}
            </div>
          )}

          {(d as any).reason?.evidence?.length > 0 && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, paddingLeft: 6 }}>
              {((d as any).reason.evidence as string[]).map((ev: string, j: number) => (
                <span key={j} style={{
                  fontSize: 9, padding: '1px 5px', borderRadius: 2,
                  background: 'var(--t-elevated)', color: 'var(--t-text-3)',
                  border: '1px solid var(--t-border)', fontFamily: 'var(--t-font-mono)',
                }}>
                  {ev}
                </span>
              ))}
            </div>
          )}

          <div style={{ fontSize: 9, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)' }}>
            {(d as any).created_at ? fmtDt((d as any).created_at) : ''}
            {(d as any).priority != null ? ` · Приоритет: ${(d as any).priority}` : ''}
          </div>
        </div>
      ))}
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────
type Tab = 'reports' | 'journal' | 'decisions'

export default function ReportsPage() {
  const { allFullReports, activity, decisions } = useTerminal()
  const [tab, setTab] = useState<Tab>('reports')

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', background: 'var(--t-bg)', overflow: 'hidden' }}>
      {/* Header + tabs */}
      <div style={{ height: 44, flexShrink: 0, display: 'flex', alignItems: 'center', background: 'var(--t-panel)', borderBottom: '1px solid var(--t-border)', padding: '0 8px', gap: 0 }}>
        <IconFileText size={13} color="var(--t-text-3)" style={{ margin: '0 8px' }} />
        <span style={{ fontSize: 11, fontWeight: 700, fontFamily: 'var(--t-font-mono)', color: 'var(--t-text)', letterSpacing: 1, marginRight: 8 }}>ОТЧЁТЫ</span>
        <div style={{ width: 1, height: 16, background: 'var(--t-border)', margin: '0 4px' }} />
        <TabBtn active={tab === 'reports'}   onClick={() => setTab('reports')}   icon={<IconFileText size={10} />}  label={`Отчёты (${allFullReports.length})`} />
        <TabBtn active={tab === 'journal'}   onClick={() => setTab('journal')}   icon={<IconBook size={10} />}      label={`Журнал (${activity.length})`} />
        <TabBtn active={tab === 'decisions'} onClick={() => setTab('decisions')} icon={<IconBulb size={10} />}      label={`Решения AI (${decisions.length})`} />
      </div>

      {/* Content */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
        {tab === 'reports'   && <ReportsTab />}
        {tab === 'journal'   && <JournalTab />}
        {tab === 'decisions' && <DecisionsTab />}
      </div>
    </div>
  )
}
