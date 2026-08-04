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

export function TestsPage() {
  const [searchParams] = useSearchParams()
  const projectFilter = searchParams.get('project')
  const tests = usePolling(() => api.listTests(), { interval: 8000 })
  const projects = usePolling(() => api.listProjects(), { interval: 15000 })

  const [starting, setStarting] = useState(false)
  const [startError, setStartError] = useState<string | null>(null)

  const rows = (tests.data ?? []).filter(
    (run) => !projectFilter || run.project_id === projectFilter,
  )

  const projectName = projects.data?.find((project) => project.id === projectFilter)?.name

  const handleStart = async () => {
    if (!projectFilter) return
    setStarting(true)
    setStartError(null)
    try {
      await api.startTests(projectFilter)
      await tests.refresh()
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
        <DetailLink to={`/tests/${run.id}`}>
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
        title="Tests"
        description={
          projectFilter
            ? `Test runs for ${projectName ?? 'the selected project'}. Each run executes the project's test suites in isolation.`
            : 'Every test run in the workspace. Open a run to see per-suite pass/fail details.'
        }
        actions={
          projectFilter ? (
            <Button onClick={() => void handleStart()} loading={starting} size="xs">
              Run tests
            </Button>
          ) : undefined
        }
      />

      {startError ? (
        <Alert color="red" title="Failed to start test run">
          {startError}
        </Alert>
      ) : null}

      <SectionCard
        title="Test runs"
        subtitle={projectFilter ? `Filtered to ${projectName ?? 'selected project'}` : 'All runs'}
        delay={60}
      >
        {tests.error ? (
          <Alert color="red" title="Failed to load test runs">
            {tests.error}
          </Alert>
        ) : (
          <HistoryTable
            rows={rows}
            columns={columns}
            getRowId={(run) => run.id}
            loading={tests.loading}
            error={null}
            emptyLabel={
              projectFilter
                ? 'No test runs for this project yet.'
                : 'No test runs yet — open a project and run its tests there.'
            }
          />
        )}
      </SectionCard>
    </Stack>
  )
}
