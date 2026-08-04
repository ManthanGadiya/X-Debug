import { Alert, Button, Stack, Text } from '@mantine/core'
import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import { DetailLink, HistoryTable, type HistoryColumn } from '../components/HistoryTable'
import { PageHeader } from '../components/PageHeader'
import { SectionCard } from '../components/SectionCard'
import { StatusBadge } from '../components/StatusBadge'
import { usePolling } from '../hooks/usePolling'
import { formatDate } from '../utils/format'

export function AnalysisPage() {
  const [searchParams] = useSearchParams()
  const projectFilter = searchParams.get('project')
  const analysis = usePolling(() => api.listAnalysis(), { interval: 8000 })
  const projects = usePolling(() => api.listProjects(), { interval: 15000 })

  const [starting, setStarting] = useState(false)
  const [startError, setStartError] = useState<string | null>(null)

  const rows = (analysis.data ?? []).filter(
    (run) => !projectFilter || run.project_id === projectFilter,
  )

  const projectName = projects.data?.find((project) => project.id === projectFilter)?.name

  const handleStart = async () => {
    if (!projectFilter) return
    setStarting(true)
    setStartError(null)
    try {
      await api.startAnalysis(projectFilter)
      await analysis.refresh()
    } catch (cause) {
      setStartError(cause instanceof Error ? cause.message : 'Unknown error')
    } finally {
      setStarting(false)
    }
  }

  const columns: HistoryColumn<(typeof rows)[number]>[] = [
    {
      key: 'id',
      header: 'Analysis',
      render: (run) => (
        <DetailLink to={`/analysis/${run.id}`}>
          <Text fw={600} c="brand" style={{ fontFamily: 'var(--xmono)' }}>
            {run.id.slice(0, 12)}
          </Text>
        </DetailLink>
      ),
    },
    {
      key: 'project',
      header: 'Project',
      render: (run) => (
        <DetailLink to={`/projects/${run.project_id}`}>
          <Text c="dimmed">{run.project_id.slice(0, 8)}</Text>
        </DetailLink>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (run) => <StatusBadge status={run.status} />,
    },
    {
      key: 'created',
      header: 'Created',
      render: (run) => <Text c="dimmed">{formatDate(run.created_at)}</Text>,
    },
  ]

  return (
    <Stack gap="lg">
      <PageHeader
        title="Analysis"
        description={
          projectFilter
            ? `Static pipeline runs for ${projectName ?? 'the selected project'}. Graphs are built per run: dependency, call, control flow, and dataflow.`
            : 'Every static analysis run in the workspace. Open a run to inspect its graphs.'
        }
        actions={
          projectFilter ? (
            <Button onClick={() => void handleStart()} loading={starting} size="xs">
              Start analysis
            </Button>
          ) : undefined
        }
      />

      {startError ? (
        <Alert color="red" title="Failed to start analysis">
          {startError}
        </Alert>
      ) : null}

      <SectionCard
        title="Analysis runs"
        subtitle={projectFilter ? `Filtered to ${projectName ?? 'selected project'}` : 'All runs'}
        delay={60}
      >
        {analysis.error ? (
          <Alert color="red" title="Failed to load analysis runs">
            {analysis.error}
          </Alert>
        ) : (
          <HistoryTable
            rows={rows}
            columns={columns}
            getRowId={(run) => run.id}
            loading={analysis.loading}
            error={null}
            emptyLabel={
              projectFilter
                ? 'No analysis runs for this project yet.'
                : 'No analysis runs yet — open a project and start analysis there.'
            }
          />
        )}
      </SectionCard>
    </Stack>
  )
}
