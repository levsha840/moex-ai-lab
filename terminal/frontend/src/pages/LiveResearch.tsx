import { useState } from 'react'
import { Group, Text, Select, Paper, Stack, ScrollArea, Badge, Divider, Loader, Center, Table, rem } from '@mantine/core'
import { useQuery } from '@tanstack/react-query'
import { IconChartCandle, IconActivity } from '@tabler/icons-react'
import { fetchReports, fetchReport, fetchCandles } from '../api/client'
import CandleChart from '../components/charts/CandleChart'
import EquityLineChart from '../components/charts/EquityLineChart'
import MetricCard from '../components/shared/MetricCard'

export default function LiveResearch() {
  const { data: reports = [] } = useQuery({ queryKey: ['reports'], queryFn: fetchReports })
  const [selectedIdx, setSelectedIdx] = useState(0)

  const current = reports[selectedIdx]

  const { data: report, isLoading: loadingReport } = useQuery({
    queryKey: ['report', current?.hypothesis_id, current?.ticker, current?.period, current?.timeframe],
    queryFn: () => fetchReport(current.hypothesis_id, current.ticker, current.period, current.timeframe),
    enabled: !!current,
  })

  const { data: candles = [], isLoading: loadingCandles } = useQuery({
    queryKey: ['candles', current?.dataset_id],
    queryFn: () => fetchCandles(current.dataset_id),
    enabled: !!current,
  })

  const reportOptions = reports.map((r, i) => ({
    value: String(i),
    label: `${r.hypothesis_id} | ${r.ticker} ${r.period} ${r.timeframe}`,
  }))

  const metrics = report?.metrics
  const trades = report?.trade_journal ?? []
  const capital = metrics?.initial_capital ?? 1_000_000
  const pf = metrics?.profit_factor

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: '#0d1117' }}>
      {/* Top bar */}
      <div style={{ padding: '10px 16px', borderBottom: '1px solid #21262d', display: 'flex', alignItems: 'center', gap: 12 }}>
        <IconChartCandle size={16} color="#58a6ff" />
        <Text size="sm" fw={700} c="#e6edf3" style={{ letterSpacing: 1 }}>LIVE RESEARCH</Text>
        <Badge color="green" variant="dot" size="sm">BACKTEST VIEW</Badge>
        <div style={{ flex: 1 }} />
        <Select
          size="xs"
          placeholder="Select report..."
          data={reportOptions}
          value={String(selectedIdx)}
          onChange={v => setSelectedIdx(Number(v ?? '0'))}
          style={{ width: 420 }}
          styles={{ input: { background: '#161b22', border: '1px solid #30363d', color: '#e6edf3', fontSize: 11 } }}
        />
      </div>

      {/* Main content */}
      <div style={{ flex: 1, display: 'grid', gridTemplateColumns: '1fr 280px', overflow: 'hidden' }}>
        {/* Left: chart + journal */}
        <div style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          {/* Candle chart */}
          <div style={{ flex: '0 0 auto', padding: '8px 8px 0' }}>
            {(loadingCandles || loadingReport) ? (
              <Center h={420}><Loader color="blue" /></Center>
            ) : (
              <CandleChart candles={candles} trades={trades} height={340} />
            )}
          </div>

          {/* Equity chart */}
          <div style={{ flex: '0 0 auto', padding: '4px 8px 0' }}>
            <Text size="10px" c="#8b949e" mb={4} pl={4}>EQUITY CURVE</Text>
            {candles.length > 0 && (
              <EquityLineChart candles={candles} trades={trades} initialCapital={capital} height={140} />
            )}
          </div>

          <Divider color="#21262d" mt={6} />

          {/* Trade Journal */}
          <div style={{ flex: 1, overflow: 'hidden', padding: '6px 8px' }}>
            <Group mb={6} gap={8}>
              <IconActivity size={12} color="#8b949e" />
              <Text size="10px" c="#8b949e" tt="uppercase" style={{ letterSpacing: 1 }}>
                Trade Journal ({trades.length} trades)
              </Text>
            </Group>
            <ScrollArea style={{ height: 'calc(100% - 24px)' }}>
              <Table striped highlightOnHover withTableBorder={false} fz={10}>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>Entry</Table.Th>
                    <Table.Th>Exit</Table.Th>
                    <Table.Th>Entry ₽</Table.Th>
                    <Table.Th>Exit ₽</Table.Th>
                    <Table.Th>PnL %</Table.Th>
                    <Table.Th>Capital</Table.Th>
                    <Table.Th>Reason</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {trades.map(t => (
                    <Table.Tr key={t.trade_id}>
                      <Table.Td style={{ color: '#8b949e' }}>{t.entry_timestamp?.slice(5, 16)}</Table.Td>
                      <Table.Td style={{ color: '#8b949e' }}>{t.exit_timestamp?.slice(5, 16)}</Table.Td>
                      <Table.Td style={{ color: '#e6edf3', fontFamily: 'monospace' }}>{t.entry_price.toFixed(2)}</Table.Td>
                      <Table.Td style={{ color: '#e6edf3', fontFamily: 'monospace' }}>{t.exit_price.toFixed(2)}</Table.Td>
                      <Table.Td style={{ color: t.pnl_pct >= 0 ? '#3fb950' : '#f85149', fontFamily: 'monospace' }}>
                        {t.pnl_pct >= 0 ? '+' : ''}{t.pnl_pct.toFixed(2)}%
                      </Table.Td>
                      <Table.Td style={{ color: '#58a6ff', fontFamily: 'monospace' }}>
                        {t.capital_after.toLocaleString('ru-RU', { maximumFractionDigits: 0 })}
                      </Table.Td>
                      <Table.Td style={{ color: '#8b949e', fontSize: 10 }}>{t.exit_reason}</Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </ScrollArea>
          </div>
        </div>

        {/* Right panel */}
        <div style={{ borderLeft: '1px solid #21262d', padding: 12, overflow: 'auto', background: '#010409' }}>
          {/* Hypothesis info */}
          <Paper p="xs" mb={10} style={{ background: '#161b22' }}>
            <Text size="10px" c="#8b949e" tt="uppercase" mb={4} style={{ letterSpacing: 1 }}>Hypothesis</Text>
            <Text size="12px" c="#58a6ff" fw={600}>{current?.hypothesis_id ?? '—'}</Text>
            <Text size="10px" c="#8b949e" mt={2}>
              {current?.ticker ?? '—'} · {current?.period ?? '—'} · {current?.timeframe ?? '1h'}
            </Text>
          </Paper>

          <Stack gap={8}>
            <MetricCard
              label="Current Capital"
              value={metrics ? `₽ ${metrics.final_capital.toLocaleString('ru-RU', { maximumFractionDigits: 0 })}` : '—'}
              color="#e6edf3"
            />
            <MetricCard
              label="Total Return"
              value={metrics ? `${metrics.total_return_pct >= 0 ? '+' : ''}${metrics.total_return_pct.toFixed(2)}%` : '—'}
              color={metrics && metrics.total_return_pct >= 0 ? '#3fb950' : '#f85149'}
              trend={metrics ? (metrics.total_return_pct >= 0 ? 'up' : 'down') : 'neutral'}
            />
            <MetricCard
              label="Max Drawdown"
              value={metrics ? `${metrics.max_drawdown_pct.toFixed(2)}%` : '—'}
              color="#f85149"
              trend="down"
            />
            <MetricCard
              label="Win Rate"
              value={metrics ? `${(metrics.win_rate * 100).toFixed(1)}%` : '—'}
              color="#e6edf3"
            />
            <MetricCard
              label="Profit Factor"
              value={metrics ? (pf === Infinity ? '∞' : (pf ?? 0).toFixed(2)) : '—'}
              color={metrics && (pf ?? 0) > 1 ? '#3fb950' : '#f85149'}
            />
            <MetricCard
              label="Trades"
              value={metrics?.num_trades ?? 0}
              sub={metrics ? `Exposure ${metrics.exposure_time_pct.toFixed(1)}%` : ''}
              color="#e6edf3"
            />
            <MetricCard
              label="Avg Trade PnL"
              value={metrics ? `${metrics.avg_trade_pnl_pct >= 0 ? '+' : ''}${metrics.avg_trade_pnl_pct.toFixed(3)}%` : '—'}
              color={metrics && metrics.avg_trade_pnl_pct >= 0 ? '#3fb950' : '#f85149'}
            />
          </Stack>
        </div>
      </div>
    </div>
  )
}
