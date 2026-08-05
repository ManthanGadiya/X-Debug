import { Text } from '@mantine/core'
import { DetailLink, HistoryTable, type HistoryColumn } from './HistoryTable'
import { SectionCard } from './SectionCard'
import { StatusBadge } from './StatusBadge'
import { formatDate } from '../utils/format'

/** A run row as accepted by `RunHistoryCard` (any of the summary types share this shape). */
export interface RunHistoryRow {
  id: string
  status: string
  created_at: string
}

interface RunHistoryCardProps {
  title: string
  subtitle: string
  delay: number
  /** Route prefix for the detail links, e.g. `/analysis`. */
  prefix: string
  runs: RunHistoryRow[]
  loading: boolean
  error: string | null
  errorTitle: string
  emptyLabel: string
}

const runColumns = (prefix: string): HistoryColumn<RunHistoryRow>[] => [
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
    render: (run) => <Text c="dimmed">{formatDate(run.created_at)}</Text>,
  },
]

/** A titled history table for one run kind (analysis, runtime, or tests). */
export function RunHistoryCard({
  title,
  subtitle,
  delay,
  prefix,
  runs,
  loading,
  error,
  errorTitle,
  emptyLabel,
}: RunHistoryCardProps) {
  return (
    <SectionCard title={title} subtitle={subtitle} delay={delay}>
      <HistoryTable
        rows={runs}
        columns={runColumns(prefix)}
        getRowId={(run) => run.id}
        loading={loading}
        error={error}
        errorTitle={errorTitle}
        emptyLabel={emptyLabel}
      />
    </SectionCard>
  )
}