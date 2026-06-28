import { useState, useMemo } from 'react'
import { IconTestPipe, IconTerminal2, IconChartLine, IconChevronDown, IconChevronUp } from '@tabler/icons-react'
import { useTerminal } from '../context/TerminalContext'
import { metricsFromReport, equityFromReport } from '../utils/portfolio'
import EquityChart from '../components/chart/EquityChart'
import { TH, TD, TR_HOVER, fmtPct, fmtF, pnlColor as pnlCol } from '../styles/tokens'

function ActionBtn({ onClick, children, accent }: { onClick: () => void; children: React.ReactNode; accent?: boolean }) {
  return (
    <button
      onClick={e => { e.stopPropagation(); onClick() }}
      style={{
        padding: '3px 8px', borderRadius: 3, border: 'none', cursor: 'pointer',
        fontSize: 9, fontFamily: 'var(--t-font-mono)', fontWeight: 600,
        background: accent ? 'rgba(41,98,255,0.15)' : 'var(--t-elevated)',
        color: accent ? 'var(--t-accent)' : 'var(--t-text-3)',
        marginRight: 4, display: 'inline-flex', alignItems: 'center', gap: 3,
      }}
    >
      {children}
    </button>
  )
}

function MetricCard({ label, value, color, sub }: { label: string; value: string; color?: string; sub?: string }) {
  return (
    <div style={{ padding: '8px 10px', background: 'var(--t-elevated)', borderRadius: 4, border: '1px solid var(--t-border)' }}>
      <div style={{ fontSize: 8, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)', fontWeight: 700, letterSpacing: 0.5, marginBottom: 3 }}>{label}</div>
      <div style={{ fontSize: 13, fontWeight: 700, fontFamily: 'var(--t-font-mono)', color: color ?? 'var(--t-text)' }}>{value}</div>
      {sub && <div style={{ fontSize: 8, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)', marginTop: 2 }}>{sub}</div>}
    </div>
  )
}

// Detail panel shown under expanded row
function DetailPanel({ reportIdx }: { reportIdx: number }) {
  const { allFullReports, candles, fullReport, selectedIdx } = useTerminal()
  const report = allFullReports[reportIdx]

  // Use candles from context only if this report is the currently loaded one
  const reportCandles = reportIdx === selectedIdx ? candles : []
  const m = useMemo(() => {
    if (!report) return null
    try { return metricsFromReport(report) } catch { return null }
  }, [report])

  const equityData = useMemo(() => {
    if (!report || !reportCandles.length) return []
    try { return equityFromReport(report, reportCandles) } catch { return [] }
  }, [report, reportCandles])

  const trades = (report as any)?.trade_journal ?? []
  const wins   = trades.filter((t: any) => t.is_winner !== false).length

  if (!report) return null

  return (
    <div style={{ padding: '14px 16px', background: 'rgba(255,255,255,0.02)', borderBottom: '1px solid var(--t-border)' }}>
      {/* Metrics grid */}
      {m && (
        <>
          <div style={{ fontSize: 9, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)', fontWeight: 700, letterSpacing: 0.8, marginBottom: 8 }}>
            РЕЗУЛЬТАТЫ БЭКТЕСТА
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 6, marginBottom: 12 }}>
            <MetricCard label="ДОХОДНОСТЬ"   value={fmtPct(m.pnlPct)}          color={pnlCol(m.pnlPct)} />
            <MetricCard label="MAX DRAWDOWN" value={`${fmtF(m.maxDrawdown)}%`}  color="var(--t-red)" />
            <MetricCard label="SHARPE"       value={fmtF(m.sharpe)}             color={m.sharpe > 1 ? 'var(--t-green)' : m.sharpe < 0 ? 'var(--t-red)' : undefined} />
            <MetricCard label="SORTINO"      value={fmtF(m.sortino)}            color={m.sortino > 1 ? 'var(--t-green)' : undefined} />
            <MetricCard label="PROFIT FACTOR" value={fmtF(m.profitFactor)}      color={m.profitFactor >= 1.5 ? 'var(--t-green)' : m.profitFactor < 1 ? 'var(--t-red)' : undefined} />
            <MetricCard label="WIN RATE"     value={`${fmtF(m.winRate, 1)}%`}   color={m.winRate >= 50 ? 'var(--t-green)' : 'var(--t-red)'}
              sub={`${wins}/${m.numTrades} сделок`} />
          </div>
        </>
      )}

      {/* Equity curve */}
      {equityData.length > 1 && (
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 9, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)', fontWeight: 700, letterSpacing: 0.8, marginBottom: 6 }}>
            КРИВАЯ КАПИТАЛА
          </div>
          <EquityChart primaryData={equityData} primaryLabel={report.ticker ?? ''} height={160} compact />
        </div>
      )}

      {/* No equity data hint */}
      {equityData.length <= 1 && reportIdx !== selectedIdx && (
        <div style={{ padding: '8px 10px', background: 'var(--t-elevated)', borderRadius: 4, fontSize: 9, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)', marginBottom: 12 }}>
          Нажмите «Терминал» чтобы загрузить данные и отобразить кривую капитала
        </div>
      )}

      {/* Mini trades list */}
      {trades.length > 0 && (
        <div>
          <div style={{ fontSize: 9, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)', fontWeight: 700, letterSpacing: 0.8, marginBottom: 6 }}>
            ПОСЛЕДНИЕ СДЕЛКИ
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  {['Бар вх.', 'Бар вых.', 'PnL ₽', 'PnL %', 'Причина выхода'].map(h => (
                    <th key={h} style={{ ...TH, position: 'relative', top: 'auto', fontSize: 8 }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(trades as any[]).slice(-10).map((t: any, i: number) => (
                  <tr key={i} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                    <td style={{ ...TD, fontSize: 9, color: 'var(--t-text-3)' }}>{t.entry_bar}</td>
                    <td style={{ ...TD, fontSize: 9, color: 'var(--t-text-3)' }}>{t.exit_bar ?? '—'}</td>
                    <td style={{ ...TD, fontSize: 9, color: pnlCol(t.pnl), fontWeight: 600 }}>
                      {t.pnl != null ? `${t.pnl >= 0 ? '+' : ''}${Math.round(t.pnl).toLocaleString('ru-RU')}` : '—'}
                    </td>
                    <td style={{ ...TD, fontSize: 9, color: pnlCol(t.pnl_pct), fontWeight: 600 }}>
                      {t.pnl_pct != null ? `${t.pnl_pct >= 0 ? '+' : ''}${t.pnl_pct.toFixed(2)}%` : '—'}
                    </td>
                    <td style={{ ...TD, fontSize: 9, color: 'var(--t-text-3)', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {t.exit_reason ?? '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

export default function BacktestsPage() {
  const { reports, allFullReports, selectedIdx, setSelectedIdx, setActiveTab, setEquityExpanded } = useTerminal()
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null)

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
        <div style={{ flex: 1 }} />
        <span style={{ fontSize: 8, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)' }}>
          Нажмите строку для раскрытия деталей
        </span>
      </div>

      {/* Table + expandable rows */}
      <div style={{ flex: 1, overflowY: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              {['#', 'Стратегия', 'Инструмент', 'Период', 'TF', 'Сделок', 'Доходность', 'Max DD', 'Win Rate', 'PF', 'Действия', ''].map((h, j) => (
                <th key={j} style={TH}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {reports.map((r, i) => {
              const m = allMetrics[i]
              const isCurrent  = i === selectedIdx
              const isExpanded = expandedIdx === i

              return (
                <>
                  <tr
                    key={r.report_id}
                    onClick={() => setExpandedIdx(isExpanded ? null : i)}
                    style={{
                      borderBottom: isExpanded ? 'none' : '1px solid rgba(255,255,255,0.04)',
                      cursor: 'pointer',
                      background: isCurrent ? 'rgba(41,98,255,0.05)' : undefined,
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
                    <td style={{ ...TD, color: m ? (m.winRate >= 50 ? 'var(--t-green)' : 'var(--t-red)') : 'var(--t-text-3)' }}>
                      {m ? `${m.winRate.toFixed(0)}%` : '—'}
                    </td>
                    <td style={{ ...TD, color: m ? (m.profitFactor >= 1.5 ? 'var(--t-green)' : m.profitFactor < 1 ? 'var(--t-red)' : 'var(--t-text-2)') : 'var(--t-text-3)' }}>
                      {m ? m.profitFactor.toFixed(2) : '—'}
                    </td>
                    <td style={{ ...TD, whiteSpace: 'nowrap' }}>
                      <ActionBtn accent onClick={() => { setSelectedIdx(i); setActiveTab('terminal') }}>
                        <IconTerminal2 size={9} />
                        Терминал
                      </ActionBtn>
                      <ActionBtn onClick={() => { setSelectedIdx(i); setEquityExpanded(true); setActiveTab('terminal') }}>
                        <IconChartLine size={9} />
                        Кривая
                      </ActionBtn>
                    </td>
                    <td style={{ ...TD, width: 24, textAlign: 'center', color: 'var(--t-text-3)' }}>
                      {isExpanded ? <IconChevronUp size={12} /> : <IconChevronDown size={12} />}
                    </td>
                  </tr>
                  {isExpanded && (
                    <tr key={`detail-${i}`}>
                      <td colSpan={12} style={{ padding: 0, borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                        <DetailPanel reportIdx={i} />
                      </td>
                    </tr>
                  )}
                </>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
