import { Alert, Button, Card, Group, Skeleton, Stack, Text, Title } from '@mantine/core'
import { useCallback, useEffect, useState } from 'react'
import { api, type HealthResponse } from '../api/client'

export function HomePage() {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const loadHealth = useCallback(async () => {
    const result = await api.health()
    setHealth(result)
  }, [])

  useEffect(() => {
    let cancelled = false
    api
      .health()
      .then((result) => {
        if (!cancelled) setHealth(result)
      })
      .catch((cause: unknown) => {
        if (!cancelled) {
          setError(cause instanceof Error ? cause.message : 'Unknown error')
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    await loadHealth()
    setLoading(false)
  }, [loadHealth])

  return (
    <Stack p="md" gap="lg">
      <Title order={2}>Dashboard</Title>
      <Text c="dimmed">Upload a repository to begin an explainable debugging analysis.</Text>

      <Card withBorder>
        <Group justify="space-between" mb="xs">
          <Title order={4}>API Status</Title>
          <Button size="xs" variant="light" onClick={() => void refresh()}>
            Refresh
          </Button>
        </Group>

        {loading ? (
          <Skeleton height={48} />
        ) : error ? (
          <Alert color="red" title="Backend unreachable">
            {error}
          </Alert>
        ) : health ? (
          <Group gap="xl">
            <StatusItem label="Status" value={health.status} />
            <StatusItem label="App" value={health.app} />
            <StatusItem label="Version" value={health.version} />
            <StatusItem label="Environment" value={health.environment} />
          </Group>
        ) : null}
      </Card>
    </Stack>
  )
}

function StatusItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <Text size="xs" c="dimmed">
        {label}
      </Text>
      <Text fw={600}>{value}</Text>
    </div>
  )
}
