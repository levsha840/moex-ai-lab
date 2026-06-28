interface Props {
  label: string
  value: string | number
  sub?: string
  cls?: 'up' | 'down' | 'cyan' | 'dim'
  mono?: boolean
}

export default function MetricCard({ label, value, sub, cls = 'dim', mono = true }: Props) {
  return (
    <div className="t-metric">
      <span className="t-metric-label">{label}</span>
      <div style={{ textAlign: 'right' }}>
        <div className={`t-metric-value ${cls}`} style={{ fontFamily: mono ? 'var(--t-font-mono)' : 'inherit' }}>
          {typeof value === 'number' ? value.toLocaleString('ru-RU') : value}
        </div>
        {sub && <div style={{ fontSize: 9, color: 'var(--t-text-3)', marginTop: 1 }}>{sub}</div>}
      </div>
    </div>
  )
}
