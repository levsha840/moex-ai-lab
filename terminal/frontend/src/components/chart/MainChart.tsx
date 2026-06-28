import { useEffect, useRef } from 'react'
import {
  createChart, CrosshairMode, LineStyle,
  type IChartApi, type ISeriesApi, type UTCTimestamp, type LogicalRange,
  type SeriesMarker,
} from 'lightweight-charts'
import type { Candle, JournalEntry } from '../../api/client'
import { calcRsi, calcMacd, calcAtr } from '../../utils/indicators'
import { useTerminal } from '../../context/TerminalContext'

interface Props {
  candles: Candle[]
  trades: JournalEntry[]
  upToBar?: number
}

const COMMON: Parameters<typeof createChart>[1] = {
  layout: { background: { color: '#131722' }, textColor: '#9598a1', fontSize: 10, fontFamily: 'monospace' },
  grid: { vertLines: { color: '#1e222d' }, horzLines: { color: '#1e222d' } },
  crosshair: {
    mode: CrosshairMode.Normal,
    vertLine: { color: '#434651', width: 1 as 1, style: 1, labelBackgroundColor: '#2962ff' },
    horzLine: { color: '#434651', width: 1 as 1, style: 1, labelBackgroundColor: '#2962ff' },
  },
  timeScale: { borderColor: '#2a2e39', timeVisible: true, secondsVisible: false },
  rightPriceScale: { borderColor: '#2a2e39' },
  handleScroll: true, handleScale: true,
}

function mkChart(el: HTMLDivElement, extra: Partial<Parameters<typeof createChart>[1]> = {}): IChartApi {
  return createChart(el, { ...COMMON, autoSize: true, ...extra } as Parameters<typeof createChart>[1])
}

const SUBPANEL: Partial<Parameters<typeof createChart>[1]> = {
  rightPriceScale: { borderColor: '#2a2e39', scaleMargins: { top: 0.1, bottom: 0.1 } },
}

export default function MainChart({ candles, trades, upToBar }: Props) {
  const mainRef = useRef<HTMLDivElement>(null)
  const rsiRef  = useRef<HTMLDivElement>(null)
  const macdRef = useRef<HTMLDivElement>(null)
  const atrRef  = useRef<HTMLDivElement>(null)

  const mcRef   = useRef<IChartApi | null>(null)
  const rcRef   = useRef<IChartApi | null>(null)
  const mc2Ref  = useRef<IChartApi | null>(null)
  const ac      = useRef<IChartApi | null>(null)

  const csSeries = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const volSer   = useRef<ISeriesApi<'Histogram'> | null>(null)
  const rsiSer   = useRef<ISeriesApi<'Line'> | null>(null)
  const macdSer  = useRef<ISeriesApi<'Line'> | null>(null)
  const sigSer   = useRef<ISeriesApi<'Line'> | null>(null)
  const histSer  = useRef<ISeriesApi<'Histogram'> | null>(null)
  const atrSer   = useRef<ISeriesApi<'Line'> | null>(null)

  const prevUpToBar = useRef<number | undefined>(undefined)

  // Sync with EquityChart via context
  const { mainChartRef, equityChartRef, chartSyncingRef, notifyCrosshairTime, subscribeCrosshairTime } = useTerminal()

  useEffect(() => {
    if (!mainRef.current || !rsiRef.current || !macdRef.current || !atrRef.current) return

    // ── Main chart ─────────────────────────────────────────────────────────
    const mc = mkChart(mainRef.current)
    mcRef.current = mc
    mainChartRef.current = mc
    csSeries.current = mc.addCandlestickSeries({
      upColor: '#089981', downColor: '#f23645',
      borderUpColor: '#089981', borderDownColor: '#f23645',
      wickUpColor: '#089981', wickDownColor: '#f23645',
    })
    volSer.current = mc.addHistogramSeries({ color: '#26a69a', priceFormat: { type: 'volume' }, priceScaleId: 'vol' })
    mc.priceScale('vol').applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } })

    // ── RSI ────────────────────────────────────────────────────────────────
    const rc = mkChart(rsiRef.current, SUBPANEL)
    rcRef.current = rc
    rsiSer.current = rc.addLineSeries({ color: '#2962ff', lineWidth: 1 as 1, title: 'RSI' });
    [30, 50, 70].forEach(lvl =>
      rsiSer.current!.createPriceLine({
        price: lvl, lineWidth: 1 as 1,
        color: lvl === 50 ? '#434651' : lvl === 30 ? '#f23645' : '#089981',
        lineStyle: LineStyle.Dashed, axisLabelVisible: false, title: '',
      })
    )

    // ── MACD ───────────────────────────────────────────────────────────────
    const mc2 = mkChart(macdRef.current, SUBPANEL)
    mc2Ref.current = mc2
    macdSer.current = mc2.addLineSeries({ color: '#2962ff', lineWidth: 1 as 1, title: 'MACD' })
    sigSer.current  = mc2.addLineSeries({ color: '#ff6d00', lineWidth: 1 as 1, title: 'Сигнал' })
    histSer.current = mc2.addHistogramSeries({ priceScaleId: 'mhist' })
    mc2.priceScale('mhist').applyOptions({ scaleMargins: { top: 0.75, bottom: 0 } })

    // ── ATR ────────────────────────────────────────────────────────────────
    const atrChart = mkChart(atrRef.current, SUBPANEL)
    ac.current = atrChart
    atrSer.current = atrChart.addLineSeries({ color: '#ffb800', lineWidth: 1 as 1, title: 'ATR' })

    // ── Internal 4-chart sync ──────────────────────────────────────────────
    let syncing = false
    const syncAll = (others: IChartApi[]) => (range: LogicalRange | null) => {
      if (syncing || !range) return
      syncing = true
      others.forEach(o => o.timeScale().setVisibleLogicalRange(range))
      syncing = false
    }
    mc.timeScale().subscribeVisibleLogicalRangeChange(syncAll([rc, mc2, atrChart]))
    rc.timeScale().subscribeVisibleLogicalRangeChange(syncAll([mc, mc2, atrChart]))
    mc2.timeScale().subscribeVisibleLogicalRangeChange(syncAll([mc, rc, atrChart]))
    atrChart.timeScale().subscribeVisibleLogicalRangeChange(syncAll([mc, rc, mc2]))

    // ── External sync with EquityChart (by visible TIME range) ───────────
    mc.timeScale().subscribeVisibleTimeRangeChange(range => {
      if (chartSyncingRef.current || !range) return
      const eq = equityChartRef.current
      if (!eq) return
      chartSyncingRef.current = true
      eq.timeScale().setVisibleRange(range)
      chartSyncingRef.current = false
    })

    // ── Crosshair → notify equity ──────────────────────────────────────────
    mc.subscribeCrosshairMove(param => {
      notifyCrosshairTime(param.time ? param.time as UTCTimestamp : null)
    })

    // ── Receive crosshair from equity → apply to main chart ────────────────
    const unsubCrosshair = subscribeCrosshairTime(time => {
      if (!time || !csSeries.current) return
      // LW Charts doesn't expose setCrosshairPosition on main chart directly,
      // but we can use applyOptions to show time label — handled by sync above
    })

    return () => {
      unsubCrosshair()
      mainChartRef.current = null
      mc.remove(); rc.remove(); mc2.remove(); atrChart.remove()
    }
  }, [])

  useEffect(() => {
    if (!csSeries.current || !candles.length) return
    const limit = upToBar !== undefined ? upToBar + 1 : candles.length
    const slice = candles.slice(0, limit)

    csSeries.current.setData(slice.map(c => ({
      time: c.time as UTCTimestamp, open: c.open, high: c.high, low: c.low, close: c.close,
    })))

    volSer.current?.setData(slice.map(c => ({
      time: c.time as UTCTimestamp, value: c.volume,
      color: c.close >= c.open ? '#08998166' : '#f2364566',
    })))

    const markers = trades
      .filter(t => t.entry_bar < limit)
      .flatMap(t => {
        const out: SeriesMarker<UTCTimestamp>[] = []
        if (t.entry_bar < limit && slice[t.entry_bar]) {
          out.push({
            time: slice[t.entry_bar].time as UTCTimestamp,
            position: 'belowBar', color: '#089981', shape: 'arrowUp',
            text: `BUY ${t.entry_price.toFixed(2)}`, size: 1,
          })
        }
        if (t.exit_bar < limit && slice[t.exit_bar]) {
          const isStop = /stop|sl/i.test(t.exit_reason ?? '')
          const isTp   = /tp|take/i.test(t.exit_reason ?? '')
          out.push({
            time: slice[t.exit_bar].time as UTCTimestamp,
            position: 'aboveBar',
            color: isStop ? '#f23645' : isTp ? '#089981' : t.is_winner ? '#2962ff' : '#f23645',
            shape: 'arrowDown',
            text: `${isStop ? 'STOP' : isTp ? 'TAKE PROFIT' : 'EXIT'} ${t.exit_price.toFixed(2)}`,
            size: 1,
          })
        }
        return out
      })
      .sort((a, b) => (a.time as number) - (b.time as number))
    csSeries.current.setMarkers(markers)

    const rsiVals = calcRsi(slice)
    rsiSer.current?.setData(slice.map((c, i) => ({ time: c.time as UTCTimestamp, value: rsiVals[i] ?? 50 })))

    const { macd, signal, hist } = calcMacd(slice)
    macdSer.current?.setData(slice.map((c, i) => ({ time: c.time as UTCTimestamp, value: macd[i] ?? 0 })))
    sigSer.current?.setData(slice.map((c, i) => ({ time: c.time as UTCTimestamp, value: signal[i] ?? 0 })))
    histSer.current?.setData(slice.map((c, i) => ({
      time: c.time as UTCTimestamp, value: hist[i] ?? 0,
      color: (hist[i] ?? 0) >= 0 ? '#08998166' : '#f2364566',
    })))

    const atrVals = calcAtr(slice)
    atrSer.current?.setData(slice.map((c, i) => ({ time: c.time as UTCTimestamp, value: atrVals[i] ?? 0 })))

    const justEntered = upToBar !== undefined && prevUpToBar.current === undefined
    prevUpToBar.current = upToBar
    if (upToBar === undefined || justEntered) {
      mcRef.current?.timeScale().fitContent()
      rcRef.current?.timeScale().fitContent()
      mc2Ref.current?.timeScale().fitContent()
      ac.current?.timeScale().fitContent()
    }
  }, [candles, trades, upToBar])

  const LabelRow = ({ text }: { text: string }) => (
    <div style={{
      flexShrink: 0, height: 20, background: '#131722',
      display: 'flex', alignItems: 'center', padding: '0 8px',
      borderTop: '1px solid #1e222d', gap: 8,
    }}>
      <span style={{ fontSize: 9, color: '#9598a1', fontFamily: 'monospace', letterSpacing: 1 }}>{text}</span>
    </div>
  )

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <div ref={mainRef} style={{ flex: 3, minHeight: 0 }} />
      <LabelRow text="RSI(14)" />
      <div ref={rsiRef} style={{ flex: 1, minHeight: 0 }} />
      <LabelRow text="MACD(12,26,9)" />
      <div ref={macdRef} style={{ flex: 1, minHeight: 0 }} />
      <LabelRow text="ATR(14)" />
      <div ref={atrRef} style={{ flex: 1, minHeight: 0 }} />
    </div>
  )
}
