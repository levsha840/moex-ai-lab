import { useState, useMemo } from 'react'
import { IconHistory } from '@tabler/icons-react'
import { useTerminal } from '../context/TerminalContext'
import type { JournalEntry } from '../api/client'

// ── Types ───────────────────────────────────────────────────────────────────────
interface TradeRow {
  tradeId: string
  reportIdx: number
  ticker: string
  strategyName: string
  trade: JournalEntry
}

// ── Helpers ─────────────────────────────────────────────────────────────────────
function fmtDt(ts: string | undefined): string {
  if (!ts) return '—'
  const d = new Date(ts)
  if (isNaN(d.getTime())) return ts.slice(0, 10)
  const dd = String(d.getDate()).padStart(2, '0')
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const yy = String(d.getFullYear()).slice(2)
  const hh = String(d.getHours()).padStart(2, '0')
  const min = String(d.getMinutes()).padStart(2, '0')
  return `${dd}.${mm}.${yy} ${hh}:${min}`
}

function holdTime(t: JournalEntry): string {
  const entry = (t as any).entry_timestamp as string | undefined
  const exit  = (t as any).exit_timestamp  as string | undefined
  if (entry && exit) {
    const ms = new Date(exit).getTime() - new Date(entry).getTime()
    if (isNaN(ms) || ms < 0) return '—'
    const h = ms / (1000 * 60 * 60)
    if (h < 1)  return `${Math.round(h * 60)}м`
    if (h < 48) return `${Math.round(h)}ч`
    return `${(h / 24).toFixed(1)}д`
  }
  const bars = (t.exit_bar ?? t.entry_bar) - t.entry_bar
  return bars > 0 ? `${bars}б` : '—'
}

function pnlCol(n: number | undefined) {
  if (n == null) return 'var(--t-text-2)'
  return n >= 0 ? 'var(--t-green)' : 'var(--t-red)'
}

// ── Styles ───────────────────────────────────────────────────────────────────────
const TH: React.CSSProperties = {
  padding: '6px 8px', color: 'var(--t-text-3)', fontWeight: 600, letterSpacing: 0.4,
  fontSize: 9, textAlign: 'left', background: 'var(--t-panel)',
  borderBottom: '1px solid var(--t-border)', fontFamily: 'var(--t-font-mono)',
  position: 'sticky', top: 0, zIndex: 1, whiteSpace: 'nowrap',
}
const TD: React.CSSProperties = {
  padding: '5px 8px', fontSize: 10, fontFamily: 'var(--t-font-mono)',
  whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
}

const SEL: React.CSSProperties = {
  padding: '3px 8px', borderRadius: 3,
  background: 'var(--t-elevated)', border: '1px solid var(--t-border)',
  color: 'var(--t-text-2)', fontSize: 10, fontFamily: 'var(--t-font-mono)',
  cursor: 'pointer', outline: 'none',
}

function FilterBtn({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: '3px 8px', borderRadius: 3, border: 'none', cursor: 'pointer',
        fontSize: 9, fontFamily: 'var(--t-font-mono)', fontWeight: 600,
        background: active ? 'rgba(41,98,255,0.15)' : 'var(--t-elevated)',
        color:      active ? 'var(--t-accent)'       : 'var(--t-text-3)',
      }}
    >
      {children}
    </button>
  )
}

// ── Main component ──────────────────────────────────────────────────────────────
export default function HistoryPage() {
  const { allFullReports, setSelectedIdx, setActiveTab, setSelectedTradeId } = useTerminal()

  const [filterTicker, setFilterTicker] = useState('')
  const [filterStatus, setFilterStatus] = useState<'all' | 'win' | 'loss'>('all')

  // Build flat list of all trades across all reports
  const allRows: TradeRow[] = useMemo(() =>
    allFullReports.flatMap((report, idx) => {
      const journal: JournalEntry[] = (report as any)?.trade_journal ?? []
      const ticker = report?.ticker ?? '?'
      const strategyName = (report?.hypothesis_id ?? '').replace('tmpl_h_', '').replace(/_/g, ' ')
      return journal.map(trade => ({
        tradeId: trade.trade_id,
        reportIdx: idx,
        ticker,
        strategyName,
        trade,
      }))
    })
  , [allFullReports])

  const uniqueTickers = useMemo(() => [...new Set(allRows.map(r => r.ticker))].sort(), [allRows])

  const filtered = useMemo(() => allRows.filter(row => {
    if (filterTicker && row.ticker !== filterTicker) return false
    if (filterStatus === 'win'  && row.trade.is_winner === false) return false
    if (filterStatus === 'loss' && row.trade.is_winner !== false) return false
    return true
  }), [allRows, filterTicker, filterStatus])

  const wins     = filtered.filter(r => r.trade.is_winner !== false).length
  const losses   = filtered.length - wins
  const totalPnl = filtered.reduce((s, r) => s + (r.trade.pnl ?? 0), 0)

  const handleClick = (row: TradeRow) => {
    setSelectedIdx(row.reportIdx)
    setSelectedTradeId(row.tradeId)
    setActiveTab('terminal')
  }

  // ── Empty states ─────────────────────────────────────────────────────────────
  if (allFullReports.length === 0) {
    return (
      <div style={{ height: '100%', display: 'flex', flexDirection: 'column', background: 'var(--t-bg)', overflow: 'hidden' }}>
        <PageHeader />
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 12, color: 'var(--t-text-3)' }}>
          <IconHistory size={40} style={{ opacity: 0.15 }} />
          <div style={{ fontSize: 12, fontFamily: 'var(--t-font-mono)' }}>История торгов пуста</div>
          <div style={{ fontSize: 10, lineHeight: 1.6 }}>Запустите бэктест для получения торговых данных</div>
        </div>
      </div>
    )
  }

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', background: 'var(--t-bg)', overflow: 'hidden' }}>
      {/* Header / Filters */}
      <div style={{ height: 44, flexShrink: 0, display: 'flex', alignItems: 'center', padding: '0 12px', background: 'var(--t-panel)', borderBottom: '1px solid var(--t-border)', gap: 8 }}>
        <IconHistory size={13} color="var(--t-text-3)" />
        <span style={{ fontSize: 11, fontWeight: 700, fontFamily: 'var(--t-font-mono)', color: 'var(--t-text)', letterSpacing: 1, flexShrink: 0 }}>
          ИСТОРИЯ ТОРГОВ
        </span>

        <div style={{ width: 1, height: 16, background: 'var(--t-border)', flexShrink: 0 }} />

        {/* Ticker filter */}
        <select value={filterTicker} onChange={e => setFilterTicker(e.target.value)} style={SEL}>
          <option value="">Все инструменты</option>
          {uniqueTickers.map(t => <option key={t} value={t}>{t}</option>)}
        </select>

        {/* Status filter */}
        <div style={{ display: 'flex', gap: 3 }}>
          <FilterBtn active={filterStatus === 'all'}  onClick={() => setFilterStatus('all')}>Все</FilterBtn>
          <FilterBtn active={filterStatus === 'win'}  onClick={() => setFilterStatus('win')}>Прибыльные</FilterBtn>
          <FilterBtn active={filterStatus === 'loss'} onClick={() => setFilterStatus('loss')}>Убыточные</FilterBtn>
        </div>

        <div style={{ flex: 1 }} />

        {/* Summary stats */}
        <div style={{ display: 'flex', gap: 14, alignItems: 'center', flexShrink: 0 }}>
          <StatChip label="Сделок" value={String(filtered.length)} />
          <StatChip label="Прибыльных" value={String(wins)} color="var(--t-green)" />
          <StatChip label="Убыточных" value={String(losses)} color="var(--t-red)" />
          <StatChip
            label="Итого PnL"
            value={`${totalPnl >= 0 ? '+' : ''}${Math.round(totalPnl).toLocaleString('ru-RU')} ₽`}
            color={pnlCol(totalPnl)}
          />
        </div>
      </div>

      {/* Table */}
      <div style={{ flex: 1, overflowY: 'auto' }}>
        {filtered.length === 0 ? (
          <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--t-text-3)', fontSize: 10, fontFamily: 'var(--t-font-mono)' }}>
            Нет сделок по выбранным фильтрам
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                <th style={TH}>Вход</th>
                <th style={TH}>Выход</th>
                <th style={TH}>Инструмент</th>
                <th style={TH}>Стратегия</th>
                <th style={TH}>Направл.</th>
                <th style={{ ...TH, textAlign: 'right' }}>Цена вх.</th>
                <th style={{ ...TH, textAlign: 'right' }}>Цена вых.</th>
                <th style={{ ...TH, textAlign: 'right' }}>PnL ₽</th>
                <th style={{ ...TH, textAlign: 'right' }}>PnL %</th>
                <th style={TH}>Причина</th>
                <th style={TH}>Удержание</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((row, i) => {
                const t = row.trade
                const entryTs = (t as any).entry_timestamp as string | undefined
                const exitTs  = (t as any).exit_timestamp  as string | undefined
                const dir     = (t as any).direction ?? 'LONG'
                const isWin   = t.is_winner !== false

                return (
                  <tr
                    key={`${row.reportIdx}-${row.tradeId}-${i}`}
                    onClick={() => handleClick(row)}
                    style={{ borderBottom: '1px solid rgba(255,255,255,0.04)', cursor: 'pointer' }}
                    onMouseEnter={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.03)')}
                    onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                  >
                    <td style={{ ...TD, color: 'var(--t-text-3)' }}>{fmtDt(entryTs) !== '—' ? fmtDt(entryTs) : `Бар ${t.entry_bar}`}</td>
                    <td style={{ ...TD, color: 'var(--t-text-3)' }}>{exitTs ? fmtDt(exitTs) : t.exit_bar != null ? `Бар ${t.exit_bar}` : '—'}</td>
                    <td style={{ ...TD, color: 'var(--t-text)', fontWeight: 600 }}>{row.ticker}</td>
                    <td style={{ ...TD, color: 'var(--t-text-2)', maxWidth: 140 }}>{row.strategyName}</td>
                    <td style={{ ...TD, color: dir === 'SHORT' ? 'var(--t-red)' : 'var(--t-green)' }}>{dir}</td>
                    <td style={{ ...TD, color: 'var(--t-text-2)', textAlign: 'right' }}>
                      {t.entry_price != null ? t.entry_price.toFixed(2) : '—'}
                    </td>
                    <td style={{ ...TD, color: 'var(--t-text-2)', textAlign: 'right' }}>
                      {t.exit_price != null ? t.exit_price.toFixed(2) : '—'}
                    </td>
                    <td style={{ ...TD, color: pnlCol(t.pnl), textAlign: 'right', fontWeight: 600 }}>
                      {t.pnl != null ? `${t.pnl >= 0 ? '+' : ''}${Math.round(t.pnl).toLocaleString('ru-RU')}` : '—'}
                    </td>
                    <td style={{ ...TD, color: pnlCol(t.pnl_pct), textAlign: 'right', fontWeight: 600 }}>
                      {t.pnl_pct != null ? `${t.pnl_pct >= 0 ? '+' : ''}${t.pnl_pct.toFixed(2)}%` : '—'}
                    </td>
                    <td style={{ ...TD, color: 'var(--t-text-3)', maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {t.exit_reason ?? '—'}
                    </td>
                    <td style={{ ...TD, color: 'var(--t-text-3)' }}>{holdTime(t)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

function PageHeader() {
  return (
    <div style={{ height: 44, flexShrink: 0, display: 'flex', alignItems: 'center', padding: '0 16px', background: 'var(--t-panel)', borderBottom: '1px solid var(--t-border)', gap: 10 }}>
      <IconHistory size={13} color="var(--t-text-3)" />
      <span style={{ fontSize: 11, fontWeight: 700, fontFamily: 'var(--t-font-mono)', color: 'var(--t-text)', letterSpacing: 1 }}>ИСТОРИЯ ТОРГОВ</span>
    </div>
  )
}

function StatChip({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 1 }}>
      <span style={{ fontSize: 8, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)', letterSpacing: 0.3 }}>{label}</span>
      <span style={{ fontSize: 10, fontWeight: 700, fontFamily: 'var(--t-font-mono)', color: color ?? 'var(--t-text)' }}>{value}</span>
    </div>
  )
}
