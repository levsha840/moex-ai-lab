type Cls = 'green' | 'red' | 'amber' | 'blue' | 'cyan' | 'gray'

const MAP: Record<string, Cls> = {
  RESEARCH_PASS: 'green',     RESEARCH_FAIL: 'red',
  VISUAL_BACKTEST: 'blue',    APPROVE: 'green',
  APPROVED: 'green',          REJECT: 'red',
  ARCHIVE: 'gray',            REQUEST_MORE_EVIDENCE: 'amber',
  MONITOR: 'blue',            PENDING: 'gray',
  NOT_STARTED: 'gray',        CANDIDATE_RESEARCH_PASSED: 'cyan',
  active: 'green',            completed: 'blue',
  fail: 'red',                pass: 'green',
  info: 'gray',               STANDBY: 'amber',
}

export default function StatusBadge({ status }: { status: string }) {
  const cls: Cls = MAP[status] ?? 'gray'
  return (
    <span className={`t-chip ${cls}`}>
      {status.replace(/_/g, ' ')}
    </span>
  )
}
