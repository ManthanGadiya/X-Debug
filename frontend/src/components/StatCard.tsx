import { Card, Stack, Text } from '@mantine/core'

interface StatCardProps {
  label: string
  value: string
  hint?: string
  tone?: 'default' | 'brand' | 'signal' | 'danger'
}

const TONE_COLORS: Record<NonNullable<StatCardProps['tone']>, string> = {
  default: 'var(--mantine-color-text)',
  brand: 'var(--mantine-color-brand-4)',
  signal: 'var(--mantine-color-signal-4)',
  danger: 'var(--mantine-color-red-4)',
}

/** An instrument-style readout: a large monospace value under a small label. */
export function StatCard({ label, value, hint, tone = 'default' }: StatCardProps) {
  return (
    <Card p="md" style={{ minWidth: 140 }}>
      <Stack gap={2}>
        <Text
          size="xs"
          c="dimmed"
          tt="uppercase"
          style={{ fontFamily: 'var(--xmono)', letterSpacing: '0.12em' }}
        >
          {label}
        </Text>
        <Text
          size="xl"
          fw={600}
          style={{ fontFamily: 'var(--xmono)', color: TONE_COLORS[tone] }}
        >
          {value}
        </Text>
        {hint ? (
          <Text size="xs" c="dimmed">
            {hint}
          </Text>
        ) : null}
      </Stack>
    </Card>
  )
}
