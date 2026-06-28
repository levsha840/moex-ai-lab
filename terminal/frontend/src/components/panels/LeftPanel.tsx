import { ScrollArea } from '@mantine/core'
import { useTerminal } from '../../context/TerminalContext'

function InstrumentRow({ idx }: { idx: number }) {
  const { reports, selectedIdx, setSelectedIdx } = useTerminal()
  const r = reports[idx]
  if (!r) return null
  const ret = r.total_return_pct
  const active = idx === selectedIdx
  return (
    <div
      onClick={() => setSelectedIdx(idx)}
      style={{
        padding: '8px 10px',
        borderBottom: '1px solid var(--t-border-dim)',
        cursor: 'pointer',
        background: active ? 'var(--t-elevated)' : 'transparent',
        borderLeft: `3px solid ${active ? 'var(--t-accent)' : 'transparent'}`,
        transition: 'background 0.1s',
      }}
      onMouseEnter={e => { if (!active) (e.currentTarget as HTMLElement).style.background = 'var(--t-hover)' }}
      onMouseLeave={e => { if (!active) (e.currentTarget as HTMLElement).style.background = 'transparent' }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
        <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--t-text)', fontFamily: 'var(--t-font-mono)' }}>
          {r.ticker}
        </span>
        <span style={{
          fontSize: 11, fontWeight: 700, fontFamily: 'var(--t-font-mono)',
          color: ret >= 0 ? 'var(--t-green)' : 'var(--t-red)',
        }}>
          {ret >= 0 ? '+' : ''}{ret.toFixed(2)}%
        </span>
      </div>
      <div style={{ fontSize: 9, color: 'var(--t-text-3)', marginTop: 1 }}>
        {r.period} · {r.timeframe.toUpperCase()}
      </div>
      <div style={{ fontSize: 9, color: 'var(--t-text-3)', marginTop: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {r.hypothesis_id}
      </div>
      <div style={{ display: 'flex', gap: 8, marginTop: 3 }}>
        <span style={{ fontSize: 9, color: 'var(--t-text-2)', fontFamily: 'var(--t-font-mono)' }}>
          WR {(r.win_rate * 100).toFixed(0)}%
        </span>
        <span style={{ fontSize: 9, color: 'var(--t-text-2)', fontFamily: 'var(--t-font-mono)' }}>
          PF {r.profit_factor === Infinity ? '∞' : r.profit_factor.toFixed(2)}
        </span>
        <span style={{ fontSize: 9, color: 'var(--t-text-2)', fontFamily: 'var(--t-font-mono)' }}>
          DD {r.max_drawdown_pct.toFixed(1)}%
        </span>
      </div>
    </div>
  )
}

export default function LeftPanel() {
  const { reports, status } = useTerminal()
  const budget = status?.research_budget

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', height: '100%',
      background: 'var(--t-bg)', borderRight: '1px solid var(--t-border)',
    }}>
      {/* Header */}
      <div className="t-section-title" style={{ letterSpacing: 1.5 }}>⬡ MARKET</div>

      {/* Instrument list */}
      <ScrollArea style={{ flex: 1 }} scrollbarSize={3}>
        {reports.length === 0 && (
          <div style={{ padding: '12px 10px', fontSize: 10, color: 'var(--t-text-3)', lineHeight: 1.5 }}>
            No backtest reports.<br />Run a visual backtest campaign to populate this panel.
          </div>
        )}
        {reports.map((_, i) => <InstrumentRow key={i} idx={i} />)}
      </ScrollArea>

      {/* Research progress mini */}
      {status && (
        <>
          <div className="t-section-title" style={{ marginTop: 0 }}>⬡ RESEARCH</div>
          <div style={{ padding: '8px 10px', flexShrink: 0 }}>
            {[
              { label: 'Hypotheses', val: `${status.hypotheses.registered}`, sub: `${status.hypotheses.tested} tested` },
              { label: 'Passed Gate', val: `${status.hypotheses.passed_alpha_gate}`, sub: `${status.hypotheses.failed} failed` },
              { label: 'Sessions', val: `${status.research.sessions}`, sub: `${status.research.total_findings} findings` },
              { label: 'Datasets', val: `${status.datasets.total}`, sub: 'P1 Universe' },
              { label: 'VB Reports', val: `${status.research.visual_backtest_reports}`, sub: 'backtested' },
            ].map(row => (
              <div key={row.label} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 5 }}>
                <span style={{ fontSize: 10, color: 'var(--t-text-2)' }}>{row.label}</span>
                <div style={{ textAlign: 'right' }}>
                  <span style={{ fontSize: 11, fontFamily: 'var(--t-font-mono)', color: 'var(--t-text)' }}>{row.val}</span>
                  <span style={{ fontSize: 9, color: 'var(--t-text-3)', marginLeft: 4 }}>{row.sub}</span>
                </div>
              </div>
            ))}
          </div>

          {budget && (
            <div style={{ padding: '0 10px 8px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
                <span style={{ fontSize: 9, color: 'var(--t-text-3)' }}>BUDGET</span>
                <span style={{ fontSize: 9, color: 'var(--t-text-2)', fontFamily: 'var(--t-font-mono)' }}>
                  {budget.used}/{budget.total}
                </span>
              </div>
              <div style={{ height: 3, background: 'var(--t-elevated)', borderRadius: 2 }}>
                <div style={{
                  height: '100%',
                  width: `${Math.min(budget.used / Math.max(budget.total, 1) * 100, 100)}%`,
                  background: budget.used / budget.total > 0.8 ? 'var(--t-red)' : 'var(--t-accent)',
                  borderRadius: 2,
                }} />
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
