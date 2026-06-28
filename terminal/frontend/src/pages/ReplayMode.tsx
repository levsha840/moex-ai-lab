import { useState, useEffect, useRef, useCallback } from 'react'
import { Select, Slider, Loader, Center, ScrollArea } from '@mantine/core'
import { useQuery } from '@tanstack/react-query'
import { IconPlayerPlay, IconPlayerPause, IconPlayerStop } from '@tabler/icons-react'
import { fetchReports, fetchReport, fetchCandles } from '../api/client'
import CandleChart from '../components/charts/CandleChart'
import EquityLineChart from '../components/charts/EquityLineChart'
import MetricCard from '../components/shared/MetricCard'

const SPEEDS = ['1', '5', '20', '100']

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
  const capital = report?.metrics?.initial_capital ?? 1_000_000

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
        if (b + step >= total - 1) { setPlaying(false); return total - 1 }
        return b + step
      })
    }, 50)
    return () => { if (intervalRef.current) clearInterval(intervalRef.current) }
  }, [playing, speed, total])

  useEffect(() => { setBar(0); setPlaying(false) }, [selectedIdx])

  const currentCapital = computeCapital(trades, bar, capital)
  const tradesExecuted = trades.filter((t: any) => t.exit_bar <= bar)
  const currentPnlPct = ((currentCapital - capital) / capital) * 100

  const reportOptions = reports.map((r, i) => ({
    value: String(i),
    label: `${r.hypothesis_id} | ${r.ticker} ${r.period}`,
  }))

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden', background: 'var(--t-bg)' }}>
      {/* Toolbar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, height: 38, padding: '0 12px', background: 'var(--t-panel)', borderBottom: '1px solid var(--t-border)', flexShrink: 0 }}>
        <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--t-text-2)', textTransform: 'uppercase', letterSpacing: 1 }}>REPLAY</span>
        <div style={{ width: 1, height: 16, background: 'var(--t-border)' }} />
        <Select size="xs" data={reportOptions} value={String(selectedIdx)}
          onChange={v => setSelectedIdx(Number(v ?? '0'))} style={{ width: 380, flexShrink: 0 }} />
        <div style={{ width: 1, height: 16, background: 'var(--t-border)' }} />

        {/* Play controls */}
        <button onClick={() => { if (bar >= total - 1) setBar(0); setPlaying(true) }}
          disabled={total === 0}
          style={{ background: playing ? 'var(--t-green)' : 'var(--t-elevated)', border: '1px solid var(--t-border)', borderRadius: 2, padding: '3px 8px', cursor: 'pointer', color: playing ? '#000' : 'var(--t-green)', display: 'flex', alignItems: 'center', gap: 4, fontSize: 10 }}>
          <IconPlayerPlay size={10} />{playing ? 'PLAYING' : 'PLAY'}
        </button>
        <button onClick={pause}
          style={{ background: 'var(--t-elevated)', border: '1px solid var(--t-border)', borderRadius: 2, padding: '3px 8px', cursor: 'pointer', color: 'var(--t-amber)', display: 'flex', alignItems: 'center', gap: 4, fontSize: 10 }}>
          <IconPlayerPause size={10} />PAUSE
        </button>
        <button onClick={stop}
          style={{ background: 'var(--t-elevated)', border: '1px solid var(--t-border)', borderRadius: 2, padding: '3px 8px', cursor: 'pointer', color: 'var(--t-red)', display: 'flex', alignItems: 'center', gap: 4, fontSize: 10 }}>
          <IconPlayerStop size={10} />STOP
        </button>

        <div style={{ width: 1, height: 16, background: 'var(--t-border)' }} />
        {/* Speed buttons */}
        <div style={{ display: 'flex', gap: 2 }}>
          {SPEEDS.map(s => (
            <button key={s} onClick={() => setSpeed(s)}
              style={{ background: speed === s ? 'var(--t-accent)' : 'var(--t-elevated)', border: '1px solid var(--t-border)', borderRadius: 2, padding: '3px 10px', cursor: 'pointer', color: speed === s ? '#fff' : 'var(--t-text-2)', fontSize: 10, fontFamily: 'var(--t-font-mono)' }}>
              ×{s}
            </button>
          ))}
        </div>

        <div style={{ flex: 1 }} />
        <span style={{ fontSize: 10, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)' }}>
          {bar} / {total} {candles[bar] ? `· ${candles[bar].ts?.slice(0, 10)}` : ''}
        </span>
      </div>

      {/* Scrubber */}
      <div style={{ padding: '6px 16px', background: 'var(--t-panel)', borderBottom: '1px solid var(--t-border)', flexShrink: 0 }}>
        <Slider value={bar} onChange={v => { pause(); setBar(v) }}
          min={0} max={Math.max(total - 1, 1)} size="xs" color="blue"
          styles={{ track: { background: 'var(--t-elevated)' } }} />
      </div>

      {/* Main area */}
      <div style={{ flex: 1, display: 'grid', gridTemplateColumns: '1fr 220px', gap: 1, background: 'var(--t-border)', overflow: 'hidden' }}>
        {/* Charts + recent trades */}
        <div style={{ background: 'var(--t-bg)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          {isLoading ? (
            <Center h="100%"><Loader /></Center>
          ) : (
            <>
              <div style={{ flex: '0 0 58%', minHeight: 0 }}>
                <CandleChart candles={candles} trades={trades} fillContainer upToBar={bar} />
              </div>
              <div style={{ flex: '0 0 28%', minHeight: 0 }}>
                <div className="t-section-title">⬡ Equity Curve</div>
                <div style={{ flex: 1, minHeight: 0, height: 'calc(100% - 24px)' }}>
                  <EquityLineChart candles={candles} trades={trades} initialCapital={capital} fillContainer upToBar={bar} />
                </div>
              </div>
              <div style={{ flex: '0 0 14%', minHeight: 0, overflow: 'hidden' }}>
                <div className="t-section-title">⬡ Recent Trades ({tradesExecuted.length})</div>
                <ScrollArea style={{ height: 'calc(100% - 24px)' }} scrollbarSize={3}>
                  {tradesExecuted.slice(-8).reverse().map((t: any) => (
                    <div key={t.trade_id} style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 10px', borderBottom: '1px solid var(--t-border-dim)' }}>
                      <span style={{ fontSize: 10, color: 'var(--t-text-2)', fontFamily: 'var(--t-font-mono)' }}>{t.entry_timestamp?.slice(5, 16)} → {t.exit_timestamp?.slice(5, 16)}</span>
                      <span style={{ fontSize: 10, fontFamily: 'var(--t-font-mono)', color: t.is_winner ? 'var(--t-green)' : 'var(--t-red)' }}>
                        {t.pnl_pct >= 0 ? '+' : ''}{t.pnl_pct.toFixed(2)}%
                      </span>
                    </div>
                  ))}
                </ScrollArea>
              </div>
            </>
          )}
        </div>

        {/* Right: live metrics */}
        <div style={{ background: 'var(--t-bg)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div className="t-section-title">⬡ Live Metrics</div>
          <MetricCard label="Bar" value={bar} cls="dim" />
          <MetricCard label="Capital" value={`₽ ${currentCapital.toLocaleString('ru-RU', { maximumFractionDigits: 0 })}`} cls="cyan" />
          <MetricCard label="PnL" value={`${currentPnlPct >= 0 ? '+' : ''}${currentPnlPct.toFixed(2)}%`} cls={currentPnlPct >= 0 ? 'up' : 'down'} />
          <MetricCard label="Trades Done" value={tradesExecuted.length} cls="dim" />
          {report?.metrics && (
            <>
              <div className="t-section-title" style={{ marginTop: 8 }}>⬡ Full Backtest</div>
              <MetricCard label="Final Return" value={`${report.metrics.total_return_pct >= 0 ? '+' : ''}${report.metrics.total_return_pct.toFixed(2)}%`} cls={report.metrics.total_return_pct >= 0 ? 'up' : 'down'} sub="complete" />
              <MetricCard label="Max DD" value={`${report.metrics.max_drawdown_pct.toFixed(2)}%`} cls="down" />
              <MetricCard label="Win Rate" value={`${(report.metrics.win_rate * 100).toFixed(1)}%`} cls={report.metrics.win_rate >= 0.5 ? 'up' : 'dim'} />
              <MetricCard label="Total Trades" value={report.metrics.num_trades} cls="dim" />
            </>
          )}
        </div>
      </div>
    </div>
  )
}
