import { Alert, Button, Group, SegmentedControl, Stack, Text } from '@mantine/core'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, type Language, type ReplayStep } from '../api/client'
import { CodeViewer } from '../components/CodeViewer'
import { PageHeader } from '../components/PageHeader'
import { SectionCard } from '../components/SectionCard'
import { StatCard } from '../components/StatCard'
import { StatusBadge } from '../components/StatusBadge'
import { usePolling } from '../hooks/usePolling'
import { formatDate, formatDuration } from '../utils/format'

export function RuntimeDetailPage() {
  const { runId = '' } = useParams()
  const detail = usePolling(() => api.getRuntime(runId), { interval: 8000 })

  const run = detail.data
  const languages = (run?.languages ?? []) as Language[]
  const [language, setLanguage] = useState<Language | null>(languages[0] ?? null)

  const activeLanguage = (language ?? languages[0] ?? null) as Language | null

  const trace = usePolling(
    () => (activeLanguage ? api.getTrace(runId, activeLanguage) : Promise.resolve(null)),
    { interval: 8000, done: (data) => data !== null },
  )
  const replay = usePolling(
    () => (activeLanguage ? api.getReplay(runId, activeLanguage) : Promise.resolve(null)),
    { interval: 8000, done: (data) => data !== null },
  )

  const [step, setStep] = useState<ReplayStep | null>(null)
  const [stepError, setStepError] = useState<string | null>(null)

  const selectStep = async (index: number | null) => {
    if (index === null || !activeLanguage) return
    setStepError(null)
    try {
      const fetched = await api.getReplayStep(runId, activeLanguage, index)
      setStep(fetched)
    } catch (cause) {
      setStepError(cause instanceof Error ? cause.message : 'Unknown error')
    }
  }

  return (
    <Stack gap="lg">
      <PageHeader
        title={run ? `Runtime ${run.id.slice(0, 8)}` : 'Runtime'}
        description={
          run ? (
            <Group gap="sm">
              <StatusBadge status={run.status} />
              <Text size="sm" c="dimmed">
                {formatDate(run.created_at)}
              </Text>
            </Group>
          ) : (
            'Loading runtime run…'
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
        <Alert color="red" title="Failed to load runtime run">
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
            <StatCard label="Languages" value={run.languages.join(', ') || '—'} />
          </Group>

          {run.error ? (
            <Alert color="red" title="Runtime error">
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

          {trace.data ? (
            <>
              <SectionCard
                title="Execution trace"
                subtitle={
                  activeLanguage
                    ? `${activeLanguage} · ${trace.data.event_count} events in ${formatDuration(trace.data.duration_seconds)}`
                    : undefined
                }
                delay={60}
              >
                {trace.data.exception ? (
                  <Alert
                    color="red"
                    title={`${trace.data.exception.type}: ${trace.data.exception.message}`}
                    mb="sm"
                  />
                ) : null}
                <CodeViewer
                  title="stdout"
                  code={trace.data.stdout || '// no output'}
                  maxHeight={180}
                />
                <CodeViewer
                  title="stderr"
                  code={trace.data.stderr || '// no error output'}
                  maxHeight={180}
                />
              </SectionCard>

              <SectionCard
                title="Replay"
                subtitle="Step through the captured trace event by event"
                delay={120}
              >
                {stepError ? (
                  <Alert color="red" title="Failed to load step">
                    {stepError}
                  </Alert>
                ) : null}

                {step ? (
                  <ReplayStepView
                    step={step}
                    onSelect={selectStep}
                    hasPrevious={step.previous_index !== null}
                    hasNext={step.next_index !== null}
                  />
                ) : replay.data && replay.data.first_index !== null ? (
                  <>
                    <Button
                      size="xs"
                      variant="light"
                      color="brand"
                      onClick={() => void selectStep(replay.data?.first_index ?? null)}
                      mb="sm"
                    >
                      Start replay
                    </Button>
                    <Text size="sm" c="dimmed">
                      {replay.data.total_events} events · max stack depth {replay.data.max_stack_depth} ·{' '}
                      {Object.entries(replay.data.count_by_type)
                        .map(([type, count]) => `${type}×${count}`)
                        .join(' · ')}
                    </Text>
                  </>
                ) : (
                  <Text size="sm" c="dimmed">
                    No replay steps available.
                  </Text>
                )}
              </SectionCard>
            </>
          ) : trace.error ? (
            <Alert color="red" title="Failed to load trace">
              {trace.error}
            </Alert>
          ) : null}
        </>
      ) : null}
    </Stack>
  )
}

interface ReplayStepViewProps {
  step: ReplayStep
  onSelect: (index: number | null) => void
  hasPrevious: boolean
  hasNext: boolean
}

function ReplayStepView({ step, onSelect, hasPrevious, hasNext }: ReplayStepViewProps) {
  const { event } = step
  const variables = Object.entries(event.variables ?? {})
  return (
    <Stack gap="sm">
      <Group justify="space-between" gap="md" wrap="wrap">
        <Group gap="sm">
          <Text size="sm" fw={600} style={{ fontFamily: 'var(--xmono)' }}>
            #{step.index + 1} / {step.total}
          </Text>
          <Text size="sm" c="brand" tt="uppercase" style={{ fontFamily: 'var(--xmono)' }}>
            {event.type}
          </Text>
        </Group>
        <Group gap="xs">
          <Button size="xs" variant="light" disabled={!hasPrevious} onClick={() => onSelect(step.previous_index)}>
            Prev
          </Button>
          <Button size="xs" variant="light" disabled={!hasNext} onClick={() => onSelect(step.next_index)}>
            Next
          </Button>
        </Group>
      </Group>
      <Text size="sm" c="dimmed" style={{ fontFamily: 'var(--xmono)' }}>
        {event.filename}:{event.lineno} · {event.function} (depth {event.depth})
      </Text>
      {event.exception ? (
        <Alert color="red" title="Exception">
          {event.exception}
        </Alert>
      ) : null}
      {variables.length > 0 ? (
        <CodeViewer title="Variables" code={JSON.stringify(variables, null, 2)} maxHeight={220} />
      ) : (
        <Text size="xs" c="dimmed">
          No variable snapshot at this step.
        </Text>
      )}
    </Stack>
  )
}
