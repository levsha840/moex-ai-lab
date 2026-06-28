import { Slider } from '@mantine/core'
import { useTerminal } from '../../context/TerminalContext'
import type { JournalEntry } from '../../api/client'

function computeCapital(trades: JournalEntry[], bar: number, initialCapital: number): number {
  let cap = initialCapital
  for (const t of trades) {
    if (t.exit_bar <= bar) cap = t.capital_after
  }
  return cap
}

const SPEEDS = [1, 5, 20, 100]

export default function ReplayOverlay() {
  const {
    candles, trades, currentSummary,
    replayActive, setReplayActive,
    replayBar, setReplayBar,
    replayPlaying, replaySpeed,
    startReplay, pauseReplay, stopReplay, setReplaySpeed,
  } = useTerminal()

  if (!replayActive) return null

  const totalBars = candles.length
  const initCap = (currentSummary?.metrics as any)?.initial_capital ?? 1_000_000
  const currentCap = computeCapital(trades, replayBar, initCap)
  const pnl = currentCap - initCap
  const pct = totalBars > 0 ? ((replayBar / (totalBars - 1)) * 100).toFixed(1) : '0.0'
  const tradesExecuted = trades.filter(t => t.exit_bar <= replayBar).length
  const candle = candles[replayBar]

  return (
    <>
      {/* Dim overlay backdrop */}
      <div style={{
        position: 'fixed', inset: 0, zIndex: 100,
        background: 'rgba(0,0,0,0.4)',
        pointerEvents: 'none',
      }} />

      {/* Control bar */}
      <div style={{
        position: 'fixed', bottom: 0, left: 200, right: 280, zIndex: 200,
        background: 'var(--t-panel)',
        borderTop: '2px solid var(--t-accent)',
        padding: '8px 16px',
        display: 'flex', flexDirection: 'column', gap: 8,
        pointerEvents: 'all',
      }}>
        {/* Status row */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <div style={{
            fontSize: 9, fontFamily: 'var(--t-font-mono)',
            color: 'var(--t-accent)', letterSpacing: 1, fontWeight: 700,
          }}>
            ▶ REPLAY MODE
          </div>
          {candle && (
            <div style={{ fontSize: 10, fontFamily: 'var(--t-font-mono)', color: 'var(--t-text-2)' }}>
              {candles[replayBar]?.ts?.slice(0, 10) ?? `Bar ${replayBar}`}
            </div>
          )}
          <div style={{ fontSize: 10, fontFamily: 'var(--t-font-mono)', color: 'var(--t-text-3)' }}>
            Bar {replayBar + 1} / {totalBars}  ·  {pct}%
          </div>
          <div style={{ fontSize: 10, fontFamily: 'var(--t-font-mono)', color: pnl >= 0 ? 'var(--t-green)' : 'var(--t-red)' }}>
            Capital: ₽{(currentCap / 1000).toFixed(1)}k ({pnl >= 0 ? '+' : ''}₽{(pnl / 1000).toFixed(1)}k)
          </div>
          <div style={{ fontSize: 10, fontFamily: 'var(--t-font-mono)', color: 'var(--t-text-2)' }}>
            Trades: {tradesExecuted}
          </div>
          <div style={{ flex: 1 }} />
          <button onClick={() => setReplayActive(false)} style={{
            background: 'none', border: '1px solid var(--t-border)', color: 'var(--t-text-3)',
            cursor: 'pointer', padding: '2px 8px', fontSize: 10, borderRadius: 2, fontFamily: 'var(--t-font-mono)',
          }}>
            CLOSE REPLAY
          </button>
        </div>

        {/* Scrubber */}
        <Slider
          value={replayBar}
          onChange={v => setReplayBar(v)}
          min={0}
          max={Math.max(totalBars - 1, 0)}
          step={1}
          size={3}
          color="blue"
          styles={{
            root: { flex: 1 },
            track: { backgroundColor: 'var(--t-elevated)' },
          }}
        />

        {/* Controls row */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {/* Play/Pause/Stop */}
          {[
            { label: '▶ PLAY',  action: startReplay,  active: replayPlaying  },
            { label: '⏸ PAUSE', action: pauseReplay,  active: !replayPlaying },
            { label: '⏹ STOP',  action: stopReplay,   active: false          },
          ].map(btn => (
            <button
              key={btn.label}
              onClick={btn.action}
              style={{
                padding: '3px 10px', fontSize: 10, fontFamily: 'var(--t-font-mono)',
                cursor: 'pointer', borderRadius: 2,
                background: btn.label.includes('PLAY') && replayPlaying ? 'var(--t-accent)' : 'var(--t-elevated)',
                border: `1px solid ${btn.label.includes('PLAY') && replayPlaying ? 'var(--t-accent)' : 'var(--t-border)'}`,
                color: btn.label.includes('PLAY') && replayPlaying ? '#fff' : 'var(--t-text-2)',
              }}
            >
              {btn.label}
            </button>
          ))}

          <div style={{ marginLeft: 12, fontSize: 9, color: 'var(--t-text-3)', letterSpacing: 1 }}>SPEED</div>
          {SPEEDS.map(s => (
            <button
              key={s}
              onClick={() => setReplaySpeed(s)}
              style={{
                padding: '3px 8px', fontSize: 10, fontFamily: 'var(--t-font-mono)',
                cursor: 'pointer', borderRadius: 2,
                background: replaySpeed === s ? 'var(--t-accent-soft)' : 'var(--t-elevated)',
                border: `1px solid ${replaySpeed === s ? 'var(--t-accent)' : 'var(--t-border)'}`,
                color: replaySpeed === s ? 'var(--t-accent)' : 'var(--t-text-3)',
              }}
            >
              ×{s}
            </button>
          ))}
        </div>
      </div>
    </>
  )
}
