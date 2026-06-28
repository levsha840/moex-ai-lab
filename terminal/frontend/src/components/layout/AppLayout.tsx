import { AppShell, Burger, Group, Text, UnstyledButton, Badge, Stack, Divider, rem } from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { Routes, Route, useNavigate, useLocation } from 'react-router-dom'
import {
  IconLayoutDashboard, IconChartCandle, IconDatabase, IconWallet,
  IconBrain, IconUser, IconPlayerPlay, IconSearch, IconActivity,
} from '@tabler/icons-react'
import Dashboard from '../../pages/Dashboard'
import LiveResearch from '../../pages/LiveResearch'
import StrategyVault from '../../pages/StrategyVault'
import PaperPortfolio from '../../pages/PaperPortfolio'
import KnowledgeMap from '../../pages/KnowledgeMap'
import ChiefScientist from '../../pages/ChiefScientist'
import ReplayMode from '../../pages/ReplayMode'
import ExplainDecision from '../../pages/ExplainDecision'

const NAV = [
  { path: '/',           label: 'Dashboard',       icon: IconLayoutDashboard, tag: null },
  { path: '/research',   label: 'Live Research',   icon: IconChartCandle,     tag: 'LIVE' },
  { path: '/strategies', label: 'Strategy Vault',  icon: IconDatabase,        tag: null },
  { path: '/paper',      label: 'Paper Portfolio', icon: IconWallet,          tag: null },
  { path: '/knowledge',  label: 'Knowledge Map',   icon: IconBrain,           tag: null },
  { path: '/scientist',  label: 'Chief Scientist', icon: IconUser,            tag: 'AI' },
  { path: '/replay',     label: 'Replay Mode',     icon: IconPlayerPlay,      tag: null },
  { path: '/explain',    label: 'Explain Decision',icon: IconSearch,          tag: null },
]

export default function AppLayout() {
  const [opened, { toggle }] = useDisclosure()
  const navigate = useNavigate()
  const location = useLocation()

  return (
    <AppShell
      navbar={{ width: 200, breakpoint: 'sm', collapsed: { mobile: !opened } }}
      padding={0}
      styles={{
        main: { background: '#0d1117', minHeight: '100vh', paddingLeft: 200 },
        navbar: { background: '#010409', borderRight: '1px solid #21262d' },
      }}
    >
      <AppShell.Navbar p="xs">
        <Group mb="sm" px="xs" pt="xs">
          <IconActivity size={20} color="#58a6ff" />
          <Text size="sm" fw={700} c="#58a6ff" style={{ letterSpacing: 1 }}>
            MOEX AI LAB
          </Text>
          <Badge size="xs" color="green" variant="dot">v1.10</Badge>
        </Group>
        <Divider color="#21262d" mb="xs" />

        <Stack gap={2}>
          {NAV.map(item => {
            const Icon = item.icon
            const active = location.pathname === item.path ||
              (item.path !== '/' && location.pathname.startsWith(item.path))
            return (
              <UnstyledButton
                key={item.path}
                onClick={() => navigate(item.path)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: rem(8),
                  padding: '7px 10px',
                  borderRadius: 6,
                  fontSize: rem(12),
                  fontFamily: 'inherit',
                  color: active ? '#e6edf3' : '#8b949e',
                  background: active ? '#161b22' : 'transparent',
                  borderLeft: active ? '2px solid #58a6ff' : '2px solid transparent',
                  transition: 'all 0.15s',
                }}
                onMouseEnter={e => { if (!active) (e.currentTarget as HTMLElement).style.color = '#c9d1d9' }}
                onMouseLeave={e => { if (!active) (e.currentTarget as HTMLElement).style.color = '#8b949e' }}
              >
                <Icon size={14} />
                <Text size="xs" style={{ flex: 1 }}>{item.label}</Text>
                {item.tag && (
                  <Badge size="xs" color={item.tag === 'LIVE' ? 'green' : 'blue'} variant="filled">
                    {item.tag}
                  </Badge>
                )}
              </UnstyledButton>
            )
          })}
        </Stack>

        <div style={{ flex: 1 }} />
        <Divider color="#21262d" mt="xs" mb="xs" />
        <Text size="10px" c="#484f58" px="xs" pb="xs">
          Research Terminal v1.0 · No Real Trading
        </Text>
      </AppShell.Navbar>

      <AppShell.Main>
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
      </AppShell.Main>
    </AppShell>
  )
}
