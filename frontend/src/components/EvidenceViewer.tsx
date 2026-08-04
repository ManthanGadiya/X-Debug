import { Box, Divider, Group, Stack, Text } from '@mantine/core'
import type { EvidenceReference, EvidenceSchema } from '../api/client'
import { formatScore } from '../utils/format'

type EvidenceItem = EvidenceSchema | EvidenceReference

interface EvidenceViewerProps {
  items: EvidenceItem[]
  title?: string
  emptyLabel?: string
}

function isReference(item: EvidenceItem): item is EvidenceReference {
  return 'artifact' in item
}

/** Renders a scored list of evidence with its source and description. */
export function EvidenceViewer({
  items,
  title = 'Evidence',
  emptyLabel = 'No evidence',
}: EvidenceViewerProps) {
  return (
    <Box>
      <Text size="sm" fw={600} mb={4}>
        {title}
      </Text>
      {items.length === 0 ? (
        <Text size="sm" c="dimmed">
          {emptyLabel}
        </Text>
      ) : (
        <Stack gap={0}>
          {items.map((item, index) => (
            <Box key={`${item.source}-${index}`}>
              {index > 0 ? <Divider my="xs" /> : null}
              <Group justify="space-between" gap="md">
                <Text size="sm" fw={600}>
                  {item.source}
                </Text>
                <Text size="sm" c="dimmed">
                  {formatScore(item.score)}
                </Text>
              </Group>
              <Text size="sm" c="dimmed">
                {item.description}
              </Text>
              {isReference(item) && item.artifact ? (
                <Text size="xs" c="dimmed">
                  artifact: {item.artifact}
                </Text>
              ) : null}
            </Box>
          ))}
        </Stack>
      )}
    </Box>
  )
}
