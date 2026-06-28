import { useMemo } from 'react'
import { IconX } from '@tabler/icons-react'
import { useTerminal } from '../../context/TerminalContext'
import EquityChart from '../chart/EquityChart'
import { equityFromReport, COMPARE_COLORS } from '../../utils/portfolio'

function shortLabel(hypothesisId: string): string {
  return hypothesisId.replace('tmpl_h_', '').replace(/_/g, ' ')
}

export default function EquityFullscreen() {
  const { equityExpanded, setEquityExpanded, fullReport, allFullReports, candles, selectedIdx, reports } = useTerminal()

  const primaryReport = fullReport
  const primarySummary = reports[selectedIdx]

  const primaryData = useMemo(() => {
    if (!primaryReport || !candles.length) return []
    return equityFromReport(primaryReport, candles)
  }, [primaryReport, candles])

  const compareData = useMemo(() => {
    return allFullReports
      .filter((r, i) => i !== selectedIdx && r && candles.length)
      .map((r, i) => ({
        label: shortLabel(r.hypothesis_id),
        ticker: r.ticker,
        color: COMPARE_COLORS[(i + 1) % COMPARE_COLORS.length],
        data: equityFromReport(r, candles),
      }))
      .filter(cd => cd.data.length > 0)
  }, [allFullReports, candles, selectedIdx])

  if (!equityExpanded) return null

  const primaryLabel = primarySummary
    ? `${primarySummary.ticker} · ${shortLabel(primarySummary.hypothesis_id)}`
    : 'Текущая стратегия'

  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      zIndex: 1000,
      background: 'rgba(10,12,18,0.95)',
      display: 'flex',
      flexDirection: 'column',
    }}>
      {/* Header */}
      <div style={{
        height: 44,
        flexShrink: 0,
        display: 'flex',
        alignItems: 'center',
        padding: '0 16px',
        borderBottom: '1px solid var(--t-border)',
        background: 'var(--t-panel)',
        gap: 12,
      }}>
        <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--t-text)', fontFamily: 'var(--t-font-mono)', letterSpacing: 1 }}>
          КРИВАЯ КАПИТАЛА
        </span>
        {allFullReports.length > 1 && (
          <span style={{ fontSize: 9, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)', padding: '2px 6px', background: 'var(--t-elevated)', borderRadius: 2, border: '1px solid var(--t-border)' }}>
            {allFullReports.length} стратегий
          </span>
        )}

        {/* Strategy metrics summary */}
        {primaryReport && (
          <div style={{ display: 'flex', gap: 16, marginLeft: 16 }}>
            {[
              { label: 'Доходность', value: `${primaryReport.metrics.total_return_pct >= 0 ? '+' : ''}${primaryReport.metrics.total_return_pct.toFixed(2)}%`, color: primaryReport.metrics.total_return_pct >= 0 ? 'var(--t-green)' : 'var(--t-red)' },
              { label: 'Макс.просадка', value: `-${primaryReport.metrics.max_drawdown_pct.toFixed(2)}%`, color: 'var(--t-red)' },
              { label: 'Win Rate', value: `${(primaryReport.metrics.win_rate * 100).toFixed(1)}%`, color: 'var(--t-text)' },
              { label: 'Сделок', value: String(primaryReport.metrics.num_trades), color: 'var(--t-text)' },
            ].map(m => (
              <div key={m.label} style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                <span style={{ fontSize: 8, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)' }}>{m.label}</span>
                <span style={{ fontSize: 11, fontFamily: 'var(--t-font-mono)', fontWeight: 700, color: m.color }}>{m.value}</span>
              </div>
            ))}
          </div>
        )}

        <div style={{ flex: 1 }} />

        <button
          onClick={() => setEquityExpanded(false)}
          style={{
            display: 'flex', alignItems: 'center', gap: 5,
            padding: '4px 10px', border: '1px solid var(--t-border)',
            background: 'var(--t-elevated)', color: 'var(--t-text-2)',
            borderRadius: 3, cursor: 'pointer', fontSize: 10, fontFamily: 'var(--t-font-mono)',
          }}
        >
          <IconX size={11} />
          Закрыть
        </button>
      </div>

      {/* Chart */}
      <div style={{ flex: 1, minHeight: 0, padding: 0 }}>
        {!primaryData.length ? (
          <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--t-text-3)', fontSize: 12, fontFamily: 'var(--t-font-mono)', flexDirection: 'column', gap: 8 }}>
            <div>Нет данных для отображения</div>
            <div style={{ fontSize: 10, color: 'var(--t-text-3)' }}>Выберите стратегию с результатами бэктеста</div>
          </div>
        ) : (
          <EquityChart
            primaryData={primaryData}
            primaryLabel={primaryLabel}
            compareData={compareData}
          />
        )}
      </div>

      {/* Footer: compare table */}
      {allFullReports.length > 0 && (
        <div style={{
          flexShrink: 0,
          height: 80,
          borderTop: '1px solid var(--t-border)',
          background: 'var(--t-panel)',
          display: 'flex',
          alignItems: 'center',
          padding: '0 16px',
          gap: 12,
          overflowX: 'auto',
        }}>
          {allFullReports.map((r, i) => {
            const isCurrent = i === selectedIdx
            const color = isCurrent ? '#089981' : COMPARE_COLORS[(i % (COMPARE_COLORS.length - 1)) + 1]
            const ret = r?.metrics?.total_return_pct ?? 0
            return (
              <div key={r?.report_id ?? i} style={{
                display: 'flex', flexDirection: 'column', gap: 3,
                padding: '6px 10px',
                border: `1px solid ${isCurrent ? '#089981' : 'var(--t-border)'}`,
                borderRadius: 4,
                background: isCurrent ? 'rgba(8,153,129,0.08)' : 'var(--t-elevated)',
                minWidth: 130,
                flexShrink: 0,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                  <div style={{ width: 8, height: 8, borderRadius: 2, background: color }} />
                  <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--t-text)', fontFamily: 'var(--t-font-mono)' }}>
                    {r?.ticker ?? '—'}
                  </span>
                  {isCurrent && <span style={{ fontSize: 7, color: '#089981', fontFamily: 'var(--t-font-mono)', background: 'rgba(8,153,129,0.15)', padding: '1px 3px', borderRadius: 2 }}>АКТИВНА</span>}
                </div>
                <div style={{ fontSize: 8, color: 'var(--t-text-3)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {shortLabel(r?.hypothesis_id ?? '')}
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <span style={{ fontSize: 10, fontFamily: 'var(--t-font-mono)', fontWeight: 700, color: ret >= 0 ? 'var(--t-green)' : 'var(--t-red)' }}>
                    {ret >= 0 ? '+' : ''}{ret.toFixed(1)}%
                  </span>
                  <span style={{ fontSize: 9, fontFamily: 'var(--t-font-mono)', color: 'var(--t-text-3)' }}>
                    DD {r?.metrics?.max_drawdown_pct?.toFixed(1) ?? '—'}%
                  </span>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
