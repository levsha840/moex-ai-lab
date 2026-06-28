const BASE = '/api'

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}: ${path}`)
  return res.json() as Promise<T>
}

// Dashboard
export const fetchStatus = () => get<LabStatus>('/dashboard/status')
export const fetchActivity = () => get<ActivityEvent[]>('/dashboard/activity')

// Research
export const fetchHypotheses = () => get<Hypothesis[]>('/research/hypotheses')
export const fetchDatasets = (params?: { ticker?: string; period?: string; timeframe?: string }) => {
  const qs = params
    ? '?' + Object.entries(params).filter(([, v]) => v).map(([k, v]) => `${k}=${v}`).join('&')
    : ''
  return get<DatasetCell[]>(`/research/datasets${qs}`)
}
export const fetchCandles = (datasetId: string) => get<Candle[]>(`/research/datasets/${datasetId}/candles`)
export const fetchReports = () => get<ReportSummary[]>('/research/reports')
export const fetchReport = (hypothesisId: string, ticker: string, period: string, timeframe = '1h') =>
  get<Report>(`/research/reports/${hypothesisId}/${ticker}/${period}?timeframe=${timeframe}`)
export const fetchTradeDetail = (hypothesisId: string, ticker: string, period: string, tradeId: string) =>
  get<TradeDetail>(`/research/reports/${hypothesisId}/${ticker}/${period}/trades/${tradeId}`)

// Strategies
export const fetchStrategies = (status?: string) =>
  get<Strategy[]>(`/strategies${status ? `?status=${status}` : ''}`)

// Paper
export const fetchPaperSummary = () => get<PaperSummary>('/paper/summary')
export const fetchPaperEquity = () => get<EquityPoint[]>('/paper/equity')
export const fetchPaperPositions = () => get<Position[]>('/paper/positions')
export const fetchPaperTrades = () => get<Trade[]>('/paper/trades')

// Knowledge
export const fetchKnowledgeGraph = () => get<KnowledgeGraph>('/knowledge/graph')

// Scientist
export const fetchDecisions = () => get<Decision[]>('/scientist/decisions')
export const fetchScientistStats = () => get<Record<string, unknown>>('/scientist/stats')

// ── Types ──────────────────────────────────────────────────────────────────

export interface LabStatus {
  lab_version: string
  mode: string
  status: string
  generated_at: string
  hypotheses: { registered: number; tested: number; passed_alpha_gate: number; failed: number }
  research: { sessions: number; total_findings: number; total_windows: number; visual_backtest_reports: number }
  datasets: { total: number }
  candidates: { total: number; approved_for_paper: number }
  paper_trading: { enabled: boolean; positions: number; capital: number; pnl: number }
  knowledge_base: { snapshots: number }
  research_budget: { total: number; used: number; remaining: number }
}

export interface ActivityEvent {
  id: string; type: string; timestamp: string; title: string; detail: string; status: string
}

export interface Hypothesis {
  template_id: string; name: string; category: string; priority: string; strategy_name: string
}

export interface DatasetCell {
  ticker: string; period: string; timeframe: string; dataset_id: string
  status: string; bar_count: number; date_from: string; date_to: string; source: string
}

export interface Candle {
  time: number; ts: string; open: number; high: number; low: number; close: number; volume: number
}

export interface ReportSummary {
  report_id: string; hypothesis_id: string; ticker: string; period: string; timeframe: string
  dataset_id: string; generated_at: string; metrics: Metrics
  num_trades: number; total_return_pct: number; max_drawdown_pct: number; win_rate: number; profit_factor: number
}

export interface Report extends ReportSummary {
  initial_capital: number; trade_journal: JournalEntry[]; chart_path: string | null
}

export interface JournalEntry {
  trade_id: string; entry_timestamp: string; entry_bar: number; entry_price: number
  exit_timestamp: string; exit_bar: number; exit_price: number; exit_reason: string
  direction: string; pnl: number; pnl_pct: number; capital_before: number; capital_after: number; is_winner: boolean
}

export interface TradeDetail {
  trade: JournalEntry
  hypothesis_id: string; strategy_name: string
  entry_analysis: { signal_type: string; entry_bar: number; entry_price: number; entry_timestamp: string; reason: string; factors: Factor[] }
  exit_analysis: { exit_bar: number; exit_price: number; exit_timestamp: string; exit_reason: string; pnl: number; pnl_pct: number }
  chief_scientist: { decision: string; rationale: string }
}

export interface Factor {
  indicator: string; value: string; confirmed: boolean; note: string
}

export interface Metrics {
  initial_capital: number; final_capital: number; total_return: number; total_return_pct: number
  max_drawdown_pct: number; win_rate: number; profit_factor: number; num_trades: number
  avg_trade_pnl: number; avg_trade_pnl_pct: number; exposure_time_pct: number
}

export interface Strategy {
  id: string; strategy: string; template_id: string; strategy_name: string; status: string
  research_score: number | null; pass_rate: number | null; windows_total: number | null
  win_rate: number | null; profit_factor: number | null; total_return_pct: number | null
  max_drawdown_pct: number | null; paper_status: string; sandbox_status: string; source: string; generated_at: string
}

export interface PaperSummary {
  enabled: boolean; initial_capital: number; current_capital: number
  total_pnl: number; total_return_pct: number; max_drawdown_pct: number
  open_positions: number; total_trades: number; win_rate: number; exposure_pct: number; note: string
}

export interface EquityPoint { bar: number; capital: number; drawdown_pct: number }
export interface Position { id: string; ticker: string; entry_price: number; current_price: number; pnl: number }
export interface Trade { id: string; ticker: string; entry_price: number; exit_price: number; pnl: number; date: string }

export interface KnowledgeNode {
  id: string; label: string; type: string; color: string; size: number; description: string
}
export interface KnowledgeEdge { source: string; target: string; label: string; weight: number }
export interface KnowledgeGraph { nodes: KnowledgeNode[]; edges: KnowledgeEdge[] }

export interface Decision {
  id: string; type: string; timestamp: string; hypothesis_id: string; hypothesis_title: string
  rationale: string; stats: Record<string, unknown>; session_id: string; research_link: string
}
