import { Alert, Group, SegmentedControl, Stack, Table, Text } from '@mantine/core'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, type Language } from '../api/client'
import { CodeViewer } from '../components/CodeViewer'
import { PageHeader } from '../components/PageHeader'
import { SectionCard } from '../components/SectionCard'
import { StatCard } from '../components/StatCard'
import { StatusBadge } from '../components/StatusBadge'
import { usePolling } from '../hooks/usePolling'
import { formatDate, formatDuration } from '../utils/format'

export function TestDetailPage() {
  const { runId = '' } = useParams()
  const detail = usePolling(() => api.getTestRun(runId), { interval: 8000 })

  const run = detail.data
  const languages = run?.languages ?? []
  const [language, setLanguage] = useState<Language | null>(null)
  const activeLanguage = (language ?? languages[0] ?? null) as Language | null

  const results = usePolling(
    () => (activeLanguage ? api.getTestResults(runId, activeLanguage) : Promise.resolve(null)),
    { interval: 8000, done: (data) => data !== null, deps: [runId, activeLanguage] },
  )

  const suite = results.data
  const failures = suite?.cases.filter((test) => test.outcome !== 'passed' && test.message) ?? []

  return (
    <Stack gap="lg">
      <PageHeader
        title={run ? `Test run ${run.id.slice(0, 8)}` : 'Test run'}
        description={
          run ? (
            <Group gap="sm">
              <StatusBadge status={run.status} />
              <Text size="sm" c="dimmed">
                {formatDate(run.created_at)}
              </Text>
            </Group>
          ) : (
            'Loading test run…'
          )
        }
        actions={
          run ? (
            <Link to={`/projects/${run.project_id}`} style={{ textDecoration: 'none' }}>
              <Text size="sm" c="brand">
                Project →
              </Text>
            </Link>
          ) : undefined
        }
      />

      {detail.error ? (
        <Alert color="red" title="Failed to load test run">
          {detail.error}
        </Alert>
      ) : null}

      {run ? (
        <>
          <Group gap="md" wrap="wrap">
            <StatCard
              label="Result"
              value={run.succeeded ? 'PASSED' : 'FAILED'}
              tone={run.succeeded ? 'signal' : 'danger'}
            />
            <StatCard label="Tests run" value={String(run.tests_run)} />
            <StatCard label="Passed" value={String(run.passed)} tone="signal" />
            <StatCard
              label="Failed"
              value={String(run.failed)}
              tone={run.failed > 0 ? 'danger' : 'default'}
            />
            <StatCard label="Skipped" value={String(run.skipped)} />
            <StatCard label="Languages" value={run.languages.join(', ') || '—'} />
          </Group>

          {run.error ? (
            <Alert color="red" title="Test run error">
              {run.error}
            </Alert>
          ) : null}

          {languages.length > 1 ? (
            <SegmentedControl
              size="xs"
              value={activeLanguage ?? undefined}
              onChange={(value) => setLanguage(value as Language)}
              data={languages}
            />
          ) : null}

          {suite ? (
            <SectionCard
              title={`${suite.language} suite`}
              subtitle={`${suite.tests_run} tests · ${suite.duration_seconds.toFixed(2)}s · ${suite.passed} passed · ${suite.failed} failed · ${suite.skipped} skipped`}
              delay={60}
            >
              {suite.error ? (
                <Alert color="red" title="Suite error">
                  {suite.error}
                </Alert>
              ) : null}

              {suite.cases.length === 0 ? (
                <Text size="sm" c="dimmed">
                  No test cases recorded for this suite.
                </Text>
              ) : (
                <Table.ScrollContainer minWidth={480}>
                  <Table striped highlightOnHover verticalSpacing="xs">
                    <Table.Thead>
                      <Table.Tr>
                        <Table.Th>Test</Table.Th>
                        <Table.Th>Outcome</Table.Th>
                        <Table.Th>Duration</Table.Th>
                      </Table.Tr>
                    </Table.Thead>
                    <Table.Tbody>
                      {suite.cases.map((test) => (
                        <Table.Tr key={test.name}>
                          <Table.Td>
                            <Text size="sm" style={{ fontFamily: 'var(--xmono)' }}>
                              {test.name}
                            </Text>
                          </Table.Td>
                          <Table.Td>
                            <Text
                              size="sm"
                              fw={600}
                              tt="uppercase"
                              c={test.outcome === 'passed' ? 'signal' : 'danger'}
                              style={{ fontFamily: 'var(--xmono)' }}
                            >
                              {test.outcome}
                            </Text>
                          </Table.Td>
                          <Table.Td>
                            <Text size="sm" c="dimmed">
                              {formatDuration(test.duration_seconds)}
                            </Text>
                          </Table.Td>
                        </Table.Tr>
                      ))}
                    </Table.Tbody>
                  </Table>
                </Table.ScrollContainer>
              )}

              {failures.length > 0 ? (
                <CodeViewer
                  title="Failures"
                  code={failures.map((test) => `--- ${test.name}\n${test.message}`).join('\n\n')}
                  maxHeight={260}
                />
              ) : null}
            </SectionCard>
          ) : results.error ? (
            <Alert color="red" title="Failed to load suite results">
              {results.error}
            </Alert>
          ) : null}
        </>
      ) : null}
    </Stack>
  )
}
