import { Center, Loader } from '@mantine/core'
import { useQuery } from '@tanstack/react-query'
import { fetchPaperSummary } from '../api/client'
import MetricCard from '../components/shared/MetricCard'

export default function PaperPortfolio() {
  const { data: summary, isLoading } = useQuery({ queryKey: ['paper-summary'], queryFn: fetchPaperSummary })

  if (isLoading) return <Center h="100%"><Loader /></Center>
  if (!summary) return null

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden', background: 'var(--t-bg)' }}>
      {/* Toolbar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, height: 38, padding: '0 12px', background: 'var(--t-panel)', borderBottom: '1px solid var(--t-border)', flexShrink: 0 }}>
        <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--t-text-2)', textTransform: 'uppercase', letterSpacing: 1 }}>PAPER PORTFOLIO</span>
        <div style={{ width: 1, height: 16, background: 'var(--t-border)' }} />
        <span className={`t-chip ${summary.enabled ? 'green' : 'amber'}`}>
          {summary.enabled ? 'ACTIVE' : 'STANDBY'}
        </span>
        <div style={{ flex: 1 }} />
        <span style={{ fontSize: 10, color: 'var(--t-text-3)' }}>Simulation only · No orders executed</span>
      </div>

      {/* KPI strip */}
      <div className="t-kpi-grid" style={{ gridTemplateColumns: 'repeat(8, 1fr)' }}>
        {[
          { label: 'Initial Capital',  val: `₽ ${summary.initial_capital.toLocaleString('ru-RU', { maximumFractionDigits: 0 })}`, col: 'var(--t-text-2)' },
          { label: 'Current Capital',  val: `₽ ${summary.current_capital.toLocaleString('ru-RU', { maximumFractionDigits: 0 })}`, col: 'var(--t-cyan)' },
          { label: 'Total PnL',        val: `${summary.total_pnl >= 0 ? '+' : ''}₽ ${summary.total_pnl.toLocaleString('ru-RU', { maximumFractionDigits: 0 })}`, col: summary.total_pnl >= 0 ? 'var(--t-green)' : 'var(--t-red)' },
          { label: 'Return',           val: `${summary.total_return_pct >= 0 ? '+' : ''}${summary.total_return_pct.toFixed(2)}%`, col: summary.total_return_pct >= 0 ? 'var(--t-green)' : 'var(--t-red)' },
          { label: 'Win Rate',         val: `${(summary.win_rate * 100).toFixed(1)}%`, col: summary.win_rate >= 0.5 ? 'var(--t-green)' : 'var(--t-text-2)' },
          { label: 'Max Drawdown',     val: `${summary.max_drawdown_pct.toFixed(2)}%`, col: 'var(--t-red)' },
          { label: 'Open Positions',   val: summary.open_positions, col: summary.open_positions > 0 ? 'var(--t-amber)' : 'var(--t-text-3)' },
          { label: 'Total Trades',     val: summary.total_trades, col: 'var(--t-text)' },
        ].map(k => (
          <div key={k.label} className="t-kpi-cell">
            <div className="t-kpi-label">{k.label}</div>
            <div className="t-kpi-val" style={{ color: k.col }}>{k.val}</div>
          </div>
        ))}
      </div>

      {/* Body */}
      <div style={{ flex: 1, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1, background: 'var(--t-border)', overflow: 'hidden' }}>
        {/* Equity curve placeholder */}
        <div style={{ background: 'var(--t-bg)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div className="t-section-title">⬡ Equity Curve</div>
          <Center h="100%" style={{ flexDirection: 'column', gap: 8 }}>
            <div style={{ fontSize: 12, color: 'var(--t-text-3)' }}>Awaiting strategy approval for paper trading</div>
            <div style={{ fontSize: 10, color: 'var(--t-text-3)' }}>Capital: ₽ {summary.initial_capital.toLocaleString('ru-RU', { maximumFractionDigits: 0 })}</div>
            <div style={{ fontSize: 10, color: 'var(--t-text-3)' }}>{summary.note}</div>
          </Center>
        </div>

        {/* Open positions */}
        <div style={{ background: 'var(--t-bg)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div className="t-section-title">⬡ Open Positions</div>
          <Center h="100%">
            <span style={{ fontSize: 11, color: 'var(--t-text-3)' }}>No open positions — paper engine on standby</span>
          </Center>
        </div>

        {/* Right metrics */}
        <div style={{ background: 'var(--t-bg)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div className="t-section-title">⬡ Portfolio Performance</div>
          <MetricCard label="Capital"   value={`₽ ${summary.current_capital.toLocaleString('ru-RU', { maximumFractionDigits: 0 })}`} cls="cyan" />
          <MetricCard label="PnL"       value={`${summary.total_pnl >= 0 ? '+' : ''}${summary.total_pnl.toFixed(0)}`} cls={summary.total_pnl >= 0 ? 'up' : 'down'} />
          <MetricCard label="Return"    value={`${summary.total_return_pct >= 0 ? '+' : ''}${summary.total_return_pct.toFixed(2)}%`} cls={summary.total_return_pct >= 0 ? 'up' : 'down'} />
          <MetricCard label="Win Rate"  value={`${(summary.win_rate * 100).toFixed(1)}%`} cls={summary.win_rate >= 0.5 ? 'up' : 'dim'} />
          <MetricCard label="Max DD"    value={`${summary.max_drawdown_pct.toFixed(2)}%`} cls="down" />
          <MetricCard label="Trades"    value={summary.total_trades} cls="dim" />
        </div>

        {/* Trade history placeholder */}
        <div style={{ background: 'var(--t-bg)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div className="t-section-title">⬡ Trade History</div>
          <Center h="100%">
            <span style={{ fontSize: 11, color: 'var(--t-text-3)' }}>No completed trades yet</span>
          </Center>
        </div>
      </div>
    </div>
  )
}
