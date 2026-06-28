import { createContext, useContext, useState, useRef, useCallback, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  fetchStatus, fetchActivity, fetchReports, fetchReport, fetchCandles,
  fetchStrategies, fetchPaperSummary, fetchDecisions, fetchKnowledgeGraph,
} from '../api/client'
import type {
  LabStatus, ActivityEvent, ReportSummary, Report,
  Candle, JournalEntry, Strategy, PaperSummary, Decision, KnowledgeGraph,
} from '../api/client'

export type TopTab = 'terminal' | 'strategy' | 'knowledge' | 'scientist'
export type BottomTab = 'trades' | 'history' | 'positions' | 'activity' | 'aibrain'

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
  // data
  status: LabStatus | undefined
  reports: ReportSummary[]
  currentSummary: ReportSummary | undefined
  fullReport: Report | undefined
  candles: Candle[]
  trades: JournalEntry[]
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
  const [replayActive, setReplayActive] = useState(false)
  const [replayBar, setReplayBar] = useState(0)
  const [replayPlaying, setReplayPlaying] = useState(false)
  const [replaySpeed, setReplaySpeed] = useState(5)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Queries
  const { data: status }       = useQuery({ queryKey: ['status'],    queryFn: fetchStatus,       refetchInterval: 60_000 })
  const { data: activity = [] }= useQuery({ queryKey: ['activity'],  queryFn: fetchActivity,     refetchInterval: 60_000 })
  const { data: reports = [] } = useQuery({ queryKey: ['reports'],   queryFn: fetchReports })
  const { data: strategies = []}= useQuery({ queryKey: ['strategies'], queryFn: () => fetchStrategies() })
  const { data: paper }        = useQuery({ queryKey: ['paper'],     queryFn: fetchPaperSummary })
  const { data: decisions = []}= useQuery({ queryKey: ['decisions'], queryFn: fetchDecisions })
  const { data: knowledgeGraph }= useQuery({ queryKey: ['kg'],       queryFn: fetchKnowledgeGraph })

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

  const trades: JournalEntry[] = (fullReport as any)?.trade_journal ?? []

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
        if (b + replaySpeed >= total - 1) {
          setReplayPlaying(false)
          return total - 1
        }
        return b + replaySpeed
      })
    }, 50)
    return () => { if (intervalRef.current) clearInterval(intervalRef.current) }
  }, [replayPlaying, replayActive, replaySpeed, candles.length])

  useEffect(() => { setReplayBar(0); setReplayPlaying(false) }, [selectedIdx])

  const value: Ctx = {
    activeTab, setActiveTab,
    bottomTab, setBottomTab,
    selectedIdx, setSelectedIdx,
    explainTradeId, setExplainTradeId,
    selectedNode, setSelectedNode,
    replayActive, setReplayActive,
    replayBar, setReplayBar,
    replayPlaying, replaySpeed, startReplay, pauseReplay, stopReplay, setReplaySpeed,
    status, reports, currentSummary, fullReport, candles, trades,
    strategies, paper, decisions, activity, knowledgeGraph,
    isLoadingCandles, isLoadingReport,
  }

  return <TerminalCtx.Provider value={value}>{children}</TerminalCtx.Provider>
}

export const useTerminal = () => useContext(TerminalCtx)
