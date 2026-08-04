import { Alert, Group, SegmentedControl, Stack, Text } from '@mantine/core'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, type GraphKind } from '../api/client'
import { CodeViewer } from '../components/CodeViewer'
import { GraphViewer } from '../components/GraphViewer'
import { PageHeader } from '../components/PageHeader'
import { SectionCard } from '../components/SectionCard'
import { StatCard } from '../components/StatCard'
import { StatusBadge } from '../components/StatusBadge'
import { usePolling } from '../hooks/usePolling'
import { formatDate } from '../utils/format'

const GRAPH_KINDS: { value: GraphKind; label: string }[] = [
  { value: 'dependency', label: 'Dependency' },
  { value: 'call', label: 'Call graph' },
  { value: 'cfg', label: 'Control flow' },
  { value: 'dataflow', label: 'Dataflow' },
]

export function AnalysisDetailPage() {
  const { analysisId = '' } = useParams()
  const [kind, setKind] = useState<GraphKind>('dependency')
  const detail = usePolling(() => api.getAnalysis(analysisId), { interval: 8000 })
  const graph = usePolling(() => api.getGraph(analysisId, kind), {
    interval: 8000,
    done: (data) => data !== null,
  })

  const run = detail.data

  return (
    <Stack gap="lg">
      <PageHeader
        title={run ? `Analysis ${run.id.slice(0, 8)}` : 'Analysis'}
        description={
          run ? (
            <Group gap="sm">
              <StatusBadge status={run.status} />
              <Text size="sm" c="dimmed">
                {formatDate(run.created_at)}
              </Text>
            </Group>
          ) : (
            'Loading analysis run…'
          )
        }
        actions={
          run ? (
            <Link to={`/projects/${run.project_id}`} style={{ textDecoration: 'none' }}>
              <Text size="sm" c="brand">
                Project →
              </Text>
            </Link>
          ) : undefined
        }
      />

      {detail.error ? (
        <Alert color="red" title="Failed to load analysis">
          {detail.error}
        </Alert>
      ) : null}

      {run ? (
        <>
          <Group gap="md" wrap="wrap">
            <StatCard label="Files parsed" value={String(run.parsed_file_count)} tone="signal" />
            <StatCard
              label="Failed files"
              value={String(run.failed_file_count)}
              tone={run.failed_file_count > 0 ? 'danger' : 'default'}
            />
            <StatCard label="Dependency edges" value={String(run.dependency_edge_count)} />
            <StatCard label="Call edges" value={String(run.call_edge_count)} />
            <StatCard label="CFG nodes" value={String(run.cfg_node_count)} />
            <StatCard label="Dataflow edges" value={String(run.dataflow_edge_count)} />
          </Group>

          {run.error ? (
            <Alert color="red" title="Analysis error">
              {run.error}
            </Alert>
          ) : null}

          <SectionCard
            title="Graphs"
            subtitle="Deterministic graph views over the parsed codebase"
            actions={
              <SegmentedControl
                size="xs"
                value={kind}
                onChange={(value) => setKind(value as GraphKind)}
                data={GRAPH_KINDS}
              />
            }
            delay={60}
          >
            {graph.error ? (
              <Alert color="red" title={`Failed to load ${kind} graph`}>
                {graph.error}
              </Alert>
            ) : graph.data ? (
              <GraphViewer graph={graph.data} />
            ) : (
              <CodeViewer title="No graph available" code="// waiting for analysis results…" />
            )}
          </SectionCard>
        </>
      ) : null}
    </Stack>
  )
}
