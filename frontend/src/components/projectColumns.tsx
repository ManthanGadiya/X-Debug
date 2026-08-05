import { Button, Group, Text } from '@mantine/core'
import { Link } from 'react-router-dom'
import type { ProjectSummary } from '../api/client'
import { DetailLink, type HistoryColumn } from './HistoryTable'
import { formatBytes, formatDate } from '../utils/format'

export interface ProjectColumnsOptions {
  /** Include the source column (Projects page only). */
  source?: boolean
  /** Include the trailing Open button column (Projects page only). */
  actions?: boolean
}

/** Columns for project history tables. The dashboard omits source and actions. */
export function projectColumns(options: ProjectColumnsOptions = {}): HistoryColumn<ProjectSummary>[] {
  const columns: HistoryColumn<ProjectSummary>[] = [
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
  ]

  if (options.source) {
    columns.push({
      key: 'source',
      header: 'Source',
      render: (project) => <Text c="dimmed">{project.source}</Text>,
    })
  }

  columns.push(
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
  )

  if (options.actions) {
    columns.push({
      key: 'actions',
      header: '',
      render: (project) => (
        <Link to={`/projects/${project.id}`} style={{ textDecoration: 'none' }}>
          <Button size="xs" variant="light" color="brand">
            Open
          </Button>
        </Link>
      ),
    })
  }

  return columns
}
