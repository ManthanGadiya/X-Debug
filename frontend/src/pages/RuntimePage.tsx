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

export function RuntimePage() {
  const [searchParams] = useSearchParams()
  const projectFilter = searchParams.get('project')
  const runtime = usePolling(() => api.listRuntime(), { interval: 8000 })
  const projects = usePolling(() => api.listProjects(), { interval: 15000 })

  const [starting, setStarting] = useState(false)
  const [startError, setStartError] = useState<string | null>(null)

  const rows = (runtime.data ?? []).filter(
    (run) => !projectFilter || run.project_id === projectFilter,
  )

  const projectName = projects.data?.find((project) => project.id === projectFilter)?.name

  const handleStart = async () => {
    if (!projectFilter) return
    setStarting(true)
    setStartError(null)
    try {
      await api.startRuntime(projectFilter)
      await runtime.refresh()
    } catch (cause) {
      setStartError(cause instanceof Error ? cause.message : 'Unknown error')
    } finally {
      setStarting(false)
    }
  }

  const columns: HistoryColumn<(typeof rows)[number]>[] = [
    {
      key: 'id',
      header: 'Run',
      render: (run) => (
        <DetailLink to={`/runtime/${run.id}`}>
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
        title="Runtime"
        description={
          projectFilter
            ? `Execution runs for ${projectName ?? 'the selected project'}. Each run captures a trace of function calls, variable snapshots, and any exception.`
            : 'Every execution run in the workspace. Open a run to replay its trace.'
        }
        actions={
          projectFilter ? (
            <Button onClick={() => void handleStart()} loading={starting} size="xs">
              Run code
            </Button>
          ) : undefined
        }
      />

      {startError ? (
        <Alert color="red" title="Failed to start run">
          {startError}
        </Alert>
      ) : null}

      <SectionCard
        title="Runtime runs"
        subtitle={projectFilter ? `Filtered to ${projectName ?? 'selected project'}` : 'All runs'}
        delay={60}
      >
        {runtime.error ? (
          <Alert color="red" title="Failed to load runtime runs">
            {runtime.error}
          </Alert>
        ) : (
          <HistoryTable
            rows={rows}
            columns={columns}
            getRowId={(run) => run.id}
            loading={runtime.loading}
            error={null}
            emptyLabel={
              projectFilter
                ? 'No runtime runs for this project yet.'
                : 'No runtime runs yet — open a project and run its code there.'
            }
          />
        )}
      </SectionCard>
    </Stack>
  )
}
