import { Alert, Button, Stack, Text } from '@mantine/core'
import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import { DetailLink, HistoryTable, type HistoryColumn } from './HistoryTable'
import { PageHeader } from './PageHeader'
import { SectionCard } from './SectionCard'
import { StatusBadge } from './StatusBadge'
import { usePolling } from '../hooks/usePolling'
import { formatDate } from '../utils/format'

export type RunKind = 'analysis' | 'runtime' | 'tests'

export interface RunListPageProps {
  kind: RunKind
  title: string
  descriptionAll: string
  /** Description shown when a project filter is active; `{project}` is replaced with the project name. */
  descriptionFiltered: string
  startLabel: string
  startErrorTitle: string
  sectionTitle: string
  emptyAll: string
  emptyFiltered: string
  errorTitle: string
}

const LISTERS: Record<RunKind, () => ReturnType<typeof api.listAnalysis>> = {
  analysis: () => api.listAnalysis(),
  runtime: () => api.listRuntime(),
  tests: () => api.listTests(),
}

const STARTERS: Record<RunKind, (projectId: string) => Promise<unknown>> = {
  analysis: (projectId) => api.startAnalysis(projectId),
  runtime: (projectId) => api.startRuntime(projectId),
  tests: (projectId) => api.startTests(projectId),
}

const DETAIL_PATHS: Record<RunKind, (id: string) => string> = {
  analysis: (id) => `/analysis/${id}`,
  runtime: (id) => `/runtime/${id}`,
  tests: (id) => `/tests/${id}`,
}

const ID_HEADERS: Record<RunKind, string> = {
  analysis: 'Analysis',
  runtime: 'Run',
  tests: 'Run',
}

/** A configured history list page shared by analysis, runtime, and tests. */
export function RunListPage({
  kind,
  title,
  descriptionAll,
  descriptionFiltered,
  startLabel,
  startErrorTitle,
  sectionTitle,
  emptyAll,
  emptyFiltered,
  errorTitle,
}: RunListPageProps) {
  const [searchParams] = useSearchParams()
  const projectFilter = searchParams.get('project')
  const runs = usePolling(LISTERS[kind], { interval: 8000 })
  const projects = usePolling(() => api.listProjects(), { interval: 15000 })

  const [starting, setStarting] = useState(false)
  const [startError, setStartError] = useState<string | null>(null)

  const rows = (runs.data ?? []).filter(
    (run) => !projectFilter || run.project_id === projectFilter,
  )

  const projectName = projects.data?.find((project) => project.id === projectFilter)?.name

  const handleStart = async () => {
    if (!projectFilter) return
    setStarting(true)
    setStartError(null)
    try {
      await STARTERS[kind](projectFilter)
      await runs.refresh()
    } catch (cause) {
      setStartError(cause instanceof Error ? cause.message : 'Unknown error')
    } finally {
      setStarting(false)
    }
  }

  const columns: HistoryColumn<(typeof rows)[number]>[] = [
    {
      key: 'id',
      header: ID_HEADERS[kind],
      render: (run) => (
        <DetailLink to={DETAIL_PATHS[kind](run.id)}>
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
        title={title}
        description={
          projectFilter
            ? descriptionFiltered.replace('{project}', projectName ?? 'the selected project')
            : descriptionAll
        }
        actions={
          projectFilter ? (
            <Button onClick={() => void handleStart()} loading={starting} size="xs">
              {startLabel}
            </Button>
          ) : undefined
        }
      />

      {startError ? (
        <Alert color="red" title={startErrorTitle}>
          {startError}
        </Alert>
      ) : null}

      <SectionCard
        title={sectionTitle}
        subtitle={projectFilter ? `Filtered to ${projectName ?? 'selected project'}` : 'All runs'}
        delay={60}
      >
        <HistoryTable
          rows={rows}
          columns={columns}
          getRowId={(run) => run.id}
          loading={runs.loading}
          error={runs.error}
          errorTitle={errorTitle}
          emptyLabel={projectFilter ? emptyFiltered : emptyAll}
        />
      </SectionCard>
    </Stack>
  )
}
