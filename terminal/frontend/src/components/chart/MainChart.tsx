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

  // Trade hover tooltip
  const tradeTooltipRef = useRef<HTMLDivElement>(null)
  // Mutable refs so crosshair callback always sees latest data
  const tradesRef  = useRef<JournalEntry[]>(trades)
  const candlesRef = useRef<Candle[]>(candles)

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

  const { mainChartRef, equityChartRef, chartSyncingRef, notifyCrosshairTime, subscribeCrosshairTime } = useTerminal()

  // Keep mutable refs in sync with props
  useEffect(() => { tradesRef.current = trades }, [trades])
  useEffect(() => { candlesRef.current = candles }, [candles])

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

    // ── Crosshair: notify equity + show trade tooltip ──────────────────────
    mc.subscribeCrosshairMove(param => {
      notifyCrosshairTime(param.time ? param.time as UTCTimestamp : null)

      const tooltip = tradeTooltipRef.current
      if (!tooltip) return

      if (!param.time || !param.point) {
        tooltip.style.display = 'none'
        return
      }

      const barTime = param.time as number
      const currentTrades = tradesRef.current
      const currentCandles = candlesRef.current

      const matched = currentTrades.filter(t =>
        currentCandles[t.entry_bar]?.time === barTime ||
        currentCandles[t.exit_bar]?.time === barTime
      )

      if (!matched.length) {
        tooltip.style.display = 'none'
        return
      }

      const t = matched[0]
      const isEntry = currentCandles[t.entry_bar]?.time === barTime
      const price = isEntry ? t.entry_price : (t.exit_price ?? 0)
      const pnl = t.pnl ?? 0
      const pnlPct = t.pnl_pct ?? 0
      const pnlCol = pnl >= 0 ? '#089981' : '#f23645'

      const dir = (t as any).direction ?? 'LONG'

      tooltip.innerHTML = `
        <div style="font-size:8px;color:#9598a1;font-family:monospace;letter-spacing:0.5px;margin-bottom:3px">
          ${isEntry ? '▲ ВХОД' : '▼ ВЫХОД'} · ${dir}
        </div>
        <div style="font-size:13px;font-weight:700;color:#e0e3ea;font-family:monospace;margin-bottom:2px">
          ${price.toFixed(2)} ₽
        </div>
        ${!isEntry ? `
          <div style="font-size:10px;color:${pnlCol};font-family:monospace;font-weight:600">
            ${pnl >= 0 ? '+' : ''}${pnl.toFixed(0)} ₽ &nbsp;(${pnlPct >= 0 ? '+' : ''}${pnlPct.toFixed(2)}%)
          </div>
        ` : ''}
        ${!isEntry && t.exit_reason ? `
          <div style="font-size:9px;color:#9598a1;margin-top:3px;max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
            ${t.exit_reason}
          </div>
        ` : ''}
      `
      tooltip.style.display = 'block'

      const containerRect = mainRef.current!.getBoundingClientRect()
      const tw = 180
      const x = Math.min(param.point.x + 14, containerRect.width - tw - 4)
      const y = Math.max(param.point.y - 70, 4)
      tooltip.style.left = x + 'px'
      tooltip.style.top = y + 'px'
    })

    // ── Receive crosshair from equity ──────────────────────────────────────
    const unsubCrosshair = subscribeCrosshairTime(_time => {
      // Main chart crosshair is driven by user mouse — no-op here
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
      color: c.close >= c.open ? '#08998155' : '#f2364555',
    })))

    // ── Compact markers: NO price text, just shape ─────────────────────────
    const markers = trades
      .filter(t => t.entry_bar < limit)
      .flatMap(t => {
        const out: SeriesMarker<UTCTimestamp>[] = []
        if (t.entry_bar < limit && slice[t.entry_bar]) {
          out.push({
            time: slice[t.entry_bar].time as UTCTimestamp,
            position: 'belowBar', color: '#089981', shape: 'arrowUp',
            text: '', size: 1,
          })
        }
        if (t.exit_bar != null && t.exit_bar < limit && slice[t.exit_bar]) {
          const isStop = /stop|sl/i.test(t.exit_reason ?? '')
          const isTp   = /tp|take/i.test(t.exit_reason ?? '')
          out.push({
            time: slice[t.exit_bar].time as UTCTimestamp,
            position: 'aboveBar',
            color: isStop ? '#f23645' : isTp ? '#089981' : t.is_winner ? '#2962ff' : '#f23645',
            shape: 'arrowDown',
            text: '', size: 1,
          })
        }
        return out
      })
      // Deduplicate same-time markers keeping last
      .reduce<SeriesMarker<UTCTimestamp>[]>((acc, m) => {
        const idx = acc.findIndex(x => x.time === m.time && x.position === m.position)
        if (idx >= 0) acc[idx] = m; else acc.push(m)
        return acc
      }, [])
      .sort((a, b) => (a.time as number) - (b.time as number))

    csSeries.current.setMarkers(markers)

    const rsiVals = calcRsi(slice)
    rsiSer.current?.setData(slice.map((c, i) => ({ time: c.time as UTCTimestamp, value: rsiVals[i] ?? 50 })))

    const { macd, signal, hist } = calcMacd(slice)
    macdSer.current?.setData(slice.map((c, i) => ({ time: c.time as UTCTimestamp, value: macd[i] ?? 0 })))
    sigSer.current?.setData(slice.map((c, i) => ({ time: c.time as UTCTimestamp, value: signal[i] ?? 0 })))
    histSer.current?.setData(slice.map((c, i) => ({
      time: c.time as UTCTimestamp, value: hist[i] ?? 0,
      color: (hist[i] ?? 0) >= 0 ? '#08998155' : '#f2364555',
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
      flexShrink: 0, height: 18, background: '#131722',
      display: 'flex', alignItems: 'center', padding: '0 8px',
      borderTop: '1px solid #1e222d', gap: 8,
    }}>
      <span style={{ fontSize: 9, color: '#434651', fontFamily: 'monospace', letterSpacing: 0.5 }}>{text}</span>
    </div>
  )

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      {/* Main chart area — wrapped for tooltip positioning */}
      <div style={{ flex: 3, minHeight: 0, position: 'relative' }}>
        <div ref={mainRef} style={{ width: '100%', height: '100%' }} />
        {/* Trade marker hover tooltip */}
        <div
          ref={tradeTooltipRef}
          style={{
            display: 'none',
            position: 'absolute',
            pointerEvents: 'none',
            padding: '6px 10px',
            background: 'rgba(19,23,34,0.96)',
            border: '1px solid #2a2e39',
            borderRadius: 4,
            zIndex: 20,
            lineHeight: 1.5,
            backdropFilter: 'blur(4px)',
            minWidth: 140,
          }}
        />
      </div>
      <LabelRow text="RSI(14)" />
      <div ref={rsiRef} style={{ flex: 1, minHeight: 0 }} />
      <LabelRow text="MACD(12,26,9)" />
      <div ref={macdRef} style={{ flex: 1, minHeight: 0 }} />
      <LabelRow text="ATR(14)" />
      <div ref={atrRef} style={{ flex: 1, minHeight: 0 }} />
    </div>
  )
}
