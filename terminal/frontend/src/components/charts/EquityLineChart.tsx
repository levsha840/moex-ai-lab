import { useEffect, useRef } from 'react'
import { createChart, type IChartApi, type ISeriesApi, type UTCTimestamp, CrosshairMode } from 'lightweight-charts'
import type { Candle, JournalEntry } from '../../api/client'

interface EquityPoint { time: number; capital: number; drawdown: number }

function buildEquity(candles: Candle[], trades: JournalEntry[], initialCapital: number): EquityPoint[] {
  if (candles.length === 0) return []
  const capitalAtExit: Map<number, number> = new Map()
  for (const t of trades) capitalAtExit.set(t.exit_bar, t.capital_after)

  let capital = initialCapital
  let rollingMax = initialCapital
  const points: EquityPoint[] = []

  for (let i = 0; i < candles.length; i++) {
    if (capitalAtExit.has(i)) capital = capitalAtExit.get(i)!
    rollingMax = Math.max(rollingMax, capital)
    const dd = rollingMax > 0 ? (capital - rollingMax) / rollingMax * 100 : 0
    points.push({ time: candles[i].time, capital, drawdown: dd })
  }
  return points
}

interface Props {
  candles: Candle[]
  trades: JournalEntry[]
  initialCapital: number
  height?: number
  upToBar?: number
}

export default function EquityLineChart({ candles, trades, initialCapital, height = 200, upToBar }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const equitySeriesRef = useRef<ISeriesApi<'Area'> | null>(null)
  const ddSeriesRef = useRef<ISeriesApi<'Area'> | null>(null)

  useEffect(() => {
    if (!containerRef.current) return
    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height,
      layout: { background: { color: '#0d1117' }, textColor: '#8b949e' },
      grid: { vertLines: { color: '#21262d' }, horzLines: { color: '#21262d' } },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: '#30363d' },
      timeScale: { borderColor: '#30363d', timeVisible: true },
    })
    chartRef.current = chart

    const eq = chart.addAreaSeries({
      lineColor: '#3fb950',
      topColor: 'rgba(63,185,80,0.15)',
      bottomColor: 'rgba(63,185,80,0)',
      lineWidth: 2,
    })
    equitySeriesRef.current = eq

    const resize = new ResizeObserver(() => {
      if (containerRef.current) chart.applyOptions({ width: containerRef.current.clientWidth })
    })
    resize.observe(containerRef.current)

    return () => { resize.disconnect(); chart.remove() }
  }, [height])

  useEffect(() => {
    if (!equitySeriesRef.current || candles.length === 0) return
    const limit = upToBar !== undefined ? upToBar + 1 : candles.length
    const pts = buildEquity(candles.slice(0, limit), trades, initialCapital)
    equitySeriesRef.current.setData(pts.map(p => ({ time: p.time as UTCTimestamp, value: p.capital })))
    chartRef.current?.timeScale().fitContent()
  }, [candles, trades, initialCapital, upToBar])

  return <div ref={containerRef} style={{ width: '100%', height }} />
}
