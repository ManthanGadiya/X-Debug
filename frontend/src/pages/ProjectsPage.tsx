import { Alert, Button, Group, Stack, Text } from '@mantine/core'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { DetailLink, HistoryTable, type HistoryColumn } from '../components/HistoryTable'
import { PageHeader } from '../components/PageHeader'
import { SectionCard } from '../components/SectionCard'
import { UploadPanel } from '../components/UploadPanel'
import { usePolling } from '../hooks/usePolling'
import { formatBytes, formatDate } from '../utils/format'

export function ProjectsPage() {
  const projects = usePolling(() => api.listProjects(), { interval: 10000 })

  const columns: HistoryColumn<NonNullable<typeof projects.data>[number]>[] = [
    {
      key: 'name',
      header: 'Project',
      render: (project) => (
        <DetailLink to={`/projects/${project.id}`}>
          <Text fw={600} c="brand">
            {project.name}
          </Text>
        </DetailLink>
      ),
    },
    {
      key: 'source',
      header: 'Source',
      render: (project) => <Text c="dimmed">{project.source}</Text>,
    },
    {
      key: 'files',
      header: 'Files',
      render: (project) => (
        <Text c="dimmed">
          {project.source_file_count} src · {project.file_count} total
        </Text>
      ),
    },
    {
      key: 'size',
      header: 'Size',
      render: (project) => <Text c="dimmed">{formatBytes(project.total_size_bytes)}</Text>,
    },
    {
      key: 'languages',
      header: 'Languages',
      render: (project) => (
        <Group gap={6}>
          {project.languages.map((language) => (
            <Text key={language} size="xs" c="dimmed" style={{ fontFamily: 'var(--xmono)' }}>
              {language}
            </Text>
          ))}
        </Group>
      ),
    },
    {
      key: 'created',
      header: 'Created',
      render: (project) => <Text c="dimmed">{formatDate(project.created_at)}</Text>,
    },
    {
      key: 'actions',
      header: '',
      render: (project) => (
        <Link to={`/projects/${project.id}`} style={{ textDecoration: 'none' }}>
          <Button size="xs" variant="light" color="brand">
            Open
          </Button>
        </Link>
      ),
    },
  ]

  return (
    <Stack gap="lg">
      <PageHeader
        title="Projects"
        description="Every repository indexed by the workspace. Open a project to run analysis, runtime, tests, and report generation."
      />

      <SectionCard
        title="New repository"
        subtitle="Upload a zip archive or clone from GitHub"
        delay={60}
      >
        <UploadPanel />
      </SectionCard>

      <SectionCard title="All projects" subtitle="Indexed repositories" delay={120}>
        {projects.error ? (
          <Alert color="red" title="Failed to load projects">
            {projects.error}
          </Alert>
        ) : (
          <HistoryTable
            rows={projects.data ?? []}
            columns={columns}
            getRowId={(project) => project.id}
            loading={projects.loading}
            error={null}
            emptyLabel="No projects yet — upload a repository above."
          />
        )}
      </SectionCard>
    </Stack>
  )
}
