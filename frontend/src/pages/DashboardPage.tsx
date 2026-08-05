import { Alert, Grid, Group, Stack, Text } from '@mantine/core'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { DetailLink, HistoryTable } from '../components/HistoryTable'
import { PageHeader } from '../components/PageHeader'
import { projectColumns } from '../components/projectColumns'
import { SectionCard } from '../components/SectionCard'
import { StatCard } from '../components/StatCard'
import { StatusBadge } from '../components/StatusBadge'
import { UploadPanel } from '../components/UploadPanel'
import { usePolling } from '../hooks/usePolling'
import { formatDate } from '../utils/format'

export function DashboardPage() {
  const projects = usePolling(() => api.listProjects(), { interval: 15000 })
  const analysis = usePolling(() => api.listAnalysis(), { interval: 8000 })
  const runtime = usePolling(() => api.listRuntime(), { interval: 8000 })
  const tests = usePolling(() => api.listTests(), { interval: 8000 })
  const health = usePolling(() => api.health(), { interval: 30000 })

  const healthError = health.error

  const projectCount = projects.data?.length ?? 0
  const runningCount = [
    ...(analysis.data ?? []),
    ...(runtime.data ?? []),
    ...(tests.data ?? []),
  ].filter((run) => run.status === 'running' || run.status === 'queued').length

  const columns = projectColumns()

  return (
    <Stack gap="lg">
      <PageHeader
        title="Dashboard"
        description="Upload a repository and inspect the explainable debugging pipeline: parsing, static graphs, runtime traces, and generated reports."
      />

      <Grid gap="md">
        <Grid.Col span={{ base: 12, md: 6, lg: 3 }}>
          <StatCard
            label="Backend"
            value={healthError ? 'OFFLINE' : 'ONLINE'}
            tone={healthError ? 'danger' : 'signal'}
          />
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 6, lg: 3 }}>
          <StatCard label="Projects" value={String(projectCount)} />
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 6, lg: 3 }}>
          <StatCard
            label="Active jobs"
            value={String(runningCount)}
            tone={runningCount > 0 ? 'brand' : 'default'}
          />
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 6, lg: 3 }}>
          <StatCard label="Analysis" value={String(analysis.data?.length ?? 0)} />
        </Grid.Col>
      </Grid>

      <UploadPanel />

      {healthError ? (
        <Alert color="red" title="Backend unreachable">
          {healthError} — start the XDebug API and refresh.
        </Alert>
      ) : null}

      <Grid gap="md">
        <Grid.Col span={{ base: 12, lg: 8 }}>
          <SectionCard
            title="Projects"
            subtitle="Recent repositories in the workspace"
            actions={
              <Link to="/projects" style={{ textDecoration: 'none' }}>
                <Text size="sm" c="brand">
                  View all →
                </Text>
              </Link>
            }
            delay={80}
          >
            <HistoryTable
              rows={projects.data ?? []}
              columns={columns}
              getRowId={(project) => project.id}
              loading={projects.loading}
              error={projects.error}
              errorTitle="Failed to load projects"
              emptyLabel="No projects yet — upload a repository above."
            />
          </SectionCard>
        </Grid.Col>

        <Grid.Col span={{ base: 12, lg: 4 }}>
          <Stack gap="md">
            <RecentRuns
              title="Analysis"
              to="/analysis"
              delay={140}
              rows={(analysis.data ?? []).slice(0, 5).map((run) => ({
                id: run.id,
                status: run.status,
                createdAt: run.created_at,
              }))}
              error={analysis.error}
            />
            <RecentRuns
              title="Runtime"
              to="/runtime"
              delay={200}
              rows={(runtime.data ?? []).slice(0, 5).map((run) => ({
                id: run.id,
                status: run.status,
                createdAt: run.created_at,
              }))}
              error={runtime.error}
            />
            <RecentRuns
              title="Tests"
              to="/tests"
              delay={260}
              rows={(tests.data ?? []).slice(0, 5).map((run) => ({
                id: run.id,
                status: run.status,
                createdAt: run.created_at,
              }))}
              error={tests.error}
            />
          </Stack>
        </Grid.Col>
      </Grid>
    </Stack>
  )
}

interface RecentRunRow {
  id: string
  status: string
  createdAt: string
}

function RecentRuns({
  title,
  to,
  rows,
  error,
  delay,
}: {
  title: string
  to: string
  rows: RecentRunRow[]
  error: string | null
  delay: number
}) {
  return (
    <SectionCard
      title={title}
      actions={
        <Link to={to} style={{ textDecoration: 'none' }}>
          <Text size="sm" c="brand">
            View all →
          </Text>
        </Link>
      }
      delay={delay}
    >
      {error ? (
        <Alert color="red" title="Failed to load">
          {error}
        </Alert>
      ) : rows.length === 0 ? (
        <Text size="sm" c="dimmed">
          No runs yet
        </Text>
      ) : (
        <Stack gap={8}>
          {rows.map((row) => (
            <Group key={row.id} justify="space-between" gap="md">
              <DetailLink to={`${to}/${row.id}`}>
                <Text size="xs" c="brand" style={{ fontFamily: 'var(--xmono)' }}>
                  {row.id.slice(0, 12)}
                </Text>
              </DetailLink>
              <Group gap="md">
                <Text size="xs" c="dimmed" style={{ fontFamily: 'var(--xmono)' }}>
                  {formatDate(row.createdAt)}
                </Text>
                <StatusBadge status={row.status} />
              </Group>
            </Group>
          ))}
        </Stack>
      )}
    </SectionCard>
  )
}
