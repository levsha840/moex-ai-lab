import { useEffect, useRef, useCallback } from 'react'
import {
  createChart, CrosshairMode, LineStyle,
  type IChartApi, type ISeriesApi, type UTCTimestamp,
} from 'lightweight-charts'
import { useTerminal } from '../../context/TerminalContext'
import type { EquityPoint } from '../../utils/portfolio'
import { findEquityValue, COMPARE_COLORS } from '../../utils/portfolio'
import { IconArrowsMaximize, IconChartArea } from '@tabler/icons-react'

// ── Types ─────────────────────────────────────────────────────────────────────

export interface CompareSeriesData {
  label: string
  ticker: string
  color: string
  data: EquityPoint[]
}

interface Props {
  primaryData: EquityPoint[]
  primaryLabel: string
  compareData?: CompareSeriesData[]
  height?: number   // px; undefined = 100%
  compact?: boolean
  onOpenFull?: () => void
}

// ── Chart config ──────────────────────────────────────────────────────────────

const CHART_OPTS: Parameters<typeof createChart>[1] = {
  layout: {
    background: { color: '#131722' },
    textColor: '#9598a1',
    fontSize: 10,
    fontFamily: 'monospace',
  },
  grid: {
    vertLines: { color: '#1e222d' },
    horzLines: { color: '#1e222d' },
  },
  crosshair: {
    mode: CrosshairMode.Normal,
    vertLine: { color: '#434651', width: 1 as 1, style: LineStyle.Solid, labelBackgroundColor: '#2962ff' },
    horzLine: { color: '#434651', width: 1 as 1, style: LineStyle.Solid, labelBackgroundColor: '#089981' },
  },
  timeScale: {
    borderColor: '#2a2e39',
    timeVisible: true,
    secondsVisible: false,
    rightOffset: 5,
  },
  rightPriceScale: {
    borderColor: '#2a2e39',
    scaleMargins: { top: 0.1, bottom: 0.1 },
  },
  handleScroll: true,
  handleScale: true,
}

// ── Tooltip helper ────────────────────────────────────────────────────────────

function formatCapital(v: number): string {
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(3)} М₽`
  if (v >= 1_000) return `${(v / 1_000).toFixed(1)} к₽`
  return `${v.toFixed(0)} ₽`
}

function formatDate(time: number): string {
  return new Date(time * 1000).toLocaleDateString('ru-RU', {
    year: 'numeric', month: 'short', day: 'numeric',
  })
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function EquityChart({
  primaryData, primaryLabel, compareData = [],
  height, compact = false, onOpenFull,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const tooltipRef   = useRef<HTMLDivElement>(null)
  const chartRef     = useRef<IChartApi | null>(null)
  const primarySer   = useRef<ISeriesApi<'Area'> | null>(null)
  const compareSeries = useRef<ISeriesApi<'Line'>[]>([])

  const { equityChartRef, mainChartRef, chartSyncingRef, subscribeCrosshairTime, notifyCrosshairTime } = useTerminal()

  // ── Create chart ───────────────────────────────────────────────────────────
  useEffect(() => {
    if (!containerRef.current) return

    const chart = createChart(containerRef.current, {
      ...CHART_OPTS,
      autoSize: true,
    } as Parameters<typeof createChart>[1])

    chartRef.current = chart
    equityChartRef.current = chart

    // Primary area series
    primarySer.current = chart.addAreaSeries({
      lineColor: '#089981',
      topColor: 'rgba(8,153,129,0.28)',
      bottomColor: 'rgba(8,153,129,0.02)',
      lineWidth: 2,
      crosshairMarkerVisible: true,
      crosshairMarkerRadius: 4,
    })

    // Sync time range WITH main price chart (bidirectional)
    chart.timeScale().subscribeVisibleTimeRangeChange(range => {
      if (chartSyncingRef.current || !range) return
      const mc = mainChartRef.current
      if (!mc) return
      chartSyncingRef.current = true
      mc.timeScale().setVisibleRange(range)
      chartSyncingRef.current = false
    })

    // Crosshair move → notify MainChart
    chart.subscribeCrosshairMove(param => {
      notifyCrosshairTime(param.time ? param.time as UTCTimestamp : null)

      // Update tooltip (direct DOM for performance — no setState)
      const tooltip = tooltipRef.current
      if (!tooltip) return

      if (!param.time || !param.point || param.point.x < 0 || param.point.y < 0) {
        tooltip.style.display = 'none'
        return
      }

      const time = param.time as number
      const equity = findEquityValue(primaryData, time)
      if (equity === null) { tooltip.style.display = 'none'; return }

      // Initial capital from first point
      const initCap = primaryData[0]?.value ?? equity
      const pnlPct = initCap > 0 ? ((equity - initCap) / initCap * 100) : 0
      const pnlColor = pnlPct >= 0 ? '#089981' : '#f23645'

      const containerRect = containerRef.current!.getBoundingClientRect()
      const x = param.point.x
      const y = param.point.y

      tooltip.innerHTML = `
        <div style="font-size:10px;color:#9598a1;margin-bottom:3px;font-family:monospace">${formatDate(time)}</div>
        <div style="font-size:13px;font-weight:700;color:#e0e3ea;font-family:monospace">${formatCapital(equity)}</div>
        <div style="font-size:10px;color:${pnlColor};font-family:monospace">${pnlPct >= 0 ? '+' : ''}${pnlPct.toFixed(2)}%</div>
      `
      tooltip.style.display = 'block'

      const tw = tooltip.offsetWidth
      const th = tooltip.offsetHeight
      const left = Math.min(Math.max(x + 12, 0), (containerRect.width - tw - 8))
      const top = Math.max(y - th - 8, 8)
      tooltip.style.left = left + 'px'
      tooltip.style.top = top + 'px'
    })

    return () => {
      equityChartRef.current = null
      chart.remove()
    }
  }, [])

  // ── Receive crosshair from MainChart → set equity crosshair ───────────────
  useEffect(() => {
    const unsub = subscribeCrosshairTime(time => {
      const chart = chartRef.current
      const ser = primarySer.current
      if (!chart || !ser || !time) {
        chart?.clearCrosshairPosition()
        return
      }
      const val = findEquityValue(primaryData, time)
      if (val !== null) {
        chart.setCrosshairPosition(val, time as UTCTimestamp, ser)
      }
    })
    return unsub
  }, [primaryData, subscribeCrosshairTime])

  // ── Receive range from MainChart → sync time range ─────────────────────────
  // (already handled via ref in the chart creation effect)

  // ── Update primary equity data ─────────────────────────────────────────────
  useEffect(() => {
    const ser = primarySer.current
    if (!ser) return

    if (!primaryData.length) {
      ser.setData([])
      return
    }

    ser.setData(primaryData)
    chartRef.current?.timeScale().fitContent()
  }, [primaryData])

  // ── Update compare series ─────────────────────────────────────────────────
  useEffect(() => {
    const chart = chartRef.current
    if (!chart) return

    // Remove old compare series
    compareSeries.current.forEach(s => { try { chart.removeSeries(s) } catch {} })
    compareSeries.current = []

    // Add new
    compareData.forEach(cd => {
      if (!cd.data.length) return
      const s = chart.addLineSeries({
        color: cd.color,
        lineWidth: 1.5 as any,
        lineStyle: LineStyle.Solid,
        crosshairMarkerVisible: false,
        title: cd.ticker,
        priceLineVisible: false,
      })
      s.setData(cd.data)
      compareSeries.current.push(s)
    })
  }, [compareData])

  // ── Subscribe to range from main chart ────────────────────────────────────
  useEffect(() => {
    const mc = mainChartRef.current
    const eq = chartRef.current
    if (!mc || !eq) return

    const handler = (range: any) => {
      if (chartSyncingRef.current || !range) return
      chartSyncingRef.current = true
      eq.timeScale().setVisibleRange(range)
      chartSyncingRef.current = false
    }
    mc.timeScale().subscribeVisibleTimeRangeChange(handler)
    return () => { mc.timeScale().unsubscribeVisibleTimeRangeChange(handler) }
  })

  // ── Render ─────────────────────────────────────────────────────────────────

  const containerStyle: React.CSSProperties = {
    position: 'relative',
    height: height !== undefined ? height : '100%',
    minHeight: compact ? 80 : 120,
    background: '#131722',
  }

  return (
    <div style={containerStyle}>
      {/* LW Charts container */}
      <div ref={containerRef} style={{ width: '100%', height: '100%' }} />

      {/* Tooltip */}
      <div
        ref={tooltipRef}
        style={{
          display: 'none',
          position: 'absolute',
          pointerEvents: 'none',
          padding: '6px 8px',
          background: 'rgba(30,34,45,0.95)',
          border: '1px solid #2a2e39',
          borderRadius: 4,
          zIndex: 10,
          lineHeight: 1.4,
          minWidth: 120,
        }}
      />

      {/* Toolbar */}
      <div style={{
        position: 'absolute',
        top: 4, right: 4,
        display: 'flex',
        gap: 4,
        zIndex: 5,
      }}>
        {onOpenFull && (
          <button
            onClick={onOpenFull}
            title="Открыть полностью"
            style={{
              display: 'flex', alignItems: 'center', gap: 4,
              padding: '3px 7px',
              background: 'rgba(30,34,45,0.85)',
              border: '1px solid #2a2e39',
              borderRadius: 3,
              color: '#9598a1',
              cursor: 'pointer',
              fontSize: 9,
              fontFamily: 'monospace',
            }}
          >
            <IconArrowsMaximize size={10} />
            Открыть полностью
          </button>
        )}
        <button
          onClick={() => chartRef.current?.timeScale().fitContent()}
          title="Авто-масштаб"
          style={{
            display: 'flex', alignItems: 'center',
            padding: '3px 6px',
            background: 'rgba(30,34,45,0.85)',
            border: '1px solid #2a2e39',
            borderRadius: 3,
            color: '#9598a1',
            cursor: 'pointer',
            fontSize: 9,
            fontFamily: 'monospace',
          }}
        >
          <IconChartArea size={10} />
        </button>
      </div>

      {/* No data state */}
      {!primaryData.length && (
        <div style={{
          position: 'absolute', inset: 0,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: '#434651', fontSize: 10, fontFamily: 'monospace',
          flexDirection: 'column', gap: 4,
        }}>
          <IconChartArea size={24} style={{ opacity: 0.3 }} />
          <span>Нет данных</span>
        </div>
      )}

      {/* Compare legend */}
      {compareData.length > 0 && (
        <div style={{
          position: 'absolute',
          top: 4, left: 6,
          display: 'flex', flexWrap: 'wrap', gap: '3px 8px',
          zIndex: 5,
          maxWidth: '60%',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <div style={{ width: 20, height: 2, background: '#089981', borderRadius: 1 }} />
            <span style={{ fontSize: 8, color: '#9598a1', fontFamily: 'monospace' }}>{primaryLabel}</span>
          </div>
          {compareData.map(cd => (
            <div key={cd.label} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <div style={{ width: 20, height: 2, background: cd.color, borderRadius: 1 }} />
              <span style={{ fontSize: 8, color: '#9598a1', fontFamily: 'monospace' }}>{cd.ticker}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
