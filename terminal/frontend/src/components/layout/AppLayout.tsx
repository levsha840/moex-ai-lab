import { useState, useEffect } from 'react'
import { Routes, Route, useNavigate, useLocation } from 'react-router-dom'
import {
  IconLayoutDashboard, IconChartCandle, IconDatabase,
  IconWallet, IconBrain, IconUser, IconPlayerPlay,
  IconSearch, IconActivity, IconCircleDot,
} from '@tabler/icons-react'
import Dashboard from '../../pages/Dashboard'
import LiveResearch from '../../pages/LiveResearch'
import StrategyVault from '../../pages/StrategyVault'
import PaperPortfolio from '../../pages/PaperPortfolio'
import KnowledgeMap from '../../pages/KnowledgeMap'
import ChiefScientist from '../../pages/ChiefScientist'
import ReplayMode from '../../pages/ReplayMode'
import ExplainDecision from '../../pages/ExplainDecision'

const TABS = [
  { path: '/',           label: 'Dashboard',       icon: IconLayoutDashboard },
  { path: '/research',   label: 'Live Research',   icon: IconChartCandle     },
  { path: '/strategies', label: 'Strategy Vault',  icon: IconDatabase        },
  { path: '/paper',      label: 'Paper Portfolio', icon: IconWallet          },
  { path: '/knowledge',  label: 'Knowledge Map',   icon: IconBrain           },
  { path: '/scientist',  label: 'Chief Scientist', icon: IconUser            },
  { path: '/replay',     label: 'Replay',          icon: IconPlayerPlay      },
  { path: '/explain',    label: 'Explain',         icon: IconSearch          },
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

export default function AppLayout() {
  const navigate = useNavigate()
  const location = useLocation()

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: 'var(--t-bg)', overflow: 'hidden' }}>
      {/* ── Top Navigation Bar ── */}
      <div style={{
        display: 'flex', alignItems: 'center', height: 36,
        background: 'var(--t-panel)', borderBottom: '1px solid var(--t-border)',
        flexShrink: 0, userSelect: 'none',
      }}>
        {/* Logo */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8,
          padding: '0 16px', borderRight: '1px solid var(--t-border)',
          height: '100%', minWidth: 180, flexShrink: 0,
        }}>
          <IconActivity size={14} color="var(--t-accent)" />
          <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--t-text)', letterSpacing: 2 }}>
            MOEX AI LAB
          </span>
        </div>

        {/* Tabs */}
        <div style={{ display: 'flex', height: '100%', flex: 1, overflowX: 'auto' }}>
          {TABS.map(tab => {
            const Icon = tab.icon
            const active = tab.path === '/'
              ? location.pathname === '/'
              : location.pathname.startsWith(tab.path)
            return (
              <button
                key={tab.path}
                onClick={() => navigate(tab.path)}
                className={`t-tab ${active ? 'active' : ''}`}
                style={{ border: 'none', outline: 'none', cursor: 'pointer' }}
              >
                <Icon size={12} />
                {tab.label}
              </button>
            )
          })}
        </div>

        {/* Right side: status + clock */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: 14,
          padding: '0 14px', borderLeft: '1px solid var(--t-border)',
          height: '100%', flexShrink: 0,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <span className="t-dot green pulse" />
            <span style={{ fontSize: 10, color: 'var(--t-text-2)' }}>RESEARCH</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <span className="t-dot amber" />
            <span style={{ fontSize: 10, color: 'var(--t-text-2)' }}>PAPER STANDBY</span>
          </div>
          <div style={{ width: 1, height: 16, background: 'var(--t-border)' }} />
          <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <IconCircleDot size={10} color="var(--t-red)" />
            <span style={{ fontSize: 10, color: 'var(--t-red)' }}>REAL: BLOCKED</span>
          </div>
          <div style={{ width: 1, height: 16, background: 'var(--t-border)' }} />
          <Clock />
        </div>
      </div>

      {/* ── Content ── */}
      <div style={{ flex: 1, overflow: 'hidden' }}>
        <Routes>
          <Route path="/"           element={<Dashboard />} />
          <Route path="/research/*" element={<LiveResearch />} />
          <Route path="/strategies" element={<StrategyVault />} />
          <Route path="/paper"      element={<PaperPortfolio />} />
          <Route path="/knowledge"  element={<KnowledgeMap />} />
          <Route path="/scientist"  element={<ChiefScientist />} />
          <Route path="/replay"     element={<ReplayMode />} />
          <Route path="/explain"    element={<ExplainDecision />} />
        </Routes>
      </div>
    </div>
  )
}
