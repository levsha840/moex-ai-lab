import { Group, Text, Badge, Paper, Stack, SimpleGrid, Alert, Center, Loader } from '@mantine/core'
import { useQuery } from '@tanstack/react-query'
import { IconWallet, IconInfoCircle } from '@tabler/icons-react'
import { fetchPaperSummary } from '../api/client'
import MetricCard from '../components/shared/MetricCard'

export default function PaperPortfolio() {
  const { data: summary, isLoading } = useQuery({ queryKey: ['paper-summary'], queryFn: fetchPaperSummary })

  if (isLoading) return <Center h="100vh"><Loader color="blue" /></Center>
  if (!summary) return null

  return (
    <div style={{ height: '100vh', overflow: 'auto', background: '#0d1117', padding: 16 }}>
      <Group mb={16} gap={10}>
        <IconWallet size={16} color="#58a6ff" />
        <Text size="sm" fw={700} c="#e6edf3" style={{ letterSpacing: 1 }}>PAPER PORTFOLIO</Text>
        <Badge color={summary.enabled ? 'green' : 'gray'} size="sm" variant="dot">
          {summary.enabled ? 'ACTIVE' : 'STANDBY'}
        </Badge>
      </Group>

      {!summary.enabled && (
        <Alert
          icon={<IconInfoCircle size={16} />}
          color="blue"
          mb={16}
          styles={{ root: { background: '#161b22', border: '1px solid #1f6feb' } }}
        >
          <Text size="12px" c="#c9d1d9">{summary.note}</Text>
          <Text size="11px" c="#8b949e" mt={4}>
            To activate: Mark a strategy as APPROVED_FOR_PAPER in Strategy Vault → Paper Trading Engine will begin simulation.
          </Text>
        </Alert>
      )}

      <SimpleGrid cols={4} spacing={10} mb={16}>
        <MetricCard
          label="Initial Capital"
          value={`₽ ${summary.initial_capital.toLocaleString('ru-RU', { maximumFractionDigits: 0 })}`}
          color="#8b949e"
        />
        <MetricCard
          label="Current Capital"
          value={`₽ ${summary.current_capital.toLocaleString('ru-RU', { maximumFractionDigits: 0 })}`}
          color="#e6edf3"
        />
        <MetricCard
          label="Total PnL"
          value={`${summary.total_pnl >= 0 ? '+' : ''}₽ ${summary.total_pnl.toLocaleString('ru-RU', { maximumFractionDigits: 0 })}`}
          color={summary.total_pnl >= 0 ? '#3fb950' : '#f85149'}
          trend={summary.total_pnl >= 0 ? 'up' : 'down'}
        />
        <MetricCard
          label="Return"
          value={`${summary.total_return_pct >= 0 ? '+' : ''}${summary.total_return_pct.toFixed(2)}%`}
          color={summary.total_return_pct >= 0 ? '#3fb950' : '#f85149'}
          trend={summary.total_return_pct >= 0 ? 'up' : 'down'}
        />
      </SimpleGrid>

      <SimpleGrid cols={4} spacing={10} mb={16}>
        <MetricCard label="Open Positions" value={summary.open_positions} color="#e6edf3" />
        <MetricCard label="Total Trades" value={summary.total_trades} color="#e6edf3" />
        <MetricCard
          label="Win Rate"
          value={`${(summary.win_rate * 100).toFixed(1)}%`}
          color={summary.win_rate >= 0.5 ? '#3fb950' : '#f85149'}
        />
        <MetricCard
          label="Max Drawdown"
          value={`${summary.max_drawdown_pct.toFixed(2)}%`}
          color="#f85149"
          trend="down"
        />
      </SimpleGrid>

      {/* Equity placeholder */}
      <Paper p="md" mb={16}>
        <Text size="11px" c="#8b949e" tt="uppercase" mb={12} style={{ letterSpacing: 1 }}>Equity Curve</Text>
        <div style={{
          height: 200, background: '#0d1117', borderRadius: 4,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          border: '1px dashed #30363d',
        }}>
          <Stack align="center" gap={4}>
            <Text size="12px" c="#484f58">Equity curve will appear when paper trading activates</Text>
            <Text size="11px" c="#30363d">Initial capital: ₽ 1,000,000 · Awaiting strategy approval</Text>
          </Stack>
        </div>
      </Paper>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <Paper p="md">
          <Text size="11px" c="#8b949e" tt="uppercase" mb={10} style={{ letterSpacing: 1 }}>Open Positions</Text>
          <Text size="12px" c="#484f58" ta="center" py={32}>No open positions</Text>
        </Paper>
        <Paper p="md">
          <Text size="11px" c="#8b949e" tt="uppercase" mb={10} style={{ letterSpacing: 1 }}>Trade History</Text>
          <Text size="12px" c="#484f58" ta="center" py={32}>No completed trades</Text>
        </Paper>
      </div>
    </div>
  )
}
