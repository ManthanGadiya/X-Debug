import { Alert, Button, Group, Stack, Text } from '@mantine/core'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api/client'
import { DetailLink, HistoryTable, type HistoryColumn } from '../components/HistoryTable'
import { PageHeader } from '../components/PageHeader'
import { SectionCard } from '../components/SectionCard'
import { StatCard } from '../components/StatCard'
import { StatusBadge } from '../components/StatusBadge'
import { usePolling } from '../hooks/usePolling'
import { formatBytes, formatDate } from '../utils/format'

export function ProjectDetailPage() {
  const { projectId = '' } = useParams()
  const project = usePolling(() => api.getProject(projectId), { interval: 10000 })
  const analysis = usePolling(() => api.listAnalysis(), { interval: 8000 })
  const runtime = usePolling(() => api.listRuntime(), { interval: 8000 })
  const tests = usePolling(() => api.listTests(), { interval: 8000 })

  const detail = project.data
  const projectAnalysis = (analysis.data ?? []).filter((run) => run.project_id === projectId)
  const projectRuntime = (runtime.data ?? []).filter((run) => run.project_id === projectId)
  const projectTests = (tests.data ?? []).filter((run) => run.project_id === projectId)

  const fileColumns: HistoryColumn<NonNullable<typeof detail>['files'][number]>[] = [
    {
      key: 'path',
      header: 'Path',
      render: (file) => <Text fw={500}>{file.path}</Text>,
    },
    {
      key: 'language',
      header: 'Language',
      render: (file) => <Text c="dimmed">{file.language}</Text>,
    },
    {
      key: 'lines',
      header: 'Lines',
      render: (file) => <Text c="dimmed">{file.lines.toLocaleString()}</Text>,
    },
    {
      key: 'size',
      header: 'Size',
      render: (file) => <Text c="dimmed">{formatBytes(file.size_bytes)}</Text>,
    },
  ]

  const runColumns = (
    prefix: string,
  ): HistoryColumn<{
    id: string
    status: string
    createdAt: string
  }>[] => [
    {
      key: 'id',
      header: 'Run',
      render: (run) => (
        <DetailLink to={`${prefix}/${run.id}`}>
          <Text c="brand" style={{ fontFamily: 'var(--xmono)' }}>
            {run.id.slice(0, 12)}
          </Text>
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
      render: (run) => <Text c="dimmed">{formatDate(run.createdAt)}</Text>,
    },
  ]

  return (
    <Stack gap="lg">
      <PageHeader
        title={detail ? detail.name : 'Project'}
        description={
          detail
            ? `Ingested from ${detail.source} · ${detail.source_file_count} source files across ${detail.languages.join(', ') || '—'} languages`
            : 'Loading project…'
        }
        actions={
          <Group gap="sm">
            <Button
              component={Link}
              to={`/analysis?project=${projectId}`}
              variant="light"
              color="brand"
              size="xs"
            >
              Analyze
            </Button>
            <Button
              component={Link}
              to={`/runtime?project=${projectId}`}
              variant="light"
              color="brand"
              size="xs"
            >
              Run
            </Button>
            <Button
              component={Link}
              to={`/tests?project=${projectId}`}
              variant="light"
              color="brand"
              size="xs"
            >
              Test
            </Button>
            <Button
              component={Link}
              to={`/reports?project=${projectId}`}
              variant="light"
              color="signal"
              size="xs"
            >
              Report
            </Button>
          </Group>
        }
      />

      {project.error ? (
        <Alert color="red" title="Failed to load project">
          {project.error}
        </Alert>
      ) : null}

      {detail ? (
        <>
          <Group gap="md" wrap="wrap">
            <StatCard label="Source files" value={String(detail.source_file_count)} />
            <StatCard label="Total files" value={String(detail.file_count)} />
            <StatCard label="Total size" value={formatBytes(detail.total_size_bytes)} />
            <StatCard label="Created" value={formatDate(detail.created_at)} />
          </Group>

          <SectionCard
            title="Source files"
            subtitle="Every file indexed for this repository"
            delay={60}
          >
            {detail.files.length === 0 ? (
              <Text size="sm" c="dimmed">
                No source files detected.
              </Text>
            ) : (
              <HistoryTable
                rows={detail.files}
                columns={fileColumns}
                getRowId={(file) => file.path}
                loading={false}
                error={null}
                emptyLabel="No source files"
              />
            )}
          </SectionCard>

          <SectionCard
            title="Analysis runs"
            subtitle="Static pipeline history for this project"
            delay={120}
          >
            {analysis.error ? (
              <Alert color="red" title="Failed to load analysis runs">
                {analysis.error}
              </Alert>
            ) : (
              <HistoryTable
                rows={projectAnalysis.map((run) => ({
                  id: run.id,
                  status: run.status,
                  createdAt: run.created_at,
                }))}
                columns={runColumns('/analysis')}
                getRowId={(run) => run.id}
                loading={analysis.loading}
                error={null}
                emptyLabel="No analysis runs yet — start one from the Analysis page."
              />
            )}
          </SectionCard>

          <SectionCard
            title="Runtime runs"
            subtitle="Execution trace history for this project"
            delay={180}
          >
            {runtime.error ? (
              <Alert color="red" title="Failed to load runtime runs">
                {runtime.error}
              </Alert>
            ) : (
              <HistoryTable
                rows={projectRuntime.map((run) => ({
                  id: run.id,
                  status: run.status,
                  createdAt: run.created_at,
                }))}
                columns={runColumns('/runtime')}
                getRowId={(run) => run.id}
                loading={runtime.loading}
                error={null}
                emptyLabel="No runtime runs yet — start one from the Runtime page."
              />
            )}
          </SectionCard>

          <SectionCard title="Test runs" subtitle="Test history for this project" delay={240}>
            {tests.error ? (
              <Alert color="red" title="Failed to load test runs">
                {tests.error}
              </Alert>
            ) : (
              <HistoryTable
                rows={projectTests.map((run) => ({
                  id: run.id,
                  status: run.status,
                  createdAt: run.created_at,
                }))}
                columns={runColumns('/tests')}
                getRowId={(run) => run.id}
                loading={tests.loading}
                error={null}
                emptyLabel="No test runs yet — start one from the Tests page."
              />
            )}
          </SectionCard>
        </>
      ) : null}
    </Stack>
  )
}
