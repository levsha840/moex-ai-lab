import { Group, Text, Badge, Paper, Stack, ScrollArea, Loader, Center, SimpleGrid, Progress } from '@mantine/core'
import { useQuery } from '@tanstack/react-query'
import { IconUser, IconCheck, IconX, IconHelp, IconArchive } from '@tabler/icons-react'
import { fetchDecisions, fetchScientistStats } from '../api/client'
import StatusBadge from '../components/shared/StatusBadge'

const DECISION_ICONS: Record<string, { icon: typeof IconCheck; color: string }> = {
  APPROVE:               { icon: IconCheck,   color: '#3fb950' },
  REJECT:                { icon: IconX,       color: '#f85149' },
  REQUEST_MORE_EVIDENCE: { icon: IconHelp,    color: '#f0883e' },
  ARCHIVE:               { icon: IconArchive, color: '#8b949e' },
  MONITOR:               { icon: IconHelp,    color: '#58a6ff' },
}

export default function ChiefScientist() {
  const { data: decisions = [], isLoading } = useQuery({ queryKey: ['decisions'], queryFn: fetchDecisions })
  const { data: stats } = useQuery({ queryKey: ['scientist-stats'], queryFn: fetchScientistStats })

  const byType = (decisions as any[]).reduce((acc: Record<string, number>, d: any) => {
    acc[d.type] = (acc[d.type] ?? 0) + 1
    return acc
  }, {})

  if (isLoading) return <Center h="100vh"><Loader color="blue" /></Center>

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: '#0d1117' }}>
      <div style={{ padding: '10px 16px', borderBottom: '1px solid #21262d' }}>
        <Group gap={10}>
          <IconUser size={16} color="#58a6ff" />
          <Text size="sm" fw={700} c="#e6edf3" style={{ letterSpacing: 1 }}>CHIEF SCIENTIST</Text>
          <Badge color="blue" size="sm">{decisions.length} decisions</Badge>
        </Group>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr', flex: 1, overflow: 'hidden' }}>
        {/* Left: stats */}
        <div style={{ borderRight: '1px solid #21262d', padding: 12, overflow: 'auto' }}>
          <Text size="10px" c="#8b949e" tt="uppercase" mb={10} style={{ letterSpacing: 1 }}>Decision Summary</Text>
          <Stack gap={10}>
            {Object.entries(DECISION_ICONS).map(([type, cfg]) => {
              const Icon = cfg.icon
              const count = byType[type] ?? 0
              const total = decisions.length || 1
              return (
                <div key={type}>
                  <Group justify="space-between" mb={4}>
                    <Group gap={6}>
                      <Icon size={12} color={cfg.color} />
                      <Text size="11px" c="#c9d1d9">{type.replace(/_/g, ' ')}</Text>
                    </Group>
                    <Text size="11px" c={cfg.color} fw={700} ff="monospace">{count}</Text>
                  </Group>
                  <Progress value={count / total * 100} color={cfg.color === '#3fb950' ? 'green' : cfg.color === '#f85149' ? 'red' : 'blue'} size="xs" radius="xs" />
                </div>
              )
            })}
          </Stack>

          <Text size="10px" c="#8b949e" tt="uppercase" mt={20} mb={10} style={{ letterSpacing: 1 }}>AI Persona</Text>
          <Paper p="sm" style={{ background: '#0d1117', border: '1px solid #21262d' }}>
            <Text size="11px" c="#c9d1d9" lh={1.6}>
              Chief Scientist evaluates research findings against the Alpha Library criteria.
              Each hypothesis is judged on pass rate, statistical significance, and regime consistency.
              Only strategies with pass_rate ≥ 40% proceed to Visual Backtest stage.
            </Text>
          </Paper>
        </div>

        {/* Right: decision log */}
        <ScrollArea style={{ flex: 1 }} p="md">
          <Stack gap={8}>
            {decisions.length === 0 && (
              <Center h={200}>
                <Text size="12px" c="#484f58">No decisions recorded yet. Run a research campaign to generate decisions.</Text>
              </Center>
            )}
            {decisions.map((d: any, i: number) => {
              const cfg = DECISION_ICONS[d.type] ?? DECISION_ICONS['MONITOR']
              const Icon = cfg.icon
              return (
                <Paper key={i} p="md" style={{ background: '#161b22', border: `1px solid #30363d`, borderLeft: `3px solid ${cfg.color}` }}>
                  <Group justify="space-between" mb={6}>
                    <Group gap={8}>
                      <Icon size={14} color={cfg.color} />
                      <Badge size="xs" color={cfg.color === '#3fb950' ? 'green' : cfg.color === '#f85149' ? 'red' : 'orange'}>
                        {d.type}
                      </Badge>
                      <Text size="12px" c="#e6edf3" fw={600} style={{ maxWidth: 400, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {d.hypothesis_title || d.hypothesis_id}
                      </Text>
                    </Group>
                    <Text size="10px" c="#8b949e" ff="monospace">
                      {d.timestamp ? new Date(d.timestamp).toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' }) : ''}
                    </Text>
                  </Group>
                  <Text size="11px" c="#8b949e" lh={1.5}>{d.rationale}</Text>
                  {d.stats?.pass_rate !== null && d.stats?.pass_rate !== undefined && (
                    <Group mt={6} gap={12}>
                      <Text size="10px" c="#484f58">
                        pass_rate: <span style={{ color: '#58a6ff', fontFamily: 'monospace' }}>{(d.stats.pass_rate * 100).toFixed(1)}%</span>
                      </Text>
                      {d.stats.windows_total && (
                        <Text size="10px" c="#484f58">
                          windows: <span style={{ color: '#8b949e', fontFamily: 'monospace' }}>{d.stats.windows_total}</span>
                        </Text>
                      )}
                    </Group>
                  )}
                </Paper>
              )
            })}
          </Stack>
        </ScrollArea>
      </div>
    </div>
  )
}
