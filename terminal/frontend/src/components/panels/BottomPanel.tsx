import { useState, useMemo } from 'react'
import { ScrollArea } from '@mantine/core'
import { useTerminal, type BottomTab } from '../../context/TerminalContext'
import type { JournalEntry, ActivityEvent } from '../../api/client'

function pnlColor(v: number) { return v >= 0 ? 'var(--t-green)' : 'var(--t-red)' }

type TradeSort = 'idx' | 'pnl' | 'pnlPct' | 'entry' | 'exit' | 'hold'

const COL_TRADES: { key: string; w: number; sort?: TradeSort }[] = [
  { key: '#',          w: 26,  sort: 'idx'    },
  { key: 'Инструм.',  w: 62                   },
  { key: 'Напр.',     w: 46                   },
  { key: 'Вход ₽',   w: 70,  sort: 'entry'   },
  { key: 'Выход ₽',  w: 70,  sort: 'exit'    },
  { key: 'PnL%',     w: 54,  sort: 'pnlPct'  },
  { key: 'PnL ₽',    w: 64,  sort: 'pnl'     },
  { key: 'Капитал',  w: 82                   },
  { key: 'Причина',  w: 90                   },
  { key: 'Уд.',      w: 36,  sort: 'hold'    },
  { key: 'Рез.',     w: 30                   },
]

// ── Таблица сделок ────────────────────────────────────────────────────────────

function TradeTable({ trades, ticker }: { trades: JournalEntry[]; ticker: string | undefined }) {
  const { selectedTradeId, setSelectedTradeId, candles } = useTerminal()
  const [sortKey, setSortKey] = useState<TradeSort>('idx')
  const [sortDir, setSortDir] = useState<1|-1>(1)

  if (trades.length === 0) {
    return (
      <div style={{ padding: '14px 12px', fontSize: 11, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)' }}>
        Нет данных
      </div>
    )
  }

  const dirLabel = (t: JournalEntry): string => ((t as any).direction ?? 'LONG')

  const holdMs = (t: JournalEntry): number => {
    if (t.exit_bar == null) return 0
    const entryC = candles[t.entry_bar], exitC = candles[t.exit_bar]
    if (entryC && exitC) return (exitC.time - entryC.time) * 1000
    return (t.exit_bar - t.entry_bar) * 3_600_000
  }

  const holdLabel = (t: JournalEntry): string => {
    const ms = holdMs(t)
    if (ms === 0) return '—'
    const h = ms / 3_600_000
    return h < 48 ? `${Math.round(h)}ч` : `${(h / 24).toFixed(1)}д`
  }

  const toggleSort = (k: TradeSort) => {
    if (sortKey === k) setSortDir(d => d === 1 ? -1 : 1); else { setSortKey(k); setSortDir(-1) }
  }

  const sorted = useMemo(() => {
    const copy = [...trades]
    copy.sort((a, b) => {
      let av = 0, bv = 0
      if (sortKey === 'idx')    { av = a.entry_bar;      bv = b.entry_bar }
      if (sortKey === 'pnl')    { av = a.pnl ?? 0;       bv = b.pnl ?? 0 }
      if (sortKey === 'pnlPct') { av = a.pnl_pct ?? 0;   bv = b.pnl_pct ?? 0 }
      if (sortKey === 'entry')  { av = a.entry_price;     bv = b.entry_price }
      if (sortKey === 'exit')   { av = a.exit_price ?? 0; bv = b.exit_price ?? 0 }
      if (sortKey === 'hold')   { av = holdMs(a);         bv = holdMs(b) }
      return (av - bv) * sortDir
    })
    return copy
  }, [trades, sortKey, sortDir, candles])

  const thStyle = (sortable?: TradeSort): React.CSSProperties => ({
    textAlign: 'left', padding: '4px 6px',
    color: sortable && sortKey === sortable ? 'var(--t-accent)' : 'var(--t-text-3)',
    fontSize: 9, fontFamily: 'var(--t-font-mono)', fontWeight: 400,
    background: 'var(--t-panel)', letterSpacing: 0.3,
    position: 'sticky', top: 0, zIndex: 1, borderBottom: '1px solid var(--t-border)',
    cursor: sortable ? 'pointer' : 'default', userSelect: 'none',
    whiteSpace: 'nowrap',
  })

  return (
    <table className="t-table" style={{ tableLayout: 'fixed', width: '100%' }}>
      <colgroup>
        {COL_TRADES.map(c => <col key={c.key} style={{ width: c.w }} />)}
      </colgroup>
      <thead>
        <tr>
          {COL_TRADES.map(c => (
            <th
              key={c.key}
              style={thStyle(c.sort)}
              onClick={c.sort ? () => toggleSort(c.sort!) : undefined}
            >
              {c.key}{c.sort && sortKey === c.sort ? (sortDir === -1 ? '↓' : '↑') : ''}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {sorted.map((t, i) => {
          const dir = dirLabel(t)
          const dirColor = dir === 'SHORT' ? 'var(--t-red)' : 'var(--t-cyan)'
          const isSelected = !!(t.trade_id && t.trade_id === selectedTradeId)
          return (
            <tr
              key={t.trade_id ?? i}
              className="t-table-row"
              onClick={() => setSelectedTradeId(isSelected ? null : (t.trade_id ?? null))}
              style={{
                cursor: 'pointer',
                background: isSelected ? 'rgba(41,98,255,0.09)' : undefined,
                outline: isSelected ? '1px solid rgba(41,98,255,0.22)' : undefined,
                outlineOffset: -1,
              }}
            >
              <td style={{ fontSize: 10, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)', padding: '4px 6px' }}>{t.entry_bar + 1}</td>
              <td style={{ fontSize: 10, color: 'var(--t-text)', fontFamily: 'var(--t-font-mono)', padding: '4px 6px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {ticker ?? '—'}
              </td>
              <td style={{ fontSize: 9, fontFamily: 'var(--t-font-mono)', padding: '4px 6px', color: dirColor, fontWeight: 700 }}>
                {dir}
              </td>
              <td style={{ fontSize: 10, fontFamily: 'var(--t-font-mono)', padding: '4px 6px', color: 'var(--t-text-2)' }}>
                {t.entry_price.toFixed(2)}
              </td>
              <td style={{ fontSize: 10, fontFamily: 'var(--t-font-mono)', padding: '4px 6px', color: 'var(--t-text-2)' }}>
                {t.exit_price?.toFixed(2) ?? '—'}
              </td>
              <td style={{ fontSize: 10, fontFamily: 'var(--t-font-mono)', padding: '4px 6px', fontWeight: 600, color: pnlColor(t.pnl_pct ?? 0) }}>
                {(t.pnl_pct ?? 0) >= 0 ? '+' : ''}{(t.pnl_pct ?? 0).toFixed(2)}%
              </td>
              <td style={{ fontSize: 10, fontFamily: 'var(--t-font-mono)', padding: '4px 6px', color: pnlColor(t.pnl ?? 0) }}>
                {(t.pnl ?? 0) >= 0 ? '+' : ''}{(t.pnl ?? 0).toFixed(0)} ₽
              </td>
              <td style={{ fontSize: 10, fontFamily: 'var(--t-font-mono)', padding: '4px 6px', color: 'var(--t-text-2)' }}>
                {t.capital_after?.toFixed(0) ?? '—'}
              </td>
              <td style={{ fontSize: 9, color: 'var(--t-text-3)', padding: '4px 6px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {t.exit_reason ?? '—'}
              </td>
              <td style={{ fontSize: 9, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)', padding: '4px 6px', whiteSpace: 'nowrap' }}>
                {holdLabel(t)}
              </td>
              <td style={{ fontSize: 10, fontFamily: 'var(--t-font-mono)', padding: '4px 6px', fontWeight: 700, color: t.is_winner ? 'var(--t-green)' : 'var(--t-red)' }}>
                {t.is_winner ? 'W' : 'L'}
              </td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

// ── Сделки (открытые) ─────────────────────────────────────────────────────────

function OpenTradesTab() {
  const { trades, currentSummary, setBottomTab } = useTerminal()
  const open = trades.filter(t => t.exit_bar == null || t.exit_price == null)
  if (open.length === 0 && trades.length > 0) {
    return (
      <div style={{ padding: '12px 12px', color: 'var(--t-text-3)', fontSize: 11, fontFamily: 'var(--t-font-mono)' }}>
        Нет открытых сделок — все позиции закрыты.{' '}
        <span style={{ color: 'var(--t-accent)', cursor: 'pointer' }} onClick={() => setBottomTab('history')}>
          История сделок →
        </span>
      </div>
    )
  }
  return <TradeTable trades={open} ticker={currentSummary?.ticker} />
}

// ── История сделок ────────────────────────────────────────────────────────────

function TradeHistoryTab() {
  const { trades, currentSummary } = useTerminal()
  const closed = trades.filter(t => t.exit_bar != null && t.exit_price != null)
  return <TradeTable trades={closed} ticker={currentSummary?.ticker} />
}

// ── Активные позиции ──────────────────────────────────────────────────────────

function PositionsTab() {
  const { paper, reports } = useTerminal()
  if (paper) {
    return (
      <div style={{ padding: '8px 12px' }}>
        <div style={{ fontSize: 10, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)', marginBottom: 6 }}>
          Бумажный портфель · {paper.open_positions} позиций открыто
        </div>
        <table className="t-table" style={{ width: '100%' }}>
          <thead>
            <tr>
              {['Инструмент', 'Стратегия', 'Тип', 'PnL%', 'Статус'].map(h => (
                <th key={h} style={{ textAlign: 'left', padding: '4px 8px', color: 'var(--t-text-3)', fontSize: 9, fontFamily: 'var(--t-font-mono)', fontWeight: 400, background: 'var(--t-panel)', borderBottom: '1px solid var(--t-border)' }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {reports.map(r => (
              <tr key={r.report_id} className="t-table-row">
                <td style={{ fontSize: 10, fontFamily: 'var(--t-font-mono)', padding: '4px 8px', color: 'var(--t-text)' }}>{r.ticker}</td>
                <td style={{ fontSize: 9, padding: '4px 8px', color: 'var(--t-text-3)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 120 }}>
                  {r.hypothesis_id.replace('tmpl_h_', '')}
                </td>
                <td style={{ fontSize: 10, fontFamily: 'var(--t-font-mono)', padding: '4px 8px', color: 'var(--t-cyan)' }}>LONG</td>
                <td style={{ fontSize: 10, fontFamily: 'var(--t-font-mono)', padding: '4px 8px', color: pnlColor(r.total_return_pct), fontWeight: 600 }}>
                  {r.total_return_pct >= 0 ? '+' : ''}{r.total_return_pct.toFixed(2)}%
                </td>
                <td style={{ fontSize: 9, fontFamily: 'var(--t-font-mono)', padding: '4px 8px', color: 'var(--t-amber)' }}>STANDBY</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }
  return (
    <div style={{ padding: '10px 12px' }}>
      <div style={{ fontSize: 11, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)', marginBottom: 8 }}>
        Нет активных позиций · Бумажный режим: Standby
      </div>
      {reports.length > 0 && (
        <div style={{ fontSize: 10, color: 'var(--t-text-3)' }}>
          {reports.length} стратег{reports.length === 1 ? 'ия' : 'ии'} готов{reports.length === 1 ? 'а' : 'ы'} к бумажной торговле
        </div>
      )}
    </div>
  )
}

// ── Журнал событий ────────────────────────────────────────────────────────────

const LEVEL_COLOR: Record<string, string> = {
  INFO: 'var(--t-text-3)', WARNING: 'var(--t-amber)', ERROR: 'var(--t-red)', SUCCESS: 'var(--t-green)',
}
const LEVEL_RU: Record<string, string> = {
  INFO: 'ИНФО', WARNING: 'ПРЕДУПР', ERROR: 'ОШИБКА', SUCCESS: 'ОК',
}

function EventLogTab() {
  const { activity } = useTerminal()
  if (activity.length === 0) {
    return (
      <div style={{ padding: '14px 12px', fontSize: 11, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)' }}>
        Нет событий
      </div>
    )
  }
  return (
    <table className="t-table" style={{ width: '100%' }}>
      <thead>
        <tr>
          {['Время', 'Уровень', 'Статус', 'Событие'].map(h => (
            <th key={h} style={{ textAlign: 'left', padding: '4px 8px', color: 'var(--t-text-3)', fontSize: 9, fontFamily: 'var(--t-font-mono)', fontWeight: 400, background: 'var(--t-panel)', borderBottom: '1px solid var(--t-border)', position: 'sticky', top: 0, zIndex: 1 }}>
              {h}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {[...activity].reverse().map((e: ActivityEvent, i) => {
          const level = (e.type ?? 'INFO').toUpperCase()
          const color = LEVEL_COLOR[level] ?? 'var(--t-text-3)'
          return (
            <tr key={i} className="t-table-row">
              <td style={{ fontSize: 9, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)', padding: '4px 8px', whiteSpace: 'nowrap', width: 70 }}>
                {e.timestamp ? new Date(e.timestamp).toLocaleTimeString('ru-RU', { hour12: false }) : '—'}
              </td>
              <td style={{ fontSize: 9, fontFamily: 'var(--t-font-mono)', padding: '4px 8px', color, fontWeight: 700, width: 64 }}>
                {LEVEL_RU[level] ?? level}
              </td>
              <td style={{ fontSize: 9, color: 'var(--t-accent)', fontFamily: 'var(--t-font-mono)', padding: '4px 8px', width: 80, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {e.status}
              </td>
              <td style={{ fontSize: 10, color: 'var(--t-text-2)', padding: '4px 8px', lineHeight: 1.4 }}>
                {e.title}{e.detail ? ` — ${e.detail}` : ''}
              </td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

// ── AI Brain ──────────────────────────────────────────────────────────────────

function AIBrainBottomTab() {
  const { reports, status, decisions } = useTerminal()
  return (
    <div style={{ padding: '10px 12px', display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12 }}>
      <div>
        <div style={{ fontSize: 9, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)', marginBottom: 6, letterSpacing: 0.5 }}>ГИПОТЕЗЫ</div>
        {status ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {[
              { label: 'Зарег.',    v: status.hypotheses.registered },
              { label: 'Протест.',  v: status.hypotheses.tested },
              { label: 'Одобрено', v: status.candidates.approved_for_paper, color: 'var(--t-green)' },
              { label: 'Сессий',   v: status.research.sessions },
            ].map(r => (
              <div key={r.label} style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ fontSize: 9, color: 'var(--t-text-3)' }}>{r.label}</span>
                <span style={{ fontSize: 10, fontFamily: 'var(--t-font-mono)', color: r.color ?? 'var(--t-text-2)' }}>{r.v}</span>
              </div>
            ))}
          </div>
        ) : <div style={{ fontSize: 10, color: 'var(--t-text-3)' }}>Загрузка…</div>}
      </div>
      <div>
        <div style={{ fontSize: 9, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)', marginBottom: 6, letterSpacing: 0.5 }}>СТРАТЕГИИ</div>
        {reports.length === 0
          ? <div style={{ fontSize: 10, color: 'var(--t-text-3)' }}>Нет отчётов</div>
          : <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {reports.slice(0, 4).map(r => (
                <div key={r.report_id} style={{ display: 'flex', justifyContent: 'space-between', gap: 4 }}>
                  <span style={{ fontSize: 9, color: 'var(--t-text-3)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>
                    {r.ticker} · {r.hypothesis_id.replace('tmpl_h_', '').slice(0, 10)}
                  </span>
                  <span style={{ fontSize: 9, fontFamily: 'var(--t-font-mono)', color: pnlColor(r.total_return_pct), flexShrink: 0 }}>
                    {r.total_return_pct >= 0 ? '+' : ''}{r.total_return_pct.toFixed(1)}%
                  </span>
                </div>
              ))}
            </div>
        }
      </div>
      <div>
        <div style={{ fontSize: 9, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)', marginBottom: 6, letterSpacing: 0.5 }}>ПОСЛЕДНИЕ РЕШЕНИЯ</div>
        {decisions.length === 0
          ? <div style={{ fontSize: 10, color: 'var(--t-text-3)' }}>Нет решений</div>
          : <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {decisions.slice(0, 4).map(d => {
                const c = d.type === 'APPROVE' ? 'var(--t-green)' : (d.type === 'REJECT' || d.type === 'ARCHIVE') ? 'var(--t-red)' : 'var(--t-amber)'
                const lbl: Record<string, string> = { APPROVE: 'ОДОБРЕНО', REJECT: 'ОТКЛОНЕНО', ARCHIVE: 'В АРХИВ', REQUEST_MORE_EVIDENCE: 'ДАННЫЕ', MONITOR: 'НАБЛЮД.' }
                return (
                  <div key={d.id} style={{ display: 'flex', justifyContent: 'space-between', gap: 4 }}>
                    <span style={{ fontSize: 9, color: 'var(--t-text-3)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>
                      {d.hypothesis_title}
                    </span>
                    <span style={{ fontSize: 9, fontFamily: 'var(--t-font-mono)', color: c, flexShrink: 0 }}>{lbl[d.type] ?? d.type}</span>
                  </div>
                )
              })}
            </div>
        }
      </div>
    </div>
  )
}

// ── Вкладки ───────────────────────────────────────────────────────────────────

const BOTTOM_TABS: { id: BottomTab; label: string }[] = [
  { id: 'trades',    label: 'Сделки'           },
  { id: 'history',   label: 'История сделок'   },
  { id: 'positions', label: 'Активные позиции' },
  { id: 'activity',  label: 'Журнал событий'   },
  { id: 'aibrain',   label: 'AI Brain'         },
]

// ── Root ──────────────────────────────────────────────────────────────────────

export default function BottomPanel() {
  const { bottomTab, setBottomTab, trades } = useTerminal()

  const renderTab = () => {
    switch (bottomTab) {
      case 'trades':    return <OpenTradesTab />
      case 'history':   return <TradeHistoryTab />
      case 'positions': return <PositionsTab />
      case 'activity':  return <EventLogTab />
      case 'aibrain':   return <AIBrainBottomTab />
      default:          return null
    }
  }

  const closedCount = trades.filter(t => t.exit_bar != null).length

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', background: 'var(--t-bg)', borderTop: '1px solid var(--t-border)' }}>
      <div style={{ display: 'flex', flexShrink: 0, borderBottom: '1px solid var(--t-border)', background: 'var(--t-panel)', overflowX: 'auto' }}>
        {BOTTOM_TABS.map(t => {
          const isActive = bottomTab === t.id
          const badge = t.id === 'history' && closedCount > 0 ? closedCount : null
          return (
            <button
              key={t.id}
              onClick={() => setBottomTab(t.id)}
              style={{
                padding: '0 14px', height: 28, border: 'none', background: 'none',
                cursor: 'pointer', fontSize: 10, fontFamily: 'var(--t-font-mono)',
                color: isActive ? 'var(--t-text)' : 'var(--t-text-3)',
                borderBottom: `2px solid ${isActive ? 'var(--t-accent)' : 'transparent'}`,
                flexShrink: 0, whiteSpace: 'nowrap', letterSpacing: 0.2,
                display: 'flex', alignItems: 'center', gap: 5,
              }}
            >
              {t.label}
              {badge !== null && (
                <span style={{ fontSize: 8, padding: '1px 4px', borderRadius: 8, background: isActive ? 'var(--t-accent-soft)' : 'var(--t-elevated)', color: isActive ? 'var(--t-accent)' : 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)' }}>
                  {badge}
                </span>
              )}
            </button>
          )
        })}
      </div>
      <ScrollArea style={{ flex: 1 }} scrollbarSize={3}>
        {renderTab()}
      </ScrollArea>
    </div>
  )
}
