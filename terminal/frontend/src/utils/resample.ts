import type { Candle } from '../api/client'

export type TF = '1m' | '5m' | '15m' | '1H' | '4H' | '1D'

export const TF_LABEL: Record<TF, string> = {
  '1m': '1М', '5m': '5М', '15m': '15М', '1H': '1Ч', '4H': '4Ч', '1D': '1Д',
}

export const TF_MINUTES: Record<TF, number> = {
  '1m': 1, '5m': 5, '15m': 15, '1H': 60, '4H': 240, '1D': 1440,
}

export interface ResampledData {
  candles: Candle[]
  barMapping: number[]  // originalBarIndex → resampledBarIndex
}

/** Parse backend timeframe string → TF enum */
export function parseNativeTF(s: string): TF {
  const t = (s ?? '').toLowerCase().trim()
  if (t === '1d' || t === 'd' || t.includes('day'))  return '1D'
  if (t === '4h' || t === '240m')                    return '4H'
  if (t === '1h' || t === 'h' || t === '60m' || t === '60') return '1H'
  if (t === '15m' || t === '15min')                  return '15m'
  if (t === '5m'  || t === '5min')                   return '5m'
  if (t === '1m'  || t === 'm' || t === '1min')      return '1m'
  return '1H'
}

/** Which TFs can be shown from native resolution (upsampling only) */
export function availableTFs(native: TF): Set<TF> {
  const nMin = TF_MINUTES[native]
  return new Set(
    (Object.entries(TF_MINUTES) as [TF, number][])
      .filter(([, m]) => m >= nMin)
      .map(([tf]) => tf)
  )
}

/** Resample candles + build barMapping (original → resampled bar index) */
export function resampleData(candles: Candle[], nativeTF: TF, targetTF: TF): ResampledData {
  if (!candles.length) return { candles: [], barMapping: [] }
  if (targetTF === nativeTF) return { candles, barMapping: candles.map((_, i) => i) }

  const nMin = TF_MINUTES[nativeTF]
  const tMin = TF_MINUTES[targetTF]
  if (tMin < nMin) return { candles, barMapping: candles.map((_, i) => i) } // can't go below native

  if (targetTF === '1D') return resampleByDay(candles)
  return resampleByMultiplier(candles, Math.round(tMin / nMin))
}

function resampleByMultiplier(candles: Candle[], mult: number): ResampledData {
  const result: Candle[] = []
  const barMapping = new Array(candles.length).fill(0)
  let i = 0
  while (i < candles.length) {
    const end = Math.min(i + mult, candles.length)
    result.push(aggregate(candles, i, end))
    const ri = result.length - 1
    for (let j = i; j < end; j++) barMapping[j] = ri
    i += mult
  }
  return { candles: result, barMapping }
}

function resampleByDay(candles: Candle[]): ResampledData {
  const MSK = 3 * 3600
  const groups = new Map<number, { start: number; end: number }>()

  // Find group boundaries
  const keys: number[] = []
  for (let i = 0; i < candles.length; i++) {
    const k = Math.floor((candles[i].time + MSK) / 86400)
    if (!groups.has(k)) { groups.set(k, { start: i, end: i }); keys.push(k) }
    else groups.get(k)!.end = i
  }
  keys.sort((a, b) => a - b)

  const result: Candle[] = []
  const barMapping = new Array(candles.length).fill(0)
  for (const k of keys) {
    const { start, end } = groups.get(k)!
    result.push(aggregate(candles, start, end + 1))
    const ri = result.length - 1
    for (let j = start; j <= end; j++) barMapping[j] = ri
  }
  return { candles: result, barMapping }
}

function aggregate(candles: Candle[], from: number, to: number): Candle {
  let hi = candles[from].high, lo = candles[from].low, vol = 0
  for (let i = from; i < to; i++) {
    if (candles[i].high > hi) hi = candles[i].high
    if (candles[i].low  < lo) lo = candles[i].low
    vol += candles[i].volume
  }
  return {
    time:   candles[from].time,
    ts:     candles[from].ts,
    open:   candles[from].open,
    high:   hi,
    low:    lo,
    close:  candles[to - 1].close,
    volume: vol,
  }
}
