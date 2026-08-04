import { Group, Text } from '@mantine/core'
import type { RunStatus } from '../api/client'

const STATUS_DOT: Record<RunStatus, { color: string; pulse?: boolean }> = {
  queued: { color: '#8f9ea9' },
  running: { color: '#00b5dd', pulse: true },
  ready: { color: '#1cc57f' },
  failed: { color: '#fa5252' },
}

interface StatusBadgeProps {
  status: string
}

/** A signal-light status indicator: colored dot + uppercase label. */
export function StatusBadge({ status }: StatusBadgeProps) {
  const normalized = status.toLowerCase() as RunStatus
  const dot = STATUS_DOT[normalized] ?? { color: '#8f9ea9' }
  const display = STATUS_DOT[normalized] ? status.toLowerCase() : status

  return (
    <Group gap={6} wrap="nowrap">
      <span
        className={dot.pulse ? 'xd-pulse' : undefined}
        style={{
          width: 8,
          height: 8,
          borderRadius: '50%',
          background: dot.color,
          boxShadow: `0 0 8px ${dot.color}`,
          flexShrink: 0,
        }}
      />
      <Text
        size="xs"
        tt="uppercase"
        fw={500}
        style={{
          fontFamily: 'var(--xmono)',
          letterSpacing: '0.08em',
          color: 'var(--mantine-color-text)',
        }}
      >
        {display}
      </Text>
    </Group>
  )
}
