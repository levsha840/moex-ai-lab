import { ScrollArea } from '@mantine/core'
import { useTerminal, type BottomTab } from '../../context/TerminalContext'
import type { JournalEntry, ActivityEvent } from '../../api/client'

// ── Цвет PnL ─────────────────────────────────────────────────────────────────

function pnlColor(v: number) { return v >= 0 ? 'var(--t-green)' : 'var(--t-red)' }

// ── Таблица сделок ────────────────────────────────────────────────────────────

const COL_TRADES = [
  { key: '#',            w: 28 },
  { key: 'Инструмент',  w: 70 },
  { key: 'Направление', w: 68 },
  { key: 'Вход ₽',      w: 70 },
  { key: 'Выход ₽',     w: 70 },
  { key: 'PnL%',        w: 56 },
  { key: 'PnL ₽',       w: 64 },
  { key: 'Капитал',     w: 80 },
  { key: 'Причина',     w: 80 },
  { key: 'Рез.',        w: 34 },
]

function TradeTable({ trades, ticker }: { trades: JournalEntry[]; ticker: string | undefined }) {
  if (trades.length === 0) {
    return (
      <div style={{ padding: '16px 12px', fontSize: 11, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)' }}>
        Нет данных сделок
      </div>
    )
  }

  const dirLabel = (t: JournalEntry) => {
    const s = (t as any).direction ?? 'LONG'
    return s === 'SHORT' ? 'SHORT' : 'LONG'
  }

  return (
    <table className="t-table" style={{ tableLayout: 'fixed', width: '100%' }}>
      <colgroup>
        {COL_TRADES.map(c => <col key={c.key} style={{ width: c.w }} />)}
      </colgroup>
      <thead>
        <tr>
          {COL_TRADES.map(c => (
            <th key={c.key} style={{ textAlign: 'left', padding: '5px 8px', color: 'var(--t-text-3)', fontSize: 9, fontFamily: 'var(--t-font-mono)', fontWeight: 400, background: 'var(--t-panel)', letterSpacing: 0.3 }}>
              {c.key}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {trades.map((t, i) => {
          const dir = dirLabel(t)
          const dirColor = dir === 'SHORT' ? 'var(--t-red)' : 'var(--t-cyan)'
          return (
            <tr key={t.trade_id ?? i} className="t-table-row">
              <td style={{ fontSize: 10, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)', padding: '4px 8px' }}>{i + 1}</td>
              <td style={{ fontSize: 10, color: 'var(--t-text)', fontFamily: 'var(--t-font-mono)', padding: '4px 8px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{ticker ?? '—'}</td>
              <td style={{ fontSize: 10, fontFamily: 'var(--t-font-mono)', padding: '4px 8px', color: dirColor, fontWeight: 600 }}>{dir}</td>
              <td style={{ fontSize: 10, fontFamily: 'var(--t-font-mono)', padding: '4px 8px', color: 'var(--t-text-2)' }}>{t.entry_price.toFixed(2)}</td>
              <td style={{ fontSize: 10, fontFamily: 'var(--t-font-mono)', padding: '4px 8px', color: 'var(--t-text-2)' }}>{t.exit_price?.toFixed(2) ?? '—'}</td>
              <td style={{ fontSize: 10, fontFamily: 'var(--t-font-mono)', padding: '4px 8px', fontWeight: 600, color: pnlColor(t.pnl_pct ?? t.pnl ?? 0) }}>
                {((t.pnl_pct ?? 0) >= 0 ? '+' : '')}{(t.pnl_pct ?? 0).toFixed(2)}%
              </td>
              <td style={{ fontSize: 10, fontFamily: 'var(--t-font-mono)', padding: '4px 8px', color: pnlColor(t.pnl ?? 0) }}>
                {(t.pnl ?? 0) >= 0 ? '+' : ''}{(t.pnl ?? 0).toFixed(0)} ₽
              </td>
              <td style={{ fontSize: 10, fontFamily: 'var(--t-font-mono)', padding: '4px 8px', color: 'var(--t-text-2)' }}>
                {t.capital_after?.toFixed(0) ?? '—'}
              </td>
              <td style={{ fontSize: 9, color: 'var(--t-text-3)', padding: '4px 8px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {t.exit_reason ?? '—'}
              </td>
              <td style={{ fontSize: 10, fontFamily: 'var(--t-font-mono)', padding: '4px 8px', fontWeight: 700, color: t.is_winner ? 'var(--t-green)' : 'var(--t-red)' }}>
                {t.is_winner ? 'W' : 'L'}
              </td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

// ── Вкладка «Сделки» (открытые) ──────────────────────────────────────────────

function OpenTradesTab() {
  const { trades, currentSummary, setBottomTab } = useTerminal()
  const open = trades.filter(t => t.exit_bar == null || t.exit_price == null)
  if (open.length === 0 && trades.length > 0) {
    return (
      <div style={{ padding: '16px 12px', color: 'var(--t-text-3)', fontSize: 11, fontFamily: 'var(--t-font-mono)' }}>
        Нет открытых сделок — все позиции закрыты.{' '}
        <span style={{ color: 'var(--t-accent)', cursor: 'pointer' }} onClick={() => setBottomTab('history')}>
          Смотрите «История сделок»
        </span>
      </div>
    )
  }
  return <TradeTable trades={open} ticker={currentSummary?.ticker} />
}

// ── Вкладка «Журнал событий» ──────────────────────────────────────────────────

const LEVEL_COLOR: Record<string, string> = {
  INFO:    'var(--t-text-3)',
  WARNING: 'var(--t-amber)',
  ERROR:   'var(--t-red)',
  SUCCESS: 'var(--t-green)',
}
const LEVEL_RU: Record<string, string> = {
  INFO: 'ИНФО', WARNING: 'ПРЕДУПР', ERROR: 'ОШИБКА', SUCCESS: 'ОК',
}

function EventLogTab() {
  const { activity } = useTerminal()
  if (activity.length === 0) {
    return (
      <div style={{ padding: '16px 12px', fontSize: 11, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)' }}>
        Нет событий
      </div>
    )
  }
  return (
    <table className="t-table">
      <thead>
        <tr>
          {['Время', 'Уровень', 'Агент', 'Событие'].map(h => (
            <th key={h} style={{ textAlign: 'left', padding: '5px 8px', color: 'var(--t-text-3)', fontSize: 9, fontFamily: 'var(--t-font-mono)', fontWeight: 400, background: 'var(--t-panel)' }}>
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
                {e.title} {e.detail ? `— ${e.detail}` : ''}
              </td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

// ── Вкладка «История сделок» ──────────────────────────────────────────────────

function TradeHistoryTab() {
  const { trades, currentSummary } = useTerminal()
  const closed = trades.filter(t => t.exit_bar != null && t.exit_price != null)
  return <TradeTable trades={closed} ticker={currentSummary?.ticker} />
}

// ── Вкладка «Активные позиции» ────────────────────────────────────────────────

function PositionsTab() {
  const { paper, reports } = useTerminal()
  if (paper) {
    return (
      <div style={{ padding: '10px 12px' }}>
        <div style={{ fontSize: 11, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)', marginBottom: 6 }}>
          Бумажный портфель · {paper.open_positions} позиций открыто
        </div>
        <table className="t-table">
          <thead>
            <tr>
              {['Инструмент', 'Стратегия', 'Тип', 'PnL%', 'Статус'].map(h => (
                <th key={h} style={{ textAlign: 'left', padding: '5px 8px', color: 'var(--t-text-3)', fontSize: 9, fontFamily: 'var(--t-font-mono)', fontWeight: 400, background: 'var(--t-panel)' }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {reports.map(r => (
              <tr key={r.report_id} className="t-table-row">
                <td style={{ fontSize: 10, fontFamily: 'var(--t-font-mono)', padding: '4px 8px', color: 'var(--t-text)' }}>{r.ticker}</td>
                <td style={{ fontSize: 9, padding: '4px 8px', color: 'var(--t-text-3)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 120 }}>{r.hypothesis_id.replace('tmpl_h_', '')}</td>
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
      <div style={{ fontSize: 11, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)', marginBottom: 10 }}>
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

// ── Вкладка «AI Brain» ────────────────────────────────────────────────────────

function AIBrainBottomTab() {
  const { reports, status, decisions } = useTerminal()
  return (
    <div style={{ padding: '10px 12px', display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10 }}>
      <div>
        <div style={{ fontSize: 9, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)', marginBottom: 6, letterSpacing: 0.5 }}>ГИПОТЕЗЫ</div>
        {status ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {[
              { label: 'Зарег.',   v: status.hypotheses.registered },
              { label: 'Протест.', v: status.hypotheses.tested },
              { label: 'Одобрено',v: status.candidates.approved_for_paper, color: 'var(--t-green)' },
              { label: 'Сессий',  v: status.research.sessions },
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
                  <span style={{ fontSize: 9, color: 'var(--t-text-3)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1, marginRight: 6 }}>
                    {r.ticker} · {r.hypothesis_id.replace('tmpl_h_', '').slice(0, 10)}…
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
                const c = d.type === 'APPROVE' ? 'var(--t-green)' : d.type === 'REJECT' || d.type === 'ARCHIVE' ? 'var(--t-red)' : 'var(--t-amber)'
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
  { id: 'trades',    label: 'Сделки'          },
  { id: 'history',   label: 'История сделок'  },
  { id: 'positions', label: 'Активные позиции' },
  { id: 'activity',  label: 'Журнал событий'  },
  { id: 'aibrain',   label: 'AI Brain'        },
]

// ── Root ──────────────────────────────────────────────────────────────────────

export default function BottomPanel() {
  const { bottomTab, setBottomTab } = useTerminal()

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

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', background: 'var(--t-bg)', borderTop: '1px solid var(--t-border)' }}>
      <div style={{ display: 'flex', flexShrink: 0, borderBottom: '1px solid var(--t-border)', background: 'var(--t-panel)', overflowX: 'auto' }}>
        {BOTTOM_TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setBottomTab(t.id)}
            style={{
              padding: '0 14px', height: 30, border: 'none', background: 'none',
              cursor: 'pointer', fontSize: 10, fontFamily: 'var(--t-font-mono)',
              color: bottomTab === t.id ? 'var(--t-text)' : 'var(--t-text-3)',
              borderBottom: `2px solid ${bottomTab === t.id ? 'var(--t-accent)' : 'transparent'}`,
              flexShrink: 0, whiteSpace: 'nowrap', letterSpacing: 0.2,
            }}
          >
            {t.label}
          </button>
        ))}
      </div>
      <ScrollArea style={{ flex: 1 }} scrollbarSize={3}>
        {renderTab()}
      </ScrollArea>
    </div>
  )
}
