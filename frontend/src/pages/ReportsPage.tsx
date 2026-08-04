import { Alert, Button, Group, Select, Stack, Text, Timeline } from '@mantine/core'
import { useState } from 'react'
import { api, type ExplanationDetail, type LocalizationDetail } from '../api/client'
import { CodeViewer } from '../components/CodeViewer'
import { EvidenceViewer } from '../components/EvidenceViewer'
import { PageHeader } from '../components/PageHeader'
import { SectionCard } from '../components/SectionCard'
import { StatCard } from '../components/StatCard'
import { usePolling } from '../hooks/usePolling'

export function ReportsPage() {
  const projects = usePolling(() => api.listProjects(), { interval: 15000 })
  const [projectId, setProjectId] = useState<string | null>(null)

  const localization = usePolling(
    () => (projectId ? api.getLocalization(projectId) : Promise.resolve(null)),
    { interval: 8000, done: (data) => data !== null && data.status !== 'running' },
  )
  const explanation = usePolling(
    () => (projectId ? api.getExplanation(projectId) : Promise.resolve(null)),
    { interval: 8000, done: (data) => data !== null && data.status !== 'running' },
  )

  const [running, setRunning] = useState<'localize' | 'explain' | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  const runLocalization = async () => {
    if (!projectId) return
    setRunning('localize')
    setActionError(null)
    try {
      await api.runLocalization(projectId)
      await localization.refresh()
      await explanation.refresh()
    } catch (cause) {
      setActionError(cause instanceof Error ? cause.message : 'Unknown error')
    } finally {
      setRunning(null)
    }
  }

  const runExplanation = async () => {
    if (!projectId) return
    setRunning('explain')
    setActionError(null)
    try {
      await api.runExplanation(projectId)
      await explanation.refresh()
    } catch (cause) {
      setActionError(cause instanceof Error ? cause.message : 'Unknown error')
    } finally {
      setRunning(null)
    }
  }

  const selected = projects.data?.find((project) => project.id === projectId)

  return (
    <Stack gap="lg">
      <PageHeader
        title="Reports"
        description="Explainable debug reports for a project: root-cause localization, then a natural-language explanation with evidence."
        actions={
          <Group gap="xs">
            <Select
              size="xs"
              placeholder="Select project"
              data={(projects.data ?? []).map((project) => ({
                value: project.id,
                label: project.name,
              }))}
              value={projectId}
              onChange={setProjectId}
              clearable
            />
            <Button
              size="xs"
              variant="light"
              color="brand"
              disabled={!projectId}
              loading={running === 'localize'}
              onClick={() => void runLocalization()}
            >
              Localize
            </Button>
            <Button
              size="xs"
              variant="light"
              color="brand"
              disabled={!projectId}
              loading={running === 'explain'}
              onClick={() => void runExplanation()}
            >
              Explain
            </Button>
          </Group>
        }
      />

      {actionError ? (
        <Alert color="red" title="Failed to run report step">
          {actionError}
        </Alert>
      ) : null}

      {!projectId ? (
        <SectionCard title="Select a project" delay={60}>
          <Text size="sm" c="dimmed">
            Choose a project above to generate its debug report.
          </Text>
        </SectionCard>
      ) : (
        <>
          <SectionCard
            title="Root-cause localization"
            subtitle={
              selected
                ? `Candidate ranking for ${selected.name}`
                : 'Candidate ranking over the knowledge graph'
            }
            delay={60}
            actions={
              localization.data?.resolved ? (
                <Text size="sm" c="signal" tt="uppercase" style={{ fontFamily: 'var(--xmono)' }}>
                  Resolved
                </Text>
              ) : undefined
            }
          >
            {localization.error ? (
              <Alert color="red" title="Failed to load localization">
                {localization.error}
              </Alert>
            ) : localization.data ? (
              <LocalizationReport data={localization.data} />
            ) : (
              <Text size="sm" c="dimmed">
                No localization yet — press Localize to rank root-cause candidates.
              </Text>
            )}
          </SectionCard>

          <SectionCard
            title="Explanation"
            subtitle="Why the failure happens, with evidence"
            delay={120}
          >
            {explanation.error ? (
              <Alert color="red" title="Failed to load explanation">
                {explanation.error}
              </Alert>
            ) : explanation.data ? (
              <ExplanationReport data={explanation.data} />
            ) : (
              <Text size="sm" c="dimmed">
                No explanation yet — press Explain to generate one.
              </Text>
            )}
          </SectionCard>
        </>
      )}
    </Stack>
  )
}

function LocalizationReport({ data }: { data: LocalizationDetail }) {
  const root = data.root_cause
  return (
    <Stack gap="md">
      <Group gap="md" wrap="wrap">
        <StatCard
          label="Confidence"
          value={`${Math.round(data.confidence * 100)}%`}
          tone={data.confidence >= 0.7 ? 'signal' : 'default'}
        />
        <StatCard label="Candidates" value={String(data.candidates.length)} />
        <StatCard
          label="Resolved"
          value={data.resolved ? 'YES' : 'NO'}
          tone={data.resolved ? 'signal' : 'danger'}
        />
      </Group>

      <Text size="sm" c="dimmed">
        {data.summary}
      </Text>

      {root ? (
        <CodeViewer
          title={`Root cause: ${root.label}`}
          code={[`score=${root.score.toFixed(3)}`, `kind=${root.kind}`, '', root.reason].join('\n')}
          maxHeight={200}
        />
      ) : null}

      <EvidenceViewer
        items={data.candidates.flatMap((candidate) =>
          candidate.evidence.map((evidence) => ({
            source: `${candidate.label} · ${evidence.description}`,
            description: evidence.description,
            score: evidence.score,
          })),
        )}
        title="Candidate evidence"
        emptyLabel="No candidate evidence recorded."
      />
    </Stack>
  )
}

function ExplanationReport({ data }: { data: ExplanationDetail }) {
  return (
    <Stack gap="md">
      <Group gap="md" wrap="wrap">
        <StatCard label="Confidence" value={`${Math.round(data.confidence * 100)}%`} />
        <StatCard label="Evidence" value={String(data.evidence.length)} />
      </Group>

      <Text size="sm">{data.why}</Text>

      {data.root_cause ? (
        <CodeViewer title="Root cause" code={data.root_cause} maxHeight={160} />
      ) : null}

      {data.where.length > 0 ? (
        <SectionCard title="Where" subtitle="Relevant source locations" delay={0}>
          <Timeline active={data.where.length - 1} bulletSize={12} lineWidth={2}>
            {data.where.map((location) => (
              <Timeline.Item
                key={`${location.file}:${location.line}`}
                title={
                  <Text size="sm" style={{ fontFamily: 'var(--xmono)' }}>
                    {location.function}
                    {location.cls ? ` (${location.cls})` : ''}
                  </Text>
                }
              >
                <Text size="xs" c="dimmed">
                  {location.file}
                  {location.line !== null ? `:${location.line}` : ''}
                </Text>
              </Timeline.Item>
            ))}
          </Timeline>
        </SectionCard>
      ) : null}

      <EvidenceViewer
        items={data.evidence.map((evidence) => ({
          source: evidence.source,
          description: evidence.description,
          score: evidence.score,
        }))}
        title="Evidence"
        emptyLabel="No evidence recorded."
      />
    </Stack>
  )
}
