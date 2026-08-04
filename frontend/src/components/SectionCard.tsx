import { Card, Group, Stack, Text } from '@mantine/core'
import type { ReactNode } from 'react'

interface SectionCardProps {
  title: string
  subtitle?: string
  actions?: ReactNode
  children: ReactNode
  delay?: number
}

/** A titled panel used to group related content on a page. */
export function SectionCard({ title, subtitle, actions, children, delay = 0 }: SectionCardProps) {
  return (
    <Card p="lg" className="xd-reveal" style={delay ? { animationDelay: `${delay}ms` } : undefined}>
      <Group justify="space-between" align="flex-start" mb="sm" wrap="wrap" gap="sm">
        <div>
          <Text size="sm" fw={600}>
            {title}
          </Text>
          {subtitle ? (
            <Text size="xs" c="dimmed">
              {subtitle}
            </Text>
          ) : null}
        </div>
        {actions ? <Group gap="xs">{actions}</Group> : null}
      </Group>
      <Stack gap="md">{children}</Stack>
    </Card>
  )
}
