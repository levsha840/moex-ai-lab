import type { Candle } from '../api/client'

type Trade = { pnl_pct: number; capital_after: number }

function ema(arr: number[], n: number): number[] {
  const k = 2 / (n + 1)
  const out: number[] = [arr[0]]
  for (let i = 1; i < arr.length; i++) out.push(arr[i] * k + out[i - 1] * (1 - k))
  return out
}

export function calcRsi(candles: Candle[], period = 14): (number | null)[] {
  const closes = candles.map(c => c.close)
  if (closes.length < period + 1) return closes.map(() => null)
  const result: (number | null)[] = new Array(period).fill(null)
  let avgG = 0, avgL = 0
  for (let i = 1; i <= period; i++) {
    const d = closes[i] - closes[i - 1]
    if (d > 0) avgG += d; else avgL -= d
  }
  avgG /= period; avgL /= period
  const rsi = (g: number, l: number) => l === 0 ? 100 : g === 0 ? 0 : 100 - 100 / (1 + g / l)
  result.push(rsi(avgG, avgL))
  for (let i = period + 1; i < closes.length; i++) {
    const d = closes[i] - closes[i - 1]
    avgG = (avgG * (period - 1) + (d > 0 ? d : 0)) / period
    avgL = (avgL * (period - 1) + (d < 0 ? -d : 0)) / period
    result.push(rsi(avgG, avgL))
  }
  return result
}

export function calcMacd(candles: Candle[], fast = 12, slow = 26, sig = 9) {
  const c = candles.map(x => x.close)
  if (c.length < slow) return { macd: c.map(() => 0), signal: c.map(() => 0), hist: c.map(() => 0) }
  const e12 = ema(c, fast)
  const e26 = ema(c, slow)
  const macd = e12.map((v, i) => v - e26[i])
  const signal = ema(macd, sig)
  const hist = macd.map((v, i) => v - signal[i])
  return { macd, signal, hist }
}

export function calcRiskMetrics(trades: Trade[], initialCapital: number) {
  if (!trades.length) return { sharpe: 0, sortino: 0, calmar: 0, var95: 0, maxDD: 0, currentDD: 0 }
  const returns = trades.map(t => t.pnl_pct / 100)
  const n = returns.length
  const mean = returns.reduce((a, b) => a + b, 0) / n
  const std = Math.sqrt(returns.map(r => (r - mean) ** 2).reduce((a, b) => a + b, 0) / n)
  const downStd = Math.sqrt(returns.filter(r => r < 0).map(r => r ** 2).reduce((a, b) => a + b, 0) / Math.max(n, 1))
  const sharpe = std > 0 ? (mean / std) * Math.sqrt(n) : 0
  const sortino = downStd > 0 ? (mean / downStd) * Math.sqrt(n) : 0
  let peak = initialCapital, maxDD = 0
  for (const t of trades) {
    if (t.capital_after > peak) peak = t.capital_after
    maxDD = Math.max(maxDD, (peak - t.capital_after) / peak)
  }
  const finalCap = trades[trades.length - 1]?.capital_after ?? initialCapital
  const currentDD = peak > 0 ? (peak - finalCap) / peak : 0
  const calmar = maxDD > 0 ? (mean * n) / maxDD : 0
  const sorted = [...returns].sort((a, b) => a - b)
  const var95 = Math.abs(sorted[Math.floor(n * 0.05)] ?? 0)
  return {
    sharpe: +sharpe.toFixed(2),
    sortino: +sortino.toFixed(2),
    calmar: +calmar.toFixed(2),
    var95: +(var95 * 100).toFixed(2),
    maxDD: +(maxDD * 100).toFixed(2),
    currentDD: +(currentDD * 100).toFixed(2),
  }
}
