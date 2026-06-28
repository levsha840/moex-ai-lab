import { useState, useMemo } from 'react'
import { ScrollArea, TextInput } from '@mantine/core'
import { IconSearch, IconTrendingUp, IconTrendingDown } from '@tabler/icons-react'
import { useTerminal } from '../../context/TerminalContext'
import type { DatasetCell, ReportSummary } from '../../api/client'

// Словарь названий тикеров MOEX P1
const NAMES: Record<string, string> = {
  SBER: 'Сбербанк', GAZP: 'Газпром', LKOH: 'Лукойл', NVTK: 'НоваТЭК',
  ROSN: 'Роснефть', TATN: 'Татнефть', MGNT: 'Магнит', YNDX: 'Яндекс',
  MTSS: 'МТС', ALRS: 'Алроса', SNGS: 'Сургутнефтегаз', VTBR: 'ВТБ',
  GMKN: 'Норникель', AFLT: 'Аэрофлот', CHMF: 'Северсталь', NLMK: 'НЛМК',
  MAGN: 'ММК', IRAO: 'Интер РАО', PIKK: 'ПИК', MTLR: 'Мечел',
  RUAL: 'РУСАЛ', PHOR: 'ФосАгро', FEES: 'ФСК ЕЭС', MOEX: 'Мосбиржа',
  POLY: 'Полюс', PLZL: 'Полюс', CBOM: 'МКБ', TRNFP: 'Транснефть',
  SGZH: 'Сегежа', DSKY: 'Детский мир', BSPB: 'Банк СПб',
  HYDR: 'РусГидро', RTKM: 'Ростелеком', TCSG: 'TCS Group',
  MAIL: 'VK', OZON: 'Ozon', SMLT: 'Самолёт',
}

type LeftSubTab = 'instruments' | 'favorites' | 'sectors'

interface InstrumentRow {
  ticker: string
  name: string
  returnPct: number | null
  reportIdx: number | null
  period: string
  timeframe: string
}

function buildInstruments(
  datasets: DatasetCell[],
  reports: ReportSummary[],
): InstrumentRow[] {
  // Дедупликация по тикеру, берём первый датасет каждого тикера
  const seen = new Set<string>()
  const rows: InstrumentRow[] = []

  for (const d of datasets) {
    if (seen.has(d.ticker)) continue
    seen.add(d.ticker)
    const ri = reports.findIndex(r => r.ticker === d.ticker)
    rows.push({
      ticker: d.ticker,
      name: NAMES[d.ticker] ?? d.ticker,
      returnPct: ri >= 0 ? reports[ri].total_return_pct : null,
      reportIdx: ri >= 0 ? ri : null,
      period: d.period,
      timeframe: d.timeframe,
    })
  }

  // Тикеры с отчётами — первыми
  rows.sort((a, b) => {
    if (a.reportIdx !== null && b.reportIdx === null) return -1
    if (a.reportIdx === null && b.reportIdx !== null) return 1
    if (a.returnPct !== null && b.returnPct !== null) return b.returnPct - a.returnPct
    return a.ticker.localeCompare(b.ticker)
  })

  return rows
}

export default function LeftPanel() {
  const { datasets, reports, status, selectedIdx, setSelectedIdx } = useTerminal()
  const [subTab, setSubTab] = useState<LeftSubTab>('instruments')
  const [search, setSearch] = useState('')

  const instruments = useMemo(
    () => buildInstruments(datasets, reports),
    [datasets, reports]
  )

  const filtered = search.trim()
    ? instruments.filter(r =>
        r.ticker.toLowerCase().includes(search.toLowerCase()) ||
        r.name.toLowerCase().includes(search.toLowerCase())
      )
    : instruments

  const budget = status?.research_budget

  const SUB_TABS: { id: LeftSubTab; label: string }[] = [
    { id: 'instruments', label: 'Инструменты' },
    { id: 'favorites',   label: 'Избранное'   },
    { id: 'sectors',     label: 'Секторы'     },
  ]

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', height: '100%',
      background: 'var(--t-bg)', borderRight: '1px solid var(--t-border)',
    }}>
      {/* Заголовок РЫНОК */}
      <div style={{
        padding: '7px 10px 5px', flexShrink: 0,
        borderBottom: '1px solid var(--t-border)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: 1.5, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)' }}>
          РЫНОК
        </span>
        <span style={{ fontSize: 9, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)' }}>
          MOEX
        </span>
      </div>

      {/* Субтабы */}
      <div style={{ display: 'flex', flexShrink: 0, borderBottom: '1px solid var(--t-border)' }}>
        {SUB_TABS.map(t => (
          <button key={t.id} onClick={() => setSubTab(t.id)} style={{
            flex: 1, padding: '5px 2px', border: 'none', background: 'none',
            fontSize: 9, cursor: 'pointer', fontFamily: 'var(--t-font-mono)',
            color: subTab === t.id ? 'var(--t-text)' : 'var(--t-text-3)',
            borderBottom: `2px solid ${subTab === t.id ? 'var(--t-accent)' : 'transparent'}`,
          }}>
            {t.label}
          </button>
        ))}
      </div>

      {/* Поиск */}
      <div style={{ padding: '5px 8px', flexShrink: 0 }}>
        <TextInput
          placeholder="Поиск..."
          size="xs"
          value={search}
          onChange={e => setSearch(e.currentTarget.value)}
          leftSection={<IconSearch size={11} color="var(--t-text-3)" />}
          styles={{
            input: {
              background: 'var(--t-elevated)', border: '1px solid var(--t-border)',
              color: 'var(--t-text)', fontSize: 10, height: 26, minHeight: 26,
              '&::placeholder': { color: 'var(--t-text-3)' },
            },
          }}
        />
      </div>

      {/* Universe label */}
      <div style={{
        padding: '2px 10px 4px', flexShrink: 0,
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      }}>
        <span style={{ fontSize: 9, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)' }}>
          Universe P1
        </span>
        <span style={{ fontSize: 9, color: 'var(--t-accent)', fontFamily: 'var(--t-font-mono)' }}>
          {status?.datasets.total ?? datasets.length} инстр.
        </span>
      </div>

      {/* Список инструментов */}
      <div style={{
        flexShrink: 0, padding: '2px 0', background: 'var(--t-panel)',
        display: 'grid', gridTemplateColumns: '1fr auto auto',
        borderBottom: '1px solid var(--t-border)',
      }}>
        {['Инструмент', 'Тикер', 'Доходн.'].map(h => (
          <div key={h} style={{ padding: '3px 8px', fontSize: 9, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)', letterSpacing: 0.5 }}>
            {h}
          </div>
        ))}
      </div>

      <ScrollArea style={{ flex: 1 }} scrollbarSize={3}>
        {filtered.length === 0 && (
          <div style={{ padding: '12px 10px', fontSize: 10, color: 'var(--t-text-3)' }}>
            {search ? 'Не найдено' : 'Загрузка инструментов…'}
          </div>
        )}
        {filtered.map(row => {
          const isActive = row.reportIdx !== null && row.reportIdx === selectedIdx
          const hasReport = row.reportIdx !== null
          const ret = row.returnPct
          return (
            <div
              key={row.ticker}
              onClick={() => { if (hasReport) setSelectedIdx(row.reportIdx!) }}
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr auto auto',
                padding: '5px 8px',
                borderBottom: '1px solid var(--t-border-dim)',
                cursor: hasReport ? 'pointer' : 'default',
                background: isActive ? 'var(--t-elevated)' : 'transparent',
                borderLeft: `2px solid ${isActive ? 'var(--t-accent)' : 'transparent'}`,
              }}
              onMouseEnter={e => { if (!isActive && hasReport) (e.currentTarget as HTMLElement).style.background = 'var(--t-hover)' }}
              onMouseLeave={e => { if (!isActive) (e.currentTarget as HTMLElement).style.background = 'transparent' }}
            >
              {/* Название */}
              <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: 10, color: 'var(--t-text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontFamily: 'var(--t-font-mono)', fontWeight: isActive ? 700 : 400 }}>
                  {row.name}
                </div>
                {hasReport && (
                  <div style={{ fontSize: 8, color: 'var(--t-text-3)', marginTop: 1 }}>
                    {row.period} · {row.timeframe.toUpperCase()}
                  </div>
                )}
              </div>
              {/* Тикер */}
              <div style={{ padding: '0 6px', alignSelf: 'center' }}>
                <span style={{ fontSize: 9, color: 'var(--t-text-2)', fontFamily: 'var(--t-font-mono)', letterSpacing: 0.5 }}>
                  {row.ticker}
                </span>
              </div>
              {/* Доходность */}
              <div style={{ alignSelf: 'center', textAlign: 'right' }}>
                {ret !== null ? (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                    {ret >= 0
                      ? <IconTrendingUp size={9} color="var(--t-green)" />
                      : <IconTrendingDown size={9} color="var(--t-red)" />}
                    <span style={{
                      fontSize: 10, fontFamily: 'var(--t-font-mono)', fontWeight: 600,
                      color: ret >= 0 ? 'var(--t-green)' : 'var(--t-red)',
                    }}>
                      {ret >= 0 ? '+' : ''}{ret.toFixed(1)}%
                    </span>
                  </div>
                ) : (
                  <span style={{ fontSize: 9, color: 'var(--t-text-3)' }}>—</span>
                )}
              </div>
            </div>
          )
        })}
      </ScrollArea>

      {/* Состояние рынка */}
      <div style={{ flexShrink: 0 }}>
        <div className="t-section-title" style={{ fontSize: 8, letterSpacing: 1.5 }}>СОСТОЯНИЕ РЫНКА</div>
        <div style={{ padding: '6px 10px' }}>
          {[
            { label: 'Режим системы', value: status?.mode?.replace('_', ' ') ?? '—', dot: 'green' },
            { label: 'Статус', value: status?.status ?? '—', dot: 'green' },
            { label: 'Исследование', value: status ? 'Активно' : '—', dot: 'green' },
            { label: 'Торговля', value: 'STANDBY', dot: 'amber' },
            { label: 'Реал. торговля', value: 'ЗАБЛОКИРОВАНА', dot: 'red' },
          ].map(row => (
            <div key={row.label} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4, alignItems: 'center' }}>
              <span style={{ fontSize: 9, color: 'var(--t-text-3)' }}>{row.label}</span>
              <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <span className={`t-dot ${row.dot}`} style={{ width: 5, height: 5 }} />
                <span style={{ fontSize: 9, color: 'var(--t-text-2)', fontFamily: 'var(--t-font-mono)' }}>{row.value}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Быстрые действия */}
      <div style={{ flexShrink: 0 }}>
        <div className="t-section-title" style={{ fontSize: 8, letterSpacing: 1.5 }}>БЫСТРЫЕ ДЕЙСТВИЯ</div>
        <div style={{ padding: '6px 8px 8px', display: 'flex', flexDirection: 'column', gap: 4 }}>
          {budget && (
            <div style={{ marginBottom: 4 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
                <span style={{ fontSize: 9, color: 'var(--t-text-3)' }}>Бюджет исследования</span>
                <span style={{ fontSize: 9, color: 'var(--t-text-2)', fontFamily: 'var(--t-font-mono)' }}>
                  {budget.used}/{budget.total}
                </span>
              </div>
              <div style={{ height: 3, background: 'var(--t-elevated)', borderRadius: 2 }}>
                <div style={{
                  height: '100%', borderRadius: 2,
                  width: `${Math.min(budget.used / Math.max(budget.total, 1) * 100, 100)}%`,
                  background: budget.used / budget.total > 0.8 ? 'var(--t-red)' : 'var(--t-accent)',
                }} />
              </div>
            </div>
          )}
          {[
            { label: '+ Новая стратегия' },
            { label: '⬡ Запустить отчёт' },
          ].map(btn => (
            <button key={btn.label} style={{
              padding: '4px 8px', border: '1px solid var(--t-border)',
              background: 'var(--t-elevated)', color: 'var(--t-text-2)',
              fontSize: 9, cursor: 'pointer', borderRadius: 2, textAlign: 'left',
              fontFamily: 'var(--t-font-mono)',
            }}>
              {btn.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
