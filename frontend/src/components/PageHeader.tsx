import { Group, Stack, Text, Title } from '@mantine/core'
import type { ReactNode } from 'react'

interface PageHeaderProps {
  title: string
  description?: ReactNode
  actions?: ReactNode
}

/** Standard page header with an indexed section label and optional actions. */
export function PageHeader({ title, description, actions }: PageHeaderProps) {
  return (
    <Stack gap={2} className="xd-reveal" mb="lg">
      <Text
        size="xs"
        c="brand"
        tt="uppercase"
        style={{ fontFamily: 'var(--xmono)', letterSpacing: '0.18em' }}
      >
        {title.toUpperCase()}
      </Text>
      <Group justify="space-between" align="flex-end" wrap="wrap" gap="md">
        <div>
          <Title order={2} mb={0}>
            {title}
          </Title>
          {description ? (
            <Text c="dimmed" size="sm" mt={4} maw={720}>
              {description}
            </Text>
          ) : null}
        </div>
        {actions ? <Group gap="sm">{actions}</Group> : null}
      </Group>
    </Stack>
  )
}
