import { useMemo } from 'react'
import { IconTestPipe, IconTerminal2, IconChartLine } from '@tabler/icons-react'
import { useTerminal } from '../context/TerminalContext'
import { metricsFromReport } from '../utils/portfolio'

function fmtPct(n: number) { return `${n >= 0 ? '+' : ''}${n.toFixed(2)}%` }
function pnlCol(n: number) { return n >= 0 ? 'var(--t-green)' : 'var(--t-red)' }

const TH: React.CSSProperties = {
  padding: '7px 10px', color: 'var(--t-text-3)', fontWeight: 600, letterSpacing: 0.5,
  fontSize: 9, textAlign: 'left', background: 'var(--t-panel)',
  borderBottom: '1px solid var(--t-border)', fontFamily: 'var(--t-font-mono)',
  position: 'sticky', top: 0, zIndex: 1, whiteSpace: 'nowrap',
}

const TD: React.CSSProperties = {
  padding: '7px 10px', fontSize: 10, fontFamily: 'var(--t-font-mono)',
}

function ActionBtn({ onClick, children, accent }: { onClick: () => void; children: React.ReactNode; accent?: boolean }) {
  return (
    <button
      onClick={e => { e.stopPropagation(); onClick() }}
      style={{
        padding: '3px 8px', borderRadius: 3, border: 'none', cursor: 'pointer',
        fontSize: 9, fontFamily: 'var(--t-font-mono)', fontWeight: 600,
        background: accent ? 'rgba(41,98,255,0.15)' : 'var(--t-elevated)',
        color: accent ? 'var(--t-accent)' : 'var(--t-text-3)',
        marginRight: 4,
      }}
    >
      {children}
    </button>
  )
}

export default function BacktestsPage() {
  const {
    reports, allFullReports, selectedIdx,
    setSelectedIdx, setActiveTab, setEquityExpanded,
  } = useTerminal()

  const allMetrics = useMemo(() =>
    allFullReports.map(r => { try { return metricsFromReport(r) } catch { return null } })
  , [allFullReports])

  if (reports.length === 0) {
    return (
      <div style={{ height: '100%', display: 'flex', flexDirection: 'column', background: 'var(--t-bg)', overflow: 'hidden' }}>
        <div style={{ height: 44, flexShrink: 0, display: 'flex', alignItems: 'center', padding: '0 16px', background: 'var(--t-panel)', borderBottom: '1px solid var(--t-border)', gap: 10 }}>
          <IconTestPipe size={13} color="var(--t-text-3)" />
          <span style={{ fontSize: 11, fontWeight: 700, fontFamily: 'var(--t-font-mono)', color: 'var(--t-text)', letterSpacing: 1 }}>БЭКТЕСТЫ</span>
        </div>
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 12, color: 'var(--t-text-3)' }}>
          <IconTestPipe size={40} style={{ opacity: 0.15 }} />
          <div style={{ fontSize: 12, fontFamily: 'var(--t-font-mono)' }}>Нет результатов бэктестов</div>
          <div style={{ fontSize: 10, lineHeight: 1.6 }}>Запустите эксперименты через Research Mode</div>
        </div>
      </div>
    )
  }

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', background: 'var(--t-bg)', overflow: 'hidden' }}>
      {/* Header */}
      <div style={{ height: 44, flexShrink: 0, display: 'flex', alignItems: 'center', padding: '0 16px', background: 'var(--t-panel)', borderBottom: '1px solid var(--t-border)', gap: 10 }}>
        <IconTestPipe size={13} color="var(--t-text-3)" />
        <span style={{ fontSize: 11, fontWeight: 700, fontFamily: 'var(--t-font-mono)', color: 'var(--t-text)', letterSpacing: 1 }}>БЭКТЕСТЫ</span>
        <span style={{ fontSize: 9, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)' }}>
          {reports.length} {reports.length === 1 ? 'отчёт' : reports.length < 5 ? 'отчёта' : 'отчётов'}
        </span>
      </div>

      {/* Table */}
      <div style={{ flex: 1, overflowY: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              {['#', 'Стратегия', 'Инструмент', 'Период', 'TF', 'Сделок', 'Доходность', 'Max DD', 'Win Rate', 'PF', 'Действия'].map(h => (
                <th key={h} style={TH}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {reports.map((r, i) => {
              const m = allMetrics[i]
              const isCurrent = i === selectedIdx
              return (
                <tr
                  key={r.report_id}
                  onClick={() => { setSelectedIdx(i); setActiveTab('terminal') }}
                  style={{
                    borderBottom: '1px solid rgba(255,255,255,0.04)', cursor: 'pointer',
                    background: isCurrent ? 'rgba(41,98,255,0.05)' : undefined,
                    outline: isCurrent ? '1px solid rgba(41,98,255,0.15)' : undefined,
                  }}
                  onMouseEnter={e => { if (!isCurrent) e.currentTarget.style.background = 'rgba(255,255,255,0.03)' }}
                  onMouseLeave={e => { e.currentTarget.style.background = isCurrent ? 'rgba(41,98,255,0.05)' : 'transparent' }}
                >
                  <td style={{ ...TD, color: 'var(--t-text-3)' }}>{i + 1}</td>
                  <td style={{ ...TD, color: 'var(--t-text)', maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {r.hypothesis_id.replace('tmpl_h_', '').replace(/_/g, ' ')}
                    {isCurrent && (
                      <span style={{ marginLeft: 6, fontSize: 8, padding: '1px 4px', borderRadius: 2, background: 'rgba(41,98,255,0.2)', color: 'var(--t-accent)' }}>
                        АКТИВЕН
                      </span>
                    )}
                  </td>
                  <td style={{ ...TD, color: 'var(--t-text-2)' }}>{r.ticker}</td>
                  <td style={{ ...TD, color: 'var(--t-text-3)' }}>{r.period}</td>
                  <td style={{ ...TD, color: 'var(--t-text-3)' }}>{r.timeframe.toUpperCase()}</td>
                  <td style={{ ...TD, color: 'var(--t-text-2)' }}>{m?.numTrades ?? r.num_trades ?? '—'}</td>
                  <td style={{ ...TD, color: pnlCol(r.total_return_pct), fontWeight: 600 }}>{fmtPct(r.total_return_pct)}</td>
                  <td style={{ ...TD, color: m ? 'var(--t-red)' : 'var(--t-text-3)' }}>
                    {m ? `${m.maxDrawdown.toFixed(1)}%` : '—'}
                  </td>
                  <td style={{ ...TD, color: 'var(--t-text-2)' }}>
                    {m ? `${m.winRate.toFixed(0)}%` : '—'}
                  </td>
                  <td style={{ ...TD, color: 'var(--t-text-2)' }}>
                    {m ? m.profitFactor.toFixed(2) : '—'}
                  </td>
                  <td style={{ ...TD, whiteSpace: 'nowrap' }}>
                    <ActionBtn accent onClick={() => { setSelectedIdx(i); setActiveTab('terminal') }}>
                      <IconTerminal2 size={9} style={{ marginRight: 3, verticalAlign: 'middle' }} />
                      Терминал
                    </ActionBtn>
                    <ActionBtn onClick={() => { setSelectedIdx(i); setEquityExpanded(true); setActiveTab('terminal') }}>
                      <IconChartLine size={9} style={{ marginRight: 3, verticalAlign: 'middle' }} />
                      Кривая
                    </ActionBtn>
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
