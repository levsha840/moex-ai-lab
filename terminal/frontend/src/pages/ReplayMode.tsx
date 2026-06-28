import { useState, useEffect, useRef, useCallback } from 'react'
import { Group, Text, Badge, Select, SegmentedControl, ActionIcon, Slider, Paper, Stack, Loader, Center } from '@mantine/core'
import { useQuery } from '@tanstack/react-query'
import { IconPlayerPlay, IconPlayerPause, IconPlayerStop } from '@tabler/icons-react'
import { fetchReports, fetchReport, fetchCandles } from '../api/client'
import CandleChart from '../components/charts/CandleChart'
import EquityLineChart from '../components/charts/EquityLineChart'
import MetricCard from '../components/shared/MetricCard'

const SPEEDS = [
  { label: '×1', value: '1' },
  { label: '×5', value: '5' },
  { label: '×20', value: '20' },
  { label: '×100', value: '100' },
]

function computeCapital(trades: any[], bar: number, initial: number): number {
  let cap = initial
  for (const t of trades) {
    if (t.exit_bar <= bar) cap = t.capital_after
    else break
  }
  return cap
}

export default function ReplayMode() {
  const { data: reports = [] } = useQuery({ queryKey: ['reports'], queryFn: fetchReports })
  const [selectedIdx, setSelectedIdx] = useState(0)
  const current = reports[selectedIdx]

  const { data: report } = useQuery({
    queryKey: ['report', current?.hypothesis_id, current?.ticker, current?.period, current?.timeframe],
    queryFn: () => fetchReport(current.hypothesis_id, current.ticker, current.period, current.timeframe),
    enabled: !!current,
  })
  const { data: candles = [], isLoading } = useQuery({
    queryKey: ['candles', current?.dataset_id],
    queryFn: () => fetchCandles(current.dataset_id),
    enabled: !!current,
  })

  const [bar, setBar] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState('5')
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const total = candles.length
  const trades = report?.trade_journal ?? []
  const capital = report?.metrics.initial_capital ?? 1_000_000

  const stop = useCallback(() => {
    setPlaying(false)
    if (intervalRef.current) clearInterval(intervalRef.current)
    setBar(0)
  }, [])

  const pause = useCallback(() => {
    setPlaying(false)
    if (intervalRef.current) clearInterval(intervalRef.current)
  }, [])

  useEffect(() => {
    if (!playing) return
    const step = Number(speed)
    intervalRef.current = setInterval(() => {
      setBar(b => {
        if (b + step >= total - 1) {
          setPlaying(false)
          return total - 1
        }
        return b + step
      })
    }, 50)
    return () => { if (intervalRef.current) clearInterval(intervalRef.current) }
  }, [playing, speed, total])

  // Reset bar when report changes
  useEffect(() => { setBar(0); setPlaying(false) }, [selectedIdx])

  const currentCapital = computeCapital(trades, bar, capital)
  const tradesExecuted = trades.filter(t => t.exit_bar <= bar)
  const currentPnl = currentCapital - capital
  const currentPnlPct = (currentPnl / capital) * 100

  const reportOptions = reports.map((r, i) => ({
    value: String(i),
    label: `${r.hypothesis_id} | ${r.ticker} ${r.period}`,
  }))

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: '#0d1117' }}>
      {/* Header */}
      <div style={{ padding: '10px 16px', borderBottom: '1px solid #21262d', display: 'flex', alignItems: 'center', gap: 12 }}>
        <IconPlayerPlay size={16} color="#58a6ff" />
        <Text size="sm" fw={700} c="#e6edf3" style={{ letterSpacing: 1 }}>REPLAY MODE</Text>
        {playing && <Badge color="green" variant="dot" size="sm">PLAYING</Badge>}
        <div style={{ flex: 1 }} />
        <Select
          size="xs"
          data={reportOptions}
          value={String(selectedIdx)}
          onChange={v => setSelectedIdx(Number(v ?? '0'))}
          style={{ width: 360 }}
          styles={{ input: { background: '#161b22', border: '1px solid #30363d', color: '#e6edf3', fontSize: 11 } }}
        />
      </div>

      {/* Controls */}
      <div style={{ padding: '8px 16px', borderBottom: '1px solid #21262d', display: 'flex', alignItems: 'center', gap: 16 }}>
        <Group gap={6}>
          <ActionIcon
            size="sm" color="green" variant={playing ? 'light' : 'filled'}
            onClick={() => { if (bar >= total - 1) setBar(0); setPlaying(true) }}
            disabled={total === 0}
          >
            <IconPlayerPlay size={12} />
          </ActionIcon>
          <ActionIcon size="sm" color="yellow" variant="light" onClick={pause}>
            <IconPlayerPause size={12} />
          </ActionIcon>
          <ActionIcon size="sm" color="red" variant="light" onClick={stop}>
            <IconPlayerStop size={12} />
          </ActionIcon>
        </Group>

        <SegmentedControl
          size="xs"
          value={speed}
          onChange={setSpeed}
          data={SPEEDS}
          styles={{ root: { background: '#161b22', border: '1px solid #30363d' }, label: { fontSize: 11, color: '#8b949e' } }}
        />

        <div style={{ flex: 1, padding: '0 12px' }}>
          <Slider
            value={bar}
            onChange={v => { pause(); setBar(v) }}
            min={0}
            max={Math.max(total - 1, 1)}
            size="xs"
            color="blue"
            styles={{ track: { background: '#21262d' } }}
          />
        </div>

        <Text size="11px" c="#8b949e" ff="monospace">
          Bar {bar} / {total}
          {candles[bar] && <span style={{ marginLeft: 8, color: '#58a6ff' }}>{candles[bar].ts?.slice(0, 16)}</span>}
        </Text>
      </div>

      {/* Main: chart + sidebar */}
      <div style={{ flex: 1, display: 'grid', gridTemplateColumns: '1fr 240px', overflow: 'hidden' }}>
        <div style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          {isLoading ? (
            <Center h="100%"><Loader color="blue" /></Center>
          ) : (
            <>
              <div style={{ flex: '0 0 auto', padding: '8px 8px 0' }}>
                <CandleChart candles={candles} trades={trades} height={320} upToBar={bar} />
              </div>
              <div style={{ flex: '0 0 auto', padding: '4px 8px 0' }}>
                <Text size="10px" c="#8b949e" mb={4} pl={4}>EQUITY CURVE</Text>
                <EquityLineChart candles={candles} trades={trades} initialCapital={capital} height={150} upToBar={bar} />
              </div>

              {/* Replay trade log */}
              <div style={{ flex: 1, overflow: 'auto', padding: '8px' }}>
                <Text size="10px" c="#8b949e" mb={6}>Executed: {tradesExecuted.length} trades</Text>
                {tradesExecuted.slice(-5).reverse().map(t => (
                  <Paper key={t.trade_id} p="xs" mb={4} style={{ background: '#0d1117', border: '1px solid #21262d' }}>
                    <Group justify="space-between">
                      <Text size="10px" c="#8b949e">{t.entry_timestamp?.slice(5, 16)} → {t.exit_timestamp?.slice(5, 16)}</Text>
                      <Text size="10px" c={t.is_winner ? '#3fb950' : '#f85149'} ff="monospace">
                        {t.pnl_pct >= 0 ? '+' : ''}{t.pnl_pct.toFixed(2)}%
                      </Text>
                    </Group>
                  </Paper>
                ))}
              </div>
            </>
          )}
        </div>

        {/* Right panel */}
        <div style={{ borderLeft: '1px solid #21262d', padding: 12, overflow: 'auto', background: '#010409' }}>
          <Stack gap={8}>
            <MetricCard label="Bar" value={bar} color="#8b949e" />
            <MetricCard
              label="Capital"
              value={`₽ ${currentCapital.toLocaleString('ru-RU', { maximumFractionDigits: 0 })}`}
              color="#e6edf3"
            />
            <MetricCard
              label="Current PnL"
              value={`${currentPnlPct >= 0 ? '+' : ''}${currentPnlPct.toFixed(2)}%`}
              color={currentPnlPct >= 0 ? '#3fb950' : '#f85149'}
              trend={currentPnlPct >= 0 ? 'up' : 'down'}
            />
            <MetricCard label="Trades Done" value={tradesExecuted.length} color="#58a6ff" />
            {report && (
              <>
                <MetricCard label="Final Return" value={`${report.metrics.total_return_pct >= 0 ? '+' : ''}${report.metrics.total_return_pct.toFixed(2)}%`} color="#8b949e" sub="(full backtest)" />
                <MetricCard label="Max DD (full)" value={`${report.metrics.max_drawdown_pct.toFixed(2)}%`} color="#f85149" />
              </>
            )}
          </Stack>
        </div>
      </div>
    </div>
  )
}
