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

// Knowledge map stays from the original page (lazy import)
import { lazy, Suspense } from 'react'
const KnowledgeMap = lazy(() => import('../../pages/KnowledgeMap'))

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const TABS: { id: TopTab | 'replay'; label: string; icon: React.ComponentType<any> }[] = [
  { id: 'terminal',  label: 'TERMINAL',  icon: IconChartCandle },
  { id: 'strategy',  label: 'STRATEGY',  icon: IconDatabase    },
  { id: 'knowledge', label: 'KNOWLEDGE', icon: IconBrain       },
  { id: 'scientist', label: 'SCIENTIST', icon: IconUser        },
  { id: 'replay',    label: 'REPLAY',    icon: IconPlayerPlay  },
]

function Clock() {
  const [now, setNow] = useState(new Date())
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(id)
  }, [])
  return (
    <span style={{ color: 'var(--t-text-2)', fontFamily: 'var(--t-font-mono)', fontSize: 11 }}>
      {now.toLocaleTimeString('ru-RU', { hour12: false })} MSK
    </span>
  )
}

function TopBar() {
  const {
    activeTab, setActiveTab,
    replayActive, setReplayActive,
    status, currentSummary,
  } = useTerminal()

  const handleTab = (id: TopTab | 'replay') => {
    if (id === 'replay') {
      setReplayActive(!replayActive)
      return
    }
    setActiveTab(id)
  }

  const researchOk = status?.research?.sessions !== undefined

  return (
    <div style={{
      height: 36, flexShrink: 0,
      display: 'flex', alignItems: 'center',
      background: 'var(--t-panel)',
      borderBottom: '1px solid var(--t-border)',
      padding: '0 12px', gap: 2,
    }}>
      {/* Logo */}
      <div style={{
        fontFamily: 'var(--t-font-mono)', fontWeight: 700, fontSize: 12,
        color: 'var(--t-accent)', letterSpacing: 2, marginRight: 16, flexShrink: 0,
        display: 'flex', alignItems: 'center', gap: 6,
      }}>
        <IconCircleDot size={12} />
        MOEX AI LAB
      </div>

      {/* Tabs */}
      {TABS.map(t => {
        const isActive = t.id === 'replay' ? replayActive : activeTab === t.id
        return (
          <button
            key={t.id}
            onClick={() => handleTab(t.id)}
            style={{
              display: 'flex', alignItems: 'center', gap: 5,
              height: 36, padding: '0 12px', border: 'none',
              background: 'none', cursor: 'pointer',
              color: isActive ? 'var(--t-text)' : 'var(--t-text-3)',
              fontFamily: 'var(--t-font-mono)', fontSize: 10, letterSpacing: 0.8,
              borderBottom: `2px solid ${isActive ? (t.id === 'replay' ? 'var(--t-amber)' : 'var(--t-accent)') : 'transparent'}`,
              marginBottom: -1,
            }}
          >
            <t.icon size={11} />
            {t.label}
          </button>
        )
      })}

      <div style={{ flex: 1 }} />

      {/* Status chips */}
      {currentSummary && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginRight: 12 }}>
          <span style={{ fontSize: 9, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)' }}>
            {currentSummary.ticker}
          </span>
          <span style={{ fontSize: 9, color: 'var(--t-text-3)' }}>·</span>
          <span style={{ fontSize: 9, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)' }}>
            {currentSummary.period} {currentSummary.timeframe.toUpperCase()}
          </span>
        </div>
      )}

      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginRight: 12 }}>
        <span className="t-dot green pulse" />
        <span style={{ fontSize: 9, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)' }}>RESEARCH</span>
        <span className="t-dot amber" style={{ marginLeft: 8 }} />
        <span style={{ fontSize: 9, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)' }}>PAPER STANDBY</span>
        <span style={{ marginLeft: 8, width: 6, height: 6, borderRadius: '50%', background: 'var(--t-red)', display: 'inline-block', border: '1px solid var(--t-red)' }} />
        <span style={{ fontSize: 9, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)' }}>REAL: BLOCKED</span>
      </div>

      <Clock />
    </div>
  )
}

function CenterPanel() {
  const { candles, trades, replayActive, replayBar, activeTab } = useTerminal()
  const upToBar = replayActive ? replayBar : undefined

  // Knowledge map takes the whole center area
  if (activeTab === 'knowledge') {
    return (
      <div style={{ flex: 1, minHeight: 0, overflow: 'hidden', position: 'relative' }}>
        <Suspense fallback={<div style={{ padding: 20, color: 'var(--t-text-3)', fontSize: 11 }}>Loading knowledge graph…</div>}>
          <KnowledgeMap />
        </Suspense>
      </div>
    )
  }

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0, overflow: 'hidden' }}>
      {/* Chart area — 65% */}
      <div style={{ flex: 65, minHeight: 0, overflow: 'hidden' }}>
        {candles.length === 0 ? (
          <div style={{
            height: '100%', display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center',
            color: 'var(--t-text-3)', fontSize: 12,
          }}>
            <IconChartCandle size={32} style={{ marginBottom: 12, opacity: 0.3 }} />
            <div>Select an instrument from the left panel</div>
          </div>
        ) : (
          <MainChart candles={candles} trades={trades} upToBar={upToBar} />
        )}
      </div>
      {/* Bottom panel — 35% */}
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
      <div style={{ flex: 1, display: 'grid', gridTemplateColumns: '200px 1fr 280px', minHeight: 0, overflow: 'hidden' }}>
        <LeftPanel />
        <CenterPanel />
        <RightPanel />
      </div>
      <ReplayOverlay />
    </div>
  )
}
