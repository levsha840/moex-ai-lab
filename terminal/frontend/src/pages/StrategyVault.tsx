import { useState } from 'react'
import { Group, Text, Badge, SegmentedControl, Table, ScrollArea, Loader, Center, TextInput, Paper, Tooltip } from '@mantine/core'
import { useQuery } from '@tanstack/react-query'
import { IconDatabase, IconSearch } from '@tabler/icons-react'
import { fetchStrategies } from '../api/client'
import StatusBadge from '../components/shared/StatusBadge'

const STATUS_FILTERS = [
  { label: 'All', value: 'all' },
  { label: 'Research', value: 'RESEARCH_PASS,RESEARCH_FAIL' },
  { label: 'Backtest', value: 'VISUAL_BACKTEST' },
  { label: 'Passed', value: 'RESEARCH_PASS' },
  { label: 'Failed', value: 'RESEARCH_FAIL' },
]

function fmt(v: number | null, decimals = 2, suffix = '') {
  if (v === null || v === undefined) return '—'
  return `${v.toFixed(decimals)}${suffix}`
}

function fmtPct(v: number | null) {
  if (v === null) return '—'
  return <span style={{ color: v >= 0 ? '#3fb950' : '#f85149', fontFamily: 'monospace' }}>
    {v >= 0 ? '+' : ''}{v.toFixed(2)}%
  </span>
}

function fmtWin(v: number | null) {
  if (v === null) return '—'
  const pct = v * 100
  return <span style={{ color: pct >= 50 ? '#3fb950' : '#8b949e', fontFamily: 'monospace' }}>
    {pct.toFixed(1)}%
  </span>
}

export default function StrategyVault() {
  const [filter, setFilter] = useState('all')
  const [search, setSearch] = useState('')

  const { data: strategies = [], isLoading } = useQuery({
    queryKey: ['strategies'],
    queryFn: () => fetchStrategies(),
  })

  const filtered = strategies.filter(s => {
    if (filter !== 'all' && !filter.split(',').includes(s.status)) return false
    if (search && !s.strategy.toLowerCase().includes(search.toLowerCase()) && !s.template_id.includes(search)) return false
    return true
  })

  const totalPassed = strategies.filter(s => s.status === 'RESEARCH_PASS').length
  const totalVB = strategies.filter(s => s.status === 'VISUAL_BACKTEST').length

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: '#0d1117' }}>
      {/* Header */}
      <div style={{ padding: '10px 16px', borderBottom: '1px solid #21262d' }}>
        <Group justify="space-between">
          <Group gap={10}>
            <IconDatabase size={16} color="#58a6ff" />
            <Text size="sm" fw={700} c="#e6edf3" style={{ letterSpacing: 1 }}>STRATEGY VAULT</Text>
            <Badge color="blue" size="sm">{strategies.length} entries</Badge>
            <Badge color="green" size="sm">{totalPassed} passed</Badge>
            <Badge color="blue" variant="outline" size="sm">{totalVB} backtested</Badge>
          </Group>
          <Group gap={8}>
            <TextInput
              size="xs"
              placeholder="Search..."
              leftSection={<IconSearch size={12} />}
              value={search}
              onChange={e => setSearch(e.currentTarget.value)}
              style={{ width: 200 }}
              styles={{ input: { background: '#161b22', border: '1px solid #30363d', color: '#e6edf3', fontSize: 11 } }}
            />
          </Group>
        </Group>
        <Group mt={8}>
          <SegmentedControl
            size="xs"
            value={filter}
            onChange={setFilter}
            data={STATUS_FILTERS}
            styles={{
              root: { background: '#161b22', border: '1px solid #30363d' },
              label: { fontSize: 11, color: '#8b949e' },
            }}
          />
        </Group>
      </div>

      {/* Table */}
      <ScrollArea style={{ flex: 1 }} p="xs">
        {isLoading ? (
          <Center h={400}><Loader color="blue" /></Center>
        ) : (
          <Table striped highlightOnHover withTableBorder={false} fz={11}>
            <Table.Thead style={{ position: 'sticky', top: 0, zIndex: 10 }}>
              <Table.Tr>
                <Table.Th>Strategy</Table.Th>
                <Table.Th>Status</Table.Th>
                <Table.Th>Research Score</Table.Th>
                <Table.Th>Pass Rate</Table.Th>
                <Table.Th>Win Rate</Table.Th>
                <Table.Th>Profit Factor</Table.Th>
                <Table.Th>Return</Table.Th>
                <Table.Th>Max DD</Table.Th>
                <Table.Th>Paper</Table.Th>
                <Table.Th>Sandbox</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {filtered.map(s => (
                <Table.Tr key={s.id}>
                  <Table.Td>
                    <Tooltip label={s.template_id} position="right">
                      <Text size="11px" c="#c9d1d9" style={{ maxWidth: 240, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', cursor: 'default' }}>
                        {s.strategy}
                      </Text>
                    </Tooltip>
                  </Table.Td>
                  <Table.Td><StatusBadge status={s.status} /></Table.Td>
                  <Table.Td>
                    {s.research_score !== null
                      ? <span style={{ color: (s.research_score ?? 0) >= 40 ? '#3fb950' : '#f85149', fontFamily: 'monospace' }}>
                          {s.research_score}%
                        </span>
                      : '—'}
                  </Table.Td>
                  <Table.Td style={{ fontFamily: 'monospace', color: '#8b949e' }}>
                    {s.pass_rate !== null ? `${(s.pass_rate * 100).toFixed(1)}%` : '—'}
                    {s.windows_total !== null && <Text span size="10px" c="#484f58"> /{s.windows_total}w</Text>}
                  </Table.Td>
                  <Table.Td>{fmtWin(s.win_rate)}</Table.Td>
                  <Table.Td style={{ fontFamily: 'monospace', color: (s.profit_factor ?? 0) >= 1 ? '#3fb950' : '#f85149' }}>
                    {s.profit_factor !== null ? (s.profit_factor === Infinity ? '∞' : fmt(s.profit_factor)) : '—'}
                  </Table.Td>
                  <Table.Td>{fmtPct(s.total_return_pct)}</Table.Td>
                  <Table.Td>
                    {s.max_drawdown_pct !== null
                      ? <span style={{ color: '#f85149', fontFamily: 'monospace' }}>{s.max_drawdown_pct.toFixed(2)}%</span>
                      : '—'}
                  </Table.Td>
                  <Table.Td><StatusBadge status={s.paper_status} /></Table.Td>
                  <Table.Td><StatusBadge status={s.sandbox_status} /></Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        )}
      </ScrollArea>
    </div>
  )
}
