import { SimpleGrid, Paper, Text, Group, Badge, Stack, ScrollArea, Loader, Center, Divider, Progress, rem } from '@mantine/core'
import { useQuery } from '@tanstack/react-query'
import { IconActivity, IconFlask, IconDatabase, IconTrophy, IconWallet, IconBrain, IconClock } from '@tabler/icons-react'
import { fetchStatus, fetchActivity } from '../api/client'
import MetricCard from '../components/shared/MetricCard'
import StatusBadge from '../components/shared/StatusBadge'

function ActivityFeed() {
  const { data, isLoading } = useQuery({ queryKey: ['activity'], queryFn: fetchActivity, refetchInterval: 60_000 })
  if (isLoading) return <Center h={200}><Loader size="sm" color="blue" /></Center>
  return (
    <ScrollArea h={420}>
      <Stack gap={6}>
        {(data ?? []).slice(0, 30).map((evt, i) => (
          <Paper key={i} p="xs" style={{ background: '#0d1117', border: '1px solid #21262d' }}>
            <Group gap={8} align="flex-start">
              <StatusBadge status={evt.status} />
              <div style={{ flex: 1 }}>
                <Text size="11px" c="#c9d1d9" lh={1.4}>{evt.title}</Text>
                <Text size="10px" c="#8b949e" mt={2}>{evt.detail}</Text>
              </div>
              <Text size="10px" c="#484f58" style={{ whiteSpace: 'nowrap' }}>
                {evt.timestamp ? new Date(evt.timestamp).toLocaleDateString('ru-RU', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : ''}
              </Text>
            </Group>
          </Paper>
        ))}
      </Stack>
    </ScrollArea>
  )
}

export default function Dashboard() {
  const { data: status, isLoading } = useQuery({ queryKey: ['status'], queryFn: fetchStatus, refetchInterval: 60_000 })

  if (isLoading) return <Center h="100vh"><Loader color="blue" /></Center>
  if (!status) return null

  const budgetPct = status.research_budget.total > 0
    ? (status.research_budget.used / status.research_budget.total) * 100 : 0

  return (
    <div style={{ padding: 16, height: '100vh', overflow: 'auto', background: '#0d1117' }}>
      {/* Header */}
      <Group mb={16} justify="space-between">
        <Group gap={10}>
          <IconActivity size={18} color="#58a6ff" />
          <Text size="sm" fw={700} c="#e6edf3" style={{ letterSpacing: 1 }}>DASHBOARD</Text>
          <Badge color="green" variant="dot" size="sm">OPERATIONAL</Badge>
        </Group>
        <Text size="11px" c="#8b949e">
          {new Date(status.generated_at).toLocaleString('ru-RU')}
        </Text>
      </Group>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: 16 }}>
        <div>
          {/* Top KPIs */}
          <SimpleGrid cols={4} spacing={10} mb={12}>
            <MetricCard
              label="Hypotheses"
              value={status.hypotheses.registered}
              sub={`${status.hypotheses.tested} tested · ${status.hypotheses.passed_alpha_gate} passed`}
              color="#58a6ff"
              icon={<IconFlask size={14} />}
            />
            <MetricCard
              label="Research Sessions"
              value={status.research.sessions}
              sub={`${status.research.total_findings} findings`}
              color="#e6edf3"
              icon={<IconDatabase size={14} />}
            />
            <MetricCard
              label="Datasets"
              value={status.datasets.total}
              sub="P1 Universe · 1H/4H/1D"
              color="#f0883e"
              icon={<IconDatabase size={14} />}
            />
            <MetricCard
              label="VB Reports"
              value={status.research.visual_backtest_reports}
              sub="Visual Backtests"
              color="#3fb950"
              icon={<IconTrophy size={14} />}
            />
          </SimpleGrid>

          <SimpleGrid cols={3} spacing={10} mb={12}>
            <MetricCard
              label="Alpha Gate Passed"
              value={status.hypotheses.passed_alpha_gate}
              sub={`${status.hypotheses.failed} failed`}
              color={status.hypotheses.passed_alpha_gate > 0 ? '#3fb950' : '#8b949e'}
              trend={status.hypotheses.passed_alpha_gate > 0 ? 'up' : 'neutral'}
            />
            <MetricCard
              label="Paper Trading"
              value={status.paper_trading.enabled ? 'ACTIVE' : 'INACTIVE'}
              sub={status.paper_trading.enabled ? `${status.paper_trading.positions} positions` : 'Awaiting approval'}
              color={status.paper_trading.enabled ? '#3fb950' : '#8b949e'}
            />
            <MetricCard
              label="Knowledge Snapshots"
              value={status.knowledge_base.snapshots}
              sub="KB entries"
              color="#bc8cff"
              icon={<IconBrain size={14} />}
            />
          </SimpleGrid>

          {/* Research Budget */}
          <Paper p="md" mb={12}>
            <Group justify="space-between" mb={8}>
              <Text size="11px" c="#8b949e" tt="uppercase" style={{ letterSpacing: 1 }}>Research Budget</Text>
              <Text size="12px" c="#e6edf3" fw={600} ff="monospace">
                {status.research_budget.used} / {status.research_budget.total} runs
              </Text>
            </Group>
            <Progress
              value={budgetPct}
              color={budgetPct > 80 ? 'red' : budgetPct > 50 ? 'yellow' : 'blue'}
              size="sm"
              radius="xs"
            />
            <Text size="10px" c="#8b949e" mt={4}>
              {status.research_budget.remaining} runs remaining
            </Text>
          </Paper>

          {/* System status grid */}
          <Paper p="md">
            <Text size="11px" c="#8b949e" tt="uppercase" mb={12} style={{ letterSpacing: 1 }}>System Status</Text>
            <Stack gap={8}>
              {[
                { label: 'Research Service',      status: 'online',   color: '#3fb950' },
                { label: 'Visual Backtest',        status: 'online',   color: '#3fb950' },
                { label: 'Campaign Runner',        status: 'online',   color: '#3fb950' },
                { label: 'Knowledge Base',         status: 'online',   color: '#3fb950' },
                { label: 'Hypothesis Registry',    status: 'online',   color: '#3fb950' },
                { label: 'Paper Trading Engine',   status: 'standby',  color: '#f0883e' },
                { label: 'T-Invest API',           status: 'blocked',  color: '#f85149' },
                { label: 'Real Trading',           status: 'blocked',  color: '#f85149' },
              ].map(s => (
                <Group key={s.label} justify="space-between">
                  <Text size="12px" c="#c9d1d9">{s.label}</Text>
                  <Group gap={6}>
                    <div style={{ width: 6, height: 6, borderRadius: '50%', background: s.color }} />
                    <Text size="11px" c={s.color} ff="monospace">{s.status}</Text>
                  </Group>
                </Group>
              ))}
            </Stack>
          </Paper>
        </div>

        {/* Activity Feed */}
        <Paper p="md" style={{ height: '100%' }}>
          <Group mb={10} gap={8}>
            <IconClock size={14} color="#8b949e" />
            <Text size="11px" c="#8b949e" tt="uppercase" style={{ letterSpacing: 1 }}>Activity Log</Text>
          </Group>
          <ActivityFeed />
        </Paper>
      </div>
    </div>
  )
}
