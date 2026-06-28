import { ScrollArea } from '@mantine/core'
import { useTerminal, type BottomTab } from '../../context/TerminalContext'
import type { JournalEntry, ActivityEvent } from '../../api/client'

function TabBar() {
  const { bottomTab, setBottomTab } = useTerminal()
  const tabs: { id: BottomTab; label: string }[] = [
    { id: 'trades',    label: 'Open Trades'    },
    { id: 'history',   label: 'Trade History'  },
    { id: 'positions', label: 'Positions'      },
    { id: 'activity',  label: 'Activity'       },
    { id: 'aibrain',   label: 'AI Brain'       },
  ]
  return (
    <div style={{
      display: 'flex', alignItems: 'center', height: 32,
      borderBottom: '1px solid var(--t-border)', flexShrink: 0,
      background: 'var(--t-panel)', paddingLeft: 4,
    }}>
      {tabs.map(t => (
        <button
          key={t.id}
          onClick={() => setBottomTab(t.id)}
          style={{
            padding: '0 12px', height: '100%', border: 'none', background: 'none',
            cursor: 'pointer', fontSize: 10, fontFamily: 'var(--t-font-mono)',
            color: bottomTab === t.id ? 'var(--t-text)' : 'var(--t-text-3)',
            borderBottom: `2px solid ${bottomTab === t.id ? 'var(--t-accent)' : 'transparent'}`,
            letterSpacing: 0.5,
          }}
        >
          {t.label}
        </button>
      ))}
    </div>
  )
}

function TradeRow({ t, onExplain }: { t: JournalEntry; onExplain: (id: string) => void }) {
  const pnlColor = (t.pnl ?? 0) >= 0 ? 'var(--t-green)' : 'var(--t-red)'
  return (
    <tr
      onClick={() => onExplain(t.trade_id)}
      style={{ cursor: 'pointer' }}
      className="t-table-row"
    >
      <td>{t.trade_id?.slice(-4) ?? '—'}</td>
      <td style={{ fontFamily: 'var(--t-font-mono)', fontSize: 10 }}>{t.entry_price?.toFixed(2) ?? '—'}</td>
      <td style={{ fontFamily: 'var(--t-font-mono)', fontSize: 10 }}>{t.exit_price?.toFixed(2) ?? '—'}</td>
      <td style={{ color: pnlColor, fontFamily: 'var(--t-font-mono)', fontSize: 10 }}>
        {(t.pnl_pct ?? 0) >= 0 ? '+' : ''}{(t.pnl_pct ?? 0).toFixed(2)}%
      </td>
      <td style={{ color: pnlColor, fontFamily: 'var(--t-font-mono)', fontSize: 10 }}>
        {(t.pnl ?? 0) >= 0 ? '+' : ''}₽{((t.pnl ?? 0) / 1000).toFixed(1)}k
      </td>
      <td style={{ fontFamily: 'var(--t-font-mono)', fontSize: 10 }}>
        ₽{(t.capital_after / 1000).toFixed(1)}k
      </td>
      <td style={{ fontSize: 9, color: 'var(--t-text-3)', maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {t.exit_reason ?? '—'}
      </td>
      <td>
        <span style={{
          fontSize: 9, padding: '1px 4px', borderRadius: 2, fontFamily: 'var(--t-font-mono)',
          background: t.is_winner ? 'var(--t-green-soft)' : 'var(--t-red-soft)',
          color: t.is_winner ? 'var(--t-green)' : 'var(--t-red)',
        }}>
          {t.is_winner ? 'W' : 'L'}
        </span>
      </td>
    </tr>
  )
}

function TradeTable({ trades, onExplain }: { trades: JournalEntry[]; onExplain: (id: string) => void }) {
  if (!trades.length) return (
    <div style={{ padding: '20px', textAlign: 'center', color: 'var(--t-text-3)', fontSize: 11 }}>
      No trades in this report
    </div>
  )
  return (
    <table className="t-table" style={{ width: '100%', tableLayout: 'auto' }}>
      <thead>
        <tr>
          {['#', 'Entry ₽', 'Exit ₽', 'PnL%', 'PnL ₽', 'Capital', 'Reason', 'W/L'].map(h => (
            <th key={h} style={{ fontSize: 9 }}>{h}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {[...trades].reverse().map(t => (
          <TradeRow key={t.trade_id} t={t} onExplain={onExplain} />
        ))}
      </tbody>
    </table>
  )
}

function ActivityFeed({ events }: { events: ActivityEvent[] }) {
  if (!events.length) return (
    <div style={{ padding: '20px', textAlign: 'center', color: 'var(--t-text-3)', fontSize: 11 }}>
      No activity events
    </div>
  )
  const statusColor = (s: string) => {
    if (s === 'success' || s === 'pass') return 'var(--t-green)'
    if (s === 'error' || s === 'fail') return 'var(--t-red)'
    if (s === 'warning') return 'var(--t-amber)'
    return 'var(--t-cyan)'
  }
  return (
    <div style={{ padding: '4px 0' }}>
      {events.slice(0, 60).map(e => (
        <div key={e.id} style={{ display: 'flex', gap: 8, padding: '4px 10px', borderBottom: '1px solid var(--t-border-dim)', alignItems: 'flex-start' }}>
          <div style={{
            width: 6, height: 6, borderRadius: '50%', marginTop: 3, flexShrink: 0,
            background: statusColor(e.status),
          }} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
              <span style={{ fontSize: 10, color: 'var(--t-text)', fontWeight: 500 }}>{e.title}</span>
              <span style={{ fontSize: 9, color: 'var(--t-text-3)', flexShrink: 0, marginLeft: 8 }}>
                {new Date(e.timestamp).toLocaleTimeString('ru', { hour: '2-digit', minute: '2-digit' })}
              </span>
            </div>
            <div style={{ fontSize: 9, color: 'var(--t-text-3)', marginTop: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {e.detail}
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

function AIBrainTab() {
  const { currentSummary, decisions, status, trades } = useTerminal()
  const d = decisions[0]
  const winCount = trades.filter(t => t.is_winner).length
  const totalTrades = trades.length
  const capital = trades[trades.length - 1]?.capital_after ?? (currentSummary?.metrics as any)?.initial_capital ?? 1_000_000

  return (
    <div style={{ padding: '10px 12px', display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12 }}>
      <div>
        <div style={{ fontSize: 9, color: 'var(--t-text-3)', marginBottom: 8, letterSpacing: 1 }}>CURRENT STATE</div>
        {[
          { label: 'Hypothesis', value: currentSummary?.hypothesis_id?.slice(7, 25) ?? '—' },
          { label: 'Instrument', value: currentSummary ? `${currentSummary.ticker} · ${currentSummary.timeframe.toUpperCase()}` : '—' },
          { label: 'Period', value: currentSummary?.period ?? '—' },
          { label: 'Trades', value: `${totalTrades} (${winCount}W / ${totalTrades - winCount}L)` },
          { label: 'Capital', value: `₽${(capital / 1_000_000).toFixed(3)}M` },
        ].map(r => (
          <div key={r.label} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
            <span style={{ fontSize: 10, color: 'var(--t-text-2)' }}>{r.label}</span>
            <span style={{ fontSize: 10, fontFamily: 'var(--t-font-mono)', color: 'var(--t-text)' }}>{r.value}</span>
          </div>
        ))}
      </div>

      <div>
        <div style={{ fontSize: 9, color: 'var(--t-text-3)', marginBottom: 8, letterSpacing: 1 }}>LAB STATUS</div>
        {status ? [
          { label: 'Hypotheses', value: `${status.hypotheses.registered} registered` },
          { label: 'Tested', value: String(status.hypotheses.tested) },
          { label: 'Alpha Passed', value: String(status.hypotheses.passed_alpha_gate) },
          { label: 'Sessions', value: String(status.research.sessions) },
          { label: 'Budget', value: `${status.research_budget.used}/${status.research_budget.total}` },
        ].map(r => (
          <div key={r.label} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
            <span style={{ fontSize: 10, color: 'var(--t-text-2)' }}>{r.label}</span>
            <span style={{ fontSize: 10, fontFamily: 'var(--t-font-mono)', color: 'var(--t-text)' }}>{r.value}</span>
          </div>
        )) : <div style={{ fontSize: 10, color: 'var(--t-text-3)' }}>Loading…</div>}
      </div>

      <div>
        <div style={{ fontSize: 9, color: 'var(--t-text-3)', marginBottom: 8, letterSpacing: 1 }}>LAST CS DECISION</div>
        {d ? (
          <>
            <div style={{ fontSize: 11, fontWeight: 700, fontFamily: 'var(--t-font-mono)', color: d.type === 'APPROVE' ? 'var(--t-green)' : d.type === 'ARCHIVE' || d.type === 'REJECT' ? 'var(--t-red)' : 'var(--t-amber)', marginBottom: 6 }}>
              {d.type}
            </div>
            <div style={{ fontSize: 9, color: 'var(--t-text-2)', marginBottom: 4, fontFamily: 'var(--t-font-mono)' }}>
              {d.hypothesis_title}
            </div>
            <div style={{ fontSize: 9, color: 'var(--t-text-3)', lineHeight: 1.5 }}>
              {d.rationale}
            </div>
          </>
        ) : (
          <div style={{ fontSize: 10, color: 'var(--t-text-3)' }}>No decisions yet</div>
        )}
      </div>
    </div>
  )
}

export default function BottomPanel() {
  const { bottomTab, setBottomTab, trades, activity, setExplainTradeId } = useTerminal()

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', height: '100%',
      background: 'var(--t-panel)', borderTop: '1px solid var(--t-border)',
      overflow: 'hidden',
    }}>
      <TabBar />
      <div style={{ flex: 1, minHeight: 0 }}>
        <ScrollArea style={{ height: '100%' }} scrollbarSize={3}>
          {bottomTab === 'trades' && (() => {
            const open = trades.filter(t => (t as any).exit_bar == null)
            if (open.length > 0) return <TradeTable trades={open} onExplain={setExplainTradeId} />
            if (trades.length > 0) return (
              <div style={{ padding: '20px', textAlign: 'center', color: 'var(--t-text-3)', fontSize: 11 }}>
                No open positions — all {trades.length} backtest trades completed.<br />
                <span style={{ color: 'var(--t-accent)', cursor: 'pointer' }} onClick={() => setBottomTab('history')}>
                  → View Trade History
                </span>
              </div>
            )
            return <div style={{ padding: '20px', textAlign: 'center', color: 'var(--t-text-3)', fontSize: 11 }}>No trades data</div>
          })()}
          {bottomTab === 'history' && (
            <TradeTable trades={trades} onExplain={setExplainTradeId} />
          )}
          {bottomTab === 'positions' && (
            <div style={{ padding: '20px', textAlign: 'center', color: 'var(--t-text-3)', fontSize: 11 }}>
              Paper trading is in STANDBY mode — no live positions
            </div>
          )}
          {bottomTab === 'activity' && <ActivityFeed events={activity} />}
          {bottomTab === 'aibrain' && <AIBrainTab />}
        </ScrollArea>
      </div>
    </div>
  )
}
