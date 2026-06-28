import { useState, useMemo } from 'react'
import { IconHistory, IconDownload, IconSearch, IconChevronLeft, IconChevronRight } from '@tabler/icons-react'
import { useTerminal } from '../context/TerminalContext'
import type { JournalEntry } from '../api/client'

const PAGE_SIZE = 75

interface TradeRow {
  tradeId: string
  reportIdx: number
  ticker: string
  strategyName: string
  trade: JournalEntry
}

type SortKey = 'date' | 'ticker' | 'pnl' | 'pnlPct' | 'hold'
type SortDir = 1 | -1

function fmtDt(ts: string | undefined): string {
  if (!ts) return '—'
  const d = new Date(ts)
  if (isNaN(d.getTime())) return ts.slice(0, 10)
  return `${String(d.getDate()).padStart(2,'0')}.${String(d.getMonth()+1).padStart(2,'0')}.${String(d.getFullYear()).slice(2)} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`
}

function holdMs(t: JournalEntry): number {
  const entry = (t as any).entry_timestamp as string | undefined
  const exit  = (t as any).exit_timestamp  as string | undefined
  if (entry && exit) {
    const ms = new Date(exit).getTime() - new Date(entry).getTime()
    return isNaN(ms) || ms < 0 ? 0 : ms
  }
  return Math.max(0, (t.exit_bar ?? t.entry_bar) - t.entry_bar) * 3600_000
}

function holdTime(t: JournalEntry): string {
  const ms = holdMs(t)
  if (ms === 0) return '—'
  const h = ms / 3_600_000
  if (h < 1)  return `${Math.round(h * 60)}м`
  if (h < 48) return `${Math.round(h)}ч`
  return `${(h / 24).toFixed(1)}д`
}

function pnlColor(n: number | undefined) {
  if (n == null) return 'var(--t-text-2)'
  return n >= 0 ? 'var(--t-green)' : 'var(--t-red)'
}

const TH: React.CSSProperties = {
  padding: '6px 8px', color: 'var(--t-text-3)', fontWeight: 600, letterSpacing: 0.4,
  fontSize: 9, textAlign: 'left', background: 'var(--t-panel)',
  borderBottom: '1px solid var(--t-border)', fontFamily: 'var(--t-font-mono)',
  position: 'sticky', top: 0, zIndex: 1, whiteSpace: 'nowrap', cursor: 'pointer',
  userSelect: 'none',
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
    <button onClick={onClick} style={{
      padding: '3px 8px', borderRadius: 3, border: 'none', cursor: 'pointer',
      fontSize: 9, fontFamily: 'var(--t-font-mono)', fontWeight: 600,
      background: active ? 'rgba(41,98,255,0.15)' : 'var(--t-elevated)',
      color: active ? 'var(--t-accent)' : 'var(--t-text-3)',
    }}>
      {children}
    </button>
  )
}

function exportCSV(rows: TradeRow[], holdTimeFn: (t: JournalEntry) => string) {
  const cols = ['Вход', 'Выход', 'Инструмент', 'Стратегия', 'Направление', 'Цена вх.', 'Цена вых.', 'PnL ₽', 'PnL %', 'Причина', 'Удержание']
  const lines = [cols.join(';')]
  for (const row of rows) {
    const t = row.trade
    const entryTs = (t as any).entry_timestamp as string | undefined
    const exitTs  = (t as any).exit_timestamp  as string | undefined
    lines.push([
      fmtDt(entryTs) !== '—' ? fmtDt(entryTs) : `Бар ${t.entry_bar}`,
      exitTs ? fmtDt(exitTs) : t.exit_bar != null ? `Бар ${t.exit_bar}` : '—',
      row.ticker,
      row.strategyName,
      (t as any).direction ?? 'LONG',
      t.entry_price?.toFixed(2) ?? '—',
      t.exit_price?.toFixed(2) ?? '—',
      Math.round(t.pnl ?? 0).toString(),
      (t.pnl_pct ?? 0).toFixed(2),
      t.exit_reason ?? '—',
      holdTimeFn(t),
    ].map(v => `"${String(v).replace(/"/g, '""')}"`).join(';'))
  }
  const blob = new Blob(['﻿' + lines.join('\n')], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `trades_${new Date().toISOString().slice(0, 10)}.csv`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

export default function HistoryPage() {
  const { allFullReports, setSelectedIdx, setActiveTab, setSelectedTradeId, jumpToBar } = useTerminal()

  const [search, setSearch]         = useState('')
  const [filterTicker, setFilterTicker] = useState('')
  const [filterStatus, setFilterStatus] = useState<'all' | 'win' | 'loss'>('all')
  const [sortKey, setSortKey]       = useState<SortKey>('date')
  const [sortDir, setSortDir]       = useState<SortDir>(-1)
  const [page, setPage]             = useState(0)

  const allRows: TradeRow[] = useMemo(() =>
    allFullReports.flatMap((report, idx) => {
      const journal: JournalEntry[] = (report as any)?.trade_journal ?? []
      const ticker = report?.ticker ?? '?'
      const strategyName = (report?.hypothesis_id ?? '').replace('tmpl_h_', '').replace(/_/g, ' ')
      return journal.map(trade => ({ tradeId: trade.trade_id, reportIdx: idx, ticker, strategyName, trade }))
    })
  , [allFullReports])

  const uniqueTickers = useMemo(() => [...new Set(allRows.map(r => r.ticker))].sort(), [allRows])

  const filtered = useMemo(() => {
    let rows = allRows
    if (filterTicker) rows = rows.filter(r => r.ticker === filterTicker)
    if (filterStatus === 'win')  rows = rows.filter(r => r.trade.is_winner !== false)
    if (filterStatus === 'loss') rows = rows.filter(r => r.trade.is_winner === false)
    if (search) {
      const q = search.toLowerCase()
      rows = rows.filter(r =>
        r.ticker.toLowerCase().includes(q) ||
        r.strategyName.toLowerCase().includes(q) ||
        r.trade.exit_reason?.toLowerCase().includes(q) ||
        ((r.trade as any).direction ?? '').toLowerCase().includes(q)
      )
    }
    return [...rows].sort((a, b) => {
      let av = 0, bv = 0
      if (sortKey === 'date') {
        av = new Date((a.trade as any).entry_timestamp ?? '').getTime() || a.trade.entry_bar
        bv = new Date((b.trade as any).entry_timestamp ?? '').getTime() || b.trade.entry_bar
      } else if (sortKey === 'pnl')    { av = a.trade.pnl ?? 0;     bv = b.trade.pnl ?? 0 }
      else if (sortKey === 'pnlPct')   { av = a.trade.pnl_pct ?? 0; bv = b.trade.pnl_pct ?? 0 }
      else if (sortKey === 'hold')     { av = holdMs(a.trade);       bv = holdMs(b.trade) }
      else if (sortKey === 'ticker')   { return sortDir * a.ticker.localeCompare(b.ticker) }
      return (av - bv) * sortDir
    })
  }, [allRows, filterTicker, filterStatus, search, sortKey, sortDir])

  const wins     = filtered.filter(r => r.trade.is_winner !== false).length
  const losses   = filtered.length - wins
  const totalPnl = filtered.reduce((s, r) => s + (r.trade.pnl ?? 0), 0)

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortDir(d => d === 1 ? -1 : 1)
    else { setSortKey(key); setSortDir(-1) }
    setPage(0)
  }

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const paginated  = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)

  // Reset page on filter/search change
  const setFilterTickerP = (v: string) => { setFilterTicker(v); setPage(0) }
  const setFilterStatusP = (v: 'all'|'win'|'loss') => { setFilterStatus(v); setPage(0) }
  const setSearchP = (v: string) => { setSearch(v); setPage(0) }

  const handleClick = (row: TradeRow) => {
    setSelectedIdx(row.reportIdx)
    setSelectedTradeId(row.tradeId)
    setActiveTab('terminal')
  }

  const handleDblClick = (row: TradeRow) => {
    setSelectedIdx(row.reportIdx)
    setSelectedTradeId(row.tradeId)
    setActiveTab('terminal')
    // jumpToBar uses original bar index; displayCandles/barMapping handled inside context
    jumpToBar(row.trade.entry_bar)
  }

  const SortIcon = ({ k }: { k: SortKey }) =>
    sortKey === k ? <span style={{ marginLeft: 2, color: 'var(--t-accent)' }}>{sortDir === -1 ? '↓' : '↑'}</span> : null

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
      <div style={{ height: 44, flexShrink: 0, display: 'flex', alignItems: 'center', padding: '0 10px', background: 'var(--t-panel)', borderBottom: '1px solid var(--t-border)', gap: 6 }}>
        <IconHistory size={13} color="var(--t-text-3)" />
        <span style={{ fontSize: 11, fontWeight: 700, fontFamily: 'var(--t-font-mono)', color: 'var(--t-text)', letterSpacing: 1, flexShrink: 0 }}>ИСТОРИЯ</span>

        <div style={{ width: 1, height: 16, background: 'var(--t-border)', flexShrink: 0 }} />

        {/* Search */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, background: 'var(--t-elevated)', border: '1px solid var(--t-border)', borderRadius: 3, padding: '2px 6px', minWidth: 140 }}>
          <IconSearch size={10} color="var(--t-text-3)" />
          <input
            value={search}
            onChange={e => setSearchP(e.target.value)}
            placeholder="Поиск..."
            style={{ background: 'none', border: 'none', outline: 'none', color: 'var(--t-text)', fontSize: 9, fontFamily: 'var(--t-font-mono)', width: 100 }}
          />
        </div>

        {/* Ticker filter */}
        <select value={filterTicker} onChange={e => setFilterTickerP(e.target.value)} style={SEL}>
          <option value="">Все инструменты</option>
          {uniqueTickers.map(t => <option key={t} value={t}>{t}</option>)}
        </select>

        {/* Status filter */}
        <div style={{ display: 'flex', gap: 3 }}>
          <FilterBtn active={filterStatus === 'all'}  onClick={() => setFilterStatusP('all')}>Все</FilterBtn>
          <FilterBtn active={filterStatus === 'win'}  onClick={() => setFilterStatusP('win')}>Прибыльные</FilterBtn>
          <FilterBtn active={filterStatus === 'loss'} onClick={() => setFilterStatusP('loss')}>Убыточные</FilterBtn>
        </div>

        <div style={{ flex: 1 }} />

        {/* Stats */}
        <StatChip label="Сделок"       value={String(filtered.length)} />
        <StatChip label="Прибыльных"   value={String(wins)}    color="var(--t-green)" />
        <StatChip label="Убыточных"    value={String(losses)}  color="var(--t-red)" />
        <StatChip label="Итого PnL"
          value={`${totalPnl >= 0 ? '+' : ''}${Math.round(totalPnl).toLocaleString('ru-RU')} ₽`}
          color={pnlColor(totalPnl)}
        />

        <div style={{ width: 1, height: 16, background: 'var(--t-border)', flexShrink: 0 }} />

        {/* CSV Export */}
        <button
          onClick={() => exportCSV(filtered, holdTime)}
          title="Экспорт в CSV"
          style={{ background: 'var(--t-elevated)', border: '1px solid var(--t-border)', borderRadius: 3, color: 'var(--t-text-3)', cursor: 'pointer', padding: '3px 7px', display: 'flex', alignItems: 'center', gap: 4 }}
        >
          <IconDownload size={11} />
          <span style={{ fontSize: 9, fontFamily: 'var(--t-font-mono)' }}>CSV</span>
        </button>
      </div>

      {/* Hint */}
      <div style={{ height: 20, flexShrink: 0, display: 'flex', alignItems: 'center', padding: '0 10px', background: 'rgba(41,98,255,0.04)', borderBottom: '1px solid var(--t-border)' }}>
        <span style={{ fontSize: 8, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)' }}>
          Клик — открыть в терминале · Двойной клик — перейти к баре на графике
        </span>
      </div>

      {/* Table */}
      <div style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
        {filtered.length === 0 ? (
          <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--t-text-3)', fontSize: 10, fontFamily: 'var(--t-font-mono)' }}>
            Нет сделок по выбранным фильтрам
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                <th style={TH} onClick={() => toggleSort('date')}>Вход <SortIcon k="date" /></th>
                <th style={TH}>Выход</th>
                <th style={TH} onClick={() => toggleSort('ticker')}>Инструмент <SortIcon k="ticker" /></th>
                <th style={TH}>Стратегия</th>
                <th style={TH}>Направл.</th>
                <th style={{ ...TH, textAlign: 'right' }}>Цена вх.</th>
                <th style={{ ...TH, textAlign: 'right' }}>Цена вых.</th>
                <th style={{ ...TH, textAlign: 'right' }} onClick={() => toggleSort('pnl')}>PnL ₽ <SortIcon k="pnl" /></th>
                <th style={{ ...TH, textAlign: 'right' }} onClick={() => toggleSort('pnlPct')}>PnL % <SortIcon k="pnlPct" /></th>
                <th style={TH}>Причина</th>
                <th style={TH} onClick={() => toggleSort('hold')}>Удержание <SortIcon k="hold" /></th>
              </tr>
            </thead>
            <tbody>
              {paginated.map((row, i) => {
                const t = row.trade
                const entryTs = (t as any).entry_timestamp as string | undefined
                const exitTs  = (t as any).exit_timestamp  as string | undefined
                const dir     = (t as any).direction ?? 'LONG'

                return (
                  <tr
                    key={`${row.reportIdx}-${row.tradeId}-${i}`}
                    onClick={() => handleClick(row)}
                    onDoubleClick={() => handleDblClick(row)}
                    style={{ borderBottom: '1px solid rgba(255,255,255,0.04)', cursor: 'pointer' }}
                    onMouseEnter={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.03)')}
                    onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                  >
                    <td style={{ ...TD, color: 'var(--t-text-3)' }}>
                      {entryTs ? fmtDt(entryTs) : `Бар ${t.entry_bar}`}
                    </td>
                    <td style={{ ...TD, color: 'var(--t-text-3)' }}>
                      {exitTs ? fmtDt(exitTs) : t.exit_bar != null ? `Бар ${t.exit_bar}` : '—'}
                    </td>
                    <td style={{ ...TD, color: 'var(--t-text)', fontWeight: 600 }}>{row.ticker}</td>
                    <td style={{ ...TD, color: 'var(--t-text-2)', maxWidth: 140 }}>{row.strategyName}</td>
                    <td style={{ ...TD, color: dir === 'SHORT' ? 'var(--t-red)' : 'var(--t-green)' }}>{dir}</td>
                    <td style={{ ...TD, color: 'var(--t-text-2)', textAlign: 'right' }}>
                      {t.entry_price != null ? t.entry_price.toFixed(2) : '—'}
                    </td>
                    <td style={{ ...TD, color: 'var(--t-text-2)', textAlign: 'right' }}>
                      {t.exit_price != null ? t.exit_price.toFixed(2) : '—'}
                    </td>
                    <td style={{ ...TD, color: pnlColor(t.pnl), textAlign: 'right', fontWeight: 600 }}>
                      {t.pnl != null ? `${t.pnl >= 0 ? '+' : ''}${Math.round(t.pnl).toLocaleString('ru-RU')}` : '—'}
                    </td>
                    <td style={{ ...TD, color: pnlColor(t.pnl_pct), textAlign: 'right', fontWeight: 600 }}>
                      {t.pnl_pct != null ? `${t.pnl_pct >= 0 ? '+' : ''}${t.pnl_pct.toFixed(2)}%` : '—'}
                    </td>
                    <td style={{ ...TD, color: 'var(--t-text-3)', maxWidth: 120 }}>{t.exit_reason ?? '—'}</td>
                    <td style={{ ...TD, color: 'var(--t-text-3)' }}>{holdTime(t)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div style={{ height: 32, flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6, background: 'var(--t-panel)', borderTop: '1px solid var(--t-border)' }}>
          <button
            disabled={page === 0}
            onClick={() => setPage(p => p - 1)}
            style={{ background: 'none', border: 'none', cursor: page === 0 ? 'default' : 'pointer', color: page === 0 ? 'var(--t-text-3)' : 'var(--t-text-2)', padding: '2px 4px', display: 'flex', alignItems: 'center' }}
          >
            <IconChevronLeft size={14} />
          </button>
          {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
            const p = totalPages <= 7 ? i : page < 4 ? i : page > totalPages - 5 ? totalPages - 7 + i : page - 3 + i
            return (
              <button key={p} onClick={() => setPage(p)} style={{
                padding: '2px 7px', borderRadius: 2, cursor: 'pointer',
                background: p === page ? 'var(--t-accent-soft)' : 'none',
                color: p === page ? 'var(--t-accent)' : 'var(--t-text-3)',
                border: p === page ? '1px solid var(--t-accent)' : '1px solid transparent',
                fontSize: 9, fontFamily: 'var(--t-font-mono)',
              }}>{p + 1}</button>
            )
          })}
          <button
            disabled={page >= totalPages - 1}
            onClick={() => setPage(p => p + 1)}
            style={{ background: 'none', border: 'none', cursor: page >= totalPages - 1 ? 'default' : 'pointer', color: page >= totalPages - 1 ? 'var(--t-text-3)' : 'var(--t-text-2)', padding: '2px 4px', display: 'flex', alignItems: 'center' }}
          >
            <IconChevronRight size={14} />
          </button>
          <span style={{ fontSize: 8, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)', marginLeft: 4 }}>
            {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, filtered.length)} из {filtered.length}
          </span>
        </div>
      )}
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
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 1, flexShrink: 0 }}>
      <span style={{ fontSize: 8, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)', letterSpacing: 0.3 }}>{label}</span>
      <span style={{ fontSize: 10, fontWeight: 700, fontFamily: 'var(--t-font-mono)', color: color ?? 'var(--t-text)' }}>{value}</span>
    </div>
  )
}
