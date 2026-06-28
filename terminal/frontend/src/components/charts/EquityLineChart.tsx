import { useEffect, useRef } from 'react'
import {
  createChart, CrosshairMode,
  type IChartApi, type ISeriesApi, type UTCTimestamp,
} from 'lightweight-charts'
import type { Candle, JournalEntry } from '../../api/client'

function buildEquity(candles: Candle[], trades: JournalEntry[], initial: number): { eq: { time: UTCTimestamp; value: number }[]; dd: { time: UTCTimestamp; value: number }[] } | null {
  if (!candles.length) return null
  const exits = new Map<number, number>()
  for (const t of trades) exits.set(t.exit_bar, t.capital_after)

  let cap = initial
  let peak = initial
  const eq: { time: UTCTimestamp; value: number }[] = []
  const dd: { time: UTCTimestamp; value: number }[] = []

  for (let i = 0; i < candles.length; i++) {
    if (exits.has(i)) cap = exits.get(i)!
    peak = Math.max(peak, cap)
    const drawdown = peak > 0 ? (cap - peak) / peak * 100 : 0
    eq.push({ time: candles[i].time as UTCTimestamp, value: cap })
    dd.push({ time: candles[i].time as UTCTimestamp, value: drawdown })
  }
  return { eq, dd }
}

interface Props {
  candles: Candle[]
  trades: JournalEntry[]
  initialCapital: number
  height?: number
  fillContainer?: boolean
  upToBar?: number
}

export default function EquityLineChart({ candles, trades, initialCapital, height = 160, fillContainer, upToBar }: Props) {
  const eqContainerRef = useRef<HTMLDivElement>(null)
  const eqChartRef     = useRef<IChartApi | null>(null)
  const eqSeriesRef    = useRef<ISeriesApi<'Area'> | null>(null)
  const ddSeriesRef    = useRef<ISeriesApi<'Area'> | null>(null)

  useEffect(() => {
    if (!eqContainerRef.current) return
    const el = eqContainerRef.current

    const chartCfg = {
      width:  el.clientWidth,
      height: fillContainer ? el.clientHeight : height,
      layout: { background: { color: '#131722' }, textColor: '#9598a1', fontSize: 10, fontFamily: 'monospace' },
      grid: { vertLines: { color: '#1e222d' }, horzLines: { color: '#1e222d' } },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: '#2a2e39' },
      timeScale: { borderColor: '#2a2e39', timeVisible: true, secondsVisible: false },
    }

    const chart = createChart(el, chartCfg)
    eqChartRef.current = chart

    const eq$ = chart.addAreaSeries({
      lineColor: '#089981', topColor: 'rgba(8,153,129,0.2)',
      bottomColor: 'rgba(8,153,129,0)', lineWidth: 2, title: 'Equity',
    })
    eqSeriesRef.current = eq$

    const resize = new ResizeObserver(() => {
      if (el) chart.applyOptions({ width: el.clientWidth, height: fillContainer ? el.clientHeight : height })
    })
    resize.observe(el)

    return () => { resize.disconnect(); chart.remove() }
  }, [height, fillContainer])

  useEffect(() => {
    if (!eqSeriesRef.current || !eqChartRef.current || candles.length === 0) return
    const limit = upToBar !== undefined ? upToBar + 1 : candles.length
    const data = buildEquity(candles.slice(0, limit), trades, initialCapital)
    if (!data) return
    eqSeriesRef.current.setData(data.eq)
    eqChartRef.current.timeScale().fitContent()
  }, [candles, trades, initialCapital, upToBar])

  return (
    <div ref={eqContainerRef} style={{ width: '100%', height: fillContainer ? '100%' : height, background: '#131722' }} />
  )
}
