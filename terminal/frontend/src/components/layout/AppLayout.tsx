import { useState, useEffect } from 'react'
import {
  IconChartCandle, IconDatabase, IconBrain, IconUser,
  IconPlayerPlay, IconCircleDot,
} from '@tabler/icons-react'
import { useTerminal, type TopTab } from '../../context/TerminalContext'
import LeftPanel from '../panels/LeftPanel'
import RightPanel from '../panels/RightPanel'
import BottomPanel from '../panels/BottomPanel'
import MainChart from '../chart/MainChart'
import ReplayOverlay from '../overlays/ReplayOverlay'
import EquityFullscreen from '../overlays/EquityFullscreen'
import { lazy, Suspense } from 'react'
const KnowledgeMap = lazy(() => import('../../pages/KnowledgeMap'))

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const TABS: { id: TopTab | 'replay'; label: string; icon: React.ComponentType<any> }[] = [
  { id: 'terminal',  label: 'Терминал',         icon: IconChartCandle },
  { id: 'strategy',  label: 'Стратегии',         icon: IconDatabase    },
  { id: 'knowledge', label: 'База знаний',        icon: IconBrain       },
  { id: 'scientist', label: 'Аналитика',          icon: IconUser        },
  { id: 'replay',    label: 'Воспроизведение',    icon: IconPlayerPlay  },
]

function Clock() {
  const [now, setNow] = useState(new Date())
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(id)
  }, [])
  return (
    <span style={{ color: 'var(--t-text-2)', fontFamily: 'var(--t-font-mono)', fontSize: 11 }}>
      {now.toLocaleTimeString('ru-RU', { hour12: false })} МСК
    </span>
  )
}

function TopBar() {
  const { activeTab, setActiveTab, replayActive, setReplayActive, currentSummary } = useTerminal()

  const handleTab = (id: TopTab | 'replay') => {
    if (id === 'replay') { setReplayActive(!replayActive); return }
    setActiveTab(id)
  }

  return (
    <div style={{
      height: 36, flexShrink: 0, display: 'flex', alignItems: 'center',
      background: 'var(--t-panel)', borderBottom: '1px solid var(--t-border)',
      padding: '0 10px', gap: 2,
    }}>
      {/* Логотип */}
      <div style={{
        fontFamily: 'var(--t-font-mono)', fontWeight: 700, fontSize: 12,
        color: 'var(--t-accent)', letterSpacing: 2, marginRight: 14, flexShrink: 0,
        display: 'flex', alignItems: 'center', gap: 6,
      }}>
        <IconCircleDot size={12} />
        MOEX AI LAB
      </div>

      {/* Вкладки */}
      {TABS.map(t => {
        const isActive = t.id === 'replay' ? replayActive : activeTab === t.id
        return (
          <button key={t.id} onClick={() => handleTab(t.id)} style={{
            display: 'flex', alignItems: 'center', gap: 4,
            height: 36, padding: '0 10px', border: 'none', background: 'none',
            cursor: 'pointer', fontSize: 10, fontFamily: 'var(--t-font-mono)',
            color: isActive ? 'var(--t-text)' : 'var(--t-text-3)',
            borderBottom: `2px solid ${isActive ? (t.id === 'replay' ? 'var(--t-amber)' : 'var(--t-accent)') : 'transparent'}`,
            marginBottom: -1, letterSpacing: 0.3,
          }}>
            <t.icon size={11} />
            {t.label}
          </button>
        )
      })}

      <div style={{ flex: 1 }} />

      {/* Текущий инструмент */}
      {currentSummary && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginRight: 14, padding: '0 8px', background: 'var(--t-elevated)', borderRadius: 3, height: 22 }}>
          <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--t-text)', fontFamily: 'var(--t-font-mono)' }}>
            {currentSummary.ticker}
          </span>
          <span style={{ fontSize: 9, color: 'var(--t-text-3)' }}>|</span>
          <span style={{ fontSize: 9, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)' }}>
            {currentSummary.period} {currentSummary.timeframe.toUpperCase()}
          </span>
        </div>
      )}

      {/* Статус системы */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginRight: 14 }}>
        <span className="t-dot green pulse" />
        <span style={{ fontSize: 9, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)' }}>Исследование</span>
        <span className="t-dot amber" style={{ marginLeft: 6 }} />
        <span style={{ fontSize: 9, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)' }}>Бумажный</span>
        <span style={{ marginLeft: 6, width: 6, height: 6, borderRadius: '50%', background: 'var(--t-red)', display: 'inline-block' }} />
        <span style={{ fontSize: 9, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)' }}>Реал: Блок.</span>
      </div>

      <Clock />
    </div>
  )
}

function ChartToolbar() {
  const { currentSummary, candles } = useTerminal()
  const lastCandle = candles[candles.length - 1]
  const prevCandle = candles[candles.length - 2]
  const change = lastCandle && prevCandle
    ? ((lastCandle.close - prevCandle.close) / prevCandle.close) * 100
    : null

  return (
    <div style={{
      height: 32, flexShrink: 0,
      display: 'flex', alignItems: 'center',
      background: 'var(--t-panel)', borderBottom: '1px solid var(--t-border)',
      padding: '0 10px', gap: 10,
    }}>
      {/* Тикер-бейдж */}
      {currentSummary ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--t-text)', fontFamily: 'var(--t-font-mono)' }}>
            {currentSummary.ticker}
          </span>
          <span style={{ fontSize: 9, color: 'var(--t-text-3)', padding: '1px 4px', background: 'var(--t-elevated)', borderRadius: 2 }}>
            MOEX
          </span>
          {lastCandle && (
            <span style={{ fontSize: 12, fontWeight: 700, fontFamily: 'var(--t-font-mono)', color: 'var(--t-text)' }}>
              {lastCandle.close.toFixed(2)}
            </span>
          )}
          {change !== null && (
            <span style={{
              fontSize: 10, fontFamily: 'var(--t-font-mono)',
              color: change >= 0 ? 'var(--t-green)' : 'var(--t-red)',
            }}>
              {change >= 0 ? '+' : ''}{change.toFixed(2)}%
            </span>
          )}
        </div>
      ) : (
        <span style={{ fontSize: 10, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)' }}>
          Выберите инструмент
        </span>
      )}

      <div style={{ width: 1, height: 16, background: 'var(--t-border)' }} />

      {/* Таймфреймы */}
      {['1ч', '4ч', '1д', '1н', '1м', '3м', '1г'].map((p, i) => (
        <button key={p} style={{
          padding: '2px 6px', borderRadius: 2,
          background: i === 0 ? 'var(--t-accent-soft)' : 'none',
          color: i === 0 ? 'var(--t-accent)' : 'var(--t-text-3)',
          fontSize: 10, cursor: 'pointer', fontFamily: 'var(--t-font-mono)',
          border: i === 0 ? '1px solid var(--t-accent)' : '1px solid transparent',
        } as React.CSSProperties}>
          {p}
        </button>
      ))}

      <div style={{ width: 1, height: 16, background: 'var(--t-border)' }} />

      {/* Индикаторы */}
      <span style={{ fontSize: 9, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)' }}>Индикаторы:</span>
      {['Объём', 'RSI', 'MACD', 'ATR'].map(ind => (
        <span key={ind} style={{
          fontSize: 9, padding: '1px 5px', borderRadius: 2,
          background: 'var(--t-elevated)', color: 'var(--t-cyan)',
          fontFamily: 'var(--t-font-mono)', border: '1px solid var(--t-border)',
        }}>
          {ind}
        </span>
      ))}

      <div style={{ flex: 1 }} />
      <span style={{ fontSize: 9, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)' }}>
        {candles.length > 0 ? `${candles.length} баров` : ''}
      </span>
    </div>
  )
}

function CenterPanel() {
  const { candles, trades, replayActive, replayBar, activeTab } = useTerminal()
  const upToBar = replayActive ? replayBar : undefined

  if (activeTab === 'knowledge') {
    return (
      <div style={{ flex: 1, minHeight: 0, overflow: 'hidden', position: 'relative' }}>
        <Suspense fallback={<div style={{ padding: 20, color: 'var(--t-text-3)', fontSize: 11 }}>Загрузка графа знаний…</div>}>
          <KnowledgeMap />
        </Suspense>
      </div>
    )
  }

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0, overflow: 'hidden' }}>
      <ChartToolbar />
      {/* График — 65% */}
      <div style={{ flex: 65, minHeight: 0, overflow: 'hidden' }}>
        {candles.length === 0 ? (
          <div style={{
            height: '100%', display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center',
            color: 'var(--t-text-3)', fontSize: 12,
          }}>
            <IconChartCandle size={40} style={{ marginBottom: 16, opacity: 0.2 }} />
            <div style={{ fontFamily: 'var(--t-font-mono)' }}>Выберите инструмент на левой панели</div>
          </div>
        ) : (
          <MainChart candles={candles} trades={trades} upToBar={upToBar} />
        )}
      </div>
      {/* Нижняя панель — 35% */}
      <div style={{ flex: 35, minHeight: 0, overflow: 'hidden' }}>
        <BottomPanel />
      </div>
    </div>
  )
}

export default function AppLayout() {
  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', overflow: 'hidden', background: 'var(--t-bg)' }}>
      <TopBar />
      <div style={{ flex: 1, display: 'grid', gridTemplateColumns: '210px 1fr 290px', minHeight: 0, overflow: 'hidden' }}>
        <LeftPanel />
        <CenterPanel />
        <RightPanel />
      </div>
      <ReplayOverlay />
      <EquityFullscreen />
    </div>
  )
}
