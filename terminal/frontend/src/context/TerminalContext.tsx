import { createContext, useContext, useState, useRef, useCallback, useEffect, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  fetchStatus, fetchActivity, fetchReports, fetchReport, fetchCandles, fetchDatasets,
  fetchStrategies, fetchPaperSummary, fetchDecisions, fetchKnowledgeGraph,
} from '../api/client'
import type {
  LabStatus, ActivityEvent, ReportSummary, Report, DatasetCell,
  Candle, JournalEntry, Strategy, PaperSummary, Decision, KnowledgeGraph,
} from '../api/client'
import type { IChartApi, UTCTimestamp } from 'lightweight-charts'
import { type TF, parseNativeTF, availableTFs, resampleData } from '../utils/resample'

// Nav tabs visible in the top bar (visual only)
export type TopTab =
  | 'terminal'   // Торговый терминал
  | 'strategy'   // Стратегии
  | 'history'    // История торгов
  | 'backtests'  // Бэктесты
  | 'portfolio'  // Портфель
  | 'risks'      // Риски
  | 'reports'    // Отчёты
  | 'scientist'  // Аналитика (legacy)
  | 'knowledge'  // База знаний (legacy)
  | 'settings'   // Настройки

export type BottomTab = 'trades' | 'history' | 'positions' | 'activity' | 'aibrain'

type RangeListener = (from: number, to: number) => void
type CrosshairListener = (time: number | null) => void

interface Ctx {
  activeTab: TopTab
  setActiveTab: (t: TopTab) => void
  bottomTab: BottomTab
  setBottomTab: (t: BottomTab) => void
  selectedIdx: number
  setSelectedIdx: (i: number) => void
  explainTradeId: string | null
  setExplainTradeId: (id: string | null) => void
  selectedNode: string | null
  setSelectedNode: (n: string | null) => void
  selectedTradeId: string | null
  setSelectedTradeId: (id: string | null) => void
  replayActive: boolean
  setReplayActive: (v: boolean) => void
  replayBar: number
  setReplayBar: (b: number | ((prev: number) => number)) => void
  replayPlaying: boolean
  replaySpeed: number
  startReplay: () => void
  pauseReplay: () => void
  stopReplay: () => void
  setReplaySpeed: (s: number) => void
  // Equity UI state
  compareMode: boolean
  setCompareMode: (v: boolean) => void
  equityExpanded: boolean
  setEquityExpanded: (v: boolean) => void
  // Timeframe
  selectedTimeframe: TF
  setSelectedTimeframe: (tf: TF) => void
  nativeTF: TF
  displayCandles: Candle[]
  displayTrades: JournalEntry[]
  barMapping: number[]
  // Chart interaction
  jumpToBar: (originalBar: number) => void
  jumpToBarRef: React.MutableRefObject<((bar: number) => void) | null>
  pendingJumpBar: React.MutableRefObject<number | null>
  // Chart sync refs
  mainChartRef: React.MutableRefObject<IChartApi | null>
  equityChartRef: React.MutableRefObject<IChartApi | null>
  chartSyncingRef: React.MutableRefObject<boolean>
  notifyCrosshairTime: (t: UTCTimestamp | null) => void
  subscribeCrosshairTime: (cb: CrosshairListener) => () => void
  // data
  status: LabStatus | undefined
  reports: ReportSummary[]
  currentSummary: ReportSummary | undefined
  fullReport: Report | undefined
  allFullReports: Report[]
  candles: Candle[]
  trades: JournalEntry[]
  datasets: DatasetCell[]
  strategies: Strategy[]
  paper: PaperSummary | undefined
  decisions: Decision[]
  activity: ActivityEvent[]
  knowledgeGraph: KnowledgeGraph | undefined
  isLoadingCandles: boolean
  isLoadingReport: boolean
}

const TerminalCtx = createContext<Ctx>(null as unknown as Ctx)

export function TerminalProvider({ children }: { children: React.ReactNode }) {
  const [activeTab, setActiveTab] = useState<TopTab>('terminal')
  const [bottomTab, setBottomTab] = useState<BottomTab>('trades')
  const [selectedIdx, setSelectedIdx] = useState(0)
  const [explainTradeId, setExplainTradeId] = useState<string | null>(null)
  const [selectedNode, setSelectedNode] = useState<string | null>(null)
  const [selectedTradeId, setSelectedTradeId] = useState<string | null>(null)
  const [replayActive, setReplayActive] = useState(false)
  const [replayBar, setReplayBar] = useState(0)
  const [replayPlaying, setReplayPlaying] = useState(false)
  const [replaySpeed, setReplaySpeed] = useState(5)
  const [compareMode, setCompareMode] = useState(false)
  const [equityExpanded, setEquityExpanded] = useState(false)
  const [selectedTimeframe, setSelectedTimeframe] = useState<TF>('1H')
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const jumpToBarRef = useRef<((bar: number) => void) | null>(null)
  const pendingJumpBar = useRef<number | null>(null)

  const mainChartRef = useRef<IChartApi | null>(null)
  const equityChartRef = useRef<IChartApi | null>(null)
  const chartSyncingRef = useRef(false)

  const crosshairSubscribers = useRef<Set<CrosshairListener>>(new Set())
  const notifyCrosshairTime = useCallback((t: UTCTimestamp | null) => {
    crosshairSubscribers.current.forEach(cb => cb(t as number | null))
  }, [])
  const subscribeCrosshairTime = useCallback((cb: CrosshairListener) => {
    crosshairSubscribers.current.add(cb)
    return () => { crosshairSubscribers.current.delete(cb) }
  }, [])

  // Queries
  const { data: status }        = useQuery({ queryKey: ['status'],     queryFn: fetchStatus,         refetchInterval: 60_000 })
  const { data: activity = [] } = useQuery({ queryKey: ['activity'],   queryFn: fetchActivity,       refetchInterval: 60_000 })
  const { data: reports = [] }  = useQuery({ queryKey: ['reports'],    queryFn: fetchReports })
  const { data: datasets = [] } = useQuery({ queryKey: ['datasets'],   queryFn: () => fetchDatasets() })
  const { data: strategies = []}= useQuery({ queryKey: ['strategies'], queryFn: () => fetchStrategies() })
  const { data: paper }         = useQuery({ queryKey: ['paper'],      queryFn: fetchPaperSummary })
  const { data: decisions = []} = useQuery({ queryKey: ['decisions'],  queryFn: fetchDecisions })
  const { data: knowledgeGraph }= useQuery({ queryKey: ['kg'],         queryFn: fetchKnowledgeGraph })

  const currentSummary = reports[selectedIdx]

  const { data: fullReport, isLoading: isLoadingReport } = useQuery({
    queryKey: ['report', currentSummary?.hypothesis_id, currentSummary?.ticker, currentSummary?.period, currentSummary?.timeframe],
    queryFn: () => fetchReport(currentSummary!.hypothesis_id, currentSummary!.ticker, currentSummary!.period, currentSummary!.timeframe),
    enabled: !!currentSummary,
  })

  const { data: candles = [], isLoading: isLoadingCandles } = useQuery({
    queryKey: ['candles', currentSummary?.dataset_id],
    queryFn: () => fetchCandles(currentSummary!.dataset_id),
    enabled: !!currentSummary,
  })

  const { data: allFullReports = [] } = useQuery({
    queryKey: ['all-full-reports', reports.map(r => r.report_id).join(',')],
    queryFn: () => Promise.all(reports.map(r => fetchReport(r.hypothesis_id, r.ticker, r.period, r.timeframe))),
    enabled: reports.length > 0,
  })

  const trades: JournalEntry[] = (fullReport as any)?.trade_journal ?? []

  // ── Timeframe resampling ───────────────────────────────────────────────────
  const nativeTF = currentSummary ? parseNativeTF(currentSummary.timeframe) : '1H' as TF

  const { candles: displayCandles, barMapping } = useMemo(() => {
    if (!candles.length) return { candles: [] as Candle[], barMapping: [] as number[] }
    const tfToUse = availableTFs(nativeTF).has(selectedTimeframe) ? selectedTimeframe : nativeTF
    return resampleData(candles, nativeTF, tfToUse)
  }, [candles, nativeTF, selectedTimeframe])

  const displayTrades = useMemo(() =>
    trades.map(t => ({
      ...t,
      entry_bar: barMapping[t.entry_bar] ?? Math.max(0, displayCandles.length - 1),
      exit_bar:  barMapping[t.exit_bar]  ?? Math.max(0, displayCandles.length - 1),
    }))
  , [trades, barMapping, displayCandles.length])

  const jumpToBar = useCallback((originalBar: number) => {
    const mapped = barMapping[originalBar] ?? originalBar
    if (jumpToBarRef.current) {
      jumpToBarRef.current(mapped)
    } else {
      pendingJumpBar.current = mapped
    }
  }, [barMapping])

  // Replay logic
  const startReplay = useCallback(() => {
    if (!replayActive) setReplayActive(true)
    setReplayPlaying(true)
  }, [replayActive])

  const pauseReplay = useCallback(() => {
    setReplayPlaying(false)
    if (intervalRef.current) clearInterval(intervalRef.current)
  }, [])

  const stopReplay = useCallback(() => {
    setReplayPlaying(false)
    setReplayBar(0)
    if (intervalRef.current) clearInterval(intervalRef.current)
  }, [])

  useEffect(() => {
    if (intervalRef.current) clearInterval(intervalRef.current)
    if (!replayPlaying || !replayActive) return
    const total = candles.length
    intervalRef.current = setInterval(() => {
      setReplayBar(b => {
        if (b + replaySpeed >= total - 1) { setReplayPlaying(false); return total - 1 }
        return b + replaySpeed
      })
    }, 50)
    return () => { if (intervalRef.current) clearInterval(intervalRef.current) }
  }, [replayPlaying, replayActive, replaySpeed, candles.length])

  useEffect(() => {
    setReplayBar(0)
    setReplayPlaying(false)
    setSelectedTradeId(null)
    // Reset to native timeframe when switching strategy
    setSelectedTimeframe(currentSummary ? parseNativeTF(currentSummary.timeframe) : '1H')
  }, [selectedIdx]) // eslint-disable-line

  const value: Ctx = {
    activeTab, setActiveTab,
    bottomTab, setBottomTab,
    selectedIdx, setSelectedIdx,
    explainTradeId, setExplainTradeId,
    selectedNode, setSelectedNode,
    selectedTradeId, setSelectedTradeId,
    replayActive, setReplayActive,
    replayBar, setReplayBar,
    replayPlaying, replaySpeed, startReplay, pauseReplay, stopReplay, setReplaySpeed,
    compareMode, setCompareMode,
    equityExpanded, setEquityExpanded,
    selectedTimeframe, setSelectedTimeframe, nativeTF,
    displayCandles, displayTrades, barMapping,
    jumpToBar, jumpToBarRef, pendingJumpBar,
    mainChartRef, equityChartRef, chartSyncingRef,
    notifyCrosshairTime, subscribeCrosshairTime,
    status, reports, currentSummary, fullReport, allFullReports, candles, trades,
    datasets, strategies, paper, decisions, activity, knowledgeGraph,
    isLoadingCandles, isLoadingReport,
  }

  return <TerminalCtx.Provider value={value}>{children}</TerminalCtx.Provider>
}

export const useTerminal = () => useContext(TerminalCtx)
