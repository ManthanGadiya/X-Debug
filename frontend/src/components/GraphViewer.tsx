import { Box, Group, Text } from '@mantine/core'
import { useMemo, useRef, useState } from 'react'
import type { GraphData, GraphNode } from '../api/client'
import { truncate } from '../utils/format'

interface Point {
  x: number
  y: number
}

const WIDTH = 900
const HEIGHT = 560
const PADDING = 40
const NODE_RADIUS = 18

const KIND_COLORS: Record<string, string> = {
  module: '#4c6ef5',
  package: '#6741d9',
  file: '#0ca678',
  function: '#f76707',
  method: '#e03131',
  class: '#d6336c',
  variable: '#f59f00',
  constant: '#12b886',
  call: '#74b816',
  import: '#15aabf',
  branch: '#7950f2',
  loop: '#7048e8',
  exception: '#fa5252',
  entrypoint: '#2f9e44',
  default: '#868e96',
}

function kindColor(kind: string): string {
  return KIND_COLORS[kind] ?? KIND_COLORS['default']
}

/**
 * Deterministic radial layout: nodes are grouped by kind and placed on rings
 * growing outward, so identical graphs always render identically.
 */
function computeLayout(nodes: GraphNode[]): Map<string, Point> {
  const groups = new Map<string, GraphNode[]>()
  for (const node of nodes) {
    const list = groups.get(node.kind) ?? []
    list.push(node)
    groups.set(node.kind, list)
  }

  const positions = new Map<string, Point>()
  const kinds = [...groups.keys()].sort()
  const kindCount = Math.max(kinds.length, 1)
  const baseRadius = Math.min(WIDTH, HEIGHT) / 2 - PADDING * 2

  kinds.forEach((kind, kindIndex) => {
    const group = groups.get(kind) ?? []
    const radius = baseRadius * (0.25 + 0.75 * (kindIndex / kindCount))
    group.forEach((node, index) => {
      const angle = (2 * Math.PI * index) / Math.max(group.length, 1) - Math.PI / 2
      positions.set(node.id, {
        x: WIDTH / 2 + radius * Math.cos(angle),
        y: HEIGHT / 2 + radius * Math.sin(angle),
      })
    })
  })

  return positions
}

interface GraphViewerProps {
  graph: GraphData
}

export function GraphViewer({ graph }: GraphViewerProps) {
  const positions = useMemo(() => computeLayout(graph.nodes), [graph.nodes])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const svgRef = useRef<SVGSVGElement>(null)

  const selected = graph.nodes.find((node) => node.id === selectedId) ?? null

  return (
    <Box>
      <Group justify="space-between" mb="xs">
        <Text size="sm" c="dimmed">
          {graph.name} — {graph.node_count} nodes, {graph.edge_count} edges
        </Text>
        {selected ? (
          <Text size="sm" fw={600}>
            {selected.label || selected.id}
          </Text>
        ) : (
          <Text size="sm" c="dimmed">
            Hover a node for details
          </Text>
        )}
      </Group>
      <Box style={{ overflow: 'auto', maxWidth: '100%' }}>
        <svg
          ref={svgRef}
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          width="100%"
          height="auto"
          role="img"
          aria-label={`${graph.name} graph`}
          data-testid="graph-viewer"
        >
          {graph.edges.map((edge, index) => {
            const source = positions.get(edge.source)
            const target = positions.get(edge.target)
            if (!source || !target) return null
            return (
              <line
                key={`${edge.source}-${edge.target}-${index}`}
                x1={source.x}
                y1={source.y}
                x2={target.x}
                y2={target.y}
                stroke="#adb5bd"
                strokeWidth={1}
                strokeOpacity={0.7}
              />
            )
          })}
          {graph.nodes.map((node) => {
            const point = positions.get(node.id)
            if (!point) return null
            const isSelected = node.id === selectedId
            return (
              <g
                key={node.id}
                onMouseEnter={() => setSelectedId(node.id)}
                onMouseLeave={() => setSelectedId(null)}
                style={{ cursor: 'default' }}
              >
                <circle
                  cx={point.x}
                  cy={point.y}
                  r={NODE_RADIUS}
                  fill={kindColor(node.kind)}
                  fillOpacity={isSelected ? 1 : 0.85}
                  stroke="#ffffff"
                  strokeWidth={isSelected ? 3 : 1.5}
                />
                <text
                  x={point.x}
                  y={point.y + 4}
                  textAnchor="middle"
                  fontSize={11}
                  fill="#ffffff"
                  fontWeight={600}
                >
                  {node.label ? truncate(node.label, 6) : '?'}
                </text>
              </g>
            )
          })}
        </svg>
      </Box>
      <Group mt="xs" gap="xs">
        {Object.entries(
          graph.nodes.reduce<Record<string, number>>((acc, node) => {
            acc[node.kind] = (acc[node.kind] ?? 0) + 1
            return acc
          }, {}),
        ).map(([kind, count]) => (
          <Group key={kind} gap={6}>
            <span
              style={{
                display: 'inline-block',
                width: 10,
                height: 10,
                borderRadius: '50%',
                background: kindColor(kind),
              }}
            />
            <Text size="xs" c="dimmed">
              {kind} ({count})
            </Text>
          </Group>
        ))}
      </Group>
    </Box>
  )
}
