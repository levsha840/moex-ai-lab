import { useState } from 'react'
import { Select, Loader, Center } from '@mantine/core'
import { useQuery } from '@tanstack/react-query'
import { IconSearch, IconArrowUp, IconArrowDown, IconCheck, IconX } from '@tabler/icons-react'
import { fetchReports, fetchReport, fetchTradeDetail } from '../api/client'
import StatusBadge from '../components/shared/StatusBadge'

export default function ExplainDecision() {
  const { data: reports = [] } = useQuery({ queryKey: ['reports'], queryFn: fetchReports })
  const [selectedReport, setSelectedReport] = useState<string>('')
  const [selectedTrade, setSelectedTrade] = useState<string>('')

  const currentReport = reports.find((_, i) => String(i) === selectedReport)

  const { data: report } = useQuery({
    queryKey: ['report', currentReport?.hypothesis_id, currentReport?.ticker, currentReport?.period, currentReport?.timeframe],
    queryFn: () => fetchReport(currentReport!.hypothesis_id, currentReport!.ticker, currentReport!.period, currentReport!.timeframe),
    enabled: !!currentReport,
  })

  const tradeOptions = (report?.trade_journal ?? []).map((t: any) => ({
    value: t.trade_id,
    label: `${t.trade_id.slice(-6)} | ${t.entry_timestamp?.slice(5, 16)} → ${t.exit_timestamp?.slice(5, 16)} | ${t.pnl_pct >= 0 ? '+' : ''}${t.pnl_pct.toFixed(2)}%`,
  }))

  const { data: detail, isLoading } = useQuery({
    queryKey: ['trade-detail', currentReport?.hypothesis_id, currentReport?.ticker, currentReport?.period, selectedTrade],
    queryFn: () => fetchTradeDetail(currentReport!.hypothesis_id, currentReport!.ticker, currentReport!.period, selectedTrade),
    enabled: !!currentReport && !!selectedTrade,
  })

  const reportOptions = reports.map((r, i) => ({
    value: String(i),
    label: `${r.hypothesis_id} | ${r.ticker} ${r.period} ${r.timeframe}`,
  }))

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden', background: 'var(--t-bg)' }}>
      {/* Toolbar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, height: 38, padding: '0 12px', background: 'var(--t-panel)', borderBottom: '1px solid var(--t-border)', flexShrink: 0 }}>
        <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--t-text-2)', textTransform: 'uppercase', letterSpacing: 1 }}>EXPLAIN DECISION</span>
        <div style={{ width: 1, height: 16, background: 'var(--t-border)' }} />
        <Select size="xs" placeholder="Select report..." data={reportOptions} value={selectedReport}
          onChange={v => { setSelectedReport(v ?? ''); setSelectedTrade('') }} style={{ width: 360 }} />
        <Select size="xs" placeholder="Select trade..." data={tradeOptions} value={selectedTrade}
          onChange={v => setSelectedTrade(v ?? '')} disabled={!report} style={{ width: 300 }} />
      </div>

      {/* Body */}
      {!selectedTrade && (
        <Center h="100%" style={{ flexDirection: 'column', gap: 10 }}>
          <IconSearch size={28} color="var(--t-text-3)" />
          <span style={{ fontSize: 12, color: 'var(--t-text-3)' }}>Select a report and a trade to see the decision explanation</span>
        </Center>
      )}

      {isLoading && <Center h="100%"><Loader /></Center>}

      {detail && (
        <div style={{ flex: 1, display: 'grid', gridTemplateColumns: '1fr 1fr', gridTemplateRows: '1fr 1fr', gap: 1, background: 'var(--t-border)', overflow: 'hidden' }}>
          {/* Trade overview */}
          <div style={{ background: 'var(--t-bg)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            <div className="t-section-title">⬡ Trade Overview</div>
            <div style={{ padding: '8px 12px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px 16px' }}>
              {[
                { label: 'Entry', value: detail.trade.entry_timestamp?.slice(0, 16), col: 'var(--t-text-2)' },
                { label: 'Exit', value: detail.trade.exit_timestamp?.slice(0, 16), col: 'var(--t-text-2)' },
                { label: 'Entry Price', value: `₽ ${detail.trade.entry_price.toFixed(2)}`, col: 'var(--t-green)' },
                { label: 'Exit Price', value: `₽ ${detail.trade.exit_price.toFixed(2)}`, col: detail.trade.is_winner ? 'var(--t-green)' : 'var(--t-red)' },
                { label: 'PnL', value: `${detail.trade.pnl_pct >= 0 ? '+' : ''}${detail.trade.pnl_pct.toFixed(3)}%`, col: detail.trade.is_winner ? 'var(--t-green)' : 'var(--t-red)' },
                { label: 'Result', value: detail.trade.is_winner ? 'WINNER ✓' : 'LOSER ✗', col: detail.trade.is_winner ? 'var(--t-green)' : 'var(--t-red)' },
              ].map(f => (
                <div key={f.label}>
                  <div style={{ fontSize: 10, color: 'var(--t-text-3)' }}>{f.label}</div>
                  <div style={{ fontSize: 12, color: f.col, fontFamily: 'var(--t-font-mono)', fontWeight: 600 }}>{f.value}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Chief Scientist */}
          <div style={{ background: 'var(--t-bg)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            <div className="t-section-title">⬡ Chief Scientist</div>
            <div style={{ padding: '10px 12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                <StatusBadge status={detail.chief_scientist.decision} />
                <span style={{ fontSize: 11, color: 'var(--t-cyan)', fontFamily: 'var(--t-font-mono)' }}>{detail.strategy_name}</span>
              </div>
              <div style={{ fontSize: 11, color: 'var(--t-text-2)', lineHeight: 1.6 }}>{detail.chief_scientist.rationale}</div>
            </div>
          </div>

          {/* Entry Analysis */}
          <div style={{ background: 'var(--t-bg)', display: 'flex', flexDirection: 'column', overflow: 'auto' }}>
            <div className="t-section-title" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <IconArrowUp size={11} color="var(--t-green)" />
              <span>⬡ Entry Analysis</span>
            </div>
            <div style={{ padding: '6px 12px', fontSize: 11, color: 'var(--t-text-2)', marginBottom: 6 }}>{detail.entry_analysis.reason}</div>
            {detail.entry_analysis.factors.map((f: any, i: number) => (
              <div key={i} style={{ padding: '6px 12px', borderBottom: '1px solid var(--t-border-dim)', display: 'flex', alignItems: 'center', gap: 10 }}>
                <div style={{ flex: 1 }}>
                  <span style={{ fontSize: 11, color: 'var(--t-text)', fontWeight: 600 }}>{f.indicator}</span>
                  <span style={{ fontSize: 10, color: 'var(--t-text-3)', marginLeft: 8 }}>{f.note}</span>
                </div>
                <span style={{ fontSize: 11, color: 'var(--t-cyan)', fontFamily: 'var(--t-font-mono)' }}>{f.value}</span>
                {f.confirmed ? <IconCheck size={11} color="var(--t-green)" /> : <IconX size={11} color="var(--t-text-3)" />}
              </div>
            ))}
          </div>

          {/* Exit Analysis */}
          <div style={{ background: 'var(--t-bg)', display: 'flex', flexDirection: 'column', overflow: 'auto' }}>
            <div className="t-section-title" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <IconArrowDown size={11} color={detail.trade.is_winner ? 'var(--t-accent)' : 'var(--t-red)'} />
              <span>⬡ Exit Analysis</span>
            </div>
            {[
              { label: 'Exit Reason', value: detail.exit_analysis.exit_reason, col: 'var(--t-amber)' },
              { label: 'Exit Price', value: `₽ ${detail.exit_analysis.exit_price.toFixed(2)}`, col: 'var(--t-text)' },
              { label: 'PnL (₽)', value: `${detail.exit_analysis.pnl >= 0 ? '+' : ''}${detail.exit_analysis.pnl.toFixed(0)}`, col: detail.trade.is_winner ? 'var(--t-green)' : 'var(--t-red)' },
              { label: 'PnL (%)', value: `${detail.exit_analysis.pnl_pct >= 0 ? '+' : ''}${detail.exit_analysis.pnl_pct.toFixed(3)}%`, col: detail.trade.is_winner ? 'var(--t-green)' : 'var(--t-red)' },
            ].map(f => (
              <div key={f.label} style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 12px', borderBottom: '1px solid var(--t-border-dim)' }}>
                <span style={{ fontSize: 11, color: 'var(--t-text-2)' }}>{f.label}</span>
                <span style={{ fontSize: 12, color: f.col, fontFamily: 'var(--t-font-mono)', fontWeight: 600 }}>{f.value}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
