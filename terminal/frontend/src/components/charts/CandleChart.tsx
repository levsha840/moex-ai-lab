import { useEffect, useRef } from 'react'
import {
  createChart, CrosshairMode,
  type IChartApi, type ISeriesApi, type UTCTimestamp,
} from 'lightweight-charts'
import type { Candle, JournalEntry } from '../../api/client'

interface Props {
  candles: Candle[]
  trades?: JournalEntry[]
  height?: number
  fillContainer?: boolean
  upToBar?: number
}

export default function CandleChart({ candles, trades = [], height = 360, fillContainer, upToBar }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef     = useRef<IChartApi | null>(null)
  const seriesRef    = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const volRef       = useRef<ISeriesApi<'Histogram'> | null>(null)

  useEffect(() => {
    if (!containerRef.current) return
    const el = containerRef.current

    const chart = createChart(el, {
      width:  el.clientWidth,
      height: fillContainer ? el.clientHeight : height,
      layout: {
        background: { color: '#131722' },
        textColor: '#9598a1',
        fontFamily: "'JetBrains Mono','Roboto Mono','Consolas',monospace",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: '#1e222d' },
        horzLines: { color: '#1e222d' },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: { color: '#2a2e39', style: 1, width: 1, labelBackgroundColor: '#2962ff' },
        horzLine: { color: '#2a2e39', style: 1, width: 1, labelBackgroundColor: '#2962ff' },
      },
      rightPriceScale: { borderColor: '#2a2e39', scaleMargins: { top: 0.1, bottom: 0.25 } },
      timeScale: { borderColor: '#2a2e39', timeVisible: true, secondsVisible: false },
      handleScroll: true,
      handleScale: true,
    })
    chartRef.current = chart

    const candles$ = chart.addCandlestickSeries({
      upColor: '#089981', downColor: '#f23645',
      borderUpColor: '#089981', borderDownColor: '#f23645',
      wickUpColor: '#089981', wickDownColor: '#f23645',
    })
    seriesRef.current = candles$

    const vol$ = chart.addHistogramSeries({
      color: '#26a69a',
      priceFormat: { type: 'volume' },
      priceScaleId: 'volume',
    })
    chart.priceScale('volume').applyOptions({ scaleMargins: { top: 0.85, bottom: 0 } })
    volRef.current = vol$

    const resize = new ResizeObserver(() => {
      if (el) chart.applyOptions({ width: el.clientWidth, height: fillContainer ? el.clientHeight : height })
    })
    resize.observe(el)

    return () => { resize.disconnect(); chart.remove(); chartRef.current = null; seriesRef.current = null }
  }, [height, fillContainer])

  useEffect(() => {
    if (!seriesRef.current || !chartRef.current || candles.length === 0) return
    const limit = upToBar !== undefined ? upToBar + 1 : candles.length
    const slice = candles.slice(0, limit)

    seriesRef.current.setData(slice.map(c => ({
      time: c.time as UTCTimestamp,
      open: c.open, high: c.high, low: c.low, close: c.close,
    })))

    if (volRef.current) {
      volRef.current.setData(slice.map((c, i) => ({
        time: c.time as UTCTimestamp,
        value: c.volume,
        color: c.close >= c.open ? '#08998166' : '#f2364566',
      })))
    }

    // Trade markers
    if (trades.length > 0) {
      const markers = trades
        .filter(t => t.entry_bar < limit)
        .flatMap(t => {
          const arr: any[] = []
          if (t.entry_bar < limit && slice[t.entry_bar]) {
            arr.push({
              time: slice[t.entry_bar].time as UTCTimestamp,
              position: 'belowBar',
              color: '#089981',
              shape: 'arrowUp',
              text: `BUY ${t.entry_price.toFixed(2)}`,
              size: 1,
            })
          }
          if (t.exit_bar < limit && slice[t.exit_bar]) {
            arr.push({
              time: slice[t.exit_bar].time as UTCTimestamp,
              position: 'aboveBar',
              color: t.is_winner ? '#2962ff' : '#f23645',
              shape: 'arrowDown',
              text: `EXIT ${t.exit_price.toFixed(2)}`,
              size: 1,
            })
          }
          return arr
        })
        .sort((a, b) => (a.time as number) - (b.time as number))
      seriesRef.current.setMarkers(markers)
    }

    if (upToBar === undefined) chartRef.current.timeScale().fitContent()
  }, [candles, trades, upToBar])

  return (
    <div ref={containerRef} style={{ width: '100%', height: fillContainer ? '100%' : height, background: '#131722' }} />
  )
}
