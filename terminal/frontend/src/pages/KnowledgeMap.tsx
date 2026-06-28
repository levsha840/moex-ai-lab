import { useRef, useEffect } from 'react'
import { Group, Text, Badge, Paper, Stack, Loader, Center, SimpleGrid } from '@mantine/core'
import { useQuery } from '@tanstack/react-query'
import { IconBrain } from '@tabler/icons-react'
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

  if (isLoading) return <Center h="100vh"><Loader color="blue" /></Center>
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
    backgroundColor: '#0d1117',
    tooltip: {
      trigger: 'item',
      backgroundColor: '#161b22',
      borderColor: '#30363d',
      textStyle: { color: '#e6edf3', fontSize: 11, fontFamily: 'monospace' },
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

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: '#0d1117' }}>
      <div style={{ padding: '10px 16px', borderBottom: '1px solid #21262d', display: 'flex', alignItems: 'center', gap: 12 }}>
        <IconBrain size={16} color="#58a6ff" />
        <Text size="sm" fw={700} c="#e6edf3" style={{ letterSpacing: 1 }}>KNOWLEDGE MAP</Text>
        <Badge color="blue" size="sm">{nodes.length} nodes · {edges.length} connections</Badge>
      </div>

      {/* Legend */}
      <div style={{ padding: '6px 16px', borderBottom: '1px solid #21262d', display: 'flex', gap: 16 }}>
        {Object.entries(typeCounts).map(([type, count]) => (
          <Group key={type} gap={6}>
            <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#58a6ff', opacity: 0.8 }} />
            <Text size="10px" c="#8b949e">{type} ({count})</Text>
          </Group>
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
