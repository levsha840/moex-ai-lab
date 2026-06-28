import { Badge } from '@mantine/core'

const STATUS_COLORS: Record<string, string> = {
  RESEARCH_PASS: 'green',
  RESEARCH_FAIL: 'red',
  VISUAL_BACKTEST: 'blue',
  APPROVED: 'green',
  REJECT: 'red',
  ARCHIVE: 'gray',
  REQUEST_MORE_EVIDENCE: 'yellow',
  PENDING: 'gray',
  NOT_STARTED: 'dark',
  CANDIDATE_RESEARCH_PASSED: 'teal',
  active: 'green',
  completed: 'blue',
  fail: 'red',
  pass: 'green',
  info: 'gray',
}

export default function StatusBadge({ status }: { status: string }) {
  const color = STATUS_COLORS[status] ?? 'gray'
  const label = status.replace(/_/g, ' ')
  return (
    <Badge size="xs" color={color} variant="light" radius="sm">
      {label}
    </Badge>
  )
}
