import { Alert, Skeleton, Stack, Table, Text } from '@mantine/core'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

export interface HistoryColumn<T> {
  key: string
  header: string
  render: (row: T) => ReactNode
}

interface HistoryTableProps<T> {
  rows: T[]
  columns: HistoryColumn<T>[]
  getRowId: (row: T) => string
  loading?: boolean
  error?: string | null
  errorTitle?: string
  emptyLabel?: string
}

/** A generic read-only table for the history list pages. */
export function HistoryTable<T>({
  rows,
  columns,
  getRowId,
  loading = false,
  error = null,
  errorTitle = 'Failed to load',
  emptyLabel = 'No records yet',
}: HistoryTableProps<T>) {
  if (error) {
    return (
      <Alert color="red" title={errorTitle}>
        {error}
      </Alert>
    )
  }

  if (loading) {
    return (
      <Stack gap={8}>
        <Skeleton height={28} />
        <Skeleton height={28} />
        <Skeleton height={28} />
      </Stack>
    )
  }

  if (rows.length === 0) {
    return (
      <Text size="sm" c="dimmed">
        {emptyLabel}
      </Text>
    )
  }

  return (
    <Table.ScrollContainer minWidth={500}>
      <Table striped highlightOnHover verticalSpacing="sm">
        <Table.Thead>
          <Table.Tr>
            {columns.map((column) => (
              <Table.Th
                key={column.key}
                tt="uppercase"
                style={{ fontFamily: 'var(--xmono)', letterSpacing: '0.08em' }}
              >
                {column.header}
              </Table.Th>
            ))}
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {rows.map((row) => (
            <Table.Tr key={getRowId(row)}>
              {columns.map((column) => (
                <Table.Td key={column.key} style={{ fontFamily: 'var(--xmono)', fontSize: 13 }}>
                  {column.render(row)}
                </Table.Td>
              ))}
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </Table.ScrollContainer>
  )
}

/** A link to a detail page, kept terse so list pages stay readable. */
export function DetailLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Link to={to} style={{ textDecoration: 'none' }}>
      {children}
    </Link>
  )
}
