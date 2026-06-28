import { useState, useEffect } from 'react'
import {
  IconChartCandle, IconDatabase, IconCircleDot,
  IconPlayerPlay, IconBriefcase, IconShield,
  IconFileText, IconSettings, IconHistory,
  IconTestPipe,
} from '@tabler/icons-react'
import { useTerminal, type TopTab, type BottomTab } from '../../context/TerminalContext'
import LeftPanel from '../panels/LeftPanel'
import RightPanel from '../panels/RightPanel'
import BottomPanel from '../panels/BottomPanel'
import MainChart from '../chart/MainChart'
import ReplayOverlay from '../overlays/ReplayOverlay'
import EquityFullscreen from '../overlays/EquityFullscreen'
import { lazy, Suspense } from 'react'
const KnowledgeMap  = lazy(() => import('../../pages/KnowledgeMap'))
const HistoryPage   = lazy(() => import('../../pages/HistoryPage'))
const BacktestsPage = lazy(() => import('../../pages/BacktestsPage'))
const PortfolioPage = lazy(() => import('../../pages/PortfolioPage'))
const RisksPage     = lazy(() => import('../../pages/RisksPage'))
const SettingsPage  = lazy(() => import('../../pages/SettingsPage'))

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type NavItem = { id: string; label: string; icon: React.ComponentType<any>; tab: TopTab; bottom?: BottomTab }

const NAV_ITEMS: NavItem[] = [
  { id: 'terminal',  label: 'Торговый терминал', icon: IconChartCandle,  tab: 'terminal'  },
  { id: 'strategy',  label: 'Стратегии',          icon: IconDatabase,     tab: 'strategy'  },
  { id: 'history',   label: 'История торгов',     icon: IconHistory,      tab: 'history' },
  { id: 'backtests', label: 'Бэктесты',           icon: IconTestPipe,     tab: 'backtests' },
  { id: 'portfolio', label: 'Портфель',            icon: IconBriefcase,    tab: 'portfolio' },
  { id: 'risks',     label: 'Риски',               icon: IconShield,       tab: 'risks'     },
  { id: 'reports',   label: 'Отчёты',             icon: IconFileText,     tab: 'reports'   },
  { id: 'settings',  label: 'Настройки',           icon: IconSettings,     tab: 'settings'  },
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
  const { activeTab, setActiveTab, setBottomTab, replayActive, setReplayActive, currentSummary } = useTerminal()
  const [activeNav, setActiveNav] = useState('terminal')

  const handleNav = (item: NavItem) => {
    setActiveNav(item.id)
    setActiveTab(item.tab)
    if (item.bottom) setBottomTab(item.bottom)
  }

  useEffect(() => {
    const map: Partial<Record<string, string>> = {
      terminal: 'terminal', strategy: 'strategy',
      history: 'history', backtests: 'backtests', portfolio: 'portfolio',
      risks: 'risks', reports: 'reports', scientist: 'reports', settings: 'settings',
    }
    const nav = map[activeTab]
    if (nav !== undefined) setActiveNav(nav)
  }, [activeTab])

  return (
    <div style={{
      height: 36, flexShrink: 0, display: 'flex', alignItems: 'center',
      background: 'var(--t-panel)', borderBottom: '1px solid var(--t-border)',
      padding: '0 10px', gap: 0,
    }}>
      {/* Логотип */}
      <div style={{
        fontFamily: 'var(--t-font-mono)', fontWeight: 700, fontSize: 12,
        color: 'var(--t-accent)', letterSpacing: 2, marginRight: 16, flexShrink: 0,
        display: 'flex', alignItems: 'center', gap: 6,
      }}>
        <IconCircleDot size={12} />
        MOEX AI LAB
      </div>

      {/* 8 навигационных вкладок */}
      {NAV_ITEMS.map(item => {
        const isActive = activeNav === item.id
        return (
          <button
            key={item.id}
            onClick={() => handleNav(item)}
            style={{
              display: 'flex', alignItems: 'center', gap: 4,
              height: 36, padding: '0 9px', border: 'none', background: 'none',
              cursor: 'pointer', fontSize: 10, fontFamily: 'var(--t-font-mono)',
              color: isActive ? 'var(--t-text)' : 'var(--t-text-3)',
              borderBottom: `2px solid ${isActive ? 'var(--t-accent)' : 'transparent'}`,
              marginBottom: -1, letterSpacing: 0.2, whiteSpace: 'nowrap', flexShrink: 0,
            }}
          >
            <item.icon size={10} />
            {item.label}
          </button>
        )
      })}

      <div style={{ flex: 1 }} />

      {/* Текущий инструмент */}
      {currentSummary && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginRight: 12, padding: '0 8px', background: 'var(--t-elevated)', borderRadius: 3, height: 22, flexShrink: 0 }}>
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
      <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginRight: 12, flexShrink: 0 }}>
        <span className="t-dot green pulse" />
        <span style={{ fontSize: 9, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)' }}>Исследование</span>
        <span className="t-dot amber" style={{ marginLeft: 4 }} />
        <span style={{ fontSize: 9, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)' }}>Бумажный</span>
        <span style={{ marginLeft: 4, width: 6, height: 6, borderRadius: '50%', background: 'var(--t-red)', display: 'inline-block' }} />
        <span style={{ fontSize: 9, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)' }}>Live: Блок.</span>
      </div>

      {/* Воспроизведение (иконка) */}
      <button
        onClick={() => setReplayActive(!replayActive)}
        title="Воспроизведение"
        style={{
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          width: 24, height: 24,
          border: `1px solid ${replayActive ? 'var(--t-amber)' : 'var(--t-border)'}`,
          borderRadius: 3,
          background: replayActive ? 'rgba(255,184,0,0.1)' : 'var(--t-elevated)',
          cursor: 'pointer',
          color: replayActive ? 'var(--t-amber)' : 'var(--t-text-3)',
          marginRight: 10, flexShrink: 0,
        }}
      >
        <IconPlayerPlay size={11} />
      </button>

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
      height: 30, flexShrink: 0,
      display: 'flex', alignItems: 'center',
      background: 'var(--t-panel)', borderBottom: '1px solid var(--t-border)',
      padding: '0 10px', gap: 8,
    }}>
      {currentSummary ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--t-text)', fontFamily: 'var(--t-font-mono)' }}>
            {currentSummary.ticker}
          </span>
          <span style={{ fontSize: 9, color: 'var(--t-text-3)', padding: '1px 4px', background: 'var(--t-elevated)', borderRadius: 2, border: '1px solid var(--t-border)' }}>
            MOEX
          </span>
          {lastCandle && (
            <span style={{ fontSize: 12, fontWeight: 600, fontFamily: 'var(--t-font-mono)', color: 'var(--t-text)' }}>
              {lastCandle.close.toFixed(2)}
            </span>
          )}
          {change !== null && (
            <span style={{ fontSize: 10, fontFamily: 'var(--t-font-mono)', color: change >= 0 ? 'var(--t-green)' : 'var(--t-red)', fontWeight: 600 }}>
              {change >= 0 ? '+' : ''}{change.toFixed(2)}%
            </span>
          )}
        </div>
      ) : (
        <span style={{ fontSize: 10, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)' }}>Выберите инструмент</span>
      )}

      <div style={{ width: 1, height: 14, background: 'var(--t-border)' }} />

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

      <div style={{ width: 1, height: 14, background: 'var(--t-border)' }} />

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

  const PAGE_STYLE: React.CSSProperties = { flex: 1, minHeight: 0, overflow: 'hidden' }

  if (activeTab === 'knowledge') {
    return (
      <div style={{ flex: 1, minHeight: 0, overflow: 'hidden', position: 'relative' }}>
        <Suspense fallback={<div style={{ padding: 20, color: 'var(--t-text-3)', fontSize: 11 }}>Загрузка…</div>}>
          <KnowledgeMap />
        </Suspense>
      </div>
    )
  }

  const PageFallback = () => (
    <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--t-text-3)', fontSize: 10, fontFamily: 'var(--t-font-mono)' }}>
      Загрузка…
    </div>
  )

  if (activeTab === 'history')   return <div style={PAGE_STYLE}><Suspense fallback={<PageFallback />}><HistoryPage /></Suspense></div>
  if (activeTab === 'backtests') return <div style={PAGE_STYLE}><Suspense fallback={<PageFallback />}><BacktestsPage /></Suspense></div>
  if (activeTab === 'portfolio') return <div style={PAGE_STYLE}><Suspense fallback={<PageFallback />}><PortfolioPage /></Suspense></div>
  if (activeTab === 'risks')     return <div style={PAGE_STYLE}><Suspense fallback={<PageFallback />}><RisksPage /></Suspense></div>
  if (activeTab === 'settings')  return <div style={PAGE_STYLE}><Suspense fallback={<PageFallback />}><SettingsPage /></Suspense></div>

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0, overflow: 'hidden' }}>
      <ChartToolbar />
      <div style={{ flex: 65, minHeight: 0, overflow: 'hidden' }}>
        {candles.length === 0 ? (
          <div style={{ height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: 'var(--t-text-3)', fontSize: 12, gap: 12 }}>
            <IconChartCandle size={40} style={{ opacity: 0.15 }} />
            <div style={{ fontFamily: 'var(--t-font-mono)' }}>Выберите инструмент на левой панели</div>
          </div>
        ) : (
          <MainChart candles={candles} trades={trades} upToBar={upToBar} />
        )}
      </div>
      <div style={{ flex: 35, minHeight: 0, overflow: 'hidden' }}>
        <BottomPanel />
      </div>
    </div>
  )
}

const FULL_WIDTH_TABS = new Set(['history', 'backtests', 'portfolio', 'risks', 'settings'])

export default function AppLayout() {
  const { activeTab } = useTerminal()
  const fullWidth = FULL_WIDTH_TABS.has(activeTab)

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', overflow: 'hidden', background: 'var(--t-bg)' }}>
      <TopBar />
      <div style={{
        flex: 1, display: 'grid',
        gridTemplateColumns: fullWidth ? '210px 1fr' : '210px 1fr 290px',
        minHeight: 0, overflow: 'hidden',
      }}>
        <LeftPanel />
        <CenterPanel />
        {!fullWidth && <RightPanel />}
      </div>
      <ReplayOverlay />
      <EquityFullscreen />
    </div>
  )
}
