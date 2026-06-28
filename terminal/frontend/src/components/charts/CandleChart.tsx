import { useEffect, useRef } from 'react'
import { createChart, CrosshairMode, type IChartApi, type ISeriesApi, type UTCTimestamp } from 'lightweight-charts'
import type { Candle, JournalEntry } from '../../api/client'

interface Props {
  candles: Candle[]
  trades?: JournalEntry[]
  height?: number
  upToBar?: number   // for replay mode — only show up to this bar index
}

export default function CandleChart({ candles, trades = [], height = 400, upToBar }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)

  useEffect(() => {
    if (!containerRef.current) return
    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height,
      layout: {
        background: { color: '#0d1117' },
        textColor: '#8b949e',
      },
      grid: {
        vertLines: { color: '#21262d' },
        horzLines: { color: '#21262d' },
      },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: '#30363d' },
      timeScale: { borderColor: '#30363d', timeVisible: true, secondsVisible: false },
    })
    chartRef.current = chart

    const candleSeries = chart.addCandlestickSeries({
      upColor: '#3fb950',
      downColor: '#f85149',
      borderUpColor: '#3fb950',
      borderDownColor: '#f85149',
      wickUpColor: '#3fb950',
      wickDownColor: '#f85149',
    })
    candleSeriesRef.current = candleSeries

    const resize = new ResizeObserver(() => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth })
      }
    })
    resize.observe(containerRef.current)

    return () => {
      resize.disconnect()
      chart.remove()
      chartRef.current = null
      candleSeriesRef.current = null
    }
  }, [height])

  // Update data
  useEffect(() => {
    if (!candleSeriesRef.current || candles.length === 0) return

    const limit = upToBar !== undefined ? upToBar + 1 : candles.length
    const data = candles.slice(0, limit).map(c => ({
      time: c.time as UTCTimestamp,
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
    }))
    candleSeriesRef.current.setData(data)

    // Add trade markers
    if (trades.length > 0 && chartRef.current) {
      const markers = trades
        .filter(t => t.entry_bar < limit)
        .flatMap(t => {
          const arr = []
          if (t.entry_bar < limit && candles[t.entry_bar]) {
            arr.push({
              time: candles[t.entry_bar].time as UTCTimestamp,
              position: 'belowBar' as const,
              color: '#3fb950',
              shape: 'arrowUp' as const,
              text: `BUY ${t.entry_price.toFixed(2)}`,
            })
          }
          if (t.exit_bar < limit && candles[t.exit_bar]) {
            arr.push({
              time: candles[t.exit_bar].time as UTCTimestamp,
              position: 'aboveBar' as const,
              color: t.is_winner ? '#58a6ff' : '#f85149',
              shape: 'arrowDown' as const,
              text: `EXIT ${t.exit_price.toFixed(2)}`,
            })
          }
          return arr
        })
        .sort((a, b) => (a.time as number) - (b.time as number))

      candleSeriesRef.current.setMarkers(markers)
    }

    if (upToBar === undefined) {
      chartRef.current?.timeScale().fitContent()
    }
  }, [candles, trades, upToBar])

  return <div ref={containerRef} style={{ width: '100%', height }} />
}
