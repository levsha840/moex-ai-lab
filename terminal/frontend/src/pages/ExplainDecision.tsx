import { useState } from 'react'
import { Group, Text, Badge, Select, Paper, Stack, Loader, Center, SimpleGrid, Divider, ThemeIcon } from '@mantine/core'
import { useQuery } from '@tanstack/react-query'
import { IconSearch, IconArrowUp, IconArrowDown, IconCheck, IconX, IconHelp } from '@tabler/icons-react'
import { fetchReports, fetchReport, fetchTradeDetail } from '../api/client'
import StatusBadge from '../components/shared/StatusBadge'

export default function ExplainDecision() {
  const { data: reports = [] } = useQuery({ queryKey: ['reports'], queryFn: fetchReports })
  const [selectedReport, setSelectedReport] = useState<string>('')
  const [selectedTrade, setSelectedTrade] = useState<string>('')

  const currentReport = reports.find((_, i) => String(i) === selectedReport)

  const { data: report } = useQuery({
    queryKey: ['report', currentReport?.hypothesis_id, currentReport?.ticker, currentReport?.period, currentReport?.timeframe],
    queryFn: () => fetchReport(currentReport!.hypothesis_id, currentReport!.ticker, currentReport!.period, currentReport!.timeframe),
    enabled: !!currentReport,
  })

  const tradeOptions = (report?.trade_journal ?? []).map(t => ({
    value: t.trade_id,
    label: `${t.trade_id.slice(-6)} | ${t.entry_timestamp?.slice(5, 16)} → ${t.exit_timestamp?.slice(5, 16)} | ${t.pnl_pct >= 0 ? '+' : ''}${t.pnl_pct.toFixed(2)}%`,
  }))

  const { data: detail, isLoading } = useQuery({
    queryKey: ['trade-detail', currentReport?.hypothesis_id, currentReport?.ticker, currentReport?.period, selectedTrade],
    queryFn: () => fetchTradeDetail(currentReport!.hypothesis_id, currentReport!.ticker, currentReport!.period, selectedTrade),
    enabled: !!currentReport && !!selectedTrade,
  })

  const reportOptions = reports.map((r, i) => ({
    value: String(i),
    label: `${r.hypothesis_id} | ${r.ticker} ${r.period} ${r.timeframe}`,
  }))

  return (
    <div style={{ height: '100vh', overflow: 'auto', background: '#0d1117', padding: 16 }}>
      <Group mb={16} gap={10}>
        <IconSearch size={16} color="#58a6ff" />
        <Text size="sm" fw={700} c="#e6edf3" style={{ letterSpacing: 1 }}>EXPLAIN DECISION</Text>
        <Badge color="blue" size="sm">Trade Analysis</Badge>
      </Group>

      {/* Selectors */}
      <SimpleGrid cols={2} spacing={12} mb={16}>
        <Select
          label="Backtest Report"
          size="xs"
          placeholder="Select report..."
          data={reportOptions}
          value={selectedReport}
          onChange={v => { setSelectedReport(v ?? ''); setSelectedTrade('') }}
          styles={{ input: { background: '#161b22', border: '1px solid #30363d', color: '#e6edf3', fontSize: 11 }, label: { fontSize: 11, color: '#8b949e' } }}
        />
        <Select
          label="Trade"
          size="xs"
          placeholder="Select trade..."
          data={tradeOptions}
          value={selectedTrade}
          onChange={v => setSelectedTrade(v ?? '')}
          disabled={!report}
          styles={{ input: { background: '#161b22', border: '1px solid #30363d', color: '#e6edf3', fontSize: 11 }, label: { fontSize: 11, color: '#8b949e' } }}
        />
      </SimpleGrid>

      {!selectedTrade && (
        <Center h={300}>
          <Stack align="center" gap={8}>
            <IconSearch size={32} color="#484f58" />
            <Text size="12px" c="#484f58">Select a report and trade to see the explanation</Text>
          </Stack>
        </Center>
      )}

      {isLoading && <Center h={300}><Loader color="blue" /></Center>}

      {detail && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          {/* Trade overview */}
          <Paper p="md">
            <Text size="11px" c="#8b949e" tt="uppercase" mb={12} style={{ letterSpacing: 1 }}>Trade Overview</Text>
            <SimpleGrid cols={2} spacing={8}>
              {[
                { label: 'Entry', value: detail.trade.entry_timestamp?.slice(0, 16), color: '#e6edf3' },
                { label: 'Exit', value: detail.trade.exit_timestamp?.slice(0, 16), color: '#e6edf3' },
                { label: 'Entry Price', value: `₽ ${detail.trade.entry_price.toFixed(2)}`, color: '#3fb950' },
                { label: 'Exit Price', value: `₽ ${detail.trade.exit_price.toFixed(2)}`, color: detail.trade.is_winner ? '#3fb950' : '#f85149' },
                { label: 'PnL', value: `${detail.trade.pnl_pct >= 0 ? '+' : ''}${detail.trade.pnl_pct.toFixed(3)}%`, color: detail.trade.is_winner ? '#3fb950' : '#f85149' },
                { label: 'Result', value: detail.trade.is_winner ? 'WINNER' : 'LOSER', color: detail.trade.is_winner ? '#3fb950' : '#f85149' },
              ].map(({ label, value, color }) => (
                <div key={label}>
                  <Text size="10px" c="#484f58">{label}</Text>
                  <Text size="12px" c={color} fw={600} ff="monospace">{value}</Text>
                </div>
              ))}
            </SimpleGrid>
          </Paper>

          {/* Chief Scientist */}
          <Paper p="md">
            <Text size="11px" c="#8b949e" tt="uppercase" mb={12} style={{ letterSpacing: 1 }}>Chief Scientist</Text>
            <Group gap={10} mb={8}>
              <ThemeIcon color="blue" variant="light" size="sm">
                <IconHelp size={12} />
              </ThemeIcon>
              <Badge color="blue">{detail.chief_scientist.decision}</Badge>
            </Group>
            <Text size="12px" c="#c9d1d9" lh={1.6}>{detail.chief_scientist.rationale}</Text>
            <Divider color="#21262d" mt={12} mb={8} />
            <Text size="11px" c="#8b949e">Strategy: <span style={{ color: '#58a6ff', fontFamily: 'monospace' }}>{detail.strategy_name}</span></Text>
          </Paper>

          {/* Entry Analysis */}
          <Paper p="md">
            <Group gap={8} mb={12}>
              <ThemeIcon color="green" variant="light" size="sm">
                <IconArrowUp size={12} />
              </ThemeIcon>
              <Text size="11px" c="#8b949e" tt="uppercase" style={{ letterSpacing: 1 }}>Entry Analysis</Text>
            </Group>
            <Text size="12px" c="#8b949e" mb={8}>{detail.entry_analysis.reason}</Text>
            <Stack gap={8}>
              {detail.entry_analysis.factors.map((f, i) => (
                <Paper key={i} p="xs" style={{ background: '#0d1117', border: '1px solid #21262d' }}>
                  <Group justify="space-between" mb={2}>
                    <Text size="11px" c="#c9d1d9" fw={600}>{f.indicator}</Text>
                    <Group gap={6}>
                      <Text size="11px" c="#58a6ff" ff="monospace">{f.value}</Text>
                      {f.confirmed
                        ? <IconCheck size={12} color="#3fb950" />
                        : <IconX size={12} color="#8b949e" />
                      }
                    </Group>
                  </Group>
                  <Text size="10px" c="#8b949e">{f.note}</Text>
                </Paper>
              ))}
            </Stack>
          </Paper>

          {/* Exit Analysis */}
          <Paper p="md">
            <Group gap={8} mb={12}>
              <ThemeIcon color={detail.trade.is_winner ? 'blue' : 'red'} variant="light" size="sm">
                <IconArrowDown size={12} />
              </ThemeIcon>
              <Text size="11px" c="#8b949e" tt="uppercase" style={{ letterSpacing: 1 }}>Exit Analysis</Text>
            </Group>
            <Stack gap={8}>
              {[
                { label: 'Exit Reason', value: detail.exit_analysis.exit_reason, color: '#f0883e' },
                { label: 'Exit Price', value: `₽ ${detail.exit_analysis.exit_price.toFixed(2)}`, color: '#e6edf3' },
                { label: 'PnL (₽)', value: `${detail.exit_analysis.pnl >= 0 ? '+' : ''}${detail.exit_analysis.pnl.toFixed(0)}`, color: detail.trade.is_winner ? '#3fb950' : '#f85149' },
                { label: 'PnL (%)', value: `${detail.exit_analysis.pnl_pct >= 0 ? '+' : ''}${detail.exit_analysis.pnl_pct.toFixed(3)}%`, color: detail.trade.is_winner ? '#3fb950' : '#f85149' },
              ].map(({ label, value, color }) => (
                <Group key={label} justify="space-between">
                  <Text size="11px" c="#8b949e">{label}</Text>
                  <Text size="12px" c={color} fw={600} ff="monospace">{value}</Text>
                </Group>
              ))}
            </Stack>
          </Paper>
        </div>
      )}
    </div>
  )
}
