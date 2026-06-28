import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { TextInput, ScrollArea, Loader, Center, Tooltip } from '@mantine/core'
import { IconSearch, IconExternalLink } from '@tabler/icons-react'
import { fetchStrategies } from '../api/client'
import type { Strategy } from '../api/client'
import StatusBadge from '../components/shared/StatusBadge'

const FILTERS = ['All', 'RESEARCH_PASS', 'RESEARCH_FAIL', 'VISUAL_BACKTEST']

function fmt(v: number | null, d = 2) {
  if (v === null || v === undefined) return <span style={{ color: 'var(--t-text-3)' }}>—</span>
  return v.toFixed(d)
}

function fmtPct(v: number | null) {
  if (v === null) return <span style={{ color: 'var(--t-text-3)' }}>—</span>
  return (
    <span style={{ color: v >= 0 ? 'var(--t-green)' : 'var(--t-red)', fontFamily: 'var(--t-font-mono)' }}>
      {v >= 0 ? '+' : ''}{v.toFixed(2)}%
    </span>
  )
}

function fmtWin(v: number | null) {
  if (v === null) return <span style={{ color: 'var(--t-text-3)' }}>—</span>
  const pct = v * 100
  return <span style={{ color: pct >= 50 ? 'var(--t-green)' : 'var(--t-text-2)', fontFamily: 'var(--t-font-mono)' }}>{pct.toFixed(1)}%</span>
}

function fmtPF(v: number | null) {
  if (v === null) return <span style={{ color: 'var(--t-text-3)' }}>—</span>
  if (v === Infinity) return <span style={{ color: 'var(--t-green)', fontFamily: 'var(--t-font-mono)' }}>∞</span>
  return <span style={{ color: v >= 1 ? 'var(--t-green)' : 'var(--t-red)', fontFamily: 'var(--t-font-mono)' }}>{v.toFixed(2)}</span>
}

function SummaryBar({ strategies }: { strategies: Strategy[] }) {
  const passed = strategies.filter(s => s.status === 'RESEARCH_PASS').length
  const failed = strategies.filter(s => s.status === 'RESEARCH_FAIL').length
  const vb     = strategies.filter(s => s.status === 'VISUAL_BACKTEST').length
  return (
    <div style={{ display: 'flex', gap: 20, alignItems: 'center', padding: '6px 12px', background: 'var(--t-panel)', borderBottom: '1px solid var(--t-border)' }}>
      <span style={{ fontSize: 10, color: 'var(--t-text-2)' }}>Total: <b style={{ color: 'var(--t-text)', fontFamily: 'var(--t-font-mono)' }}>{strategies.length}</b></span>
      <span style={{ fontSize: 10, color: 'var(--t-text-2)' }}>Passed: <b style={{ color: 'var(--t-green)', fontFamily: 'var(--t-font-mono)' }}>{passed}</b></span>
      <span style={{ fontSize: 10, color: 'var(--t-text-2)' }}>Failed: <b style={{ color: 'var(--t-red)', fontFamily: 'var(--t-font-mono)' }}>{failed}</b></span>
      <span style={{ fontSize: 10, color: 'var(--t-text-2)' }}>Backtested: <b style={{ color: 'var(--t-accent)', fontFamily: 'var(--t-font-mono)' }}>{vb}</b></span>
    </div>
  )
}

export default function StrategyVault() {
  const [filter, setFilter] = useState('All')
  const [search, setSearch] = useState('')

  const { data: strategies = [], isLoading } = useQuery({ queryKey: ['strategies'], queryFn: () => fetchStrategies() })

  const filtered = strategies.filter(s => {
    if (filter !== 'All' && s.status !== filter) return false
    if (search && !s.strategy.toLowerCase().includes(search.toLowerCase()) && !s.template_id.includes(search)) return false
    return true
  })

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden', background: 'var(--t-bg)' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '0 12px', height: 38, background: 'var(--t-panel)', borderBottom: '1px solid var(--t-border)', flexShrink: 0 }}>
        <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--t-text-2)', textTransform: 'uppercase', letterSpacing: 1 }}>STRATEGY VAULT</span>
        <div style={{ width: 1, height: 16, background: 'var(--t-border)' }} />
        {/* Filter tabs */}
        {FILTERS.map(f => (
          <button key={f} onClick={() => setFilter(f)}
            style={{
              background: 'none', border: 'none', cursor: 'pointer', padding: '4px 10px',
              fontSize: 11, fontFamily: 'var(--t-font-mono)',
              color: filter === f ? 'var(--t-text)' : 'var(--t-text-2)',
              borderBottom: filter === f ? '2px solid var(--t-accent)' : '2px solid transparent',
              transition: 'all 0.1s',
            }}>
            {f}
          </button>
        ))}
        <div style={{ flex: 1 }} />
        <TextInput
          size="xs"
          placeholder="Search strategy..."
          leftSection={<IconSearch size={11} />}
          value={search}
          onChange={e => setSearch(e.currentTarget.value)}
          style={{ width: 200 }}
        />
      </div>

      <SummaryBar strategies={strategies} />

      {/* Table */}
      {isLoading ? (
        <Center h="100%"><Loader /></Center>
      ) : (
        <ScrollArea style={{ flex: 1 }} scrollbarSize={3}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead style={{ position: 'sticky', top: 0, zIndex: 10 }}>
              <tr>
                {['Strategy', 'Status', 'Score', 'Pass Rate', 'Win Rate', 'Profit Factor', 'Return', 'Max DD', 'Paper', 'Sandbox', ''].map(h => (
                  <th key={h} className="mantine-Table-th">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map(s => (
                <tr key={s.id}
                  onMouseEnter={e => (e.currentTarget.style.background = 'var(--t-hover)')}
                  onMouseLeave={e => (e.currentTarget.style.background = '')}
                  style={{ cursor: 'default' }}>
                  <td className="mantine-Table-td" style={{ maxWidth: 260 }}>
                    <Tooltip label={s.template_id} position="right" withArrow>
                      <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: 'var(--t-text)' }}>
                        {s.strategy}
                      </div>
                    </Tooltip>
                  </td>
                  <td className="mantine-Table-td"><StatusBadge status={s.status} /></td>
                  <td className="mantine-Table-td">
                    {s.research_score !== null
                      ? <span style={{ color: (s.research_score ?? 0) >= 40 ? 'var(--t-green)' : 'var(--t-red)', fontFamily: 'var(--t-font-mono)' }}>{s.research_score}%</span>
                      : <span style={{ color: 'var(--t-text-3)' }}>—</span>
                    }
                  </td>
                  <td className="mantine-Table-td">
                    {s.pass_rate !== null
                      ? <><span style={{ fontFamily: 'var(--t-font-mono)', color: 'var(--t-text-2)' }}>{(s.pass_rate * 100).toFixed(1)}%</span>
                          {s.windows_total && <span style={{ color: 'var(--t-text-3)', fontSize: 9, marginLeft: 4 }}>/{s.windows_total}w</span>}
                        </>
                      : <span style={{ color: 'var(--t-text-3)' }}>—</span>
                    }
                  </td>
                  <td className="mantine-Table-td">{fmtWin(s.win_rate)}</td>
                  <td className="mantine-Table-td">{fmtPF(s.profit_factor)}</td>
                  <td className="mantine-Table-td">{fmtPct(s.total_return_pct)}</td>
                  <td className="mantine-Table-td">
                    {s.max_drawdown_pct !== null
                      ? <span style={{ color: 'var(--t-red)', fontFamily: 'var(--t-font-mono)' }}>{s.max_drawdown_pct.toFixed(2)}%</span>
                      : <span style={{ color: 'var(--t-text-3)' }}>—</span>
                    }
                  </td>
                  <td className="mantine-Table-td"><StatusBadge status={s.paper_status} /></td>
                  <td className="mantine-Table-td"><StatusBadge status={s.sandbox_status} /></td>
                  <td className="mantine-Table-td">
                    {s.source === 'visual_backtest' && (
                      <button
                        onClick={() => window.location.hash = '#/research'}
                        style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '2px 8px', background: 'var(--t-accent-soft)', border: '1px solid var(--t-border-accent)', borderRadius: 2, cursor: 'pointer', color: 'var(--t-accent)', fontSize: 10, fontFamily: 'var(--t-font-mono)' }}>
                        <IconExternalLink size={10} />
                        Open
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollArea>
      )}
    </div>
  )
}
