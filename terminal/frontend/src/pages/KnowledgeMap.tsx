import { useState, useCallback, useRef, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import ReactECharts from 'echarts-for-react'
import { fetchKnowledgeGraph } from '../api/client'
import type { KnowledgeNode } from '../api/client'

// ── Node type config ──────────────────────────────────────────────────────────

const TYPE_CFG: Record<string, { color: string; shape: string; label: string }> = {
  root:       { color: '#f0883e', shape: 'diamond',   label: 'Root'       },
  category:   { color: '#00b0ff', shape: 'roundRect', label: 'Category'   },
  hypothesis: { color: '#089981', shape: 'circle',    label: 'Hypothesis' },
  instrument: { color: '#ffb800', shape: 'rect',      label: 'Instrument' },
  regime:     { color: '#9c27b0', shape: 'triangle',  label: 'Regime'     },
  evidence:   { color: '#f23645', shape: 'pin',       label: 'Evidence'   },
}

const typeColor = (t: string) => TYPE_CFG[t]?.color ?? '#9598a1'
const typeShape = (t: string) => TYPE_CFG[t]?.shape ?? 'circle'

// ── Side details panel ────────────────────────────────────────────────────────

function SidePanel({ node, onClose }: { node: KnowledgeNode; onClose: () => void }) {
  const cfg = TYPE_CFG[node.type]
  return (
    <div style={{
      position: 'absolute', top: 0, right: 0, bottom: 0, width: 260,
      background: 'rgba(19,23,34,0.97)', borderLeft: '1px solid #2a2e39',
      display: 'flex', flexDirection: 'column', zIndex: 10,
      backdropFilter: 'blur(4px)',
    }}>
      {/* header */}
      <div style={{ padding: '10px 14px 8px', borderBottom: '1px solid #2a2e39', display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ width: 9, height: 9, borderRadius: node.type === 'root' ? 2 : '50%', background: cfg?.color ?? '#9598a1', flexShrink: 0 }} />
        <span style={{ flex: 1, fontSize: 11, fontWeight: 700, fontFamily: 'monospace', color: '#e6edf3', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {node.label}
        </span>
        <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#8b949e', fontSize: 14, lineHeight: 1, padding: 2 }}>✕</button>
      </div>

      {/* body */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '12px 14px' }}>
        {/* type chip */}
        <div style={{ marginBottom: 14 }}>
          <span style={{
            fontSize: 9, padding: '2px 8px', borderRadius: 2, fontFamily: 'monospace', fontWeight: 700, letterSpacing: 0.5,
            background: (cfg?.color ?? '#9598a1') + '22', color: cfg?.color ?? '#9598a1',
            border: `1px solid ${(cfg?.color ?? '#9598a1')}44`,
          }}>
            {node.type.toUpperCase()}
          </span>
        </div>

        {/* description */}
        {node.description && (
          <div style={{ marginBottom: 14 }}>
            <div style={{ fontSize: 8, color: '#8b949e', fontFamily: 'monospace', fontWeight: 700, letterSpacing: 0.5, marginBottom: 5 }}>ОПИСАНИЕ</div>
            <div style={{ fontSize: 10, color: '#d1d4dc', fontFamily: 'monospace', lineHeight: 1.6 }}>{node.description}</div>
          </div>
        )}

        {/* id */}
        <div>
          <div style={{ fontSize: 8, color: '#8b949e', fontFamily: 'monospace', fontWeight: 700, letterSpacing: 0.5, marginBottom: 5 }}>ID</div>
          <div style={{ fontSize: 9, color: '#8b949e', fontFamily: 'monospace', wordBreak: 'break-all' }}>{node.id}</div>
        </div>
      </div>
    </div>
  )
}

// ── Main ──────────────────────────────────────────────────────────────────────

export default function KnowledgeMap() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['knowledge-graph'],
    queryFn: fetchKnowledgeGraph,
    staleTime: 60_000,
  })

  const [selected, setSelected] = useState<KnowledgeNode | null>(null)
  const chartRef = useRef<any>(null)

  // Build ECharts option whenever data changes
  const option = useCallback(() => {
    if (!data) return {}
    const { nodes, edges } = data

    const eNodes = nodes.map(n => ({
      id: n.id,
      name: n.label,
      symbolSize: Math.max(n.size, 12),
      symbol: typeShape(n.type),
      itemStyle: {
        color: typeColor(n.type),
        borderColor: typeColor(n.type) + '55',
        borderWidth: n.type === 'root' ? 3 : 1,
        shadowBlur: n.type === 'root' ? 20 : 0,
        shadowColor: typeColor(n.type) + '80',
      },
      label: {
        show: n.size >= 16,
        color: '#e6edf3',
        fontSize: n.type === 'root' ? 13 : n.size >= 25 ? 10 : 9,
        fontFamily: 'monospace',
        fontWeight: n.type === 'root' ? 700 : 400,
        distance: 5,
      },
      emphasis: {
        itemStyle: {
          borderWidth: 3,
          borderColor: typeColor(n.type),
          shadowBlur: 30,
          shadowColor: typeColor(n.type) + 'aa',
        },
      },
    }))

    const eEdges = edges.map(e => ({
      source: e.source,
      target: e.target,
      lineStyle: {
        color: '#2a2e39',
        width: Math.max(e.weight ?? 1, 0.5),
        curveness: 0.08,
        opacity: 0.7,
      },
      emphasis: { lineStyle: { color: '#434651', width: 2, opacity: 1 } },
    }))

    return {
      backgroundColor: '#0d1117',
      tooltip: {
        trigger: 'item',
        backgroundColor: '#1e222d',
        borderColor: '#2a2e39',
        borderWidth: 1,
        padding: [8, 12],
        textStyle: { color: '#d1d4dc', fontSize: 11, fontFamily: 'monospace' },
        formatter: (params: any) => {
          if (params.dataType === 'edge') return ''
          const n = data.nodes.find(nd => nd.id === params.data.id)
          if (!n) return params.data.name
          const dot = `<span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:${typeColor(n.type)};margin-right:5px"></span>`
          return `${dot}<b>${n.label}</b><br/><span style="color:#8b949e;font-size:10px">${n.type}</span>${n.description ? `<br/><span style="color:#9598a1;font-size:10px">${n.description}</span>` : ''}`
        },
      },
      series: [{
        type: 'graph',
        layout: 'force',
        data: eNodes,
        links: eEdges,
        roam: true,
        draggable: true,
        zoom: 0.85,
        force: {
          initLayout: 'circular',
          repulsion: 280,
          gravity: 0.08,
          edgeLength: [60, 220],
          friction: 0.5,
          layoutAnimation: true,
        },
        emphasis: {
          focus: 'adjacency',
          blurScope: 'global',
        },
        lineStyle: { color: '#2a2e39', curveness: 0.08, opacity: 0.6 },
        edgeSymbol: ['none', 'arrow'],
        edgeSymbolSize: [0, 6],
        selectedMode: 'single',
        select: {
          itemStyle: { borderWidth: 3 },
        },
      }],
    }
  }, [data])

  // Click handler
  const onEvents = {
    click: (params: any) => {
      if (params.dataType !== 'node') { setSelected(null); return }
      const n = data?.nodes.find(nd => nd.id === params.data.id) ?? null
      setSelected(prev => prev?.id === n?.id ? null : n)
    },
  }

  // Resize chart when side panel opens/closes
  useEffect(() => {
    const inst = chartRef.current?.getEchartsInstance?.()
    if (inst) setTimeout(() => inst.resize(), 300)
  }, [selected])

  // ── Loading / Error ─────────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#0d1117' }}>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16 }}>
          <div style={{
            width: 32, height: 32, border: '2px solid #2a2e39', borderTopColor: '#f0883e',
            borderRadius: '50%', animation: 'spin 0.8s linear infinite',
          }} />
          <span style={{ fontSize: 10, color: '#8b949e', fontFamily: 'monospace', letterSpacing: 1 }}>ЗАГРУЗКА КАРТЫ ЗНАНИЙ…</span>
        </div>
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    )
  }

  if (isError || !data) {
    return (
      <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#0d1117' }}>
        <span style={{ fontSize: 10, color: '#f23645', fontFamily: 'monospace' }}>
          Ошибка загрузки — /api/knowledge/graph недоступен
        </span>
      </div>
    )
  }

  const { nodes, edges } = data

  // Type counts for legend
  const typeCounts: Record<string, number> = {}
  for (const n of nodes) typeCounts[n.type] = (typeCounts[n.type] ?? 0) + 1

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden', background: '#0d1117' }}>

      {/* ── Top bar ─────────────────────────────────────────────────────────── */}
      <div style={{
        flexShrink: 0, height: 36,
        display: 'flex', alignItems: 'center', gap: 0,
        background: 'rgba(22,27,34,0.95)', borderBottom: '1px solid #2a2e39',
        padding: '0 14px',
      }}>
        {/* Title */}
        <span style={{ fontSize: 10, fontWeight: 700, color: '#e6edf3', fontFamily: 'monospace', letterSpacing: 1.2, marginRight: 16 }}>
          KNOWLEDGE MAP
        </span>

        {/* Stats */}
        <span style={{ fontSize: 10, color: '#8b949e', fontFamily: 'monospace', marginRight: 4 }}>
          {nodes.length} nodes
        </span>
        <span style={{ color: '#2a2e39', margin: '0 6px' }}>·</span>
        <span style={{ fontSize: 10, color: '#8b949e', fontFamily: 'monospace', marginRight: 4 }}>
          {edges.length} edges
        </span>
        <span style={{ color: '#2a2e39', margin: '0 6px' }}>·</span>
        <span style={{ fontSize: 10, color: '#8b949e', fontFamily: 'monospace', marginRight: 16 }}>
          {Object.keys(typeCounts).length} categories
        </span>

        <div style={{ width: 1, height: 16, background: '#2a2e39', marginRight: 16 }} />

        {/* Legend */}
        {Object.entries(TYPE_CFG).map(([type, cfg]) => {
          const count = typeCounts[type] ?? 0
          if (!count) return null
          return (
            <div key={type} style={{ display: 'flex', alignItems: 'center', gap: 5, marginRight: 14 }}>
              <span style={{
                width: 7, height: 7, flexShrink: 0,
                background: cfg.color,
                borderRadius: type === 'root' ? 1 : type === 'hypothesis' ? '50%' : 0,
                display: 'inline-block',
              }} />
              <span style={{ fontSize: 9, color: cfg.color, fontFamily: 'monospace', letterSpacing: 0.3 }}>
                {cfg.label}
              </span>
              <span style={{ fontSize: 9, color: '#8b949e', fontFamily: 'monospace' }}>
                {count}
              </span>
            </div>
          )
        })}

        <div style={{ flex: 1 }} />

        {/* Hint */}
        <span style={{ fontSize: 9, color: '#484f58', fontFamily: 'monospace' }}>
          scroll to zoom · drag to pan · click node for details
        </span>
      </div>

      {/* ── Graph area ──────────────────────────────────────────────────────── */}
      <div style={{ flex: 1, minHeight: 0, position: 'relative', overflow: 'hidden' }}>
        <ReactECharts
          ref={chartRef}
          option={option()}
          style={{ height: '100%', width: '100%' }}
          opts={{ renderer: 'canvas', devicePixelRatio: window.devicePixelRatio }}
          onEvents={onEvents}
          notMerge
        />

        {/* Side details panel */}
        {selected && (
          <SidePanel node={selected} onClose={() => setSelected(null)} />
        )}
      </div>
    </div>
  )
}
