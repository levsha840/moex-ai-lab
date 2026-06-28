import { useEffect, useRef } from 'react'
import {
  createChart, CrosshairMode, LineStyle,
  type IChartApi, type ISeriesApi, type UTCTimestamp, type LogicalRange,
} from 'lightweight-charts'
import type { Candle, JournalEntry } from '../../api/client'
import { calcRsi, calcMacd } from '../../utils/indicators'

interface Props {
  candles: Candle[]
  trades: JournalEntry[]
  upToBar?: number
}

const CHART_BASE = {
  layout: { background: { color: '#131722' }, textColor: '#9598a1', fontSize: 10, fontFamily: 'monospace' },
  grid: { vertLines: { color: '#1e222d' }, horzLines: { color: '#1e222d' } },
  crosshair: {
    mode: CrosshairMode.Normal,
    vertLine: { color: '#434651', width: 1 as 1, style: 1, labelBackgroundColor: '#2962ff' },
    horzLine: { color: '#434651', width: 1 as 1, style: 1, labelBackgroundColor: '#2962ff' },
  },
  timeScale: { borderColor: '#2a2e39', timeVisible: true, secondsVisible: false },
  handleScroll: true,
  handleScale: true,
} as const

function makeChart(el: HTMLDivElement, extraOpts: Record<string, unknown> = {}): IChartApi {
  return createChart(el, {
    ...CHART_BASE,
    ...extraOpts,
    autoSize: true,
    rightPriceScale: { borderColor: '#2a2e39', ...(extraOpts.rightPriceScale ?? {}) },
  } as Parameters<typeof createChart>[1])
}

export default function MainChart({ candles, trades, upToBar }: Props) {
  const mainRef   = useRef<HTMLDivElement>(null)
  const rsiRef    = useRef<HTMLDivElement>(null)
  const macdRef   = useRef<HTMLDivElement>(null)

  const mainChart = useRef<IChartApi | null>(null)
  const rsiChart  = useRef<IChartApi | null>(null)
  const macdChart = useRef<IChartApi | null>(null)
  const prevUpToBar = useRef<number | undefined>(undefined)

  const candleSeries = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const volSeries    = useRef<ISeriesApi<'Histogram'> | null>(null)
  const rsiSeries    = useRef<ISeriesApi<'Line'> | null>(null)
  const macdLine     = useRef<ISeriesApi<'Line'> | null>(null)
  const sigLine      = useRef<ISeriesApi<'Line'> | null>(null)
  const histSeries   = useRef<ISeriesApi<'Histogram'> | null>(null)

  // Init charts once
  useEffect(() => {
    if (!mainRef.current || !rsiRef.current || !macdRef.current) return

    // ── Main chart ──────────────────────────────────────────────────────
    const mc = makeChart(mainRef.current)
    mainChart.current = mc

    const cs = mc.addCandlestickSeries({
      upColor: '#089981', downColor: '#f23645',
      borderUpColor: '#089981', borderDownColor: '#f23645',
      wickUpColor: '#089981', wickDownColor: '#f23645',
    })
    candleSeries.current = cs

    const vs = mc.addHistogramSeries({
      color: '#26a69a', priceFormat: { type: 'volume' }, priceScaleId: 'vol',
    })
    mc.priceScale('vol').applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } })
    volSeries.current = vs

    // ── RSI chart ───────────────────────────────────────────────────────
    const rc = makeChart(rsiRef.current, { rightPriceScale: { scaleMargins: { top: 0.1, bottom: 0.1 } } })
    rsiChart.current = rc

    const rs = rc.addLineSeries({ color: '#2962ff', lineWidth: 1, title: 'RSI' })
    rsiSeries.current = rs

    // OB/OS levels
    ;[30, 50, 70].forEach(lvl => {
      rs.createPriceLine({ price: lvl, color: lvl === 50 ? '#434651' : lvl === 30 ? '#f23645' : '#089981', lineWidth: 1, lineStyle: LineStyle.Dashed, axisLabelVisible: false, title: String(lvl) })
    })

    // ── MACD chart ──────────────────────────────────────────────────────
    const mc2 = makeChart(macdRef.current, { rightPriceScale: { scaleMargins: { top: 0.1, bottom: 0.1 } } })
    macdChart.current = mc2

    macdLine.current = mc2.addLineSeries({ color: '#2962ff', lineWidth: 1, title: 'MACD' })
    sigLine.current  = mc2.addLineSeries({ color: '#ff6d00', lineWidth: 1, title: 'Signal' })
    histSeries.current = mc2.addHistogramSeries({ priceFormat: { type: 'price', precision: 4 }, priceScaleId: 'macdvol' })
    mc2.priceScale('macdvol').applyOptions({ scaleMargins: { top: 0.75, bottom: 0 } })

    // ── Sync time scales ─────────────────────────────────────────────────
    let syncing = false
    const syncAll = (source: IChartApi, others: IChartApi[]) =>
      (range: LogicalRange | null) => {
        if (syncing || !range) return
        syncing = true
        others.forEach(o => o.timeScale().setVisibleLogicalRange(range))
        syncing = false
      }

    mc.timeScale().subscribeVisibleLogicalRangeChange(syncAll(mc, [rc, mc2]))
    rc.timeScale().subscribeVisibleLogicalRangeChange(syncAll(rc, [mc, mc2]))
    mc2.timeScale().subscribeVisibleLogicalRangeChange(syncAll(mc2, [mc, rc]))

    return () => { mc.remove(); rc.remove(); mc2.remove() }
  }, [])

  // Update data when candles/trades/upToBar change
  useEffect(() => {
    if (!candleSeries.current || !candles.length) return
    const limit = upToBar !== undefined ? upToBar + 1 : candles.length
    const slice = candles.slice(0, limit)

    // Candles
    candleSeries.current.setData(slice.map(c => ({
      time: c.time as UTCTimestamp, open: c.open, high: c.high, low: c.low, close: c.close,
    })))

    // Volume
    volSeries.current?.setData(slice.map(c => ({
      time: c.time as UTCTimestamp,
      value: c.volume,
      color: c.close >= c.open ? '#08998166' : '#f2364566',
    })))

    // Markers: BUY / EXIT
    const markers = trades
      .filter(t => t.entry_bar < limit)
      .flatMap(t => {
        const out: any[] = []
        if (t.entry_bar < limit && slice[t.entry_bar]) {
          out.push({
            time: slice[t.entry_bar].time as UTCTimestamp,
            position: 'belowBar', color: '#089981', shape: 'arrowUp',
            text: `BUY ${t.entry_price.toFixed(2)}`, size: 1,
          })
        }
        if (t.exit_bar < limit && slice[t.exit_bar]) {
          const isStop = t.exit_reason?.toUpperCase().includes('STOP') || t.exit_reason?.toUpperCase().includes('SL')
          const isTp   = t.exit_reason?.toUpperCase().includes('TP') || t.exit_reason?.toUpperCase().includes('TAKE')
          out.push({
            time: slice[t.exit_bar].time as UTCTimestamp,
            position: 'aboveBar',
            color: isStop ? '#f23645' : isTp ? '#089981' : t.is_winner ? '#2962ff' : '#f23645',
            shape: 'arrowDown',
            text: `${isStop ? 'STOP' : isTp ? 'TP' : 'EXIT'} ${t.exit_price.toFixed(2)}`,
            size: 1,
          })
        }
        return out
      })
      .sort((a, b) => (a.time as number) - (b.time as number))
    candleSeries.current.setMarkers(markers)

    const justEnteredReplay = upToBar !== undefined && prevUpToBar.current === undefined
    prevUpToBar.current = upToBar
    if (upToBar === undefined || justEnteredReplay) mainChart.current?.timeScale().fitContent()

    // RSI
    const rsiVals = calcRsi(slice)
    rsiSeries.current?.setData(
      slice.map((c, i) => ({ time: c.time as UTCTimestamp, value: rsiVals[i] ?? 50 }))
    )

    // MACD
    const { macd, signal, hist } = calcMacd(slice)
    macdLine.current?.setData(slice.map((c, i) => ({ time: c.time as UTCTimestamp, value: macd[i] ?? 0 })))
    sigLine.current?.setData(slice.map((c, i) => ({ time: c.time as UTCTimestamp, value: signal[i] ?? 0 })))
    histSeries.current?.setData(slice.map((c, i) => ({
      time: c.time as UTCTimestamp, value: hist[i] ?? 0,
      color: (hist[i] ?? 0) >= 0 ? '#08998166' : '#f2364566',
    })))

    if (upToBar === undefined || justEnteredReplay) {
      rsiChart.current?.timeScale().fitContent()
      macdChart.current?.timeScale().fitContent()
    }
  }, [candles, trades, upToBar])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      {/* Main candle chart */}
      <div ref={mainRef} style={{ flex: 3, minHeight: 0 }} />
      {/* RSI */}
      <div style={{ flexShrink: 0, height: 18, background: '#131722', display: 'flex', alignItems: 'center', padding: '0 6px', borderTop: '1px solid #1e222d' }}>
        <span style={{ fontSize: 9, color: '#9598a1', fontFamily: 'monospace', letterSpacing: 1 }}>RSI(14)</span>
      </div>
      <div ref={rsiRef} style={{ flex: 1, minHeight: 0 }} />
      {/* MACD */}
      <div style={{ flexShrink: 0, height: 18, background: '#131722', display: 'flex', alignItems: 'center', padding: '0 6px', borderTop: '1px solid #1e222d' }}>
        <span style={{ fontSize: 9, color: '#9598a1', fontFamily: 'monospace', letterSpacing: 1 }}>MACD(12,26,9)</span>
      </div>
      <div ref={macdRef} style={{ flex: 1, minHeight: 0 }} />
    </div>
  )
}
