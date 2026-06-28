import { Paper, Text, Group, rem } from '@mantine/core'
import type { ReactNode } from 'react'

interface Props {
  label: string
  value: string | number
  sub?: string
  color?: string
  icon?: ReactNode
  trend?: 'up' | 'down' | 'neutral'
}

export default function MetricCard({ label, value, sub, color = '#e6edf3', icon, trend }: Props) {
  const trendColor = trend === 'up' ? '#3fb950' : trend === 'down' ? '#f85149' : '#8b949e'
  return (
    <Paper p="md" style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: 8 }}>
      <Group justify="space-between" mb={4}>
        <Text size="10px" c="#8b949e" tt="uppercase" style={{ letterSpacing: 1 }}>
          {label}
        </Text>
        {icon && <span style={{ color: '#8b949e' }}>{icon}</span>}
      </Group>
      <Text size="xl" fw={700} c={color} ff="monospace" lh={1.2}>
        {typeof value === 'number' ? value.toLocaleString() : value}
      </Text>
      {sub && (
        <Text size="11px" c={trendColor} mt={2}>
          {sub}
        </Text>
      )}
    </Paper>
  )
}
