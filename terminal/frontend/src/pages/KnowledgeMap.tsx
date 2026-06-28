import { useRef, useEffect } from 'react'
import { Loader, Center } from '@mantine/core'
import { useQuery } from '@tanstack/react-query'
import ReactECharts from 'echarts-for-react'
import { fetchKnowledgeGraph } from '../api/client'

const NODE_SHAPE: Record<string, string> = {
  root: 'diamond',
  category: 'roundRect',
  hypothesis: 'circle',
  instrument: 'rect',
  regime: 'triangle',
  evidence: 'pin',
}

export default function KnowledgeMap() {
  const { data, isLoading } = useQuery({ queryKey: ['knowledge-graph'], queryFn: fetchKnowledgeGraph })

  if (isLoading) return <Center h="100%"><Loader /></Center>
  if (!data) return null

  const { nodes, edges } = data

  // Type legend
  const typeCounts: Record<string, number> = {}
  for (const n of nodes) typeCounts[n.type] = (typeCounts[n.type] ?? 0) + 1

  const echartsNodes = nodes.map(n => ({
    id: n.id,
    name: n.label,
    symbolSize: n.size,
    symbol: NODE_SHAPE[n.type] ?? 'circle',
    itemStyle: { color: n.color, borderColor: n.color + '66', borderWidth: 1 },
    label: {
      show: n.size >= 18,
      color: '#e6edf3',
      fontSize: n.size >= 25 ? 11 : 9,
      fontFamily: 'monospace',
    },
    tooltip: { formatter: `${n.label}<br/>${n.description ?? ''}` },
  }))

  const echartsEdges = edges.map(e => ({
    source: e.source,
    target: e.target,
    lineStyle: { color: '#30363d', width: e.weight ?? 1, curveness: 0.1 },
    label: { show: false },
  }))

  const option = {
    backgroundColor: '#131722',
    tooltip: {
      trigger: 'item',
      backgroundColor: '#1e222d',
      borderColor: '#2a2e39',
      textStyle: { color: '#d1d4dc', fontSize: 11, fontFamily: 'monospace' },
      formatter: (params: any) => {
        const n = nodes.find(nd => nd.id === params.data.id)
        if (!n) return params.data.name
        return `<b>${n.label}</b><br/><span style="color:#8b949e">${n.type} · ${n.description ?? ''}</span>`
      },
    },
    series: [{
      type: 'graph',
      layout: 'force',
      data: echartsNodes,
      links: echartsEdges,
      roam: true,
      draggable: true,
      force: {
        repulsion: 200,
        gravity: 0.05,
        edgeLength: [80, 200],
        friction: 0.4,
      },
      emphasis: {
        focus: 'adjacency',
        lineStyle: { width: 2 },
      },
      lineStyle: { color: '#30363d', curveness: 0.1 },
      edgeSymbol: ['none', 'arrow'],
      edgeSymbolSize: [0, 8],
    }],
  }

  const NODE_COLORS: Record<string, string> = {
    root: '#2962ff', category: '#00b0ff', hypothesis: '#089981',
    instrument: '#ffb800', regime: '#9c27b0', evidence: '#f23645',
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden', background: 'var(--t-bg)' }}>
      {/* Toolbar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, height: 38, padding: '0 12px', background: 'var(--t-panel)', borderBottom: '1px solid var(--t-border)', flexShrink: 0 }}>
        <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--t-text-2)', textTransform: 'uppercase', letterSpacing: 1 }}>KNOWLEDGE MAP</span>
        <div style={{ width: 1, height: 16, background: 'var(--t-border)' }} />
        <span style={{ fontSize: 11, fontFamily: 'var(--t-font-mono)', color: 'var(--t-text)' }}>{nodes.length} nodes · {edges.length} edges</span>
        <div style={{ width: 1, height: 16, background: 'var(--t-border)' }} />
        {Object.entries(typeCounts).map(([type, count]) => (
          <span key={type} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 10, color: 'var(--t-text-2)' }}>
            <span style={{ width: 7, height: 7, borderRadius: '50%', background: NODE_COLORS[type] ?? '#9598a1', display: 'inline-block' }} />
            {type} {count}
          </span>
        ))}
      </div>

      <div style={{ flex: 1 }}>
        <ReactECharts
          option={option}
          style={{ height: '100%', width: '100%' }}
          opts={{ renderer: 'canvas' }}
        />
      </div>
    </div>
  )
}
