// Shared design tokens — single source of truth for all pages
// Modify here, propagates everywhere.

import type React from 'react'

// ── Table styles ──────────────────────────────────────────────────────────────
export const TH: React.CSSProperties = {
  padding: '5px 8px', color: 'var(--t-text-3)', fontWeight: 700, letterSpacing: 0.4,
  fontSize: 9, textAlign: 'left', background: 'var(--t-panel)',
  borderBottom: '1px solid var(--t-border)', fontFamily: 'var(--t-font-mono)',
  position: 'sticky', top: 0, zIndex: 2, whiteSpace: 'nowrap',
  userSelect: 'none',
}

export const TH_R: React.CSSProperties = { ...TH, textAlign: 'right' }

export const TD: React.CSSProperties = {
  padding: '4px 8px', fontSize: 10, fontFamily: 'var(--t-font-mono)',
  whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
}

export const TD_R: React.CSSProperties = { ...TD, textAlign: 'right' }

export const TR_HOVER: React.CSSProperties = { borderBottom: '1px solid rgba(255,255,255,0.04)', cursor: 'pointer' }

// ── Section headers ───────────────────────────────────────────────────────────
export const SH_STYLE: React.CSSProperties = {
  fontSize: 9, letterSpacing: 0.8, color: 'var(--t-text-3)',
  fontFamily: 'var(--t-font-mono)', fontWeight: 700, padding: '10px 0 6px',
}

// ── Cards ─────────────────────────────────────────────────────────────────────
export const CARD: React.CSSProperties = {
  padding: '8px 10px', background: 'var(--t-elevated)', borderRadius: 4,
  border: '1px solid var(--t-border)', display: 'flex', flexDirection: 'column', gap: 3,
}

export const CARD_LABEL: React.CSSProperties = {
  fontSize: 8, color: 'var(--t-text-3)', fontFamily: 'var(--t-font-mono)',
  fontWeight: 700, letterSpacing: 0.5,
}

export const CARD_VALUE: React.CSSProperties = {
  fontSize: 14, fontWeight: 700, fontFamily: 'var(--t-font-mono)', color: 'var(--t-text)',
}

// ── Page header ───────────────────────────────────────────────────────────────
export const PAGE_HEADER: React.CSSProperties = {
  height: 40, flexShrink: 0, display: 'flex', alignItems: 'center',
  padding: '0 12px', background: 'var(--t-panel)',
  borderBottom: '1px solid var(--t-border)', gap: 8,
}

export const PAGE_TITLE: React.CSSProperties = {
  fontSize: 11, fontWeight: 700, fontFamily: 'var(--t-font-mono)',
  color: 'var(--t-text)', letterSpacing: 1,
}

// ── Common chip/badge ──────────────────────────────────────────────────────────
export function chipStyle(color: string): React.CSSProperties {
  return {
    fontSize: 8, padding: '1px 5px', borderRadius: 2, fontFamily: 'var(--t-font-mono)',
    fontWeight: 700, letterSpacing: 0.5,
    background: color + '22', color, border: `1px solid ${color}44`,
  }
}

// ── Sort indicator helper ──────────────────────────────────────────────────────
export function sortIcon(active: boolean, dir: 1 | -1): string {
  if (!active) return ''
  return dir === -1 ? ' ↓' : ' ↑'
}

// ── ECharts base config (dark theme) ─────────────────────────────────────────
export function echartsBase(extra?: Record<string, unknown>) {
  return {
    backgroundColor: 'transparent',
    textStyle: { fontFamily: 'monospace', fontSize: 9 },
    grid: { top: 30, right: 12, bottom: 24, left: 52 },
    xAxis: {
      type: 'category',
      axisLine: { lineStyle: { color: '#2a2e39' } },
      axisLabel: { color: '#6c7282', fontSize: 8, interval: 'auto' },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: '#1e222d', type: 'dashed' } as any },
      axisLabel: { color: '#6c7282', fontSize: 8 },
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#1e222d',
      borderColor: '#2a2e39',
      borderWidth: 1,
      textStyle: { color: '#d1d4dc', fontSize: 9 },
      axisPointer: { lineStyle: { color: '#434651', type: 'dashed' } },
    },
    toolbox: {
      right: 8, top: 4,
      itemSize: 11,
      iconStyle: { borderColor: '#6c7282' },
      emphasis: { iconStyle: { borderColor: '#d1d4dc' } },
      feature: {
        dataZoom: { yAxisIndex: 'none', title: { zoom: 'Zoom', back: 'Reset' } },
        restore: { title: 'Autoscale' },
        saveAsImage: { title: 'PNG', type: 'png', backgroundColor: '#131722' },
      },
    },
    dataZoom: [
      { type: 'inside', start: 0, end: 100 },
    ],
    ...extra,
  }
}

// ── Color helpers ──────────────────────────────────────────────────────────────
export function pnlColor(n: number | null | undefined): string {
  if (n == null) return 'var(--t-text-2)'
  return n >= 0 ? 'var(--t-green)' : 'var(--t-red)'
}

export function fmtPct(n: number | null | undefined, dec = 2): string {
  if (n == null || isNaN(n)) return '—'
  return `${n >= 0 ? '+' : ''}${n.toFixed(dec)}%`
}

export function fmtF(n: number | null | undefined, dec = 2): string {
  if (n == null || isNaN(n)) return '—'
  return n.toFixed(dec)
}

export function fmtRub(n: number): string {
  return `${n >= 0 ? '+' : ''}${Math.round(n).toLocaleString('ru-RU')} ₽`
}
